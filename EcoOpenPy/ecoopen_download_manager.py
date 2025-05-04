import asyncio
import logging
from typing import Optional, List, Dict
from aiohttp import ClientSession
from ecoopen_utils import get_header_variations, is_pdf_content, log_response_details, get_alternative_url

# Configure logging with more detail
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

async def download_with_aiohttp(doi: str, url: str, download_dir: str, session: ClientSession, api_configs: Dict, semaphore: asyncio.Semaphore) -> Optional[str]:
    """Download a PDF using aiohttp with retries and header variations."""
    logging.debug(f"Starting download_with_aiohttp for DOI {doi} with URL {url}")
    async with semaphore:
        max_retries = 3
        initial_delay = 1
        headers_list = get_header_variations()
        timeout = aiohttp.ClientTimeout(total=60)

        for retry_count in range(max_retries):
            headers = headers_list[retry_count % len(headers_list)]
            logging.debug(f"Retry {retry_count + 1}/{max_retries} for DOI {doi} with headers: {headers}")
            if "api.elsevier.com" in url.lower() and "elsevier" in api_configs and "api_key" in api_configs["elsevier"]:
                headers["X-ELS-APIKey"] = api_configs["elsevier"]["api_key"]
                logging.debug(f"Using Elsevier API key for DOI {doi}")

            try:
                async with session.get(url, headers=headers, allow_redirects=True, timeout=timeout) as response:
                    logging.debug(f"Received response for DOI {doi}: Status {response.status}")
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "").lower()
                    logging.info(f"Attempt {retry_count + 1}/{max_retries} for DOI {doi} - Status: {response.status}, Content-Type: {content_type}")

                    if "application/json" in content_type and "api.elsevier.com" in url.lower():
                        data = await response.json()
                        article = data.get("full-text-retrieval-response", {}).get("coredata", {})
                        pdf_url = article.get("link", [{}])[0].get("href") if article.get("openaccess", "0") == "1" else url
                        if pdf_url and pdf_url != url:
                            logging.debug(f"Found Elsevier PDF URL for DOI {doi}: {pdf_url}")
                            url = pdf_url
                            continue
                        logging.warning(f"No PDF URL in Elsevier API response for DOI {doi}")
                        return None

                    if not any(x in content_type for x in ["pdf", "octet-stream", "binary", "application/x-download"]):
                        if not url.lower().endswith(".pdf"):
                            await log_response_details(doi, response)
                            logging.debug(f"Content-Type {content_type} not a PDF and URL does not end with .pdf for DOI {doi}")
                            return None
                        logging.info(f"URL ends with .pdf, proceeding despite Content-Type: {content_type}")

                    content = await response.read()
                    if not is_pdf_content(content):
                        logging.warning(f"Content for DOI {doi} does not start with PDF magic bytes")
                        return None

                    download_path = f"{download_dir}/{doi}/paper.pdf"
                    os.makedirs(os.path.dirname(download_path), exist_ok=True)
                    with open(download_path, "wb") as f:
                        f.write(content)

                    file_size = os.path.getsize(download_path)
                    if file_size < 1000:
                        os.remove(download_path)
                        logging.warning(f"Downloaded file for DOI {doi} is too small: {file_size} bytes")
                        return None

                    logging.info(f"Successfully downloaded with aiohttp for DOI {doi} to {download_path} (Size: {file_size} bytes)")
                    return download_path

            except aiohttp.ClientResponseError as e:
                await log_response_details(doi, response if 'response' in locals() else None)
                if e.status == 429:
                    retry_count += 1
                    delay = initial_delay * (2 ** retry_count) + random.uniform(0, 1)
                    logging.warning(f"Rate limit hit for DOI {doi}, retrying ({retry_count}/{max_retries}) after {delay:.2f}s")
                    await asyncio.sleep(delay)
                elif e.status in [403, 404, 401]:
                    logging.warning(f"Failed for DOI {doi}: Status {e.status}")
                    break
                else:
                    logging.error(f"Error downloading for DOI {doi}: {e}")
                    break
            except Exception as e:
                logging.error(f"Unexpected error downloading for DOI {doi}: {e}")
                break

        # Try alternative URL as a fallback
        alt_url = await get_alternative_url(url)
        if alt_url:
            logging.info(f"Retrying with alternative URL for DOI {doi}: {alt_url}")
            return await download_with_aiohttp(doi, alt_url, download_dir, session, api_configs, semaphore)
        logging.debug(f"All retries failed for DOI {doi} with URL {url}")
        return None

async def manage_download(doi: str, url: str, download_dir: str, session: ClientSession, api_configs: Dict, semaphore: asyncio.Semaphore) -> Optional[str]:
    """Manage the download process with aiohttp (browser fallback temporarily disabled for debugging)."""
    logging.debug(f"Starting manage_download for DOI {doi} with URL {url}")
    result = await download_with_aiohttp(doi, url, download_dir, session, api_configs, semaphore)
    if result:
        logging.debug(f"Download successful for DOI {doi}: {result}")
        return result

    logging.info(f"Download failed for DOI {doi} with URL {url} using aiohttp")
    # Temporarily disable browser fallback for debugging
    # logging.info(f"Falling back to browser download for DOI {doi}")
    # return await download_with_browser(doi, url, download_dir)
    return None