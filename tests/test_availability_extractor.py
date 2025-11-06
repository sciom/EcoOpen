import json

from app.services.availability import AvailabilityEngine


def _engine() -> AvailabilityEngine:
    return AvailabilityEngine(
        data_allowed_domains=[
            "zenodo.org",
            "osf.io",
            "datadryad.org",
        ],
        code_allowed_domains=[
            "github.com",
            "gitlab.com",
        ],
        deny_substrings=["orcid.org", "urldefense.com"],
        dataset_doi_prefixes=["10.5281"],
        max_contexts=4,
    )


def test_extract_statements_with_headings():
    pages = [
        "\nIntroduction text\n\nDATA AVAILABILITY\nAll data supporting this article are available at "
        "https://zenodo.org/record/7010687 and archived under DOI 10.5281/zenodo.7010687. "
        "See author profiles at https://orcid.org/0000-0001.\n\n"
        "CODE AVAILABILITY\nAnalysis scripts are released on GitHub: https://github.com/example/repo.",
    ]
    engine = _engine()

    def fake_chat(system: str, prompt: str) -> str:
        assert "CONTEXTS" in prompt
        return json.dumps(
            {
                "data": {
                    "verdict": "present",
                    "raw_quote": "All data supporting this article are available at https://zenodo.org/record/7010687.",
                    "clean_statement": "All data supporting this article are available at https://zenodo.org/record/7010687.",
                    "links": ["https://zenodo.org/record/7010687", "https://orcid.org/0000-0001-9040-9296"],
                    "confidence": 0.85,
                },
                "code": {
                    "verdict": "present",
                    "raw_quote": "Analysis scripts are released on GitHub: https://github.com/example/repo.",
                    "clean_statement": "Analysis scripts are released on GitHub: https://github.com/example/repo.",
                    "links": ["https://github.com/example/repo"],
                    "confidence": 0.7,
                },
            }
        )

    result = engine.extract(pages, chat_fn=fake_chat, diagnostics=True)

    assert result.data_statement is not None
    assert "All data supporting this article" in result.data_statement
    assert result.code_statement is not None
    assert "Analysis scripts are released" in result.code_statement

    # Links: zenodo kept, ORCID removed, GitHub kept
    assert result.data_links == ["https://zenodo.org/record/7010687"]
    assert result.code_links == ["https://github.com/example/repo"]
    assert result.data_confidence > 0.5
    assert result.code_confidence > 0.5
    assert "llm_raw" in result.diagnostics


def test_extract_statements_without_headings():
    pages = [
        "The data are available upon reasonable request and have been deposited at https://osf.io/abcd/ "
        "under accession 10.5281/zenodo.9999. The analysis code is available at "
        "https://gitlab.com/example/project with documentation.",
    ]
    engine = _engine()

    # Force LLM failure to trigger fallback path
    def bad_chat(system: str, prompt: str) -> str:
        return "not-json"

    result = engine.extract(pages, chat_fn=bad_chat, diagnostics=False)

    assert result.data_statement is not None
    assert "data are available" in result.data_statement.lower()
    assert result.code_statement is not None
    assert "analysis code" in result.code_statement.lower()
    assert "https://osf.io/abcd/" in result.data_links
    assert "https://gitlab.com/example/project" in result.code_links
    # Fallback confidence should be modest
    assert 0.0 <= result.data_confidence <= 0.7


def test_heading_only_does_not_return_statement():
    pages = [
        "Data availability:",
        "Acknowledgements The authors thank everyone.",
    ]
    engine = _engine()

    def empty_chat(system: str, prompt: str) -> str:
        return ""

    result = engine.extract(pages, chat_fn=empty_chat, diagnostics=False)
    assert result.data_statement is None
