import os
import aiohttp
import pdfplumber
import re
import logging
from typing import List, Dict, Optional

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    print("Warning: PyMuPDF not installed. Falling back to pdfplumber-only extraction.")

try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_statements(pdf_path: str, nlp, matcher, nlp_patterns: Dict, has_spacy: bool, download_dir: str) -> Dict:
    """Extract data/code availability statements and links from PDF."""
    try:
        text = ""
        if HAS_PYMUPDF:
            doc = fitz.open(pdf_path)
            for page in doc:
                text += page.get_text("text") + " "
            doc.close()
        if not text.strip():
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if not page_text:
                        page_text = page.extract_text_simple() or ""
                    text += page_text + " "
        
        if not text.strip():
            logging.warning(f"No text extracted from PDF: {pdf_path}")
            return {"data_statements": None, "code_statements": None, "data_links": [], "license": None}
        
        debug_path = os.path.join(download_dir, "debug", f"{os.path.basename(pdf_path)}.txt")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(text)
        
        data_statements = []
        code_statements = []
        data_links = []
        license_found = None
        
        if has_spacy and nlp and matcher:
            doc = nlp(text)
            matches = matcher(doc)
            if not matches:
                logging.info(f"No spaCy matches found in PDF: {pdf_path}")
            for match_id, start, end in matches:
                label = nlp.vocab.strings[match_id]
                span = doc[start:end]
                statement = span.text
                url = None
                for token in span:
                    if token.like_url:
                        url = token.text
                        break
                if label.startswith("DATA"):
                    data_statements.append(statement)
                    if url:
                        data_links.append(url)
                elif label.startswith("CODE"):
                    code_statements.append(statement)
                    if url:
                        data_links.append(url)
        else:
            for pattern in nlp_patterns["data_availability"]:
                matches = re.findall(pattern["regex"], text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        statement, url = match
                        data_statements.append(statement)
                        data_links.append(url)
                    else:
                        data_statements.append(match)
                        if "http" in match:
                            data_links.append(match)
            
            for pattern in nlp_patterns["code_availability"]:
                matches = re.findall(pattern["regex"], text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        statement, url = match
                        code_statements.append(statement)
                        data_links.append(url)
                    else:
                        code_statements.append(match)
                        if "http" in match:
                            data_links.append(url)
        
        for lic in nlp_patterns["licenses"]:
            if re.search(lic, text, re.IGNORECASE):
                license_found = lic
                break
        
        if not data_statements and not code_statements:
            logging.info(f"No data or code statements found in PDF: {pdf_path}")
        
        return {
            "data_statements": "; ".join(data_statements) if data_statements else None,
            "code_statements": "; ".join(code_statements) if code_statements else None,
            "data_links": data_links,
            "license": license_found
        }
    except Exception as e:
        logging.error(f"Error extracting statements from {pdf_path}: {e}")
        return {"data_statements": None, "code_statements": None, "data_links": [], "license": None}

async def download_datasets(doi: str, links: List[str], download_dir: str, api_configs: Dict, session: aiohttp.ClientSession) -> Dict:
    """Download datasets from links and return metadata."""
    safe_doi = doi  # Already sanitized
    data_dir = os.path.join(download_dir, safe_doi, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    download_status = False
    data_download_paths = []
    data_size = 0
    number_of_files = 0
    repository = None
    repository_url = None
    file_format = None
    license = None

    for link in links:
        try:
            if "zenodo.org" in link.lower():
                repo_data = await download_zenodo(link, data_dir, api_configs, session)
            elif "datadryad.org" in link.lower():
                repo_data = await download_dryad(link, data_dir, api_configs, session)
            else:
                repo_data = await download_generic(link, data_dir, session)
            
            if repo_data["success"]:
                download_status = True
                data_download_paths.append(repo_data["path"])
                data_size += repo_data["size"]
                number_of_files += repo_data["count"]
                repository = repo_data.get("repository", repository)
                repository_url = link
                file_format = repo_data.get("format", file_format)
                license = repo_data.get("license", license)
        except Exception as e:
            logging.error(f"Error downloading dataset from {link}: {e}")

    return {
        "download_status": download_status,
        "data_download_path": "; ".join(data_download_paths) if data_download_paths else None,
        "data_size": data_size / (1024 * 1024) if data_size else None,
        "number_of_files": number_of_files,
        "repository": repository,
        "repository_url": repository_url,
        "format": file_format,
        "license": license
    }

async def download_zenodo(link: str, data_dir: str, api_configs: Dict, session: aiohttp.ClientSession) -> Dict:
    """Download dataset from Zenodo API."""
    try:
        if "zenodo" not in api_configs or "base_url" not in api_configs["zenodo"]:
            logging.error("Zenodo API configuration missing")
            return {"success": False}
        record_id = re.search(r"zenodo\.org/record/(\d+)", link)
        if not record_id:
            logging.warning(f"No Zenodo record ID found in link: {link}")
            return {"success": False}
        record_id = record_id.group(1)
        url = f"{api_configs['zenodo']['base_url']}/{record_id}"
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
        
        paths = []
        total_size = 0
        count = 0
        for file in data.get("files", []):
            file_url = file["links"]["self"]
            filename = file["key"]
            file_path = os.path.join(data_dir, filename)
            async with session.get(file_url) as file_response:
                file_response.raise_for_status()
                with open(file_path, "wb") as f:
                    async for chunk in file_response.content.iter_chunked(8192):
                        f.write(chunk)
            total_size += os.path.getsize(file_path)
            paths.append(file_path)
            count += 1
        
        if HAS_MAGIC:
            mime = magic.Magic(mime=True)
            file_format = mime.from_file(paths[0]).split("/")[-1] if paths else None
        else:
            file_format = paths[0].split(".")[-1] if paths and "." in paths[0] else None
        
        license = data.get("metadata", {}).get("license", {}).get("id")
        if license:
            license = license.upper()
            if "CC0" in license:
                license = "CC0"
            elif "CC-BY" in license:
                license = "CC-BY"
            elif "MIT" in license:
                license = "MIT"
            elif "GPL" in license:
                license = "GPL"
            elif "CC-BY-SA" in license:
                license = "CC-BY-SA"
            elif "CC-BY-NC" in license:
                license = "CC-BY-NC"
        
        logging.info(f"Successfully downloaded dataset from Zenodo for link: {link}")
        return {
            "success": True,
            "path": "; ".join(paths),
            "size": total_size,
            "count": count,
            "repository": "Zenodo",
            "format": file_format,
            "license": license
        }
    except (aiohttp.ClientError, OSError) as e:
        logging.error(f"Error downloading from Zenodo: {e}")
        return {"success": False}

async def download_dryad(link: str, data_dir: str, api_configs: Dict, session: aiohttp.ClientSession) -> Dict:
    """Download dataset from Dryad API."""
    try:
        if "dryad" not in api_configs or "base_url" not in api_configs["dryad"]:
            logging.error("Dryad API configuration missing")
            return {"success": False}
        doi_match = re.search(r"datadryad\.org/stash/dataset/doi:([\d.]+)", link)
        if not doi_match:
            logging.warning(f"No Dryad DOI found in link: {link}")
            return {"success": False}
        dryad_doi = doi_match.group(1)
        url = f"{api_configs['dryad']['base_url']}/doi:{dryad_doi}"
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
        
        paths = []
        total_size = 0
        count = 0
        for file in data.get("_embedded", {}).get("stash:files", []):
            file_url = file["_links"]["stash:file-download"]["href"]
            filename = file["path"]
            file_path = os.path.join(data_dir, filename)
            async with session.get(file_url) as file_response:
                file_response.raise_for_status()
                with open(file_path, "wb") as f:
                    async for chunk in file_response.content.iter_chunked(8192):
                        f.write(chunk)
            total_size += os.path.getsize(file_path)
            paths.append(file_path)
            count += 1
        
        if HAS_MAGIC:
            mime = magic.Magic(mime=True)
            file_format = mime.from_file(paths[0]).split("/")[-1] if paths else None
        else:
            file_format = paths[0].split(".")[-1] if paths and "." in paths[0] else None
        
        license = data.get("license", {}).get("name")
        if license:
            license = license.upper()
            if "CC0" in license:
                license = "CC0"
            elif "CC-BY" in license:
                license = "CC-BY"
            elif "MIT" in license:
                license = "MIT"
            elif "GPL" in license:
                license = "GPL"
            elif "CC-BY-SA" in license:
                license = "CC-BY-SA"
            elif "CC-BY-NC" in license:
                license = "CC-BY-NC"
        
        logging.info(f"Successfully downloaded dataset from Dryad for link: {link}")
        return {
            "success": True,
            "path": "; ".join(paths),
            "size": total_size,
            "count": count,
            "repository": "Dryad",
            "format": file_format,
            "license": license
        }
    except (aiohttp.ClientError, OSError) as e:
        logging.error(f"Error downloading from Dryad: {e}")
        return {"success": False}

async def download_generic(link: str, data_dir: str, session: aiohttp.ClientSession) -> Dict:
    """Generic download for non-API repositories."""
    try:
        filename = link.split("/")[-1] or "dataset"
        file_path = os.path.join(data_dir, filename)
        async with session.get(link) as response:
            response.raise_for_status()
            with open(file_path, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
        size = os.path.getsize(file_path)
        if HAS_MAGIC:
            mime = magic.Magic(mime=True)
            file_format = mime.from_file(file_path).split("/")[-1]
        else:
            file_format = filename.split(".")[-1] if "." in filename else None
        logging.info(f"Successfully downloaded generic dataset from link: {link}")
        return {
            "success": True,
            "path": file_path,
            "size": size,
            "count": 1,
            "repository": None,
            "format": file_format,
            "license": None
        }
    except (aiohttp.ClientError, OSError) as e:
        logging.error(f"Error downloading generic dataset: {e}")
        return {"success": False}