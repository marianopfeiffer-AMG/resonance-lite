"""Orchestrated run (SPEC §3.2 steps 8-9): audio ∥ visual → build → qc.

`run --detach` starts the run in its own session so closing Claude Code (or the terminal)
does not kill paid work in progress; on macOS it also keeps the machine awake. Progress and a
heartbeat live in state/run.json; `rlite wait` polls it in short slices Claude can call.
"""

import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from rl.audio.step import AudioProviders, AudioStep
from rl.build import BuildStep
from rl.exitcodes import ExitCode, RlError
from rl.plan import Plan, load_plan
from rl.qc import run_qc
from rl.stage import require_approval
from rl.state import State, StateStore, now_iso
from rl.visual.step import VisualProviders, VisualStep

HEARTBEAT_S = 30
DEAD_AFTER_S = 120
ORDER = ("produce", "build", "qc")


def _heartbeat(store: StateStore, stop: threading.Event) -> None:
    while not stop.wait(HEARTBEAT_S):
        store.update("run", lambda s: s.update(heartbeat=time.time()))


def run_job(
    job: Path,
    plan: Plan | None = None,
    *,
    start_from: str = "produce",
    regen_stale: bool = False,
    audio_providers: AudioProviders | None = None,
    visual_providers: VisualProviders | None = None,
) -> State:
    plan = plan or load_plan(job)
    require_approval(job, plan)
    store = StateStore(job)
    store.replace(
        "run",
        {
            "status": "running",
            "pid": os.getpid(),
            "step": start_from,
            "started": now_iso(),
            "heartbeat": time.time(),
            "error": None,
        },
    )
    stop = threading.Event()
    beat = threading.Thread(target=_heartbeat, args=(store, stop), daemon=True)
    beat.start()
    try:
        steps = ORDER[ORDER.index(start_from) :]
        if "produce" in steps:
            _set_step(store, "produce")
            with ThreadPoolExecutor(max_workers=2) as pool:
                audio = pool.submit(
                    AudioStep(job, plan, audio_providers).run, regen_stale=regen_stale
                )
                visual = pool.submit(
                    VisualStep(job, plan, visual_providers).run, regen_stale=regen_stale
                )
                errors = [f.exception() for f in (audio, visual)]
            first = next((e for e in errors if e is not None), None)
            if first is not None:
                raise first
        if "build" in steps:
            _set_step(store, "build")
            BuildStep(job, plan).run()
        _set_step(store, "qc")
        qc = run_qc(job, plan)
    except RlError as err:
        error = {"code": int(err.code), "message": str(err), "hint": err.hint}
        store.update("run", lambda s: s.update(status="failed", error=error))
        raise
    except Exception as err:
        message = f"{type(err).__name__}: {err}"
        store.update(
            "run",
            lambda s: s.update(
                status="failed", error={"code": int(ExitCode.INTERNAL), "message": message}
            ),
        )
        raise
    finally:
        stop.set()
    return store.update(
        "run", lambda s: s.update(status="done", finished=now_iso(), qc_passed=qc["passed"])
    )


def _set_step(store: StateStore, step: str) -> None:
    store.update("run", lambda s: s.update(step=step, heartbeat=time.time()))


def detach(job: Path, args: list[str]) -> dict[str, Any]:
    """Start `rlite run` in a new session (survives the parent) and keep a Mac awake."""
    log = (job / "job.log").open("a", encoding="utf-8")
    child = subprocess.Popen(
        [sys.executable, "-m", "rl.cli", "run", str(job), "--child", *args],
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    awake = False
    if sys.platform == "darwin":
        try:
            subprocess.Popen(
                ["caffeinate", "-ims", "-w", str(child.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            awake = True
        except FileNotFoundError:
            awake = False
    return {
        "pid": child.pid,
        "log": str(job / "job.log"),
        "keeping_awake": awake,
        "on_battery": on_battery(),
    }


def on_battery() -> bool | None:
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(
            ["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5
        ).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return "Battery Power" in out


def run_status(job: Path) -> State:
    """run.json plus liveness: a 'running' run without a recent heartbeat is reported 'dead'."""
    state = StateStore(job).read("run")
    if (
        state.get("status") == "running"
        and time.time() - float(state.get("heartbeat", 0)) > DEAD_AFTER_S
    ):
        state = {
            **state,
            "status": "dead",
            "hint": "The run stopped (closed laptop, crash). Resume it: rlite run <job> --detach",
        }
    return state


def wait(job: Path, timeout_s: float, poll_s: float = 5.0) -> tuple[int, State]:
    """Block up to timeout_s. Returns (exit code, run state): 0 done, 11 still running."""
    deadline = time.monotonic() + timeout_s
    while True:
        state = run_status(job)
        status = state.get("status")
        if status == "done":
            return int(ExitCode.OK), state
        if status == "failed":
            return int((state.get("error") or {}).get("code", ExitCode.INTERNAL)), state
        if status == "dead":
            return int(ExitCode.INTERNAL), state
        if not status:
            return int(ExitCode.CONFIG), {
                "error": "This job has never been run.",
                "hint": "rlite run <job> --detach",
            }
        if time.monotonic() >= deadline:
            return int(ExitCode.RUNNING), state
        time.sleep(poll_s)
