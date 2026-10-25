"""ElevenLabs: sound effects (ambient) and music. Synchronous, so NOT resumable (SPEC §7.0)."""

from pathlib import Path
from typing import Any

import requests

from rl.exitcodes import ConfigError, ProviderError, QuotaExhausted
from rl.providers.base import MIN_AUDIO_BYTES, with_backoff
from rl.secrets import get_secret, mask

API = "https://api.elevenlabs.io"
MUSIC_MIN_MS, MUSIC_MAX_MS = 3_000, 600_000  # /v1/music limits (docs, 2026-10)
SFX_TIMEOUT_S, MUSIC_TIMEOUT_S = 180, 900


class ElevenLabs:
    resumable = False

    def __init__(self, api_key: str | None = None, session: requests.Session | None = None) -> None:
        self._key = api_key
        self._http = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        return {
            "xi-api-key": self._key or get_secret("elevenlabs"),
            "Content-Type": "application/json",
        }

    def _post_audio(self, path: str, payload: dict[str, Any], out: Path, timeout: float) -> Path:
        try:
            resp = with_backoff(
                lambda: self._http.post(
                    API + path, json=payload, headers=self._headers(), timeout=timeout
                )
            )
        except requests.Timeout as exc:
            # The call may have been charged; never retry automatically.
            raise ProviderError(
                "ElevenLabs did not answer in time; the call may have been charged.",
                retryable=False,
            ) from exc
        except requests.ConnectionError as exc:
            raise ProviderError("Could not reach ElevenLabs.", retryable=True) from exc
        self._raise_for_error(resp)
        body = resp.content
        if len(body) < MIN_AUDIO_BYTES or body[:1] == b"{":
            raise ProviderError(
                "ElevenLabs returned an error instead of audio: "
                + mask(body[:200].decode("utf-8", "ignore"))
            )
        partial = out.with_suffix(out.suffix + ".partial")
        partial.write_bytes(body)
        partial.replace(out)
        return out

    @staticmethod
    def _raise_for_error(resp: requests.Response) -> None:
        if resp.status_code == 200:
            return
        text = mask(resp.text[:300])
        if resp.status_code == 401:
            raise ConfigError(
                "ElevenLabs rejected the API key.",
                hint="Open a separate terminal and run: rlite key set elevenlabs",
            )
        if "quota_exceeded" in text or resp.status_code == 402:
            raise QuotaExhausted(
                "ElevenLabs credits are exhausted for this billing period.",
                hint="Top up or upgrade the ElevenLabs plan, then resume the job.",
            )
        retryable = resp.status_code in (429, 500, 502, 503, 504)
        raise ProviderError(f"ElevenLabs HTTP {resp.status_code}: {text}", retryable=retryable)

    def generate_sfx(self, prompt: str, seconds: float, out: Path, *, loop: bool = True) -> Path:
        payload = {
            "text": prompt,
            "duration_seconds": seconds,
            "prompt_influence": 0.6,
            "loop": loop,
        }
        return self._post_audio("/v1/sound-generation", payload, out, SFX_TIMEOUT_S)

    def generate_music(
        self, prompt: str, seconds: int, out: Path, *, instrumental: bool = True
    ) -> Path:
        ms = max(MUSIC_MIN_MS, min(int(seconds * 1000), MUSIC_MAX_MS))
        payload = {"prompt": prompt, "music_length_ms": ms, "force_instrumental": instrumental}
        return self._post_audio(
            "/v1/music?output_format=mp3_44100_192", payload, out, MUSIC_TIMEOUT_S
        )

    def remaining_credits(self) -> int | None:
        """Approximate remaining credits (character_limit - character_count), or None."""
        try:
            resp = self._http.get(
                API + "/v1/user/subscription", headers=self._headers(), timeout=20
            )
        except requests.RequestException:
            return None
        if resp.status_code != 200:
            self._raise_for_error(resp)
        data = resp.json()
        try:
            return int(data["character_limit"]) - int(data["character_count"])
        except (KeyError, TypeError, ValueError):
            return None
