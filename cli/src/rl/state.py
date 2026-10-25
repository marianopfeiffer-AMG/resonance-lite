"""Per-step state files written only by rlite.

One JSON file per step keeps parallel steps (audio and visual) from overwriting each other.
Every write happens under an exclusive flock and lands atomically via tmp file + os.replace.
"""

import fcntl
import json
import os
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rl.exitcodes import StateCorrupt

STEPS = ("validate", "still", "audio", "visual", "build", "qc", "upload", "approval", "cost")

State = dict[str, Any]


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class StateStore:
    """Read and atomically update the state files of one job."""

    def __init__(self, job_dir: Path) -> None:
        self.dir = job_dir / "state"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, step: str) -> Path:
        if step not in STEPS:
            raise ValueError(f"Unknown state step: {step}")
        return self.dir / f"{step}.json"

    @contextmanager
    def _write_lock(self, step: str) -> Iterator[None]:
        fd = os.open(self.dir / f"{step}.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def read(self, step: str) -> State:
        """Return the step state, or an empty dict if the step never ran."""
        path = self._path(step)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StateCorrupt(
                f"State file is corrupt: {path.name}", hint="Run `rlite repair <job>`."
            ) from exc
        if not isinstance(data, dict):
            raise StateCorrupt(f"State file is not an object: {path.name}")
        return data

    def update(self, step: str, mutate: Callable[[State], None]) -> State:
        """Read-modify-write a step state under its lock; returns the new state."""
        with self._write_lock(step):
            state = self.read(step)
            mutate(state)
            state["updated"] = now_iso()
            self._atomic_write(self._path(step), state)
            return state

    def replace(self, step: str, state: State) -> State:
        """Overwrite a step state atomically."""

        def _set(current: State) -> None:
            current.clear()
            current.update(state)

        return self.update(step, _set)

    @staticmethod
    def _atomic_write(path: Path, data: State) -> None:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
