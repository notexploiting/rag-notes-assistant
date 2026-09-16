# rag-notes-assistant

## Project overview

A small Retrieval-Augmented Generation (RAG) app, where you upload plain-text (e.g. pdf, md) notes, ask questions about them, and get answers grounded in that content.

## Why this project exists

This project was built to gain hands-on experience designing and deploying a containerized RAG system from scratch. The motivation came directly from seeing internal AI tools, specifically an AI assistant developed within the University of Toronto's Department of Statistical Sciences, alongisde an enterprise platform used during my time at Travelers Insurance.

## Stack

-   **Frontend**: React (Vite)

-   **Backend**: FastAPI

-   **Database**: Implementing document ingestion, chunking, and vector similarity search using ChromaDB

-   **LLM**: Groq (OpenAI-compatible API), resolved dynamically at startup (model discovery fallback)

-   **Infrastructure**: Docker Compose with 3 services (frontend, backend, database), networking, persistent volumes, and startup race condition handling

## Running locally

1.  Duplicate '.env-template' and rename as '.env', then add your Groq API key from [https://console.groq.com/](https://console.groq.com/home)
2.  Run 'docker compose up –build'
3.  Open http://localhost:5173
4.  Choose file, press 'Upload notes', then ask away