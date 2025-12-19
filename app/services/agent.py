import itertools
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence
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
from app.services.text_normalizer import PDFTextNormalizer, ParagraphBlock

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
        base = self._base
        try:
            base = base.removesuffix("/v1")
        except Exception:
            pass
        url = f"{base}/v1/embeddings"
        payload = {"model": self._model, "input": texts}
        delays = [0.0, 0.5, 1.0, 2.0]
        last_err: Optional[Exception] = None
        for delay in delays:
            if delay:
                import time as _t
                _t.sleep(delay)
            try:
                with httpx.Client(timeout=60.0) as client:
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
                        body = (r.text or "")[:200]
                        msg = "Embeddings endpoint /v1/embeddings unavailable or model not found"
                        try:
                            data = r.json()
                            if isinstance(data, dict):
                                errtxt = data.get("error") or data.get("message") or ""
                                if errtxt:
                                    msg = f"Embeddings 404: {errtxt[:180]}"
                        except Exception:
                            pass
                        raise LLMServiceError(msg)
                    if r.status_code in (408, 429) or 500 <= r.status_code < 600:
                        last_err = LLMServiceError(f"Embeddings error {r.status_code}: {r.text[:200]}")
                        continue
                    raise LLMServiceError(f"Embeddings error {r.status_code}: {r.text[:200]}")
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_err = LLMServiceError(f"Embeddings service unavailable: {e}")
                continue
            except Exception as e:
                last_err = LLMServiceError(f"Embeddings service error: {e}")
                break
        assert last_err is not None
        raise last_err

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
            embed_base = settings.EMBEDDINGS_BASE_URL or settings.AGENT_BASE_URL
            self.embeddings = EndpointEmbeddings(
                base_url=embed_base,
                api_key=(settings.EMBEDDINGS_API_KEY or settings.AGENT_API_KEY),
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
        self._text_normalizer = PDFTextNormalizer() if pdfplumber is not None else None
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

    def _load_pdf_blocks(self, pdf_path: str) -> List[ParagraphBlock]:
        try:
            if self._text_normalizer is not None:
                try:
                    blocks = self._text_normalizer.extract(pdf_path)
                    if blocks:
                        return blocks
                except Exception as exc:
                    logger.debug("text_normalizer_failed %s", exc, exc_info=True)

            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            fallback_blocks: List[ParagraphBlock] = []
            counter = itertools.count()
            for idx, doc in enumerate(docs):
                text = (doc.page_content or "").strip()
                if not text:
                    continue
                fallback_blocks.append(
                    ParagraphBlock(
                        text=text,
                        page=idx + 1,
                        column=0,
                        seq=next(counter),
                    )
                )
            if not fallback_blocks:
                raise InvalidPDFError("PDF appears to be empty or unreadable")
            return fallback_blocks
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

        # Join lines that don't end with sentence-ending punctuation
        # This handles text that wraps across lines mid-sentence
        lines = t.split("\n")
        merged_lines = []
        current_line = ""

        for line in lines:
            line = line.strip()
            if not line:
                # Preserve paragraph breaks
                if current_line:
                    merged_lines.append(current_line)
                    current_line = ""
                if merged_lines and merged_lines[-1] != "":
                    merged_lines.append("")
                continue

            # Check if previous line ended with sentence-ending punctuation
            if current_line and current_line[-1] in ".!?;":
                merged_lines.append(current_line)
                current_line = line
            else:
                # Continue the sentence from previous line
                if current_line:
                    current_line += " " + line
                else:
                    current_line = line

        # Add any remaining line
        if current_line:
            merged_lines.append(current_line)

        # Join merged lines
        t = "\n".join(merged_lines)
        # Repair intra-word spaced letters caused by OCR (e.g., 't r o p i c a l i z a t i o n')
        def _compact_word_sequence(match: re.Match) -> str:
            seq = match.group(0)
            letters = seq.split()
            if len(letters) >= 4:
                return "".join(letters)
            return seq
        t = re.sub(r"(?:\b\w\b\s+){3,}\w\b", _compact_word_sequence, t)

        # Now extract sentences and ensure proper separation
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

    def _heuristic_title(self, blocks: Sequence[ParagraphBlock]) -> Optional[str]:
        stopword_pattern = re.compile(
            r"\b(abstract|introduction|copyright|doi|license|keywords|data availability|authors|affiliations|received|accepted)\b",
            flags=re.IGNORECASE,
        )
        # Additional pattern to detect journal headers that should be skipped
        journal_header_pattern = re.compile(
            r"^[a-zA-Z\s]+\(\d{4}\)\s+\d+,\s+\d+-\d+$",
            flags=re.IGNORECASE,
        )
        
        for block in blocks:
            if block.page > 1:
                break
            if block.column > 0:
                continue
            candidate = self._normalize_text(block.text).strip()
            candidate = re.sub(r"\s+", " ", candidate)
            
            # Skip journal headers (e.g., "Molecular Ecology (2000) 9, 1319-1324")
            if journal_header_pattern.match(candidate):
                continue
                
            if not candidate or candidate.endswith(":"):
                continue
            # Relax length constraints slightly for journal headers
            if len(candidate) < 8 or len(candidate) > 250:
                continue
            words = candidate.split()
            if len(words) < 2 or len(words) > 40:
                continue
            if stopword_pattern.search(candidate):
                continue
            # Relax alpha ratio for citations and journal headers
            alpha_ratio = sum(1 for ch in candidate if ch.isalpha()) / len(candidate)
            if alpha_ratio < 0.4:  # Reduced from 0.5
                continue
            return candidate
        return None

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

    def _persist_diagnostics(self, diagnostics: Dict[str, object]) -> None:
        try:
            base_dir = Path(__file__).resolve().parent.parent
            log_dir = base_dir / "logs" / "availability"
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            context_id = str(
                self._ctx.get("doc_id")
                or self._ctx.get("filename")
                or self._ctx.get("job_id")
                or "unknown"
            )
            safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", context_id)
            logfile = log_dir / f"{timestamp}_{safe_id}.json"
            payload = {
                "timestamp": timestamp,
                "context": self._ctx,
                "diagnostics": diagnostics,
            }
            with logfile.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
        except Exception:
            logger.exception("Failed to persist availability diagnostics")

    def analyze(self, pdf_path: str) -> PDFAnalysisResultModel:
        # Load and clean text
        with log_timing(logger, "load_pdf", **self._ctx):
            blocks = self._load_pdf_blocks(pdf_path)
        with log_timing(logger, "normalize_text", **self._ctx):
            normalized_pages = [self._normalize_text(block.text) for block in blocks]
            normalized = "\n\n".join(normalized_pages)
        normalizer_meta = {
            "block_count": len(blocks),
            "first_page_blocks": sum(1 for b in blocks if b.page == 1),
            "columns_first_page": len({b.column for b in blocks if b.page == 1}),
            "first_block_preview": blocks[0].text[:200] if blocks else None,
        }

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
            "Ignore journal headers like 'Molecular Ecology (2000) 9, 1319-1324'. "
            "The title is typically descriptive of the research content. "
            "If no clear title is found, respond with exactly: 'None'"
        )
        sys_data_license = "Extract ONLY explicit data sharing license text if present.\n" "Return 'None' if absent."
        sys_code_license = "Extract ONLY explicit code/software license text if present.\n" "Return 'None' if absent."

        availability = self._availability_engine.extract(
            normalized_pages,
            chat_fn=lambda system, user: self._chat(system, user),
            diagnostics=True,
        )
        if availability.diagnostics:
            availability.diagnostics.setdefault("normalizer", normalizer_meta)
            logger.debug("availability_diagnostics %s", availability.diagnostics)
            self._persist_diagnostics(availability.diagnostics)

        data_stmt = availability.data_statement
        code_stmt = availability.code_statement
        data_links = availability.data_links
        code_links = availability.code_links
        confidence_scores: Dict[str, float] = dict(availability.confidence_scores)
        debug_info = availability.diagnostics if settings.EXPOSE_AVAILABILITY_DEBUG else None

        # DOI: harvest candidates from front matter with heuristic scoring
        doi = None
        doi_candidates: List[str] = []
        refs_match = re.search(r"(?im)^\s*(references|bibliography)\b", normalized)
        front_matter = normalized[: refs_match.start()] if refs_match else normalized
        front_matter = front_matter[:20000]

        doi_patterns = [
            r"(?:doi:\s*)?(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s\"<>]+)",
            r"10\.\d{4,9}/[^\s\"<>]+",
        ]
        for pat in doi_patterns:
            for m in re.finditer(pat, front_matter, flags=re.IGNORECASE):
                grp = m.group(1) if m.lastindex else m.group(0)
                val = validate_doi(grp)
                if val:
                    # Avoid dataset DOIs (zenodo/dryad/osf) being mistaken as article DOI
                    if any(val.startswith(p + "/") for p in settings.DATA_LINK_DATASET_DOI_PREFIXES):
                        continue
                    doi_candidates.append(val)
        if not doi_candidates:
            for pat in doi_patterns:
                for m in re.finditer(pat, normalized, flags=re.IGNORECASE):
                    grp = m.group(1) if m.lastindex else m.group(0)
                    val = validate_doi(grp)
                    if val:
                        if any(val.startswith(p + "/") for p in settings.DATA_LINK_DATASET_DOI_PREFIXES):
                            continue
                        doi_candidates.append(val)
        # Deduplicate preserve order
        seen_d = set()
        ordered_candidates: List[str] = []
        for c in doi_candidates:
            if c not in seen_d:
                seen_d.add(c)
                ordered_candidates.append(c)

        # Score candidates
        candidate_scores: Dict[str, float] = {}
        candidate_pos: Dict[str, int] = {}
        for c in ordered_candidates:
            pos = front_matter.find(c)
            if pos < 0:
                pos = normalized.find(c)
            base = 1.0 if 0 <= pos < 5000 else 0.6
            ctx = normalized[max(0, pos - 30): pos + len(c) + 30] if pos >= 0 else ""
            boost = 0.0
            if re.search(r"doi:\s*" + re.escape(c), ctx, flags=re.IGNORECASE):
                boost += 0.4
            if re.search(r"https?://(?:dx\.)?doi\.org/" + re.escape(c), ctx, flags=re.IGNORECASE):
                boost += 0.3
            score = round(base + boost, 3)
            candidate_scores[c] = float(score)
            candidate_pos[c] = int(pos)

        # Select preliminary DOI by score
        doi_prelim = None
        if candidate_scores:
            doi_prelim = max(candidate_scores.keys(), key=lambda k: candidate_scores[k])
            doi = doi_prelim
            confidence_scores["doi"] = min(1.0, float(candidate_scores[doi_prelim]))

        # If still no DOI, LLM fallback with hallucination guard
        if not doi:
            doi_ctx = self._similarity_context_multi(
                vs,
                [
                    "DOI digital object identifier citation reference",
                    "https doi.org 10. journal article identifier",
                    "front matter citation DOI",
                ],
                k_each=4,
                max_chars=4000,
            )
            if doi_ctx:
                if len(doi_ctx) > 4000:
                    doi_ctx = doi_ctx[:4000]
                try:
                    doi_raw = self._chat(sys_doi, f"Text:\n{doi_ctx}\n\nReturn ONLY the DOI or 'None'.")
                except LLMServiceError as exc:
                    logger.warning("doi_chat_failed: %s", exc)
                    doi_raw = None
                cand = self._validate_doi(doi_raw) if doi_raw else None
                if cand and cand in normalized:
                    doi = cand
                    confidence_scores["doi"] = 0.5
        if not doi:
            # Final regex sweep
            for pat in [
                r"10\.\d{4,9}/[^\s\"<>]+",
                r"doi:\s*(10\.\d{4,9}/[^\s\"<>]+)",
                r"https?://(?:dx\.)?doi\.org/(10\.\d{4,9}/[^\s\"<>]+)",
            ]:
                m2 = re.search(pat, normalized, flags=re.IGNORECASE)
                if m2:
                    grp = m2.group(1) if m2.lastindex else m2.group(0)
                    cand = validate_doi(grp)
                    if cand and not any(cand.startswith(p + "/") for p in settings.DATA_LINK_DATASET_DOI_PREFIXES):
                        doi = cand
                        confidence_scores["doi"] = max(confidence_scores.get("doi", 0.4), 0.45)
                        break

        # Prepare DOI diagnostics (verification added after title resolution)
        scored_list = [
            {"value": c, "pos": candidate_pos.get(c, -1), "score": candidate_scores.get(c, 0.0)}
            for c in ordered_candidates
        ]
        scored_list.sort(key=lambda d: float(d.get("score", 0.0)), reverse=True)
        doi_selected_score = candidate_scores.get(doi, 0.0) if doi else 0.0
        doi_verification_meta = None
        if availability.diagnostics is not None:
            availability.diagnostics["doi_debug"] = {
                "candidates": ordered_candidates,
                "scored": scored_list,
                "selected": doi,
                "prelim_score": doi_selected_score,
            }
            if settings.EXPOSE_AVAILABILITY_DEBUG:
                debug_info = availability.diagnostics

        # Title: prefer LLM if configured, with heuristics/enrichment as fallback
        title_source = "heuristic"
        heuristic_title = self._heuristic_title(blocks)
        title = None
        
        # Debug: Log heuristic title extraction
        logger.debug(f"Heuristic title extracted: '{heuristic_title}' from {len(blocks)} blocks")

        def _llm_title_from_front() -> Optional[str]:
            front_blocks: List[str] = []
            for b in blocks:
                if b.page != 1:
                    break
                if b.column != 0:
                    continue
                txt = (b.text or '').strip()
                if txt:
                    front_blocks.append(re.sub(r"\s+", " ", txt))
            front_ctx = "\n".join(front_blocks[:6])
            if not front_ctx:
                return None
            try:
                enhanced_prompt = f"Front Matter (first page):\n{front_ctx}\n\n"
                enhanced_prompt += "Note: Journal headers like 'Journal Name (Year) Volume, Pages' are NOT titles. "
                enhanced_prompt += "Look for the actual research title that describes the study content.\n\n"
                enhanced_prompt += "Return ONLY the title or 'None'."
                logger.debug(f"LLM title extraction prompt: {enhanced_prompt[:200]}...")
                raw = self._chat(sys_title, enhanced_prompt)
                logger.debug(f"LLM title raw response: '{raw}'")
            except LLMServiceError:
                raw = None
                logger.debug("LLM title extraction failed with LLMServiceError")
            if raw:
                cleaned = raw.strip()
                if cleaned.lower() not in {"none", "not found", "n/a", "na", ""} and 5 <= len(cleaned) <= 300:
                    return cleaned
            return None

        if settings.ENABLE_TITLE_LLM_PREFERRED:
            cand = _llm_title_from_front()
            if not cand:
                cand = self._extract_single(
                    vs,
                    query="title abstract introduction paper study research",
                    system=sys_title,
                    label="title",
                    k=4,
                )
            if cand and (10 <= len(cand) <= 300):
                title = cand
                title_source = "llm"
            else:
                # Fallback to heuristic/enrichment
                title = heuristic_title
                if settings.ENABLE_TITLE_ENRICHMENT:
                    try:
                        from app.services.title_resolver import TitleResolver
                        resolver = TitleResolver()
                        enriched = resolver.resolve(blocks)
                        if enriched.title:
                            title = enriched.title
                            title_source = enriched.source
                    except Exception:
                        pass
        else:
            # Original order: heuristic -> enrichment -> LLM
            title = heuristic_title
            if settings.ENABLE_TITLE_ENRICHMENT:
                try:
                    from app.services.title_resolver import TitleResolver
                    resolver = TitleResolver()
                    enriched = resolver.resolve(blocks)
                    if enriched.title:
                        title = enriched.title
                        title_source = enriched.source
                except Exception:
                    pass
            if not title:
                cand = _llm_title_from_front() or self._extract_single(
                    vs,
                    query="title abstract introduction paper study research",
                    system=sys_title,
                    label="title",
                    k=4,
                )
                if cand and (10 <= len(cand) <= 300):
                    title = cand
                    title_source = "llm"

        if availability.diagnostics is not None:
            availability.diagnostics["title_debug"] = {
                "heuristic": heuristic_title,
                "final": title,
                "source": title_source if title else None,
            }
            if settings.EXPOSE_AVAILABILITY_DEBUG:
                debug_info = availability.diagnostics

        # Crossref-based verification and reconciliation using title and DOI
        if settings.ENABLE_DOI_VERIFICATION and (title or heuristic_title):
            try:
                from app.services.doi_registry import DOIRegistry
                reg = DOIRegistry()
                title_text = title or heuristic_title

                # Title search: may provide a DOI candidate
                title_rec = reg.search_by_title(title_text)
                title_sim = reg.title_similarity(title_rec.get("title") if title_rec else None, title_text)

                # Existing DOI verification, if any
                doi_rec = reg.lookup(doi) if doi else None
                doi_sim = reg.title_similarity(doi_rec.get("title") if doi_rec else None, title_text)

                # Decide DOI based on sims
                replaced_by_title_search = False
                base_conf = float(confidence_scores.get("doi", 0.0))
                strong_harvest = bool(doi and (base_conf >= 0.9))
                if not doi and title_rec and title_rec.get("doi") and title_sim >= 0.4:
                    doi = title_rec.get("doi")
                    confidence_scores["doi"] = min(1.0, 0.6 + float(title_sim))
                    replaced_by_title_search = True
                elif doi:
                    if not doi_rec or doi_sim < 0.2:
                        # Only allow replacement of an existing DOI if it wasn't harvested strongly
                        # and the title search match is clearly stronger
                        if (not strong_harvest) and title_rec and title_rec.get("doi") and title_sim >= max(0.6, doi_sim + 0.25):
                            doi = title_rec.get("doi")
                            confidence_scores["doi"] = min(1.0, 0.55 + float(title_sim))
                            replaced_by_title_search = True
                        else:
                            base_conf = float(confidence_scores.get("doi", 0.5))
                            confidence_scores["doi"] = max(base_conf * 0.7, 0.3)
                    else:
                        base_conf = float(confidence_scores.get("doi", 0.5))
                        confidence_scores["doi"] = min(1.0, max(base_conf, base_conf + 0.2 + float(doi_sim)))

                if availability.diagnostics is not None:
                    dd = availability.diagnostics.get("doi_debug")
                    if not isinstance(dd, dict):
                        dd = {}
                    dd["verification"] = {
                        "registry_record": doi_rec,
                        "title_similarity": doi_sim,
                        "verified": bool(doi_rec and doi_sim >= 0.2),
                    }
                    dd["title_search"] = {
                        "record": title_rec,
                        "title_similarity": title_sim,
                        "used": replaced_by_title_search,
                    }
                    availability.diagnostics["doi_debug"] = dd

                if availability.diagnostics is not None:
                    td = availability.diagnostics.get("title_debug")
                    if not isinstance(td, dict):
                        td = {}
                    td["title_verification"] = {
                        "search_record": title_rec,
                        "similarity": title_sim,
                        "verified": bool(title_rec and title_sim >= 0.4),
                    }
                    availability.diagnostics["title_debug"] = td

                if settings.EXPOSE_AVAILABILITY_DEBUG:
                    debug_info = availability.diagnostics
            except Exception:
                pass

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
        # Normalize license identifiers for consistency
        def _norm_license(txt: Optional[str]) -> Optional[str]:
            if not txt:
                return None
            t = txt.strip()
            low = t.lower()
            patterns = [
                (r"creative\s+commons\s+attribution\s+4\.0", "CC-BY-4.0"),
                (r"creative\s+commons\s+attribution", "CC-BY"),
                (r"cc[- ]by[- ]4\.0", "CC-BY-4.0"),
                (r"cc[- ]by", "CC-BY"),
                (r"mit\s+license", "MIT"),
                (r"gpl\s*v?3", "GPL-3.0"),
                (r"apache\s+2", "Apache-2.0"),
                (r"bsd\s+3", "BSD-3-Clause"),
                (r"bsd\s+2", "BSD-2-Clause"),
                (r"cc0", "CC0"),
            ]
            for pat, rep in patterns:
                if re.search(pat, low):
                    return rep
            # Fallback: collapse whitespace and capitalize common tokens
            t = re.sub(r"\s+", " ", t)
            return t
        data_license = _norm_license(data_license)
        code_license = _norm_license(code_license)

        # Optional link verification/normalization (non-network)
        if settings.ENABLE_LINK_VERIFICATION:
            try:
                from app.services.link_inspector import LinkInspector

                insp = LinkInspector()

                def _sanitize(urls: Optional[List[str]]) -> List[str]:
                    infos = insp.inspect(urls or [])
                    return [i.url for i in infos]

                data_links = _sanitize(data_links)
                code_links = _sanitize(code_links)

                if availability.diagnostics is not None:
                    availability.diagnostics["link_verification"] = {
                        "enabled": True,
                        "data_links": data_links,
                        "code_links": code_links,
                    }
                    if settings.EXPOSE_AVAILABILITY_DEBUG:
                        debug_info = availability.diagnostics
            except Exception:
                # Never fail the core workflow due to enrichment
                pass

        diag = availability.diagnostics if isinstance(availability.diagnostics, dict) else None
        title_src = None
        if title and isinstance(diag, dict):
            td = diag.get("title_debug")
            if isinstance(td, dict):
                src = td.get("source")
                if isinstance(src, str):
                    title_src = src
        # Availability status derivation
        def _status_from(statement: Optional[str], links: List[str], kind: str) -> Optional[str]:
            if not statement:
                return "none"
            s = statement.lower()
            # Future availability patterns
            future_phrases = [
                "will be available",
                "will be made available",
                "will become available",
                "will be deposited",
                "will be archived",
                "available after",
                "available upon publication",
            ]
            if any(p in s for p in future_phrases):
                return "future"
            # Restricted availability patterns
            restricted_phrases = [
                "upon request",
                "available upon request",
                "reasonable request",
                "from the corresponding author",
                "available from the corresponding author",
                "available by request",
                "requests to the corresponding author",
            ]
            if any(p in s for p in restricted_phrases):
                return "restricted"
            # Embedded only (no external repository)
            embedded_phrases = [
                "in the paper",
                "in the article",
                "within the article",
                "in the supplementary",
                "in the supplement",
                "supplementary material",
                "supporting information only",
                "supplementary materials",
            ]
            if kind == "data" and any(p in s for p in embedded_phrases):
                if not links:
                    return "embedded"
            if links:
                return "open"
            return "none"

        data_status = _status_from(data_stmt, data_links, "data")
        code_status = _status_from(code_stmt, code_links, "code")

        # Quality warnings
        quality_warnings: List[str] = []
        def _is_truncated(stmt: Optional[str]) -> bool:
            if not stmt:
                return False
            return bool(re.search(r"https:?$", stmt.strip()))
        if _is_truncated(data_stmt):
            quality_warnings.append("data_statement_truncated_url")
        if _is_truncated(code_stmt):
            quality_warnings.append("code_statement_truncated_url")
        # Fused link detection (raw contexts may have been split; if any http appears >1 in original statement without separator)
        def _fused(stmt: Optional[str]) -> bool:
            if not stmt:
                return False
            s = stmt.lower()
            return s.count("http://") + s.count("https://") > len(data_links) + len(code_links) + 1
        if _fused(data_stmt):
            quality_warnings.append("data_fused_links_possible")
        if _fused(code_stmt):
            quality_warnings.append("code_fused_links_possible")
        # License issues
        if data_license and code_license and data_license == code_license:
            quality_warnings.append("identical_data_code_license")
        if data_license and not re.search(r"\d", data_license) and data_license.startswith("CC-BY"):
            quality_warnings.append("data_license_missing_version")
        # Attach warnings into debug_info for transparency
        if isinstance(debug_info, dict):
            debug_info.setdefault("quality_warnings", quality_warnings)
        else:
            debug_info = {"quality_warnings": quality_warnings}
        return PDFAnalysisResultModel(
            title=title,
            title_source=title_src,
            doi=doi,
            data_availability_statement=data_stmt,
            code_availability_statement=code_stmt,
            data_availability_status=data_status,
            code_availability_status=code_status,
            data_sharing_license=data_license,
            code_license=code_license,
            data_links=data_links,
            code_links=code_links,
            confidence_scores=confidence_scores,
            debug_info=debug_info,
        )
