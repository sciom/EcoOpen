import argparse
from ecoopen.ecoopen import process_and_analyze_dois, DEFAULT_DATA_FORMATS
import logging

logger = logging.getLogger(__name__)

def main() -> None:
    """Command-line interface for ecoopen package."""
    parser = argparse.ArgumentParser(
        description="Process DOIs to download PDFs, extract text, and analyze data and code availability statements."
    )
    parser.add_argument(
        "--dois",
        type=str,
        help="Comma-separated list of DOIs to process (e.g., 'doi1,doi2,doi3')"
    )
    parser.add_argument(
        "--input-file",
        type=str,
        help="Path to a CSV file containing a 'doi' column with DOIs to process"
    )
    parser.add_argument(
        "--save-to-disk",
        action="store_true",
        default=True,
        help="Save downloaded PDFs to disk (default: True)"
    )
    parser.add_argument(
        "--email",
        type=str,
        help="Email address to use for Unpaywall API requests (alternatively, set UNPAYWALL_EMAIL environment variable)"
    )
    parser.add_argument(
        "--download-dir",
        type=str,
        default="./downloads",
        help="Directory to save downloaded PDFs (default: ./downloads)"
    )
    parser.add_argument(
        "--data-download-dir",
        type=str,
        default="./data_downloads",
        help="Directory to save downloaded data files (default: ./data_downloads)"
    )
    parser.add_argument(
        "--target-formats",
        type=str,
        default=",".join(DEFAULT_DATA_FORMATS),
        help=f"Comma-separated list of target data formats to download (default: {','.join(DEFAULT_DATA_FORMATS)})"
    )
    args = parser.parse_args()

    if not args.dois and not args.input_file:
        parser.error("Either --dois or --input-file must be provided.")

    dois = None
    if args.dois:
        dois = [doi.strip() for doi in args.dois.split(",")]
    
    target_formats = [fmt.strip() for fmt in args.target_formats.split(",")]

    df = process_and_analyze_dois(
        input_file=args.input_file,
        dois=dois,
        save_to_disk=args.save_to_disk,
        email=args.email,
        download_dir=args.download_dir,
        data_download_dir=args.data_download_dir,
        target_formats=target_formats
    )
    print("Processing complete. Output saved to ecoopen_output.csv")
    print(df[["identifier", "doi", "title", "data_availability_statements", "all_data_availability_statements", "code_availability_statements", "all_code_availability_statements", "downloaded_data_files"]])

if __name__ == "__main__":
    main()