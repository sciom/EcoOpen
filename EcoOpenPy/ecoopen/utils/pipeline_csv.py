import csv
from typing import List
from ecoopen.ecoopen import full_pipeline_search_and_extract

def save_pipeline_results_to_csv(results: List[dict], csv_path: str):
    columns = [
        "identifier", "doi", "title", "authors", "published", "url", "journal",
        "has_fulltext", "is_oa", "downloaded", "path", "pdf_content_length",
        "data_links", "downloaded_data_files", "data_availability_statements", "code_availability_statements",
        "format", "repository", "repository_url", "download_status", "data_download_path", "data_size", "number_of_files", "license"
    ]
    with open(csv_path, mode="w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter=';')
        writer.writeheader()
        for i, r in enumerate(results, 1):
            extraction = r.get("extraction", {}) or {}
            def safe_str(val):
                if isinstance(val, (list, dict)):
                    return str(val)
                return val
            row = {
                "identifier": f"{i:03}",
                "doi": r.get("doi"),
                "title": r.get("title"),
                "authors": r.get("authors"),
                "published": r.get("published"),
                "url": r.get("landing_url"),
                "journal": r.get("journal"),
                "has_fulltext": bool(r.get("pdf_path")),
                "is_oa": None,
                "downloaded": bool(r.get("pdf_path")),
                "path": r.get("pdf_path"),
                "pdf_content_length": r.get("pdf_size"),
                "data_links": safe_str(extraction.get("data_urls")),
                "downloaded_data_files": None,
                "data_availability_statements": safe_str(extraction.get("data_statements")),
                "code_availability_statements": safe_str(extraction.get("code_statements")),
                "format": None,
                "repository": None,
                "repository_url": None,
                "download_status": None,
                "data_download_path": None,
                "data_size": None,
                "number_of_files": None,
                "license": None,
            }
            writer.writerow(row)
    print(f"Saved {len(results)} results to {csv_path}")

def run_and_save_pipeline_from_doi_list(doi_list, csv_path):
    results = []
    for doi in doi_list:
        res = full_pipeline_search_and_extract(doi, top_n=1, save_pdfs=False)
        if res and isinstance(res[0].get("extraction"), dict):
            results.append(res[0])
    save_pipeline_results_to_csv(results, csv_path)
    return results
