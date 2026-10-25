import json
import multiprocessing
from pathlib import Path

import pytest
from conftest import load_example

from rl.exitcodes import LockedError, NeedsApproval, StateCorrupt
from rl.hashing import clip_hash, plan_hash, still_hash
from rl.locks import step_lock
from rl.stage import derive_stage, require_approval
from rl.state import StateStore


def _increment(job_dir: str, n: int) -> None:
    store = StateStore(Path(job_dir))
    for _ in range(n):
        store.update("cost", lambda s: s.__setitem__("count", s.get("count", 0) + 1))


def test_concurrent_updates_do_not_lose_writes(tmp_path: Path) -> None:
    ctx = multiprocessing.get_context("spawn")
    procs = [ctx.Process(target=_increment, args=(str(tmp_path), 50)) for _ in range(4)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    assert StateStore(tmp_path).read("cost")["count"] == 200


def test_corrupt_state_raises(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    (tmp_path / "state" / "audio.json").write_text("{not json")
    with pytest.raises(StateCorrupt):
        store.read("audio")


def test_unknown_step_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        StateStore(tmp_path).read("steps")


def test_step_lock_is_exclusive(tmp_path: Path) -> None:
    with step_lock(tmp_path, "audio"):
        with pytest.raises(LockedError), step_lock(tmp_path, "audio"):
            pass
        with step_lock(tmp_path, "visual"):
            pass  # different steps never block each other


def test_clip_hash_cascades_from_still() -> None:
    a = clip_hash("rain moves", "kling3_0", "pro", start_sha="aaa")
    b = clip_hash("rain moves", "kling3_0", "pro", start_sha="bbb")
    assert a != b
    assert still_hash({"image_prompt": "x"}, "nano_banana_2", "2k") == still_hash(
        {"image_prompt": "x", "motion_prompt": "ignored"}, "nano_banana_2", "2k"
    )


def _job(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    plan = load_example("ambient")
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    return tmp_path, plan


def test_stage_progression(tmp_path: Path) -> None:
    job, plan = _job(tmp_path)
    store = StateStore(job)
    assert derive_stage(job) == "draft"
    store.replace("validate", {"ok": True, "plan_hash": plan_hash(plan)})
    assert derive_stage(job) == "validated"
    store.replace("still", {"status": "done", "sha256": "s1"})
    assert derive_stage(job) == "still_ready"
    with pytest.raises(NeedsApproval):
        require_approval(job, plan)
    store.replace("approval", {"plan_hash": plan_hash(plan), "still_sha256": "s1"})
    assert derive_stage(job) == "approved"
    require_approval(job, plan)
    store.replace("audio", {"status": "running"})
    assert derive_stage(job) == "producing"
    store.replace("visual", {"status": "failed"})
    assert derive_stage(job) == "failed"
    store.replace("build", {"status": "done"})
    store.replace("qc", {"status": "done", "passed": True})
    assert derive_stage(job) == "delivered"


def test_editing_plan_after_approval_requires_new_approval(tmp_path: Path) -> None:
    job, plan = _job(tmp_path)
    store = StateStore(job)
    store.replace("still", {"status": "done", "sha256": "s1"})
    store.replace("approval", {"plan_hash": plan_hash(plan), "still_sha256": "s1"})
    plan["concept"] = "changed"
    with pytest.raises(NeedsApproval):
        require_approval(job, plan)
