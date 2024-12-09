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
from urllib.parse import urlparse
from urllib.request import urlretrieve
from urllib.error import HTTPError
from requests.exceptions import HTTPError, RequestException
import urllib
import pathlib
from time import sleep
import pdfplumber
from pprint import pprint
from tqdm import tqdm
from datetime import datetime

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

def get_date_string(published):
    
    return "-".join([str(i) for i in published])

def FindPapers(query="", doi="", author="", number_of_papers=200,
                         sort="relevance", order="desc", start_year=2010,
                         end_year=datetime.now().year, only_oa=False, callback=None):
    dataframe = {
        "doi":[],
        "title":[],
        "authors":[],
        "published":[],
        "url":[],
        "has_fulltext":[],
        "is_oa":[]
    }
    
    if query != "":
        search = Works().search(query)
    if doi != "" and type(doi) == str:
        if "doi.org/" not in doi:
            doi = "https://doi.org/"+doi
        elif "https://" not in doi:
            doi = "https://"+doi
        search = Works().filter(doi=doi, is_paratext=False)
    elif doi != "" and type(doi) == list:
        print("Multiple DOIs detected, searching for each DOI")
        for d in tqdm(doi):
            if "doi.org/" not in d:
                d = "https://doi.org/"+d
            elif "https://" not in d:
                d = "https://"+d
            search  = Works().filter(doi=d, is_paratext=False).get()
            for i in search:
                dataframe = fill_dataframe(i, dataframe)
        df = pd.DataFrame(dataframe)
        if sort == "published":
            df = df.sort_values(
                by="published", ascending=False, ignore_index=True)
        return df

    if author != "":
        search = Authors().search(author)
        authors = search.get()
        if len(authors) > 1:
            id_ = authors[0]["id"]
            search = Works().filter(author={"id":id_})
        else:
            raise ValueError("Author not found")
    
    filtered_search = search.filter(has_doi=True)
    if only_oa:
        filtered_search = filtered_search.filter(is_oa=True)
    filtered_search = filtered_search.filter(
                from_publication_date=str(start_year)+"-01-01",
                to_publication_date=str(end_year)+"-12-31",
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
        authors =  paper["authorships"]
        authors_list = []
        for author in authors:
            authors_list.append(author["author"]["display_name"])
            
        dataframe["authors"].append(", ".join(authors_list))
    except KeyError:
        dataframe["authors"].append("")
        
    try:
        dataframe["published"].append(paper["publication_date"])
    except KeyError:
        dataframe["published"].append("")
    try:
        if paper["primary_location"]["pdf_url"] == None:
            dataframe["url"].append("")
        else:
            dataframe["url"].append(paper["primary_location"]["pdf_url"])
    except KeyError:
        dataframe["url"].append("")
        
    try:
        dataframe["has_fulltext"].append(paper["has_fulltext"])
    except KeyError:
        dataframe["has_fulltext"].append("")
        
    try:
        dataframe["is_oa"].append(paper["primary_location"]["is_oa"])
    except KeyError:
        dataframe["is_oa"].append("")

    return dataframe

def custom_tokenizer(text):
    pattern = r"(?u)\b\w\w+\b[!]*"
    return re.findall(pattern, text) 

def clean_title(title):
    # remove special characters from the title
    title = "".join([i if i.isalnum() else "_" for i in title])
    return title

def find_das(sentences):
    """Find data availability sentences in the text"""
    das_keywords = keywords["data_availability"]
    das_sentences = [
        sentence for sentence in sentences if any(
            kw.lower() in sentence.lower() for kw in das_keywords)]
    return das_sentences

def find_keywords(sentences):
    """find keywords in sentences"""
    detected = []
    kw = keywords.copy()
    kw.pop("data_availability")
    for k in kw.keys():
        kk = kw[k]
        for sentence in sentences:
            if any(kw.lower() in sentence.lower() for kw in kk):
                detected.append(sentence)
    return detected

def find_dataKW(path):
    """Find data keywords in the text"""
    raw = ReadPDF(path)
    
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', raw)
    # print(sentences, "!!!")
    das_sentences = find_das(sentences)
    keyword_sentences = find_keywords(sentences)

    # detect links in the sentences
    data_links = []
    for sentence in keyword_sentences:
        link = re.findall(r'(https?://\S+)', sentence)
        # print(link)
        if link != []:
            data_links.append(link)
    
    # clean the links
    dl = []
    for i in data_links:
        for j in i:
            # split merged links
            if len(j.split("http")) > 2:
                for k in j.split("http"):
                    if k != "":
                        if ("http"+k) not in dl:
                            dl.append("http"+k)
            else:
                if j not in dl:
                    dl.append(j)
    # clean special non standard url characters
    dl = [i.replace(")", "").replace("]", "").replace("}", "") for i in dl]
    dl = [i.replace("(", "").replace("[", "").replace("{", "") for i in dl]
    dl = [i.replace(";", "").replace(",", "") for i in dl]
    
    dln = []
    for i in dl:
        if "accessed" in i:
            dln.append(i.split("accessed")[0])
        else:
            dln.append(i)
    
    return das_sentences, dln

def ReadPDFMeta(filepath):
    # parse PDF using 
    pdf = pdfplumber.open(filepath)
    
    # print(pdf.metadata)
    return pdf.metadata

def ReadPDF(filepath):
    # parse PDF using 
    raw = ""
    try:
        pdf = pdfplumber.open(filepath)
        for page in pdf.pages:
            raw += page.extract_text()
        pdf.close()
    except Exception as e:
        print(f"Error reading {filepath}", e)
    # print(raw)
    return raw #.replace("\n", "")

def ReadPDFs(filepaths):
    # if filepaths is a dataframe extract filepaths
    if type(filepaths) == pd.core.frame.DataFrame:
        filepaths = filepaths["path"].tolist()
    raws = []
    for file in filepaths:
        if type(file) == pathlib.PosixPath:
            file = str(file)
        raw = ReadPDF(file)
        raws.append(raw)
    return raws

def findDOI(string):
    # Function that detects possible DOI in a given string
    return re.findall(
        r"10.\d{4,9}/[-._;()/:a-zA-Z0-9]+", string, re.IGNORECASE)

def find_doi(path):
    pdf2doi.config.set('verbose',False)
    meta = ReadPDFMeta(path)
    
    doi = []
    for key in meta.keys():
        doi = findDOI(meta[key])
        if doi != []:
            doi = doi[0]
            break
    if doi == []:
        online_search = pdf2doi.find_identifier(path, "title_google")
        doi = online_search["identifier"]
    return doi

def FindOpenData(files, method="web"):
    """Prototype function to find open data in scientific papers"""

    print(f"Finding open data:")
    data_links = []

    if method == "keywords":
        for i in tqdm(files["path"].tolist()):
            try:
                das, dl = find_dataKW(i)
                data_links.append(dl)
            except FileNotFoundError:
                data_links.append([])
    elif method == "web":
        for i in tqdm(files["doi"].tolist()):
            dl = find_data_web(i)
            data_links.append(dl)
    else:
        raise ValueError("Method not recognized, use keywords or web!")

    files["data_links"+f"_{method}"] = data_links

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
    # print(papers)
    papers_searched = FindPapers(doi=doi_list)
    # print(papers_searched)
    papers_searched = pd.merge(papers, papers_searched, how="right", on="doi")
    
    return papers_searched
        
        
        
def analyze_reference_document(path):
    """
    Analyze reference document for data availability
    Used to analyze references in pdf or other text documents
    """

    # reference document analysis routine
    result = {
        "doi":[],
        "title":[],
        "authors":[],
        "original_data_present": [],
        "data_links": []
    }
    return result


if __name__ == "__main__":
    # papers = FindPapers(author="Antica Čulina", sort="published")
    
    links = find_dataKW('/home/domagoj/Documents/papers3/Ying_Song_et_al_2021_Deep_Learning_Enables_Accurate_Diagnosis_of_Novel_Coronavirus__COVID_19__With_C.pdf')
    print(links)