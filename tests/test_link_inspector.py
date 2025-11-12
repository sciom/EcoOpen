from app.services.link_inspector import LinkInspector, LinkInfo


def test_link_inspector_normalize_and_dedupe():
    insp = LinkInspector()
    urls = [
        "www.github.com/user/repo",
        "https://github.com/user/repo",
        "http://zenodo.org/record/12345),",
        "not-a-url",
    ]
    infos = insp.inspect(urls)
    # Should normalize www. -> https:// and strip trailing punct, dedupe github
    urls_out = [i.url for i in infos]
    assert "https://github.com/user/repo" in urls_out
    # Normalizer does not upgrade http->https or strip www if already part of URL after prefixing
    assert "http://zenodo.org/record/12345" in urls_out
    assert all(u.startswith("http") for u in urls_out)



def test_link_inspector_classification():
    insp = LinkInspector()
    urls = [
        "https://zenodo.org/record/999",
        "https://github.com/user/repo",
        "https://example.org/other",
    ]
    infos = insp.inspect(urls)
    kinds = {i.url: i.kind for i in infos}
    assert kinds["https://zenodo.org/record/999"] == "data"
    assert kinds["https://github.com/user/repo"] == "code"
    assert kinds["https://example.org/other"] == "other"


def test_link_inspector_split_kinds():
    insp = LinkInspector()
    infos = insp.inspect([
        "https://zenodo.org/record/1",
        "https://github.com/a/b",
        "https://example.com/x",
    ])
    data, code, other = insp.split_kinds(infos)
    assert data == ["https://zenodo.org/record/1"]
    assert code == ["https://github.com/a/b"]
    assert other == ["https://example.com/x"]
