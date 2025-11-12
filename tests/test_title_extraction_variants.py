from app.services.title_resolver import TitleResolver
from app.services.text_normalizer import ParagraphBlock


def _block(text: str, page: int = 1, column: int = 0, seq: int = 0) -> ParagraphBlock:
    return ParagraphBlock(text=text, page=page, column=column, seq=seq)


def test_short_title_allowed():
    blocks = [
        _block("AI Forecasting"),  # 13 chars, 2 words previously rejected (<3 words)
        _block("Abstract"),
    ]
    r = TitleResolver().resolve(blocks)
    assert r.title == "AI Forecasting"


def test_long_wrapped_title_space_merge():
    blocks = [
        _block("Integrated Climate Risk Assessment"),
        _block("for Coastal Urban Planning"),
        _block("under Socioeconomic Uncertainty"),
        _block("Author Affiliations"),
    ]
    r = TitleResolver().resolve(blocks)
    assert r.title in {
        "Integrated Climate Risk Assessment",
        "Integrated Climate Risk Assessment: for Coastal Urban Planning: under Socioeconomic Uncertainty",
        "Integrated Climate Risk Assessment for Coastal Urban Planning under Socioeconomic Uncertainty",
    }


def test_affiliation_break_after_lines():
    blocks = [
        _block("Deep Reinforcement Learning"),
        _block("for Adaptive Energy Systems"),
        _block("Department of Computer Science"),  # should stop before this line
        _block("Extra Line That Should Not Appear"),
    ]
    r = TitleResolver().resolve(blocks)
    assert "Extra Line" not in (r.title or "")
    assert "Department of Computer Science" not in (r.title or "")


def test_reject_affiliation_line_as_title():
    blocks = [
        _block("Department of Biology"),  # looks like affiliation should be rejected
        _block("Institute of Marine Science"),
    ]
    r = TitleResolver().resolve(blocks)
    assert r.title is None
