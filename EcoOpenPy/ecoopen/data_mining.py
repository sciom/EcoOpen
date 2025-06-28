import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote
import logging
import os
from typing import List
from ecoopen.utils_misc import is_data_related_url
from ecoopen.constants import MAX_URL_LENGTH, USER_AGENTS

logger = logging.getLogger(__name__)

# Zenodo API token (set as environment variable for security)
ZENODO_ACCESS_TOKEN = os.getenv("ZENODO_ACCESS_TOKEN", "")

def fetch_zenodo_files(doi_url: str) -> List[str]:
    """
    Fetch downloadable files from Zenodo using the Zenodo API.
    
    Args:
        doi_url (str): The Zenodo DOI URL (e.g., https://doi.org/10.5281/zenodo.1234567)
    
    Returns:
        list: List of URLs to downloadable files.
    """
    logger.debug(f"Fetching Zenodo files for {doi_url}")
    try:
        # Extract the Zenodo record ID from the DOI URL
        record_id = doi_url.split("zenodo.")[-1]
        if not record_id.isdigit():
            logger.error(f"Could not extract Zenodo record ID from URL: {doi_url}")
            return []
        
        # Use Zenodo API to fetch the record
        api_url = f"https://zenodo.org/api/records/{record_id}"
        headers = {"Authorization": f"Bearer {ZENODO_ACCESS_TOKEN}"} if ZENODO_ACCESS_TOKEN else {}
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
        record = response.json()
        
        # Extract file URLs
        file_urls = [file["links"]["self"] for file in record.get("files", [])]
        logger.info(f"Fetched {len(file_urls)} file URLs from Zenodo for {doi_url}: {file_urls}")
        return file_urls
    except requests.exceptions.RequestException as e:
        logger.error(f"Zenodo API error for {doi_url}: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Failed to fetch Zenodo files for {doi_url}: {str(e)}")
        return []

def fetch_dryad_files(doi_url: str) -> List[str]:
    """
    Fetch downloadable files from Dryad using the Dryad API download endpoint.
    
    Args:
        doi_url (str): The Dryad DOI URL (e.g., https://doi.org/10.5061/dryad.6939c)
    
    Returns:
        list: List of URLs to downloadable files (typically a single ZIP file).
    """
    logger.debug(f"Fetching Dryad files for {doi_url}")
    try:
        # Extract the DOI from the URL (e.g., 10.5061/dryad.6939c)
        doi_match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)', doi_url)
        if not doi_match:
            logger.error(f"Could not extract Dryad DOI from URL: {doi_url}")
            return []
        
        dryad_doi = doi_match.group(1)
        encoded_doi = quote(dryad_doi)
        download_url = f"https://datadryad.org/api/v2/datasets/{encoded_doi}/download"
        logger.info(f"Using Dryad API download endpoint: {download_url}")
        return [download_url]
    except Exception as e:
        logger.error(f"Failed to fetch Dryad files for {doi_url}: {str(e)}")
        return []

def fetch_figshare_files(doi_url: str) -> List[str]:
    """
    Fetch downloadable files from Figshare using the Figshare API.
    
    Args:
        doi_url (str): The Figshare DOI URL (e.g., https://doi.org/10.6084/m9.figshare.14167259)
    
    Returns:
        list: List of URLs to downloadable files.
    """
    logger.debug(f"Fetching Figshare files for {doi_url}")
    try:
        # Extract the Figshare article ID from the DOI URL
        article_id = doi_url.split("figshare.")[-1].split(".")[-1]
        api_url = f"https://api.figshare.com/v2/articles/{article_id}"
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        article = response.json()
        
        # Extract file URLs
        file_urls = [file["download_url"] for file in article.get("files", [])]
        logger.info(f"Fetched {len(file_urls)} file URLs from Figshare for {doi_url}: {file_urls}")
        return file_urls
    except Exception as e:
        logger.error(f"Failed to fetch Figshare files for {doi_url}: {str(e)}")
        return []

def find_data_urls(url: str, session: requests.Session, target_formats: List[str], max_depth: int = 1, visited: set = None) -> List[str]:
    """
    Recursively search for data URLs on a webpage that match the target formats.
    
    Args:
        url (str): The URL to search.
        session (requests.Session): The session to use for HTTP requests.
        target_formats (list): List of target file extensions (e.g., ["csv", "xlsx"]).
        max_depth (int): Maximum recursion depth for following links.
        visited (set): Set of visited URLs to avoid cycles.
    
    Returns:
        list: List of URLs pointing to data files.
    """
    if visited is None:
        visited = set()
    
    if url in visited or max_depth < 0:
        logger.debug(f"Skipping URL {url}: already visited or max depth reached")
        return []
    
    visited.add(url)
    data_urls = []
    
    # Normalize URL to handle DOI redirects
    if url.startswith("https://doi.org/"):
        try:
            response = session.head(url, timeout=15, allow_redirects=True)
            url = response.url
            logger.info(f"Resolved DOI URL {url} to {response.url}")
        except Exception as e:
            logger.error(f"Failed to resolve DOI URL {url}: {str(e)}")
            return []

    # Check for specific repositories and use API if possible
    if "zenodo.org" in url:
        zenodo_files = fetch_zenodo_files(url)
        data_urls.extend([u for u in zenodo_files if is_data_related_url(u, target_formats)])
    elif "dryad" in url:
        dryad_files = fetch_dryad_files(url)
        data_urls.extend([u for u in dryad_files if is_data_related_url(u, target_formats)])
    elif "figshare.com" in url or "figshare" in url:
        figshare_files = fetch_figshare_files(url)
        data_urls.extend([u for u in figshare_files if is_data_related_url(u, target_formats)])

    # If API calls returned files, return them
    if data_urls:
        logger.info(f"Returning API-fetched data URLs: {data_urls}")
        return data_urls

    # Otherwise, fall back to web scraping
    try:
        # Make the HTTP request
        response = session.get(url, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        # Check if the URL is a direct file link by examining Content-Type
        content_type = response.headers.get("content-type", "").lower()
        if any(ext in content_type for ext in target_formats) or any(url.lower().endswith(f".{ext.lower()}") for ext in target_formats):
            logger.info(f"Found direct data URL: {url}")
            return [url]
        
        # If the content is HTML, parse it for links
        if "text/html" not in content_type:
            logger.debug(f"Skipping non-HTML content at {url}: Content-Type: {content_type}")
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for direct links to data files
        for ext in target_formats:
            pattern = rf"\.{ext}(?:\?.*)?$"
            data_links = soup.find_all("a", href=re.compile(pattern, re.I))
            for link in data_links:
                href = link.get("href")
                if href:
                    full_url = urljoin(url, href)
                    if is_data_related_url(full_url, target_formats) and full_url not in visited:
                        data_urls.append(full_url)
                        visited.add(full_url)
        
        # If no direct links are found, look for potential download pages
        if not data_urls and max_depth > 0:
            download_keywords = ["download", "data", "dataset", "file", "raw", "access", "get"]
            potential_links = soup.find_all("a", href=True, text=re.compile("|".join(download_keywords), re.I))
            for link in potential_links:
                href = link.get("href")
                full_url = urljoin(url, href)
                if is_data_related_url(full_url, target_formats) and full_url not in visited:
                    logger.info(f"Following potential download link: {full_url}")
                    # Handle specific repository patterns
                    if "github.com" in full_url:
                        if "/blob/" in full_url:
                            raw_url = full_url.replace("/blob/", "/raw/")
                            if any(raw_url.lower().endswith(f".{ext}") for ext in target_formats):
                                data_urls.append(raw_url)
                                visited.add(raw_url)
                            else:
                                sub_urls = find_data_urls(raw_url, session, target_formats, max_depth - 1, visited)
                                data_urls.extend(sub_urls)
                        elif "raw.githubusercontent.com" in full_url:
                            if any(full_url.lower().endswith(f".{ext}") for ext in target_formats):
                                data_urls.append(full_url)
                                visited.add(full_url)
                        else:
                            sub_urls = find_data_urls(full_url, session, target_formats, max_depth - 1, visited)
                            data_urls.extend(sub_urls)
                    elif "dryad" in full_url and "/stash/" in full_url:
                        download_url = full_url + "/downloads" if not full_url.endswith("/downloads") else full_url
                        sub_urls = find_data_urls(download_url, session, target_formats, max_depth - 1, visited)
                        data_urls.extend(sub_urls)
                    elif "zenodo.org" in full_url and "/record/" in full_url:
                        download_url = full_url + "/files" if not full_url.endswith("/files") else full_url
                        sub_urls = find_data_urls(download_url, session, target_formats, max_depth - 1, visited)
                        data_urls.extend(sub_urls)
                    elif "pangaea.de" in full_url:
                        download_url = full_url + "?format=zip" if not full_url.endswith("?format=zip") else full_url
                        sub_urls = find_data_urls(download_url, session, target_formats, max_depth - 1, visited)
                        data_urls.extend(sub_urls)
                    else:
                        sub_urls = find_data_urls(full_url, session, target_formats, max_depth - 1, visited)
                        data_urls.extend(sub_urls)
        
        logger.info(f"Found {len(data_urls)} data URLs at {url}: {data_urls}")
        return data_urls
    except Exception as e:
        logger.error(f"Error scraping data URLs from {url}: {str(e)}")
        return []