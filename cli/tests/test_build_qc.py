import json
from pathlib import Path
from typing import Any

import pytest
from audio_utils import image, noise, video
from conftest import load_example
from PIL import Image

from rl import ffmpeg
from rl.build import BuildStep
from rl.cli import main
from rl.exitcodes import ConfigError, ExitCode
from rl.hashing import plan_hash
from rl.qc import run_qc
from rl.state import StateStore
from rl.thumbnail import keyword, make_thumbnail, mode_label, template_index
from rl.visual.media import final_loop_encode


def prepared_job(tmp_path: Path, plan: dict[str, Any], *, loop: bool) -> Path:
    """A job whose audio and visual steps are done, built from synthetic media."""
    job = tmp_path / "home" / "jobs" / "j-build"
    (job / "visual").mkdir(parents=True)
    (job / "audio").mkdir()
    (job / "plan.json").write_text(json.dumps(plan))
    still = image(job / "visual" / "still.png")
    audio = job / "audio" / "audio.m4a"
    ffmpeg.run(["-i", str(noise(tmp_path / "bed.wav", 40)), "-c:a", "aac", str(audio)], audio)
    store = StateStore(job)
    store.replace("still", {"status": "done", "sha256": "s", "output": str(still)})
    store.replace("approval", {"plan_hash": plan_hash(plan), "still_sha256": "s"})
    store.replace(
        "audio",
        {"status": "done", "assemble": {"hash": "a1", "output": str(audio), "duration_s": 40.0}},
    )
    if loop:
        clip = video(job / "visual" / "clip_01.mp4", 3, size="1920x1080")
        loop_path = final_loop_encode(clip, job / "visual" / "loop.mp4")
        store.replace("visual", {"status": "done", "kind": "loop", "output": str(loop_path)})
    else:
        store.replace("visual", {"status": "done", "kind": "still", "output": str(still)})
    return job


@pytest.mark.parametrize("loop", [True, False])
def test_build_produces_exact_video_and_deliverables(isolated_home: Path, loop: bool) -> None:
    plan = load_example("ambient")
    job = prepared_job(isolated_home, plan, loop=loop)
    state = BuildStep(job, plan).run()
    video_path = Path(state["video"])
    assert ffmpeg.duration(video_path) == pytest.approx(40, abs=0.5)
    assert ffmpeg.video_size(video_path) == (1920, 1080)
    sheet = (job / "final" / "UPLOAD.md").read_text()
    assert "Rain on a Tent ⛺ 1 Min | Sleep" in sheet  # {duration} resolved from the real audio
    assert "Altered or synthetic content: Yes" in sheet
    assert Image.open(job / "final" / "thumbnail.png").size == (1280, 720)
    assert (
        json.loads((job / "final" / "provenance.json").read_text())["audio"]["engine"]
        == "elevenlabs"
    )


def test_build_is_skipped_when_nothing_changed(isolated_home: Path) -> None:
    plan = load_example("ambient")
    job = prepared_job(isolated_home, plan, loop=False)
    first = BuildStep(job, plan).run()
    mtime = Path(first["video"]).stat().st_mtime
    BuildStep(job, plan).run()
    assert Path(first["video"]).stat().st_mtime == mtime


def test_build_requires_audio_and_visual(isolated_home: Path) -> None:
    plan = load_example("ambient")
    job = prepared_job(isolated_home, plan, loop=False)
    StateStore(job).replace("visual", {"status": "running"})
    with pytest.raises(ConfigError):
        BuildStep(job, plan).run()


def test_qc_passes_and_extracts_frames(
    isolated_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = load_example("ambient")
    job = prepared_job(isolated_home, plan, loop=True)
    BuildStep(job, plan).run()
    state = run_qc(job, plan)
    assert state["passed"], state["checks"]
    assert len(state["frames"]) == 4 and all(Path(f).exists() for f in state["frames"])
    assert main(["qc", job.name, "--json"]) in (ExitCode.OK, ExitCode.PARTIAL)


def test_thumbnail_helpers(tmp_path: Path) -> None:
    assert keyword("Rain on a Tent ⛺ {duration} | Sleep") == "RAIN ON A TENT"
    assert keyword("Deep Sleep Piano · {duration}") == "DEEP SLEEP PIANO"
    assert mode_label("functional", "focus") == "FOCUS MUSIC"
    assert {template_index(s) for s in ("a", "b", "c", "d", "e", "f")} <= {0, 1, 2}
    for idea in ("rain", "fire", "waves", "piano"):
        out = make_thumbnail(
            image(tmp_path / "bg.png"),
            tmp_path / f"{idea}.png",
            title="Fireplace Crackling {duration}",
            seconds=7200,
            mode="ambient",
            use="sleep",
            seed_text=idea,
        )
        assert Image.open(out).size == (1280, 720)
