import pandas as pd
import requests
import os
import logging
import re
import time
from tqdm import tqdm
from pyalex import Works
from urllib.parse import quote

# Configuration
UNPAYWALL_EMAIL = "domagojhack@gmail.com"
DOWNLOAD_DIR = "./downloads"
LOG_FILE = "ecoopen.log"

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def validate_doi(doi):
    """Validate DOI format using regex."""
    # Regex for DOI: starts with '10.', followed by numbers and optional characters
    doi_pattern = r'^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$'
    try:
        return bool(re.match(doi_pattern, doi))
    except TypeError:
        logging.warning(f"Invalid DOI format: {doi}")
        return False

def create_download_dir():
    """Create download directory if it doesn't exist."""
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

def get_unpaywall_data(doi):
    """Query Unpaywall for open-access status and full-text URL."""
    try:
        url = f"https://api.unpaywall.org/v2/{quote(doi)}?email={UNPAYWALL_EMAIL}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        is_oa = data.get("is_oa", False)
        # Check all OA locations for a URL
        fulltext_urls = []
        oa_locations = data.get("oa_locations", [])
        if is_oa and oa_locations:
            for location in oa_locations:
                if location.get("url_for_pdf"):
                    fulltext_urls.append(location["url_for_pdf"])
                elif location.get("url_for_landing_page"):
                    fulltext_urls.append(location["url_for_landing_page"])
                elif location.get("url"):
                    fulltext_urls.append(location["url"])
        has_fulltext = bool(fulltext_urls)
        logging.info(f"Unpaywall for DOI {doi}: is_oa={is_oa}, has_fulltext={has_fulltext}, fulltext_urls={fulltext_urls}, oa_locations={oa_locations}")
        return is_oa, has_fulltext, fulltext_urls
    except Exception as e:
        logging.error(f"Unpaywall error for DOI {doi}: {str(e)}")
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
            # Get potential PDF URL from OpenAlex
            pdf_url = work.get("open_access", {}).get("oa_url", None)
            logging.info(f"OpenAlex for DOI {doi}: pdf_url={pdf_url}, landing_page_url={url}")
            return title, authors, published, journal, url, pdf_url
        return "", "", "", "", "", None
    except Exception as e:
        logging.error(f"OpenAlex error for DOI {doi}: {str(e)}")
        return "", "", "", "", "", None

def download_pdf(doi, urls):
    """Download PDF from a list of URLs and save locally with retries and session."""
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    session.headers.update(headers)
    safe_doi = quote(doi, safe="")
    file_path = os.path.join(DOWNLOAD_DIR, f"{safe_doi}.pdf")
    
    for url in urls:
        for attempt in range(3):  # Retry up to 3 times
            try:
                if not url or not url.startswith(('http://', 'https://')):
                    logging.error(f"Invalid or missing URL for DOI {doi}: {url}")
                    break
                logging.info(f"Attempt {attempt + 1}/3 for DOI {doi} with URL: {url}")
                response = session.get(url, timeout=15, stream=True, allow_redirects=True)
                if response.status_code == 403:
                    logging.warning(f"403 Forbidden for DOI {doi}, retrying after delay...")
                    time.sleep(2)  # Wait before retrying
                    continue
                response.raise_for_status()
                # Check if the response is a PDF
                content_type = response.headers.get("content-type", "").lower()
                if "pdf" not in content_type and "octet-stream" not in content_type:
                    # Try appending /pdf to the URL if it's a landing page
                    if not url.endswith(".pdf"):
                        new_url = url.rstrip("/") + "/pdf"
                        logging.info(f"URL not a PDF, trying modified URL for DOI {doi}: {new_url}")
                        response = session.get(new_url, timeout=15, stream=True, allow_redirects=True)
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "").lower()
                        if "pdf" not in content_type and "octet-stream" not in content_type:
                            logging.warning(f"URL for DOI {doi} does not point to a PDF: {new_url}, Content-Type: {content_type}")
                            break
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logging.info(f"Downloaded PDF for DOI {doi} to {file_path}")
                return True, file_path
            except Exception as e:
                logging.error(f"Download error for DOI {doi}: {str(e)} (URL: {url})")
                if attempt < 2:  # If not the last attempt
                    time.sleep(2)  # Wait before retrying
                continue
        logging.info(f"All attempts failed for URL: {url}")
    return False, ""

def extract_text_from_pdf(file_path):
    """Placeholder: Extract text from PDF for analysis."""
    # To be implemented with data availability statement examples
    return ""

def analyze_data_availability(text):
    """Placeholder: Analyze text for data availability statements."""
    # To be implemented with rule-based extraction
    return "", []  # Returns statement and list of data links

def analyze_code_availability(text):
    """Placeholder: Analyze text for code availability statements."""
    # To be implemented with rule-based extraction
    return ""  # Returns statement

def analyze_data_metadata(links):
    """Placeholder: Analyze data links for metadata (format, repository, etc.)."""
    # To be implemented after data download functionality
    return {
        "format": "",
        "repository": "",
        "repository_url": "",
        "download_status": False,
        "data_download_path": "",
        "data_size": 0.0,
        "number_of_files": 0,
        "license": ""
    }

def process_dois(doi_list):
    """Process list of DOIs and generate output table."""
    create_download_dir()
    results = []
    
    for doi in tqdm(doi_list, desc="Processing DOIs"):
        if not validate_doi(doi):
            logging.warning(f"Invalid DOI: {doi}")
            continue
        
        # Query Unpaywall
        is_oa, has_fulltext, fulltext_urls = get_unpaywall_data(doi)
        logging.info(f"DOI {doi}: is_oa={is_oa}, has_fulltext={has_fulltext}, fulltext_urls={fulltext_urls}")
        
        # Get metadata from OpenAlex
        title, authors, published, journal, url, pdf_url = get_openalex_data(doi)
        
        # Download PDF if available
        downloaded = False
        path = ""
        # Try Unpaywall URLs first
        if has_fulltext and fulltext_urls:
            logging.info(f"Attempting to download PDF for DOI {doi} from Unpaywall URLs: {fulltext_urls}")
            downloaded, path = download_pdf(doi, fulltext_urls)
        # Fallback to OpenAlex PDF URL if Unpaywall fails
        if not downloaded and pdf_url:
            logging.info(f"Unpaywall failed or no URL, attempting to download PDF for DOI {doi} from OpenAlex PDF URL: {pdf_url}")
            downloaded, path = download_pdf(doi, [pdf_url])
        # Fallback to OpenAlex landing page URL for all articles
        if not downloaded and url:
            logging.info(f"No PDF URL available, attempting to download PDF for DOI {doi} from OpenAlex landing page URL (may require institutional access): {url}")
            downloaded, path = download_pdf(doi, [url])
        if not downloaded:
            logging.info(f"No download succeeded for DOI {doi}: has_fulltext={has_fulltext}, fulltext_urls={fulltext_urls}, openalex_pdf_url={pdf_url}, landing_page_url={url}")
        
        # Placeholder for text analysis
        text = extract_text_from_pdf(path) if downloaded else ""
        data_availability, data_links = analyze_data_availability(text)
        code_availability = analyze_code_availability(text)
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
            "path": path,
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
        results.append(result)
    
    return pd.DataFrame(results)

def main(input_file=None, dois=None):
    """Main function to run EcoOpen."""
    if input_file:
        df = pd.read_csv(input_file)
        doi_list = df["doi"].tolist()
    elif dois:
        doi_list = dois
    else:
        raise ValueError("Provide either input_file or dois")
    
    df = process_dois(doi_list)
    output_file = "ecoopen_output.csv"
    df.to_csv(output_file, index=False)
    logging.info(f"Output saved to {output_file}")
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
    main(dois=sample_dois)