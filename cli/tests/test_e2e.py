"""End-to-end with mocked providers and synthetic media: plan → still → approve → run → final/."""

import json
import time
from pathlib import Path
from typing import Any

import pytest
from conftest import load_example
from test_audio_step import FakeEleven
from test_visual import FakeHiggs, fake_download

from rl.audio.step import AudioProviders
from rl.cli import main
from rl.exitcodes import ExitCode, NeedsApproval
from rl.maintenance import clean, repair
from rl.run import run_job, run_status, wait
from rl.stage import derive_stage
from rl.state import StateStore
from rl.visual.step import VisualProviders, run_still


def _new_job(capsys: pytest.CaptureFixture[str], plan: dict[str, Any]) -> Path:
    assert main(["new", plan["idea"], "--json"]) == ExitCode.OK
    job = Path(json.loads(capsys.readouterr().out)["path"])
    (job / "plan.json").write_text(json.dumps(plan))
    return job


def test_full_pipeline_ambient_cinemagraph(
    isolated_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = load_example("ambient")
    plan["target_duration_s"] = 1800
    plan["visual"]["n_clips"] = 2
    job = _new_job(capsys, plan)

    assert main(["validate", job.name, "--json"]) == ExitCode.OK
    capsys.readouterr()
    hf = FakeHiggs()
    vp = VisualProviders(higgsfield=hf, downloader=fake_download, sleep=lambda s: None)
    run_still(job, plan, vp)
    assert derive_stage(job) == "still_ready"

    with pytest.raises(NeedsApproval):
        run_job(
            job, plan, audio_providers=AudioProviders(elevenlabs=FakeEleven()), visual_providers=vp
        )
    assert main(["approve", job.name, "--json"]) == ExitCode.OK
    capsys.readouterr()

    plan_short = json.loads((job / "plan.json").read_text())
    state = run_job(
        job,
        plan_short,
        audio_providers=AudioProviders(elevenlabs=FakeEleven()),
        visual_providers=vp,
    )
    assert state["status"] == "done"
    assert derive_stage(job) in ("delivered", "built")
    final = job / "final"
    for name in ("video.mp4", "thumbnail.png", "UPLOAD.md", "provenance.json"):
        assert (final / name).exists(), name

    code, run_state = wait(job, timeout_s=1)
    assert code == ExitCode.OK and run_state["status"] == "done"

    result = clean(job, keep_final=True, force=True)
    assert (final / "video.mp4").exists()
    assert result["removed"]


def test_wait_reports_running_and_dead(isolated_home: Path) -> None:
    job = isolated_home / "home" / "jobs" / "j-wait"
    job.mkdir(parents=True)
    (job / "plan.json").write_text(json.dumps(load_example("ambient")))
    store = StateStore(job)
    assert wait(job, timeout_s=0)[0] == ExitCode.CONFIG
    store.replace("run", {"status": "running", "heartbeat": time.time(), "step": "produce"})
    assert wait(job, timeout_s=0.01, poll_s=0.01)[0] == ExitCode.RUNNING
    store.replace("run", {"status": "running", "heartbeat": time.time() - 600, "step": "produce"})
    assert run_status(job)["status"] == "dead"


def test_detach_requires_approval(isolated_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    job = _new_job(capsys, load_example("ambient"))
    assert main(["run", job.name, "--detach", "--json"]) == ExitCode.NEEDS_APPROVAL


def test_repair_quarantines_corrupt_state(isolated_home: Path) -> None:
    job = isolated_home / "home" / "jobs" / "j-rep"
    (job / "state").mkdir(parents=True)
    (job / "plan.json").write_text(json.dumps(load_example("ambient")))
    (job / "state" / "audio.json").write_text("{broken")
    result = repair(job)
    assert result["quarantined"] == ["audio"]
    assert not (job / "state" / "audio.json").exists()
