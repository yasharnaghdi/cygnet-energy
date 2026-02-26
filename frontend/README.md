# Cygnet Frontend Developer Guide

This frontend replaces the Streamlit dashboard with a React + TypeScript app.

## Stack

- Vite + React 18 + TypeScript
- Mantine UI
- TanStack Query for server state
- Zustand for session context (zone, date range, persona, scenario)
- Axios for API client

## Prerequisites

- Node.js 20+ and npm
- Python backend running locally
- Optional for AI reports:
  - Ollama local server, or
  - Hugging Face extra dependencies in backend, or
  - OpenAI API key

## Run Locally

1. Install frontend dependencies:

```bash
cd frontend
npm install
```

2. Start backend (repo root):

```bash
poetry run uvicorn src.api.main:app --host 127.0.0.1 --port 8001
```

3. Start frontend:

```bash
cd frontend
npm run dev
```

Frontend runs on `http://localhost:3000`.

## Environment

- Development: [`.env.development`](/Users/yasharnaghdi/code/energy/cygnet-energy/frontend/.env.development)
- Production: [`.env.production`](/Users/yasharnaghdi/code/energy/cygnet-energy/frontend/.env.production)

In development, API calls use Vite proxy (`/api` -> `127.0.0.1:8001`).

## Date/Zone Source Of Truth

The shared context in [sessionStore.ts](/Users/yasharnaghdi/code/energy/cygnet-energy/frontend/src/store/sessionStore.ts) is the single source of truth:

- `zone`
- `dateRange`
- `persona`
- `scenario`

Sidebar controls update this store, and all pages consume the same values:

- Generation page queries data for the selected zone/range
- Ingestion page fetches for the same zone/range
- AI Insights report request carries the same zone/range and generation context

## AI Report Backends (Including Local LLMs)

AI Insights supports selecting backend + model directly from UI:

- `ollama` (local)
- `huggingface` (local/inference)
- `openai`
- `fallback`

The UI always exposes these backend choices even if backend-status reports fallback-only.

### Ollama path

```bash
ollama pull llama3.2:3b-instruct-q8_0
ollama serve
```

Then in AI Insights:

- Backend: `Ollama (Local)`
- Model override: your local model name (for example `llama3.2:3b-instruct-q8_0`)

### Hugging Face path

Install backend extras:

```bash
poetry install --extras llm
```

Then choose `Hugging Face (Local)` and set model override if needed.

### OpenAI path

Set in backend `.env`:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional)

Then choose `OpenAI` in AI Insights.

## Validation Commands

```bash
cd frontend
npx tsc --noEmit
npm run build
```

## Troubleshooting

- `Network Error` or timeout:
  - Verify backend is running on `127.0.0.1:8001`.
- `500` on generation history:
  - Validate legacy generation route + DB schema compatibility.
- AI shows fallback template:
  - Check selected backend/model in UI.
  - Ensure local LLM service is up (`ollama serve`) or required backend env/deps are present.
