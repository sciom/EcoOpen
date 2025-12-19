from __future__ import annotations

import itertools
import statistics
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

try:
    import pdfplumber  # type: ignore
except ImportError:  # pragma: no cover - handled by caller
    pdfplumber = None  # type: ignore


@dataclass
class ParagraphBlock:
    text: str
    page: int
    column: int
    seq: int


class PDFTextNormalizer:
    """Parse PDFs into column-aware, cleaned paragraphs using pdfplumber."""

    def __init__(
        self,
        *,
        line_merge_tolerance: float = 2.5,
        paragraph_gap: float = 12.0,
        min_column_gap_ratio: float = 0.15,
    ) -> None:
        self._line_merge_tolerance = line_merge_tolerance
        self._paragraph_gap = paragraph_gap
        self._min_column_gap_ratio = min_column_gap_ratio
        self._counter = itertools.count()

    def extract(self, path: str) -> List[ParagraphBlock]:
        if pdfplumber is None:
            raise RuntimeError("pdfplumber is required for PDFTextNormalizer")

        blocks: List[ParagraphBlock] = []
        with pdfplumber.open(path) as pdf:
            for page_idx, page in enumerate(pdf.pages, start=1):
                words = page.extract_words(
                    keep_blank_chars=False,
                    use_text_flow=False,
                    extra_attrs=["fontname", "size"],
                )

                # Heuristic: if many single-char "words", rebuild from chars
                if words and self._singleton_ratio(words) > 0.3:
                    try:
                        words = self._rebuild_words_from_chars(page.chars)
                    except Exception:
                        # Fallback to original words on error
                        pass

                if not words:
                    for para in self._split_simple(page.extract_text() or ""):
                        cleaned = self._clean_paragraph(para)
                        if cleaned:
                            blocks.append(
                                ParagraphBlock(
                                    text=cleaned,
                                    page=page_idx,
                                    column=0,
                                    seq=next(self._counter),
                                )
                            )
                    continue

                page_width = float(page.width or 0.0)
                column_groups = self._split_columns(words, page_width)
                for column_index, column_words in enumerate(column_groups):
                    for paragraph in self._words_to_paragraphs(column_words):
                        cleaned = self._clean_paragraph(paragraph)
                        if cleaned:
                            # Debug log for paragraphs containing URL patterns
                            if 'http' in cleaned.lower() and cleaned.endswith((':', 'https:', 'http:')):
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.warning(
                                    f"Incomplete URL detected in paragraph (page {page_idx}, col {column_index}): "
                                    f"'{cleaned[-50:]}'"
                                )
                            blocks.append(
                                ParagraphBlock(
                                    text=cleaned,
                                    page=page_idx,
                                    column=column_index,
                                    seq=next(self._counter),
                                )
                            )

        blocks.sort(key=lambda b: (b.page, b.column, b.seq))
        return blocks

    # ------------------------------------------------------------------ column handling
    def _split_columns(self, words: Sequence[dict], page_width: float) -> List[List[dict]]:
        if not words:
            return []

        centers = sorted((float(w.get("x0", 0.0)) + float(w.get("x1", 0.0))) / 2.0 for w in words)
        if len(centers) < 2 or page_width <= 0:
            return [list(words)]

        gaps: List[Tuple[float, float]] = []
        prev = centers[0]
        for current in centers[1:]:
            gaps.append((current - prev, (current + prev) / 2.0))
            prev = current

        max_gap, split_center = max(gaps, key=lambda item: item[0])
        # Require minimum ratio and a mid-page split
        center_ratio = split_center / max(page_width, 1.0)
        if max_gap < page_width * self._min_column_gap_ratio or not (0.35 <= center_ratio <= 0.65):
            return [list(words)]

        split_x = split_center
        left: List[dict] = []
        right: List[dict] = []
        for word in words:
            center = (float(word.get("x0", 0.0)) + float(word.get("x1", 0.0))) / 2.0
            (left if center <= split_x else right).append(word)

        total = max(1, len(words))
        if len(left) / total < 0.25 or len(right) / total < 0.25:
            # One side too sparse; treat as single-column
            return [list(words)]

        groups: List[List[dict]] = []
        for column_words in (left, right):
            if column_words:
                column_words.sort(key=lambda w: (float(w.get("top", 0.0)), float(w.get("x0", 0.0))))
                groups.append(column_words)
        return groups if groups else [list(words)]

    # ------------------------------------------------------------------ lines & paragraphs
    def _words_to_paragraphs(self, words: Sequence[dict]) -> List[str]:
        if not words:
            return []

        lines: List[List[dict]] = []
        current_line: List[dict] = []
        last_top: float | None = None

        for word in words:
            top = float(word.get("top", 0.0))
            if last_top is None or abs(top - last_top) <= self._line_merge_tolerance:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(current_line)
                current_line = [word]
            last_top = top
        if current_line:
            lines.append(current_line)

        paragraphs: List[str] = []
        buffer: List[str] = []
        last_bottom: float | None = None

        for line_words in lines:
            line_text = self._line_to_text(line_words)
            if not line_text:
                continue
            top = float(line_words[0].get("top", 0.0))
            bottom = float(line_words[-1].get("bottom", 0.0))

            if last_bottom is not None and top - last_bottom > self._paragraph_gap:
                if buffer:
                    paragraphs.append(" ".join(buffer))
                    buffer = []

            buffer.append(line_text)
            last_bottom = bottom

        if buffer:
            paragraphs.append(" ".join(buffer))

        # Post-process paragraphs to merge continuation lines and fix broken URLs
        paragraphs = self._merge_broken_urls(paragraphs)
        
        return self._merge_inline_headings(paragraphs)

    def _line_to_text(self, words: Sequence[dict]) -> str:
        parts: List[str] = []
        for word in words:
            text = (word.get("text") or "").strip()
            if text:
                parts.append(text)
        return " ".join(parts).strip()

    def _merge_inline_headings(self, paragraphs: Sequence[str]) -> List[str]:
        merged: List[str] = []
        skip_next = False
        for idx, para in enumerate(paragraphs):
            if skip_next:
                skip_next = False
                continue
            stripped = para.strip()
            if stripped.endswith(":") and len(stripped) < 80 and idx + 1 < len(paragraphs):
                merged.append(f"{stripped} {paragraphs[idx + 1].strip()}")
                skip_next = True
            else:
                merged.append(stripped)
        return merged

    def _merge_broken_urls(self, paragraphs: Sequence[str]) -> List[str]:
        """Merge paragraphs that contain broken URLs continuing from previous paragraph."""
        if not paragraphs:
            return []
        
        merged: List[str] = []
        i = 0
        while i < len(paragraphs):
            current = paragraphs[i].strip()
            
            # Check if current paragraph ends with incomplete URL (https: or http:)
            if re.search(r'https?:\s*$', current, re.IGNORECASE):
                # Merge with next paragraph until we have a complete URL
                combined = current
                j = i + 1
                found_complete = False
                while j < len(paragraphs) and (j - i) < 3:
                    next_para = paragraphs[j].strip()
                    combined = combined.rstrip() + " " + next_para
                    
                    # Normalize the combined text to fix URL spacing before checking
                    normalized = re.sub(r'(https?)\s*:\s*/\s*/', r'\1://', combined, flags=re.IGNORECASE)
                    
                    # Check for complete URL with domain and TLD
                    if re.search(r'https?://[\w\-]+\.[\w\-]+', normalized, re.IGNORECASE):
                        # Found complete URL - use normalized version
                        merged.append(normalized)
                        i = j + 1
                        found_complete = True
                        break
                    j += 1
                
                if not found_complete:
                    # Didn't find complete URL, normalize and add what we have
                    normalized = re.sub(r'(https?)\s*:\s*/\s*/', r'\1://', combined, flags=re.IGNORECASE)
                    merged.append(normalized)
                    i = j
            else:
                merged.append(current)
                i += 1
        
        return merged

    def _split_simple(self, text: str) -> List[str]:
        if not text:
            return []
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return [chunk.strip() for chunk in normalized.split("\n\n") if chunk.strip()]

    # ------------------------------------------------------------------ cleaning helpers
    def _clean_paragraph(self, text: str) -> str:
        if not text:
            return ""
        cleaned = text
        cleaned = cleaned.replace("\u2013", "-").replace("\u2014", "-")
        cleaned = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", cleaned)
        cleaned = cleaned.replace("\n", " ")
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"\s+\.", ".", cleaned)
        cleaned = re.sub(r"\s+,", ",", cleaned)
        
        # Canonicalize URLs FIRST before any other transformations
        cleaned = self._canonicalize_urls(cleaned)
        
        # Protect URLs from further processing by temporarily replacing them
        url_placeholders: List[Tuple[str, str]] = []
        url_pattern = re.compile(r'https?://[^\s]+', re.IGNORECASE)
        for idx, match in enumerate(url_pattern.finditer(cleaned)):
            placeholder = f"__URL_PLACEHOLDER_{idx}__"
            url_placeholders.append((placeholder, match.group(0)))
        for placeholder, url in url_placeholders:
            cleaned = cleaned.replace(url, placeholder, 1)
        
        # Compact OCR spaced letter sequences (e.g., 't r o p i c a l') into single words
        # Only match sequences that are clearly OCR artifacts (single letters with spaces)
        def _compact(match: re.Match) -> str:
            seq = match.group(0)
            parts = seq.strip().split()
            # Only compact if we have 5+ single letters in sequence
            if len(parts) >= 5 and all(len(p) == 1 and p.isalpha() for p in parts):
                return "".join(parts)
            return seq
        cleaned = re.sub(r"(?:\b[a-zA-Z]\b\s+){4,}[a-zA-Z]\b", _compact, cleaned)
        
        # Restore URLs
        for placeholder, url in url_placeholders:
            cleaned = cleaned.replace(placeholder, url)
        
        # Split fused URLs introduced by missing whitespace (multiple http occurrences).
        cleaned = re.sub(r"(https?://[^\s]{10,}?)(https?://)", r"\1 \2", cleaned)

        lower = cleaned.lower()
        if lower.startswith(("orcid", "keywords", "received", "accepted", "submitted", "correspondence")):
            return ""
        if "©" in cleaned or "copyright" in lower:
            return ""
        if lower.startswith("references"):
            return ""
        return cleaned.strip()

    def _canonicalize_urls(self, text: str) -> str:
        # Step 0: Remove invisible Unicode characters that break URLs
        invisible_chars = [
            '\u200B',  # Zero-width space
            '\u200C',  # Zero-width non-joiner  
            '\u200D',  # Zero-width joiner
            '\u00AD',  # Soft hyphen
            '\uFEFF',  # Zero-width no-break space
        ]
        for char in invisible_chars:
            text = text.replace(char, '')
        
        # Step 1: Remove urldefense wrappers (handle spaces in urldefense itself)
        cleaned = re.sub(
            r'https?://\s*urlde\s*fense\s*\.\s*com\s*/\s*v3\s*/\s*__\s*/?',
            '',
            text,
            flags=re.IGNORECASE,
        )
        
        # Step 2: Fix protocol splits: "http : / /" or "http:/ /" -> "http://"
        cleaned = re.sub(r'(https?)\s*:\s*/\s*/\s*', r'\1://', cleaned, flags=re.IGNORECASE)
        
        # Step 3: Remove spaces within URLs (simple character-by-character)
        result = []
        i = 0
        while i < len(cleaned):
            # Look for http:// or https://
            match = re.match(r'(https?://)', cleaned[i:], re.IGNORECASE)
            if match:
                # Found a URL start
                result.append(match.group(1))
                i += match.end()
                
                # Collect URL characters, removing spaces
                url_chars = []
                while i < len(cleaned) and len(url_chars) < 200:
                    # Check for end of URL: space + common word
                    remaining = cleaned[i:]
                    if remaining.startswith((' and ', ' the ', ' on ', ' at ', ' in ', ' from ', ' or ', ' to ', ' are ', ' is ')):
                        break
                    
                    ch = cleaned[i]
                    # Skip whitespace in URLs
                    if ch in ' \t\n\r':
                        i += 1
                        continue
                    # Collect URL characters
                    elif ch.isalnum() or ch in '.-_/=?&:#%':
                        url_chars.append(ch)
                        i += 1
                    else:
                        # Non-URL character, stop
                        break
                
                result.append(''.join(url_chars))
            else:
                # Regular character, just copy it
                result.append(cleaned[i])
                i += 1
        
        return ''.join(result)

    # ------------------------------------------------------------------ helpers
    def _singleton_ratio(self, words: Sequence[dict]) -> float:
        if not words:
            return 0.0
        singles = 0
        total = 0
        for w in words:
            t = str(w.get("text") or "")
            if not t:
                continue
            total += 1
            if len(t) == 1 and t.isalpha():
                singles += 1
        return singles / total if total else 0.0

    def _rebuild_words_from_chars(self, chars: Sequence[dict]) -> List[dict]:
        # Build lines by y-position, then split into tokens by x-gaps
        if not chars:
            return []
        # Sort by top then x0
        chars_sorted = sorted(chars, key=lambda c: (float(c.get("top", 0.0)), float(c.get("x0", 0.0))))
        lines: List[List[dict]] = []
        current: List[dict] = []
        last_top: float | None = None
        tol = max(1.5, self._line_merge_tolerance)
        for ch in chars_sorted:
            top = float(ch.get("top", 0.0))
            if last_top is None or abs(top - last_top) <= tol:
                current.append(ch)
            else:
                if current:
                    lines.append(current)
                current = [ch]
            last_top = top
        if current:
            lines.append(current)

        rebuilt: List[dict] = []
        for line_chars in lines:
            line_chars = sorted(line_chars, key=lambda c: float(c.get("x0", 0.0)))
            widths = [float(c.get("x1", 0.0)) - float(c.get("x0", 0.0)) for c in line_chars]
            median_w = statistics.median(widths) if widths else 1.0
            gap_threshold = max(1.0, 0.6 * median_w)

            token_chars: List[dict] = []
            prev_x1: float | None = None
            for ch in line_chars:
                x0 = float(ch.get("x0", 0.0))
                if prev_x1 is None or x0 - prev_x1 <= gap_threshold:
                    token_chars.append(ch)
                else:
                    token_text = "".join((str(c.get("text") or "")) for c in token_chars).strip()
                    if token_text:
                        rebuilt.append(
                            {
                                "text": token_text,
                                "x0": float(token_chars[0].get("x0", 0.0)),
                                "x1": float(token_chars[-1].get("x1", 0.0)),
                                "top": float(min(c.get("top", 0.0) for c in token_chars)),
                                "bottom": float(max(c.get("bottom", 0.0) for c in token_chars)),
                            }
                        )
                    token_chars = [ch]
                prev_x1 = float(ch.get("x1", 0.0))
            if token_chars:
                token_text = "".join((str(c.get("text") or "")) for c in token_chars).strip()
                if token_text:
                    rebuilt.append(
                        {
                            "text": token_text,
                            "x0": float(token_chars[0].get("x0", 0.0)),
                            "x1": float(token_chars[-1].get("x1", 0.0)),
                            "top": float(min(c.get("top", 0.0) for c in token_chars)),
                            "bottom": float(max(c.get("bottom", 0.0) for c in token_chars)),
                        }
                    )
        return rebuilt
