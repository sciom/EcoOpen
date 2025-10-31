from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.validation import validate_url

logger = logging.getLogger(__name__)


@dataclass
class Paragraph:
    """Lightweight paragraph representation with metadata for validation."""

    text: str
    label: Optional[str]
    index: int


@dataclass
class RankedContext:
    """Scored context fed to the LLM."""

    label: str
    text: str
    score: float
    source: str  # heading | phrase | global
    index: int


@dataclass
class AvailabilityExtraction:
    data_statement: Optional[str]
    code_statement: Optional[str]
    data_links: List[str]
    code_links: List[str]
    data_confidence: float
    code_confidence: float
    diagnostics: Dict[str, object] = field(default_factory=dict)

    @property
    def confidence_scores(self) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        if self.data_statement:
            scores["data_availability"] = self.data_confidence
        if self.code_statement:
            scores["code_availability"] = self.code_confidence
        return scores


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


class AvailabilityEngine:
    """Hybrid extractor that combines LLM extraction with deterministic validation."""

    def __init__(
        self,
        *,
        data_allowed_domains: Sequence[str],
        code_allowed_domains: Sequence[str],
        deny_substrings: Sequence[str],
        dataset_doi_prefixes: Sequence[str],
        max_contexts: int = 8,
    ) -> None:
        self._data_allowed_domains = frozenset(d.lower() for d in data_allowed_domains)
        self._code_allowed_domains = frozenset(d.lower() for d in code_allowed_domains)
        self._deny_substrings = tuple(s.lower() for s in deny_substrings)
        self._dataset_doi_prefixes = tuple(p.lower() for p in dataset_doi_prefixes)
        self._max_contexts = max(2, max_contexts)

        self._data_heading_tokens = (
            "data availability",
            "availability of data",
            "data and materials availability",
            "data accessibility",
            "availability of supporting data",
        )
        self._code_heading_tokens = (
            "code availability",
            "software availability",
            "source code availability",
            "code and data availability",
            "availability of code",
        )
        self._data_keywords = (
            "data availability",
            "data are available",
            "data is available",
            "data deposited",
            "dataset",
            "supplementary data",
            "zenodo",
            "dryad",
            "figshare",
            "osf",
            "dataverse",
            "upon request",
            "reasonable request",
            "repository",
        )
        self._code_keywords = (
            "code availability",
            "code is available",
            "code are available",
            "analysis code",
            "scripts",
            "software",
            "github",
            "gitlab",
            "bitbucket",
            "code ocean",
            "open source",
            "repository",
        )

    # ------------------------------------------------------------------ public API
    def extract(
        self,
        pages: Sequence[str],
        *,
        chat_fn: Callable[[str, str], str],
        diagnostics: bool = False,
    ) -> AvailabilityExtraction:
        paragraphs = self._segment_pages(pages)
        data_contexts = self._rank_contexts(paragraphs, label="data")
        code_contexts = self._rank_contexts(paragraphs, label="code")

        trimmed_data = data_contexts[: self._max_contexts]
        trimmed_code = code_contexts[: self._max_contexts]

        llm_payload = None
        llm_raw = None

        if trimmed_data or trimmed_code:
            system_prompt, user_prompt = self._build_prompt(trimmed_data, trimmed_code)
            try:
                llm_raw = chat_fn(system_prompt, user_prompt)
                llm_payload = self._parse_llm_response(llm_raw)
            except Exception as exc:
                logger.debug("availability_llm_error %s", exc, exc_info=True)
                llm_payload = None

        result_data = self._select_result(
            label="data",
            llm_entry=(llm_payload or {}).get("data") if llm_payload else None,
            contexts=trimmed_data,
        )
        result_code = self._select_result(
            label="code",
            llm_entry=(llm_payload or {}).get("code") if llm_payload else None,
            contexts=trimmed_code,
        )

        diag: Dict[str, object] = {}
        if diagnostics:
            diag = {
                "data_contexts": [c.text for c in trimmed_data],
                "code_contexts": [c.text for c in trimmed_code],
                "llm_raw": llm_raw,
                "llm_payload": llm_payload,
                "data_fallback": result_data.fallback,
                "data_raw_quote": result_data.raw_quote,
                "code_fallback": result_code.fallback,
                "code_raw_quote": result_code.raw_quote,
            }

        return AvailabilityExtraction(
            data_statement=result_data.statement,
            code_statement=result_code.statement,
            data_links=result_data.links,
            code_links=result_code.links,
            data_confidence=result_data.confidence,
            code_confidence=result_code.confidence,
            diagnostics=diag,
        )

    # ------------------------------------------------------------------ segmentation
    def _segment_pages(self, pages: Sequence[str]) -> List[Paragraph]:
        paragraphs: List[Paragraph] = []
        idx = 0
        for raw_page in pages:
            if not raw_page:
                continue
            blocks = [block.strip() for block in re.split(r"\n{2,}", raw_page) if block.strip()]
            for block in blocks:
                normalized = _normalize_text(block)
                label = self._infer_heading(normalized)
                # Inline heading case: "Data availability: ..." -> split once
                if label in {"data", "code"} and ":" in block.split("\n")[0][:80]:
                    head, rest = block.split(":", 1)
                    paragraphs.append(Paragraph(text=_normalize_text(head) + ":", label=label, index=idx))
                    idx += 1
                    remainder = rest.strip()
                    if remainder:
                        paragraphs.append(Paragraph(text=_normalize_text(remainder), label=None, index=idx))
                        idx += 1
                    continue
                paragraphs.append(Paragraph(text=normalized, label=label, index=idx))
                idx += 1
        return paragraphs

    def _infer_heading(self, text: str) -> Optional[str]:
        lowered = text.lower()
        for token in self._data_heading_tokens:
            if lowered.startswith(token):
                return "data"
        for token in self._code_heading_tokens:
            if lowered.startswith(token):
                return "code"
        if len(text.split()) <= 6 and text.isupper():
            return "generic"
        return None

    # ------------------------------------------------------------------ ranking
    def _rank_contexts(self, paragraphs: Sequence[Paragraph], *, label: str) -> List[RankedContext]:
        contexts: List[RankedContext] = []
        keywords = self._data_keywords if label == "data" else self._code_keywords
        heading_label = label

        for para in paragraphs:
            if not para.text:
                continue
            score = 0.0
            lower = para.text.lower()

            if para.label == heading_label:
                score += 5.0
            elif para.label == "generic":
                score += 1.0

            for kw in keywords:
                if kw in lower:
                    score += 1.4

            if "available" in lower and label in lower:
                score += 1.2
            if "upon request" in lower or "reasonable request" in lower:
                score += 0.5
            if "supplementary" in lower or "supporting information" in lower:
                score += 0.4

            if any(deny in lower for deny in self._deny_substrings):
                score -= 1.5

            if score <= 0.5:
                continue

            source = "heading" if para.label == heading_label else "phrase"
            contexts.append(RankedContext(label=label, text=para.text, score=score, source=source, index=para.index))

        # Fallback: if nothing scored, use the entire doc (rare but defensive)
        if not contexts and paragraphs:
            merged = " ".join(p.text for p in paragraphs)
            contexts.append(RankedContext(label=label, text=_normalize_text(merged), score=1.0, source="global", index=0))

        contexts.sort(key=lambda c: (c.score, -c.index), reverse=True)
        return contexts

    # ------------------------------------------------------------------ prompt + parsing
    def _build_prompt(self, data_ctx: Sequence[RankedContext], code_ctx: Sequence[RankedContext]) -> Tuple[str, str]:
        system = (
            "You extract data and code availability statements from scientific papers. "
            "Use ONLY the provided contexts. "
            "If information exists, copy the exact sentence(s) into raw_quote and provide a clean_statement that repairs hyphenation/spaces but keeps the same meaning. "
            "If information is missing, respond with \"none\"."
        )

        def format_block(label: str, ctxs: Sequence[RankedContext]) -> str:
            lines = []
            for idx, ctx in enumerate(ctxs, start=1):
                lines.append(f"[{label.upper()} #{idx}] {ctx.text}")
            return "\n".join(lines)

        user_sections = [
            "CONTEXTS:",
            format_block("data", data_ctx) if data_ctx else "[DATA] none",
            format_block("code", code_ctx) if code_ctx else "[CODE] none",
            "",
            "Respond with strict JSON:",
            "{",
            '  "data": { "verdict": "present|absent", "raw_quote": "... or none", "clean_statement": "... or none", "links": ["..."], "confidence": 0-1 },',
            '  "code": { "verdict": "present|absent", "raw_quote": "... or none", "clean_statement": "... or none", "links": ["..."], "confidence": 0-1 }',
            "}",
            "Rules:",
            "- raw_quote must be contiguous text copied exactly from a single provided context (include complete sentence(s) explicitly describing availability).",
            "- clean_statement may fix broken words or spacing but must not introduce new facts.",
            "- Links must appear in the same context as the raw_quote.",
            "- Use absolute URLs only; omit ORCID or unrelated references.",
            '- If unavailable, set verdict "absent", raw_quote "none", clean_statement "none", and links [].',
        ]
        user = "\n".join(section for section in user_sections if section)
        return system, user

    def _parse_llm_response(self, raw: str) -> Optional[Dict[str, Dict[str, object]]]:
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Attempt to extract JSON between braces
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
            except Exception:
                return None
        if not isinstance(data, dict):
            return None
        payload: Dict[str, Dict[str, object]] = {}
        for key in ("data", "code"):
            entry = data.get(key)
            if isinstance(entry, dict):
                payload[key] = entry
        return payload or None

    # ------------------------------------------------------------------ validation + fallback
    @dataclass
    class _Result:
        statement: Optional[str]
        raw_quote: Optional[str]
        links: List[str]
        confidence: float
        fallback: bool

    def _select_result(
        self,
        *,
        label: str,
        llm_entry: Optional[Dict[str, object]],
        contexts: Sequence[RankedContext],
    ) -> "_Result":
        if llm_entry:
            verdict = str(llm_entry.get("verdict") or "").lower()
            raw_quote = llm_entry.get("raw_quote")
            clean_stmt = llm_entry.get("clean_statement")
            links = llm_entry.get("links")
            confidence = llm_entry.get("confidence")
            raw_text = str(raw_quote).strip() if isinstance(raw_quote, str) else ""
            if verdict == "present" and raw_text and raw_text.lower() != "none":
                if self._quote_in_contexts(raw_text, contexts) and self._contains_availability_keywords(raw_text, label=label):
                    filtered_links = self._filter_links(raw_text, links, label=label)
                    final_statement = str(clean_stmt).strip() if isinstance(clean_stmt, str) and clean_stmt.strip().lower() != "none" else raw_text
                    final_statement = self._repair_spacing(final_statement)
                    conf = self._normalize_confidence(confidence, base=0.75)
                    return self._Result(statement=final_statement, raw_quote=raw_text, links=filtered_links, confidence=conf, fallback=False)

        # fallback using the best context sentences
        if not contexts:
            return self._Result(statement=None, raw_quote=None, links=[], confidence=0.0, fallback=True)

        best = contexts[0]
        trimmed = self._trim_sentences(best.text, label=label)
        if not trimmed:
            return self._Result(statement=None, raw_quote=None, links=[], confidence=0.0, fallback=True)
        extracted_links = self._filter_links(trimmed, [], label=label)
        base_conf = min(0.6, best.score / 8.0)
        return self._Result(statement=trimmed, raw_quote=trimmed, links=extracted_links, confidence=base_conf, fallback=True)

    def _quote_in_contexts(self, quote: str, contexts: Sequence[RankedContext]) -> bool:
        normalized_quote = _normalize_text(quote)
        for ctx in contexts:
            ctx_norm = _normalize_text(ctx.text)
            if normalized_quote and normalized_quote in ctx_norm:
                return True
        return False

    def _contains_availability_keywords(self, text: str, *, label: str) -> bool:
        lower = text.lower()
        if not any(token in lower for token in ("avail", "accessible", "access", "request", "provided", "supplied", "deposited", "archived", "shared")):
            return False
        if label == "data":
            return any(term in lower for term in ("data", "dataset", "supplementary", "repository", "zenodo", "dryad", "figshare", "osf", "dataverse", "pangaea", "archive"))
        return any(term in lower for term in ("code", "software", "script", "analysis", "github", "gitlab", "bitbucket", "source", "notebook"))

    def _normalize_confidence(self, value: object, *, base: float) -> float:
        if isinstance(value, (int, float)):
            try:
                return max(0.0, min(1.0, float(value)))
            except Exception:
                return base
        return base

    def _trim_sentences(self, text: str, *, label: str) -> Optional[str]:
        sentences = re.split(r"(?<=[\.!?])\s+(?=[A-Z0-9])", text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return None
        if len(sentences) == 1:
            return sentences[0]
        preferred: List[str] = []
        for sentence in sentences:
            low = sentence.lower()
            if label == "data" and ("data" in low and "avail" in low):
                preferred.append(sentence)
            elif label == "code" and (("code" in low or "software" in low) and ("avail" in low or "github" in low or "gitlab" in low)):
                preferred.append(sentence)
            if preferred:
                break
        if preferred:
            return " ".join(preferred)
        return " ".join(sentences[:2])

    def _repair_spacing(self, text: str) -> str:
        repaired = re.sub(r"\s+", " ", text.replace(" - ", "-"))
        repaired = repaired.replace(" ,", ",").replace(" .", ".")
        repaired = re.sub(r"\s+:", ":", repaired)
        return repaired.strip()

    def _filter_links(self, context_text: str, links: Iterable[object], *, label: str) -> List[str]:
        collected: List[str] = []

        def _maybe_add(url: str) -> None:
            clean = url.strip().rstrip(".,;)]}")
            if not clean.startswith(("http://", "https://")):
                if clean.lower().startswith("www."):
                    clean = "https://" + clean
                else:
                    return
            low = clean.lower()
            if any(sub in low for sub in self._deny_substrings):
                return
            domain = self._domain(clean)
            if not domain:
                return
            allowed = self._data_allowed_domains if label == "data" else self._code_allowed_domains
            if domain in allowed or (domain == "doi.org" and self._is_dataset_doi(clean)):
                if validate_url(clean) and clean not in collected:
                    collected.append(clean)

        if links:
            for entry in links:
                if isinstance(entry, str):
                    _maybe_add(entry)

        if not collected:
            pattern = r"http[s]?://[^\s\)]+"
            for match in re.findall(pattern, context_text):
                _maybe_add(match)

        return collected

    def _domain(self, url: str) -> Optional[str]:
        match = re.match(r"^https?://([^/]+)", url, flags=re.IGNORECASE)
        if not match:
            return None
        domain = match.group(1).lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _is_dataset_doi(self, url: str) -> bool:
        if "doi.org/" not in url.lower():
            return False
        doi = url.lower().split("doi.org/", 1)[1]
        return any(doi.startswith(prefix) for prefix in self._dataset_doi_prefixes)
