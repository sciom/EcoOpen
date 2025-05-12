import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from ecoopen.utils import log_message  # Import from utils
import os

# Zenodo API token (set as environment variable for security)
ZENODO_ACCESS_TOKEN = os.getenv("ZENODO_ACCESS_TOKEN", "")

def fetch_zenodo_files(doi_url):
    """
    Fetch downloadable files from Zenodo using the Zenodo API.
    
    Args:
        doi_url (str): The Zenodo DOI URL (e.g., https://doi.org/10.5281/zenodo.1234567)
    
    Returns:
        list: List of URLs to downloadable files.
    """
    try:
        # Extract the Zenodo record ID from the DOI URL
        record_id = doi_url.split("zenodo.")[-1]
        if not record_id.isdigit():
            log_message("ERROR", f"Could not extract Zenodo record ID from URL: {doi_url}")
            return []
        
        # Use Zenodo API to fetch the record
        api_url = f"https://zenodo.org/api/records/{record_id}"
        headers = {"Authorization": f"Bearer {ZENODO_ACCESS_TOKEN}"} if ZENODO_ACCESS_TOKEN else {}
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
        record = response.json()
        
        # Extract file URLs
        file_urls = [file["links"]["self"] for file in record.get("files", [])]
        log_message("INFO", f"Fetched {len(file_urls)} file URLs from Zenodo for {doi_url}: {file_urls}")
        return file_urls
    except Exception as e:
        log_message("ERROR", f"Failed to fetch Zenodo files for {doi_url}: {str(e)}")
        return []

def fetch_dryad_files(doi_url):
    """
    Fetch downloadable files from Dryad using the Dryad API.
    
    Args:
        doi_url (str): The Dryad DOI URL (e.g., https://doi.org/10.5061/dryad.6939c)
    
    Returns:
        list: List of URLs to downloadable files.
    """
    try:
        # Extract the Dryad identifier from the DOI URL
        identifier = doi_url.split("dryad.")[-1]
        api_url = f"https://datadryad.org/api/v2/datasets/doi%3A10.5061%2Fdryad.{identifier}"
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        dataset = response.json()
        
        # Dryad API returns file paths; construct the download URLs
        file_urls = []
        for file in dataset.get("_embedded", {}).get("stash:files", []):
            file_path = file.get("path")
            if file_path:
                download_url = f"https://datadryad.org/stash/downloads/file_stream/{file['id']}"
                file_urls.append(download_url)
        log_message("INFO", f"Fetched {len(file_urls)} file URLs from Dryad for {doi_url}: {file_urls}")
        return file_urls
    except Exception as e:
        log_message("ERROR", f"Failed to fetch Dryad files for {doi_url}: {str(e)}")
        return []

def fetch_figshare_files(doi_url):
    """
    Fetch downloadable files from Figshare using the Figshare API.
    
    Args:
        doi_url (str): The Figshare DOI URL (e.g., https://doi.org/10.6084/m9.figshare.14167259)
    
    Returns:
        list: List of URLs to downloadable files.
    """
    try:
        # Extract the Figshare article ID from the DOI URL
        article_id = doi_url.split("figshare.")[-1].split(".")[-1]
        api_url = f"https://api.figshare.com/v2/articles/{article_id}"
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        article = response.json()
        
        # Extract file URLs
        file_urls = [file["download_url"] for file in article.get("files", [])]
        log_message("INFO", f"Fetched {len(file_urls)} file URLs from Figshare for {doi_url}: {file_urls}")
        return file_urls
    except Exception as e:
        log_message("ERROR", f"Failed to fetch Figshare files for {doi_url}: {str(e)}")
        return []

def find_data_urls(url, session, target_formats, max_depth=3, visited=None):
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
        return []
    
    visited.add(url)
    data_urls = []
    
    # Normalize URL to handle DOI redirects
    if url.startswith("https://doi.org/"):
        try:
            response = session.head(url, timeout=15, allow_redirects=True)
            url = response.url
            log_message("INFO", f"Resolved DOI URL {url} to {response.url}")
        except Exception as e:
            log_message("ERROR", f"Failed to resolve DOI URL {url}: {str(e)}")
            return []

    # Check for specific repositories and use API if possible
    if "zenodo.org" in url:
        zenodo_files = fetch_zenodo_files(url)
        data_urls.extend(zenodo_files)
    elif "dryad" in url:
        dryad_files = fetch_dryad_files(url)
        data_urls.extend(dryad_files)
    elif "figshare.com" in url or "figshare" in url:
        figshare_files = fetch_figshare_files(url)
        data_urls.extend(figshare_files)

    # If API calls returned files, return them
    if data_urls:
        return data_urls

    # Otherwise, fall back to web scraping
    try:
        # Make the HTTP request
        response = session.get(url, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        # Check if the URL is a direct file link by examining Content-Type
        content_type = response.headers.get("content-type", "").lower()
        if any(ext in content_type for ext in target_formats) or any(url.lower().endswith(f".{ext.lower()}") for ext in target_formats):
            log_message("INFO", f"Found direct data URL: {url}")
            return [url]
        
        # If the content is HTML, parse it for links
        if "text/html" not in content_type:
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
                    if full_url not in visited:
                        data_urls.append(full_url)
                        visited.add(full_url)
        
        # If no direct links are found, look for potential download pages
        if not data_urls and max_depth > 0:
            download_keywords = ["download", "data", "dataset", "file", "raw", "access", "get"]
            potential_links = soup.find_all("a", href=True, text=re.compile("|".join(download_keywords), re.I))
            for link in potential_links:
                href = link.get("href")
                full_url = urljoin(url, href)
                if full_url not in visited:
                    log_message("INFO", f"Following potential download link: {full_url}")
                    # Handle specific repository patterns
                    if "github.com" in full_url:
                        # Check if the URL is a /blob/ link, which can be converted to a raw URL
                        if "/blob/" in full_url:
                            raw_url = full_url.replace("/blob/", "/raw/")
                            # Check if the raw URL matches a target format
                            if any(raw_url.lower().endswith(f".{ext}") for ext in target_formats):
                                data_urls.append(raw_url)
                                visited.add(raw_url)
                            else:
                                # Follow the raw URL to see if it leads to more files
                                sub_urls = find_data_urls(raw_url, session, target_formats, max_depth - 1, visited)
                                data_urls.extend(sub_urls)
                        elif "raw.githubusercontent.com" in full_url:
                            # Direct raw file URL
                            if any(full_url.lower().endswith(f".{ext}") for ext in target_formats):
                                data_urls.append(full_url)
                                visited.add(full_url)
                        else:
                            # Follow the link to find more files
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
        
        log_message("INFO", f"Found {len(data_urls)} data URLs at {url}: {data_urls}")
        return data_urls
    except Exception as e:
        log_message("ERROR", f"Error scraping data URLs from {url}: {str(e)}")
        return []