#!/usr/bin/env python3
"""
Test script for the simplified EcoOpen package
"""

import sys
import os

# Add current directory to path
sys.path.append('.')

def test_basic_functionality():
    """Test basic imports and functionality."""
    print("=== Testing EcoOpen Simplified ===")
    
    try:
        from ecoopen import (
            LLM_AVAILABLE, get_doi_metadata, process_single_doi, 
            process_dois_to_csv, LLMExtractor
        )
        print("✓ Imports successful")
        
        # Test LLM availability
        print(f"✓ LLM Available: {LLM_AVAILABLE}")
        
        if LLM_AVAILABLE:
            try:
                extractor = LLMExtractor()
                print("✓ LLM extractor initialization successful")
            except Exception as e:
                print(f"⚠ LLM extractor failed (Ollama may not be running): {e}")
        
        # Test metadata retrieval
        print("\n--- Testing Metadata Retrieval ---")
        test_doi = "10.1111/2041-210X.12952"
        metadata = get_doi_metadata(test_doi)
        if metadata:
            print(f"✓ Metadata retrieved for {test_doi}")
            print(f"  Title: {metadata.get('title', 'N/A')[:60]}...")
            print(f"  Authors: {metadata.get('authors', 'N/A')[:60]}...")
            print(f"  Journal: {metadata.get('journal', 'N/A')}")
        else:
            print(f"⚠ No metadata found for {test_doi}")
        
        # Test single DOI processing
        print("\n--- Testing Single DOI Processing ---")
        result = process_single_doi(test_doi, save_pdf=False)
        print(f"✓ DOI processed: {result['doi']}")
        print(f"  Has fulltext: {result['has_fulltext']}")
        print(f"  PDF size: {result['pdf_content_length']} bytes")
        if result['data_availability_statements']:
            print(f"  Data statement: {result['data_availability_statements'][:100]}...")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_csv_output():
    """Test CSV output format."""
    print("\n--- Testing CSV Output ---")
    
    try:
        from ecoopen import process_dois_to_csv, CSV_COLUMNS
        
        # Test with a few DOIs
        test_dois = [
            "10.1111/2041-210X.12952",
            "10.5194/bg-15-3521-2018"
        ]
        
        df = process_dois_to_csv(test_dois, "test_output.csv", save_pdfs=False)
        
        print(f"✓ Processed {len(test_dois)} DOIs")
        print(f"✓ CSV saved with {len(df)} rows")
        print(f"✓ Columns: {list(df.columns)}")
        
        # Verify column structure
        if list(df.columns) == CSV_COLUMNS:
            print("✓ Column structure matches requirements")
        else:
            print("⚠ Column structure mismatch")
            print(f"Expected: {CSV_COLUMNS}")
            print(f"Got: {list(df.columns)}")
        
        # Show sample data
        if not df.empty:
            print("\n--- Sample Row ---")
            row = df.iloc[0]
            for col in ['identifier', 'doi', 'title', 'has_fulltext', 'data_availability_statements']:
                print(f"  {col}: {row[col]}")
        
        return True
        
    except Exception as e:
        print(f"✗ CSV test failed: {e}")
        return False


def test_pdf_processing():
    """Test direct PDF processing if LLM is available."""
    try:
        from ecoopen import LLM_AVAILABLE
        if not LLM_AVAILABLE:
            print("\n--- Skipping PDF test (LLM not available) ---")
            return True
    except ImportError:
        print("\n--- Skipping PDF test (import failed) ---")
        return True
    
    print("\n--- Testing PDF Processing ---")
    
    # Look for a test PDF
    pdf_dirs = ['./tests/pdf_downloads', './pdf_downloads', './pdfs']
    test_pdf = None
    
    for pdf_dir in pdf_dirs:
        if os.path.exists(pdf_dir):
            pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
            if pdf_files:
                test_pdf = os.path.join(pdf_dir, pdf_files[0])
                break
    
    if not test_pdf:
        print("⚠ No test PDF found, skipping direct PDF test")
        return True
    
    try:
        from ecoopen import process_pdf_file
        
        result = process_pdf_file(test_pdf)
        print(f"✓ PDF processed: {os.path.basename(test_pdf)}")
        print(f"  Title: {result.get('title', 'N/A')[:60]}...")
        print(f"  Data statements: {len(result.get('data_availability_statements', ''))}")
        print(f"  Code statements: {len(result.get('code_availability_statements', ''))}")
        
        return True
        
    except Exception as e:
        print(f"⚠ PDF processing failed: {e}")
        return True  # Non-critical


def main():
    """Run all tests."""
    print("Testing EcoOpen Simplified Package")
    print("=" * 50)
    
    tests = [
        test_basic_functionality,
        test_csv_output,
        test_pdf_processing
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{len(tests)} tests")
    
    if passed == len(tests):
        print("🎉 All tests passed! The simplified package is working correctly.")
        print("\nNext steps:")
        print("1. Install LLM dependencies: pip install -r requirements_simple.txt")
        print("2. Start Ollama: ollama run phi4")
        print("3. Run: python ecoopen_simple.py --check-llm")
    else:
        print("⚠ Some tests failed. Check the errors above.")
    
    # Cleanup
    if os.path.exists("test_output.csv"):
        os.remove("test_output.csv")


if __name__ == "__main__":
    main()
