from typing import Dict, Optional
import aiohttp
from urllib.parse import quote
import asyncio
import xml.etree.ElementTree as ET
import logging
import random

async def query_openalex(doi: str, api_configs: Dict, session: aiohttp.ClientSession) -> Optional[Dict]:
    """Query OpenAlex API for metadata with retry logic."""
    if "openalex" not in api_configs or "base_url" not in api_configs["openalex"]:
        logging.error(f"OpenAlex API configuration missing for DOI {doi}")
        return None
    max_retries = api_configs["openalex"].get("max_retries", 3)
    initial_delay = api_configs["openalex"].get("initial_delay", 1)
    retry_count = 0

    while retry_count < max_retries:
        try:
            url = f"{api_configs['openalex']['base_url']}/doi/{doi}"
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                metadata = {
                    "title": data.get("title"),
                    "authors": ", ".join([author["author"]["display_name"] for author in data.get("authorships", [])]),
                    "published": data.get("publication_date"),
                    "url": data.get("primary_location", {}).get("landing_page_url"),
                    "journal": data.get("primary_location", {}).get("source", {}).get("display_name"),
                    "is_oa": data.get("open_access", {}).get("is_oa", False),
                    "fulltext_url": data.get("open_access", {}).get("oa_url"),
                    "source": "OpenAlex"
                }
                if metadata["fulltext_url"]:
                    logging.info(f"OpenAlex provided full-text URL for DOI {doi}: {metadata['fulltext_url']}")
                return metadata
        except aiohttp.ClientResponseError as e:
            if e.status == 429:  # Rate limit
                retry_count += 1
                delay = initial_delay * (2 ** retry_count) + random.uniform(0, 1)
                logging.warning(f"Rate limit hit for OpenAlex on DOI {doi}, retrying ({retry_count}/{max_retries}) after {delay:.2f}s")
                await asyncio.sleep(delay)
            else:
                logging.error(f"Error querying OpenAlex for DOI {doi}: {e}")
                break
        except Exception as e:
            logging.error(f"Unexpected error querying OpenAlex for DOI {doi}: {e}")
            break
    return None

async def query_unpaywall(doi: str, api_configs: Dict, session: aiohttp.ClientSession) -> Optional[Dict]:
    """Query Unpaywall API for open-access status and full-text URL with retry logic."""
    if "unpaywall" not in api_configs or "base_url" not in api_configs["unpaywall"]:
        logging.error(f"Unpaywall API configuration missing for DOI {doi}")
        return None
    max_retries = api_configs["unpaywall"].get("max_retries", 3)
    initial_delay = api_configs["unpaywall"].get("initial_delay", 1)
    retry_count = 0

    while retry_count < max_retries:
        try:
            email = api_configs["unpaywall"].get("email")
            if not email:
                logging.warning(f"Unpaywall email missing in configuration for DOI {doi}")
                return None
            url = f"{api_configs['unpaywall']['base_url']}/{quote(doi)}?email={email}"
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                best_oa = data.get("best_oa_location", {})
                result = {
                    "is_oa": data.get("is_oa", False),
                    "fulltext_url": best_oa.get("url_for_pdf") if best_oa else None,
                    "url": best_oa.get("url") if best_oa else None
                }
                if not result["is_oa"]:
                    logging.info(f"Unpaywall found no open-access version for DOI {doi}")
                if result["fulltext_url"]:
                    logging.info(f"Unpaywall provided full-text URL for DOI {doi}: {result['fulltext_url']}")
                return result
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
    return None

async def query_crossref(doi: str, api_configs: Dict, session: aiohttp.ClientSession) -> Optional[Dict]:
    """Query CrossRef API for metadata with retry logic."""
    if "crossref" not in api_configs or "base_url" not in api_configs["crossref"]:
        logging.error(f"CrossRef API configuration missing for DOI {doi}")
        return None
    max_retries = api_configs["crossref"].get("max_retries", 3)
    initial_delay = api_configs["crossref"].get("initial_delay", 1)
    retry_count = 0

    while retry_count < max_retries:
        try:
            url = f"{api_configs['crossref']['base_url']}/{doi}"
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                item = data.get("message", {})
                authors = ", ".join([f"{author.get('given', '')} {author.get('family', '')}".strip() for author in item.get("author", [])])
                published = item.get("published", {}).get("date-parts", [[None]])[0][0]
                license = None
                for lic in item.get("license", []):
                    if lic.get("URL"):
                        lic_name = lic.get("URL").split("/")[-1].upper()
                        if lic_name in ["CC-BY", "CC0", "MIT", "GPL", "CC-BY-SA", "CC-BY-NC", "CC-BY-ND"]:
                            license = lic_name
                            break
                return {
                    "title": item.get("title", [None])[0],
                    "authors": authors if authors else None,
                    "published": f"{published}-01-01" if published else None,
                    "url": item.get("URL"),
                    "journal": item.get("container-title", [None])[0],
                    "is_oa": False,
                    "fulltext_url": None,
                    "license": license,
                    "source": "CrossRef"
                }
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                retry_count += 1
                delay = initial_delay * (2 ** retry_count) + random.uniform(0, 1)
                logging.warning(f"Rate limit hit for CrossRef on DOI {doi}, retrying ({retry_count}/{max_retries}) after {delay:.2f}s")
                await asyncio.sleep(delay)
            else:
                logging.error(f"Error querying CrossRef for DOI {doi}: {e}")
                break
        except Exception as e:
            logging.error(f"Unexpected error querying CrossRef for DOI {doi}: {e}")
            break
    return None

async def query_core(doi: str, api_configs: Dict, session: aiohttp.ClientSession) -> Optional[Dict]:
    """Query CORE API for metadata and full-text with retry logic."""
    if "core" not in api_configs or "base_url" not in api_configs["core"]:
        logging.error(f"CORE API configuration missing for DOI {doi}")
        return None
    max_retries = api_configs["core"].get("max_retries", 3)
    initial_delay = api_configs["core"].get("initial_delay", 1)
    retry_count = 0

    while retry_count < max_retries:
        try:
            url = f"{api_configs['core']['base_url']}/{doi}"
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                metadata = {
                    "title": data.get("title"),
                    "authors": ", ".join(data.get("authors", [])),
                    "published": data.get("datePublished"),
                    "url": data.get("fullTextUrl"),
                    "journal": data.get("journal"),
                    "is_oa": data.get("isOpenAccess", False),
                    "fulltext_url": data.get("fullTextUrl"),
                    "source": "CORE"
                }
                if metadata["fulltext_url"]:
                    logging.info(f"CORE provided full-text URL for DOI {doi}: {metadata['fulltext_url']}")
                return metadata
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                retry_count += 1
                delay = initial_delay * (2 ** retry_count) + random.uniform(0, 1)
                logging.warning(f"Rate limit hit for CORE on DOI {doi}, retrying ({retry_count}/{max_retries}) after {delay:.2f}s")
                await asyncio.sleep(delay)
            else:
                logging.error(f"Error querying CORE for DOI {doi}: {e}")
                break
        except Exception as e:
            logging.error(f"Unexpected error querying CORE for DOI {doi}: {e}")
            break
    return None

async def query_pubmed(doi: str, api_configs: Dict, session: aiohttp.ClientSession) -> Optional[Dict]:
    """Query PubMed API for metadata and full-text with retry logic."""
    if "pubmed" not in api_configs or "base_url" not in api_configs["pubmed"]:
        logging.error(f"PubMed API configuration missing for DOI {doi}")
        return None
    max_retries = api_configs["pubmed"].get("max_retries", 3)
    initial_delay = api_configs["pubmed"].get("initial_delay", 1)
    retry_count = 0

    while retry_count < max_retries:
        try:
            search_url = f"{api_configs['pubmed']['base_url']}/esearch.fcgi?db=pubmed&term={quote(doi)}[DOI]&retmode=json"
            async with session.get(search_url) as response:
                response.raise_for_status()
                data = await response.json()
                id_list = data.get("esearchresult", {}).get("idlist", [])
                if not id_list:
                    logging.info(f"No PubMed record found for DOI {doi}")
                    return None
                pubmed_id = id_list[0]
            
            fetch_url = f"{api_configs['pubmed']['base_url']}/efetch.fcgi?db=pubmed&id={pubmed_id}&retmode=xml"
            async with session.get(fetch_url) as response:
                response.raise_for_status()
                xml_data = await response.text()
                root = ET.fromstring(xml_data)
                article = root.find(".//Article")
                if not article:
                    return None
                title = article.find("ArticleTitle").text if article.find("ArticleTitle") is not None else None
                authors = ", ".join([f"{author.find('ForeName').text} {author.find('LastName').text}" for author in article.findall(".//Author") if author.find('ForeName') is not None and author.find('LastName') is not None])
                pub_date = article.find(".//PubDate/Year").text if article.find(".//PubDate/Year") is not None else None
                journal = article.find(".//Journal/Title").text if article.find(".//Journal/Title") is not None else None
                pmc_id = root.find(".//ArticleId[@IdType='pmc']").text if root.find(".//ArticleId[@IdType='pmc']") is not None else None
                fulltext_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/" if pmc_id else None
                metadata = {
                    "title": title,
                    "authors": authors,
                    "published": f"{pub_date}-01-01" if pub_date else None,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
                    "journal": journal,
                    "is_oa": bool(pmc_id),
                    "fulltext_url": fulltext_url,
                    "source": "PubMed"
                }
                if metadata["fulltext_url"]:
                    logging.info(f"PubMed provided full-text URL for DOI {doi}: {metadata['fulltext_url']}")
                return metadata
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                retry_count += 1
                delay = initial_delay * (2 ** retry_count) + random.uniform(0, 1)
                logging.warning(f"Rate limit hit for PubMed on DOI {doi}, retrying ({retry_count}/{max_retries}) after {delay:.2f}s")
                await asyncio.sleep(delay)
            else:
                logging.error(f"Error querying PubMed for DOI {doi}: {e}")
                break
        except Exception as e:
            logging.error(f"Unexpected error querying PubMed for DOI {doi}: {e}")
            break
    return None

async def query_elsevier(doi: str, api_configs: Dict, session: aiohttp.ClientSession) -> Optional[Dict]:
    """Query Elsevier ScienceDirect API for metadata and full-text with retry logic."""
    if "elsevier" not in api_configs:
        logging.error(f"Elsevier API configuration section missing for DOI {doi}")
        raise ValueError("Elsevier API configuration section missing")
    if "base_url" not in api_configs["elsevier"]:
        logging.error(f"Elsevier API base_url missing for DOI {doi}")
        raise ValueError("Elsevier API base_url missing")
    if "api_key" not in api_configs["elsevier"] or not api_configs["elsevier"]["api_key"]:
        logging.error(f"Elsevier API key missing or empty for DOI {doi}")
        raise ValueError("Elsevier API configuration or API key missing")
    
    logging.info(f"Using Elsevier API key: {api_configs['elsevier']['api_key']} for DOI {doi}")
    max_retries = api_configs["elsevier"].get("max_retries", 3)
    initial_delay = api_configs["elsevier"].get("initial_delay", 1)
    retry_count = 0

    while retry_count < max_retries:
        try:
            url = f"{api_configs['elsevier']['base_url']}/doi/{doi}?httpAccept=application/json"
            headers = {"X-ELS-APIKey": api_configs["elsevier"]["api_key"]}
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                article = data.get("full-text-retrieval-response", {}).get("coredata", {})
                authors = ", ".join([author.get("givenName", "") + " " + author.get("surname", "") for author in article.get("dc:creator", [])])
                published = article.get("prism:coverDate")
                is_oa = article.get("openaccess", "0") == "1"
                fulltext_url = article.get("link", [{}])[0].get("href") if is_oa else f"{api_configs['elsevier']['base_url']}/doi/{doi}?view=FIRSTPAGE"
                license = None
                if is_oa and "license" in article:
                    lic_name = article["license"].upper()
                    if lic_name in ["CC-BY", "CC0", "CC-BY-SA", "CC-BY-NC", "CC-BY-ND"]:
                        license = lic_name
                metadata = {
                    "title": article.get("dc:title"),
                    "authors": authors,
                    "published": published,
                    "url": article.get("prism:doi"),
                    "journal": article.get("prism:publicationName"),
                    "is_oa": is_oa,
                    "fulltext_url": fulltext_url,
                    "license": license,
                    "source": "Elsevier"
                }
                if metadata["fulltext_url"]:
                    logging.info(f"Elsevier provided full-text URL for DOI {doi}: {metadata['fulltext_url']}")
                return metadata
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
    return None