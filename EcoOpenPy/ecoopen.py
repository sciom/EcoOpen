import os
import yaml
import pandas as pd
import requests
import pdfplumber
import spacy
from typing import List, Dict, Optional
from tqdm import tqdm
from urllib.parse import quote
import re

class EcoOpen:
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize EcoOpen with configuration."""
        self.config = self._load_config(config_path)
        self.download_dir = self.config.get("download_dir", "downloads")
        self.batch_size = self.config.get("batch_size", 25)
        self.api_configs = self.config.get("apis", {})
        self.nlp_patterns = self.config.get("nlp_patterns", {})
        self.nlp = spacy.load("en_core_web_sm")
        os.makedirs(self.download_dir, exist_ok=True)
        self.results = []

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file."""
        default_config = {
            "download_dir": "downloads",
            "batch_size": 25,
            "apis": {
                "openalex": {"base_url": "https://api.openalex.org/works"},
                "unpaywall": {"base_url": "https://api.unpaywall.org/v2", "email": "your-email@example.com"},
                "crossref": {"base_url": "https://api.crossref.org/works"},
                "core": {"base_url": "https://api.core.ac.uk/v3"},
                "pubmed": {"base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"}
            },
            "nlp_patterns": {
                "data_availability": [
                    r"Data available at (https?://[^\s]+)",
                    r"Dataset is deposited in (Zenodo|Dryad|Figshare|PANGAEA) at (https?://[^\s]+)",
                    r"Data can be accessed via (https?://[^\s]+)",
                    r"All data are available on (Zenodo|Dryad|Figshare|PANGAEA) \((https?://[^\s]+)\)",
                    r"Supplementary data available at (https?://[^\s]+)"
                ],
                "code_availability": [
                    r"Code is available on GitHub at (https?://[^\s]+)",
                    r"Scripts are deposited in (Zenodo|GitHub) \((https?://[^\s]+)\)",
                    r"Software available at (https?://[^\s]+)",
                    r"Analysis code can be found at (https?://[^\s]+)"
                ],
                "licenses": [
                    r"CC-BY", r"CC0", r"MIT", r"GPL"
                ]
            },
            "repositories": ["Zenodo", "Dryad", "Figshare", "GitHub", "PANGAEA"]
        }
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
            default_config.update(user_config)
        return default_config

    def process_dois(self, dois: List[str]) -> pd.DataFrame:
        """Process a list of DOIs and return a DataFrame with results."""
        self.results = []
        batches = [dois[i:i + self.batch_size] for i in range(0, len(dois), self.batch_size)]

        for batch in tqdm(batches, desc="Processing DOI batches"):
            for doi in batch:
                result = self._process_single_doi(doi)
                self.results.append(result)
        
        return pd.DataFrame(self.results)

    def _process_single_doi(self, doi: str) -> Dict:
        """Process a single DOI and return metadata."""
        result = {
            "doi": doi,
            "title": None,
            "authors": None,
            "published": None,
            "url": None,
            "journal": None,
            "has_fulltext": False,
            "is_oa": False,
            "downloaded": False,
            "path": None,
            "data_links": [],
            "data_availability_statements": None,
            "code_availability_statements": None,
            "format": None,
            "repository": None,
            "repository_url": None,
            "download_status": False,
            "data_download_path": None,
            "data_size": None,
            "number_of_files": 0,
            "license": None
        }

        # Query OpenAlex
        metadata = self._query_openalex(doi)
        if metadata:
            result.update({
                "title": metadata.get("title"),
                "authors": metadata.get("authors"),
                "published": metadata.get("published"),
                "url": metadata.get("url"),
                "journal": metadata.get("journal"),
                "is_oa": metadata.get("is_oa", False),
                "has_fulltext": bool(metadata.get("fulltext_url"))
            })

        # Query Unpaywall for better OA detection
        unpaywall_data = self._query_unpaywall(doi)
        if unpaywall_data:
            result["is_oa"] = unpaywall_data.get("is_oa", result["is_oa"])
            result["has_fulltext"] = bool(unpaywall_data.get("fulltext_url")) or result["has_fulltext"]
            result["url"] = unpaywall_data.get("url", result["url"])
            metadata["fulltext_url"] = unpaywall_data.get("fulltext_url", metadata.get("fulltext_url"))

        # Download full text if available
        if result["has_fulltext"] and metadata.get("fulltext_url"):
            download_path = self._download_fulltext(doi, metadata["fulltext_url"])
            if download_path:
                result["downloaded"] = True
                result["path"] = download_path
                # Extract data/code availability statements
                statements = self._extract_statements(download_path)
                result["data_availability_statements"] = statements.get("data_statements")
                result["code_availability_statements"] = statements.get("code_statements")
                result["data_links"] = statements.get("data_links", [])

        return result

    def _query_openalex(self, doi: str) -> Optional[Dict]:
        """Query OpenAlex API for metadata."""
        try:
            url = f"{self.api_configs['openalex']['base_url']}/doi/{doi}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return {
                "title": data.get("title"),
                "authors": ", ".join([author["author"]["display_name"] for author in data.get("authorships", [])]),
                "published": data.get("publication_date"),
                "url": data.get("primary_location", {}).get("landing_page_url"),
                "journal": data.get("primary_location", {}).get("source", {}).get("display_name"),
                "is_oa": data.get("open_access", {}).get("is_oa", False),
                "fulltext_url": data.get("open_access", {}).get("oa_url")
            }
        except requests.RequestException as e:
            print(f"Error querying OpenAlex for DOI {doi}: {e}")
            return None

    def _query_unpaywall(self, doi: str) -> Optional[Dict]:
        """Query Unpaywall API for open-access status and full-text URL."""
        try:
            email = self.api_configs["unpaywall"].get("email")
            url = f"{self.api_configs['unpaywall']['base_url']}/{quote(doi)}?email={email}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            best_oa = data.get("best_oa_location", {})
            return {
                "is_oa": data.get("is_oa", False),
                "fulltext_url": best_oa.get("url_for_pdf") if best_oa else None,
                "url": best_oa.get("url") if best_oa else None
            }
        except requests.RequestException as e:
            print(f"Error querying Unpaywall for DOI {doi}: {e}")
            return None

    def _download_fulltext(self, doi: str, url: str) -> Optional[str]:
        """Download full-text PDF and store by DOI."""
        try:
            safe_doi = quote(doi, safe="")
            download_path = os.path.join(self.download_dir, safe_doi, "paper.pdf")
            os.makedirs(os.path.dirname(download_path), exist_ok=True)
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(download_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return download_path
        except requests.RequestException as e:
            print(f"Error downloading full text for DOI {doi}: {e}")
            return None

    def _extract_statements(self, pdf_path: str) -> Dict:
        """Extract data/code availability statements and links from PDF."""
        try:
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
            
            data_statements = []
            code_statements = []
            data_links = []
            
            # Apply NLP patterns
            for pattern in self.nlp_patterns["data_availability"]:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        statement, url = match
                        data_statements.append(statement)
                        data_links.append(url)
                    else:
                        data_statements.append(match)
                        if "http" in match:
                            data_links.append(match)
            
            for pattern in self.nlp_patterns["code_availability"]:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        statement, url = match
                        code_statements.append(statement)
                        data_links.append(url)
                    else:
                        code_statements.append(match)
                        if "http" in match:
                            data_links.append(match)
            
            return {
                "data_statements": "; ".join(data_statements) if data_statements else None,
                "code_statements": "; ".join(code_statements) if code_statements else None,
                "data_links": data_links
            }
        except Exception as e:
            print(f"Error extracting statements from {pdf_path}: {e}")
            return {"data_statements": None, "code_statements": None, "data_links": []}

# Example usage
if __name__ == "__main__":
    # Sample DOIs (open-access ecological papers)
    sample_dois = [
        "10.1038/s41597-019-0344-7",  # Example from Nature Scientific Data
        "10.1002/ecy.2439"             # Example from Ecology
    ]
    eco = EcoOpen()
    df = eco.process_dois(sample_dois)
    df.to_csv("ecoopen_results_updated.csv", index=False)
    print(df)