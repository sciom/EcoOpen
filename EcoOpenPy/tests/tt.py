from ecoopen import extract_all_information, download_pdf, extract_text_from_pdf

# Example open-access DOI (replace with any OA paper for real test)
doi = "10.1371/journal.pone.0266781"  # PLOS ONE, open access

# Step 1: Get PDF download URLs (simulate Unpaywall/OpenAlex, or use your own logic)
# For this demo, let's use the direct PLOS PDF link:
pdf_url = f"https://journals.plos.org/plosone/article/file?id={doi}&type=printable"
pdf_urls = [pdf_url]

# Step 2: Download the PDF
success, pdf_content, pdf_size, file_path = download_pdf(
    doi=doi,
    urls=pdf_urls,
    save_to_disk=False,  # Set True to save locally
    download_dir="./downloads",
    identifier="demo",
    title="plos_paper"
)

if not success:
    print("PDF download failed.")
    exit(1)

# Step 3: Extract text from the PDF
text = extract_text_from_pdf(pdf_content)
if not text.strip():
    print("PDF text extraction failed.")
    exit(1)

# Step 4: Extract all information from the text
result = extract_all_information(text)

print("Data URLs:", result["data_urls"])
print("Code URLs:", result["code_urls"])
print("DOIs:", result["dois"])
print("Accessions:", result["accessions"])
print("Data Statements:", result["data_statements"][:500])  # Print first 500 chars
print("Code Statements:", result["code_statements"][:500])