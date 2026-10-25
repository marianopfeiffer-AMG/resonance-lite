"""Suno through Apiframe (unofficial, optional, off by default). Resumable by jobId."""

from typing import Any

import requests

from rl.exitcodes import ConfigError, ProviderError, QuotaExhausted
from rl.providers.base import BROWSER_UA, JobStatus, PollResult
from rl.secrets import get_secret, mask

API = "https://api.apiframe.ai"
SUBMIT_TIMEOUT_S, POLL_TIMEOUT_S = 60, 30


class Apiframe:
    resumable = True

    def __init__(self, api_key: str | None = None, session: requests.Session | None = None) -> None:
        self._key = api_key
        self._http = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        # Header goes through requests (never a process argv). Cloudflare blocks urllib's UA.
        return {
            "X-API-Key": self._key or get_secret("apiframe"),
            "Content-Type": "application/json",
            "User-Agent": BROWSER_UA,
        }

    def _check(self, resp: requests.Response) -> Any:
        if resp.status_code == 401:
            raise ConfigError(
                "Apiframe rejected the API key.", hint="Run in a terminal: rlite key set apiframe"
            )
        if resp.status_code == 402 or "insufficient" in resp.text.lower():
            raise QuotaExhausted(
                "Apiframe credits are exhausted.", hint="Top up Apiframe, then resume."
            )
        if resp.status_code == 403:
            raise ProviderError(
                "Apiframe blocked the request (Cloudflare 403/1010).", retryable=True
            )
        if resp.status_code >= 400:
            raise ProviderError(
                f"Apiframe HTTP {resp.status_code}: {mask(resp.text[:200])}",
                retryable=resp.status_code in (429, 500, 502, 503, 504),
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise ProviderError("Apiframe returned a non-JSON response.", retryable=True) from exc

    def submit(self, track: dict[str, Any], model_version: str = "V4_5PLUS") -> str:
        """Submit one track (2 takes). Never retried blindly: a timeout may have created a job."""
        instrumental = bool(track["instrumental"])
        payload = {
            # In custom mode `prompt` is the lyrics: instrumentals send "[Instrumental]", never the
            # style, or Suno may sing the style text.
            "prompt": "[Instrumental]" if instrumental else (track.get("lyrics") or ""),
            "model": "suno",
            "sunoParams": {
                "custom_mode": True,
                "instrumental": instrumental,
                "model_version": model_version,
                "title": track["title"],
                "style": track["style"],
                **({"vocal_gender": track["vocal_gender"]} if track.get("vocal_gender") else {}),
            },
        }
        try:
            resp = self._http.post(
                API + "/v2/music/generate",
                json=payload,
                headers=self._headers(),
                timeout=SUBMIT_TIMEOUT_S,
            )
        except requests.Timeout as exc:
            raise ProviderError(
                "Apiframe did not confirm the submission; a job may exist and be charged.",
                retryable=False,
            ) from exc
        except requests.ConnectionError as exc:
            raise ProviderError("Could not reach Apiframe.", retryable=True) from exc
        data = self._check(resp)
        job_id = data.get("jobId") if isinstance(data, dict) else None
        if not job_id:
            raise ProviderError("Apiframe did not return a jobId.")
        return str(job_id)

    def poll(self, job_id: str) -> PollResult:
        try:
            resp = self._http.get(
                f"{API}/v2/jobs/{job_id}", headers=self._headers(), timeout=POLL_TIMEOUT_S
            )
        except requests.RequestException as exc:
            raise ProviderError("Could not reach Apiframe while polling.", retryable=True) from exc
        data = self._check(resp)
        status = str(data.get("status", "")).upper()
        state: JobStatus = (
            "done" if status == "COMPLETED" else "failed" if status == "FAILED" else "running"
        )
        tracks = (data.get("result") or {}).get("tracks") or []
        urls = [t["audioUrl"] for t in tracks if isinstance(t, dict) and t.get("audioUrl")]
        return PollResult(
            status=state, urls=urls, error=data.get("error") if state == "failed" else None
        )
