import types
import httpx
import pytest

from app.services.llm_client import HttpLLMClient, ChatMessage
from app.services.agent import EndpointEmbeddings


class _FakeResponse:
    def __init__(self, status_code: int, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


class _FakeClient:
    def __init__(self, side_effects):
        self._effects = list(side_effects)
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json=None, headers=None):
        self.calls += 1
        eff = self._effects.pop(0)
        if isinstance(eff, BaseException):
            raise eff
        return eff


def _patch_httpx_client(monkeypatch, side_effects):
    fake = _FakeClient(side_effects)

    def _fake_ctor(*args, **kwargs):
        return fake

    monkeypatch.setattr(httpx, "Client", _fake_ctor)
    return fake


def _patch_sleep(monkeypatch):
    calls = {"count": 0, "delays": []}

    def _fake_sleep(s):
        calls["count"] += 1
        calls["delays"].append(s)

    import time
    monkeypatch.setattr(time, "sleep", _fake_sleep)
    return calls


def test_http_llm_client_retries_then_succeeds(monkeypatch):
    sleep_calls = _patch_sleep(monkeypatch)
    ok_payload = {"choices": [{"message": {"content": " hello world "}}]}
    fake = _patch_httpx_client(monkeypatch, [
        _FakeResponse(429, text="busy"),
        _FakeResponse(200, json_data=ok_payload),
    ])

    client = HttpLLMClient(base_url="http://example.com/v1", api_key=None, model="gpt-x")
    out = client.chat_complete([ChatMessage(role="user", content="hi")])
    assert out == "hello world"
    assert fake.calls == 2
    # One backoff sleep should have occurred (0.5)
    assert sleep_calls["count"] >= 1
    assert 0.5 in sleep_calls["delays"]


def test_http_llm_client_timeout_then_succeeds(monkeypatch):
    sleep_calls = _patch_sleep(monkeypatch)
    ok_payload = {"choices": [{"message": {"content": "ok"}}]}
    fake = _patch_httpx_client(monkeypatch, [
        httpx.TimeoutException("timeout"),
        _FakeResponse(200, json_data=ok_payload),
    ])

    client = HttpLLMClient(base_url="http://example.com/v1", api_key=None, model="gpt-x")
    out = client.chat_complete([ChatMessage(role="user", content="hi")])
    assert out == "ok"
    assert fake.calls == 2
    assert sleep_calls["count"] >= 1


def test_embeddings_retries_then_succeeds(monkeypatch):
    sleep_calls = _patch_sleep(monkeypatch)
    ok_payload = {"data": [{"embedding": [0.1, 0.2]}]}
    fake = _patch_httpx_client(monkeypatch, [
        _FakeResponse(500, text="oops"),
        _FakeResponse(200, json_data=ok_payload),
    ])

    emb = EndpointEmbeddings(base_url="http://example.com/v1", api_key=None, model="embed-x")
    vecs = emb.embed_documents(["hello"])
    assert vecs == [[0.1, 0.2]]
    assert fake.calls == 2
    assert sleep_calls["count"] >= 1
