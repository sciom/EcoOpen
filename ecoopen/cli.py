import argparse
from ecoopen.ecoopen import process_and_analyze_dois  # Absolute import

def main():
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
    args = parser.parse_args()

    if not args.dois and not args.input_file:
        parser.error("Either --dois or --input-file must be provided.")

    dois = None
    if args.dois:
        dois = [doi.strip() for doi in args.dois.split(",")]

    df = process_and_analyze_dois(
        input_file=args.input_file,
        dois=dois,
        save_to_disk=args.save_to_disk
    )
    print("Processing complete. Output saved to ecoopen_output.csv")
    print(df[["doi", "data_availability_statements", "code_availability_statements"]])

if __name__ == "__main__":
    main()