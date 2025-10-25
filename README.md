# EcoOpen — PDF Scientific Data Extractor

FastAPI + Vue app that extracts structured research metadata from PDF papers: DOI/title, data/code availability statements, and cleaned/validated data/code links. Use it via a simple REST API or the bundled web UI.

## Highlights
- Accurate DOI/title (no guessing), availability statements, and link repair/deduplication
- Single-file synchronous mode (no database required)
- Batch jobs and CSV export when MongoDB is available
- Works with local Ollama or any OpenAI‑compatible endpoint

## Requirements
- Python 3.10+
- Node.js 18+
- Optional: MongoDB 6+ (for background jobs/batch)
- Optional: Ollama with `nomic-embed-text` for local embeddings (`ollama pull nomic-embed-text`)

## Install
- Backend (choose one)
  - Conda: `./setup_conda.sh && conda activate ecoopen-llm`
  - venv: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Configure (optional): `cp .env.example .env` and set `AGENT_BASE_URL`/`AGENT_MODEL` (and `JWT_SECRET` for production)

## Run
- API: `./run_api.sh` → http://localhost:8000
- Frontend:
  - `cd frontend && npm install && npm run dev` → http://localhost:5173
  - To point the UI at a custom API URL, create `frontend/.env` with `VITE_API_BASE=http://localhost:8000`

## Authenticate
All analyze endpoints require auth. Register or login to obtain a bearer token.

Password requirements: at least 8 characters and must include letters and numbers. Registration requires `password_confirm` to match `password`.

```bash
# Register (requires password_confirm)
curl -sS -X POST -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"Abcdef12","password_confirm":"Abcdef12"}' \
  http://localhost:8000/auth/register

# Login → TOKEN
TOKEN=$(curl -sS -X POST -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"Abcdef12"}' \
  http://localhost:8000/auth/login | jq -r .access_token)
```

Frontend tip: the UI auto‑logs in after a successful registration.

## Quick analyze
Analyze a single PDF synchronously (no MongoDB needed):

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/paper.pdf;type=application/pdf" \
  "http://localhost:8000/analyze?mode=sync"
```

Response includes `title`, `doi`, availability statements, and normalized `data_links`/`code_links`.

For batch processing and CSV export, run MongoDB and use the UI or `POST /analyze/batch`.

## Troubleshooting
- Missing embeddings (Ollama): `ollama pull nomic-embed-text`
- No database? Use `mode=sync` for single-file analysis
- LLM endpoint down: service falls back to deterministic extraction when possible

## Contributing & License
Contributions are welcome via issues and PRs. This is an open‑source project; see the repository’s license file for details.
