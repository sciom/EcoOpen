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
            "data availability statement",
            "data accessibility",
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
        
        # Clean contexts before sending to LLM (remove invisible chars, fix URLs)
        cleaned_data_contexts = []
        for ctx in trimmed_data:
            cleaned_text = self._canonicalize_urls(ctx.text)
            cleaned_data_contexts.append(RankedContext(
                label=ctx.label,
                text=cleaned_text,
                score=ctx.score,
                source=ctx.source,
                index=ctx.index
            ))
        
        cleaned_code_contexts = []
        for ctx in trimmed_code:
            cleaned_text = self._canonicalize_urls(ctx.text)
            cleaned_code_contexts.append(RankedContext(
                label=ctx.label,
                text=cleaned_text,
                score=ctx.score,
                source=ctx.source,
                index=ctx.index
            ))

        llm_payload = None
        llm_raw = None

        if cleaned_data_contexts or cleaned_code_contexts:
            system_prompt, user_prompt = self._build_prompt(cleaned_data_contexts, cleaned_code_contexts)
            try:
                llm_raw = chat_fn(system_prompt, user_prompt)
                llm_payload = self._parse_llm_response(llm_raw)
            except Exception as exc:
                logger.debug("availability_llm_error %s", exc, exc_info=True)
                llm_payload = None

        result_data = self._select_result(
            label="data",
            llm_entry=(llm_payload or {}).get("data") if llm_payload else None,
            contexts=cleaned_data_contexts,  # Use cleaned contexts for validation too
        )
        result_code = self._select_result(
            label="code",
            llm_entry=(llm_payload or {}).get("code") if llm_payload else None,
            contexts=cleaned_code_contexts,  # Use cleaned contexts for validation too
        )

        diag: Dict[str, object] = {}
        if diagnostics:
            diag = {
                "data_contexts": [c.text for c in cleaned_data_contexts],
                "code_contexts": [c.text for c in cleaned_code_contexts],
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
                # BUT: make sure we don't split on colons inside URLs (https:// or http://)
                if label in {"data", "code"}:
                    # Look for heading pattern like "Data Availability:" at start of line
                    # Use a more precise check: colon within first 80 chars, but NOT part of a URL
                    first_line = block.split("\n")[0][:80]
                    if ":" in first_line:
                        # Check if this is a heading (colon not part of URL)
                        # Find first colon that's not part of http:// or https://
                        colon_pos = -1
                        for i, ch in enumerate(first_line):
                            if ch == ':':
                                # Check if this is part of http:// or https://
                                if i > 0 and first_line[max(0, i-5):i+3].lower() in ('http://', 'https://'):
                                    continue
                                # Found a real heading colon
                                colon_pos = i
                                break
                        
                        if colon_pos > 0:
                            # Split on first non-URL colon in the whole block
                            # Find the same position in the full block
                            block_colon_pos = block.find(':', 0, 100)  # Search first 100 chars
                            # Make sure it's not a URL colon
                            if block_colon_pos > 0:
                                before_colon = block[max(0, block_colon_pos-5):block_colon_pos].lower()
                                after_colon = block[block_colon_pos:block_colon_pos+3]
                                if not (before_colon.endswith(('http', 'https')) or after_colon.startswith('//')):
                                    # This is a real heading
                                    head = block[:block_colon_pos]
                                    rest = block[block_colon_pos+1:]
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

        # Identify heading indices to boost the immediate following paragraphs
        heading_indices = {p.index for p in paragraphs if p.label == heading_label}
        neighbor_indices = set()
        for hi in heading_indices:
            neighbor_indices.add(hi + 1)
            neighbor_indices.add(hi + 2)

        for para in paragraphs:
            if not para.text:
                continue
            score = 0.0
            lower = para.text.lower()

            if para.label == heading_label:
                score += 5.0
            elif para.label == "generic":
                score += 1.0

            # Boost paragraphs that immediately follow a relevant heading
            if para.index in neighbor_indices:
                score += 2.2

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

            if para.text.strip().endswith(":") and len(para.text.strip()) < 80:
                score -= 3.0

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
                canonical_raw = self._canonicalize_urls(self._repair_spacing(raw_text))
                if self._quote_in_contexts(canonical_raw, contexts) and self._contains_availability_keywords(canonical_raw, label=label):
                    safe_links = links if isinstance(links, (list, tuple)) else []
                    # Split fused links by looking ahead at new http(s) schemes
                    expanded_links: List[str] = []
                    for entry in safe_links:
                        if isinstance(entry, str) and entry.count("http") > 1:
                            parts = re.split(r"(?=https?://)", entry)
                            for p in parts:
                                p = p.strip()
                                if p:
                                    expanded_links.append(p)
                        elif isinstance(entry, str):
                            expanded_links.append(entry)
                    filtered_links = self._filter_links(canonical_raw, expanded_links, label=label)
                    final_statement_raw = str(clean_stmt).strip() if isinstance(clean_stmt, str) and clean_stmt.strip().lower() != "none" else canonical_raw
                    final_statement = self._canonicalize_urls(self._repair_spacing(final_statement_raw))
                    conf = self._normalize_confidence(confidence, base=0.75)
                    return self._Result(statement=final_statement, raw_quote=canonical_raw, links=filtered_links, confidence=conf, fallback=False)

        # fallback using the best context sentences
        for candidate in contexts:
            trimmed = self._trim_sentences(candidate.text, label=label)
            if not trimmed:
                continue
            extracted_links = self._filter_links(trimmed, [], label=label)
            base_conf = min(0.6, candidate.score / 8.0)
            return self._Result(statement=trimmed, raw_quote=trimmed, links=extracted_links, confidence=base_conf, fallback=True)
        if contexts:
            first = contexts[0]
            cleaned = self._canonicalize_urls(self._repair_spacing(first.text))
            if self._contains_availability_keywords(cleaned, label=label):
                extracted_links = self._filter_links(cleaned, [], label=label)
                base_conf = min(0.4, first.score / 10.0)
                return self._Result(statement=cleaned, raw_quote=None, links=extracted_links, confidence=base_conf, fallback=True)
        return self._Result(statement=None, raw_quote=None, links=[], confidence=0.0, fallback=True)

    def _quote_in_contexts(self, quote: str, contexts: Sequence[RankedContext]) -> bool:
        normalized_quote = _normalize_text(self._canonicalize_urls(quote))
        for ctx in contexts:
            ctx_norm = _normalize_text(self._canonicalize_urls(ctx.text))
            if normalized_quote and normalized_quote in ctx_norm:
                return True
        return False

    def _contains_availability_keywords(self, text: str, *, label: str) -> bool:
        lower = text.lower()
        padding = r"[-\s\w,;:/\(\)]{0,80}"
        pattern_data = re.compile(
            r"(?:code\s+and\s+raw\s+data|data(?:set|s)?|supplementary(?:\s+materials)?|raw data|materials|open data|data availability statement)"
            + padding
            + r"(available|accessible|deposited|provided|shared|request|archiv|badge)",
            re.IGNORECASE,
        )
        pattern_code = re.compile(
            r"(code|software|scripts?|analysis|notebook|pipeline|source code|code availability statement)"
            + padding
            + r"(available|accessible|provided|shared|repository|github|gitlab|bitbucket)",
            re.IGNORECASE,
        )
        return bool(pattern_data.search(text) if label == "data" else pattern_code.search(text))

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
        for sentence in sentences:
            if self._contains_availability_keywords(sentence, label=label):
                return sentence
        for i in range(len(sentences) - 1):
            combo = f"{sentences[i]} {sentences[i + 1]}"
            if self._contains_availability_keywords(combo, label=label):
                return combo
        return None

    def _repair_spacing(self, text: str) -> str:
        repaired = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
        repaired = re.sub(r"\s+", " ", repaired.replace(" - ", "-"))
        repaired = repaired.replace(" ,", ",").replace(" .", ".")
        repaired = re.sub(r"\s+:", ":", repaired)
        return repaired.strip()

    def _canonicalize_urls(self, text: str) -> str:
        # Step 0: Remove invisible Unicode characters (zero-width spaces, soft hyphens, etc)
        # These are common in PDF text extraction artifacts
        invisible_chars = [
            '\u200B',  # Zero-width space
            '\u200C',  # Zero-width non-joiner
            '\u200D',  # Zero-width joiner
            '\u00AD',  # Soft hyphen
            '\uFEFF',  # Zero-width no-break space (BOM)
        ]
        for char in invisible_chars:
            text = text.replace(char, '')
        
        # Remove urldefense wrappers (with spaces)
        cleaned = re.sub(
            r'https?://\s*urlde\s*fense\s*\.\s*com\s*/\s*v3\s*/\s*__\s*/?',
            '',
            text,
            flags=re.IGNORECASE,
        )
        
        # Remove urldefense artifact suffixes like: __;!!N11eV2iwtfs!6catv...
        # These appear after URLs as: .git__;!!randomchars$ 
        # Stop before common words
        cleaned = re.sub(
            r'(__\s*;?\s*!!\s*[A-Za-z0-9!$\-_\s+/=]+?)(\s+(?:and|the|on|at|in|from|or|to|is|are)\b|$)',
            r'\2',  # Keep only the trailing word/space
            cleaned
        )
        
        # Fix intra-domain spacing like "zenod o", "git lab"
        fixed_domains = [
            (r"z\s*e\s*n\s*o\s*d\s*o", "zenodo"),
            (r"d\s*r\s*y\s*a\s*d", "dryad"),
            (r"g\s*i\s*t\s*h\s*u\s*b", "github"),
            (r"g\s*i\s*t\s*l\s*a\s*b", "gitlab"),
            (r"o\s*s\s*f", "osf"),
        ]
        for pat, rep in fixed_domains:
            cleaned = re.sub(pat, rep, cleaned, flags=re.IGNORECASE)
        
        # Merge URL fragments
        pattern = re.compile(r"(https?://[^\s]+)\s+([^\s])")
        for _ in range(10):  # Limit iterations
            def repl(match: re.Match[str]) -> str:
                follower = match.group(2)
                tail = match.string[match.end(0) : match.end(0) + 12]
                if follower in "/?-_=.":
                    return match.group(1) + follower
                if any(ch in "/?-_=." for ch in tail):
                    return match.group(1) + follower
                if match.group(1).endswith(("=", "-", "_")):
                    return match.group(1) + follower
                return match.group(1) + " " + follower

            updated = pattern.sub(repl, cleaned)
            if updated == cleaned:
                break
            cleaned = updated
        
        return cleaned

    def _filter_links(self, context_text: str, links: Iterable[object], *, label: str) -> List[str]:
        collected: List[str] = []
        # Canonicalize any spaced/broken URLs in the context first
        context_text = self._canonicalize_urls(context_text)

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
            # Treat dx.doi.org as doi.org for dataset DOIs; only count dataset DOIs for data, not code
            is_doi_domain = domain in {"doi.org", "dx.doi.org"}
            ok = False
            if domain in allowed:
                ok = True
            elif is_doi_domain and label == "data" and self._is_dataset_doi(clean):
                ok = True
            if ok and validate_url(clean) and clean not in collected:
                collected.append(clean)

        if links:
            for entry in links:
                if isinstance(entry, str):
                    _maybe_add(entry)

        if not collected:
            # First pass simple pattern
            pattern = r"http[s]?://[^\s\)]+"
            raw_matches = re.findall(pattern, context_text)
            # Detect fused URLs and split on subsequent http(s) occurrences
            fixed_matches: List[str] = []
            for m in raw_matches:
                if m.count("http") > 1:
                    parts = re.split(r"(?=https?://)", m)
                    for p in parts:
                        p = p.strip()
                        if p:
                            fixed_matches.append(p)
                else:
                    fixed_matches.append(m)
            for match in fixed_matches:
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
