"""repair and clean (SPEC §5)."""

import json
import shutil
import time
from pathlib import Path
from typing import Any

from rl.exitcodes import ConfigError
from rl.stage import derive_stage
from rl.state import STEPS

INTERMEDIATES = (
    "audio/items",
    "audio/work",
    "visual/frames",
    "visual/ring_base.mp4",
    "visual/ring_loop.mp4",
    "final/qc",
)


def repair(job: Path) -> dict[str, Any]:
    """Quarantine unreadable state files so the next run can continue.

    A quarantined file can hold provider job ids; those generations are not lost on the
    provider side but cannot be resumed, so the report asks the user to check dashboards.
    """
    quarantined = []
    for step in STEPS:
        path = job / "state" / f"{step}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                continue
        except json.JSONDecodeError:
            pass
        target = path.with_name(f"{step}.corrupt-{int(time.time())}.json")
        path.rename(target)
        quarantined.append(step)
    note = (
        "Quarantined steps restart from scratch. If they had jobs in progress, check the "
        "provider dashboards before re-running to avoid paying twice."
        if quarantined
        else "State is readable; nothing to repair."
    )
    return {"quarantined": quarantined, "note": note}


def clean(job: Path, *, keep_final: bool, force: bool) -> dict[str, Any]:
    stage = derive_stage(job)
    if stage not in ("delivered", "uploaded") and not force:
        raise ConfigError(
            f"The job is '{stage}', not delivered: its intermediates (already paid for) "
            "may still be needed.",
            hint="Finish the job first, or pass --force if the user agrees to lose them.",
        )
    removed, freed = [], 0
    targets = list(INTERMEDIATES) + ["visual/clip_*.mp4", "audio/*.partial.*"]
    if not keep_final:
        targets.append("final/video.mp4")
    for pattern in targets:
        for path in job.glob(pattern):
            size = (
                sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
                if path.is_dir()
                else path.stat().st_size
            )
            shutil.rmtree(path) if path.is_dir() else path.unlink()
            removed.append(str(path.relative_to(job)))
            freed += size
    return {"removed": removed, "freed_mb": round(freed / 1e6, 1)}
