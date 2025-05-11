import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from ecoopen.utils import log_message  # Import from utils

def find_data_urls(url, session, target_formats, max_depth=1, visited=None):
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
        
        # If no direct links are found, look for potential download pages (e.g., "Download" buttons)
        if not data_urls and max_depth > 0:
            download_keywords = ["download", "data", "dataset", "file", "raw"]
            potential_links = soup.find_all("a", href=True, text=re.compile("|".join(download_keywords), re.I))
            for link in potential_links:
                href = link.get("href")
                full_url = urljoin(url, href)
                if full_url not in visited:
                    log_message("INFO", f"Following potential download link: {full_url}")
                    sub_urls = find_data_urls(full_url, session, target_formats, max_depth - 1, visited)
                    data_urls.extend(sub_urls)
        
        log_message("INFO", f"Found {len(data_urls)} data URLs at {url}: {data_urls}")
        return data_urls
    except Exception as e:
        log_message("ERROR", f"Error scraping data URLs from {url}: {str(e)}")
        return []