from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import httpx
import logging
import time

from app.core.config import settings
from app.core.errors import LLMServiceError
from app.services import log_timing


logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    role: str
    content: str


class LLMClient:
    """Abstraction over LLM providers. Supports HTTP and (future) MCP backends."""

    def chat_complete(self, messages: List[ChatMessage], model: Optional[str] = None, temperature: float = 0.0) -> str:
        raise NotImplementedError


class HttpLLMClient(LLMClient):
    def __init__(self, base_url: str, api_key: Optional[str], model: str) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key or None
        self._model = model

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def _retry_delays(self) -> List[float]:
        return [0.5, 1.0, 2.0, 4.0]

    def chat_complete(self, messages: List[ChatMessage], model: Optional[str] = None, temperature: float = 0.0) -> str:
        m = model or self._model
        base = self._base
        try:
            base = base.removesuffix("/v1")
        except Exception:
            pass
        url = f"{base}/v1/chat/completions"
        payload = {
            "model": m,
            "messages": [{"role": x.role, "content": x.content} for x in messages],
            "temperature": temperature,
        }
        last_err: Optional[Exception] = None
        status_val: Optional[int] = None
        with log_timing(logger, op="http_llm_chat", model=m, base_url=self._base):
            for attempt, delay in enumerate([0.0] + self._retry_delays()):
                if delay:
                    time.sleep(delay)
                try:
                    with httpx.Client(timeout=float(settings.AGENT_TIMEOUT_SECONDS)) as client:
                        r = client.post(url, json=payload, headers=self._headers())
                        status_val = r.status_code
                        if 200 <= r.status_code < 300:
                            data = r.json()
                            if isinstance(data, dict) and "choices" in data:
                                try:
                                    content = data["choices"][0]["message"]["content"]
                                    return (content or "").strip()
                                except Exception:
                                    raise LLMServiceError("Invalid OpenAI response format")
                            raise LLMServiceError("Unexpected response: missing choices")
                        if r.status_code in (404, 405):
                            raise LLMServiceError("LLM endpoint /v1/chat/completions not found on AGENT_BASE_URL")
                        if r.status_code in (408, 429) or 500 <= r.status_code < 600:
                            last_err = LLMServiceError(f"LLM error {r.status_code}: {r.text[:200]}")
                            continue
                        body = r.text if r.text else ""
                        raise LLMServiceError(f"LLM error {r.status_code}: {body[:200]}")
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    last_err = LLMServiceError(f"LLM service unavailable: {e}")
                    continue
                except Exception as e:
                    last_err = LLMServiceError(f"LLM service error: {e}")
                    break
        assert last_err is not None
        raise last_err


class McpLLMClient(LLMClient):
    """Minimal JSON-RPC over WebSocket client to a local MCP-like server."""

    def __init__(self, server_url: str, tool_name: str, model: str) -> None:
        self._server_url = server_url
        self._tool = tool_name
        self._model = model

    def chat_complete(self, messages: List[ChatMessage], model: Optional[str] = None, temperature: float = 0.0) -> str:
        try:
            import asyncio
            import json
            import websockets

            async def _call():
                async with websockets.connect(self._server_url, open_timeout=5) as ws:
                    req = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": self._tool,
                        "params": {
                            "model": model or self._model,
                            "messages": [{"role": m.role, "content": m.content} for m in messages],
                            "temperature": temperature,
                        },
                    }
                    await ws.send(json.dumps(req))
                    raw = await ws.recv()
                    data = json.loads(raw)
                    if "error" in data and data["error"]:
                        raise LLMServiceError(str(data["error"]))
                    result = data.get("result")
                    if not isinstance(result, str):
                        raise LLMServiceError("Invalid MCP response: missing result string")
                    return result

            return asyncio.run(_call())
        except LLMServiceError:
            raise
        except Exception as e:
            raise LLMServiceError(f"MCP client error: {e}")


def get_llm_client() -> LLMClient:
    if settings.MCP_ENABLED:
        return McpLLMClient(settings.MCP_SERVER_URL, settings.MCP_TOOL_NAME, settings.AGENT_MODEL)
    return HttpLLMClient(settings.AGENT_BASE_URL, settings.AGENT_API_KEY, settings.AGENT_MODEL)

