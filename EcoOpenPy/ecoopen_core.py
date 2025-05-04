import os
import yaml
import pandas as pd
from typing import List, Dict, Optional
from tqdm import tqdm
from spacy.matcher import Matcher
import asyncio
import aiohttp
import logging

try:
    import spacy
    SPACY_NLP = spacy.load("en_core_web_sm")
    HAS_SPACY = True
except (ImportError, OSError):
    HAS_SPACY = False
    print("Warning: spaCy or model 'en_core_web_sm' not found. Falling back to regex-based NLP.")

# Configure logging with more detail
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class EcoOpen:
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize EcoOpen with configuration."""
        logging.debug("Initializing EcoOpen")
        self.config = self._load_config(config_path)
        self.download_dir = self.config.get("download_dir", "downloads")
        self.batch_size = self.config.get("batch_size", 10)
        self.api_configs = self.config.get("apis", {})
        self.nlp_patterns = self.config.get("nlp_patterns", {})
        self.nlp = SPACY_NLP if HAS_SPACY else None
        self.matcher = self._setup_nlp_matcher() if HAS_SPACY else None
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(os.path.join(self.download_dir, "debug"), exist_ok=True)
        self.results = []

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file with deep merge."""
        logging.debug(f"Loading config from {config_path}")
        default_config = {
            "download_dir": "downloads",
            "batch_size": 10,
            "apis": {
                "openalex": {"base_url": "https://api.openalex.org/works", "rate_limit": 10, "max_retries": 3, "initial_delay": 1},
                "unpaywall": {"base_url": "https://api.unpaywall.org/v2", "email": "your-email@example.com", "rate_limit": 10, "max_retries": 3, "initial_delay": 1},
                "crossref": {"base_url": "https://api.crossref.org/works", "rate_limit": 5, "max_retries": 3, "initial_delay": 1},
                "core": {"base_url": "https://api.core.ac.uk/v3/works", "rate_limit": 5, "max_retries": 3, "initial_delay": 1},
                "pubmed": {"base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils", "rate_limit": 3, "max_retries": 3, "initial_delay": 1},
                "elsevier": {"base_url": "https://api.elsevier.com/content/article", "api_key": "your-elsevier-api-key", "rate_limit": 10, "max_retries": 3, "initial_delay": 1}
            },
            "nlp_patterns": {
                "data_availability": [
                    {"pattern": [{"LOWER": "data"}, {"LOWER": "available"}, {"LOWER": "at"}, {"LIKE_URL": True}], "label": "DATA_URL", "regex": r"Data available at (https?://[^\s]+)"},
                    {"pattern": [{"LOWER": "dataset"}, {"LOWER": "is"}, {"LOWER": "deposited"}, {"LOWER": "in"}, {"LOWER": {"IN": ["zenodo", "dryad", "figshare", "pangaea"]}}, {"LOWER": "at"}, {"LIKE_URL": True}], "label": "DATA_URL", "regex": r"Dataset is deposited in (Zenodo|Dryad|Figshare|PANGAEA) at (https?://[^\s]+)"},
                    {"pattern": [{"LOWER": "data"}, {"LOWER": "can"}, {"LOWER": "be"}, {"LOWER": "accessed"}, {"LOWER": "via"}, {"LIKE_URL": True}], "label": "DATA_URL", "regex": r"Data can be accessed via (https?://[^\s]+)"},
                    {"pattern": [{"LOWER": "supplementary"}, {"LOWER": "data"}, {"LOWER": "available"}, {"LOWER": "at"}, {"LIKE_URL": True}], "label": "DATA_URL", "regex": r"Supplementary data available at (https?://[^\s]+)"},
                    {"pattern": [{"LOWER": "data"}, {"LOWER": "are"}, {"LOWER": "available"}, {"LOWER": "in"}, {"LOWER": {"IN": ["zenodo", "dryad", "figshare", "pangaea"]}}, {"LOWER": {"IN": ["under", "at"]}}, {"LIKE_URL": True}], "label": "DATA_URL", "regex": r"Data are available in (Zenodo|Dryad|Figshare|PANGAEA) (?:under|at) (https?://[^\s]+)"},
                    {"pattern": [{"LOWER": "dataset"}, {"LOWER": "available"}, {"LOWER": "on"}, {"LOWER": {"IN": ["zenodo", "dryad", "figshare", "pangaea"]}}, {"LIKE_URL": True}], "label": "DATA_URL", "regex": r"Dataset available on (Zenodo|Dryad|Figshare|PANGAEA) (https?://[^\s]+)"},
                    {"pattern": [{"LOWER": "data"}, {"LOWER": "deposited"}, {"LOWER": "at"}, {"LOWER": {"IN": ["doi", "record"]}}, {"LIKE_URL": True}], "label": "DATA_URL", "regex": r"Data deposited at (?:DOI|record):?\s*(https?://[^\s]+)"},
                    {"pattern": [{"LOWER": "available"}, {"LOWER": "in"}, {"LOWER": {"IN": ["repository", "database"]}}, {"LOWER": {"IN": ["zenodo", "dryad", "figshare", "pangaea"]}}, {"LIKE_URL": True}], "label": "DATA_URL", "regex": r"Available in (?:repository|database) (Zenodo|Dryad|Figshare|PANGAEA) (https?://[^\s]+)"},
                    {"pattern": [{"LOWER": "data"}, {"LOWER": "hosted"}, {"LOWER": "at"}, {"LOWER": {"IN": ["zenodo", "dryad", "figshare", "pangaea"]}}, {"LIKE_URL": True}], "label": "DATA_URL", "regex": r"Data hosted at (Zenodo|Dryad|Figshare|PANGAEA) (https?://[^\s]+)"},
                    {"pattern": [{"LOWER": "data"}, {"LOWER": "available"}, {"LOWER": "upon"}, {"LOWER": "request"}], "label": "DATA_REQUEST", "regex": r"Data available upon request"},
                    {"pattern": [{"LOWER": "data"}, {"LOWER": "archived"}, {"LOWER": "at"}, {"LIKE_URL": True}], "label": "DATA_URL", "regex": r"Data archived at (https?://[^\s]+)"}
                ],
                "code_availability": [
                    {"pattern": [{"LOWER": "code"}, {"LOWER": "is"}, {"LOWER": "available"}, {"LOWER": "on"}, {"LOWER": "github"}, {"LOWER": "at"}, {"LIKE_URL": True}], "label": "CODE_URL", "regex": r"Code is available on GitHub at (https?://[^\s]+)"},
                    {"pattern": [{"LOWER": "scripts"}, {"LOWER": "are"}, {"LOWER": "deposited"}, {"LOWER": "in"}, {"LOWER": {"IN": ["zenodo", "github"]}}, {"LOWER": "at"}, {"LIKE_URL": True}], "label": "CODE_URL", "regex": r"Scripts are deposited in (Zenodo|GitHub) \((https?://[^\s]+)\)"},
                    {"pattern": [{"LOWER": "analysis"}, {"LOWER": "code"}, {"LOWER": "can"}, {"LOWER": "be"}, {"LOWER": "found"}, {"LOWER": "at"}, {"LIKE_URL": True}], "label": "CODE_URL", "regex": r"Analysis code can be found at (https?://[^\s]+)"},
                    {"pattern": [{"LOWER": "code"}, {"LOWER": "available"}, {"LOWER": "at"}, {"LIKE_URL": True}], "label": "CODE_URL", "regex": r"Code available at (https?://[^\s]+)"},
                    {"pattern": [{"LOWER": "software"}, {"LOWER": "available"}, {"LOWER": "on"}, {"LOWER": "github"}, {"LIKE_URL": True}], "label": "CODE_URL", "regex": r"Software available on GitHub (https?://[^\s]+)"}
                ],
                "licenses": ["CC-BY", "CC0", "MIT", "GPL", "CC-BY-SA", "CC-BY-NC", "CC-BY-ND", "Apache-2.0"]
            },
            "repositories": ["Zenodo", "Dryad", "Figshare", "GitHub", "PANGAEA"]
        }
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f) or {}
            merged_config = default_config.copy()
            for key, value in user_config.items():
                if key in merged_config and isinstance(value, dict) and isinstance(merged_config[key], dict):
                    merged_config[key] = {**merged_config[key], **value}
                else:
                    merged_config[key] = value
            if "elsevier" in merged_config["apis"] and "base_url" not in merged_config["apis"]["elsevier"]:
                merged_config["apis"]["elsevier"]["base_url"] = "https://api.elsevier.com/content/article"
            return merged_config
        return default_config

    def _setup_nlp_matcher(self) -> Matcher:
        """Set up spaCy Matcher for NLP patterns."""
        logging.debug("Setting up NLP matcher")
        matcher = Matcher(self.nlp.vocab)
        for pattern in self.nlp_patterns["data_availability"]:
            matcher.add(pattern["label"], [pattern["pattern"]])
        for pattern in self.nlp_patterns["code_availability"]:
            matcher.add(pattern["label"], [pattern["pattern"]])
        return matcher

    async def process_dois(self, dois: List[str]) -> pd.DataFrame:
        """Process a list of DOIs asynchronously and return a DataFrame with results."""
        logging.debug(f"Processing {len(dois)} DOIs")
        try:
            from ecoopen_download_nlp import extract_statements, download_datasets
            from ecoopen_download_manager import manage_download
            logging.debug("Successfully imported extract_statements and download_datasets from ecoopen_download_nlp")
        except ImportError as e:
            logging.error(f"Failed to import from ecoopen_download_nlp: {e}")
            raise

        self.results = []
        batches = [dois[i:i + self.batch_size] for i in range(0, len(dois), self.batch_size)]
        semaphore = asyncio.Semaphore(5)  # Limit concurrent downloads to 5

        async with aiohttp.ClientSession() as session:
            for batch in tqdm(batches, desc="Processing DOI batches"):
                logging.debug(f"Processing batch of {len(batch)} DOIs")
                tasks = [self._process_single_doi(doi, session, semaphore) for doi in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in batch_results:
                    if isinstance(result, dict):
                        self.results.append(result)
                    elif isinstance(result, Exception):
                        logging.error(f"Error processing DOI in batch: {str(result)}")
                await asyncio.sleep(1)  # Delay between batches

        logging.debug(f"Processed {len(self.results)} results")
        return pd.DataFrame(self.results)

    async def _process_single_doi(self, doi: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore) -> Dict:
        """Process a single DOI and return metadata."""
        logging.debug(f"Processing DOI {doi}")
        from ecoopen_api import query_unpaywall, query_openalex, query_crossref, query_core, query_pubmed, query_elsevier
        from ecoopen_download_nlp import extract_statements, download_datasets
        from ecoopen_download_manager import manage_download

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

        metadata = None
        unpaywall_data = None
        fulltext_sources = []

        # Step 1: Query Unpaywall for OA status and full-text URL
        if "unpaywall" in self.api_configs:
            max_retries = self.api_configs["unpaywall"].get("max_retries", 3)
            initial_delay = self.api_configs["unpaywall"].get("initial_delay", 1)
            retry_count = 0
            while retry_count < max_retries:
                try:
                    unpaywall_data = await query_unpaywall(doi, self.api_configs, session)
                    if unpaywall_data:
                        result["is_oa"] = unpaywall_data.get("is_oa", False)
                        result["has_fulltext"] = bool(unpaywall_data.get("fulltext_url"))
                        result["url"] = unpaywall_data.get("url", result["url"])
                        if unpaywall_data.get("fulltext_url"):
                            fulltext_sources.append(("Unpaywall", unpaywall_data["fulltext_url"]))
                            logging.debug(f"Unpaywall found full-text URL for DOI {doi}: {unpaywall_data['fulltext_url']}")
                    break
                except aiohttp.ClientResponseError as e:
                    if e.status == 429:
                        retry_count += 1
                        delay = initial_delay * (2 ** retry_count) + random.uniform(0, 1)
                        logging.warning(f"Rate limit hit for Unpaywall on DOI {doi}, retrying ({retry_count}/{max_retries}) after {delay:.2f}s")
                        await asyncio.sleep(delay)
                    else:
                        logging.error(f"Error querying Unpaywall for DOI {doi}: {e}")
                        break
                except Exception as e:
                    logging.error(f"Unexpected error querying Unpaywall for DOI {doi}: {e}")
                    break
        else:
            logging.warning(f"Unpaywall configuration missing for DOI {doi}")

        # Step 2: Query other APIs for metadata
        api_attempts = [("OpenAlex", query_openalex), ("CrossRef", query_crossref), ("CORE", query_core), ("PubMed", query_pubmed)]
        for api_name, query_func in api_attempts:
            if metadata:
                break
            max_retries = self.api_configs.get(api_name.lower(), {}).get("max_retries", 3)
            initial_delay = self.api_configs.get(api_name.lower(), {}).get("initial_delay", 1)
            retry_count = 0
            while retry_count < max_retries:
                try:
                    metadata = await query_func(doi, self.api_configs, session)
                    if metadata:
                        result.update({
                            "title": metadata.get("title"),
                            "authors": metadata.get("authors"),
                            "published": metadata.get("published"),
                            "url": metadata.get("url", result["url"]),
                            "journal": metadata.get("journal"),
                            "is_oa": metadata.get("is_oa", result["is_oa"]),
                            "has_fulltext": bool(metadata.get("fulltext_url")) or result["has_fulltext"],
                            "license": metadata.get("license")
                        })
                        if metadata.get("fulltext_url"):
                            fulltext_sources.append((metadata.get("source", api_name), metadata["fulltext_url"]))
                            logging.debug(f"{api_name} found full-text URL for DOI {doi}: {metadata['fulltext_url']}")
                        logging.info(f"Successfully retrieved metadata for DOI {doi} using {api_name}")
                        break
                    else:
                        logging.warning(f"No metadata retrieved for DOI {doi} using {api_name}")
                        break
                except aiohttp.ClientResponseError as e:
                    if e.status == 429:
                        retry_count += 1
                        delay = initial_delay * (2 ** retry_count) + random.uniform(0, 1)
                        logging.warning(f"Rate limit hit for {api_name} on DOI {doi}, retrying ({retry_count}/{max_retries}) after {delay:.2f}s")
                        await asyncio.sleep(delay)
                    else:
                        logging.error(f"Error querying {api_name} for DOI {doi}: {e}")
                        break
                except Exception as e:
                    logging.error(f"Unexpected error querying {api_name} for DOI {doi}: {e}")
                    break
            if not metadata:
                logging.warning(f"Failed to retrieve metadata for DOI {doi} using {api_name} after {retry_count} retries")

        # If metadata is still None, set basic metadata
        if not metadata:
            metadata = {
                "title": "Unknown",
                "authors": "Unknown",
                "published": "Unknown",
                "url": result["url"],
                "journal": "Unknown",
                "is_oa": result["is_oa"],
                "fulltext_url": fulltext_sources[0][1] if fulltext_sources else None,
                "source": "Unpaywall" if fulltext_sources else "Unknown"
            }
            result.update({
                "title": metadata["title"],
                "authors": metadata["authors"],
                "published": metadata["published"],
                "url": metadata["url"],
                "journal": metadata["journal"],
                "is_oa": metadata["is_oa"],
                "has_fulltext": bool(metadata["fulltext_url"])
            })
            logging.debug(f"Set basic metadata for DOI {doi}: {result}")

        # Step 3: Download full text using multiple sources
        if metadata:
            logging.debug(f"Starting download attempts for DOI {doi} with {len(fulltext_sources)} sources: {fulltext_sources}")
            # Elsevier (only for downloading, if DOI starts with 10.1016)
            if doi.startswith("10.1016") and "elsevier" in self.api_configs:
                max_retries = self.api_configs["elsevier"].get("max_retries", 3)
                initial_delay = self.api_configs["elsevier"].get("initial_delay", 1)
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        elsevier_data = await query_elsevier(doi, self.api_configs, session)
                        if elsevier_data and elsevier_data.get("fulltext_url"):
                            fulltext_sources.append(("Elsevier", elsevier_data["fulltext_url"]))
                            logging.debug(f"Elsevier found full-text URL for DOI {doi}: {elsevier_data['fulltext_url']}")
                        break
                    except aiohttp.ClientResponseError as e:
                        if e.status == 429:
                            retry_count += 1
                            delay = initial_delay * (2 ** retry_count) + random.uniform(0, 1)
                            logging.warning(f"Rate limit hit for Elsevier on DOI {doi}, retrying ({retry_count}/{max_retries}) after {delay:.2f}s")
                            await asyncio.sleep(delay)
                        elif e.status == 401:
                            logging.error(f"Elsevier API unauthorized for DOI {doi}: {e}. Skipping further retries.")
                            break
                        else:
                            logging.error(f"Error querying Elsevier for DOI {doi}: {e}")
                            break
                    except Exception as e:
                        logging.error(f"Unexpected error querying Elsevier for DOI {doi}: {e}")
                        break

            for source_name, fulltext_url in fulltext_sources:
                if result["downloaded"]:
                    break
                logging.debug(f"Attempting download for DOI {doi} from {source_name} with URL {fulltext_url}")
                safe_doi = doi.replace('/', '_')
                download_path = await manage_download(safe_doi, fulltext_url, self.download_dir, session, self.api_configs, semaphore)
                if download_path:
                    result["downloaded"] = True
                    result["path"] = download_path
                    logging.debug(f"Successfully downloaded for DOI {doi}, now extracting statements")
                    statements = extract_statements(download_path, self.nlp, self.matcher, self.nlp_patterns, HAS_SPACY, self.download_dir)
                    result["data_availability_statements"] = statements.get("data_statements")
                    result["code_availability_statements"] = statements.get("code_statements")
                    result["data_links"] = statements.get("data_links", [])
                    text_license = statements.get("license")
                    if result["data_links"]:
                        download_results = await download_datasets(safe_doi, result["data_links"], self.download_dir, self.api_configs, session)
                        result.update(download_results)
                        if download_results.get("license"):
                            result["license"] = download_results["license"]
                        elif text_license and not result["license"]:
                            result["license"] = text_license
                    elif text_license and not result["license"]:
                        result["license"] = text_license
                else:
                    logging.warning(f"Failed to download full text for DOI {doi} from {source_name}")
            if not result["downloaded"]:
                logging.info(f"No full text downloaded for DOI {doi} after trying all sources")

        logging.debug(f"Finished processing DOI {doi}: {result}")
        return result