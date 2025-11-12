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
    Also supports title-based search to find candidate DOIs.
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

    def _headers(self) -> Dict[str, str]:
        ua_email = (settings.ENRICHMENT_CONTACT_EMAIL or "").strip()
        if ua_email:
            ua = f"EcoOpen/1.0 (+mailto:{ua_email})"
        else:
            ua = "EcoOpen/1.0"
        return {
            "Accept": "application/json",
            "User-Agent": ua,
        }

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
                resp = client.get(url, headers=self._headers())
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

    def _search_crossref_by_title(self, title: str, rows: int = 5) -> Optional[Dict[str, Any]]:
        try:
            params = {"query.title": title, "rows": rows}
            # Be polite: include contact email if provided
            if settings.ENRICHMENT_CONTACT_EMAIL:
                params["mailto"] = settings.ENRICHMENT_CONTACT_EMAIL
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(
                    "https://api.crossref.org/works",
                    headers=self._headers(),
                    params=params,
                )
            if resp.status_code != 200:
                logger.debug("crossref_title_search_non_200 %s %s", resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            items = (data.get("message") or {}).get("items") or []
            best = None
            best_sim = 0.0
            for it in items:
                titles = it.get("title") or []
                t0 = titles[0] if titles else None
                sim = self.title_similarity(t0, title)
                if sim > best_sim:
                    doi = it.get("DOI") or it.get("doi")
                    year = None
                    try:
                        issued = it.get("issued") or {}
                        parts = issued.get("date-parts") or []
                        if parts and parts[0] and parts[0][0]:
                            year = int(parts[0][0])
                    except Exception:
                        year = None
                    best_sim = sim
                    best = {"doi": doi, "title": t0, "issued_year": year, "score": sim, "source": "crossref"}
            return best
        except Exception as e:
            logger.debug("crossref_title_search_error %s", e)
            return None

    def _search_openalex_by_title(self, title: str, rows: int = 5) -> Optional[Dict[str, Any]]:
        try:
            params = {"search": title, "per_page": rows}
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(
                    "https://api.openalex.org/works",
                    headers=self._headers(),
                    params=params,
                )
            if resp.status_code != 200:
                logger.debug("openalex_title_search_non_200 %s %s", resp.status_code, resp.text[:200])
                return None
            data = resp.json() or {}
            items = data.get("results") or []
            best = None
            best_sim = 0.0
            for it in items:
                t0 = it.get("display_name")
                sim = self.title_similarity(t0, title)
                if sim > best_sim:
                    doi_raw = it.get("doi") or ""
                    doi = doi_raw
                    if isinstance(doi_raw, str) and doi_raw.lower().startswith("https://doi.org/"):
                        doi = doi_raw[len("https://doi.org/") :]
                    year = it.get("publication_year")
                    try:
                        year = int(year) if year is not None else None
                    except Exception:
                        year = None
                    best_sim = sim
                    best = {"doi": doi, "title": t0, "issued_year": year, "score": sim, "source": "openalex"}
            return best
        except Exception as e:
            logger.debug("openalex_title_search_error %s", e)
            return None

    def search_by_title(self, title: Optional[str], rows: int = 5) -> Optional[Dict[str, Any]]:
        """
        Query external registries for works matching the given title. Returns the best match
        as a dict: { 'doi': '...', 'title': '...', 'issued_year': 2020, 'score': <similarity>, 'source': 'crossref|openalex' }
        or None if no suitable match.
        """
        if not title:
            return None
        q = title.strip()
        if not q:
            return None
        # Try Crossref first, then OpenAlex; pick the better score
        best_cr = self._search_crossref_by_title(q, rows=rows)
        best_oa = self._search_openalex_by_title(q, rows=rows)
        candidates = [b for b in [best_cr, best_oa] if b and b.get("doi")]
        if not candidates:
            return best_cr or best_oa
        # choose highest score; tie-breaker by configured preference
        candidates.sort(key=lambda d: float(d.get("score", 0.0)), reverse=True)
        top = candidates[0]
        if len(candidates) > 1 and candidates[0].get("score") == candidates[1].get("score"):
            preferred = (settings.DOI_TITLE_SEARCH_PREFERRED_SOURCE or "crossref").lower()
            other = candidates[1]
            if other.get("source") == preferred:
                top = other
        return top
 
