import contextlib
import time
from typing import Dict, Iterator, Any


def _kv(ctx: Dict[str, Any]) -> str:
    parts = []
    for k, v in ctx.items():
        try:
            parts.append(f"{k}={v}")
        except Exception:
            parts.append(f"{k}=?")
    return " ".join(parts)


@contextlib.contextmanager
def log_timing(logger, op: str, **ctx: Any) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt_ms = int((time.perf_counter() - t0) * 1000)
        msg_ctx = {**ctx, "op": op, "duration_ms": dt_ms}
        logger.info(_kv(msg_ctx))
