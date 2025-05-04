import logging
import random
from typing import List, Dict, Optional
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_header_variations() -> List[Dict[str, str]]:
    """Return a list of header variations to mimic different browser behaviors."""
    return [
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/pdf,application/octet-stream,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
            "Connection": "keep-alive"
        },
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
            "Accept": "application/pdf,application/octet-stream,*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://scholar.google.com/",
            "Connection": "keep-alive"
        },
        {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Accept": "application/pdf,application/octet-stream,*/*",
            "Accept-Language": "en-US,en;q=0.8",
            "Referer": "https://www.bing.com/",
            "Connection": "keep-alive"
        }
    ]

def is_pdf_content(content: bytes) -> bool:
    """Check if the content starts with PDF magic bytes."""
    return content.startswith(b"%PDF-")

async def log_response_details(doi: str, response: Optional[aiohttp.ClientResponse]) -> None:
    """Log detailed response information for debugging."""
    if response:
        logging.info(f"Response details for DOI {doi}: Status {response.status}, Headers {response.headers}")
        if response.status != 200:
            try:
                body_snippet = (await response.read())[:200].decode('utf-8', errors='ignore')
                logging.info(f"Response body snippet for DOI {doi}: {body_snippet}")
            except Exception as e:
                logging.warning(f"Could not read response body for DOI {doi}: {e}")
    else:
        logging.warning(f"No response received for DOI {doi}")

async def get_alternative_url(url: str) -> Optional[str]:
    """Generate alternative URLs for fallback attempts."""
    if url.lower().endswith(".pdf"):
        return None
    alternative = f"{url}/pdf"
    logging.info(f"Generated alternative URL: {alternative}")
    return alternative