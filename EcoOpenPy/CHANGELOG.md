# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-07-06

### Added
- Initial release of EcoOpen as an installable Python package
- Command line interface via `ecoopen` command
- Python API for programmatic access
- LLM-based data availability extraction using Ollama
- DOI extraction and OpenAlex metadata integration
- Batch PDF processing capabilities
- Data file download with format filtering
- Hardware-optimized model selection (phi4/phi3:mini)
- Comprehensive documentation and examples

### Features
- **Batch Processing**: Process entire folders of PDFs automatically
- **DOI Extraction**: Extract DOIs using regex and LLM fallback
- **OpenAlex Integration**: Fetch comprehensive metadata for papers
- **LLM Extraction**: Intelligent data/code availability extraction
- **Data Downloads**: Find and download data files with format filtering
- **Progress Tracking**: Real-time progress bars and detailed logging
- **Error Handling**: Robust error handling for large batch operations
