import os
from ecoopen import extract_text_from_pdf, extract_all_information, save_pipeline_results_to_csv

def test_pdf_folder_pipeline():
    pdf_dir = "/home/domagoj/Dev/EcoOpen/EcoOpenPy/tests/pdf_downloads"
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]
    results = []
    for i, pdf_file in enumerate(pdf_files, 1):
        pdf_path = os.path.join(pdf_dir, pdf_file)
        with open(pdf_path, "rb") as f:
            pdf_content = f.read()
        text = extract_text_from_pdf(pdf_content)
        extraction = extract_all_information(text) if text else None
        results.append({
            "identifier": f"{i:03}",
            "pdf_file": pdf_file,
            "extracted_text_length": len(text) if text else 0,
            "extraction": extraction,
        })
    # Save to CSV
    save_pipeline_results_to_csv(results, "../ecoopen_output_from_pdfs.csv")
    print(f"Test finished: {len(results)} PDFs processed. Output saved to ecoopen_output_from_pdfs.csv.")

if __name__ == "__main__":
    test_pdf_folder_pipeline()
