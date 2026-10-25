"""Per-step locks. flock is released by the kernel when the process dies, so no stale locks."""

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from rl.exitcodes import LockedError


@contextmanager
def step_lock(job_dir: Path, step: str) -> Iterator[None]:
    """Hold an exclusive, non-blocking lock for a long-running step of one job."""
    state_dir = job_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(state_dir / f"{step}.run.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LockedError(
                f"Another rlite process is already running step '{step}' for this job.",
                hint="Check progress with `rlite status <job>`.",
            ) from exc
        yield
    finally:
        os.close(fd)
