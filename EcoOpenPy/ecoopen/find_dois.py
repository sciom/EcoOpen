import fitz  # PyMuPDF for PDF text extraction
import re
import os
import logging
import requests
from urllib.parse import quote

# Setup logging
logging.basicConfig(
    filename="find_dois.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode='w'  # Clear the log file before writing
)

def validate_doi(doi):
    """Validate DOI format using regex."""
    doi_pattern = r'^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$'
    try:
        return bool(re.match(doi_pattern, doi))
    except TypeError:
        logging.warning(f"Invalid DOI format: {doi}")
        return False

def extract_title_from_pdf(pdf_path):
    """Extract a potential title from the PDF (first few lines of text)."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        # Extract text from the first page
        for page_num in range(min(1, doc.page_count)):
            page = doc[page_num]
            text += page.get_text("text")
        doc.close()

        # Take the first few lines and clean up
        lines = text.split('\n')[:3]  # First 3 lines often contain the title
        title = ' '.join(line.strip() for line in lines if line.strip())
        # Clean up title: remove excessive whitespace, special characters
        title = re.sub(r'\s+', ' ', title)
        title = title[:100]  # Limit title length for search
        logging.info(f"Extracted potential title from {pdf_path}: {title}")
        return title
    except Exception as e:
        logging.error(f"Error extracting title from {pdf_path}: {str(e)}")
        return None

def search_doi_by_title(title):
    """Search for a DOI online using the CrossRef API based on the title."""
    if not title:
        return None

    try:
        # Encode the title for the API query
        encoded_title = quote(title)
        url = f"https://api.crossref.org/works?query.title={encoded_title}&rows=1"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Check if a result was found
        if data.get("message", {}).get("items"):
            item = data["message"]["items"][0]
            doi = item.get("DOI")
            if doi and validate_doi(doi):
                logging.info(f"Found DOI via CrossRef for title '{title}': {doi}")
                return doi
        logging.warning(f"No DOI found via CrossRef for title: {title}")
        return None
    except Exception as e:
        logging.error(f"Error searching DOI for title '{title}': {str(e)}")
        return None

def find_dois(directory):
    """Find DOIs from the content of PDF files in the specified directory, using title search as a fallback."""
    doi_pattern = r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+'
    doi_file_mapping = {}  # Maps DOI to file path
    files_without_doi = []

    if not os.path.exists(directory):
        logging.error(f"Directory {directory} does not exist.")
        return [], {}

    for filename in os.listdir(directory):
        if filename.lower().endswith(".pdf"):
            file_path = os.path.join(directory, filename)
            try:
                # Read the PDF content
                doc = fitz.open(file_path)
                text = ""
                # Extract text from the first few pages (e.g., first 5 pages) to speed up processing
                for page_num in range(min(5, doc.page_count)):
                    page = doc[page_num]
                    text += page.get_text("text")
                doc.close()

                # Search for DOIs in the text
                matches = re.findall(doi_pattern, text)
                valid_dois = [doi for doi in matches if validate_doi(doi)]

                if valid_dois:
                    # Take the first valid DOI found (likely the paper's own DOI)
                    doi = valid_dois[0]
                    doi_file_mapping[doi] = file_path
                    logging.info(f"Found DOI {doi} from PDF content: {file_path}")
                else:
                    # If no DOI is found, extract the title and search online
                    title = extract_title_from_pdf(file_path)
                    if title:
                        doi = search_doi_by_title(title)
                        if doi:
                            doi_file_mapping[doi] = file_path
                            logging.info(f"Found DOI {doi} via title search for PDF: {file_path}")
                        else:
                            files_without_doi.append(file_path)
                            logging.warning(f"No DOI found via title search for PDF: {file_path}")
                    else:
                        files_without_doi.append(file_path)
                        logging.warning(f"Could not extract title or DOI from PDF: {file_path}")
            except Exception as e:
                logging.error(f"Error processing PDF file {file_path}: {str(e)}")
                files_without_doi.append(file_path)

    # List of unique DOIs
    dois = list(doi_file_mapping.keys())
    logging.info(f"Found {len(dois)} valid DOIs from directory {directory}: {dois}")
    if files_without_doi:
        logging.warning(f"Files without a detectable DOI: {files_without_doi}")

    return dois, doi_file_mapping