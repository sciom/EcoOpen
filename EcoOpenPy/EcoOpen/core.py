from habanero import Crossref
import numpy as np
import re
from tqdm import tqdm
import pandas as pd
import itertools
from pathlib import Path
import sys
import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urlparse, urljoin
from urllib.request import urlretrieve
from urllib.error import HTTPError
from requests.exceptions import HTTPError, RequestException
import urllib
import pathlib
from time import sleep
import pdfplumber
from pprint import pprint
from datetime import datetime
import concurrent.futures

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from EcoOpen.utils.keywords import keywords
from EcoOpen.data_download import *
from pyalex import Works, Authors
from itertools import chain

from requests_html import HTMLSession

import requests
import pandas as pd
from requests.exceptions import HTTPError, RequestException
from http.cookiejar import CookieJar

from EcoOpen.paper_download import *
import pdf2doi

# Add biological databases to keywords (assuming keywords.py is editable)
bio_databases = [
    "genbank", "ncbi", "pdb", "uniprot", "ensembl", "dryad", "geo",
    "ebi.ac.uk", "datadryad.org", "pangaea.de", "figshare.com", "osf.io"
]
keywords["repositories"] = keywords["repositories"] + bio_databases

def get_date_string(published):
    return "-".join([str(i) for i in published])

def FindPapers(query="", doi="", author="", number_of_papers=200,
               sort="relevance", order="desc", start_year=2010,
               end_year=datetime.now().year, only_oa=False, callback=None):
    dataframe = {
        "doi": [],
        "title": [],
        "authors": [],
        "published": [],
        "url": [],
        "journal": [],
        "has_fulltext": [],
        "is_oa": []
    }
    
    if query != "":
        search = Works().search(query)
    if doi != "" and type(doi) == str:
        if "doi.org/" not in doi:
            doi = "https://doi.org/" + doi
        elif "https://" not in doi:
            doi = "https://" + doi
        search = Works().filter(doi=doi, is_paratext=False)
    elif doi != "" and type(doi) == list:
        print("Multiple DOIs detected, searching for each DOI")
        for d in tqdm(doi):
            if "doi.org/" not in d:
                d = "https://doi.org/" + d
            elif "https://" not in d:
                d = "https://" + d
            search = Works().filter(doi=d, is_paratext=False).get()
            for i in search:
                dataframe = fill_dataframe(i, dataframe)
        df = pd.DataFrame(dataframe)
        if sort == "published":
            df = df.sort_values(by="published", ascending=False, ignore_index=True)
        return df

    if author != "":
        search = Authors().search(author)
        authors = search.get()
        if len(authors) > 1:
            id_ = authors[0]["id"]
            search = Works().filter(author={"id": id_})
        else:
            raise ValueError("Author not found")
    
    filtered_search = search.filter(has_doi=True)
    if only_oa:
        print("Searching only for open access articles")
        filtered_search = filtered_search.filter(is_oa=True)
    filtered_search = filtered_search.filter(
        from_publication_date=str(start_year) + "-01-01",
        to_publication_date=str(end_year) + "-12-31",
        type="article")
    count = filtered_search.count()

    if count > 200 and count < 2000:
        pager = filtered_search.paginate(per_page=200)
        for i in tqdm(chain(*pager)):
            dataframe = fill_dataframe(i, dataframe)
    elif count > 2000:
        print(f"# EcoOpen Warning: Please narrow down the search.")
        print(f"Too many articles found ({count}) with the following query:\n")
        print(f'"{query}"')
        print("Only the first 2000 articles will be processed.\n")
        pager = filtered_search.paginate(per_page=200, n_max=2000)
        for i in chain(*pager):
            dataframe = fill_dataframe(i, dataframe)  
    else:
        for i in filtered_search.get():
            dataframe = fill_dataframe(i, dataframe)
    df = pd.DataFrame(dataframe)
    if sort == "published":
        df = df.sort_values(by="published", ascending=False, ignore_index=True)
    
    print(f"Found {len(df)} articles")
    return df

def fill_dataframe(paper, dataframe):
    try:
        dataframe["doi"].append(paper["doi"])
    except KeyError:
        dataframe["doi"].append("")
    try:
        dataframe["title"].append(paper["title"])
    except KeyError:
        dataframe["title"].append("")
    try:
        authors = paper["authorships"]
        authors_list = [author["author"]["display_name"] for author in authors]
        dataframe["authors"].append(", ".join(authors_list))
    except KeyError:
        dataframe["authors"].append("")
    try:
        dataframe["published"].append(paper["publication_date"])
    except KeyError:
        dataframe["published"].append("")
    try:
        if paper["primary_location"]["pdf_url"] is None:
            dataframe["url"].append("")
        else:
            dataframe["url"].append(paper["primary_location"]["pdf_url"])
    except KeyError:
        dataframe["url"].append("")
    try:
        dataframe["journal"].append(paper["primary_location"]["source"]["display_name"] if paper["primary_location"]["source"] else "")
    except KeyError:
        dataframe["journal"].append("")
    try:
        dataframe["has_fulltext"].append(paper["has_fulltext"])
    except KeyError:
        dataframe["has_fulltext"].append("")
    try:
        dataframe["is_oa"].append(paper["open_access"]["is_oa"])
    except KeyError:
        dataframe["is_oa"].append("")
    return dataframe

def custom_tokenizer(text):
    pattern = r"(?u)\b\w\w+\b[!]*"
    return re.findall(pattern, text) 

def clean_title(title):
    title = "".join([i if i.isalnum() else "_" for i in title])
    return title

def find_das(sentences):
    das_keywords = keywords["data_availability"]
    return [sentence for sentence in sentences if any(kw.lower() in sentence.lower() for kw in das_keywords)]

def find_code_availability(sentences):
    code_keywords = ["code", "software", "github", "gitlab", "bitbucket", "repository", "available at", "source code"]
    return [sentence for sentence in sentences if any(kw.lower() in sentence.lower() for kw in code_keywords)]

def find_keywords(sentences):
    detected = []
    kw = keywords.copy()
    kw.pop("data_availability", None)
    for k in kw.keys():
        kk = kw[k]
        for sentence in sentences:
            if any(kw.lower() in sentence.lower() for kw in kk):
                detected.append(sentence)
    return detected

def clean_url(url, base_url=None):
    """Clean and validate a URL, handling relative URLs and malformed ones."""
    url = url.strip('.,;()[]{}"\'')  # Remove common trailing/leading punctuation
    if not url.startswith(('http://', 'https://')) and base_url:
        url = urljoin(base_url, url)  # Convert relative URLs to absolute
    if validators.url(url):  # Check if it's a valid URL
        return url
    return None

def find_dataKW(pdf_path, timeout=30):
    try:
        raw = ReadPDF(pdf_path)
        if not raw:
            return [], [], []
        base_url = None  # We'll infer this later if needed
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', raw)
        das_sentences = find_das(sentences)
        code_sentences = find_code_availability(sentences)
        keyword_sentences = find_keywords(sentences)

        data_links = []
        for sentence in das_sentences + keyword_sentences + code_sentences:
            # Enhanced link detection with bio databases in mind
            links = re.findall(r'(https?://[^\s()[\]{}]+|doi\.org/[^\s()[\]{}]+|ncbi\.nlm\.nih\.gov/[^\s()[\]{}]+|ebi\.ac\.uk/[^\s()[\]{}]+)', sentence)
            for link in links:
                cleaned_link = clean_url(link, base_url)
                if cleaned_link and cleaned_link not in data_links:
                    data_links.append(cleaned_link)
        return das_sentences, code_sentences, data_links
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        return [], [], []

def ReadPDFMeta(filepath):
    pdf = pdfplumber.open(filepath)
    return pdf.metadata

def ReadPDF(filepath):
    raw = ""
    try:
        pdf = pdfplumber.open(filepath)
        for page in pdf.pages:
            raw += page.extract_text() or ""
        pdf.close()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return raw

def ReadPDFs(filepaths):
    if isinstance(filepaths, pd.DataFrame):
        filepaths = filepaths["path"].tolist()
    raws = []
    for file in filepaths:
        if isinstance(file, pathlib.PosixPath):
            file = str(file)
        raw = ReadPDF(file)
        raws.append(raw)
    return raws

def findDOI(string):
    return re.findall(r"10.\d{4,9}/[-._;()/:a-zA-Z0-9]+", string, re.IGNORECASE)

def find_doi(path):
    pdf2doi.config.set('verbose', False)
    meta = ReadPDFMeta(path)
    doi = []
    for key in meta.keys():
        doi = findDOI(meta[key])
        if doi:
            doi = doi[0]
            break
    if not doi:
        online_search = pdf2doi.find_identifier(path, "title_google")
        doi = online_search["identifier"] if online_search else ""
    return doi

def find_data_web(doi, retries=3, timeout=5):
    url = f"https://doi.org/{doi}"
    session = HTMLSession()
    data_links = []

    for attempt in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            real_url = r.url
            domain = real_url.split('/')[2]
            soup = BeautifulSoup(r.html.html, 'lxml')

            closed_snippets = ["buy article", "access the full article", "purchase pdf"]
            if any(snippet in str(soup).lower() for snippet in closed_snippets):
                break

            supplementary_snippets = ["supplementary", "supplemental", "additional", "appendix", "download"]
            for link in soup.find_all('a', href=True):
                href = link.get('href').lower()
                if (any(snippet in href for snippet in supplementary_snippets) or 
                    any(repo in href for repo in keywords["repositories"])):
                    full_url = clean_url(href, f"https://{domain}")
                    if full_url and full_url not in data_links:
                        data_links.append(full_url)
            break
        except (requests.RequestException, ValueError) as e:
            if attempt == retries - 1:
                print(f"Failed to scrape {doi} after {retries} attempts: {e}")
            sleep(1)
    return data_links

def validate_link(link):
    try:
        response = requests.head(link, timeout=5, allow_redirects=True)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '').lower()
            return 'text/html' not in content_type or any(db in link for db in bio_databases)
        return False
    except requests.RequestException:
        return False

def infer_data_details(links):
    formats = []
    repositories = []
    repository_urls = []
    for link in links:
        ext = link.split('.')[-1].lower().split('?')[0]
        formats.append(ext if ext in ['csv', 'xlsx', 'zip', 'pdf', 'txt', 'fasta', 'gb'] else 'unknown')
        repo = 'unknown'
        repo_url = link
        for r in keywords["repositories"]:
            if r in link.lower():
                repo = r
                repo_url = link
                break
        repositories.append(repo)
        repository_urls.append(repo_url)
    return formats, repositories, repository_urls

def FindOpenData(files, method="web", max_workers=4, validate_links=True):
    """
    Find open data in scientific papers using keywords or web scraping.
    
    Args:
        files (pd.DataFrame): DataFrame with 'path' (for keywords) and 'doi' (for web) columns.
        method (str): 'keywords' (PDF parsing) or 'web' (web scraping).
        max_workers (int): Number of parallel workers for processing.
        validate_links (bool): Whether to validate detected links.
    
    Returns:
        pd.DataFrame: Updated DataFrame with all requested columns including license.
    """
    print(f"Finding open data using {method} method:")
    data_links = []
    das_sentences = []
    code_sentences = []

    if method == "keywords":
        if "path" not in files.columns:
            raise ValueError("DataFrame must contain 'path' column for keywords method")
        
        def process_pdf(pdf_path):
            das, code, links = find_dataKW(pdf_path)
            valid_links = links if not validate_links else [l for l in links if validate_link(l)]
            return das, code, valid_links

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(tqdm(executor.map(process_pdf, files["path"].tolist()), total=len(files)))
        das_sentences, code_sentences, data_links = zip(*results) if results else ([], [], [])

    elif method == "web":
        if "doi" not in files.columns:
            raise ValueError("DataFrame must contain 'doi' column for web method")
        
        def process_doi(doi):
            links = find_data_web(doi)
            return links if not validate_links else [l for l in links if validate_link(l)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            data_links = list(tqdm(executor.map(process_doi, files["doi"].tolist()), total=len(files)))
        das_sentences = [[] for _ in range(len(files))]
        code_sentences = [[] for _ in range(len(files))]

    else:
        raise ValueError("Method must be 'keywords' or 'web'")

    files["paper_download_status"] = files.get("path", "").apply(lambda x: "downloaded" if x and os.path.exists(x) else "not_downloaded")
    files["journal"] = files.get("journal", "")
    files[f"data_links_{method}"] = data_links
    files["data_availability_statements"] = das_sentences
    files["code_availability_statements"] = code_sentences

    formats_list = []
    repositories_list = []
    repository_urls_list = []
    for links in data_links:
        formats, repos, repo_urls = infer_data_details(links)
        formats_list.append(formats)
        repositories_list.append(repos)
        repository_urls_list.append(repo_urls)
    
    files["format"] = formats_list
    files["repository"] = repositories_list
    files["repository_url"] = repository_urls_list
    files["download_status"] = ["pending" if links else "no_links" for links in data_links]
    files["download_date"] = ["" for _ in range(len(files))]
    files["download_path"] = [[] for _ in range(len(files))]
    files["data_size"] = [[] for _ in range(len(files))]
    files["license"] = ["unknown" for _ in range(len(files))]

    print(f"Processed {len(files)} papers, found data links in {sum(1 for dl in data_links if dl)}")
    return files

def load_papers(paper_dir):
    paper_dir = os.path.expanduser(paper_dir)
    papers_paths = list(Path(paper_dir).glob("*.pdf"))
    doi_list = []
    detected_pdfs = []
    for i in tqdm(papers_paths):
        try:
            doi = find_doi(i)            
        except Exception as e:
            print(e, i)
            continue
        if doi:
            doi_list.append(doi)
            detected_pdfs.append(str(i))
    papers = pd.DataFrame({"doi": doi_list, "path": detected_pdfs})
    papers_searched = FindPapers(doi=doi_list)
    papers_searched = pd.merge(papers, papers_searched, how="right", on="doi")
    return papers_searched

def analyze_reference_document(path):
    result = {
        "doi": [],
        "title": [],
        "authors": [],
        "original_data_present": [],
        "data_links": []
    }
    return result

if __name__ == "__main__":
    papers = pd.DataFrame({
        "doi": ["10.1007/s10886-017-0919-8"],
        "path": ["/home/user/papers/paper.pdf"]
    })
    result = FindOpenData(papers, method="keywords")
    print(result)