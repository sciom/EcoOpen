# EcoOpen LLM — PDF Scientific Data Extractor

Modern FastAPI backend with a Vue 3 frontend for extracting structured information from scientific PDFs. The legacy Streamlit app and CLI scripts have been removed.

## Features

- DOI and Title extraction (validated; no guesses)
- Data/Code availability statements and licenses
- Data/Code links with repair and de-duplication
- Single-file analyze and batch jobs with progress
- CSV export for batch results

## What's new (core reliability and extraction quality)

- Domain-specific errors ensure functional issues (invalid PDF, missing embeddings, LLM outages) are surfaced clearly instead of generic API errors.
- New synchronous analyze mode that reads and analyzes a PDF without requiring MongoDB.
- Context repair: expands extracted availability statements to full paragraph/sentence boundaries (no truncated mid-sentence spans).
- URL repair: reconstructs and normalizes URLs broken by line breaks or hyphenation; trims trailing punctuation; deduplicates and validates links.
- Graceful degradation: if the LLM endpoint is unavailable, deterministic heuristics still extract useful signals.

## Quick start: Analyze a PDF (auth required)

All analyze endpoints now require authentication. First, create a user and get a token:

```bash
curl -sS -X POST \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"secret"}' \
  "http://localhost:8000/auth/register"

# or login
TOKEN=$(curl -sS -X POST \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"secret"}' \
  "http://localhost:8000/auth/login" | jq -r .access_token)
```

Analyze a single PDF synchronously by calling the API with `mode=sync` and the bearer token:

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/paper.pdf;type=application/pdf" \
  "http://localhost:8000/analyze?mode=sync"
```

The response is a JSON with fields like `title`, `doi`, `data_availability_statement`, `code_availability_statement`, `data_links`, and `code_links`.

Troubleshooting:

- Embedding model missing (Ollama): You'll get `400` with `code: embed_model_missing`. Install:

  ```bash
  ollama pull nomic-embed-text
  ```

- LLM endpoint unavailable: You'll get `502` when the agent is required; otherwise the service falls back to deterministic extraction where possible.
- Invalid/corrupted PDF: You'll get `400` with a clear message.

## Prerequisites

- Python 3.10+
- Node.js 18+
- Optional local embeddings: Ollama running with `nomic-embed-text` (only if you rely on local embedding; otherwise remote agent can still extract with reduced recall)

## Setup

### Python environment

- Option A (recommended): Conda

  ```bash
  ./setup_conda.sh            # creates env 'ecoopen-llm' and installs deps
  conda activate ecoopen-llm
  ```

- Option B: Pip

  ```bash
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  ```

### Configuration (optional but recommended)

```bash
cp .env.example .env
# Edit .env to set AGENT_BASE_URL / AGENT_API_KEY, and OLLAMA_* if using local embeddings
```

## Run

### Run locally (no Docker)

#### Service (MongoDB)

- Local install (MongoDB 6+): `mongod --dbpath /path/to/db`
- Or skip entirely and use `mode=sync` for single-file analysis without Mongo.

#### Backend (FastAPI)

```bash
./run_api.sh
```

The API will be available at <http://localhost:8000>
Endpoints:

- `GET /health` — status, agent and embeddings reachability
- `GET /config` — runtime caps (max file size, models)
- `POST /analyze` — multipart form with `file=<PDF>`
- `POST /analyze/batch` — multipart form with `files=<PDF>...`
- `GET /export/csv/{job_id}` — CSV export for batch

#### Background Worker
A MongoDB-backed in-process worker starts automatically with the FastAPI app and polls for documents with status `queued`.

Notes:

- Single analyze marks the document queued and waits up to 180s for completion (then falls back to synchronous processing if still pending).
- Batch analyze processes documents asynchronously; progress and results are stored in MongoDB.
- Concurrency controlled via `QUEUE_CONCURRENCY` in `.env`.

#### Frontend (Vue 3 + Vite)

```bash
cd frontend
npm install
npm run dev
```
Open <http://localhost:5173>
If your API uses a non-default URL, create `frontend/.env`:

```bash
VITE_API_BASE=http://localhost:8000
```

## Testing
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v
```

## Development

### Code Quality Tools

```bash
# Format code with black
black app/ tests/

# Sort imports
isort app/ tests/

# Lint with flake8
flake8 app/ tests/

# Type checking with mypy
mypy app/
```

### Project Structure

```text
EcoOpen_LLM/
├── app/
│  ├── core/config.py
│  ├── models/schemas.py
│  ├── routes/{health.py, analyze.py, export.py}
│  ├── services/{agent.py, jobs.py}
│  └── main.py
├── frontend/
│  ├── src/
│  ├── dist/           # built artifacts (ignored in git)
│  └── ...
├── tests/
│  └── test_api.py
├── .env.example
├── AGENT_PLAN.md
├── requirements.txt
├── run_api.sh
├── setup_conda.sh
└── README.md
```

## Env Vars (.env)
- `AGENT_BASE_URL` — OpenAI-compatible base URL (e.g., `https://.../v1`)
- `AGENT_MODEL` — agent model id (include the full tag when required)
  - Examples: `llama3.1`, `gpt-oss:120b`, `nomic-embed-text:latest`
- `AGENT_API_KEY` — optional bearer key
- `OLLAMA_HOST` — local Ollama URL (default `http://localhost:11434`)
- `OLLAMA_MODEL` — local LLM model (default `phi3:mini`)
- `OLLAMA_EMBED_MODEL` — embedding model (default `nomic-embed-text`)
- `MAX_FILE_SIZE_MB` — upload cap (default 50)
- `CORS_ORIGINS` — allowed origins list
- `REPAIR_CONTEXT_ENABLED` — expand statements to paragraph/sentence (default: true)
- `REPAIR_URLS_ENABLED` — repair and normalize URLs (default: true)

## Behavior Notes
- Chroma telemetry disabled via `ChromaSettings(anonymized_telemetry=False)`.
- With URL repair on, the service attempts to reconstruct split or hyphenated links and trims trailing punctuation before validation.
- Data links are filtered to primary repositories/DOI hosts; general website mentions are excluded by design.
- Batch jobs run sequentially and expose progress.

## Contributing
Issues and PRs are welcome.

## License
Open source. See the repository license file.
