# EcoOpen

EcoOpen is a Python package for processing DOIs to download PDFs, extract text, and analyze data and code availability statements in scientific papers. It can be integrated with paper search APIs like OpenAlex to find DOIs and process the resulting papers, and it supports downloading open data files in specified formats.

## Installation

You can install EcoOpen via pip:

```bash
pip install ecoopen
```

## Usage

### As a Library

#### Processing DOIs Directly

You can use `ecoopen` to process a list of DOIs directly:

```python
from ecoopen import process_and_analyze_dois, find_dois

# Process a list of DOIs
dois = ["10.3390/ecologies2030017", "10.1111/gcb.12963"]
df = process_and_analyze_dois(
    dois=dois,
    save_to_disk=True,
    email="your.email@example.com",
    download_dir="./pdf_downloads",
    data_download_dir="./data_downloads",
    target_formats=["csv", "xlsx"]
)
print(df[["identifier", "doi", "title", "data_availability_statements", "all_data_availability_statements", "code_availability_statements", "all_code_availability_statements", "downloaded_data_files"]])
```

#### Finding DOIs in a Directory of PDFs

You can also use `ecoopen` to find DOIs in a directory of PDFs:

```python
# Find DOIs in a directory of PDFs
dois, doi_file_mapping = find_dois("./downloads")
print(f"Found DOIs: {dois}")
```

#### Downloading Open Data

EcoOpen can search for and download open data files mentioned in papers or linked from landing pages. By default, it targets common spreadsheet and delimited formats (`csv`, `tsv`, `txt`, `xlsx`, `xls`), but you can specify your own formats:

```python
from ecoopen import process_and_analyze_dois

# Process DOIs and download data files in specified formats
dois = ["10.3390/ecologies2030017"]
df = process_and_analyze_dois(
    dois=dois,
    save_to_disk=True,
    email="your.email@example.com",
    target_formats=["csv", "xlsx"],  # Only download CSV and Excel files
    data_download_dir="./my_data_downloads"
)
print(df[["identifier", "doi", "title", "data_links", "downloaded_data_files"]])
```

#### File Naming Convention

EcoOpen uses a structured naming convention for downloaded PDFs and data files to make them easier to reference and search:

- **PDF Files**: `<identifier>_<sanitized_doi>_<sanitized_title>.pdf`
  - `identifier`: A sequential number (e.g., `001`, `002`) assigned to each DOI.
  - `sanitized_doi`: The DOI with backslashes replaced by underscores (e.g., `10.3390_ecologies2030017`).
  - `sanitized_title`: A sanitized version of the paper title (e.g., `Ecology_Study_2020`).

- **Data Files**: `<identifier>_<sanitized_doi>_<sanitized_title>_<original_filename>`
  - `original_filename`: The original filename of the data file, preserving its extension.

For example, for the DOI `10.3390/ecologies2030017` with the title "Ecology Study 2020" and identifier `001`, the files might be named:
- PDF: `001_10.3390_ecologies2030017_Ecology_Study_2020.pdf`
- Data file: `001_10.3390_ecologies2030017_Ecology_Study_2020_dataset.csv`

#### Data and Code Availability Detection

EcoOpen analyzes the full text of papers to detect data and code availability statements. The detection algorithm has been enhanced to:

- **Analyze All Statements**: Instead of taking the first matching statement, EcoOpen now collects all potential data and code availability statements in the paper.
- **Scoring System**: Each statement is scored based on:
  - **Category Priority**: Statements indicating availability in repositories or supplementary materials are prioritized over "upon request" or "not available".
  - **Context Relevance**: Statements containing phrases like "this study", "we provide", or "our data/code" are boosted, as they likely refer to the paper's own data or code.
  - **Keyword Density**: Statements with more relevant keywords (e.g., "data", "code", "available", repository names) receive a higher score.
  - **Third-Party Detection**: Statements likely referring to third-party data or code (e.g., containing "obtained from", "third-party") are penalized.
- **Best Match Selection**: The statement with the highest score is selected as the primary data or code availability statement.
- **All Statements Output**: All detected statements are included in the output for transparency, under the columns `all_data_availability_statements` and `all_code_availability_statements`.

The output DataFrame includes:
- `data_availability_statements`: The best-matching data availability statement.
- `all_data_availability_statements`: A list of all detected data availability statements with their categories and scores.
- `code_availability_statements`: The best-matching code availability statement.
- `all_code_availability_statements`: A list of all detected code availability statements with their categories and scores.

### Command-Line Interface

EcoOpen provides a CLI for processing DOIs. You must provide an email address for Unpaywall API requests, either via the `--email` argument or by setting the `UNPAYWALL_EMAIL` environment variable.

#### Basic Usage

```bash
ecoopen --dois "10.3390/ecologies2030017,10.1111/gcb.12963" --save-to-disk --email "your.email@example.com"
```

Or process DOIs from a CSV file:

```bash
ecoopen --input-file dois.csv --save-to-disk --email "your.email@example.com"
```

Alternatively, set the `UNPAYWALL_EMAIL` environment variable:

```bash
export UNPAYWALL_EMAIL="your.email@example.com"
ecoopen --dois "10.3390/ecologies2030017,10.1111/gcb.12963" --save-to-disk
```

#### Downloading Open Data via CLI

You can use the CLI to download open data files in specific formats and save them to a custom directory:

```bash
ecoopen --dois "10.3390/ecologies2030017" --save-to-disk --email "your.email@example.com" --target-formats "csv,xlsx" --data-download-dir "./my_data_downloads"
```

### Integrating with Paper Search APIs (OpenAlex)

EcoOpen can be integrated with paper search APIs like [OpenAlex](https://openalex.org/) to search for papers and process their DOIs. OpenAlex is a free catalog of scholarly papers that provides a powerful API for searching papers by title, author, keyword, and more. EcoOpen already uses `pyalex` (a Python client for OpenAlex) as a dependency, so you can easily search for papers and pass the resulting DOIs to `ecoopen` for processing.

#### Setting Up OpenAlex

1. **Install `pyalex`**:
   - The `pyalex` library is already included as a dependency of `ecoopen`, so you don’t need to install it separately if you’ve installed `ecoopen`.

2. **Configure Your Email (Optional but Recommended)**:
   - OpenAlex recommends providing an email address with API requests to identify the user and provide better support. You can set this via the `pyalex` configuration:
     ```python
     import pyalex
     pyalex.config.email = "your.email@example.com"
     ```
   - Alternatively, you can pass the email directly when using `ecoopen`, as shown below.

#### Example: Search for Papers with OpenAlex and Process with EcoOpen

You can search for papers using OpenAlex and then process the resulting DOIs with `ecoopen`. Here’s an example that searches for papers with the keyword "ecology" published in 2020, processes them, and downloads associated data files:

```python
from pyalex import Works
from ecoopen import process_and_analyze_dois

# Configure pyalex (optional, for better API access)
import pyalex
pyalex.config.email = "your.email@example.com"

# Search for papers using OpenAlex
works = Works().filter(
    publication_year=2020,
    title_and_abstract={"search": "ecology"}
).get()

# Extract DOIs from the search results
dois = [work["doi"].replace("https://doi.org/", "") for work in works if work["doi"]]

# Process the DOIs with ecoopen
if dois:
    df = process_and_analyze_dois(
        dois=dois[:5],  # Limit to 5 DOIs for this example
        save_to_disk=True,
        email="your.email@example.com",
        target_formats=["csv", "xlsx"],
        data_download_dir="./data_downloads"
    )
    print(df[["identifier", "doi", "title", "data_availability_statements", "all_data_availability_statements", "code_availability_statements", "all_code_availability_statements", "downloaded_data_files"]])
else:
    print("No papers found with the given search criteria.")
```

#### Notes on OpenAlex Integration

- **API Access**: OpenAlex does not require an API key, but providing an email address is recommended for better rate limits and support. See the [OpenAlex API documentation](https://docs.openalex.org/) for more details.
- **Rate Limits**: OpenAlex has rate limits for API requests. If you encounter issues, consider adding delays between requests or contacting OpenAlex support.
- **Search Parameters**: You can customize the search query using various filters (e.g., `publication_year`, `author`, `institution`). Refer to the [pyalex documentation](https://github.com/J535D165/pyalex) for more options.
- **Error Handling**: Ensure you handle cases where no papers are found or DOIs are missing from the search results.

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

## Contributing

Contributions are welcome! Please open an issue or submit a pull request on [GitHub](https://github.com/yourusername/ecoopen).  # Replace with your GitHub URL