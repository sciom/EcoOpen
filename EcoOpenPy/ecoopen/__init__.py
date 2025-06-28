from ecoopen.find_dois import find_dois  # Absolute import
from ecoopen.ecoopen import *
from ecoopen.ecoopen import full_pipeline_search_and_extract, extract_text_from_pdf
from ecoopen.utils.pipeline_csv import save_pipeline_results_to_csv, run_and_save_pipeline_from_doi_list

__version__ = "0.1.0"

__all__ = [
    "extract_all_information",
    "extract_urls_from_text",
    "extract_dois_from_text",
    "extract_accessions_from_text",
    "score_data_statement",
    "find_dois",
    "full_pipeline_search_and_extract",
    "extract_text_from_pdf",
    "save_pipeline_results_to_csv",
    "run_and_save_pipeline_from_doi_list",
    # Oddpub-inspired helpers
    "oddpub_extract_statements",
    "ODDPUB_DATA_AVAILABILITY",
    "ODDPUB_CODE_AVAILABILITY",
    "ODDPUB_REPOSITORIES",
    "ODDPUB_FILE_FORMATS",
    "ODDPUB_ACCESSION_PATTERNS"
]