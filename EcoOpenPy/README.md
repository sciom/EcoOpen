# EcoOpen

EcoOpen is a Python package designed to process DOIs, download associated PDFs, extract text, and analyze data and code availability statements. It can also download data files from repositories like Dryad, Zenodo, GitHub, and Figshare, using both web scraping and API calls for supported repositories.

## Features

- Validates and processes DOIs to retrieve metadata via Unpaywall and OpenAlex.
- Downloads PDFs from open-access sources.
- Extracts text from PDFs using PyMuPDF.
- Analyzes data and code availability statements using NLP (spaCy).
- Downloads data files from repositories using web scraping and APIs (e.g., Zenodo, Dryad, Figshare).
- Outputs results to a CSV file with detailed metadata.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ecoopen.git
   cd ecoopen
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

   The `requirements.txt` includes:
   ```
   pandas
   requests
   beautifulsoup4
   pyalex
   PyMuPDF
   tqdm
   spacy
   zenodo-client
   ```

3. Install the spaCy English model:
   ```bash
   python -m spacy download en_core_web_sm
   ```

4. Install the package locally:
   ```bash
   pip install -e .
   ```

## Usage

### Command-Line Interface (CLI)
Process a list of DOIs and save the results to a CSV file:

```bash
ecoopen --dois "10.1111/2041-210X.12952" --save-to-disk --email "your.email@example.com" --download-dir "./pdf_downloads" --data-download-dir "./data_downloads"
```

Or process DOIs from a CSV file:

```bash
ecoopen --input-file input_dois.csv --save-to-disk --email "your.email@example.com" --download-dir "./pdf_downloads" --data-download-dir "./data_downloads"
```

### As a Library
You can also use EcoOpen as a Python library:

```python
from ecoopen import process_and_analyze_dois

dois = ["10.1111/2041-210X.12952"]
df = process_and_analyze_dois(
    dois=dois,
    save_to_disk=True,
    email="your.email@example.com",
    download_dir="./pdf_downloads",
    data_download_dir="./data_downloads",
    target_formats=["csv", "xlsx"]
)
print(df[["identifier", "doi", "title", "data_links", "downloaded_data_files"]])
```

## Setting Up the Zenodo API

EcoOpen uses the Zenodo API to fetch downloadable files from Zenodo repositories, which is more reliable than web scraping. To enable this feature, you need to set up a Zenodo API token:

1. **Obtain a Zenodo API Token**:
   - Go to [Zenodo](https://zenodo.org) and sign in (or create an account).
   - Navigate to "Applications" > "Personal Access Tokens" in your user settings.
   - Generate a new token with the scope `deposit:write` (though for downloading, read-only access is sufficient).
   - Copy the generated token.

2. **Set the Zenodo API Token as an Environment Variable**:
   - On Linux/MacOS:
     ```bash
     export ZENODO_ACCESS_TOKEN="your_zenodo_token"
     ```
   - On Windows (Command Prompt):
     ```cmd
     set ZENODO_ACCESS_TOKEN=your_zenodo_token
     ```
   - Alternatively, you can add the export command to your shell configuration file (e.g., `~/.bashrc`, `~/.zshrc`) to make it persistent.

3. **Verify the Token**:
   - Run the EcoOpen command as shown above. If the token is set correctly, EcoOpen will use the Zenodo API to fetch files from Zenodo links. If no token is provided, it will fall back to web scraping, which may be less reliable.

**Note**: Providing a Zenodo API token allows EcoOpen to directly access file URLs from Zenodo records, improving download success rates. Without a token, the package will attempt to scrape Zenodo pages, which may fail due to rate limiting or page structure changes.

## Downloading Data from GitHub

EcoOpen downloads data from GitHub repositories by scraping GitHub pages to find direct download links. It looks for file URLs in the repository, such as raw file links (e.g., `https://raw.githubusercontent.com/user/repo/main/data.csv`), and converts `/blob/` URLs to raw URLs for downloading. No GitHub API token is required, as the package relies entirely on web scraping for GitHub data.

**Note**: Web scraping GitHub pages may be affected by rate limiting or changes in page structure. Ensure that your IP is not blocked by GitHub when making frequent requests.

## Output

The package generates an `ecoopen_output.csv` file with the following columns:
- `identifier`: Unique identifier for each DOI.
- `doi`: The processed DOI.
- `title`: Title of the paper.
- `authors`: Authors of the paper.
- `published`: Publication date.
- `url`: Landing page URL.
- `journal`: Journal name.
- `has_fulltext`: Whether a full-text URL was found.
- `is_oa`: Whether the paper is open access.
- `downloaded`: Whether the PDF was successfully downloaded.
- `path`: Path to the downloaded PDF.
- `pdf_content_length`: Size of the PDF in bytes.
- `data_links`: List of data URLs found in the paper.
- `downloaded_data_files`: List of paths to downloaded data files.
- `data_availability_statements`: Primary data availability statement.
- `all_data_availability_statements`: All data availability statements found.
- `code_availability_statements`: Primary code availability statement.
- `all_code_availability_statements`: All code availability statements found.
- `format`, `repository`, `repository_url`, `download_status`, `data_download_path`, `data_size`, `number_of_files`, `license`: Metadata about downloaded data files.

## Logging

EcoOpen generates a log file (`ecoopen.log`) with detailed information about the processing steps, including API calls, download attempts, and errors. Check this file to debug issues with PDF or data downloads.

## Troubleshooting

- **PDF Download Failures**: If PDFs fail to download (e.g., `403 Forbidden`), ensure your IP is not blocked by the target servers. The package rotates user agents to mitigate this, but some publishers may still restrict access.
- **Data Download Failures**: If data files are not downloaded, check `ecoopen.log` for errors. Ensure that API tokens (e.g., Zenodo) are set correctly if the data links point to those repositories.
- **GitHub Scraping Issues**: If GitHub data downloads fail, verify that the repository links are accessible and contain files in the target formats (`csv`, `xlsx`, etc.). GitHub may block requests if they detect automated scraping; consider adding delays or using a VPN if issues persist.
- **Zenodo API Issues**: If Zenodo downloads fail, verify your API token and ensure it has the correct permissions. Without a token, the package falls back to web scraping, which may fail for complex pages.

## Contributing

Contributions are welcome! Please submit a pull request or open an issue on GitHub.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.