"""
main.py - FastAPI backend for the RAG (Retrieval-Augmented Generation) assistant.

Responsibilities of this file:
1. Connect to the ChromaDB vector database (with a retry loop, since containers can finish starting up in any order).
2. Connect to Groq's OpenAI-compatible chat completion API.
3. Automatically detect which LLM model is currently available on your Groq account (providers frequently rename/retire models).
4. Expose two HTTP endpoints:
     - POST /upload/  -> accepts a text file, chunks it, embeds it, stores it
     - POST /chat/    -> accepts a question, retrieves relevant chunks, asks the LLM to answer using only that context
"""

import os
import uuid
import time

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import chromadb
from chromadb.utils import embedding_functions

from openai import OpenAI


# ---------------------------------------------------------------------------
# CREATE THE FASTAPI APP
# ---------------------------------------------------------------------------
app = FastAPI(title="RAG Notes Assistant")

# Allow the React frontend (a different origin/port) to call this API from the browser
# For now, allow everything instead of selecting exact URL's
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# CONNECT TO CHROMADB
# ---------------------------------------------------------------------------
# Why the retry loop exists:
# Docker Compose starts all containers at roughly the same time. FastAPI
# boots in well under a second, but ChromaDB takes a few seconds to be
# ready to accept connections. Without retrying, this backend would crash
# on its very first attempt to connect (startup race condition).
chroma_client = None
collection = None

for attempt in range(5):
    try:
        # "db" is the *service name* we'll give ChromaDB in docker-compose.yml.
        chroma_client = chromadb.HttpClient(host="db", port=8000)

        # Turns text into vectors so we can search by meaning (vs. just by keywords)
        # This downloads a small ONNX model the first time it runs.
        default_ef = embedding_functions.DefaultEmbeddingFunction()

        # Like "CREATE TABLE IF NOT EXISTS" for a vector collection.
        collection = chroma_client.get_or_create_collection(
            name="notes",
            embedding_function=default_ef,
        )
        print("Successfully connected to ChromaDB")
        break
    except Exception as e:
        print(f"Waiting for the database to wake up (attempt {attempt + 1}/5): {e}")
        time.sleep(3)

if collection is None:
    # Fail loudly on startup instead of limping along with a broken db conn
    # ... and confusing 500 errors later ...
    raise RuntimeError("Could not connect to ChromaDB after 5 attempts.")


# ---------------------------------------------------------------------------
# CONNECT TO GROQ (VIA THE OPENAI-COMPATIBLE CLIENT)
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is not set. Add it to your .env file "
        "in the project root before starting the backend"
    )

llm_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)


# ---------------------------------------------------------------------------
# DYNAMIC MODEL RESOLVER
# ---------------------------------------------------------------------------
# Why this exists: LLM providers retire and rename models often. Hardcoding
# a model string means your app silently breaks the day that model is
# deprecated. Instead, we ask Groq "what models can I actually use right
# now?" on startup and pick the first valid text (non-audio) model.
def get_best_available_model() -> str:
    try:
        available_models = llm_client.models.list().data
        for model in available_models:
            # Skip speech-to-text models (Whisper) since we only want chat models.
            if "whisper" not in model.id.lower():
                print(f"Auto-resolved active model: {model.id}")
                return model.id
    except Exception as e:
        print(f"Could not fetch model list from Groq: {e}")

    # Last-resort fallback if the lookup above fails entirely for some
    # reason (e.g. network issue). This string may itself be outdated by
    # the time you read this ... but this is just a safety net
    return "llama3-8b-8192"


ACTIVE_MODEL = get_best_available_model()


# ---------------------------------------------------------------------------
# REQUEST SCHEMA
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    """Shape of the JSON body the frontend sends to POST /chat/."""
    query: str


# ---------------------------------------------------------------------------
# ENDPOINT: UPLOAD A DOCUMENT
# ---------------------------------------------------------------------------
@app.post("/upload/")
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts a plain-text (.txt / .md) file, splits it into chunks on blank
    lines, and stores each chunk as a vector embedding in ChromaDB.
    """
    content = await file.read()

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Could not read file as UTF-8 text. Please upload a .txt or .md file.",
        )

    # Naive chunking: split on blank lines (paragraph breaks) and drop
    # fragments too short to be useful context. 
    # 
    # Note that a more advanced system might chunk by token count or use
    # overlapping windows so context isn't lost at chunk boundaries.
    chunks = [c.strip() for c in text.split("\n\n") if len(c.strip()) > 10]

    if not chunks:
        return {"message": "No usable text found in that file."}

    # Every chunk needs a unique ID, plus metadata so we can trace it back
    # to its source file when we display answers later.
    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"filename": file.filename} for _ in chunks]

    collection.add(documents=chunks, metadatas=metadatas, ids=ids)

    return {"message": f"Processed {len(chunks)} chunks from {file.filename}"}


# ---------------------------------------------------------------------------
# ENDPOINT: ASK A QUESTION (THE ACTUAL "RAG" STEP)
# ---------------------------------------------------------------------------
@app.post("/chat/")
async def chat_with_notes(request: QueryRequest):
    """
    Retrieval-Augmented Generation, in three steps:
      1. RETRIEVE - find the chunks most semantically similar to the question.
      2. AUGMENT  - stuff those chunks into the prompt as "context".
      3. GENERATE - ask the LLM to answer using only that context.
    """
    results = collection.query(query_texts=[request.query], n_results=3)

    documents = results["documents"][0] if results["documents"] else []
    context = "\n\n".join(documents)

    prompt = f"""You are a helpful assistant. Answer the question using ONLY
the context provided below. If the answer isn't in the context, say you
don't have enough information — do not make something up.

Context:
{context}

Question: {request.query}
"""

    response = llm_client.chat.completions.create(
        model=ACTIVE_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    # Collect the unique source filenames so the frontend can show which
    # document(s) the answer was grounded in.
    sources = []
    if results["metadatas"] and results["metadatas"][0]:
        sources = list({meta["filename"] for meta in results["metadatas"][0]})

    return {
        "answer": response.choices[0].message.content,
        "sources": sources,
    }