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
from keywords import keywords  # Import the keywords dictionary
from multiprocessing import Pool
import threading

# Configuration
UNPAYWALL_EMAIL = "domagojhack@gmail.com"
DOWNLOAD_DIR = "./downloads"
LOG_FILE = "ecoopen.log"

# Setup logging with thread-safe handler
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode='w'  # Clear the log file before writing
)

# Thread-safe logging handler
logging_lock = threading.Lock()

def log_message(level, message):
    with logging_lock:
        if level == "INFO":
            logging.info(message)
        elif level == "WARNING":
            logging.warning(message)
        elif level == "ERROR":
            logging.error(message)

# Initialize the spaCy NLP pipeline with minimal components
nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer", "tagger"])

def validate_doi(doi):
    """Validate DOI format using regex."""
    doi_pattern = r'^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$'
    try:
        return bool(re.match(doi_pattern, doi))
    except TypeError:
        log_message("WARNING", f"Invalid DOI format: {doi}")
        return False

def create_download_dir():
    """Create download directory if it doesn't exist."""
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        log_message("INFO", f"Created download directory: {DOWNLOAD_DIR}")

def get_unpaywall_data(doi):
    """Query Unpaywall for open-access status and full-text URL."""
    try:
        url = f"https://api.unpaywall.org/v2/{quote(doi)}?email={UNPAYWALL_EMAIL}"
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
                url_to_add = None
                if location.get("url_for_pdf"):
                    url_to_add = location["url_for_pdf"]
                elif location.get("url_for_landing_page"):
                    url_to_add = location["url_for_landing_page"]
                elif location.get("url"):
                    url_to_add = location["url"]
                if url_to_add:
                    if location.get("host_type") == "repository":
                        repo_urls.append(url_to_add)
                    else:
                        publisher_urls.append(url_to_add)
            fulltext_urls = repo_urls + publisher_urls
        has_fulltext = bool(fulltext_urls)
        log_message("INFO", f"Unpaywall for DOI {doi}: is_oa={is_oa}, has_fulltext={has_fulltext}, fulltext_urls={fulltext_urls}, oa_locations={oa_locations}")
        return is_oa, has_fulltext, fulltext_urls
    except Exception as e:
        log_message("ERROR", f"Unpaywall error for DOI {doi}: {str(e)}")
        return False, False, []

def get_openalex_data(doi):
    """Query OpenAlex for metadata and potential PDF URL."""
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
            log_message("INFO", f"OpenAlex for DOI {doi}: pdf_url={pdf_url}, landing_page_url={url}")
            return title, authors, published, journal, url, pdf_url
        return "", "", "", "", "", None
    except Exception as e:
        log_message("ERROR", f"OpenAlex error for DOI {doi}: {str(e)}")
        return "", "", "", "", "", None

def find_pdf_url_from_landing_page(url, session):
    """Attempt to find a PDF URL by scraping the landing page."""
    try:
        response = session.get(url, timeout=15, allow_redirects=True)
        response.raise_for_status()
        if "text/html" in response.headers.get("content-type", "").lower():
            soup = BeautifulSoup(response.text, "html.parser")
            pdf_links = soup.find_all("a", href=re.compile(r"\.pdf(?:\?.*)?$", re.I))
            for link in pdf_links:
                href = link.get("href")
                if href:
                    if href.startswith("http"):
                        return href
                    from urllib.parse import urljoin
                    return urljoin(url, href)
        return None
    except Exception as e:
        log_message("ERROR", f"Error scraping PDF URL from landing page {url}: {str(e)}")
        return None

def download_pdf(doi, urls, save_to_disk=True):
    """Download PDF from a list of URLs and return binary content."""
    session = requests.Session()
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
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
    safe_doi = quote(doi, safe="")
    file_path = os.path.join(DOWNLOAD_DIR, f"{safe_doi}.pdf") if save_to_disk else ""
    
    for url in urls:
        # Extract the base landing page URL for the Referer header
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path.rsplit('/', 1)[0]}"
        headers["Referer"] = base_url  # Set Referer to the landing page
        session.headers.update(headers)

        # Visit the landing page to establish a session and get cookies
        try:
            landing_response = session.get(base_url, timeout=15, allow_redirects=True)
            landing_response.raise_for_status()
            log_message("INFO", f"Visited landing page for DOI {doi}: {base_url}, Cookies: {session.cookies.get_dict()}")
        except Exception as e:
            log_message("WARNING", f"Failed to visit landing page for DOI {doi}: {base_url}, Error: {str(e)}")

        # Try the original URL and a version without the version parameter
        url_variants = [url]
        if "version=" in url:
            url_without_version = url.split("?")[0]
            url_variants.append(url_without_version)

        for pdf_url in url_variants:
            for attempt in range(3):
                try:
                    if not pdf_url or not pdf_url.startswith(('http://', 'https://')):
                        log_message("ERROR", f"Invalid or missing URL for DOI {doi}: {pdf_url}")
                        break
                    log_message("INFO", f"Attempt {attempt + 1}/3 for DOI {doi} with URL: {pdf_url}")
                    response = session.get(pdf_url, timeout=15, stream=True, allow_redirects=True)
                    if response.status_code == 403:
                        log_message("WARNING", f"403 Forbidden for DOI {doi}, Response Headers: {response.headers}, Content: {response.text[:500]}...")
                        time.sleep(random.uniform(3, 6))  # Increased delay
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if "pdf" not in content_type and "octet-stream" not in content_type:
                        if not pdf_url.endswith(".pdf"):
                            new_url = pdf_url.rstrip("/") + "/pdf"
                            log_message("INFO", f"URL not a PDF, trying modified URL for DOI {doi}: {new_url}")
                            response = session.get(new_url, timeout=15, stream=True, allow_redirects=True)
                            response.raise_for_status()
                            content_type = response.headers.get("content-type", "").lower()
                            if "pdf" not in content_type and "octet-stream" not in content_type:
                                pdf_url_from_landing = find_pdf_url_from_landing_page(base_url, session)
                                if pdf_url_from_landing:
                                    log_message("INFO", f"Found PDF URL via scraping for DOI {doi}: {pdf_url_from_landing}")
                                    response = session.get(pdf_url_from_landing, timeout=15, stream=True, allow_redirects=True)
                                    response.raise_for_status()
                                    content_type = response.headers.get("content-type", "").lower()
                                    if "pdf" not in content_type and "octet-stream" not in content_type:
                                        log_message("WARNING", f"Scraped URL for DOI {doi} does not point to a PDF: {pdf_url_from_landing}, Content-Type: {content_type}")
                                        break
                                else:
                                    log_message("WARNING", f"No PDF URL found after scraping for DOI {doi}, Content-Type: {content_type}")
                                    break
                    pdf_content = b"".join(response.iter_content(chunk_size=8192))
                    pdf_content_length = len(pdf_content)
                    if save_to_disk:
                        create_download_dir()
                        with open(file_path, "wb") as f:
                            f.write(pdf_content)
                        log_message("INFO", f"Saved PDF for DOI {doi} to {file_path} (size: {pdf_content_length} bytes)")
                    else:
                        log_message("INFO", f"Downloaded PDF content for DOI {doi} (size: {pdf_content_length} bytes, not saved to disk)")
                    return True, pdf_content, pdf_content_length, file_path
                except Exception as e:
                    log_message("ERROR", f"Download error for DOI {doi}: {str(e)} (URL: {pdf_url})")
                    if attempt < 2:
                        time.sleep(random.uniform(3, 6))  # Increased delay
                    continue
            log_message("INFO", f"All attempts failed for URL: {pdf_url}")
    return False, None, 0, ""

def extract_text_from_pdf(pdf_content):
    """Extract text from PDF content (binary string)."""
    try:
        if not pdf_content:
            return ""
        doc = fitz.open("pdf", pdf_content)
        text = ""
        for page in doc:
            text += page.get_text("text")
        doc.close()
        log_message("INFO", f"Extracted text from PDF (length: {len(text)} characters)")
        return text
    except Exception as e:
        log_message("ERROR", f"Error extracting text from PDF: {str(e)}")
        return ""

def find_section(text, section_keywords):
    """Find a specific section in the text (e.g., 'Data Availability') and extract its content."""
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if any(keyword.lower() in line.lower() for keyword in section_keywords):
            # Extract text until the next section header or end of document
            section_text = []
            for j in range(i + 1, len(lines)):
                # Simple heuristic for section headers: starts with capital letter, no lowercase words
                if re.match(r'^\s*[A-Z][A-Z\s]+\s*$', lines[j].strip()):
                    break
                if lines[j].strip():
                    section_text.append(lines[j])
            return '\n'.join(section_text).strip()
    return text  # Fallback to full text if no section found

def analyze_data_availability(text, doc_cache=None):
    """Analyze text for data availability statements using NLP and extract data links."""
    if not text:
        return "No text available for analysis.", []

    # Focus on relevant sections using keywords from keywords.py
    relevant_text = find_section(text, keywords["data_availability"])
    
    # Process the text with spaCy (use cached doc if available)
    doc = doc_cache.get(relevant_text) if doc_cache and relevant_text in doc_cache else nlp(relevant_text)
    if doc_cache is not None and relevant_text not in doc_cache:
        doc_cache[relevant_text] = doc
    
    # Use keywords from keywords.py
    data_keywords = keywords["data"] + keywords["all_data"] + keywords["dataset_name"]
    availability_keywords = keywords["available"] + keywords["was_available"]
    negation_keywords = keywords["not_available"] + keywords["not_data"]
    repository_keywords = keywords["repositories"] + keywords["field_specific_repo"] + keywords["github"]
    request_keywords = keywords["upon_request"]
    supplement_keywords = keywords["supplement"] + keywords["supplemental_table_name"] + keywords["supplemental_dataset"]
    
    statements = []
    current_statement = []
    current_category = None
    
    for sent in doc.sents:
        sent_text = sent.text.lower()
        # Check if the sentence contains data-related keywords and availability-related keywords
        has_data = any(kw in sent_text for kw in data_keywords)
        has_availability = any(kw in sent_text for kw in availability_keywords)
        
        if has_data and has_availability:
            # Additional checks for context
            has_negation = any(kw in sent_text for kw in negation_keywords)
            has_repository = any(kw in sent_text for kw in repository_keywords)
            has_request = any(kw in sent_text for kw in request_keywords)
            has_supplement = any(kw in sent_text for kw in supplement_keywords)
            has_accession = any(re.search(pattern, sent_text) for pattern in keywords["accession_nr"])
            
            # Categorize the statement
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
            
            # Group consecutive sentences
            if current_statement and current_category == category:
                current_statement.append(sent.text.strip())
            else:
                if current_statement:
                    statements.append((current_category, " ".join(current_statement)))
                current_statement = [sent.text.strip()]
                current_category = category
        else:
            # If the sentence doesn't match, close the current statement
            if current_statement:
                statements.append((current_category, " ".join(current_statement)))
                current_statement = []
                current_category = None
    
    # Add the last statement if it exists
    if current_statement:
        statements.append((current_category, " ".join(current_statement)))
    
    if statements:
        # Prioritize statements: Repository > Supplementary > Request > Other > Not Available
        priority = {
            "Available in Repository": 1,
            "Available in Supplementary Materials": 2,
            "Available Upon Request": 3,
            "Other Availability": 4,
            "Not Available": 5
        }
        statements.sort(key=lambda x: priority.get(x[0], 6))
        
        # Take the highest priority statement
        category, statement = statements[0]
        log_message("INFO", f"Data availability match for DOI: Category={category}, Statement={statement}")
        
        # Extract URLs from the statement
        urls = re.findall(r"(?:https?://[^\s]+|doi:[^\s]+|<doi:[^\s>]+>)", statement)
        return statement, urls
    
    log_message("INFO", f"No data availability statement found for DOI. Text excerpt: {text[:500]}...")
    return "No data availability statement found.", []

def analyze_code_availability(text, doc_cache=None):
    """Analyze text for code availability statements using NLP."""
    if not text:
        return "No text available for analysis."
    
    # Focus on relevant sections using keywords from keywords.py
    section_keywords = ["Code Availability", "Software Availability", "Availability of Code", "Supporting Information"]
    relevant_text = find_section(text, section_keywords)
    
    # Use cached doc if available, otherwise process with spaCy
    doc = doc_cache.get(relevant_text) if doc_cache and relevant_text in doc_cache else nlp(relevant_text)
    
    # Use keywords from keywords.py
    code_keywords = keywords["source_code"]
    availability_keywords = keywords["available"] + keywords["was_available"]
    negation_keywords = keywords["not_available"]
    repository_keywords = keywords["github"] + keywords["repositories"]
    request_keywords = keywords["upon_request"]
    supplement_keywords = keywords["supplement"] + keywords["supplemental_table_name"]
    
    statements = []
    current_statement = []
    current_category = None
    
    for sent in doc.sents:
        sent_text = sent.text.lower()
        # Check if the sentence contains code-related keywords and availability-related keywords
        has_code = any(kw in sent_text for kw in code_keywords)
        has_availability = any(kw in sent_text for kw in availability_keywords)
        
        if has_code and has_availability:
            # Additional checks for context
            has_negation = any(kw in sent_text for kw in negation_keywords)
            has_repository = any(kw in sent_text for kw in repository_keywords)
            has_request = any(kw in sent_text for kw in request_keywords)
            has_supplement = any(kw in sent_text for kw in supplement_keywords)
            
            # Categorize the statement
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
            
            # Group consecutive sentences
            if current_statement and current_category == category:
                current_statement.append(sent.text.strip())
            else:
                if current_statement:
                    statements.append((current_category, " ".join(current_statement)))
                current_statement = [sent.text.strip()]
                current_category = category
        else:
            # If the sentence doesn't match, close the current statement
            if current_statement:
                statements.append((current_category, " ".join(current_statement)))
                current_statement = []
                current_category = None
    
    # Add the last statement if it exists
    if current_statement:
        statements.append((current_category, " ".join(current_statement)))
    
    if statements:
        # Prioritize statements: Repository > Supplementary > Request > Other > Not Available
        priority = {
            "Available in Repository": 1,
            "Available in Supplementary Materials": 2,
            "Available Upon Request": 3,
            "Other Availability": 4,
            "Not Available": 5
        }
        statements.sort(key=lambda x: priority.get(x[0], 6))
        
        # Take the highest priority statement
        category, statement = statements[0]
        log_message("INFO", f"Code availability match for DOI: Category={category}, Statement={statement}")
        return statement
    
    log_message("INFO", f"No code availability statement found for DOI. Text excerpt: {text[:500]}...")
    return "No code availability statement found."

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
            metadata["data_size"] = float(content_length) / 1024  # Convert to KB
        
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
        metadata["number_of_files"] = 1  # Simplified assumption
        
        metadata["license"] = "Unknown"
        
        log_message("INFO", f"Data metadata for link {link}: {metadata}")
    except Exception as e:
        log_message("ERROR", f"Error analyzing data metadata for link {link}: {str(e)}")
    
    return metadata

def process_doi_wrapper(args):
    """Wrapper function to call process_single_doi with arguments."""
    doi, save_to_disk = args
    return process_single_doi(doi, save_to_disk)

def process_single_doi(doi, save_to_disk=True):
    """Process a single DOI (used for parallel processing)."""
    if not validate_doi(doi):
        log_message("WARNING", f"Invalid DOI: {doi}")
        return None
    
    # Query Unpaywall
    is_oa, has_fulltext, fulltext_urls = get_unpaywall_data(doi)
    log_message("INFO", f"DOI {doi}: is_oa={is_oa}, has_fulltext={has_fulltext}, fulltext_urls={fulltext_urls}")
    
    # Get metadata from OpenAlex
    title, authors, published, journal, url, pdf_url = get_openalex_data(doi)
    
    # Download PDF if available
    downloaded = False
    pdf_content = None
    pdf_content_length = 0
    file_path = ""
    if has_fulltext and fulltext_urls:
        log_message("INFO", f"Attempting to download PDF for DOI {doi} from Unpaywall URLs: {fulltext_urls}")
        downloaded, pdf_content, pdf_content_length, file_path = download_pdf(doi, fulltext_urls, save_to_disk)
    if not downloaded and pdf_url:
        log_message("INFO", f"Unpaywall failed or no URL, attempting to download PDF for DOI {doi} from OpenAlex PDF URL: {pdf_url}")
        downloaded, pdf_content, pdf_content_length, file_path = download_pdf(doi, [pdf_url], save_to_disk)
    if not downloaded and url:
        log_message("INFO", f"No PDF URL available, attempting to download PDF for DOI {doi} from OpenAlex landing page URL: {url}")
        downloaded, pdf_content, pdf_content_length, file_path = download_pdf(doi, [url], save_to_disk)
    if not downloaded:
        log_message("INFO", f"No download succeeded for DOI {doi}: has_fulltext={has_fulltext}, fulltext_urls={fulltext_urls}, openalex_pdf_url={pdf_url}, landing_page_url={url}")
    
    # Extract and analyze text
    text = extract_text_from_pdf(pdf_content) if downloaded else ""
    
    # Cache NLP results to reuse between data and code availability analysis
    doc_cache = {}
    data_availability, data_links = analyze_data_availability(text, doc_cache)
    code_availability = analyze_code_availability(text, doc_cache)
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
    
    # Compile result with all requested columns
    result = {
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
        "data_links": data_links,
        "data_availability_statements": data_availability,
        "code_availability_statements": code_availability,
        "format": data_metadata["format"],
        "repository": data_metadata["repository"],
        "repository_url": data_metadata["repository_url"],
        "download_status": data_metadata["download_status"],
        "data_download_path": data_metadata["data_download_path"],
        "data_size": data_metadata["data_size"],
        "number_of_files": data_metadata["number_of_files"],
        "license": data_metadata["license"]
    }
    return result

def process_dois(doi_list, save_to_disk=True):
    """Process list of DOIs and generate output table using parallel processing."""
    if save_to_disk:
        create_download_dir()
    
    # Prepare arguments for parallel processing
    args = [(doi, save_to_disk) for doi in doi_list]
    
    # Use multiprocessing to parallelize DOI processing
    with Pool() as pool:
        results = list(tqdm(pool.imap(process_doi_wrapper, args), total=len(doi_list), desc="Processing DOIs"))
    
    # Filter out None results (invalid DOIs)
    results = [r for r in results if r is not None]
    return pd.DataFrame(results)

def process_and_analyze_dois(input_file=None, dois=None, save_to_disk=True):
    """Process DOIs, download PDFs, extract text, and analyze data and code availability."""
    if input_file:
        df = pd.read_csv(input_file)
        doi_list = df["doi"].tolist()
    elif dois:
        doi_list = dois
    else:
        raise ValueError("Provide either input_file or dois")
    
    df = process_dois(doi_list, save_to_disk)
    output_file = "ecoopen_output.csv"
    df.to_csv(output_file, index=False, sep=';')  # Use semicolon as delimiter
    log_message("INFO", f"Output saved to {output_file}")
    return df

if __name__ == "__main__":
    # Full DOI list (106 valid DOIs, excluding "NA")
    sample_dois = [
        "10.1046/j.1526-100x.2000.80038.x",
        "10.1006/jhev.1999.0361",
        "10.1023/A:1007643800508",
        "10.1016/S0022-0981(00)00211-2",
        "10.1007/PL00008879",
        "10.1046/j.1365-2664.2000.00543.x",
        "10.1111/j.1095-8312.2000.tb00208.x",
        "10.3354/meps206033",
        "10.1023/A:1005453220792",
        "10.1046/j.1365-2656.2000.00374.x",
        "10.1006/clad.1999.0127",
        "10.1016/S0022-0981(00)00208-2",
        "10.1098/rspb.2001.1642",
        "10.1016/S0304-3800(01)00257-5",
        "10.1080/002229301300323875",
        "10.1006/bijl.2001.0522",
        "10.1046/j.1365-294X.2001.01179.x",
        "10.2307/2680224",
        "10.1007/S00265-001-0433-3",
        "10.1078/0367-2530-00055",
        "10.1023/A:1020951514763",
        "10.1016/j.ecoinf.2022.101808",
        "10.1016/j.ecoinf.2023.102204",
        "10.1016/S1055-7903(03)00161-1",
        "10.3390/d14080591",
        "10.1016/j.pedobi.2022.150843",
        "10.1186/s13717-021-00300-w",
        "10.1111/aje.13028",
        "10.1002/eco.2288",
        "10.1007/s00265-020-02952-8",
        "10.1002/ecs2.2427",
        "10.5194/bg-15-3521-2018",
        "10.1007/s11252-024-01543-z",
        "10.1016/j.ecolecon.2017.09.005",
        "10.5751/ES-13405-270407",
        "10.1111/gcb.13854",
        "10.1002/jwmg.22488",
        "10.1098/rspb.2017.1342",
        "10.1111/2041-210X.12952",
        "10.1007/s00606-016-1324-4",
        "10.1007/s00248-023-02291-x",
        "10.1111/gcb.15597",
        "10.1111/mec.12929",
        "10.1098/rspb.2016.1703",
        "10.1002/ecy.4020",
        "10.1002/ece3.10136",
        "10.1002/ecs2.4208",
        "10.1002/ecs2.3771",
        "10.3354/meps11697",
        "10.1007/s10530-021-02645-x",
        "10.1111/gcb.15818",
        "10.5194/bg-15-5377-2018",
        "10.1111/1365-2745.12863",
        "10.1111/1365-2745.12769",
        "10.1016/j.fooweb.2021.e00199",
        "10.1038/hdy.2011.91",
        "10.3390/d16020102",
        "10.5194/bg-11-4839-2014",
        "10.1007/s00265-019-2698-4",
        "10.1093/sysbio/syq048",
        "10.1098/rspb.2013.2167",
        "10.1002/ece3.10524",
        "10.1098/rspb.2018.1235",
        "10.3996/082016-JFWM-059",
        "10.1002/ece3.9377",
        "10.3398/064.076.0306",
        "10.1007/s00248-018-1218-9",
        "10.1016/j.ympev.2008.01.034",
        "10.1046/j.1472-4642.2003.00024.x",
        "10.1002/ece3.9754",
        "10.1080/23766808.2023.2261196",
        "10.1093/oxfordjournals.molbev.a026266",
        "10.1007/s10980-022-01426-8",
        "10.1111/ddi.13193",
        "10.1111/mec.12452",
        "10.12705/633.8",
        "10.1098/rspb.2008.1264",
        "10.1002/ece3.4063",
        "10.1111/gcb.15749",
        "10.1086/600082",
        "10.1007/s00606-007-0516-3",
        "10.1098/rspb.2013.2952",
        "10.1016/j.polar.2018.09.004",
        "10.1111/evo.12134",
        "10.1007/s00239-013-9552-5",
        "10.1038/s41437-022-00522-4",
        "10.1007/s00606-011-0547-7",
        "10.1111/1365-2435.12253",
        "10.1016/j.baae.2015.04.011",
        "10.1007/s11252-2012-0284-x",
        "10.1016/j.biocon.2013.05.008",
        "10.1007/s11252-014-0419-3",
        "10.3390/ecologies2030017",
        "10.1111/syen.12432",
        "10.1017/S0266467410000611",
        "10.1111/rec.13679",
        "10.1007/s11252-021-01198-0",
        "10.1111/j.1469-1795.2008.00299.x",
        "10.1111/gcb.12963",
        "10.1093/molbev/msn072",
        "10.3389/fevo.2019.00515",
        "10.1890/05-0380"
    ]
    process_and_analyze_dois(dois=sample_dois, save_to_disk=True)