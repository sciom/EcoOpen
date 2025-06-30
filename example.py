"""
example.py - Practical example for EcoOpen: Process sample PDFs and save to CSV
"""

import sys
import os
from EcoOpenPy import ecoopen

if __name__ == "__main__":
    # Process a sample of PDFs from the tests/test_papers folder
    test_folder = os.path.join(os.path.dirname(__file__), "EcoOpenPy", "tests", "test_papers")
    output_csv = "ecoopen_sample_results.csv"
    
    print(f"🔍 Processing sample PDFs from: {test_folder}")
    print(f"📊 Results will be saved to: {output_csv}")
    print("-" * 50)
    
    # Get all PDF files and select a manageable sample
    all_pdfs = [f for f in os.listdir(test_folder) if f.lower().endswith(".pdf")]
    
    # Select a diverse sample of papers (mix of newer and older papers)
    sample_pdfs = [
        "Biological Reviews - 2024 - Janas - Avian colouration in a polluted world  a meta‐analysis.pdf",
        "Ecology Letters - 2022 - Atkinson - Terrestrial ecosystem restoration increases biodiversity and reduces its variability  Copy.pdf",
        "10.1111@syen.12432.pdf",
        "agostini2021.pdf",
        "ncomms11666.pdf"
    ]
    
    # Filter to only existing files
    existing_samples = [pdf for pdf in sample_pdfs if pdf in all_pdfs]
    
    # If selected samples don't exist, use first 5 available PDFs
    if len(existing_samples) < 3:
        existing_samples = all_pdfs[:5]
    
    print(f"📄 Processing {len(existing_samples)} sample papers:")
    for i, pdf in enumerate(existing_samples, 1):
        print(f"   {i}. {pdf}")
    print()
    
    # Create a temporary folder with just our sample PDFs
    sample_folder = os.path.join(os.path.dirname(__file__), "temp_sample")
    os.makedirs(sample_folder, exist_ok=True)
    
    # Copy sample PDFs to temp folder
    import shutil
    for pdf in existing_samples:
        src = os.path.join(test_folder, pdf)
        dst = os.path.join(sample_folder, pdf)
        shutil.copy2(src, dst)
    
    try:
        # Process the sample folder and save to CSV
        df = ecoopen.process_pdf_folder_to_csv(
            folder_path=sample_folder,
            output_file=output_csv,
            recursive=False
        )
        
        print("\n" + "=" * 50)
        print("📈 PROCESSING SUMMARY")
        print("=" * 50)
        
        if not df.empty:
            total_papers = len(df)
            papers_with_doi = len(df[df['doi'] != ''])
            papers_with_title = len(df[df['title'] != ''])
            papers_with_data = len(df[df['data_availability_statements'] != ''])
            papers_with_code = len(df[df['code_availability_statements'] != ''])
            
            print(f"📄 Total papers processed: {total_papers}")
            print(f"🔗 Papers with DOI: {papers_with_doi} ({papers_with_doi/total_papers*100:.1f}%)")
            print(f"📖 Papers with title: {papers_with_title} ({papers_with_title/total_papers*100:.1f}%)")
            print(f"💾 Papers with data statements: {papers_with_data} ({papers_with_data/total_papers*100:.1f}%)")
            print(f"💻 Papers with code statements: {papers_with_code} ({papers_with_code/total_papers*100:.1f}%)")
            
            print(f"\n✅ Results saved to: {output_csv}")
            print(f"📁 Open the CSV file to see detailed extraction results for each paper")
            
            # Show detailed results
            print(f"\n🔍 DETAILED RESULTS:")
            print("-" * 50)
            for i, row in df.iterrows():
                print(f"{i+1}. {os.path.basename(row['path'])}")
                print(f"   Title: {row['title'][:80]}{'...' if len(row['title']) > 80 else ''}")
                print(f"   DOI: {row['doi'] if row['doi'] else 'Not found'}")
                print(f"   Data: {'Yes' if row['data_availability_statements'] else 'No'}")
                print(f"   Code: {'Yes' if row['code_availability_statements'] else 'No'}")
                if row['data_availability_statements']:
                    print(f"   Data details: {row['data_availability_statements'][:100]}{'...' if len(row['data_availability_statements']) > 100 else ''}")
                print()
        else:
            print("❌ No PDFs were processed successfully.")
            print("Check that PDFs exist in the test_papers folder and try again.")
            
    finally:
        # Clean up temp folder
        shutil.rmtree(sample_folder, ignore_errors=True)
        
    print(f"\n💡 To process all {len(all_pdfs)} papers, use:")
    print(f"   python3 -m EcoOpenPy.ecoopen --pdf-folder '{test_folder}' --output all_papers_results.csv")


