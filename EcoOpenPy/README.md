# EcoOpen

EcoOpen is a Python package for processing DOIs to download PDFs, extract text, and analyze data and code availability statements in scientific papers.

## Installation

You can install EcoOpen via pip:

```bash
pip install ecoopen
```

## Usage

### As a Library

```python
from ecoopen import process_and_analyze_dois, find_dois

# Process a list of DOIs
dois = ["10.3390/ecologies2030017", "10.1111/gcb.12963"]
df = process_and_analyze_dois(dois=dois, save_to_disk=True)
print(df[["doi", "data_availability_statements", "code_availability_statements"]])

# Find DOIs in a directory of PDFs
dois, doi_file_mapping = find_dois("./downloads")
print(f"Found DOIs: {dois}")
```

### Command-Line Interface

EcoOpen provides a CLI for processing DOIs:

```bash
ecoopen --dois "10.3390/ecologies2030017,10.1111/gcb.12963" --save-to-disk
```

Or process DOIs from a CSV file:

```bash
ecoopen --input-file dois.csv --save-to-disk
```

## Requirements

- Python 3.6+
- pandas
- requests
- spacy
- pyalex
- beautifulsoup4
- tqdm
- PyMuPDF

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.