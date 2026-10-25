"""Per-call budget enforcement (SPEC §8).

Every paid call reserves its estimated cost first. The reservation is checked against the
per-job and per-month caps (in USD) and stays counted until it is committed or released, so
a call that never returns (non-resumable provider, timeout) still counts as spent.

This is a brake against accidents (an expensive plan, a retry loop), not a vault: raising the
cap requires a typed confirmation on a real terminal and is always logged.
"""

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rl.config import budget_limits
from rl.exitcodes import BudgetExceeded, ConfigError
from rl.paths import jobs_dir
from rl.state import State, StateStore, now_iso


def _month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def _job_total(state: State) -> float:
    return sum(float(e["usd"]) for e in state.get("entries", []) if e["status"] != "released")


def _month_total(month: str) -> float:
    root = jobs_dir()
    if not root.is_dir():
        return 0.0
    total = 0.0
    for job in root.iterdir():
        if not (job / "state" / "cost.json").exists():
            continue
        for entry in StateStore(job).read("cost").get("entries", []):
            if entry["status"] != "released" and entry["month"] == month:
                total += float(entry["usd"])
    return total


class Budget:
    """Budget ledger of one job (state/cost.json)."""

    def __init__(self, job_dir: Path) -> None:
        self.job_dir = job_dir
        self.store = StateStore(job_dir)

    def reserve(self, provider: str, usd: float, label: str) -> str:
        """Reserve the estimated cost of one paid call, or raise BudgetExceeded."""
        limits = budget_limits()
        month = _month()
        reservation = uuid.uuid4().hex[:12]

        def _apply(state: State) -> None:
            job_cap = limits["per_job_usd"] + float(state.get("extra_allowance_usd", 0.0))
            job_total = _job_total(state)
            if job_total + usd > job_cap:
                raise BudgetExceeded(
                    f"This call (~USD {usd:.2f}, {label}) would take the job to "
                    f"USD {job_total + usd:.2f}, over its cap of USD {job_cap:.2f}.",
                    hint="Ask the user. Only they can raise it, in their own terminal: "
                    "rlite budget allow <job> --usd <amount>",
                )
            month_total = _month_total(month)
            if month_total + usd > limits["per_month_usd"]:
                raise BudgetExceeded(
                    f"This call would take this month's spend to USD {month_total + usd:.2f}, "
                    f"over the monthly cap of USD {limits['per_month_usd']:.2f}.",
                    hint="The user can change budget.per_month_usd in channel.yaml.",
                )
            state.setdefault("entries", []).append(
                {
                    "id": reservation,
                    "provider": provider,
                    "label": label,
                    "usd": round(usd, 4),
                    "status": "reserved",
                    "month": month,
                    "at": now_iso(),
                }
            )

        self.store.update("cost", _apply)
        return reservation

    def commit(self, reservation: str, usd: float | None = None) -> None:
        """Mark a reservation as spent, optionally with the actual cost."""
        self._set(reservation, "spent", usd)

    def release(self, reservation: str) -> None:
        """Cancel a reservation for a call that provably did not charge."""
        self._set(reservation, "released", None)

    def _set(self, reservation: str, status: str, usd: float | None) -> None:
        def _apply(state: State) -> None:
            for entry in state.get("entries", []):
                if entry["id"] == reservation:
                    entry["status"] = status
                    if usd is not None:
                        entry["usd"] = round(usd, 4)
                    return
            raise KeyError(reservation)

        self.store.update("cost", _apply)

    def summary(self) -> dict[str, Any]:
        state = self.store.read("cost")
        limits = budget_limits()
        return {
            "job_usd": round(_job_total(state), 2),
            "job_cap_usd": limits["per_job_usd"] + float(state.get("extra_allowance_usd", 0.0)),
            "month_usd": round(_month_total(_month()), 2),
            "month_cap_usd": limits["per_month_usd"],
        }

    def allow_extra(self, usd: float) -> None:
        """Raise this job's cap. Requires a typed confirmation on a real terminal."""
        if not sys.stdin.isatty():
            raise ConfigError(
                "Raising a budget needs the user's confirmation in their own terminal.",
                hint="Ask the user to run this command themselves in a separate terminal.",
            )
        answer = input(f"Type 'allow {usd:g}' to raise this job's budget by USD {usd:g}: ")
        if answer.strip() != f"allow {usd:g}":
            raise ConfigError("Confirmation did not match; budget unchanged.")

        def _apply(state: State) -> None:
            state["extra_allowance_usd"] = float(state.get("extra_allowance_usd", 0.0)) + usd
            state.setdefault("allowance_log", []).append({"usd": usd, "at": now_iso()})

        self.store.update("cost", _apply)
