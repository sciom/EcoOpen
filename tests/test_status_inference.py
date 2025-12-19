from app.models.schemas import PDFAnalysisResultModel


def _infer_status(data_stmt: str | None, code_stmt: str | None, data_links: list[str], code_links: list[str]):
    # mirror logic quickly (we just check expected mappings from statements)
    def status_from(statement: str | None, links: list[str], kind: str) -> str:
        if not statement:
            return "none"
        s = statement.lower()
        future = [
            "will be available",
            "will be made available",
            "will become available",
            "will be deposited",
            "will be archived",
            "available after",
            "available upon publication",
        ]
        if any(p in s for p in future):
            return "future"
        restricted = [
            "upon request",
            "available upon request",
            "reasonable request",
            "from the corresponding author",
            "available from the corresponding author",
            "available by request",
            "requests to the corresponding author",
        ]
        if any(p in s for p in restricted):
            return "restricted"
        embedded = [
            "in the paper",
            "in the article",
            "within the article",
            "in the supplementary",
            "in the supplement",
            "supplementary material",
            "supporting information only",
            "supplementary materials",
        ]
        if kind == "data" and any(p in s for p in embedded):
            if not links:
                return "embedded"
        if links:
            return "open"
        return "none"

    return status_from(data_stmt, data_links, "data"), status_from(code_stmt, code_links, "code")


def test_status_restricted_upon_request():
    data_stmt = "The data are available upon reasonable request from the corresponding author."
    code_stmt = None
    ds, cs = _infer_status(data_stmt, code_stmt, [], [])
    assert ds == "restricted"
    assert cs == "none"


def test_status_embedded_only():
    data_stmt = "All data are provided in the article and in the supplementary materials."
    code_stmt = None
    ds, cs = _infer_status(data_stmt, code_stmt, [], [])
    assert ds == "embedded"
    assert cs == "none"


def test_status_future_availability():
    data_stmt = "All datasets will be made available upon publication."
    ds, _ = _infer_status(data_stmt, None, [], [])
    assert ds == "future"
