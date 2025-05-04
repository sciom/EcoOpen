import logging
from typing import Optional
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def download_with_browser(doi: str, url: str, download_dir: str) -> Optional[str]:
    """Download a PDF using a headless browser with Playwright."""
    try:
        safe_doi = doi  # Already sanitized in ecoopen_core.py
        download_path = f"{download_dir}/{safe_doi}/paper.pdf"
        os.makedirs(os.path.dirname(download_path), exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            # Set user agent to mimic a real browser
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/pdf,application/octet-stream,*/*",
                "Accept-Language": "en-US,en;q=0.9"
            })

            logging.info(f"Attempting browser download for DOI {doi} from {url}")
            response = await page.goto(url, wait_until="networkidle", timeout=30000)
            
            if response is None or response.status != 200:
                logging.warning(f"Browser failed to load URL for DOI {doi}: Status {response.status if response else 'None'}")
                await browser.close()
                return None

            content_type = response.headers.get("content-type", "").lower()
            logging.info(f"Browser response for DOI {doi} - Content-Type: {content_type}")

            if "pdf" not in content_type and "octet-stream" not in content_type:
                if not url.lower().endswith(".pdf"):
                    logging.warning(f"Browser URL for DOI {doi} does not point to a PDF: {content_type}")
                    await browser.close()
                    return None
                logging.info(f"Browser URL ends with .pdf, proceeding despite Content-Type: {content_type}")

            content = await response.body()
            with open(download_path, "wb") as f:
                f.write(content)

            file_size = os.path.getsize(download_path)
            if file_size < 1000:
                os.remove(download_path)
                logging.warning(f"Browser downloaded file for DOI {doi} is too small: {file_size} bytes")
                await browser.close()
                return None

            logging.info(f"Browser successfully downloaded full text for DOI {doi} to {download_path} (Size: {file_size} bytes)")
            await browser.close()
            return download_path

    except PlaywrightTimeoutError as e:
        logging.error(f"Browser timeout error downloading for DOI {doi}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected browser error downloading for DOI {doi}: {e}")
        return None
    finally:
        if 'browser' in locals():
            await browser.close()