from ecoopen import process_and_analyze_dois
dois = [
"10.1111/2041-210X.12952"
]

df = process_and_analyze_dois(
    dois=dois,
    save_to_disk=True,
    email="your.email@example.com",
    download_dir="./pdf_downloads",
    data_download_dir="./data_downloads",
    # target_formats=["csv", "xlsx"]
)