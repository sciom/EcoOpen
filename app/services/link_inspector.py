from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


@dataclass
class LinkInfo:
    url: str
    kind: str  # data|code|other


class LinkInspector:
    """Lightweight link normalizer/deduper (no network)."""

    DATA_HINTS = ("zenodo.org", "figshare.com", "dryad", "dataverse", "osf.io", "openneuro", "doi.org/10.")
    CODE_HINTS = ("github.com", "gitlab", "bitbucket", "huggingface.co", "codeberg.org")

    def __init__(self) -> None:
        pass

    def _classify(self, url: str) -> str:
        low = url.lower()
        if any(h in low for h in self.DATA_HINTS):
            return "data"
        if any(h in low for h in self.CODE_HINTS):
            return "code"
        return "other"

    def _normalize(self, url: str) -> Optional[str]:
        url = url.strip()
        if not url:
            return None
        if url.startswith("www."):
            url = "https://" + url
        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            return None
        # strip trailing punctuation
        url = url.rstrip("),.;]")
        return url

    def inspect(self, urls: Iterable[str]) -> List[LinkInfo]:
        seen = set()
        out: List[LinkInfo] = []
        for raw in urls:
            norm = self._normalize(raw)
            if not norm:
                continue
            if norm in seen:
                continue
            seen.add(norm)
            kind = self._classify(norm)
            out.append(LinkInfo(url=norm, kind=kind))
        return out

    def split_kinds(self, infos: Iterable[LinkInfo]) -> Tuple[List[str], List[str], List[str]]:
        data: List[str] = []
        code: List[str] = []
        other: List[str] = []
        for info in infos:
            if info.kind == "data":
                data.append(info.url)
            elif info.kind == "code":
                code.append(info.url)
            else:
                other.append(info.url)
        return data, code, other
