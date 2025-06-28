import logging
from typing import List
from ecoopen.constants import MAX_URL_LENGTH

logger = logging.getLogger(__name__)

def log_message(level: str, message: str) -> None:
    """Log a message at the specified level."""
    if level == "INFO":
        logger.info(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "ERROR":
        logger.error(message)
    elif level == "DEBUG":
        logger.debug(message)

def is_data_related_url(url: str, target_formats: List[str]) -> bool:
    """Check if a URL is likely to point to a data file."""
    if len(url) > MAX_URL_LENGTH:
        return False
    url_lower = url.lower()
    data_domains = [
        "zenodo.org", "dryad.org", "figshare.com", "github.com", "raw.githubusercontent.com",
        "dataverse.org", "osf.io", "pangaea.de", "genbank", "sra", "geo", "arrayexpress", "ena"
    ]
    exclude_domains = [
        "facebook.com", "twitter.com", "linkedin.com", "instagram.com",
        "login", "signup", "sign-in", "auth", "cookie", "privacy", "terms"
    ]
    is_data = (
        any(domain in url_lower for domain in data_domains) or
        any(url_lower.endswith(f".{ext}") for ext in target_formats)
    )
    is_excluded = any(domain in url_lower for domain in exclude_domains)
    return is_data and not is_excluded