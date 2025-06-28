import csv
from ecoopen import run_and_save_pipeline_from_doi_list

def test_full_pipeline_on_doi_list():
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

if __name__ == "__main__":
    test_full_pipeline_on_doi_list()
