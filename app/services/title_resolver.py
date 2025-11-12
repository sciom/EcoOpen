from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

from app.services.text_normalizer import ParagraphBlock


@dataclass
class TitleResolution:
    title: Optional[str]
    source: str  # heuristic|llm|enriched
    confidence: float


class TitleResolver:
    """Local title resolver that improves heuristic by merging first-page lines.

    This is a non-network baseline to reduce LLM dependence. It can later be
    extended to query external services when toggled on.
    """

    def __init__(self, max_lines: int = 8) -> None:
        self.max_lines = max_lines

    def _normalize(self, s: str) -> str:
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        s = re.sub(r"\s+", " ", s.strip())
        return s

    def _is_bad(self, s: str) -> bool:
        l = s.lower()
        if not s or len(s) < 8 or len(s) > 240:
            return True
        # use whole-word stopword matching to avoid false positives
        if re.search(r"\b(abstract|introduction|copyright|license|doi|keywords)\b", l):
            return True
        words = s.split()
        if len(words) < 2 or len(words) > 45:
            return True
        letters = sum(1 for ch in s if ch.isalpha())
        if letters < 0.5 * len(s):
            return True
        return False

    def _merge_first_page(self, blocks: Sequence[ParagraphBlock]) -> List[str]:
        lines: List[str] = []
        cue_re = re.compile(r"\b(author|affiliation|department|correspondence|university|institute)\b", re.IGNORECASE)
        for b in blocks:
            if b.page != 1:
                break
            if b.column != 0:
                continue
            text = (b.text or "").strip()
            if not text:
                continue
            low = text.lower()
            # If we've already collected some lines, stop on affiliation cues
            if lines and cue_re.search(low):
                break
            for ln in text.split("\n"):
                ln = ln.strip()
                if not ln:
                    continue
                # stop if a line itself looks like affiliation/author
                if cue_re.search(ln):
                    break
                lines.append(ln)
                if len(lines) >= self.max_lines:
                    break
            if len(lines) >= self.max_lines:
                break
        return lines

    def resolve(self, blocks: Sequence[ParagraphBlock]) -> TitleResolution:
        lines = self._merge_first_page(blocks)
        if not lines:
            return TitleResolution(title=None, source="heuristic", confidence=0.0)

        # Try single-line first (first few lines)
        for ln in lines[:4]:
            cand = self._normalize(ln)
            if not self._is_bad(cand):
                return TitleResolution(title=cand, source="heuristic", confidence=0.6)

        # Try merging 2-4 lines with colon/subtitle
        merged: List[str] = []
        for i in range(min(4, len(lines))):
            merged.append(self._normalize(lines[i]))
            cand = ": ".join(merged)
            if not self._is_bad(cand):
                return TitleResolution(title=cand, source="heuristic", confidence=0.56)

        # Try merging 2-4 lines plain spaces (no colon)
        merged_space: List[str] = []
        for i in range(min(4, len(lines))):
            merged_space.append(self._normalize(lines[i]))
            cand2 = " ".join(merged_space)
            if not self._is_bad(cand2):
                return TitleResolution(title=cand2, source="heuristic", confidence=0.54)

        # Fallback: longest reasonable line
        best = max((self._normalize(ln) for ln in lines), key=lambda s: len(s), default="")
        if best and not self._is_bad(best):
            return TitleResolution(title=best, source="heuristic", confidence=0.5)
        return TitleResolution(title=None, source="heuristic", confidence=0.0)
