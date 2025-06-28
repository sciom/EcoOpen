import pandas as pd
import requests
import re
import time
import random
from tqdm import tqdm
from pyalex import Works
from urllib.parse import quote, urlparse, urljoin, unquote
import fitz  # PyMuPDF for PDF text extraction
import io
import logging
from bs4 import BeautifulSoup
import os
import spacy
from ecoopen.keywords import keywords, DATA_AVAILABILITY_KEYWORDS, CODE_AVAILABILITY_KEYWORDS  # Absolute import
from ecoopen.data_mining import find_data_urls  # Import from data_mining
from ecoopen.utils_misc import log_message, is_data_related_url  # Import from utils_misc
import unicodedata
import signal
from ratelimit import limits, sleep_and_retry
from typing import Any, Dict, List, Optional, Tuple, Union
from ecoopen.constants import USER_AGENTS, MAX_URL_LENGTH, MAX_STATEMENT_LENGTH

logger = logging.getLogger(__name__)

# Try to import LLM extractor (optional dependency)
try:
    from ecoopen.llm_extractor import extract_all_information_llm, LLMDataExtractor
    LLM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LLM extractor not available: {e}")
    LLM_AVAILABLE = False
    extract_all_information_llm = None
    LLMDataExtractor = None

# Configuration
DOWNLOAD_DIR = "./downloads"
DATA_DOWNLOAD_DIR = "./data_downloads"
LOG_FILE = "ecoopen.log"
DEFAULT_DATA_FORMATS = ["csv", "tsv", "txt", "xlsx", "xls", "zip", "rar", "tar.gz"]
MAX_STATEMENT_LENGTH = 500  # Maximum length for availability statements
MAX_URL_LENGTH = 100  # Maximum length for valid URLs

# Initialize logging
def init_logging():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        filemode='a'  # Append to log file
    )

init_logging()  # Initialize for main process

# Initialize the spaCy NLP pipeline with minimal components
nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer", "tagger"])

# Compile accession number patterns at module level to avoid warnings
ACCESSION_PATTERNS = [re.compile(pattern) for pattern in keywords["accession_nr"]]

def validate_doi(doi):
    """Validate DOI format using regex."""
    doi_pattern = r'^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$'
    try:
        return bool(re.match(doi_pattern, doi))
    except TypeError:
        logger.warning(f"Invalid DOI format: {doi}")
        return False

def create_download_dir(download_dir=DOWNLOAD_DIR):
    """Create download directory if it doesn't exist."""
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        logger.info(f"Created download directory: {download_dir}")

def create_data_download_dir(data_download_dir=DATA_DOWNLOAD_DIR):
    """Create data download directory if it doesn't exist."""
    if not os.path.exists(data_download_dir):
        os.makedirs(data_download_dir)
        logger.info(f"Created data download directory: {data_download_dir}")

def create_article_subfolder(data_download_dir, identifier, doi):
    """Create a subfolder for an article based on identifier and DOI."""
    safe_doi = doi.replace('/', '_')
    subfolder_name = f"{identifier}_{safe_doi}"
    subfolder_path = os.path.join(data_download_dir, subfolder_name)
    if not os.path.exists(subfolder_path):
        os.makedirs(subfolder_path)
        logger.info(f"Created article subfolder: {subfolder_path}")
    return subfolder_path

def sanitize_filename(text, max_length=50):
    """Sanitize a string to be used in filenames."""
    text = re.sub(r'[<>:"/\\|?*]', '_', text)
    text = text.replace(' ', '_')
    text = re.sub(r'[^a-zA-Z0-9_-]', '', text)
    return text[:max_length]

def clean_text(text: str) -> str:
    """Clean text by removing invisible Unicode characters."""
    cleaned_text = unicodedata.normalize('NFKD', text)
    cleaned_text = ''.join(c for c in cleaned_text if unicodedata.category(c) not in ('Cf', 'Cc', 'Cn'))
    logger.debug(f"Cleaned text from '{text[:100]}...' to '{cleaned_text[:100]}...'")
    return cleaned_text

def truncate_statement(statement: str, max_length: int = MAX_STATEMENT_LENGTH) -> str:
    """Truncate a statement to a maximum length, adding ellipsis if needed."""
    if len(statement) > max_length:
        statement = statement[:max_length - 3] + "..."
        logger.debug(f"Truncated statement to {max_length} characters: {statement}")
    return statement

@sleep_and_retry
@limits(calls=5, period=120)  # Reduced calls to avoid rate limits
def get_unpaywall_data(doi: str, email: Optional[str] = None) -> Tuple[bool, bool, List[str]]:
    """Query Unpaywall for open-access status and full-text URL."""
    logger.debug(f"Starting Unpaywall query for DOI: {doi}")
    if email is None:
        email = os.getenv("UNPAYWALL_EMAIL")
    if not email:
        raise ValueError("An email address is required for Unpaywall API requests.")
    try:
        url = f"https://api.unpaywall.org/v2/{quote(doi)}?email={email}"
        logger.debug(f"Unpaywall API URL: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        is_oa = data.get("is_oa", False)
        fulltext_urls = []
        oa_locations = data.get("oa_locations", [])
        if is_oa and oa_locations:
            repo_urls = []
            publisher_urls = []
            for location in oa_locations:
                url_to_add = location.get("url_for_pdf") or location.get("url_for_landing_page") or location.get("url")
                if url_to_add and len(url_to_add) <= MAX_URL_LENGTH:
                    if location.get("host_type") == "repository":
                        repo_urls.append(url_to_add)
                    else:
                        publisher_urls.append(url_to_add)
            fulltext_urls = repo_urls + publisher_urls
        has_fulltext = bool(fulltext_urls)
        logger.info(f"Unpaywall for DOI {doi}: is_oa={is_oa}, has_fulltext={has_fulltext}, fulltext_urls={fulltext_urls}")
        return is_oa, has_fulltext, fulltext_urls
    except requests.exceptions.RequestException as e:
        logger.error(f"Unpaywall error for DOI {doi}: {str(e)}")
        return False, False, []

def get_crossref_journal(doi: str) -> str:
    """Query CrossRef for journal name as a fallback."""
    url = f"https://api.crossref.org/works/{quote(doi)}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        journal = data["message"].get("container-title", [""])[0]
        logger.debug(f"CrossRef journal for DOI {doi}: {journal}")
        return journal
    except requests.exceptions.RequestException as e:
        logger.error(f"CrossRef error for DOI {doi}: {str(e)}")
        return ""

@sleep_and_retry
@limits(calls=5, period=120)  # Reduced calls to avoid rate limits
def get_openalex_data(doi: str) -> Tuple[str, str, str, str, str, Optional[str]]:
    """Query OpenAlex for metadata and potential PDF URL with CrossRef fallback."""
    logger.debug(f"Starting OpenAlex query for DOI: {doi}")
    try:
        work = Works().filter(doi=doi).get()
        if work:
            work = work[0]
            title = work.get("title", "")
            authors = ", ".join([auth["author"]["display_name"] for auth in work.get("authorships", [])])
            published = work.get("publication_date", "")
            host_venue = work.get("host_venue", {})
            journal = host_venue.get("display_name", "")
            if not journal:
                journal = get_crossref_journal(doi)
            url = host_venue.get("url", "")
            pdf_url = work.get("open_access", {}).get("oa_url", None)
            if pdf_url and len(pdf_url) > MAX_URL_LENGTH:
                pdf_url = None
            logger.info(f"OpenAlex for DOI {doi}: pdf_url={pdf_url}, landing_page_url={url}, journal={journal}")
            return title, authors, published, journal, url, pdf_url
        return "", "", "", "", "", None
    except Exception as e:
        logger.error(f"OpenAlex error for DOI {doi}: {str(e)}")
        journal = get_crossref_journal(doi)
        return "", "", "", journal, "", None

def find_pdf_url_from_landing_page(url, session):
    """Attempt to find a PDF URL by scraping the landing page."""
    logger.debug(f"Scraping landing page for PDF URL: {url}")
    try:
        response = session.get(url, timeout=15, allow_redirects=True)
        response.raise_for_status()
        if "text/html" in response.headers.get("content-type", "").lower():
            soup = BeautifulSoup(response.text, "html.parser")
            pdf_links = soup.find_all("a", href=re.compile(r"\.pdf(?:\?.*)?$", re.I))
            for link in pdf_links:
                href = link.get("href")
                if href and len(href) <= MAX_URL_LENGTH:
                    if href.startswith("http"):
                        logger.debug(f"Found PDF URL: {href}")
                        return href
                    full_url = urljoin(url, href)
                    if len(full_url) <= MAX_URL_LENGTH:
                        logger.debug(f"Found PDF URL (relative): {full_url}")
                        return full_url
            download_links = soup.find_all("a", text=re.compile(r"download.*pdf|pdf.*download", re.I))
            for link in download_links:
                href = link.get("href")
                if href and len(href) <= MAX_URL_LENGTH:
                    if href.startswith("http"):
                        logger.debug(f"Found PDF URL via download link: {href}")
                        return href
                    full_url = urljoin(url, href)
                    if len(full_url) <= MAX_URL_LENGTH:
                        logger.debug(f"Found PDF URL via download link (relative): {full_url}")
                        return full_url
        logger.debug(f"No PDF URL found on landing page: {url}")
        return None
    except Exception as e:
        logger.error(f"Error scraping PDF URL from landing page {url}: {str(e)}")
        return None

def download_pdf(doi, urls, save_to_disk=True, download_dir=DOWNLOAD_DIR, identifier="001", title="unknown"):
    """Download PDF from a list of URLs and return binary content."""
    logger.debug(f"Starting PDF download for DOI: {doi}, URLs: {urls}")
    session = requests.Session()
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1",
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    session.headers.update(headers)
    
    safe_doi = doi.replace('/', '_')
    safe_title = sanitize_filename(title)
    filename = f"{identifier}_{safe_doi}_{safe_title}.pdf"
    file_path = os.path.join(download_dir, filename) if save_to_disk else ""
    
    for url in urls:
        if len(url) > MAX_URL_LENGTH:
            logger.warning(f"Skipping PDF URL due to length > {MAX_URL_LENGTH}: {url[:100]}...")
            continue
        logger.info(f"Attempting PDF download from URL: {url}")
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path.rsplit('/', 1)[0]}"
        headers["Referer"] = base_url
        session.headers.update(headers)

        try:
            logger.debug(f"Visiting landing page: {base_url}")
            landing_response = session.get(base_url, timeout=15, allow_redirects=True)
            landing_response.raise_for_status()
            logger.info(f"Visited landing page for DOI {doi}: {base_url}, Cookies: {session.cookies.get_dict()}")
        except Exception as e:
            logger.warning(f"Failed to visit landing page for DOI {doi}: {base_url}, Error: {str(e)}")

        url_variants = [url]
        if "version=" in url:
            url_without_version = url.split("?")[0]
            url_variants.append(url_without_version)

        for pdf_url in url_variants:
            if len(pdf_url) > MAX_URL_LENGTH:
                logger.warning(f"Skipping PDF URL variant due to length > {MAX_URL_LENGTH}: {pdf_url[:100]}...")
                continue
            for attempt in range(3):
                try:
                    if not pdf_url or not pdf_url.startswith(('http://', 'https://')):
                        logger.error(f"Invalid or missing URL for DOI {doi}: {pdf_url}")
                        break
                    logger.info(f"Attempt {attempt + 1}/3 for DOI {doi} with URL: {pdf_url}")
                    headers["User-Agent"] = random.choice(user_agents)
                    session.headers.update(headers)
                    response = session.get(pdf_url, timeout=15, stream=True, allow_redirects=True)
                    if response.status_code == 403:
                        logger.warning(f"403 Forbidden for DOI {doi}, Response Headers: {response.headers}, Content: {response.text[:500]}...")
                        time.sleep(random.uniform(5, 10))
                        alt_pdf_url = find_pdf_url_from_landing_page(base_url, session)
                        if alt_pdf_url and len(alt_pdf_url) <= MAX_URL_LENGTH:
                            logger.info(f"Found alternative PDF URL via scraping: {alt_pdf_url}")
                            response = session.get(alt_pdf_url, timeout=15, stream=True, allow_redirects=True)
                            response.raise_for_status()
                        else:
                            continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    logger.debug(f"Content-Type of response: {content_type}")
                    if "pdf" not in content_type and "octet-stream" not in content_type:
                        if not pdf_url.endswith(".pdf"):
                            new_url = pdf_url.rstrip("/") + "/pdf"
                            if len(new_url) > MAX_URL_LENGTH:
                                logger.warning(f"Skipping modified PDF URL due to length > {MAX_URL_LENGTH}: {new_url[:100]}...")
                                continue
                            logger.info(f"URL not a PDF, trying modified URL for DOI {doi}: {new_url}")
                            response = session.get(new_url, timeout=15, stream=True, allow_redirects=True)
                            response.raise_for_status()
                            content_type = response.headers.get("content-type", "").lower()
                            logger.debug(f"Content-Type of modified URL response: {content_type}")
                            if "pdf" not in content_type and "octet-stream" not in content_type:
                                pdf_url_from_landing = find_pdf_url_from_landing_page(base_url, session)
                                if pdf_url_from_landing and len(pdf_url_from_landing) <= MAX_URL_LENGTH:
                                    logger.info(f"Found PDF URL via scraping for DOI {doi}: {pdf_url_from_landing}")
                                    response = session.get(pdf_url_from_landing, timeout=15, stream=True, allow_redirects=True)
                                    response.raise_for_status()
                                    content_type = response.headers.get("content-type", "").lower()
                                    logger.debug(f"Content-Type of scraped URL response: {content_type}")
                                    if "pdf" not in content_type and "octet-stream" not in content_type:
                                        logger.warning(f"Scraped URL for DOI {doi} does not point to a PDF: {pdf_url_from_landing}, Content-Type: {content_type}")
                                        break
                                else:
                                    logger.warning(f"No PDF URL found after scraping for DOI {doi}, Content-Type: {content_type}")
                                    break
                    pdf_content = b"".join(response.iter_content(chunk_size=8192))
                    pdf_content_length = len(pdf_content)
                    logger.debug(f"PDF content length: {pdf_content_length} bytes")
                    if save_to_disk:
                        create_download_dir(download_dir)
                        with open(file_path, "wb") as f:
                            f.write(pdf_content)
                        logger.info(f"Saved PDF for DOI {doi} to {file_path} (size: {pdf_content_length} bytes)")
                    else:
                        logger.info(f"Downloaded PDF content for DOI {doi} (size: {pdf_content_length} bytes, not saved to disk)")
                    return True, pdf_content, pdf_content_length, file_path
                except Exception as e:
                    logger.error(f"Download error for DOI {doi}: {str(e)} (URL: {pdf_url})")
                    if attempt < 2:
                        time.sleep(random.uniform(5, 10))
                    continue
            logger.info(f"All attempts failed for URL: {pdf_url}")
    return False, None, 0, ""

def download_data_file(url, doi, data_download_dir, target_formats, identifier="001", title="unknown", recursion_depth=0):
    """Download a data file if it matches the target formats, saving to an article-specific subfolder."""
    logger.debug(f"Starting data download for URL: {url}, DOI: {doi}, recursion_depth: {recursion_depth}")
    if recursion_depth > 1:  # Limit recursion to one level
        logger.info(f"Maximum recursion depth reached for URL {url}")
        return None
    
    if len(url) > MAX_URL_LENGTH:
        logger.warning(f"Skipping data URL due to length > {MAX_URL_LENGTH}: {url[:100]}...")
        return None
    
    target_formats_lower = [ext.lower().lstrip('.') for ext in target_formats]
    logger.debug(f"Target formats (lowercase): {target_formats_lower}")
    
    article_subfolder = create_article_subfolder(data_download_dir, identifier, doi)
    
    parsed_url = urlparse(url)
    path = parsed_url.path.lower()
    logger.info(f"Checking URL for download: {url}, path: {path}")
    
    if not is_data_related_url(url, target_formats_lower):
        logger.info(f"Skipping non-data-related URL: {url}")
        return None
    
    if any(path.endswith(f".{ext}") for ext in target_formats_lower):
        try:
            session = requests.Session()
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            ]
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
            session.headers.update(headers)
            logger.debug(f"Headers for download session: {headers}")

            logger.debug(f"Sending GET request to URL: {url}")
            response = session.get(url, timeout=15, stream=True, allow_redirects=True)
            logger.debug(f"Response status code: {response.status_code}")
            response.raise_for_status()

            filename = None
            content_disposition = response.headers.get("content-disposition", "")
            logger.debug(f"Content-Disposition header: {content_disposition}")
            if "filename=" in content_disposition.lower():
                filename = re.findall(r'filename="(.+)"', content_disposition)
                filename = filename[0] if filename else None
                logger.debug(f"Filename extracted from Content-Disposition: {filename}")
            if not filename:
                filename = os.path.basename(parsed_url.path) or "downloaded_data"
                logger.debug(f"Filename extracted from URL path: {filename}")
            
            if not any(filename.lower().endswith(f".{ext}") for ext in target_formats_lower):
                content_type = response.headers.get("content-type", "").lower()
                logger.debug(f"Content-Type of downloaded file: {content_type}")
                if "csv" in content_type:
                    filename += ".csv"
                elif "excel" in content_type or "spreadsheet" in content_type:
                    filename += ".xlsx"
                elif "text" in content_type:
                    filename += ".txt"
                elif "zip" in content_type:
                    filename += ".zip"
                elif "rar" in content_type:
                    filename += ".rar"
                elif "tar" in content_type:
                    filename += ".tar.gz"
                else:
                    logger.info(f"Skipping data URL {url} for DOI {doi}: unable to determine file format from Content-Type: {content_type}")
                    return None
                logger.debug(f"Updated filename with inferred extension: {filename}")

            base_filename, ext = os.path.splitext(filename)
            safe_filename = f"{base_filename}{ext}"
            file_path = os.path.join(article_subfolder, safe_filename)
            logger.debug(f"Safe filename for download: {safe_filename}, full path: {file_path}")

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        logger.debug(f"Wrote chunk of {len(chunk)} bytes to {file_path}")
            
            file_size = os.path.getsize(file_path) / 1024
            logger.info(f"Downloaded data file for DOI {doi} to {file_path} (size: {file_size:.2f} KB)")
            return file_path
        except Exception as e:
            logger.error(f"Failed to download data file from {url} for DOI {doi}: {str(e)}")
            return None
    
    logger.info(f"URL {url} does not directly match target formats, attempting to scrape for data files")
    session = requests.Session()
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    session.headers.update(headers)
    logger.debug(f"Headers for scraping session: {headers}")
    new_urls = find_data_urls(url, session, target_formats_lower, max_depth=1)
    logger.debug(f"Found potential data URLs after scraping: {new_urls}")
    if not new_urls:
        logger.info(f"No downloadable files found for URL {url}")
        return None
    
    downloaded_files = []
    for new_url in new_urls:
        file_path = download_data_file(
            new_url, doi, data_download_dir, target_formats, identifier, title, recursion_depth + 1
        )
        if file_path:
            downloaded_files.append(file_path)
    
    return downloaded_files[0] if downloaded_files else None

def timeout_handler(signum, frame):
    """Handle timeout for PDF extraction."""
    raise TimeoutError("PDF extraction timed out")

def extract_text_from_pdf(pdf_content):
    """Extract text from PDF content (binary string) with timeout."""
    logger.debug(f"Starting PDF text extraction, content length: {len(pdf_content) if pdf_content else 0} bytes")
    try:
        if not pdf_content:
            return ""
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)  # 30-second timeout
        doc = fitz.open("pdf", pdf_content)
        text = ""
        for page in doc:
            page_text = page.get_text("text")
            text += page_text
            logger.debug(f"Extracted text from page, length: {len(page_text)} characters")
        doc.close()
        signal.alarm(0)  # Disable alarm
        logger.info(f"Extracted text from PDF (length: {len(text)} characters)")
        return clean_text(text)
    except Exception as e:
        signal.alarm(0)  # Disable alarm on error
        logger.error(f"Error extracting text from PDF: {str(e)}")
        return ""

# --- Enhanced Extraction Logic ---

def extract_dois_from_text(text: str) -> List[str]:
    """Extract DOIs from text using robust regex."""
    doi_pattern = r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+"
    found = re.findall(doi_pattern, text)
    # Clean and deduplicate
    dois = list({doi.strip('.,;:()[]<>') for doi in found if validate_doi(doi)})
    logger.debug(f"Extracted DOIs: {dois}")
    return dois

def extract_accessions_from_text(text: str) -> List[str]:
    """Extract accession numbers using stricter patterns (e.g., PRJNA123456, SRR123456, GSE123456)."""
    # Common bio accession patterns (add more as needed)
    patterns = [
        r"PRJNA\d{6,}", r"SRR\d{6,}", r"GSE\d{6,}", r"GSM\d{6,}", r"EGAS\d{6,}", r"EGAD\d{6,}",
        r"ENA\d{6,}", r"E-MTAB-\d{3,}", r"PXD\d{6,}", r"SAMN\d{6,}", r"DRR\d{6,}", r"ERR\d{6,}",
        r"SRX\d{6,}", r"ERX\d{6,}", r"DRX\d{6,}", r"SRS\d{6,}", r"ERS\d{6,}", r"DRS\d{6,}"
    ]
    found = set()
    for pat in patterns:
        found.update(re.findall(pat, text))
    accessions = list(found)
    logger.debug(f"Extracted accessions: {accessions}")
    return accessions

def extract_urls_from_text(text: str, prioritize_data_section: bool = False) -> List[str]:
    """Extract URLs from a given text string, prioritizing data-related URLs."""
    url_pattern = r"(https?://[^\s<>\"';)]+|doi:[^\s<>\"';)]+|<doi:[^\s<>\"';)]+>|www\.[^\s<>\"';)]+|10\.\d{4,9}/[^\s<>\"';)]+)"
    urls = re.findall(url_pattern, text, re.IGNORECASE)
    cleaned_urls = []
    data_domains = [
        "zenodo.org", "dryad.org", "figshare.com", "github.com", "raw.githubusercontent.com",
        "dataverse.org", "osf.io", "pangaea.de", "genbank", "sra", "geo", "arrayexpress", "ena"
    ]
    DEFAULT_DATA_FORMATS = ["csv", "tsv", "txt", "xlsx", "xls", "zip", "rar", "tar.gz"]
    for url in urls:
        url = url.strip(".,;()[]{}")
        if url.startswith("www."):
            url = "https://" + url
        elif url.startswith("doi:"):
            url = "https://doi.org/" + url[4:]
        elif url.startswith("<doi:") and url.endswith(">"):
            url = "https://doi.org/" + url[5:-1]
        elif url.startswith("10.") and "/" in url:
            url = "https://doi.org/" + url
        if len(url) > MAX_URL_LENGTH:
            continue
        url_lower = url.lower()
        if (
            re.match(r"^https?://", url, re.IGNORECASE) and
            (any(domain in url_lower for domain in data_domains) or
             any(url_lower.endswith(f".{ext}") for ext in DEFAULT_DATA_FORMATS))
        ):
            cleaned_urls.append(url)
    return cleaned_urls

def score_data_statement(statement: str, category: str) -> int:
    """Score a data availability statement based on relevance and context."""
    score = 0
    statement_lower = statement.lower()
    priority = {
        "Available in Repository": 5,
        "Available in Supplementary Materials": 4,
        "Available Upon Request": 3,
        "Other Availability": 2,
        "Not Available": 1
    }
    score += priority.get(category, 0) * 10
    paper_specific_phrases = ["this study", "we provide", "our data", "our dataset", "in this paper"]
    if any(phrase in statement_lower for phrase in paper_specific_phrases):
        score += 20
    third_party_phrases = ["obtained from", "third-party", "third party", "accessed from"]
    if any(phrase in statement_lower for phrase in third_party_phrases):
        score -= 15
    data_keywords = ["data", "dataset", "supplementary"]
    keyword_count = sum(1 for kw in data_keywords if kw in statement_lower)
    score += keyword_count * 2
    repo_count = sum(1 for repo in ["zenodo", "figshare", "dryad", "dataverse", "osf", "github"] if repo in statement_lower)
    score += repo_count * 5
    return score

def extract_all_information(text: str, method: str = "keyword") -> dict:
    """
    Extract all relevant information (data/code availability, DOIs, URLs, accessions, etc.) from text.
    
    Args:
        text: Input text to analyze
        method: Extraction method - "keyword" (default), "llm", or "both"
    
    Returns:
        Dictionary with all detected items
    """
    if method == "llm" and LLM_AVAILABLE:
        logger.info("Using LLM-based extraction")
        # For LLM method, we need PDF content, not just text
        # This is a limitation - we'll note it in the result
        return {
            "extraction_method": "llm",
            "error": "LLM extraction requires PDF content, not plain text. Use extract_all_information_from_pdf_llm() instead.",
            "text_provided": True,
            "text_length": len(text)
        }
    
    # Default keyword-based extraction
    logger.info("Using keyword-based extraction")
    
    # Section detection (simple version)
    data_section = text
    code_section = text
    # Sentence tokenization (robust)
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # Oddpub-inspired extraction
    oddpub_results = oddpub_extract_statements(sentences)
    # Statement extraction (legacy: sentences containing 'data' or 'code')
    data_statements = " ".join([s for s in sentences if "data" in s.lower()])
    code_statements = " ".join([s for s in sentences if "code" in s.lower()])
    # URL/DOI/accession extraction
    all_urls = extract_urls_from_text(text)
    data_urls = [u for u in all_urls if any(domain in u for domain in ["zenodo", "dryad", "figshare", "dataverse", "osf", "pangaea", "genbank"])]
    code_urls = [u for u in all_urls if "github" in u]
    dois = extract_dois_from_text(text)
    accessions = extract_accessions_from_text(text)
    
    result = {
        "extraction_method": "keyword",
        "data_section": data_section,
        "code_section": code_section,
        "data_statements": data_statements,
        "code_statements": code_statements,
        "all_urls": all_urls,
        "data_urls": data_urls,
        "code_urls": code_urls,
        "dois": dois,
        "accessions": accessions,
        # Oddpub-inspired
        "data_statements_oddpub": oddpub_results["data_statements_oddpub"],
        "code_statements_oddpub": oddpub_results["code_statements_oddpub"]
    }
    
    if method == "both" and LLM_AVAILABLE:
        logger.info("Both methods requested, but LLM requires PDF content")
        result["llm_note"] = "LLM extraction requires PDF content, not plain text"
    
    return result

def full_pipeline_search_and_extract(query: str, top_n: int = 3, save_pdfs: bool = True, openalex_email: str = None) -> list:
    """
    Full pipeline: search OpenAlex for papers by query, download PDFs, extract text and information.
    Returns a list of dicts with metadata, extraction results, and file paths.
    """
    from pyalex import Works
    results = []
    works = Works().search(query).get()
    if not works:
        logger.warning(f"No results found for query: {query}")
        return results
    for i, work in enumerate(works[:top_n]):
        doi = work.get("doi")
        title = work.get("title", "")
        authors = ", ".join([auth["author"]["display_name"] for auth in work.get("authorships", [])])
        published = work.get("publication_date", "")
        host_venue = work.get("host_venue", {})
        journal = host_venue.get("display_name", "")
        pdf_url = work.get("open_access", {}).get("oa_url")
        landing_url = host_venue.get("url", "")
        # Try to get PDF URLs (OpenAlex, Unpaywall, landing page)
        pdf_urls = []
        if pdf_url:
            pdf_urls.append(pdf_url)
        # Try Unpaywall if no PDF URL
        if not pdf_urls and doi:
            try:
                is_oa, has_fulltext, unpaywall_urls = get_unpaywall_data(doi, email=openalex_email)
                pdf_urls.extend(unpaywall_urls)
            except Exception as e:
                logger.warning(f"Unpaywall lookup failed for DOI {doi}: {e}")
        # Try landing page scraping if still no PDF URL
        if not pdf_urls and landing_url:
            session = requests.Session()
            alt_pdf = find_pdf_url_from_landing_page(landing_url, session)
            if alt_pdf:
                pdf_urls.append(alt_pdf)
        # Download PDF
        pdf_success, pdf_content, pdf_size, pdf_path = download_pdf(
            doi or f"no-doi-{i}", pdf_urls, save_to_disk=save_pdfs, identifier=f"{i+1:03}", title=title
        )
        text = extract_text_from_pdf(pdf_content) if pdf_success else None
        extraction = extract_all_information(text) if text else None
        results.append({
            "doi": doi,
            "title": title,
            "authors": authors,
            "published": published,
            "journal": journal,
            "landing_url": landing_url,
            "pdf_urls": pdf_urls,
            "pdf_path": pdf_path if pdf_success else None,
            "pdf_size": pdf_size if pdf_success else None,
            "extracted_text_length": len(text) if text else 0,
            "extraction": extraction,
        })
    return results

# Oddpub-inspired: use expanded keywords from keywords.py
from ecoopen.keywords import DATA_AVAILABILITY_KEYWORDS, CODE_AVAILABILITY_KEYWORDS

ODDPUB_DATA_AVAILABILITY = [k.lower() for k in DATA_AVAILABILITY_KEYWORDS]
ODDPUB_CODE_AVAILABILITY = [k.lower() for k in CODE_AVAILABILITY_KEYWORDS]

ODDPUB_REPOSITORIES = [
    "zenodo", "figshare", "dryad", "dataverse", "osf", "pangaea", "genbank", "github", "bitbucket", "gitlab",
    "ncbi", "ebi", "arrayexpress", "ega", "pride", "proteomexchange", "openneuro", "neurovault", "kaggle"
]
ODDPUB_FILE_FORMATS = [
    ".csv", ".tsv", ".txt", ".xlsx", ".xls", ".zip", ".rar", ".tar.gz", ".json", ".xml", ".hdf5", ".mat"
]
ODDPUB_ACCESSION_PATTERNS = [
    r"PRJNA\d{6,}", r"SRR\d{6,}", r"GSE\d{6,}", r"GSM\d{6,}", r"EGAS\d{6,}", r"EGAD\d{6,}",
    r"ENA\d{6,}", r"E-MTAB-\d{3,}", r"PXD\d{6,}", r"SAMN\d{6,}", r"DRR\d{6,}", r"ERR\d{6,}",
    r"SRX\d{6,}", r"ERX\d{6,}", r"DRX\d{6,}", r"SRS\d{6,}", r"ERS\d{6,}", r"DRS\d{6,}"
]

__all__ = [
    "clean_text",
    "truncate_statement",
    "validate_doi",
    "extract_all_information",
    "extract_urls_from_text",
    "extract_dois_from_text",
    "extract_accessions_from_text",
    "score_data_statement",
    "full_pipeline_search_and_extract",
    "oddpub_extract_statements",
]

def oddpub_find_section_indices(sentences: List[str], section_keywords: List[str]) -> List[int]:
    """Return indices of sentences that are section headers matching any keyword."""
    indices = []
    for i, s in enumerate(sentences):
        s_clean = s.lower().strip()
        for kw in section_keywords:
            if s_clean.startswith(kw):
                indices.append(i)
    return indices

def oddpub_extract_section(sentences: List[str], section_keywords: List[str], max_section_len: int = 10) -> List[str]:
    """Extract sentences from the first matching section (up to max_section_len sentences)."""
    indices = oddpub_find_section_indices(sentences, section_keywords)
    if not indices:
        return []
    start = indices[0]
    # Section ends at next section header or after max_section_len sentences
    for end in range(start+1, min(start+max_section_len+1, len(sentences))):
        if any(sentences[end].lower().startswith('<section>') or sentences[end].lower().startswith('section') for _ in [0]):
            return sentences[start:end]
    return sentences[start:start+max_section_len]

def oddpub_sentence_matches(sentence: str, keyword_lists: List[List[str]], require_all: bool = True) -> bool:
    """Return True if the sentence matches all (or any) keyword lists (case-insensitive substring match)."""
    s = sentence.lower()
    if require_all:
        return all(any(kw in s for kw in kwlist) for kwlist in keyword_lists)
    else:
        return any(any(kw in s for kw in kwlist) for kwlist in keyword_lists)

def oddpub_extract_statements(sentences: List[str]) -> dict:
    """Oddpub-style extraction: prioritize DAS/CAS sections, then scan all sentences for data/code availability."""
    # Section-aware extraction
    das_section = oddpub_extract_section(sentences, ODDPUB_DATA_AVAILABILITY)
    cas_section = oddpub_extract_section(sentences, ODDPUB_CODE_AVAILABILITY)
    # Fallback: scan all sentences
    data_statements = []
    code_statements = []
    for s in sentences:
        if oddpub_sentence_matches(s, [ODDPUB_DATA_AVAILABILITY, ODDPUB_REPOSITORIES], require_all=True):
            data_statements.append(s)
        if oddpub_sentence_matches(s, [ODDPUB_CODE_AVAILABILITY, ODDPUB_REPOSITORIES], require_all=True):
            code_statements.append(s)
    # Prefer section if found, else use fallback
    data_result = das_section if das_section else data_statements
    code_result = cas_section if cas_section else code_statements
    return {
        "data_statements_oddpub": data_result,
        "code_statements_oddpub": code_result
    }

def extract_all_information_from_pdf_llm(pdf_content: bytes, method: str = "llm") -> dict:
    """
    Extract all relevant information from PDF using LLM-based analysis.
    
    Args:
        pdf_content: PDF file content as bytes
        method: Extraction method - "llm", "keyword", or "both"
    
    Returns:
        Dictionary with extracted information
    """
    if method == "llm" and LLM_AVAILABLE:
        logger.info("Using LLM-based extraction for PDF")
        return extract_all_information_llm(pdf_content)
    
    elif method == "keyword" or not LLM_AVAILABLE:
        logger.info("Using keyword-based extraction for PDF")
        # Extract text first, then use keyword extraction
        text = extract_text_from_pdf(pdf_content)
        if text:
            return extract_all_information(text, method="keyword")
        else:
            return {"error": "Failed to extract text from PDF", "extraction_method": "keyword"}
    
    elif method == "both" and LLM_AVAILABLE:
        logger.info("Using both extraction methods for PDF")
        # Run both extractions
        llm_result = extract_all_information_llm(pdf_content)
        
        # Also run keyword extraction
        text = extract_text_from_pdf(pdf_content)
        if text:
            keyword_result = extract_all_information(text, method="keyword")
        else:
            keyword_result = {"error": "Failed to extract text for keyword analysis"}
        
        # Combine results
        combined_result = {
            "extraction_method": "both",
            "llm_results": llm_result,
            "keyword_results": keyword_result,
            "comparison": {
                "llm_success": llm_result.get("success", False),
                "keyword_success": "error" not in keyword_result,
                "llm_found_data": False,
                "keyword_found_data": False
            }
        }
        
        # Add comparison metrics
        if llm_result.get("success") and "availability_info" in llm_result:
            availability = llm_result["availability_info"]
            if isinstance(availability, dict):
                combined_result["comparison"]["llm_found_data"] = availability.get("data_availability", {}).get("found", False)
        
        if "data_statements" in keyword_result:
            combined_result["comparison"]["keyword_found_data"] = len(keyword_result.get("data_statements", "").strip()) > 0
        
        return combined_result
    
    else:
        return {
            "error": "LLM extraction not available. Install LLM dependencies with: pip install -r requirements_llm.txt",
            "extraction_method": method,
            "llm_available": LLM_AVAILABLE
        }