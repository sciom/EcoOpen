import requests
import os

from bs4 import BeautifulSoup

from requests_html import HTMLSession
import random
from pathlib import Path
from tqdm import tqdm

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:54.0) Gecko/20100101 Firefox/54.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/602.3.12 (KHTML, like Gecko) Version/10.1.2 Safari/602.3.12",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; AS; rv:11.0) like Gecko",
]
headers_list = [
    {"User-Agent": "Mozilla/5.0", "TE": "Trailers"},
    {"User-Agent": "Mozilla/5.0"},
    {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.5"},
    {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf"},
    {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip, deflate"},
    {"User-Agent": "Mozilla/5.0", "Connection": "keep-alive"},
    {"User-Agent": "Mozilla/5.0", "Cache-Control": "max-age=0"},
    {"User-Agent": "Mozilla/5.0", "Upgrade-Insecure-Requests": "1"},
    {"User-Agent": "Mozilla/5.0", "DNT": "1"},
    {"User-Agent": "Mozilla/5.0", "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7"},
    {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.5", "Accept": "application/pdf"},
    {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.5", "Accept-Encoding": "gzip, deflate"},
    {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.5", "Connection": "keep-alive"},
    {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.5", "Cache-Control": "max-age=0"},
    {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.5", "Upgrade-Insecure-Requests": "1"},
    {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.5", "DNT": "1"},
    {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.5", "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7"},
    {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.5", "TE": "Trailers"},
    {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf", "Accept-Encoding": "gzip, deflate"},
    {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf", "Connection": "keep-alive"},
    {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf", "Cache-Control": "max-age=0"},
    {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf", "Upgrade-Insecure-Requests": "1"},
    {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf", "DNT": "1"},
    {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf", "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7"},
    {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf", "TE": "Trailers"}
]

# List of other header fields
header_fields = [
    # {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"},
    {"Accept-Language": "en-US,en;q=0.5"},
    {"Connection": "keep-alive"},
    {"Cache-Control": "max-age=0"},
    {"Upgrade-Insecure-Requests": "1"},
    {"DNT": "1"},
    {"Accept": "application/pdf"},
]

def generate_random_headers_list(n):
    headers_list = []
    for _ in range(n):
        headers = {
            "User-Agent": random.choice(user_agents),
            "TE": "Trailers"
        }
        # Add a random number of additional headers
        additional_headers = random.sample(header_fields, random.randint(1, 3))
        for field in additional_headers:
            headers.update(field)
        headers_list.append(headers)
    return headers_list

def download_pdf(url, title, output_dir, headers_list=headers_list):
    output_dir = os.path.expanduser(output_dir)
    
    output_file = os.path.join(output_dir, title + ".pdf")
    # print(output_file)
    for headers in generate_random_headers_list(30):
        try:
            response = requests.get(url, headers=headers, allow_redirects=True)
            if response.status_code == 200:
                with open(output_file, 'wb') as f:
                    f.write(response.content)
                # print(
                    # f"Downloaded PDF from {url} and saved as {output_file}",
                    # headers)
                return True
            # else:
            #     print(
                # f"Failed with status code {response.status_code} using headers {headers}")
        except requests.exceptions.RequestException as e:
            pass
            # print(f"Request failed: {e} using headers {headers}")
    
    # print(f"Failed to download PDF from {url} with all provided headers")
    return False

def DownloadPapers(papers, output_dir, other_sources=False, callback=None):
    print("Downloading papers")
    output_dir = os.path.expanduser(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    downloaded = []
    downloadable = []
    paths = []
    
    pbar = tqdm(total=len(papers))
    for idx, i in papers.iterrows():
        url = i["url"]
        title = i["title"]
        year = i["published"][:4]
        author = i["authors"].split(",")
        is_oa = i["is_oa"]
        # print(url, is_oa)
        
        etal = False
        if len(author) > 1:
            author = author[0]
            etal = True
        
        if etal:
            author = author + "_et_al"
        filename = f"{author}_{year}_{title}"    
        # non-alphanumeric characters in title replace with underscore
        
        filename = "".join([c if c.isalnum() else "_" for c in filename])
        
        # shorten the fielname
        if len(filename) > 100:
            filename = filename[:100]
        
        if url != "":
            result = download_pdf(i["url"], filename, output_dir)
        elif url == "" and is_oa:
            try:
                url = find_pdf(i["doi"])
            except Exception as e:
                print(e)
                url = ""
            if url !="":
                # print("downloading from site")
                result = download_pdf(url, filename, output_dir)
            else:
                result = False
        elif url == "" and not is_oa and other_sources:
            result = download_other_sources(i["doi"], filename, output_dir)
        else:
            result = False
        downloadable.append(result)
        if not result and is_oa:
            result = download_other_sources(i["doi"], filename, output_dir)
        elif other_sources and not result:
            result = download_other_sources(i["doi"], filename, output_dir)
        downloaded.append(result)
        
        if result:
            paths.append(f"{output_dir}/{filename}.pdf")
        else:
            paths.append("")
        pbar.update(1)
        # print(f"Downloaded {idx+1}/{len(papers)} papers")
        if callback:
            callback(idx+1, len(papers))
    pbar.close()

    papers["downloaded"] = downloaded
    papers["downloadable"] = downloadable
    papers["path"] = paths
    
    # count downloaded papers
    downloaded_count = len([i for i in downloaded if i])
    print(f"Downloaded {downloaded_count}/{len(papers)} papers")
    return papers
               
            
def find_pdf(url):
    # print(url)
    for headers in generate_random_headers_list(20):
        session = requests.Session()
        
        response = session.get(url, headers=headers, allow_redirects=True)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'xml')
            
            # get domain of the response
            domain = response.url.split("/")[2]
            # print(soup.prettify())
            for a in soup.find_all('a', href=True):
                # print(a["href"])
                if "pdf" in a['href']:
                    
                    if domain not in a['href']:
                        return f"https://{domain}{a['href']}"
                    return a['href']
            break
        else:
            pass
            # print(
                # f"Failed with status code {response.status_code} using headers {headers}")
    return ""

def download_other_sources(doi, title, output_dir):
    output_dir = Path(os.path.expanduser(output_dir))
    output_dir = output_dir.absolute()
    # print(output_dir)
    if not os.path.exists(output_dir):
        os.system(f"mkdir {output_dir}")
    site_url = "https://sci-hub.se/"
    download_link = site_url+doi
    # Send a GET request to the Sci-Hub page
    response = requests.get(download_link, timeout=10)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the iframe or embed tag containing the PDF
        iframe = soup.find('iframe')
        if iframe:
            pdf_url = iframe['src']
        else:
            embed = soup.find('embed')
            if embed:
                pdf_url = embed['src']
            else:
                # print("PDF URL not found")
                return False
        # Handle relative URLs
        if pdf_url.startswith("/downloads"):
            pdf_url = f"https://sci-hub.se{pdf_url}"
        if pdf_url.startswith('//'):
            pdf_url = f"https:{pdf_url}"
        elif pdf_url.startswith('/'):
            pdf_url = f"https:/{pdf_url}"
            
        # Send a GET request to the extracted PDF URL
        # print(pdf_url)
        try:
            pdf_response = requests.get(pdf_url, timeout=3)

            # Check if the request was successful
            if pdf_response.status_code == 200:
                file_path = f"{output_dir}/{title}.pdf"
                # Create the output directory if it doesn't exist
                os.makedirs(output_dir, exist_ok=True)
                # Save the content of the response as a PDF file
                with open(file_path, 'wb') as f:
                    f.write(pdf_response.content)
                # print(f"Downloaded {file_name}")
                return True
        except requests.exceptions.ConnectionError:
            # print("Connection error")
            # print(pdf_url)
            return False
    return False