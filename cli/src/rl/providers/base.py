"""Shared provider types and HTTP helpers."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import requests

from rl.exitcodes import ProviderError

JobStatus = Literal["running", "done", "failed"]
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
MIN_AUDIO_BYTES = 2048


@dataclass
class PollResult:
    status: JobStatus
    urls: list[str] = field(default_factory=list)
    error: str | None = None


def download(url: str, out: Path, timeout: float = 300) -> Path:
    """Download to a .partial file and rename only when complete."""
    partial = out.with_suffix(out.suffix + ".partial")
    with requests.get(url, stream=True, timeout=timeout) as resp:
        if resp.status_code != 200:
            raise ProviderError(f"Download failed (HTTP {resp.status_code})", retryable=True)
        with partial.open("wb") as fh:
            for chunk in resp.iter_content(1 << 16):
                fh.write(chunk)
    partial.replace(out)
    return out


def with_backoff(
    call: Callable[[], requests.Response],
    *,
    attempts: int = 5,
    retry_status: tuple[int, ...] = (429, 500, 502, 503, 504),
    sleep: Callable[[float], None] = time.sleep,
) -> requests.Response:
    """Retry a request on rate limits and server errors (requests that were rejected, not run).

    Timeouts are NOT retried here: for non-resumable providers a timed-out call may already
    have been charged, so the caller decides.
    """
    resp = call()
    for attempt in range(1, attempts):
        if resp.status_code not in retry_status:
            break
        sleep(2**attempt)
        resp = call()
    return resp
