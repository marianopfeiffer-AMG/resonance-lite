"""Job stage derived from state files (never stored separately, so it cannot drift)."""

from pathlib import Path

from rl.exitcodes import NeedsApproval
from rl.hashing import plan_hash
from rl.plan import Plan, load_plan
from rl.state import StateStore

PRODUCTION_STEPS = ("audio", "visual", "build")


def derive_stage(job_dir: Path, plan: Plan | None = None) -> str:
    plan = plan if plan is not None else load_plan(job_dir)
    store = StateStore(job_dir)
    status = {step: store.read(step).get("status") for step in (*PRODUCTION_STEPS, "qc", "upload")}

    if status["upload"] == "done":
        return "uploaded"
    if status["build"] == "done":
        qc = store.read("qc")
        return "delivered" if qc.get("status") == "done" and qc.get("passed") else "built"
    if any(status[s] == "failed" for s in PRODUCTION_STEPS):
        return "failed"
    if any(status[s] in ("running", "done") for s in PRODUCTION_STEPS):
        return "producing"

    current = plan_hash(plan)
    if _approval_matches(store, current):
        return "approved"
    validated = store.read("validate")
    if validated.get("ok") and validated.get("plan_hash") == current:
        return "still_ready" if store.read("still").get("status") == "done" else "validated"
    return "draft"


def _approval_matches(store: StateStore, current_plan_hash: str) -> bool:
    approval = store.read("approval")
    still = store.read("still")
    return (
        bool(approval)
        and approval.get("plan_hash") == current_plan_hash
        and approval.get("still_sha256") == still.get("sha256")
    )


def require_approval(job_dir: Path, plan: Plan) -> None:
    """Raise unless the current plan and still are the ones the user approved."""
    if not _approval_matches(StateStore(job_dir), plan_hash(plan)):
        raise NeedsApproval(
            "The plan or the still changed since the user approved it (or it was never approved).",
            hint="Show the checkpoint to the user again, then run `rlite approve <job>`.",
        )
