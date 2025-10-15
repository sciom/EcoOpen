# Agent-Centric Migration Plan (Native, No Docker)

## Goals
- Replace Streamlit UI with FastAPI backend and Vue 3 + Tailwind frontend.
- Maintain original features: DOI, Title, Data/Code availability statements, Data/Code links, CSV export, batch processing.
- Move to an agent + tools architecture using an OpenAI-compatible agent endpoint.
- Native development (Python + Node), no containers.

## Model Endpoint
- Agent model: `gpt-oss:120b`
- Base URL: `https://teal-fast-suitably.ngrok-free.app/v1` (OpenAI-compatible)
- Configurable env: `AGENT_BASE_URL`, `AGENT_MODEL`, optional `AGENT_API_KEY`

## Backend (FastAPI)
- Endpoints:
  - `GET /health`: server + agent + embeddings reachability.
  - `GET /config`: caps (max file size, allowed types, model).
  - `POST /analyze` (multipart `file`): single result JSON.
  - `POST /analyze/batch` (multipart `files[]`): returns `job_id`.
  - `GET /jobs/{job_id}`: {status, progress, results?, error?}.
  - `GET /export/csv?job_id=...`: CSV export for batch.
- Cross-cutting:
  - CORS allowlist, gzip, request ID.
  - Limits: file size, MIME, filename sanitization; per-request temp dir; cleanup.
  - In-memory job store; sequential batch via `asyncio.Semaphore(1)`.

## Agent + Tools
- System prompt: "Extract only explicitly present scientific metadata from PDFs. Never invent. Return structured results."
- Tools:
  - `PdfLoad(file_path)` – full document load/validation.
  - `ChunkText(text, chunk_size, overlap)` – sliding-window chunks.
  - `BuildVectorStore(chunks, collection_name)` – per-request collection (no destructive deletes).
  - `SimilaritySearch(store_id, query, k)` – get contextual passages.
  - `LLMExtract(context, task)` – task-specific prompts: doi | title | data_stmt | code_stmt | data_license | code_license | links[data|code].
  - `DOILookupByTitle(title)` – Crossref strict matching.
  - `CSVExport(results[])` – CSV string/bytes.
  - `Cleanup(store_id, tmp_paths[])` – delete temporary artifacts.
- Orchestration (single): load → chunk → embed → search → extract → aggregate → DOI-by-title (optional) → cleanup.
- Orchestration (batch): sequential application per file with progress.
- Observability: step logs (tool, params summary, duration, outcome) for UI timeline.

## Data Models
- `PDFAnalysisResult`:
  - `title?`, `doi?`, `data_availability_statement?`, `code_availability_statement?`, `data_sharing_license?`, `code_license?`, `data_links[]`, `code_links[]`, `confidence_scores{}`.
- `BatchStatus`:
  - `job_id`, `status` (queued|running|done|error), `progress{current,total}`, `results[]?`, `error?`.
- `Problem`: `code`, `message`, `details?`, `trace_id`.

## CSV Schema
- Columns: `source_file, filename, title, doi, doi_from_title_search, data_availability_statement, code_availability_statement, data_sharing_license, code_license, data_links_count, code_links_count, data_links, code_links, error`.
- Values: explicit-only. Missing values are empty (no guesses).

## Anti-Hallucination Controls
- Prompt guardrails: "Only extract if explicitly present; return 'None' otherwise; never infer/paraphrase".
- Validation: DOI must start with `10.`; reasonable title length; URL regex + filtering; short responses rejected.
- If validation fails → field set to `None`.

## Frontend (Vue 3 + Tailwind)
- Single Analyze: drag/drop, progress timeline of agent steps, result cards (Title/DOI with doi.org link), lists of Data/Code links, expanders for statements/licenses, copy JSON.
- Batch: multi-upload, create job, poll status, summary table with counts, per-item details, CSV download.
- Settings: model fixed to `gpt-oss:120b` default, chunk size, health indicator; persisted in `localStorage`.
- API Client: Typed Axios; DTOs matching backend schemas; polling helper; toast errors.

## Native Setup
- Backend: `fastapi`, `uvicorn[standard]`, `python-multipart`, `pydantic-settings`, `httpx`, `pytest`, `pytest-asyncio`, `openai` (for OpenAI-compatible agent calls), keep `chromadb`, `langchain-community`, `pypdf`.
- Frontend: Vite + Vue 3 + TypeScript; Tailwind.
- Run:
  - Backend: `uvicorn app.main:app --reload --port 8000`
  - Frontend: `npm run dev` (proxy to `http://localhost:8000`)

## Implementation Steps
1) Define agent system prompt + anti-hallucination policies.
2) Implement Tools wrapping current analyzer pipeline pieces; remove destructive collection delete.
3) Integrate AgentRunner (OpenAI-compatible client) and step logs.
4) FastAPI endpoints for analyze, batch, jobs, CSV export, health, config.
5) Batch queue (sequential) + progress tracking.
6) Vue app pages: Single Analyze, Batch, Settings; API client.
7) Update requirements and README; remove Streamlit files when stable.

## Tests
- Non-hallucination: missing fields → None.
- Full-document coverage.
- Batch sequentiality and progress.
- CSV schema and values.

## Env Vars (.env example)
```
AGENT_BASE_URL=https://teal-fast-suitably.ngrok-free.app/v1
AGENT_MODEL=gpt-oss:120b
AGENT_API_KEY=changeme-if-required
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=phi3:mini
MAX_FILE_SIZE_MB=50
CORS_ORIGINS=http://localhost:5173
```

---

# Backend Patches Plan (2025-09)

## Reliability
- Disable Chroma telemetry everywhere using `ChromaSettings(anonymized_telemetry=False)`.
- Pass `base_url=settings.OLLAMA_HOST` to `Ollama` and `OllamaEmbeddings`.
- Health endpoint accepts embed model names with tag suffix (e.g., `:latest`).
- Analyze: convert missing embedding model to HTTP 400 with an actionable fix.

## Recall Improvements for Data/Code Availability
- Text cleaning before chunking:
  - De-hyphenate line breaks: `re.sub(r"(\w)-\n(\w)", r"\1\2", text)`.
  - Normalize whitespace and collapse excessive newlines.
- Deterministic extraction by headings (exact section capture):
  - Data headings: `data availability( statement)?`, `availability of data( and materials)?`, `data and materials availability`, `data accessibility`.
  - Code headings: `code availability`, `software availability`, `source code availability`, `code and data availability`.
  - Capture 1–3 paragraphs following the heading until the next heading/blank gap.
- Phrase-based fallback when no headings:
  - Data phrases: `data (are|is) available`, `have been deposited`, `can be accessed`, `available at|from`, `dataset available`, `supplementary data are available`, `upon request`.
  - Code phrases: `code (is|are) available`, `source code is available`, `repository at`, `scripts available`, `software available`, `GitHub|GitLab|Bitbucket`.
  - Extract the surrounding paragraph.
- Retrieval tuning when heuristics fail:
  - Larger chunks `1500–2000` with overlap `200–300` to avoid splitting statements.
  - Increase similarity `k` to `6–8`.
  - Expanded query bags for data/code search.
- Link extraction from statements into `data_links`/`code_links`.

## Files To Update
- `app/services/agent.py`
  - Add `base_url` for embeddings; telemetry-off Chroma client.
  - Normalize text; deterministic extraction; expanded search; larger k.
  - Raise clear error if embedding model missing.
- `pdf_analyzer.py`
  - Use `settings` for models/host and telemetry-off Chroma.
  - Same text normalization + deterministic extraction + link capture.
  - Raise clear error on missing embedding model.
- `app/routes/health.py`
  - Accept tag suffix on embed model names.
- `app/routes/analyze.py`
  - Convert missing-embed-model errors to HTTP 400 with a helpful message.

## Validation (manual)
- `/health` shows `degraded` when embed model missing; `ok` when present.
- Papers with clear “Data Availability”/“Code Availability” headings are extracted exactly.
- Papers with phrase forms (no headings) get captured; URLs are added to links fields.
- Existing fields (DOI, title) remain guarded.
