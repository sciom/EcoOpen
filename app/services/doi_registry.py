import time
import logging
from typing import Optional, Tuple, Dict, Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class DOIRegistry:
    """
    Minimal Crossref-backed DOI lookup with simple in-memory cache.
    Used to verify DOI existence and fetch title metadata for similarity checks.
    """

    _cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def __init__(self, timeout_sec: Optional[int] = None, cache_ttl: Optional[int] = None) -> None:
        self.timeout = float(timeout_sec if timeout_sec is not None else settings.DOI_HTTP_TIMEOUT_SECONDS)
        self.cache_ttl = int(cache_ttl if cache_ttl is not None else settings.DOI_CACHE_TTL)

    @staticmethod
    def _norm_doi(doi: str) -> str:
        return (doi or "").strip().lower()

    def _get_cached(self, doi: str) -> Optional[Dict[str, Any]]:
        key = self._norm_doi(doi)
        if not key:
            return None
        item = self._cache.get(key)
        if not item:
            return None
        ts, data = item
        if self.cache_ttl <= 0 or (time.time() - ts) <= self.cache_ttl:
            return data
        try:
            del self._cache[key]
        except Exception:
            pass
        return None

    def _set_cached(self, doi: str, data: Dict[str, Any]) -> None:
        key = self._norm_doi(doi)
        if not key:
            return
        self._cache[key] = (time.time(), data)

    def lookup(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetch Crossref metadata for a DOI. Returns None on errors.
        Response shape:
          { 'title': '...', 'container_title': '...', 'issued_year': 2020 }
        """
        cached = self._get_cached(doi)
        if cached is not None:
            return cached
        url = f"https://api.crossref.org/works/{doi}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers={"Accept": "application/json"})
            if resp.status_code != 200:
                logger.debug("crossref_non_200 %s %s", resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            msg = data.get("message") or {}
            titles = msg.get("title") or []
            title = titles[0] if titles else None
            container_titles = msg.get("container-title") or []
            container_title = container_titles[0] if container_titles else None
            issued = msg.get("issued") or {}
            year = None
            try:
                parts = issued.get("date-parts") or []
                if parts and parts[0] and parts[0][0]:
                    year = int(parts[0][0])
            except Exception:
                year = None
            rec = {
                "title": title,
                "container_title": container_title,
                "issued_year": year,
            }
            self._set_cached(doi, rec)
            return rec
        except Exception as e:
            logger.debug("crossref_error %s", e)
            return None

    @staticmethod
    def _tokenize_title(s: Optional[str]) -> set:
        if not s:
            return set()
        import re as _re
        tokens = [t for t in _re.findall(r"[A-Za-z0-9]+", s.lower()) if len(t) >= 3]
        return set(tokens)

    def title_similarity(self, a: Optional[str], b: Optional[str]) -> float:
        """Compute a simple Jaccard similarity over alphanumeric tokens (len>=3)."""
        A = self._tokenize_title(a)
        B = self._tokenize_title(b)
        if not A or not B:
            return 0.0
        inter = len(A & B)
        union = len(A | B)
        if union == 0:
            return 0.0
        return inter / union
