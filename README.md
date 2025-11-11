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
- Configure (optional): `cp .env.example .env` and set `AGENT_BASE_URL`/`AGENT_MODEL` (and `JWT_SECRET` for production). For embeddings choose:
  - `EMBEDDINGS_BACKEND=endpoint` with `AGENT_EMBED_MODEL=<id>` to use the same OpenAI-compatible server for embeddings, or
  - `EMBEDDINGS_BACKEND=ollama` with `OLLAMA_HOST` and `OLLAMA_EMBED_MODEL` (e.g., `nomic-embed-text`).

## Run
- API: `./run_api.sh` → http://localhost:8000
- Frontend:
  - `cd frontend && npm install && npm run dev` → http://localhost:5173
  - To point the UI at a custom API URL, create `frontend/.env` with `VITE_API_BASE=http://localhost:8000`

## Deploy
- One‑shot deploy with systemd + nginx:
  - `./deploy.sh` (builds frontend, installs backend deps, reloads services)
  - Flags:
    - `SKIP_FRONTEND=1` skip building the frontend
    - `INSTALL_BACKEND=0` don’t (re)install Python deps
    - `DISABLE_CONFLICTING_SITES=0` keep other nginx sites
    - `PUBLIC_BASE=https://ecoopen.sciom.net` override public health url
- Verify:
  - Local: `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3290/health` → `200`
  - Public: `curl -s -o /dev/null -w '%{http_code}\n' "$PUBLIC_BASE/api/health"` → `200`

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

# Current user and admin flag
curl -sS -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/me
# → { "id": "...", "email": "you@example.com", "is_admin": false }
```

Admin emails are configured via `ADMIN_EMAILS` in environment or `.env` (comma‑separated addresses).

Frontend tip: the UI auto‑logs in after a successful registration and syncs admin/user id state from `/auth/me`.

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

## Testing
Run the test suite to verify functionality:
```bash
# Unit tests (no external services required)
pytest tests/ -v -m "not integration"

# Full workflow test (requires Ollama and LLM endpoint)
pytest tests/test_workflow_full.py -v -s
```

The full workflow test assesses extraction accuracy and performance on example PDFs. See `tests/README.md` for details.

## Troubleshooting
- Missing embeddings (Ollama): `ollama pull nomic-embed-text`
- No database? Use `mode=sync` for single-file analysis
- LLM endpoint down: service falls back to deterministic extraction when possible

## Contributing & License
Contributions are welcome via issues and PRs. This is an open‑source project; see the repository’s license file for details.
