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
import re
from datetime import datetime
import validators

repos = keywords["field_specific_repo"] + keywords["repositories"]

filetypes = [
    "csv", "xlsx", "xls", "txt", "pdf", "zip", "tar.gz", "tar", "gz", "json",
    "docx", "doc", "ods", "odt", "pptx", "ppt", "png", "jpg", "md", "exe",
    "tab", "fasta", "gb"
]

repositories = keywords["repositories"]

def download_file(url, output_dir):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        filename = url.split('/')[-1].split("?")[0]
        if not any(filename.lower().endswith('.' + ft) for ft in filetypes):
            filename += '.unknown'
        file_path = os.path.join(output_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(response.content)
        return file_path if os.path.getsize(file_path) > 0 else None
    except requests.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return None

def download_osf_file(url, output_dir, file_name):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        return file_path if os.path.getsize(file_path) > 0 else None
    except requests.RequestException as e:
        print(f"Error downloading OSF file {url}: {e}")
        return None

def get_data_from_link(link, output_dir="examples/data"):
    print(f"Processing link: {link}")
    if not validators.url(link):
        print(f"Invalid URL: {link}")
        return [], "unknown"

    try:
        domain = link.split('/')[2]
    except IndexError:
        print(f"Invalid URL format: {link}")
        return [], "unknown"
    source = domain.replace("www.", "").replace(".", "_")
    for r in repositories:
        if r in link:
            source = r
            break
    output_dir = os.path.expanduser(f"{output_dir}/{source}")
    os.makedirs(output_dir, exist_ok=True)

    if "accessed" in link:
        link = link.split("accessed")[0]

    downloaded_files = []
    license_info = "unknown"

    try:
        s = HTMLSession()
        r = s.get(link, timeout=5)
        if "Content-Type" in r.headers and "text/html" not in r.headers["Content-Type"]:
            filename = r.headers.get("Content-Disposition", "").split("filename=")[-1] or "data_file"
            if not any(filename.lower().endswith('.' + ft) for ft in filetypes):
                filename += '.bin'
            file_path = os.path.join(output_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(r.content)
            downloaded_files = [file_path] if os.path.getsize(file_path) > 0 else []
            return downloaded_files, license_info

        soup = BeautifulSoup(r.html.html, 'html.parser')

        # Enhanced license scraping
        license_patterns = [
            r"license\s*[:=]\s*(CC0|CC\s*BY|CC\s*BY-SA|CC\s*BY-NC|MIT|Public\s*Domain|Apache|GPL)",
            r"Creative\s*Commons\s*(CC0|BY|BY-SA|BY-NC)",
            r"under\s*(CC0|CC\s*BY|CC\s*BY-SA|CC\s*BY-NC|MIT|Public\s*Domain)",
            r"(CC0|CC\s*BY|CC\s*BY-SA|CC\s*BY-NC|MIT|Public\s*Domain)\s*license",
        ]
        
        # Search in full text
        page_text = soup.get_text().lower()
        for pattern in license_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                license_info = match.group(1) or match.group(0).replace("license", "").strip()
                print(f"Found license: {license_info} in page text")
                break

        # Search in specific tags if not found in full text
        if license_info == "unknown":
            for tag in soup.find_all(['p', 'div', 'span', 'a', 'meta']):
                text = tag.get_text().lower()
                for pattern in license_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        license_info = match.group(1) or match.group(0).replace("license", "").strip()
                        print(f"Found license: {license_info} in tag {tag.name}")
                        break
                if license_info != "unknown":
                    break

        # Repository-specific scraping
        if "dryad" in link.lower() and license_info == "unknown":
            license_info = "CC0 (Dryad default)"  # Dryad typically uses CC0
            print(f"Assigned default Dryad license: {license_info}")
        elif "osf.io" in link.lower() and license_info == "unknown":
            license_elem = soup.find("div", class_="license") or soup.find(string=re.compile("license", re.I))
            if license_elem:
                license_info = license_elem.get_text(strip=True)
                print(f"Found OSF license: {license_info}")
        elif "figshare" in link.lower() and license_info == "unknown":
            license_elem = soup.find("div", class_="license-info") or soup.find("a", href=re.compile("creativecommons"))
            if license_elem:
                license_info = license_elem.get_text(strip=True) or "CC BY (figshare default)"
                print(f"Found figshare license: {license_info}")
        elif "zenodo" in link.lower() and license_info == "unknown":
            license_elem = soup.find("div", class_="ui license") or soup.find(string=re.compile("license", re.I))
            if license_elem:
                license_info = license_elem.get_text(strip=True)
                print(f"Found Zenodo license: {license_info}")

        # Download logic remains the same
        if "osf.io" in link:
            zip_ = f"https://files.osf.io/v1/resources/{link.split('/')[-2]}/providers/osfstorage/?zip="
            fp = download_osf_file(zip_, output_dir, f'{link.split("/")[-2]}.zip')
            downloaded_files = [fp] if fp else []
        elif "pangaea" in link:
            pangaea_formats = {"tab": "?format=textfile", "zip": "?format=zip"}
            for f in pangaea_formats:
                data_link = link + pangaea_formats[f]
                fp = download_file(data_link, output_dir)
                if fp:
                    downloaded_files = [fp]
                    if license_info == "unknown":
                        license_info = "CC BY (Pangaea default)"
                    break
        elif "dryad" in link:
            doi = re.search(r'10\.\d{4,9}/dryad\.[a-zA-Z0-9]+', link)
            if doi:
                dryad_download_link = f"https://datadryad.org/stash/downloads/file_stream/{doi.group(0).split('.')[-1]}"
                fp = download_file(dryad_download_link, output_dir)
                downloaded_files = [fp] if fp else []
        elif "figshare" in link:
            figshare_link = next((a.get('href') for a in soup.find_all('a') if "ndownloader" in a.get('href', '')), "")
            if figshare_link:
                fp = download_file(figshare_link, output_dir)
                downloaded_files = [fp] if fp else []
        elif "ncbi.nlm.nih.gov" in link:
            for a in soup.find_all('a', href=True):
                href = a['href']
                if any(ext in href.lower() for ext in ['fasta', 'gb', 'txt', 'xml']):
                    full_url = href if href.startswith('http') else f"https://www.ncbi.nlm.nih.gov{href}"
                    fp = download_file(full_url, output_dir)
                    if fp:
                        downloaded_files.append(fp)
            if license_info == "unknown":
                license_info = "Public Domain (NCBI default)"
        elif "ebi.ac.uk" in link:
            for a in soup.find_all('a', href=True):
                href = a['href']
                if any(ext in href.lower() for ext in ['fasta', 'xml', 'txt']):
                    full_url = href if href.startswith('http') else f"https://www.ebi.ac.uk{href}"
                    fp = download_file(full_url, output_dir)
                    if fp:
                        downloaded_files.append(fp)
            if license_info == "unknown":
                license_info = "CC0 or CC BY (EBI default)"
        else:
            for a in soup.find_all('a'):
                href = a.get('href', '')
                if any("." + ft in href.lower() for ft in filetypes):
                    full_url = href if href.startswith('http') else f"https://{domain}{href}"
                    fp = download_file(full_url, output_dir)
                    if fp:
                        downloaded_files.append(fp)
    except requests.RequestException as e:
        print(f"Error processing {link}: {e}")

    return downloaded_files, license_info

def delete_empty_folders(root):
    for dirpath, _, _ in os.walk(root, topdown=False):
        if not os.listdir(dirpath):
            os.rmdir(dirpath)

def DownloadData(data_report, output_dir):
    print("\nAttempting to download open data from the web.")
    print("Be advised that due to the nature of different websites, automatic download may not be possible.")
    print("Manual download may be required.")
    print("Please check the output directory for downloaded files.\n")

    data_dirs = []
    number_of_files = []
    formats_s = []
    download_paths = []
    data_sizes = []
    download_dates = []
    download_statuses = []
    licenses = []

    progress = tqdm(total=len(data_report))
    for idx, row in data_report.iterrows():
        links = []
        for col in ["data_links_keywords", "data_links_web"]:
            try:
                links += eval(row[col]) if isinstance(row[col], str) else row[col]
            except (KeyError, TypeError):
                pass

        title = row["title"]
        title = "".join([i if i.isalnum() else "_" for i in title])
        data_dir = Path(os.path.expanduser(f"{output_dir}/{title}"))
        if len(str(data_dir)) > 50:
            data_dir = Path(str(data_dir)[:50])
        os.makedirs(data_dir, exist_ok=True)

        downloaded_files = []
        license_info = "unknown"
        if links:
            for link in links:
                print(f"Downloading data from {link}")
                files, lic = get_data_from_link(link, data_dir)
                downloaded_files.extend(files)
                if lic != "unknown":
                    license_info = lic

        data_amount = 0
        formats = []
        sizes = []
        for root, _, files in os.walk(data_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.getsize(file_path) > 0:
                    data_amount += 1
                    formats.append(file.split(".")[-1])
                    size_mb = os.path.getsize(file_path) / 1048576
                    sizes.append(round(size_mb, 2))

        if data_amount > 0:
            data_dirs.append(str(data_dir))
            download_paths.append(downloaded_files)
            data_sizes.append(sizes)
            download_dates.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            download_statuses.append("success")
            licenses.append(license_info)
        else:
            data_dirs.append("")
            download_paths.append([])
            data_sizes.append([])
            download_dates.append("")
            download_statuses.append("failed" if links else "no_links")
            licenses.append("unknown")
            if os.path.exists(data_dir):
                delete_empty_folders(data_dir)
                if os.path.exists(data_dir) and not os.listdir(data_dir):
                    os.rmdir(data_dir)

        number_of_files.append(data_amount)
        formats_s.append(formats)
        progress.update(1)

    delete_empty_folders(output_dir)

    data_report["data_dir"] = data_dirs
    data_report["number_of_files"] = number_of_files
    data_report["formats"] = formats_s
    data_report["download_path"] = download_paths
    data_report["data_size"] = data_sizes
    data_report["download_date"] = download_dates
    data_report["download_status"] = download_statuses
    data_report["license"] = licenses

    print("Download attempt complete.")
    return data_report

if __name__ == '__main__':
    doi = "10.3390/microorganisms10091765"
    links = ["https://doi.org/10.5061/dryad.example"]  # Example link
    data_report = pd.DataFrame({"title": ["test"], "data_links_web": [links]})
    result = DownloadData(data_report, "~/Downloads/test_data")
    print(result)