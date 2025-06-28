#!/usr/bin/env python3
"""
Test script for LLM-based data availability extraction in EcoOpen.
This script demonstrates the new LLM capabilities and compares them with keyword-based extraction.
"""

import os
import sys
sys.path.append('/home/domagoj/Dev/EcoOpen/EcoOpenPy')

from ecoopen import LLM_AVAILABLE, extract_all_information_from_pdf_llm, extract_text_from_pdf, extract_all_information
import json

def test_llm_extraction():
    """Test LLM-based extraction on a sample PDF."""
    
    print("=== EcoOpen LLM Extraction Test ===")
    print(f"LLM Available: {LLM_AVAILABLE}")
    
    if not LLM_AVAILABLE:
        print("\nLLM functionality not available.")
        print("To enable LLM extraction, install dependencies:")
        print("pip install -r requirements_llm.txt")
        print("\nAlso make sure Ollama is running with phi4 and nomic-embed-text models:")
        print("ollama run phi4")
        print("ollama run nomic-embed-text")
        return
    
    # Test with a PDF from the test folder
    pdf_path = "/home/domagoj/Dev/EcoOpen/EcoOpenPy/tests/pdf_downloads"
    pdf_files = [f for f in os.listdir(pdf_path) if f.endswith('.pdf')]
    
    if not pdf_files:
        print("No PDF files found in test directory")
        return
    
    # Use the first PDF for testing
    test_pdf = os.path.join(pdf_path, pdf_files[0])
    print(f"\nTesting with: {pdf_files[0]}")
    
    with open(test_pdf, 'rb') as f:
        pdf_content = f.read()
    
    print("\n--- Testing LLM-only extraction ---")
    try:
        llm_result = extract_all_information_from_pdf_llm(pdf_content, method="llm")
        print("LLM extraction completed!")
        
        if llm_result.get("success"):
            availability = llm_result.get("availability_info", {})
            if isinstance(availability, dict):
                data_avail = availability.get("data_availability", {})
                code_avail = availability.get("code_availability", {})
                
                print(f"Data availability found: {data_avail.get('found', False)}")
                print(f"Code availability found: {code_avail.get('found', False)}")
                
                if data_avail.get('found'):
                    print(f"Data access type: {data_avail.get('access_type', 'unknown')}")
                    print(f"Data confidence: {data_avail.get('confidence', 'unknown')}")
                
                if code_avail.get('found'):
                    print(f"Code access type: {code_avail.get('access_type', 'unknown')}")
                    print(f"Code confidence: {code_avail.get('confidence', 'unknown')}")
        else:
            print("LLM extraction failed")
            print(f"Error: {llm_result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"LLM extraction error: {e}")
    
    print("\n--- Testing comparison (both methods) ---")
    try:
        both_result = extract_all_information_from_pdf_llm(pdf_content, method="both")
        print("Comparison extraction completed!")
        
        if "comparison" in both_result:
            comp = both_result["comparison"]
            print(f"LLM success: {comp.get('llm_success', False)}")
            print(f"Keyword success: {comp.get('keyword_success', False)}")
            print(f"LLM found data: {comp.get('llm_found_data', False)}")
            print(f"Keyword found data: {comp.get('keyword_found_data', False)}")
            
    except Exception as e:
        print(f"Comparison extraction error: {e}")
    
    print("\n--- Testing keyword-only extraction for reference ---")
    try:
        text = extract_text_from_pdf(pdf_content)
        if text:
            keyword_result = extract_all_information(text, method="keyword")
            print("Keyword extraction completed!")
            print(f"Data statements found: {len(keyword_result.get('data_statements', ''))}")
            print(f"Code statements found: {len(keyword_result.get('code_statements', ''))}")
            print(f"URLs found: {len(keyword_result.get('all_urls', []))}")
            print(f"DOIs found: {len(keyword_result.get('dois', []))}")
        else:
            print("Failed to extract text from PDF")
            
    except Exception as e:
        print(f"Keyword extraction error: {e}")

def test_batch_llm_processing():
    """Test LLM extraction on multiple PDFs and save results."""
    
    if not LLM_AVAILABLE:
        print("LLM functionality not available for batch processing")
        return
    
    print("\n=== Batch LLM Processing Test ===")
    
    pdf_dir = "/home/domagoj/Dev/EcoOpen/EcoOpenPy/tests/pdf_downloads"
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')][:5]  # Test first 5 PDFs
    
    results = []
    
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\nProcessing {i}/{len(pdf_files)}: {pdf_file}")
        pdf_path = os.path.join(pdf_dir, pdf_file)
        
        try:
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
            
            # Use LLM extraction
            result = extract_all_information_from_pdf_llm(pdf_content, method="llm")
            
            results.append({
                "pdf_file": pdf_file,
                "llm_result": result,
                "success": result.get("success", False)
            })
            
            if result.get("success"):
                print("✓ LLM extraction successful")
            else:
                print("✗ LLM extraction failed")
                
        except Exception as e:
            print(f"✗ Error processing {pdf_file}: {e}")
            results.append({
                "pdf_file": pdf_file,
                "error": str(e),
                "success": False
            })
    
    # Save results
    output_file = "/home/domagoj/Dev/EcoOpen/EcoOpenPy/llm_test_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nBatch processing completed. Results saved to: {output_file}")
    
    # Summary
    successful = sum(1 for r in results if r.get("success"))
    print(f"Successfully processed: {successful}/{len(results)} PDFs")

if __name__ == "__main__":
    print("Starting LLM extraction tests...")
    
    # Test single PDF extraction
    test_llm_extraction()
    
    # Test batch processing
    if LLM_AVAILABLE:
        test_batch_llm_processing()
    
    print("\nTest completed!")
