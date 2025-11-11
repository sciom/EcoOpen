# EcoOpen Tests

This directory contains the test suite for EcoOpen.

## Test Categories

Tests are marked with pytest markers for selective execution:

- **unit**: Unit tests that don't require external dependencies (default, always run)
- **integration**: Integration tests requiring MongoDB, Ollama, or LLM endpoints
- **slow**: Tests that take significant time to complete

## Running Tests

### Run all non-integration tests (default)
```bash
pytest tests/ -v -m "not integration"
```

### Run all tests including integration tests
```bash
pytest tests/ -v
```

### Run only integration tests
```bash
pytest tests/ -v -m integration
```

### Run the full workflow test
```bash
pytest tests/test_workflow_full.py -v -s
```

## Full Workflow Test

The `test_workflow_full.py` test provides comprehensive assessment of the PDF analysis pipeline:

### What it does
1. Processes multiple example PDFs with known content
2. Measures performance metrics (processing time per document)
3. Validates extraction accuracy against expected results
4. Generates a detailed report with:
   - Success/failure rates
   - Extraction results (title, DOI, statements, links)
   - Accuracy validation per document
   - Performance statistics

### Requirements
The workflow test requires:
- Ollama running locally with `nomic-embed-text` model (`ollama pull nomic-embed-text`)
- A reachable LLM endpoint (configured via `AGENT_BASE_URL` in `.env`)
- Or: An OpenAI-compatible endpoint with embeddings support

### Example Output
```
================================================================================
FULL WORKFLOW TEST REPORT
================================================================================

Total Tests: 3
Successful: 3
Failed: 0
Success Rate: 100.0%
Total Duration: 45230ms (45.23s)

--------------------------------------------------------------------------------

Test 1: test_data_paper.pdf
  Status: ✓ PASS
  Duration: 15234ms
  Title: Machine Learning for Climate Prediction
  DOI: 10.1234/example.2024.001
  Data Statement: All datasets used in this study are publicly availab...
  Code Statement: None
  Data Links: 2
    - https://zenodo.org/record/123456
    - https://data.noaa.gov/dataset/climate-2024
  Code Links: 0
  Accuracy Validation:
    ✓ doi_match
    ✓ title_has_keywords
    ✓ has_data_statement
    ✓ data_links_count
    ✓ overall

--------------------------------------------------------------------------------
PERFORMANCE SUMMARY
--------------------------------------------------------------------------------
Average processing time: 15077ms (15.08s)
Fastest: 14823ms
Slowest: 15234ms

--------------------------------------------------------------------------------
ACCURACY SUMMARY
--------------------------------------------------------------------------------
Tests with expected results: 3/3
Accuracy Rate: 100.0%
================================================================================
```

### Headless Execution
The workflow test runs completely headless with no UI or user interaction required:
- No MongoDB database needed (uses AgentRunner directly)
- No API server needed (bypasses FastAPI layer)
- No browser or GUI required
- Can be run in CI/CD pipelines (will skip if services unavailable)

### Customizing Test PDFs
The example PDFs in `example_papers/` are generated test fixtures. To test with real papers:

1. Place PDF files in `example_papers/`
2. Update `test_workflow_full.py` to add new test cases with expected values
3. Run the test suite

## Test Data

### Example Papers
The `example_papers/` directory contains test PDF fixtures:
- `test_data_paper.pdf`: Paper with data availability statement and links
- `test_code_paper.pdf`: Paper with code availability statement and links
- `test_full_paper.pdf`: Paper with both data and code availability

These are synthetic papers created specifically for testing and are tracked in git.
