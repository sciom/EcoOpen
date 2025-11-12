from app.services.title_resolver import TitleResolver, TitleResolution
from app.services.text_normalizer import ParagraphBlock


def _block(text: str, page: int = 1, column: int = 0, seq: int = 0) -> ParagraphBlock:
    return ParagraphBlock(text=text, page=page, column=column, seq=seq)


def test_title_resolver_single_line():
    blocks = [
        _block("Deep Learning for Ecological Forecasting"),
        _block("Abstract"),
    ]
    r = TitleResolver().resolve(blocks)
    assert isinstance(r, TitleResolution)
    assert r.title == "Deep Learning for Ecological Forecasting"
    assert r.source == "heuristic"
    assert r.confidence >= 0.5


def test_title_resolver_multi_line_merge():
    blocks = [
        _block("Climate Change Impacts"),
        _block("on Marine Biodiversity"),
        _block("and Conservation Strategies"),
        _block("Author Names"),  # should stop before this
    ]
    r = TitleResolver().resolve(blocks)
    assert r.title is not None
    assert r.title.startswith("Climate Change Impacts")
    # merged variants
    assert r.title in {
        "Climate Change Impacts",
        "Climate Change Impacts: on Marine Biodiversity",
        "Climate Change Impacts: on Marine Biodiversity: and Conservation Strategies",
        "Climate Change Impacts on Marine Biodiversity and Conservation Strategies",
    }


def test_title_resolver_rejects_bad():
    blocks = [
        _block("Abstract"),
        _block("Keywords"),
    ]
    r = TitleResolver().resolve(blocks)
    assert r.title is None
    assert r.confidence == 0.0
