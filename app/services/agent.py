import logging
import re
from typing import Dict, List, Optional
from uuid import uuid4

import chromadb
import httpx

try:
    import pdfplumber  # type: ignore
except ImportError:  # pragma: no cover - pdfplumber provided via requirements
    pdfplumber = None
from chromadb.config import Settings as ChromaSettings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.embeddings import Embeddings

from app.core.config import settings
from app.core.errors import (
    EmbeddingModelMissingError,
    InvalidPDFError,
    LLMServiceError,
)
from app.core.validation import validate_doi
from app.models.schemas import PDFAnalysisResultModel
from app.services import log_timing
from app.services.availability import AvailabilityEngine
from app.services.llm_client import ChatMessage, get_llm_client

logger = logging.getLogger(__name__)


class EndpointEmbeddings(Embeddings):
    def __init__(self, base_url: str, api_key: Optional[str], model: str) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key or None
        self._model = model

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            with httpx.Client(timeout=60.0) as client:
                # Always use OpenAI-style v1 embeddings endpoint
                base = self._base
                try:
                    base = base.removesuffix("/v1")
                except Exception:
                    pass
                url = f"{base}/v1/embeddings"
                payload = {"model": self._model, "input": texts}
                r = client.post(url, json=payload, headers=self._headers())
                if 200 <= r.status_code < 300:
                    data = r.json()
                    items = data.get("data") or []
                    if not items:
                        raise LLMServiceError("Embedding response missing data")
                    vectors: List[List[float]] = []
                    for item in items:
                        vec = item.get("embedding") or item.get("vector")
                        if not isinstance(vec, list):
                            raise LLMServiceError("Invalid embedding format from endpoint")
                        vectors.append(vec)
                    return vectors
                if r.status_code in (404, 405):
                    raise LLMServiceError("Embeddings endpoint /v1/embeddings not found on AGENT_BASE_URL")
                raise LLMServiceError(f"Embeddings error {r.status_code}: {r.text[:200]}")
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            raise LLMServiceError(f"Embeddings service unavailable: {e}")

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


class AgentRunner:
    """
    Agent-based PDF analysis runner that extracts structured information from scientific papers.

    Uses a selectable embedding backend (Ollama or HTTP endpoint) for vector search,
    combined with an OpenAI-compatible LLM endpoint for extraction.
    """

    def __init__(self, context: Optional[dict] = None) -> None:
        """Initialize the agent runner with embeddings, vector store, and LLM configuration.
        Optionally accept a correlation context (e.g., doc_id, job_id, filename) for logging.
        """
        self._ctx = context or {}
        # Embeddings backend selection
        self._embed_backend = (settings.EMBEDDINGS_BACKEND or "ollama").lower()
        if self._embed_backend == "endpoint":
            self.embeddings = EndpointEmbeddings(
                base_url=settings.AGENT_BASE_URL,
                api_key=settings.AGENT_API_KEY,
                model=settings.AGENT_EMBED_MODEL,
            )
        else:
            # Default to Ollama
            self._embed_backend = "ollama"
            self.embeddings = OllamaEmbeddings(
                model=settings.OLLAMA_EMBED_MODEL,
                base_url=settings.OLLAMA_HOST,
            )

        try:
            self._chroma_client = chromadb.EphemeralClient(settings=ChromaSettings(anonymized_telemetry=False))
        except Exception:
            self._chroma_client = chromadb.PersistentClient(
                path=settings.CHROMA_DB_PATH, settings=ChromaSettings(anonymized_telemetry=False)
            )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1800,
            chunk_overlap=250,
            length_function=len,
        )
        # OpenAI-compatible endpoint config (HTTP-based client)
        self._agent_base_url = settings.AGENT_BASE_URL.rstrip("/")
        self._agent_model = settings.AGENT_MODEL
        self._agent_api_key = settings.AGENT_API_KEY
        self._availability_engine = AvailabilityEngine(
            data_allowed_domains=settings.DATA_LINK_ALLOWED_DOMAINS,
            code_allowed_domains=settings.CODE_LINK_ALLOWED_DOMAINS,
            deny_substrings=settings.LINK_DENY_SUBSTRINGS,
            dataset_doi_prefixes=settings.DATA_LINK_DATASET_DOI_PREFIXES,
        )

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion via configured LLM client (HTTP or MCP)."""
        client = get_llm_client()
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]
        with log_timing(logger, "llm_chat", model=self._agent_model, **self._ctx):
            return client.chat_complete(messages, model=self._agent_model, temperature=0.0)

    def _load_pdf_pages(self, pdf_path: str) -> List[str]:
        try:
            pages: List[str] = []
            if pdfplumber is not None:
                try:
                    with pdfplumber.open(pdf_path) as pdf:
                        for page in pdf.pages:
                            text = page.extract_text(layout=True) or ""
                            if text:
                                pages.append(text)
                except Exception:
                    pages = []
            if not pages:
                loader = PyPDFLoader(pdf_path)
                docs = loader.load()
                pages = [doc.page_content for doc in docs if doc.page_content]
            if not pages:
                raise InvalidPDFError("PDF appears to be empty or unreadable")
            return pages
        except InvalidPDFError:
            raise
        except Exception as e:
            raise InvalidPDFError(f"Failed to read PDF: {e}")

    def _normalize_text(self, text: str) -> str:
        # de-hyphenate across line breaks
        t = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
        # join URLs broken across line breaks (e.g., http-\n s://)
        t = re.sub(r"(https?)\s*:\s*//\s*", r"\1://", t, flags=re.IGNORECASE)
        # normalize newlines and spaces
        t = t.replace("\r\n", "\n").replace("\r", "\n")
        t = re.sub(r"[ \t]{2,}", " ", t)

        # Extract sentences and ensure proper separation
        # Split on sentence-ending punctuation (. ! ? ;) followed by whitespace
        parts = re.split(r"([.!?;])\s+", t)

        sentences = []
        current_sentence = ""

        for i, part in enumerate(parts):
            if not part:
                continue

            # If this is a punctuation mark
            if part in ".!?;":
                current_sentence = current_sentence.rstrip() + part
                # Check if next part starts with capital letter or is empty (end of text)
                if i + 1 < len(parts):
                    next_part = parts[i + 1].strip()
                    # Add sentence if it's complete (next part starts with capital/digit or is empty)
                    if current_sentence.strip() and (not next_part or next_part[0].isupper() or next_part[0].isdigit()):
                        sentences.append(current_sentence.strip())
                        current_sentence = ""
                    elif current_sentence.strip():
                        # Keep building the sentence (e.g., for abbreviations)
                        current_sentence += " "
                else:
                    # Last punctuation mark
                    if current_sentence.strip():
                        sentences.append(current_sentence.strip())
                        current_sentence = ""
            else:
                current_sentence += part.strip() + " "

        # Add any remaining text as final sentence
        if current_sentence.strip():
            sentences.append(current_sentence.strip())

        # Join sentences with newlines to ensure proper separation
        result = "\n".join(sentences)

        # Clean up excessive newlines
        result = re.sub(r"\n{3,}", "\n\n", result)

        return result

    def _chunk(self, text: str) -> List[str]:
        return self.text_splitter.split_text(text)

    def _vector_store(self, chunks: List[str]) -> Chroma:
        collection_name = f"pdf_analysis_{uuid4().hex[:8]}"
        return Chroma.from_texts(
            texts=chunks,
            embedding=self.embeddings,
            client=self._chroma_client,
            collection_name=collection_name,
        )

    def _similarity_context(self, vs: Chroma, query: str, k: int) -> str:
        docs = vs.similarity_search(query, k=k)
        return "\n".join([d.page_content for d in docs])

    def _similarity_context_multi(self, vs: Chroma, queries: List[str], k_each: int = 4, max_chars: int = 12000) -> str:
        seen = set()
        parts: List[str] = []
        for q in queries:
            try:
                docs = vs.similarity_search(q, k=k_each)
            except (ValueError, RuntimeError):
                docs = []
            for d in docs:
                t = (d.page_content or "").strip()
                if t and t not in seen:
                    seen.add(t)
                    parts.append(t)
            if sum(len(p) for p in parts) >= max_chars:
                break
        ctx = "\n".join(parts)
        if len(ctx) > max_chars:
            ctx = ctx[:max_chars]
        return ctx

    def _extract_single(self, vs: Chroma, query: str, system: str, label: str, k: int = 6) -> Optional[str]:
        ctx = self._similarity_context(vs, query=query, k=k)
        user = f"Text:\n{ctx}\n\nReturn ONLY the {label} or 'None'."
        out = self._chat(system, user)
        if not out:
            return None
        val = out.strip()
        if val.lower() in {"none", "not found", "n/a", "na", ""}:
            return None
        return val

    def _validate_doi(self, s: str) -> Optional[str]:
        if not s:
            return None
        s = s.strip()
        m = re.search(r"(?:doi:\s*)?(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s\"<>]+)", s, flags=re.IGNORECASE)
        if m:
            return validate_doi(m.group(1))
        return validate_doi(s)

    def analyze(self, pdf_path: str) -> PDFAnalysisResultModel:
        # Load and clean text
        with log_timing(logger, "load_pdf", **self._ctx):
            pages = self._load_pdf_pages(pdf_path)
        with log_timing(logger, "normalize_text", **self._ctx):
            normalized_pages = [self._normalize_text(page) for page in pages]
            normalized = "\n\n".join(normalized_pages)

        # Chunk and build vector store
        with log_timing(logger, "chunk_text", **self._ctx):
            chunks = self._chunk(normalized)
        try:
            with log_timing(logger, "build_vector_store", backend=self._embed_backend, **self._ctx):
                vs = self._vector_store(chunks)
        except Exception as e:
            msg = str(e)
            if self._embed_backend == "ollama" and (
                ('model "' in msg and "not found" in msg) or ("No such model" in msg) or ("not available" in msg)
            ):
                raise EmbeddingModelMissingError(
                    f'Ollama embedding model "{settings.OLLAMA_EMBED_MODEL}" is not available. '
                    f"Please run: ollama pull {settings.OLLAMA_EMBED_MODEL}"
                )
            # Propagate as service error
            raise LLMServiceError(f"Embedding backend error: {msg}")

        # Prompts
        sys_doi = (
            "You are an expert at extracting DOIs from scientific papers. "
            "Look for DOI patterns like '10.1234/example', 'doi:10.1234/example', or 'https://doi.org/10.1234/example'. "
            "Extract ONLY the DOI number (starting with '10.') if explicitly present in the text. "
            "If no DOI is found, respond with exactly: 'None'"
        )
        sys_title = (
            "You are an expert at identifying scientific paper titles. "
            "Look for the main title which is usually the most prominent heading at the beginning. "
            "Extract ONLY the main title, not subtitles, author names, or journal names. "
            "If no clear title is found, respond with exactly: 'None'"
        )
        sys_data_license = "Extract ONLY explicit data sharing license text if present.\n" "Return 'None' if absent."
        sys_code_license = "Extract ONLY explicit code/software license text if present.\n" "Return 'None' if absent."

        availability = self._availability_engine.extract(
            normalized_pages,
            chat_fn=lambda system, user: self._chat(system, user),
            diagnostics=logger.isEnabledFor(logging.DEBUG),
        )
        if availability.diagnostics:
            logger.debug("availability_diagnostics %s", availability.diagnostics)

        data_stmt = availability.data_statement
        code_stmt = availability.code_statement
        data_links = availability.data_links
        code_links = availability.code_links
        confidence_scores: Dict[str, float] = dict(availability.confidence_scores)

        # DOI: deterministic front-matter first, then LLM fallback
        doi = None
        # Limit search to front matter before References/Bibliography and to first ~20k chars
        refs_match = re.search(r"(?im)^\s*(references|bibliography)\b", normalized)
        search_zone = normalized[: refs_match.start()] if refs_match else normalized
        search_zone = search_zone[:20000]
        m = re.search(
            r"(?:doi:\s*)?(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s\"<>]+)", search_zone, flags=re.IGNORECASE
        )
        if m:
            doi = validate_doi(m.group(1))
        if not doi:
            doi_ctx = self._similarity_context_multi(
                vs,
                [
                    "DOI digital object identifier citation reference",
                    "https doi.org 10. journal article identifier",
                    "front matter citation DOI",
                ],
                k_each=4,
                max_chars=6000,
            )
            if doi_ctx:
                doi_raw = self._chat(sys_doi, f"Text:\n{doi_ctx}\n\nReturn ONLY the DOI or 'None'.")
                doi = self._validate_doi(doi_raw) if doi_raw else None
        if not doi:
            # Final regex sweep over the whole document
            for pat in [
                r"10\.\d{4,9}/[^\s\"<>]+",
                r"doi:\s*(10\.\d{4,9}/[^\s\"<>]+)",
                r"https?://(?:dx\.)?doi\.org/(10\.\d{4,9}/[^\s\"<>]+)",
            ]:
                m2 = re.search(pat, normalized, flags=re.IGNORECASE)
                if m2:
                    grp = m2.group(1) if m2.lastindex else m2.group(0)
                    doi = validate_doi(grp)
                    if doi:
                        break

        # Title
        title = self._extract_single(
            vs,
            query="title abstract introduction paper study research",
            system=sys_title,
            label="title",
            k=4,
        )
        if title and (len(title) < 10 or len(title) > 300):
            title = None

        # Licenses
        data_license = self._extract_single(
            vs,
            query="data sharing license Creative Commons CC BY MIT GPL Apache proprietary dataset license",
            system=sys_data_license,
            label="data sharing license",
            k=6,
        )
        if data_license and len(data_license) < 5:
            data_license = None

        code_license = self._extract_single(
            vs,
            query="code license software license MIT GPL Apache BSD Creative Commons proprietary licensing",
            system=sys_code_license,
            label="code license",
            k=6,
        )
        if code_license and len(code_license) < 5:
            code_license = None

        return PDFAnalysisResultModel(
            title=title,
            doi=doi,
            data_availability_statement=data_stmt,
            code_availability_statement=code_stmt,
            data_sharing_license=data_license,
            code_license=code_license,
            data_links=data_links,
            code_links=code_links,
            confidence_scores=confidence_scores,
        )
