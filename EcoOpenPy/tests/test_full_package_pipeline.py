import csv
from ecoopen import run_and_save_pipeline_from_doi_list

def test_full_package_pipeline_and_csv():
    # Read DOIs from the provided CSV file
    dois = []
    with open("../expected_output/dois.csv", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            doi = row.get("DOI")
            if doi and doi.strip():
                dois.append(doi.strip())
    assert dois, "No DOIs found in the input file."
    # Run the integrated pipeline and save to CSV
    results = run_and_save_pipeline_from_doi_list(dois, "../ecoopen_output.csv")
    print(f"Test finished: {len(results)} valid extractions from {len(dois)} DOIs.")
    # Review the output CSV
    with open("../ecoopen_output.csv", newline="") as f:
        reader = csv.DictReader(f, delimiter=';')
        rows = list(reader)
        print(f"CSV contains {len(rows)} rows.")
        if rows:
            print("First row:")
            for k, v in rows[0].items():
                print(f"  {k}: {v}")

if __name__ == "__main__":
    test_full_package_pipeline_and_csv()
