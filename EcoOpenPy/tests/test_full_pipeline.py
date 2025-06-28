from ecoopen import full_pipeline_search_and_extract

def test_full_pipeline_search_and_extract():
    # Use a simple, broad query to ensure results (e.g., 'climate change')
    query = "climate change"
    results = full_pipeline_search_and_extract(query, top_n=3, save_pdfs=False)
    assert isinstance(results, list)
    assert len(results) > 0
    # Find the first result with extraction output
    valid = [r for r in results if isinstance(r.get("extraction"), dict)]
    assert valid, "No valid extraction results found."
    first = valid[0]
    assert "doi" in first
    assert "title" in first
    assert "extraction" in first
    # Check that at least one extraction field is present and is a list or str
    assert any(isinstance(first["extraction"].get(k), (list, str)) for k in ["data_urls", "code_urls", "dois", "accessions", "data_statements", "code_statements"])
    print("Test passed: full_pipeline_search_and_extract")

if __name__ == "__main__":
    test_full_pipeline_search_and_extract()
