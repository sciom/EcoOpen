import logging

# Maximum length for valid URLs (user-specified constraint)
MAX_URL_LENGTH = 100

# Simplified logging utility for multiprocessing compatibility
def log_message(level, message):
    """Log a message at the specified level."""
    if level == "INFO":
        logging.info(message)
    elif level == "WARNING":
        logging.warning(message)
    elif level == "ERROR":
        logging.error(message)
    elif level == "DEBUG":
        logging.debug(message)

def is_data_related_url(url, target_formats):
    """Check if a URL is likely to point to a data file."""
    if len(url) > MAX_URL_LENGTH:
        return False
    url_lower = url.lower()
    # Known data repositories
    data_domains = [
        "zenodo.org", "dryad.org", "figshare.com", "github.com", "raw.githubusercontent.com",
        "dataverse.org", "osf.io", "pangaea.de", "genbank", "sra", "geo", "arrayexpress", "ena"
    ]
    # Non-data-related domains to exclude
    exclude_domains = [
        "facebook.com", "twitter.com", "linkedin.com", "instagram.com",
        "login", "signup", "sign-in", "auth", "cookie", "privacy", "terms"
    ]
    # Check for repository domains or target formats
    is_data = (
        any(domain in url_lower for domain in data_domains) or
        any(url_lower.endswith(f".{ext}") for ext in target_formats)
    )
    # Exclude non-data domains
    is_excluded = any(domain in url_lower for domain in exclude_domains)
    return is_data and not is_excluded