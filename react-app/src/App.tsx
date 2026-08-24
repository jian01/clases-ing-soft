import { useState, useEffect, SubmitEvent } from "react";
import "./App.css";

const API_BASE = "/api";
const TIMEOUT_MS = 2000;

type HealthStatus = "unknown" | "checking" | "ok" | "error";

function fetchWithTimeout(url: string, options: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  return fetch(url, { ...options, signal: controller.signal }).finally(() =>
    clearTimeout(timer)
  );
}

async function fetchEntries(): Promise<string[]> {
  const res = await fetchWithTimeout(`${API_BASE}/read`);
  if (!res.ok) throw new Error(`Failed to fetch entries: ${res.status}`);
  const data = await res.json();
  return data.content as string[];
}

async function saveEntry(content: string): Promise<void> {
  const res = await fetch(`${API_BASE}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(`Failed to save entry: ${res.status}`);
}

async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

export default function App() {
  const [entries, setEntries] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthStatus>("unknown");

  async function load() {
    try {
      setError(null);
      const data = await fetchEntries();
      setEntries(data);
      setHealth("ok");
    } catch (err) {
      const message =
        err instanceof Error && err.name === "AbortError"
          ? "Backend no responde (timeout)"
          : err instanceof Error
          ? err.message
          : "Unknown error";
      setError(message);
      setHealth("error");
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  async function handleHealthCheck() {
    setHealth("checking");
    const ok = await checkHealth();
    setHealth(ok ? "ok" : "error");
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      await saveEntry(trimmed);
      setInput("");
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      alert(`No se pudo guardar la entrada: ${message}`);
    } finally {
      setLoading(false);
    }
  }

  const healthLabel: Record<HealthStatus, string> = {
    unknown: "Check backend",
    checking: "Checking...",
    ok: "Backend: OK",
    error: "Backend: unreachable",
  };

  return (
    <div className="container">
      <div className="header">
        <h1>Storage App</h1>
        <button
          onClick={handleHealthCheck}
          disabled={health === "checking"}
          className={`button button-health button-health--${health}`}
        >
          {healthLabel[health]}
        </button>
      </div>

      <form onSubmit={handleSubmit} className="form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type something to store..."
          disabled={loading}
          className="input"
        />
        <button type="submit" disabled={loading || !input.trim()} className="button">
          {loading ? "Saving..." : "Save"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      <div className="list-header">
        <span className="list-title">Entries</span>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="button button-secondary"
        >
          {refreshing ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <ul className="list">
        {entries.length === 0 ? (
          <li className="empty">No entries yet.</li>
        ) : (
          entries.map((entry, i) => (
            <li key={i} className="list-item">
              {entry}
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
