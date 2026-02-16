# Local LLM Setup (Ollama + AI Insights)

## 1) Install and run Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
ollama pull phi3:mini
ollama serve
```

Default endpoint: `http://localhost:11434`

## 2) Configure environment

Add to `.env`:

```bash
AUTH_BYPASS_DEV=true
CYGNET_API_URL=http://127.0.0.1:8001
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=phi3:mini
```

## 3) Start FastAPI

```bash
AUTH_BYPASS_DEV=true \
OLLAMA_BASE_URL=http://localhost:11434 \
OLLAMA_MODEL=phi3:mini \
poetry run uvicorn src.api.main:app --host 127.0.0.1 --port 8001
```

## 4) Verify backend status

```bash
curl -sS http://127.0.0.1:8001/api/reports/backend-status
```

Expected: `"backend":"ollama"` and the configured model name.

## 5) Verify weighted report generation (POST)

```bash
curl -sS -X POST http://127.0.0.1:8001/api/reports/generate \
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
  }' \
  --max-time 180
```

Expected: JSON response with `narrative`, `scenario`, and normalized `parameter_weights`.

## 6) Start Streamlit and run AI Insights

```bash
streamlit run src/ui/app.py
```

If your app entrypoint is `main_app.py`, use:

```bash
streamlit run main_app.py
```

Inside AI Insights:
1. Select scenario.
2. Select zone/date/persona.
3. Click `Run Analysis`.

## Timeout behavior

- Ollama generate timeout in backend: `180s`
- AI Insights frontend request timeout: `200s`

This avoids premature failures during CPU inference.

## Troubleshooting

1. `405 Method Not Allowed`:
   - UI is calling `POST` but backend is still old `GET` only.
   - Restart FastAPI with latest code.
   - UI includes a legacy GET fallback, but weighted scenario inputs are not applied in legacy mode.
2. `404 Not Found`:
   - `CYGNET_API_URL` is pointing to the wrong process/port.
3. Timeout:
   - Use a smaller model or shorter date window.
