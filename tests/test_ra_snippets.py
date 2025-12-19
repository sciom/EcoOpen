import re
from app.core.validation import validate_doi
from app.services.availability import AvailabilityEngine


def _engine() -> AvailabilityEngine:
    return AvailabilityEngine(
        data_allowed_domains=[
            "zenodo.org",
            "osf.io",
            "doi.org",
            "dx.doi.org",
            "datadryad.org",
        ],
        code_allowed_domains=[
            "github.com",
            "gitlab.com",
        ],
        deny_substrings=["orcid.org", "urldefense.com"],
        dataset_doi_prefixes=["10.5281", "10.5061", "10.17605"],
        max_contexts=4,
    )


def test_doi_trim_parenthetical_fragment():
    raw = "10.5061/dryad.q205m(Lucas-Barbosaetal.2015)."
    assert validate_doi(raw) == "10.5061/dryad.q205m"


def test_ra408_dryad_link_extracted_even_with_parentheses():
    pages = [
        "Data accessibility: data deposited in the Dryad Digital Repository: http://dx.doi.org/10.5061/dryad.q205m(Lucas-Barbosaetal.2015).",
    ]
    engine = _engine()

    def bad_chat(system: str, prompt: str) -> str:
        return ""

    result = engine.extract(pages, chat_fn=bad_chat, diagnostics=False)
    assert result.data_statement is not None
    assert any("doi.org/10.5061/dryad.q205m" in u for u in result.data_links)


def test_ra404_data_accessibility_with_link():
    pages = [
        "DATA ACCESSIBILITY\nThe data that support the findings are available at the Dryad Digital Repository (https://doi.org/10.5061/dryad.zcrjdfnd4).",
    ]
    engine = _engine()

    def bad_chat(system: str, prompt: str) -> str:
        return ""

    result = engine.extract(pages, chat_fn=bad_chat, diagnostics=False)
    assert result.data_statement is not None
    assert any("doi.org/10.5061/dryad.zcrjdfnd4" in u for u in result.data_links)


def test_ra401_genbank_statement_no_link():
    pages = [
        "Data accessibility All DNA sequences are available in GenBank database:",
    ]
    engine = _engine()

    def bad_chat(system: str, prompt: str) -> str:
        return ""

    result = engine.extract(pages, chat_fn=bad_chat, diagnostics=False)
    # Statement should be detected but without links
    assert result.data_statement is not None
    assert result.data_links == []
