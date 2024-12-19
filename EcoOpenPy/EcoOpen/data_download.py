# Web scraper looking for data on the web for a certain paper

import pandas as pd
from bs4 import BeautifulSoup
from EcoOpen.utils.keywords import keywords
import os
import requests
from pathlib import Path
from itertools import chain
import urllib3
from requests_html import HTMLSession
from tqdm import tqdm
import asyncio

from requests_html import HTMLSession, AsyncHTMLSession
from EcoOpen.utils.keywords import field_specific_repo, repositories

import validators
from pyDataverse.api import NativeApi, DataAccessApi
from pyDataverse.models import Dataverse

repos = field_specific_repo+repositories

test_urls = [
    'https://link.springer.com/article/10.1007/s10886-017-0919-8',
    "https://link.springer.com/article/10.1007/s10886-018-0942-4",
    "https://doi.org/10.1073/pnas.1211733109",
    "http://dx.doi.org/10.3955/046.091.0105",
    "https://doi.org/10.1016/j.scitotenv.2013.10.121",
    "https://doi.org/10.1111/nph.14333"
    ]

filetypes = [
    "csv", "xlsx", "xls", "txt", "pdf", "zip",
    "tar.gz", "tar", "gz", "json", "docx",
    "doc", "ods", "odt", "pptx", "ppt", "png",
    "jpg", "md", "exe", "tab"]

repositories = keywords["repositories"]

exclude = []
for i in filetypes:
    exclude.append(i.lower()+".")

def find_data_web(doi):
    url = "https://doi.org/" + doi
    s = HTMLSession()
    r = s.get(url)
    real_url = r.url
    domain = real_url.split('/')[2]
    soup = BeautifulSoup(r.html.html, 'lxml')
    supplementary_files = []
    closed_article_snippets = [
        "buy article",
        "access the full article",
        "purchase pdf",
    ]
    
    supplementary_snippets = [
        "supplementary",
        "supplemental",
        "additional",
        "appendix",
        "appendices",
        "suppl_file",
        "download"
    ]
    
    if any(snippet in str(soup).lower() for snippet in closed_article_snippets):
        return supplementary_files
    
    links = soup.find_all('a', href=True)
    for link in links:
        href = link.get('href').lower()
        if any(snippet in href for snippet in supplementary_snippets) or any(repo in href for repo in repos):
            if "http" not in href:
                href = "https://" + domain + href
            supplementary_files.append(href)
    
    return supplementary_files

def download_file(url, output_dir):
    response = requests.get(url)
    filename = url.split('/')[-1]
    if "?" in filename:
        filename = filename.split("?")[0]
    with open(os.path.join(output_dir, filename), 'wb') as f:
        f.write(response.content)


def download_osf_file(url, output_dir, file_name):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    # print(url)
    # print(output_dir)
    # print(file_name)
    try:
        # Send a GET request to the URL
        response = requests.get(url,  headers=headers, stream=True)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Create the output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Define the file path
            file_path = os.path.join(output_dir, file_name)
            
            # Save the content of the response as a file
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            
            # print(f"File downloaded successfully and saved as {file_path}")
            return file_path
        else:
            # print(f"Failed to download file. Status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException:
        return None

def get_data_from_link(link, output_dir="examples/data"):
    print(link, "!!")
    
    # There can be three types of links
    # 1. repository links
    # 2. site link
    # 3. direct download link
        
    #test if output_dir exists
    domain = link.split('/')[2]
    source = domain.replace("www.", "").replace(".", "_")
    for r in repositories:
        if r in link:
            source = r
            break
    output_dir = os.path.expanduser(str(output_dir)+"/"+source)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_dir = os.path.expanduser(output_dir)
    # test if link is direct download link
    
    # if link is not a route to a website download the content
    
    if "accessed" in link:
        new_link = link.split("accessed")[0]
        link = new_link
        
    #print(link)
    if validators.url(link):      
        try:
            s = HTMLSession()
            
            r = s.get(link, timeout=5)
            if r.headers["Content-Type"] != "text/html" or r.headers["Content-Type"] == "application/x-Research-Info-Systems":
                # print(r.headers["Content-Type"])
                filename = ""
                try:
                    if "Content-Disposition" in r.headers:
                        filename = r.headers["Content-Disposition"].split("filename=")[1]
                except KeyError:
                    pass
                except IndexError:
                    pass
                if r.headers["Content-Type"] == "application/x-Research-Info-Systems":
                    filename = "RIS.txt"
                if filename != "":
                    # remove any unwanted characters
                    extension = filename.split(".")[-1]
                    # remove any unwanted characters from extension
                    extension = "."+"".join([i if i.isalnum() else "" for i in extension])
                    filename = "".join([i if i.isalnum() else "_" for i in filename]) + extension
                    with open(os.path.join(output_dir, filename), 'wb') as f:
                        f.write(r.content)
                        return [os.path.join(output_dir, filename)]
        except KeyError:
            pass
        except requests.exceptions.ConnectionError:
            pass
        except requests.exceptions.RequestException as e:
            print(f'RequestException: {e}')
            return []
            
        if "osf.io" in link:
            # print(link.split("/")[-2])
            zip_ = "https://files.osf.io/v1/resources/"+ link.split("/")[-2] +"/providers/osfstorage/?zip="
            fp = download_osf_file(zip_, output_dir, f'{link.split("/")[-2]}.zip')
            return [fp]
        elif "pangaea" in link:
            #print(link, "PANGAEA")
            pangaea_formats = {
                "tab":"?format=textfile",
                "zip":"?format=zip"  
            }
            for f in pangaea_formats:
                # try:
                data_link = link+pangaea_formats[f]
                s = HTMLSession()
                r = s.get(data_link)
                with open(os.path.join(output_dir, f"dataset_pangaea.{f}"), 'wb') as f:
                    f.write(r.content)
                return [os.path.join(output_dir, f"dataset_pangaea.{f}")]
                # except:
                #     pass
        elif "dryad" in link:
            #print(link, "DRYAD")
            doi = link.split("dx.doi.org")[1][1:]
            
            #print(doi)
            
            url_doi = "doi%3A"+doi.replace("/", "%2F")
            
            dryad_download_api = f"https://datadryad.org/api/v2/datasets/{url_doi}/download"
            
            r = requests.get(dryad_download_api)
            with open(os.path.join(output_dir, f"dataset_dryad.zip"), 'wb') as f:
                f.write(r.content)

        elif "figshare" in link:
            #print(link)
            s = HTMLSession()
            r = s.get(link)
            soup = BeautifulSoup(r.html.html, 'html.parser')
            figshare_link = ""
            for link in soup.find_all('a'):
                try:
                    if "ndownloader" in link.get('href'):
                        figshare_link = link.get('href')
                except TypeError:
                    pass
            if figshare_link != "":
                download_file(figshare_link, output_dir)
                return [os.path.join(output_dir, figshare_link.split("/")[-1])]
        elif "dataverse" in link:
            base_url = link.split("/dataset")
            #print(base_url)
            return []
        else:
            try:
                s = HTMLSession()
                r = s.get(link)
                real_url = r.url
                domain = real_url.split('/')[2]
                soup = BeautifulSoup(r.html.html, 'html.parser')
                files = []
                for i in filetypes:
                    filename = ""
                    links = soup.find_all('a')
                    for link in links:
                        try:
                            if "."+i in link.get('href') or "."+i in link.get('title'):
                                l = link.get('href')
                                if "http" not in l:
                                    l = "https://"+domain + l
                                files.append(l)
                        except TypeError:
                            pass
                downloaded_files = []
                for i in files:
                    filename = i.split("/")[-1]
                    if "?" in filename:
                        filename = filename.split("?")[0]
                        
                    if filename != "":
                        if any([i in filename.lower() for i in filetypes]):
                            if filename not in downloaded_files:
                                # print("Downloading", filename)
                                download_file(i, output_dir)
                                downloaded_files.append(filename)
                    else:
                        pass
                        # print("Invalid filename", i)
                return downloaded_files
            except requests.exceptions.RequestException as e:
                #print(f'RequestException: {e}')
                return []
            except Exception as e:
                print(f'Exception: {e}')
    else:
        return []

def delete_empty_folders(root):
    """Function to delete empty folders in a directory tree."""
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        for dirname in dirnames:
            full_path = os.path.join(dirpath, dirname)
            if not os.listdir(full_path): 
                os.rmdir(full_path)

def DownloadData(data_report, output_dir):
    print("")
    print("Attempting to download open data from the web.")
    print("Be advised that due to the nature of different websites, automatic download may not be possible.")
    print("Manual download may be required.")
    print("Please check the output directory for downloaded files.")
    print("")

    data_dirs = []
    number_of_files = []
    formats_s = []
    progress = tqdm(total=len(data_report))
    for idx, row in data_report.iterrows():
        
        data_amount = 0
        data_dir = ""
        links = []
        for i in ["data_links_keywords", "data_links_web"]:
            try:
                links += eval(row[i]) if isinstance(row[i], str) else row[i]
            except KeyError:
                pass
            except TypeError:
                pass
        title = row["title"]
        title = "".join([i if i.isalnum() else "_" for i in title])
        data_dir = Path(os.path.expanduser(str(output_dir)+"/"+title))

        if len(str(data_dir)) > 30:
            data_dir = Path(str(data_dir)[:50])
        data_dirs.append(str(data_dir))
        os.makedirs(data_dir, exist_ok=True)

        if len(links) > 0:
            for i in links:
                print("Downloading data from", i)
                get_data_from_link(i, data_dir)
        formats = []
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                data_amount += 1
                formats.append(file.split(".")[-1])

        number_of_files.append(data_amount)
        progress.update(1)
        formats_s.append(formats)
    new_data_dirs = []
    for i in data_dirs:
        try:
            if len(os.listdir(i)) == 0:
                os.rmdir(i)
                new_data_dirs.append("")
            else:
                new_data_dirs.append(i)
        except FileNotFoundError:
            new_data_dirs.append(i)
            
    delete_empty_folders(output_dir)

    data_report["data_dir"] = new_data_dirs
    data_report["number_of_files"] = number_of_files
    data_report["formats"] = formats_s

    print("Download attempt complete.")

    return data_report

if __name__ == '__main__':
    doi = "10.1016/j.tpb.2012.08.002"
    doi = "10.3390/microorganisms10091765"
    
    links = find_data_web(doi)
    
    data = get_data_from_link(links[0], "~/Documents/pp")
