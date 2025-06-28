# EcoOpen LLM Rework - Implementation Summary

## Overview

This document summarizes the LLM-based rework of the EcoOpen package, which adds intelligent data availability extraction capabilities using Large Language Models (LLMs) while maintaining backward compatibility with the existing keyword-based approach.

## Key Features

### 1. **Dual Extraction Methods**
- **Keyword-based**: Traditional pattern matching (existing functionality)
- **LLM-based**: Intelligent reasoning using Phi4 model via Ollama
- **Comparison mode**: Run both methods and compare results

### 2. **Advanced LLM Capabilities**
- Context-aware analysis using vector embeddings
- Intelligent section detection and reasoning
- Confidence scoring for detected statements
- Structured JSON output with detailed categorization
- Support for multiple data/code availability scenarios

### 3. **Easy Integration**
- Optional dependency (graceful fallback if LLM not available)
- Backward compatible API
- Same function signatures with additional `method` parameter

## Architecture

### Core Components

1. **`llm_extractor.py`** - New LLM extraction engine
   - `LLMDataExtractor` class for advanced extraction
   - Vector database integration with ChromaDB
   - Structured prompt engineering for data availability detection

2. **Enhanced `ecoopen.py`** - Updated main module
   - `extract_all_information()` with method selection
   - `extract_all_information_from_pdf_llm()` for PDF-based LLM analysis
   - Backward compatibility maintained

3. **Requirements and Dependencies**
   - `requirements_llm.txt` - Optional LLM dependencies
   - Ollama integration for local LLM inference
   - ChromaDB for vector storage and retrieval

### LLM Pipeline

```
PDF Input → Text Chunking → Vector Embeddings → ChromaDB Storage
                                                      ↓
Retrieval-Augmented Generation ← Structured Prompts ← Query Processing
                ↓
        JSON Output with:
        - Data availability detection
        - Code availability detection  
        - Confidence scores
        - Access type classification
        - Repository identification
```

## Usage Examples

### Basic Usage (Keyword Method)
```python
from ecoopen import extract_all_information

# Traditional keyword-based extraction
result = extract_all_information(text, method="keyword")
print(result["data_statements"])
```

### LLM-Based Extraction
```python
from ecoopen import extract_all_information_from_pdf_llm

# LLM-based extraction from PDF
with open("paper.pdf", "rb") as f:
    result = extract_all_information_from_pdf_llm(f.read(), method="llm")
    
# Check results
availability = result["availability_info"]["data_availability"]
print(f"Data found: {availability['found']}")
print(f"Confidence: {availability['confidence']}")
print(f"Access type: {availability['access_type']}")
```

### Comparison Mode
```python
# Run both methods and compare
result = extract_all_information_from_pdf_llm(pdf_content, method="both")

comparison = result["comparison"]
print(f"LLM found data: {comparison['llm_found_data']}")
print(f"Keywords found data: {comparison['keyword_found_data']}")
```

## Files Added/Modified

### New Files
- `ecoopen/llm_extractor.py` - Core LLM extraction engine
- `requirements_llm.txt` - LLM dependencies
- `test_llm_extraction.py` - LLM functionality tests
- `test_basic_integration.py` - Integration verification
- `ecoopen_llm_app.py` - Streamlit web interface

### Modified Files
- `ecoopen/ecoopen.py` - Enhanced with LLM integration
- `ecoopen/__init__.py` - Updated exports for LLM functionality

## Installation and Setup

### 1. Basic Package (Keyword-only)
```bash
# Already works with existing installation
pip install -e .
```

### 2. LLM Functionality
```bash
# Install LLM dependencies
pip install -r requirements_llm.txt

# Install and start Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama run phi4
ollama run nomic-embed-text
```

### 3. Verify Installation
```bash
python test_basic_integration.py
python test_llm_extraction.py  # If LLM deps installed
```

## Web Interface

A Streamlit app provides an intuitive interface for analyzing papers:

```bash
streamlit run ecoopen_llm_app.py
```

Features:
- Upload PDF files for analysis
- Choose extraction method (keyword/LLM/both)
- Compare results side-by-side
- Download analysis results as JSON

## LLM Output Structure

The LLM extraction returns detailed, structured information:

```json
{
  "extraction_method": "LLM",
  "model_info": {
    "llm_model": "phi4",
    "embedding_model": "nomic-embed-text"
  },
  "availability_info": {
    "data_availability": {
      "found": true,
      "statements": ["Data are available at..."],
      "confidence": "high",
      "access_type": "open",
      "repositories": ["Zenodo"],
      "urls": ["https://zenodo.org/..."]
    },
    "code_availability": {
      "found": true,
      "statements": ["Code is available on GitHub..."],
      "confidence": "medium",
      "access_type": "open",
      "repositories": ["GitHub"],
      "urls": ["https://github.com/..."]
    },
    "overall_assessment": {
      "data_openly_available": true,
      "code_openly_available": true,
      "confidence": "high",
      "summary": "Both data and code are openly available"
    }
  }
}
```

## Advantages of LLM Approach

1. **Context Understanding**: Can understand nuanced language and context
2. **Section Awareness**: Identifies relevant sections automatically
3. **Confidence Scoring**: Provides confidence levels for detections
4. **Access Type Classification**: Distinguishes between open/restricted/upon-request
5. **Repository Recognition**: Identifies specific data repositories
6. **Flexible Detection**: Catches variations in wording and phrasing

## Performance Considerations

- **Speed**: LLM extraction is slower than keyword matching
- **Resources**: Requires Ollama server and vector database
- **Accuracy**: Generally higher precision and recall than keywords
- **Scalability**: Good for batch processing with proper resource allocation

## Testing and Validation

### Test Files
- `test_basic_integration.py` - Verifies package structure and imports
- `test_llm_extraction.py` - Tests LLM functionality with sample PDFs

### Validation Approach
- Compare against existing keyword-based results
- Manual verification of LLM detections
- Performance metrics (precision, recall, F1-score)

## Future Enhancements

1. **Model Selection**: Support for different LLM models
2. **Fine-tuning**: Domain-specific model training
3. **Caching**: Vector store persistence for faster reprocessing
4. **Batch Processing**: Optimized pipeline for large document sets
5. **API Integration**: Cloud-based LLM services (OpenAI, Anthropic)

## Backward Compatibility

The rework maintains full backward compatibility:
- All existing functions work unchanged
- Default behavior remains keyword-based
- LLM functionality is optional and gracefully disabled if dependencies missing

## Conclusion

This LLM rework significantly enhances EcoOpen's capabilities while maintaining its ease of use and reliability. The dual-method approach allows users to choose the best extraction method for their needs, while the comparison mode provides insights into the strengths of each approach.

The implementation is production-ready and provides a solid foundation for future enhancements and research applications.
