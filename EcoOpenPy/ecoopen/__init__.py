#!/usr/bin/env python3
"""
EcoOpen - Simplified LLM-based Data Availability Extraction
===========================================================

A streamlined package for extracting data and code availability information from 
scientific PDFs using Large Language Models (Ollama + LangChain + ChromaDB).

Features:
- LLM-based intelligent extraction (no keyword matching)
- Direct PDF processing from DOIs or local files
- Clean CSV output with standardized columns
- Metadata extraction from OpenAlex API
- Simple, focused codebase

Author: Domagoj K. Hackenberger
License: MIT
"""

__version__ = "1.0.0"
__author__ = "Domagoj K. Hackenberger"
__email__ = "domagoj.hackenberger@example.com"
__license__ = "MIT"

# Import main classes and functions for easy access
from .core import (
    LLMExtractor,
    process_single_pdf_file,
    process_pdf_folder_to_csv,
    find_pdf_files,
    extract_doi_from_pdf,
    fetch_openalex_metadata,
    download_paper_data,
    extract_data_urls_from_text,
    check_ollama_performance,
    auto_detect_best_model,
    CSV_COLUMNS,
    DATA_FORMATS,
    LLM_AVAILABLE
)

__all__ = [
    "LLMExtractor",
    "process_single_pdf_file", 
    "process_pdf_folder_to_csv",
    "find_pdf_files",
    "extract_doi_from_pdf",
    "fetch_openalex_metadata",
    "download_paper_data",
    "extract_data_urls_from_text",
    "check_ollama_performance",
    "auto_detect_best_model",
    "CSV_COLUMNS",
    "DATA_FORMATS",
    "LLM_AVAILABLE",
]
