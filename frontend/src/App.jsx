import { useState } from "react";
import "./App.css";

// Base URL of our FastAPI backend. Docker Compose publishes the backend's
// port 8000 to your host machine, so the browser (running on your host,
// not inside a container) reaches it via plain localhost.
const API_URL = "http://localhost:8000";

function App() {
  // --- State ---
  const [file, setFile] = useState(null);               // file picked by the user
  const [uploadStatus, setUploadStatus] = useState(""); // feedback after upload
  const [question, setQuestion] = useState("");         // current text in the input box
  const [messages, setMessages] = useState([]);         // chat history
  const [isLoading, setIsLoading] = useState(false);    // true while waiting on /chat/
  const [error, setError] = useState("");               // user-facing error message

  // --- Handlers ---

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setUploadStatus("");
  };

  const handleUpload = async () => {
    if (!file) {
      setUploadStatus("Choose a .txt or .md file first.");
      return;
    }

    // FormData is how the browser sends a file as multipart/form-data,
    // which matches what FastAPI's UploadFile expects on the other end.
    const formData = new FormData();
    formData.append("file", file);

    try {
      setUploadStatus("Uploading...");
      const res = await fetch(`${API_URL}/upload/`, {
        method: "POST",
        body: formData,
        // No Content-Type header here on purpose since the browser sets the
        // correct multipart boundary automatically when you pass FormData.
      });

      if (!res.ok) {
        throw new Error(`Server responded with ${res.status}`);
      }

      const data = await res.json();
      setUploadStatus(data.message);
    } catch (err) {
      setUploadStatus("Upload failed. Is the backend container running?");
      console.error(err);
    }
  };

  const handleAsk = async () => {
    if (!question.trim()) return;

    const userMessage = { role: "user", text: question };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setIsLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_URL}/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userMessage.text }),
      });

      if (!res.ok) {
        throw new Error(`Server responded with ${res.status}`);
      }

      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: data.answer, sources: data.sources },
      ]);
    } catch (err) {
      // This is the exact failure mode that I kept running into earlier in this project
      // Network failure, or the backend returning a 500. It would hang quietly
      // But now we catch it and show a user-facing error message
      setError("Error querying API. Check that the backend container is running and healthy.");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  // --- Render ---
  return (
    <div className="app">
      <h1>Notes Assistant</h1>

      <section className="upload-panel">
        <input type="file" accept=".txt,.md" onChange={handleFileChange} />
        <button onClick={handleUpload}>Upload notes</button>
        {uploadStatus && <p className="status">{uploadStatus}</p>}
      </section>

      <section className="chat-panel">
        <div className="messages">
          {messages.map((m, i) => (
            <div key={i} className={`message ${m.role}`}>
              <p>{m.text}</p>
              {m.sources && m.sources.length > 0 && (
                <p className="sources">Sources: {m.sources.join(", ")}</p>
              )}
            </div>
          ))}
          {isLoading && <p className="loading">Thinking...</p>}
        </div>

        {error && <p className="error">{error}</p>}

        <div className="input-row">
          <input
            type="text"
            value={question}
            placeholder="Ask something about your notes"
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          />
          <button onClick={handleAsk} disabled={isLoading}>
            Ask AI
          </button>
        </div>
      </section>
    </div>
  );
}

export default App;