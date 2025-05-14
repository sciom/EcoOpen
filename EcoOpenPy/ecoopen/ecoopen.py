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
from ecoopen.keywords import keywords  # Absolute import
from ecoopen.data_mining import find_data_urls  # Import from data_mining
from ecoopen.utils import log_message, is_data_related_url  # Import from utils
import unicodedata
import signal
from ratelimit import limits, sleep_and_retry

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
        logging.warning(f"Invalid DOI format: {doi}")
        return False

def create_download_dir(download_dir=DOWNLOAD_DIR):
    """Create download directory if it doesn't exist."""
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        logging.info(f"Created download directory: {download_dir}")

def create_data_download_dir(data_download_dir=DATA_DOWNLOAD_DIR):
    """Create data download directory if it doesn't exist."""
    if not os.path.exists(data_download_dir):
        os.makedirs(data_download_dir)
        logging.info(f"Created data download directory: {data_download_dir}")

def create_article_subfolder(data_download_dir, identifier, doi):
    """Create a subfolder for an article based on identifier and DOI."""
    safe_doi = doi.replace('/', '_')
    subfolder_name = f"{identifier}_{safe_doi}"
    subfolder_path = os.path.join(data_download_dir, subfolder_name)
    if not os.path.exists(subfolder_path):
        os.makedirs(subfolder_path)
        logging.info(f"Created article subfolder: {subfolder_path}")
    return subfolder_path

def sanitize_filename(text, max_length=50):
    """Sanitize a string to be used in filenames."""
    text = re.sub(r'[<>:"/\\|?*]', '_', text)
    text = text.replace(' ', '_')
    text = re.sub(r'[^a-zA-Z0-9_-]', '', text)
    return text[:max_length]

def clean_text(text):
    """Clean text by removing invisible Unicode characters."""
    cleaned_text = unicodedata.normalize('NFKD', text)
    cleaned_text = ''.join(c for c in cleaned_text if unicodedata.category(c) not in ('Cf', 'Cc', 'Cn'))
    logging.debug(f"Cleaned text from '{text[:100]}...' to '{cleaned_text[:100]}...'")
    return cleaned_text

def truncate_statement(statement, max_length=MAX_STATEMENT_LENGTH):
    """Truncate a statement to a maximum length, adding ellipsis if needed."""
    if len(statement) > max_length:
        statement = statement[:max_length - 3] + "..."
        logging.debug(f"Truncated statement to {max_length} characters: {statement}")
    return statement

@sleep_and_retry
@limits(calls=10, period=60)  # 10 calls per minute
def get_unpaywall_data(doi, email=None):
    """Query Unpaywall for open-access status and full-text URL."""
    logging.debug(f"Starting Unpaywall query for DOI: {doi}")
    if email is None:
        email = os.getenv("UNPAYWALL_EMAIL")
    
    if not email:
        raise ValueError("An email address is required for Unpaywall API requests.")
    
    try:
        url = f"https://api.unpaywall.org/v2/{quote(doi)}?email={email}"
        logging.debug(f"Unpaywall API URL: {url}")
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
        logging.info(f"Unpaywall for DOI {doi}: is_oa={is_oa}, has_fulltext={has_fulltext}, fulltext_urls={fulltext_urls}")
        return is_oa, has_fulltext, fulltext_urls
    except Exception as e:
        logging.error(f"Unpaywall error for DOI {doi}: {str(e)}")
        return False, False, []

@sleep_and_retry
@limits(calls=10, period=60)  # 10 calls per minute
def get_openalex_data(doi):
    """Query OpenAlex for metadata and potential PDF URL."""
    logging.debug(f"Starting OpenAlex query for DOI: {doi}")
    try:
        work = Works().filter(doi=doi).get()
        if work:
            work = work[0]
            title = work.get("title", "")
            authors = ", ".join([auth["author"]["display_name"] for auth in work.get("authorships", [])])
            published = work.get("publication_date", "")
            journal = work.get("host_venue", {}).get("display_name", "")
            url = work.get("host_venue", {}).get("url", "")
            pdf_url = work.get("open_access", {}).get("oa_url", None)
            if pdf_url and len(pdf_url) > MAX_URL_LENGTH:
                pdf_url = None
            logging.info(f"OpenAlex for DOI {doi}: pdf_url={pdf_url}, landing_page_url={url}")
            return title, authors, published, journal, url, pdf_url
        return "", "", "", "", "", None
    except Exception as e:
        logging.error(f"OpenAlex error for DOI {doi}: {str(e)}")
        return "", "", "", "", "", None

def find_pdf_url_from_landing_page(url, session):
    """Attempt to find a PDF URL by scraping the landing page."""
    logging.debug(f"Scraping landing page for PDF URL: {url}")
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
                        logging.debug(f"Found PDF URL: {href}")
                        return href
                    full_url = urljoin(url, href)
                    if len(full_url) <= MAX_URL_LENGTH:
                        logging.debug(f"Found PDF URL (relative): {full_url}")
                        return full_url
            download_links = soup.find_all("a", text=re.compile(r"download.*pdf|pdf.*download", re.I))
            for link in download_links:
                href = link.get("href")
                if href and len(href) <= MAX_URL_LENGTH:
                    if href.startswith("http"):
                        logging.debug(f"Found PDF URL via download link: {href}")
                        return href
                    full_url = urljoin(url, href)
                    if len(full_url) <= MAX_URL_LENGTH:
                        logging.debug(f"Found PDF URL via download link (relative): {full_url}")
                        return full_url
        logging.debug(f"No PDF URL found on landing page: {url}")
        return None
    except Exception as e:
        logging.error(f"Error scraping PDF URL from landing page {url}: {str(e)}")
        return None

def download_pdf(doi, urls, save_to_disk=True, download_dir=DOWNLOAD_DIR, identifier="001", title="unknown"):
    """Download PDF from a list of URLs and return binary content."""
    logging.debug(f"Starting PDF download for DOI: {doi}, URLs: {urls}")
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
            logging.warning(f"Skipping PDF URL due to length > {MAX_URL_LENGTH}: {url[:100]}...")
            continue
        logging.info(f"Attempting PDF download from URL: {url}")
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path.rsplit('/', 1)[0]}"
        headers["Referer"] = base_url
        session.headers.update(headers)

        try:
            logging.debug(f"Visiting landing page: {base_url}")
            landing_response = session.get(base_url, timeout=15, allow_redirects=True)
            landing_response.raise_for_status()
            logging.info(f"Visited landing page for DOI {doi}: {base_url}, Cookies: {session.cookies.get_dict()}")
        except Exception as e:
            logging.warning(f"Failed to visit landing page for DOI {doi}: {base_url}, Error: {str(e)}")

        url_variants = [url]
        if "version=" in url:
            url_without_version = url.split("?")[0]
            url_variants.append(url_without_version)

        for pdf_url in url_variants:
            if len(pdf_url) > MAX_URL_LENGTH:
                logging.warning(f"Skipping PDF URL variant due to length > {MAX_URL_LENGTH}: {pdf_url[:100]}...")
                continue
            for attempt in range(3):
                try:
                    if not pdf_url or not pdf_url.startswith(('http://', 'https://')):
                        logging.error(f"Invalid or missing URL for DOI {doi}: {pdf_url}")
                        break
                    logging.info(f"Attempt {attempt + 1}/3 for DOI {doi} with URL: {pdf_url}")
                    headers["User-Agent"] = random.choice(user_agents)
                    session.headers.update(headers)
                    response = session.get(pdf_url, timeout=15, stream=True, allow_redirects=True)
                    if response.status_code == 403:
                        logging.warning(f"403 Forbidden for DOI {doi}, Response Headers: {response.headers}, Content: {response.text[:500]}...")
                        time.sleep(random.uniform(5, 10))
                        alt_pdf_url = find_pdf_url_from_landing_page(base_url, session)
                        if alt_pdf_url and len(alt_pdf_url) <= MAX_URL_LENGTH:
                            logging.info(f"Found alternative PDF URL via scraping: {alt_pdf_url}")
                            response = session.get(alt_pdf_url, timeout=15, stream=True, allow_redirects=True)
                            response.raise_for_status()
                        else:
                            continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    logging.debug(f"Content-Type of response: {content_type}")
                    if "pdf" not in content_type and "octet-stream" not in content_type:
                        if not pdf_url.endswith(".pdf"):
                            new_url = pdf_url.rstrip("/") + "/pdf"
                            if len(new_url) > MAX_URL_LENGTH:
                                logging.warning(f"Skipping modified PDF URL due to length > {MAX_URL_LENGTH}: {new_url[:100]}...")
                                continue
                            logging.info(f"URL not a PDF, trying modified URL for DOI {doi}: {new_url}")
                            response = session.get(new_url, timeout=15, stream=True, allow_redirects=True)
                            response.raise_for_status()
                            content_type = response.headers.get("content-type", "").lower()
                            logging.debug(f"Content-Type of modified URL response: {content_type}")
                            if "pdf" not in content_type and "octet-stream" not in content_type:
                                pdf_url_from_landing = find_pdf_url_from_landing_page(base_url, session)
                                if pdf_url_from_landing and len(pdf_url_from_landing) <= MAX_URL_LENGTH:
                                    logging.info(f"Found PDF URL via scraping for DOI {doi}: {pdf_url_from_landing}")
                                    response = session.get(pdf_url_from_landing, timeout=15, stream=True, allow_redirects=True)
                                    response.raise_for_status()
                                    content_type = response.headers.get("content-type", "").lower()
                                    logging.debug(f"Content-Type of scraped URL response: {content_type}")
                                    if "pdf" not in content_type and "octet-stream" not in content_type:
                                        logging.warning(f"Scraped URL for DOI {doi} does not point to a PDF: {pdf_url_from_landing}, Content-Type: {content_type}")
                                        break
                                else:
                                    logging.warning(f"No PDF URL found after scraping for DOI {doi}, Content-Type: {content_type}")
                                    break
                    pdf_content = b"".join(response.iter_content(chunk_size=8192))
                    pdf_content_length = len(pdf_content)
                    logging.debug(f"PDF content length: {pdf_content_length} bytes")
                    if save_to_disk:
                        create_download_dir(download_dir)
                        with open(file_path, "wb") as f:
                            f.write(pdf_content)
                        logging.info(f"Saved PDF for DOI {doi} to {file_path} (size: {pdf_content_length} bytes)")
                    else:
                        logging.info(f"Downloaded PDF content for DOI {doi} (size: {pdf_content_length} bytes, not saved to disk)")
                    return True, pdf_content, pdf_content_length, file_path
                except Exception as e:
                    logging.error(f"Download error for DOI {doi}: {str(e)} (URL: {pdf_url})")
                    if attempt < 2:
                        time.sleep(random.uniform(5, 10))
                    continue
            logging.info(f"All attempts failed for URL: {pdf_url}")
    return False, None, 0, ""

def download_data_file(url, doi, data_download_dir, target_formats, identifier="001", title="unknown", recursion_depth=0):
    """Download a data file if it matches the target formats, saving to an article-specific subfolder."""
    logging.debug(f"Starting data download for URL: {url}, DOI: {doi}, recursion_depth: {recursion_depth}")
    if recursion_depth > 1:  # Limit recursion to one level
        logging.info(f"Maximum recursion depth reached for URL {url}")
        return None
    
    if len(url) > MAX_URL_LENGTH:
        logging.warning(f"Skipping data URL due to length > {MAX_URL_LENGTH}: {url[:100]}...")
        return None
    
    target_formats_lower = [ext.lower().lstrip('.') for ext in target_formats]
    logging.debug(f"Target formats (lowercase): {target_formats_lower}")
    
    article_subfolder = create_article_subfolder(data_download_dir, identifier, doi)
    
    parsed_url = urlparse(url)
    path = parsed_url.path.lower()
    logging.info(f"Checking URL for download: {url}, path: {path}")
    
    if not is_data_related_url(url, target_formats_lower):
        logging.info(f"Skipping non-data-related URL: {url}")
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
            logging.debug(f"Headers for download session: {headers}")

            logging.debug(f"Sending GET request to URL: {url}")
            response = session.get(url, timeout=15, stream=True, allow_redirects=True)
            logging.debug(f"Response status code: {response.status_code}")
            response.raise_for_status()

            filename = None
            content_disposition = response.headers.get("content-disposition", "")
            logging.debug(f"Content-Disposition header: {content_disposition}")
            if "filename=" in content_disposition.lower():
                filename = re.findall(r'filename="(.+)"', content_disposition)
                filename = filename[0] if filename else None
                logging.debug(f"Filename extracted from Content-Disposition: {filename}")
            if not filename:
                filename = os.path.basename(parsed_url.path) or "downloaded_data"
                logging.debug(f"Filename extracted from URL path: {filename}")
            
            if not any(filename.lower().endswith(f".{ext}") for ext in target_formats_lower):
                content_type = response.headers.get("content-type", "").lower()
                logging.debug(f"Content-Type of downloaded file: {content_type}")
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
                    logging.info(f"Skipping data URL {url} for DOI {doi}: unable to determine file format from Content-Type: {content_type}")
                    return None
                logging.debug(f"Updated filename with inferred extension: {filename}")

            base_filename, ext = os.path.splitext(filename)
            safe_filename = f"{base_filename}{ext}"
            file_path = os.path.join(article_subfolder, safe_filename)
            logging.debug(f"Safe filename for download: {safe_filename}, full path: {file_path}")

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        logging.debug(f"Wrote chunk of {len(chunk)} bytes to {file_path}")
            
            file_size = os.path.getsize(file_path) / 1024
            logging.info(f"Downloaded data file for DOI {doi} to {file_path} (size: {file_size:.2f} KB)")
            return file_path
        except Exception as e:
            logging.error(f"Failed to download data file from {url} for DOI {doi}: {str(e)}")
            return None
    
    logging.info(f"URL {url} does not directly match target formats, attempting to scrape for data files")
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
    logging.debug(f"Headers for scraping session: {headers}")
    new_urls = find_data_urls(url, session, target_formats_lower, max_depth=1)
    logging.debug(f"Found potential data URLs after scraping: {new_urls}")
    if not new_urls:
        logging.info(f"No downloadable files found for URL {url}")
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
    logging.debug(f"Starting PDF text extraction, content length: {len(pdf_content) if pdf_content else 0} bytes")
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
            logging.debug(f"Extracted text from page, length: {len(page_text)} characters")
        doc.close()
        signal.alarm(0)  # Disable alarm
        logging.info(f"Extracted text from PDF (length: {len(text)} characters)")
        return clean_text(text)
    except Exception as e:
        signal.alarm(0)  # Disable alarm on error
        logging.error(f"Error extracting text from PDF: {str(e)}")
        return ""

def find_section(text, section_keywords, next_section_keywords=None):
    """Find a specific section in the text (e.g., 'Data Availability') and extract its content."""
    logging.debug(f"Finding section with keywords: {section_keywords}")
    lines = text.split('\n')
    section_text = []
    in_section = False
    
    for i, line in enumerate(lines):
        if any(keyword.lower() in line.lower() for keyword in section_keywords):
            logging.debug(f"Found section start: {line.strip()}")
            in_section = True
            continue
        
        if in_section and next_section_keywords:
            if any(keyword.lower() in line.lower() for keyword in next_section_keywords):
                logging.debug(f"Reached next section: {line.strip()}")
                break
        
        if in_section and line.strip():
            section_text.append(line.strip())
    
    if section_text:
        section = ' '.join(section_text).strip()
        section = clean_text(section)
        logging.debug(f"Found section: {section[:500]}...")
        return section
    logging.debug("No specific section found, returning full text")
    return clean_text(text)

def search_for_dataset(dataset_name, doi):
    """Search for the dataset online to find potential URLs."""
    logging.debug(f"Searching for dataset: {dataset_name}")
    potential_urls = []
    dataset_name_lower = dataset_name.lower()

    repositories = [
        ("Dryad", "https://datadryad.org/stash/dataset/"),
        ("Zenodo", "https://zenodo.org/record/"),
        ("Figshare", "https://figshare.com/articles/dataset/"),
        ("GitHub", "https://github.com/search?q="),
    ]

    for repo_name, base_url in repositories:
        if repo_name.lower() in dataset_name_lower:
            url = f"{base_url}{dataset_name.replace(' ', '_')}"
            if len(url) <= MAX_URL_LENGTH:
                potential_urls.append(url)
        else:
            url = f"{base_url}{dataset_name.replace(' ', '+')}"
            if len(url) <= MAX_URL_LENGTH:
                potential_urls.append(url)

    logging.debug(f"Potential URLs for dataset {dataset_name}: {potential_urls}")
    return potential_urls

def clean_url(url):
    """Clean a URL by removing invisible Unicode characters."""
    cleaned_url = unicodedata.normalize('NFKD', url)
    cleaned_url = ''.join(c for c in cleaned_url if unicodedata.category(c) not in ('Cf', 'Cc', 'Cn'))
    logging.debug(f"Cleaned URL from '{url}' to '{cleaned_url}'")
    return cleaned_url

def extract_urls_from_text(text, prioritize_data_section=False):
    """Extract URLs from a given text string, prioritizing data-related URLs."""
    logging.debug(f"Extracting URLs from text: {text[:500]}...")
    # Updated regex to stop at common URL boundaries
    url_pattern = r"(https?://[^\s<>\"\';)]+|doi:[^\s<>\"\';)]+|<doi:[^\s<>\"\';)]+>|www\.[^\s<>\"\';)]+|10\.\d{4,9}/[^\s<>\"\';)]+)"
    urls = re.findall(url_pattern, text, re.IGNORECASE)
    cleaned_urls = []
    data_domains = [
        "zenodo.org", "dryad.org", "figshare.com", "github.com", "raw.githubusercontent.com",
        "dataverse.org", "osf.io", "pangaea.de", "genbank", "sra", "geo", "arrayexpress", "ena"
    ]
    
    # Use NLP to prioritize URLs from data accessibility section
    if prioritize_data_section:
        doc = nlp(text)
        data_urls = []
        for sent in doc.sents:
            sent_text = sent.text.lower()
            if any(kw in sent_text for kw in ["data accessibility", "data availability", "dataset"]):
                sent_urls = re.findall(url_pattern, sent.text, re.IGNORECASE)
                data_urls.extend(sent_urls)
        if data_urls:
            urls = data_urls  # Prioritize URLs from data section
    
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
        url = clean_url(url)
        if len(url) > MAX_URL_LENGTH:
            logging.warning(f"Discarding URL due to length > {MAX_URL_LENGTH}: {url[:100]}...")
            continue
        url_lower = url.lower()
        # Only include URLs from known data repositories or with data file extensions
        if (
            re.match(r"^https?://", url, re.IGNORECASE) and
            (any(domain in url_lower for domain in data_domains) or
             any(url_lower.endswith(f".{ext}") for ext in DEFAULT_DATA_FORMATS))
        ):
            cleaned_urls.append(url)
    logging.debug(f"Extracted URLs: {cleaned_urls}")
    return cleaned_urls

def extract_urls_from_full_text(text):
    """Extract URLs from the entire PDF text, without prioritizing data section."""
    return extract_urls_from_text(text, prioritize_data_section=False)

def score_data_statement(statement, category):
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

    data_keywords = keywords["data"] + keywords["all_data"] + keywords["dataset_name"]
    keyword_count = sum(1 for kw in data_keywords if kw in statement_lower)
    score += keyword_count * 2

    repo_count = sum(1 for repo in keywords["repositories"] + keywords["field_specific_repo"] if repo.lower() in statement_lower)
    score += repo_count * 5

    return score

def score_code_statement(statement, category):
    """Score a code availability statement based on relevance and context."""
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

    paper_specific_phrases = ["this study", "we provide", "our code", "in this paper"]
    if any(phrase in statement_lower for phrase in paper_specific_phrases):
        score += 20

    third_party_phrases = ["obtained from", "third-party", "third party", "accessed from"]
    if any(phrase in statement_lower for phrase in third_party_phrases):
        score -= 15

    code_keywords = keywords["source_code"]
    keyword_count = sum(1 for kw in code_keywords if kw in statement_lower)
    score += keyword_count * 2

    repo_count = sum(1 for repo in keywords["github"] + keywords["repositories"] if repo.lower() in statement_lower)
    score += repo_count * 5

    return score

def analyze_data_availability(text, doc_cache=None):
    """Analyze text for data availability statements using NLP and extract data links."""
    if not text:
        return "No text available for analysis.", [], []

    next_section_keywords = ["ORCID", "References", "Acknowledgments", "Conflict of Interest", "Author Contributions"]
    relevant_text = find_section(text, keywords["data_availability"], next_section_keywords)
    logging.debug(f"Data availability section text: {relevant_text[:500]}...")
    
    doc = doc_cache.get(relevant_text) if doc_cache and relevant_text in doc_cache else nlp(relevant_text)
    if doc_cache is not None and relevant_text not in doc_cache:
        doc_cache[relevant_text] = doc
    
    data_keywords = keywords["data"] + keywords["all_data"] + keywords["dataset_name"]
    availability_keywords = keywords["available"] + keywords["was_available"]
    negation_keywords = keywords["not_available"] + keywords["not_data"]
    repository_keywords = keywords["repositories"] + keywords["field_specific_repo"] + keywords["github"]
    request_keywords = keywords["upon_request"]
    supplement_keywords = keywords["supplement"] + keywords["supplemental_table_name"] + keywords["supplemental_dataset"]
    
    all_statements = []
    current_statement = []
    current_category = None
    all_data_links = []
    best_statement = None
    best_score = -1
    
    for sent in doc.sents:
        sent_text = clean_text(sent.text)
        sent_text_lower = sent_text.lower()
        has_data = any(kw in sent_text_lower for kw in data_keywords)
        has_availability = any(kw in sent_text_lower for kw in availability_keywords)
        logging.debug(f"Sentence: '{sent_text}', has_data={has_data} (keywords matched: {', '.join(kw for kw in data_keywords if kw in sent_text_lower)}), has_availability={has_availability} (keywords matched: {', '.join(kw for kw in availability_keywords if kw in sent_text_lower)})")
        
        if has_data and has_availability:
            urls = extract_urls_from_text(sent_text, prioritize_data_section=True)
            all_data_links.extend(urls)
            logging.debug(f"Extracted URLs from data availability sentence '{sent_text}': {urls}")

            has_negation = any(kw in sent_text_lower for kw in negation_keywords)
            has_repository = any(kw in sent_text_lower for kw in repository_keywords)
            has_request = any(kw in sent_text_lower for kw in request_keywords)
            has_supplement = any(kw in sent_text_lower for kw in supplement_keywords)
            has_accession = any(pattern.search(sent_text_lower) for pattern in ACCESSION_PATTERNS)
            
            if has_negation:
                category = "Not Available"
            elif has_request:
                category = "Available Upon Request"
            elif has_repository or has_accession:
                category = "Available in Repository"
            elif has_supplement:
                category = "Available in Supplementary Materials"
            else:
                category = "Other Availability"
            
            if current_statement and current_category == category:
                current_statement.append(sent_text.strip())
            else:
                if current_statement:
                    full_statement = " ".join(current_statement)
                    score = score_data_statement(full_statement, current_category)
                    all_statements.append((current_category, full_statement, score))
                    logging.debug(f"Scored data statement: Category={current_category}, Score={score}, Statement={full_statement[:500]}...")
                    if score > best_score:
                        best_statement = full_statement
                        best_score = score
                current_statement = [sent_text.strip()]
                current_category = category
        else:
            if current_statement:
                full_statement = " ".join(current_statement)
                score = score_data_statement(full_statement, current_category)
                all_statements.append((current_category, full_statement, score))
                logging.debug(f"Scored data statement: Category={current_category}, Score={score}, Statement={full_statement[:500]}...")
                if score > best_score:
                    best_statement = full_statement
                    best_score = score
                current_statement = []
                current_category = None
    
    if current_statement:
        full_statement = " ".join(current_statement)
        score = score_data_statement(full_statement, current_category)
        all_statements.append((current_category, full_statement, score))
        logging.debug(f"Scored data statement: Category={current_category}, Score={score}, Statement={full_statement[:500]}...")
        if score > best_score:
            best_statement = full_statement
            best_score = score
    
    section_urls = extract_urls_from_text(relevant_text, prioritize_data_section=True)
    all_data_links.extend([url for url in section_urls if url not in all_data_links])
    logging.debug(f"Extracted URLs from entire data availability section: {section_urls}")

    has_data_keywords = any(kw in relevant_text.lower() for kw in data_keywords)
    logging.debug(f"Section contains data keywords: {has_data_keywords} (keywords matched: {', '.join(kw for kw in data_keywords if kw in relevant_text.lower())})")
    
    if all_statements:
        if best_statement:
            best_statement = truncate_statement(best_statement)
            logging.info(f"Best data availability statement selected: Score={best_score}, Statement={best_statement}")
        else:
            best_statement = truncate_statement(all_statements[0][1])
            logging.info(f"No best statement found, using first statement: Statement={best_statement}")
        
        if not all_data_links and "available" in relevant_text.lower() and "not available" not in relevant_text.lower():
            dataset_name = relevant_text
            logging.info(f"No URLs found in statement, searching for dataset: {dataset_name}")
            potential_urls = search_for_dataset(dataset_name, "")
            all_data_links.extend([url for url in potential_urls if len(url) <= MAX_URL_LENGTH])

        if not all_data_links:
            logging.info("No URLs found after dataset search, searching full text for URLs")
            full_text_urls = extract_urls_from_full_text(text)
            all_data_links.extend([url for url in full_text_urls if len(url) <= MAX_URL_LENGTH])
        
        all_statements_formatted = [truncate_statement(stmt) for _, stmt, _ in all_statements]
        logging.debug(f"Final data links after all searches: {all_data_links}")
        return best_statement, all_data_links, all_statements_formatted
    
    logging.info(f"No data availability statement found for DOI. Text excerpt: {text[:500]}...")
    full_text_urls = extract_urls_from_full_text(text)
    return "No data availability statement found.", full_text_urls, []

def analyze_code_availability(text, doc_cache=None, data_section_text=None):
    """Analyze text for code availability statements using NLP."""
    if not text:
        return "No text available for analysis.", []

    next_section_keywords = ["ORCID", "References", "Acknowledgments", "Conflict of Interest", "Author Contributions", "Data Availability"]
    section_keywords = ["Code Availability", "Software Availability", "Availability of Code", "Supporting Information"]
    relevant_text = find_section(text, section_keywords, next_section_keywords)
    logging.debug(f"Code availability section text: {relevant_text[:500]}...")
    
    doc = doc_cache.get(relevant_text) if doc_cache and relevant_text in doc_cache else nlp(relevant_text)
    if doc_cache is not None and relevant_text not in doc_cache:
        doc_cache[relevant_text] = doc
    
    code_keywords = keywords["source_code"]
    availability_keywords = keywords["available"] + keywords["was_available"]
    negation_keywords = keywords["not_available"]
    repository_keywords = keywords["github"] + keywords["repositories"]
    request_keywords = keywords["upon_request"]
    supplement_keywords = keywords["supplement"] + keywords["supplemental_table_name"]
    
    all_statements = []
    
    for sent in doc.sents:
        sent_text = clean_text(sent.text)
        sent_text_lower = sent_text.lower()
        has_code = any(kw in sent_text_lower for kw in code_keywords)
        has_availability = any(kw in sent_text_lower for kw in availability_keywords)
        logging.debug(f"Sentence in code section: '{sent_text}', has_code={has_code} (keywords matched: {', '.join(kw for kw in code_keywords if kw in sent_text_lower)}), has_availability={has_availability} (keywords matched: {', '.join(kw for kw in availability_keywords if kw in sent_text_lower)})")
        
        if has_code and has_availability:
            has_negation = any(kw in sent_text_lower for kw in negation_keywords)
            has_repository = any(kw in sent_text_lower for kw in repository_keywords)
            has_request = any(kw in sent_text_lower for kw in request_keywords)
            has_supplement = any(kw in sent_text_lower for kw in supplement_keywords)
            
            if has_negation:
                category = "Not Available"
            elif has_request:
                category = "Available Upon Request"
            elif has_repository:
                category = "Available in Repository"
            elif has_supplement:
                category = "Available in Supplementary Materials"
            else:
                category = "Other Availability"
            
            score = score_code_statement(sent_text, category)
            all_statements.append((category, sent_text, score))
            logging.debug(f"Found code statement in code section: Category={category}, Score={score}, Statement={sent_text[:500]}...")
    
    if not all_statements and data_section_text:
        logging.info("No dedicated code availability section found, checking data availability section for code references")
        section_text = clean_text(data_section_text)
        section_lower = section_text.lower()
        has_code_in_section = any(kw in section_lower for kw in code_keywords)
        has_availability_in_section = any(kw in section_lower for kw in availability_keywords)
        logging.debug(f"Data section text: '{section_text[:500]}...', has_code={has_code_in_section} (keywords matched: {', '.join(kw for kw in code_keywords if kw in section_lower)}), has_availability={has_availability_in_section} (keywords matched: {', '.join(kw for kw in availability_keywords if kw in section_lower)})")
        
        if has_code_in_section:
            doc = nlp(section_text)
            for sent in doc.sents:
                sent_text = clean_text(sent.text)
                sent_text_lower = sent_text.lower()
                has_code = any(kw in sent_text_lower for kw in code_keywords)
                has_availability = any(kw in sent_text_lower for kw in availability_keywords)
                logging.debug(f"Sentence in data section: '{sent_text}', has_code={has_code} (keywords matched: {', '.join(kw for kw in code_keywords if kw in sent_text_lower)}), has_availability={has_availability} (keywords matched: {', '.join(kw for kw in availability_keywords if kw in sent_text_lower)})")
                
                if has_code and has_availability:
                    has_negation = any(kw in sent_text_lower for kw in negation_keywords)
                    has_repository = any(kw in sent_text_lower for kw in repository_keywords)
                    has_request = any(kw in sent_text_lower for kw in request_keywords)
                    has_supplement = any(kw in sent_text_lower for kw in supplement_keywords)
                    
                    if has_negation:
                        category = "Not Available"
                    elif has_request:
                        category = "Available Upon Request"
                    elif has_repository:
                        category = "Available in Repository"
                    elif has_supplement:
                        category = "Available in Supplementary Materials"
                    else:
                        category = "Other Availability"
                    
                    score = score_code_statement(sent_text, category)
                    all_statements.append((category, sent_text, score))
                    logging.debug(f"Found code statement in data section: Category={category}, Score={score}, Statement={sent_text[:500]}...")
                elif has_code:
                    if has_availability_in_section:
                        category = "Other Availability"
                        score = score_code_statement(sent_text, category)
                        all_statements.append((category, sent_text, score))
                        logging.debug(f"Found partial code statement in data section (availability in section): Category={category}, Score={score}, Statement={sent_text[:500]}...")
    
    if all_statements:
        all_statements.sort(key=lambda x: x[2], reverse=True)
        best_statement = truncate_statement(all_statements[0][1])
        category = all_statements[0][0]
        score = all_statements[0][2]
        logging.info(f"Best code availability statement: Category={category}, Score={score}, Statement={best_statement}")
        all_statements_formatted = [truncate_statement(stmt) for _, stmt, _ in all_statements]
        return best_statement, all_statements_formatted
    
    logging.info(f"No code availability statement found for DOI. Text excerpt: {text[:500]}...")
    return "No code availability statement found.", []

def analyze_data_metadata(links):
    """Analyze metadata of data links (format, repository, etc.)."""
    metadata = {
        "format": "",
        "repository": "",
        "repository_url": "",
        "download_status": False,
        "data_download_path": "",
        "data_size": 0.0,
        "number_of_files": 0,
        "license": ""
    }
    
    if not links:
        return metadata
    
    link = links[0]
    if len(link) > MAX_URL_LENGTH:
        logging.warning(f"Skipping data metadata analysis due to URL length > {MAX_URL_LENGTH}: {link[:100]}...")
        return metadata
    
    try:
        response = requests.head(link, timeout=10, allow_redirects=True)
        response.raise_for_status()
        
        content_type = response.headers.get("content-type", "").lower()
        if "csv" in content_type:
            metadata["format"] = "CSV"
        elif "json" in content_type:
            metadata["format"] = "JSON"
        elif "zip" in content_type:
            metadata["format"] = "ZIP"
        else:
            metadata["format"] = content_type.split("/")[-1] if "/" in content_type else "Unknown"
        
        content_length = response.headers.get("content-length")
        if content_length:
            metadata["data_size"] = float(content_length) / 1024
        
        if "zenodo.org" in link:
            metadata["repository"] = "Zenodo"
            metadata["repository_url"] = "https://zenodo.org"
        elif "figshare.com" in link:
            metadata["repository"] = "Figshare"
            metadata["repository_url"] = "https://figshare.com"
        elif "github.com" in link:
            metadata["repository"] = "GitHub"
            metadata["repository_url"] = "https://github.com"
        elif "dryad" in link:
            metadata["repository"] = "Dryad"
            metadata["repository_url"] = "https://datadryad.org"
        else:
            metadata["repository"] = "Unknown"
            metadata["repository_url"] = link
        
        metadata["download_status"] = True
        metadata["number_of_files"] = 1
        metadata["license"] = "Unknown"
        
        logging.info(f"Data metadata for link {link}: {metadata}")
    except Exception as e:
        logging.error(f"Error analyzing data metadata for link {link}: {str(e)}")
    
    return metadata

def process_doi_wrapper(args):
    """Wrapper function to call process_single_doi with arguments."""
    init_logging()  # Ensure logging is set up in child process
    doi, save_to_disk, email, download_dir, data_download_dir, target_formats, identifier, title = args
    return process_single_doi(doi, save_to_disk, email, download_dir, data_download_dir, target_formats, identifier, title)

def process_single_doi(doi, save_to_disk=True, email=None, download_dir=DOWNLOAD_DIR, data_download_dir=DATA_DOWNLOAD_DIR, target_formats=DEFAULT_DATA_FORMATS, identifier="001", title="unknown"):
    """Process a single DOI (used for parallel processing)."""
    logging.debug(f"Starting processing for DOI: {doi}")
    if not validate_doi(doi):
        logging.warning(f"Invalid DOI: {doi}")
        return None
    
    is_oa, has_fulltext, fulltext_urls = get_unpaywall_data(doi, email)
    logging.info(f"DOI {doi}: is_oa={is_oa}, has_fulltext={has_fulltext}, fulltext_urls={fulltext_urls}")
    
    title_from_api, authors, published, journal, url, pdf_url = get_openalex_data(doi)
    title = title_from_api if title_from_api else title
    
    downloaded = False
    pdf_content = None
    pdf_content_length = 0
    file_path = ""
    if has_fulltext and fulltext_urls:
        logging.info(f"Attempting to download PDF for DOI {doi} from Unpaywall URLs: {fulltext_urls}")
        downloaded, pdf_content, pdf_content_length, file_path = download_pdf(doi, fulltext_urls, save_to_disk, download_dir, identifier, title)
    if not downloaded and pdf_url:
        logging.info(f"Unpaywall failed or no URL, attempting to download PDF for DOI {doi} from OpenAlex PDF URL: {pdf_url}")
        downloaded, pdf_content, pdf_content_length, file_path = download_pdf(doi, [pdf_url], save_to_disk, download_dir, identifier, title)
    if not downloaded and url:
        logging.info(f"No PDF URL available, attempting to download PDF for DOI {doi} from OpenAlex landing page URL: {url}")
        downloaded, pdf_content, pdf_content_length, file_path = download_pdf(doi, [url], save_to_disk, download_dir, identifier, title)
    if not downloaded:
        logging.info(f"No download succeeded for DOI {doi}: has_fulltext={has_fulltext}, fulltext_urls={fulltext_urls}, openalex_pdf_url={pdf_url}, landing_page_url={url}")
    
    text = extract_text_from_pdf(pdf_content) if downloaded else ""
    doc_cache = {}
    
    data_availability, data_links, all_data_statements = analyze_data_availability(text, doc_cache)
    data_section_text = find_section(text, keywords["data_availability"], ["ORCID", "References", "Acknowledgments", "Conflict of Interest", "Author Contributions"])
    
    code_availability, all_code_statements = analyze_code_availability(text, doc_cache, data_section_text)
    
    data_metadata = analyze_data_metadata(data_links) if data_links else {
        "format": "",
        "repository": "",
        "repository_url": "",
        "download_status": False,
        "data_download_path": "",
        "data_size": 0.0,
        "number_of_files": 0,
        "license": ""
    }

    additional_data_links = []
    session = requests.Session()
    landing_pages = [url] if url else []
    if fulltext_urls:
        landing_pages.extend([u for u in fulltext_urls if not u.endswith(".pdf") and len(u) <= MAX_URL_LENGTH])
    
    landing_pages.extend([link for link in data_links if link.startswith(('http://', 'https://')) and len(link) <= MAX_URL_LENGTH])
    seen = set()
    landing_pages = [page for page in landing_pages if not (page in seen or seen.add(page))]
    
    for landing_page in landing_pages:
        if is_data_related_url(landing_page, target_formats):
            new_links = find_data_urls(landing_page, session, [ext.lstrip('.') for ext in target_formats])
            additional_data_links.extend([link for link in new_links if len(link) <= MAX_URL_LENGTH])
    
    all_data_links = list(set(data_links + additional_data_links))
    logging.info(f"All data links for DOI {doi}: {all_data_links}")

    downloaded_data_files = []
    create_data_download_dir(data_download_dir)
    for link in all_data_links:
        file_path = download_data_file(link, doi, data_download_dir, target_formats, identifier, title)
        if file_path:
            downloaded_data_files.append(file_path)
    
    result = {
        "identifier": identifier,
        "doi": doi,
        "title": title,
        "authors": authors,
        "published": published,
        "url": url,
        "journal": journal,
        "has_fulltext": has_fulltext,
        "is_oa": is_oa,
        "downloaded": downloaded,
        "path": file_path,
        "pdf_content_length": pdf_content_length,
        "data_links": all_data_links,
        "downloaded_data_files": downloaded_data_files,
        "data_availability_statements": data_availability,
        "all_data_availability_statements": all_data_statements,
        "code_availability_statements": code_availability,
        "all_code_availability_statements": all_code_statements,
        "format": data_metadata["format"],
        "repository": data_metadata["repository"],
        "repository_url": data_metadata["repository_url"],
        "download_status": data_metadata["download_status"],
        "data_download_path": data_metadata["data_download_path"],
        "data_size": data_metadata["data_size"],
        "number_of_files": data_metadata["number_of_files"],
        "license": data_metadata["license"]
    }
    logging.debug(f"Completed processing for DOI: {doi}")
    return result

def process_dois(doi_list, save_to_disk=True, email=None, download_dir=DOWNLOAD_DIR, data_download_dir=DATA_DOWNLOAD_DIR, target_formats=DEFAULT_DATA_FORMATS):
    """Process list of DOIs and generate output table using parallel processing."""
    if save_to_disk:
        create_download_dir(download_dir)
    
    args = [
        (
            doi,
            save_to_disk,
            email,
            download_dir,
            data_download_dir,
            target_formats,
            f"{idx + 1:03d}",
            "unknown"
        )
        for idx, doi in enumerate(doi_list)
    ]
    
    from multiprocessing import Pool
    with Pool(processes=4) as pool:  # Limit to 4 processes to reduce resource strain
        results = list(tqdm(pool.imap(process_doi_wrapper, args), total=len(doi_list), desc="Processing DOIs"))
    
    results = [r for r in results if r is not None]
    return pd.DataFrame(results)

def process_and_analyze_dois(input_file=None, dois=None, save_to_disk=True, email=None, download_dir=DOWNLOAD_DIR, data_download_dir=DATA_DOWNLOAD_DIR, target_formats=DEFAULT_DATA_FORMATS):
    """Process DOIs, download PDFs, extract text, and analyze data and code availability."""
    if input_file:
        df = pd.read_csv(input_file)
        doi_list = df["doi"].tolist()
    elif dois:
        doi_list = dois
    else:
        raise ValueError("Provide either input_file or dois")
    
    df = process_dois(doi_list, save_to_disk, email, download_dir, data_download_dir, target_formats)
    output_file = "ecoopen_output.csv"
    df.to_csv(output_file, index=False, sep=';')
    logging.info(f"Output saved to {output_file}")
    return df