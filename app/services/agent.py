import re
import logging
from typing import List, Optional, Tuple
from uuid import uuid4
from urllib.parse import urlparse, urlunparse

from app.core.config import settings
from app.models.schemas import PDFAnalysisResultModel

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.embeddings import Embeddings
import chromadb
from chromadb.config import Settings as ChromaSettings
import httpx
from app.core.errors import (
    InvalidPDFError,
    EmbeddingModelMissingError,
    LLMServiceError,
)
from app.services.llm_client import get_llm_client, ChatMessage
from app.core.validation import validate_doi, validate_url
from app.services import log_timing

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
            self._chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH, settings=ChromaSettings(anonymized_telemetry=False))
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1800,
            chunk_overlap=250,
            length_function=len,
        )
        # OpenAI-compatible endpoint config (HTTP-based client)
        self._agent_base_url = settings.AGENT_BASE_URL.rstrip("/")
        self._agent_model = settings.AGENT_MODEL
        self._agent_api_key = settings.AGENT_API_KEY

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion via configured LLM client (HTTP or MCP)."""
        client = get_llm_client()
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]
        with log_timing(logger, "llm_chat", model=self._agent_model, **self._ctx):
            return client.chat_complete(messages, model=self._agent_model, temperature=0.0)

    def _load_pdf(self, pdf_path: str) -> str:
        try:
            loader = PyPDFLoader(pdf_path)
            pages = loader.load()
            if not pages:
                raise InvalidPDFError("PDF appears to be empty or unreadable")
            return "\n".join([p.page_content for p in pages])
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
        t = re.sub(r"\n{3,}", "\n\n", t)
        t = re.sub(r"[ \t]{2,}", " ", t)
        return t

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

    def _extract_by_headings(self, text: str, headings: List[str]) -> Optional[str]:
        pattern = r"(?ims)^(?:" + "|".join(headings) + r")\s*\n+(?P<body>.+?)(?=\n\s*^[A-Z][^\n]{0,80}$|\n\n\n|\Z)"
        m = re.search(pattern, text)
        if not m:
            return None
        body = m.group("body").strip()
        parts = [p.strip() for p in body.split("\n\n") if p.strip()]
        return "\n\n".join(parts[:2]) if parts else None

    def _extract_by_phrases(self, text: str, phrases: List[str]) -> Optional[str]:
        pattern = r"(?is)(?:" + "|".join(phrases) + r").+?(?:\.\n|\n\n|\.)"
        m = re.search(pattern, text)
        return m.group(0).strip() if m else None

    def _extract_links_from_text(self, text: str) -> List[str]:
        links: List[str] = []
        if not text:
            return links
        # Reconstruct fragmented URLs across whitespace and hyphenation
        text = re.sub(r"(https?)\s*:\s*//\s*", r"\1://", text, flags=re.IGNORECASE)
        text = re.sub(r"(?i)([a-z]{2,}://[\w\-\.]+)\s*-\n\s*([\w/])", r"\1\2", text)
        url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        for url in re.findall(url_pattern, text):
            if len(url) > 10 and "." in url:
                links.append(url)
        # Also catch 'www.example.com/...' without scheme and add https
        for m in re.findall(r"(?<![a-z])www\.[\w\-\.]+(?:/[\w\-\./%#?=&]+)?", text, flags=re.IGNORECASE):
            links.append("https://" + m)
        seen = set()
        clean: List[str] = []
        for l in links:
            low = l.lower().rstrip(".,;)]")
            if low in seen or any(b in low for b in ["none", "example"]):
                continue
            seen.add(low)
            clean.append(l.rstrip(".,;)]"))
        return clean

    def _expand_statement_context(self, normalized_text: str, statement: Optional[str], max_chars: int = 600) -> Optional[str]:
        if not statement:
            return None
        s = statement.strip()
        if not s:
            return None
        # Try to locate the statement (or its prefix) in the normalized text
        probe = s[:120]
        idx = normalized_text.find(probe)
        if idx < 0 and len(s) > 60:
            probe = s[:60]
            idx = normalized_text.find(probe)
        if idx < 0:
            return s
        # Expand to surrounding paragraph boundaries
        a = normalized_text.rfind("\n\n", 0, idx)
        a = 0 if a < 0 else a + 2
        b = normalized_text.find("\n\n", idx + len(probe))
        b = len(normalized_text) if b < 0 else b
        span = normalized_text[a:b].strip()
        # Ensure ends with sentence punctuation; if not, try to extend to next period
        if not re.search(r"[\.!?]\)?$", span) and b < len(normalized_text):
            extra = normalized_text[b: b + 400]
            m = re.search(r".+?[\.!?]\)?", extra)
            if m:
                span = (span + " " + m.group(0)).strip()
        if len(span) > max_chars:
            span = span[:max_chars].rstrip()
        return span or s

    def _repair_urls(self, urls: List[str]) -> List[str]:
        repaired: List[str] = []
        seen = set()
        for u in urls:
            if not u:
                continue
            s = u.strip()
            s = re.sub(r"\s+", "", s)
            s = re.sub(r"[\]\)\.,;]+$", "", s)
            if not s.lower().startswith(("http://", "https://")):
                if s.lower().startswith("www."):
                    s = "https://" + s
                else:
                    # skip non-http
                    continue
            try:
                parsed = urlparse(s)
                netloc = parsed.netloc.lower()
                if netloc.startswith("www."):
                    netloc = netloc[4:]
                # collapse consecutive slashes in path
                path = re.sub(r"/{2,}", "/", parsed.path)
                rebuilt = urlunparse((parsed.scheme, netloc, path, "", parsed.query, parsed.fragment))
                low = rebuilt.lower()
                if low not in seen and validate_url(rebuilt):
                    seen.add(low)
                    repaired.append(rebuilt)
            except Exception:
                continue
        return repaired

    def analyze(self, pdf_path: str) -> PDFAnalysisResultModel:
        # Load and clean text
        with log_timing(logger, "load_pdf", **self._ctx):
            raw_text = self._load_pdf(pdf_path)
        with log_timing(logger, "normalize_text", **self._ctx):
            normalized = self._normalize_text(raw_text)

        # Heuristic extraction
        data_heading_variants = [
            r"data availability(?: statement)?",
            r"availability of data(?: and materials)?",
            r"data and materials availability",
            r"data accessibility",
            r"availability of supporting data",
            r"supporting information",
        ]
        code_heading_variants = [
            r"code availability",
            r"software availability",
            r"source code availability",
            r"code and data availability",
        ]
        data_phrase_variants = [
            r"data\s+(?:are|is)\s+available",
            r"data\s+have\s+been\s+deposited",
            r"data\s+can\s+be\s+accessed",
            r"data\s+available\s+(?:at|from)",
            r"dataset\s+available",
            r"supplementary\s+data\s+are\s+available",
            r"upon\s+request",
            r"available\s+upon\s+reasonable\s+request",
            r"data\s+deposited\s+in",
        ]
        code_phrase_variants = [
            r"code\s+(?:is|are)\s+available",
            r"source\s+code\s+is\s+available",
            r"repository\s+at",
            r"scripts\s+available",
            r"software\s+available",
            r"github|gitlab|bitbucket",
        ]

        data_stmt_heur = self._extract_by_headings(normalized, data_heading_variants) or self._extract_by_phrases(normalized, data_phrase_variants)
        code_stmt_heur = self._extract_by_headings(normalized, code_heading_variants) or self._extract_by_phrases(normalized, code_phrase_variants)

        # Chunk and build vector store
        with log_timing(logger, "chunk_text", **self._ctx):
            chunks = self._chunk(normalized)
        try:
            with log_timing(logger, "build_vector_store", backend=self._embed_backend, **self._ctx):
                vs = self._vector_store(chunks)
        except Exception as e:
            msg = str(e)
            if self._embed_backend == "ollama" and (("model \"" in msg and "not found" in msg) or ("No such model" in msg) or ("not available" in msg)):
                raise EmbeddingModelMissingError(
                    f'Ollama embedding model "{settings.OLLAMA_EMBED_MODEL}" is not available. '
                    f'Please run: ollama pull {settings.OLLAMA_EMBED_MODEL}'
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
        sys_data = (
            "You are an expert at finding data availability statements in scientific papers. "
            "Look for explicit statements about data availability, data access, data sharing, or where data can be found. "
            "Common phrases include 'data are available', 'data deposited', 'supplementary data', 'data accessible at', etc. "
            "Return an EXACT QUOTED SPAN from the provided Text, preserving wording and punctuation. Do NOT paraphrase. "
            "If no data availability statement is found, respond with exactly: 'None'"
        )
        sys_code = (
            "You are an expert at finding code availability statements in scientific papers. "
            "Look for explicit statements about code availability, software access, repository links, or programming resources. "
            "Common phrases include 'code available', 'source code', 'GitHub', 'repository', 'software available', etc. "
            "Return an EXACT QUOTED SPAN from the provided Text, preserving wording and punctuation. Do NOT paraphrase. "
            "If no code availability statement is found, respond with exactly: 'None'"
        )
        sys_data_license = (
            "Extract ONLY explicit data sharing license text if present.\n"
            "Return 'None' if absent."
        )
        sys_code_license = (
            "Extract ONLY explicit code/software license text if present.\n"
            "Return 'None' if absent."
        )
        sys_links = (
            "Extract ONLY explicit links (full URLs).\n"
            "Return comma-separated links or 'None'."
        )

        # DOI: deterministic front-matter first, then LLM fallback
        doi = None
        # Limit search to front matter before References/Bibliography and to first ~20k chars
        refs_match = re.search(r"(?im)^\s*(references|bibliography)\b", normalized)
        search_zone = normalized[: refs_match.start()] if refs_match else normalized
        search_zone = search_zone[:20000]
        m = re.search(r"(?:doi:\s*)?(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s\"<>]+)", search_zone, flags=re.IGNORECASE)
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

        # Data availability - Deterministic first, then agent fallback
        data_stmt = data_stmt_heur
        if not data_stmt:
            data_ctx = self._similarity_context_multi(
                vs,
                [
                    "data availability access supplementary materials dataset repository accessibility archived deposited Dryad Zenodo Figshare OSF",
                    "availability of data and materials availability of supporting data",
                    "data deposited archived repository data accessible at upon request",
                ],
                k_each=6,
                max_chars=12000,
            )
            if data_ctx:
                data_stmt = self._chat(sys_data, f"Text:\n{data_ctx}\n\nReturn ONLY the data availability statement or 'None'.")
        if data_stmt and len(data_stmt) < 10:
            data_stmt = None
        # Context repair: expand to full paragraph/sentence if enabled
        if settings.REPAIR_CONTEXT_ENABLED and data_stmt:
            data_stmt = self._expand_statement_context(normalized, data_stmt)

        # Code availability - Deterministic first, then agent fallback
        code_stmt = code_stmt_heur
        if not code_stmt:
            code_ctx = self._similarity_context_multi(
                vs,
                [
                    "code availability software scripts GitHub GitLab Bitbucket repository programming analysis source reproducibility",
                    "source code available software availability repository link",
                ],
                k_each=6,
                max_chars=10000,
            )
            if code_ctx:
                code_stmt = self._chat(sys_code, f"Text:\n{code_ctx}\n\nReturn ONLY the code availability statement or 'None'.")
        if code_stmt and len(code_stmt) < 10:
            code_stmt = None
        # Context repair for code statement
        if settings.REPAIR_CONTEXT_ENABLED and code_stmt:
            code_stmt = self._expand_statement_context(normalized, code_stmt)

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

        # Links (primary data sources only for data_links)
        def _extract_links(query: str) -> List[str]:
            ctx = self._similarity_context(vs, query=query, k=6)
            out = self._chat(sys_links, f"Text:\n{ctx}\n\nLinks:")
            links: List[str] = []
            if out and out.strip().lower() not in {"none", "not found", "n/a", "na", ""}:
                url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
                for url in re.findall(url_pattern, out):
                    if len(url) > 10 and "." in url:
                        links.append(url)
                if "," in out:
                    for tok in [t.strip() for t in out.split(",")]:
                        if tok.startswith(("http", "www", "github.com", "doi.org")) and len(tok) > 10:
                            links.append(tok)
            seen = set()
            clean: List[str] = []
            for l in links:
                low = l.lower()
                if low in seen:
                    continue
                if any(bad in low for bad in ["none", "not found", "example"]):
                    continue
                seen.add(low)
                clean.append(l)
            return clean

        DATA_REPO_WHITELIST = {
            "zenodo.org",
            "figshare.com",
            "datadryad.org",
            "dryad.org",
            "osf.io",
            "pangaea.de",
            "data.mendeley.com",
            "openneuro.org",
            "dataverse.org",
            "purl.org",  # sometimes dataset DOIs use purl -> redirects
            "ebi.ac.uk",
            "ncbi.nlm.nih.gov",
            "ega-archive.org",
        }
        DATASET_DOI_PREFIXES = {
            "10.5281",  # Zenodo
            "10.6084",  # Figshare
            "10.5061",  # Dryad
            "10.17605",  # OSF
            "10.1594",  # PANGAEA
            "10.7910",  # Dataverse (Harvard DVN)
            "10.18112",  # OpenNeuro
        }

        def _clean_url(u: str) -> str:
            return re.sub(r"[\.,;\)\]]+$", "", u).strip()

        def _domain(u: str) -> str:
            try:
                net = urlparse(u).netloc.lower()
                if net.startswith("www."):
                    net = net[4:]
                return net
            except Exception:
                return ""

        def _is_dataset_doi(u: str) -> bool:
            if not u.lower().startswith("http"):
                return False
            if "doi.org/10." in u.lower():
                try:
                    doi_part = u.split("doi.org/", 1)[1]
                    doi_part = doi_part.strip()
                    for pref in DATASET_DOI_PREFIXES:
                        if doi_part.startswith(pref):
                            return True
                except Exception:
                    return False
            return False

        def _is_primary_dataset_link(u: str) -> bool:
            d = _domain(u)
            return d in DATA_REPO_WHITELIST or _is_dataset_doi(u)

        def _filter_valid_primary(links: List[str]) -> List[str]:
            out: List[str] = []
            seen = set()
            for l in links:
                cu = _clean_url(l)
                if not validate_url(cu):
                    continue
                if not _is_primary_dataset_link(cu):
                    continue
                low = cu.lower()
                if low in seen:
                    continue
                seen.add(low)
                out.append(cu)
            return out

        def _extract_links_around(text: str, center_idx: int, window: int = 600) -> List[str]:
            if center_idx < 0:
                return []
            a = max(0, center_idx - window)
            b = min(len(text), center_idx + window)
            return self._extract_links_from_text(text[a:b])

        data_links: List[str] = []
        code_links: List[str] = []

        # Data links from statement (and nearby context), then LLM, filtered to primary sources
        stmt_text = data_stmt or data_stmt_heur
        cand_data_links: List[str] = []
        if stmt_text:
            cand_data_links.extend(self._extract_links_from_text(stmt_text))
            # Try to find the statement in the full text and collect nearby links
            probe = stmt_text[:80] if len(stmt_text) >= 80 else stmt_text
            idx = normalized.find(probe) if probe else -1
            cand_data_links.extend(_extract_links_around(normalized, idx, 600))
        # Add LLM-extracted links but still filter strictly
        cand_data_links.extend(_extract_links("data repository dataset download link URL supplementary materials"))
        # Optional repair of candidate URLs
        if settings.REPAIR_URLS_ENABLED:
            cand_data_links = self._repair_urls(cand_data_links)
        data_links = _filter_valid_primary(cand_data_links)

        # Code links: keep as before but validate/repair
        if code_stmt_heur:
            code_links.extend(self._extract_links_from_text(code_stmt_heur))
        code_links.extend(_extract_links("GitHub repository code software scripts programming source"))
        if settings.REPAIR_URLS_ENABLED:
            code_links = self._repair_urls(code_links)
        else:
            code_links = [
                _clean_url(u) for u in code_links if validate_url(_clean_url(u))
            ]

        def _dedup(xs: List[str]) -> List[str]:
            seen = set()
            out: List[str] = []
            for x in xs:
                lx = x.lower()
                if lx in seen:
                    continue
                seen.add(lx)
                out.append(x)
            return out

        data_links = _dedup(data_links)
        code_links = _dedup(code_links)

        return PDFAnalysisResultModel(
            title=title,
            doi=doi,
            data_availability_statement=data_stmt,
            code_availability_statement=code_stmt,
            data_sharing_license=data_license,
            code_license=code_license,
            data_links=data_links,
            code_links=code_links,
            confidence_scores={},
        )
