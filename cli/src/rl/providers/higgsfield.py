"""Higgsfield through its official CLI (user's own login). Resumable: jobs are polled by id."""

import json
import re
import subprocess
from collections.abc import Callable, Sequence
from typing import Any

from rl.exitcodes import ConfigError, ProviderError, QuotaExhausted
from rl.providers.base import JobStatus, PollResult

Runner = Callable[[Sequence[str], float], subprocess.CompletedProcess[str]]
TESTED_CLI = ((1, 1), (1, 99))  # inclusive range of tested major.minor versions
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_DONE = {"completed", "succeeded", "success"}
_FAILED = {"failed", "error", "canceled", "cancelled", "nsfw", "rejected"}


def _run(args: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["higgsfield", *args], capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError as exc:
        raise ConfigError(
            "The Higgsfield CLI is not installed.",
            hint="Install it (brew install higgsfield-ai/tap/higgsfield), "
            "then run: higgsfield auth login",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ProviderError("The Higgsfield CLI did not answer in time.", retryable=True) from exc


class Higgsfield:
    resumable = True

    def __init__(self, runner: Runner | None = None) -> None:
        self._run = runner or _run

    def _json(self, args: Sequence[str], timeout: float = 120) -> Any:
        proc = self._run([*args, "--json"], timeout)
        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            low = output.lower()
            if "expired" in low or "not logged in" in low or "unauthorized" in low:
                raise ConfigError(
                    "Your Higgsfield session expired.",
                    hint="Run in a terminal: higgsfield auth login",
                )
            if "insufficient" in low and "credit" in low:
                raise QuotaExhausted(
                    "Not enough Higgsfield credits.", hint="Top up Higgsfield, then resume."
                )
            raise ProviderError(
                f"higgsfield {' '.join(args[:2])} failed: {output[:300]}", retryable=False
            )
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Unexpected Higgsfield output: {proc.stdout[:200]}") from exc

    @staticmethod
    def _params(params: dict[str, str | int | float]) -> list[str]:
        out: list[str] = []
        for key, value in params.items():
            out += [f"--{key}", str(value)]
        return out

    def cost(self, model: str, params: dict[str, str | int | float]) -> float:
        """Credits a job would cost (does not create it or spend anything)."""
        data = self._json(["generate", "cost", model, *self._params(params)])
        return float(data["credits"])

    def submit(self, model: str, params: dict[str, str | int | float]) -> str:
        """Create a job and return its id.

        The caller must store the id BEFORE waiting, so a resume polls it instead of paying again.
        """
        data = self._json(["generate", "create", model, *self._params(params)])
        job = data[0] if isinstance(data, list) and data else data
        job_id = job.get("id") if isinstance(job, dict) else None
        if not job_id:
            match = _UUID.search(json.dumps(data))
            job_id = match.group(0) if match else None
        if not job_id:
            raise ProviderError("Higgsfield did not return a job id.")
        return str(job_id)

    def poll(self, job_id: str) -> PollResult:
        job = self._json(["generate", "get", job_id], timeout=60)
        status = str(job.get("status", "")).lower()
        state: JobStatus = (
            "done" if status in _DONE else "failed" if status in _FAILED else "running"
        )
        urls = [u for u in (job.get("result_url"),) if isinstance(u, str) and u]
        return PollResult(status=state, urls=urls, error=None if state != "failed" else status)

    def account(self) -> dict[str, Any]:
        """Credits and plan of the logged-in account. Never exposes or stores the email."""
        data = self._json(["account", "status"], timeout=30)
        return {"credits": data.get("credits"), "plan": data.get("subscription_plan_type")}

    def version(self) -> tuple[int, int] | None:
        proc = self._run(["--version"], 15)
        match = re.search(r"(\d+)\.(\d+)", proc.stdout or "")
        return (int(match.group(1)), int(match.group(2))) if match else None
