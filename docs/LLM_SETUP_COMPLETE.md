# Complete Local LLM Setup

This project supports two local AI backends for report generation:

1. `ollama` (recommended): external local server
2. `huggingface`: in-process transformers

Selection priority is automatic: `ollama` -> `huggingface` -> `fallback`.

## Option 1: Ollama (Recommended)

Install:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Pull a model:

```bash
ollama pull phi3:mini
```

Run server:

```bash
ollama serve
```

Configure `.env`:

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=phi3:mini
AUTH_BYPASS_DEV=true
CYGNET_API_URL=http://127.0.0.1:8001
```

## Option 2: HuggingFace Transformers

Install optional dependencies:

```bash
poetry install --extras llm
```

Set model (example):

```bash
export HF_MODEL="TinyLlama/TinyLlama-1.1B-Chat-v1.0"
```

## API checks

Start API:

```bash
AUTH_BYPASS_DEV=true poetry run uvicorn src.api.main:app --port 8001
```

Check backend selection:

```bash
curl "http://127.0.0.1:8001/api/reports/backend-status"
```

Generate weighted report (new API path):

```bash
curl -X POST http://127.0.0.1:8001/api/reports/generate \
  -H "Content-Type: application/json" \
  -d '{
    "persona": "trader",
    "zone": "DE",
    "date_range": ["2026-02-16", "2026-02-23"],
    "scenario": "High Renewable",
    "parameter_weights": {
      "renewable_share": 0.5,
      "carbon": 0.3,
      "price": 0.1,
      "margin": 0.1
    }
  }'
```

Legacy compatibility path:

```bash
curl "http://127.0.0.1:8001/api/reports/generate?persona=trader&zone=DE"
```

Note: legacy `GET` does not carry scenario weights and should only be used as fallback.

## AI Insights frontend flow

The Streamlit AI Insights tab now uses:

1. Scenario selection (`Base Case`, `High Renewable`, `Grid Stress`, `Custom`)
2. Parameter selection (zone, date range, persona)
3. Report generation via `POST /api/reports/generate`

Timeout configuration:

- Backend Ollama call: `180s`
- Frontend report request: `200s`

## Streamlit troubleshooting for 404

If AI Insights shows `Report generation failed (404)`:

1. Ensure FastAPI process includes latest code and is restarted.
2. Ensure it is running on the same URL Streamlit targets.
3. Set explicit API URL in `.env`:

```bash
CYGNET_API_URL=http://127.0.0.1:8001
```

4. Restart Streamlit after changing environment variables.

## Streamlit troubleshooting for 405

If AI Insights shows `Report generation failed (405)`:

1. Backend is likely on an older build with only `GET /api/reports/generate`.
2. Restart FastAPI using current code.
3. Temporary behavior: UI retries legacy `GET`, but weighted scenario settings are ignored.
