import sys
import logging
from ecoopen import process_and_analyze_dois

# Increase recursion limit temporarily to handle deep recursion during testing
sys.setrecursionlimit(2000)

# Initialize logging for main process
logging.basicConfig(
    filename="ecoopen.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode='a'  # Append to log file
)

dois = [
    "10.1111/2041-210X.12952"
]

logging.info(f"Starting test with {len(dois)} DOIs")

df = process_and_analyze_dois(
    dois=dois,
    save_to_disk=True,
    email="your_real_email@domain.com",  # Replace with a valid Unpaywall-registered email
    download_dir="./pdf_downloads",
    data_download_dir="./data_downloads",
    target_formats=["csv", "xlsx"]
)

logging.info("Test completed")
print("Test completed. Output saved to ecoopen_output.csv")
print(df[["identifier", "doi", "title", "data_availability_statements", "downloaded_data_files"]])