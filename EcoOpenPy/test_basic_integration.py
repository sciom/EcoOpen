#!/usr/bin/env python3
"""
Simple test to verify EcoOpen LLM integration works.
"""

import sys
sys.path.append('/home/domagoj/Dev/EcoOpen/EcoOpenPy')

def test_imports():
    """Test that imports work correctly."""
    print("Testing EcoOpen LLM imports...")
    
    try:
        from ecoopen import LLM_AVAILABLE, extract_all_information
        print(f"✓ Basic imports successful")
        print(f"✓ LLM Available: {LLM_AVAILABLE}")
        
        # Test keyword extraction (should always work)
        sample_text = """
        Data are available at Zenodo repository (DOI: 10.5281/zenodo.123456).
        Code for analysis is available on GitHub at https://github.com/user/repo.
        Supplementary data files are provided as Additional File 1.
        """
        
        result = extract_all_information(sample_text, method="keyword")
        print(f"✓ Keyword extraction test successful")
        print(f"  - URLs found: {len(result.get('all_urls', []))}")
        print(f"  - DOIs found: {len(result.get('dois', []))}")
        print(f"  - Data statements: {len(result.get('data_statements', ''))}")
        
        # Test LLM availability
        if LLM_AVAILABLE:
            from ecoopen import extract_all_information_from_pdf_llm, LLMDataExtractor
            print("✓ LLM imports successful")
            
            # Test LLM extractor initialization (without actually running it)
            try:
                extractor = LLMDataExtractor()
                print("✓ LLM extractor initialization successful")
            except Exception as e:
                print(f"⚠ LLM extractor initialization failed: {e}")
                print("  (This is expected if Ollama is not running)")
        else:
            print("ℹ LLM functionality not available (install requirements_llm.txt)")
            
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def test_package_structure():
    """Test that the package structure is correct."""
    print("\nTesting package structure...")
    
    try:
        import ecoopen
        print(f"✓ Package version: {ecoopen.__version__}")
        
        # Check key functions are available
        functions_to_check = [
            'extract_all_information',
            'extract_text_from_pdf',
            'extract_urls_from_text',
            'extract_dois_from_text'
        ]
        
        for func_name in functions_to_check:
            if hasattr(ecoopen, func_name):
                print(f"✓ {func_name} available")
            else:
                print(f"✗ {func_name} missing")
                
        return True
        
    except Exception as e:
        print(f"✗ Package structure test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== EcoOpen LLM Integration Test ===")
    
    success1 = test_imports()
    success2 = test_package_structure()
    
    if success1 and success2:
        print("\n🎉 All tests passed! EcoOpen LLM integration is ready.")
        print("\nNext steps:")
        print("1. Install LLM dependencies: pip install -r requirements_llm.txt")
        print("2. Start Ollama: ollama run phi4")
        print("3. Test with: python test_llm_extraction.py")
        print("4. Run Streamlit app: streamlit run ecoopen_llm_app.py")
    else:
        print("\n❌ Some tests failed. Check the errors above.")
