import json
from pathlib import Path
from typing import Any

import pytest
from audio_utils import image, video
from conftest import load_example

from rl import ffmpeg
from rl.exitcodes import ConfigError, NeedsApproval, StaleItems
from rl.hashing import plan_hash
from rl.providers.base import PollResult
from rl.state import StateStore
from rl.visual import stabilize_close as stab
from rl.visual.media import concat_xfade, final_loop_encode, last_frame
from rl.visual.step import VisualProviders, VisualStep, run_still


class FakeHiggs:
    def __init__(self) -> None:
        self.submitted: list[tuple[str, dict[str, Any]]] = []
        self.polled: list[str] = []

    def submit(self, model: str, params: dict[str, Any]) -> str:
        self.submitted.append((model, params))
        return f"job-{len(self.submitted)}"

    def poll(self, job_id: str) -> PollResult:
        self.polled.append(job_id)
        kind = "png" if self.submitted and self.submitted[-1][0] == "nano_banana_2" else "mp4"
        return PollResult("done", [f"https://x/{job_id}.{kind}"])


def fake_download(url: str, out: Path) -> Path:
    if out.suffix == ".png":
        return image(out)
    return video(out, seconds=3)


def make_job(tmp_path: Path, plan: dict[str, Any], *, validated: bool = True) -> Path:
    job = tmp_path / "home" / "jobs" / "j-vis"
    job.mkdir(parents=True)
    (job / "plan.json").write_text(json.dumps(plan))
    if validated:
        StateStore(job).replace("validate", {"ok": True, "plan_hash": plan_hash(plan)})
    return job


def approve(job: Path, plan: dict[str, Any]) -> None:
    store = StateStore(job)
    store.replace(
        "approval", {"plan_hash": plan_hash(plan), "still_sha256": store.read("still")["sha256"]}
    )


def providers(hf: FakeHiggs) -> VisualProviders:
    return VisualProviders(higgsfield=hf, downloader=fake_download, sleep=lambda s: None)


def test_still_requires_validation(isolated_home: Path) -> None:
    plan = load_example("functional")
    job = make_job(isolated_home, plan, validated=False)
    with pytest.raises(ConfigError):
        run_still(job, plan, providers(FakeHiggs()))


def test_still_is_reused_and_reroll_pays_again(isolated_home: Path) -> None:
    plan = load_example("functional")
    job = make_job(isolated_home, plan)
    hf = FakeHiggs()
    first = run_still(job, plan, providers(hf))
    run_still(job, plan, providers(hf))
    assert len(hf.submitted) == 1
    assert hf.submitted[0][1]["aspect_ratio"] == "16:9"
    run_still(job, plan, providers(hf), reroll=True)
    assert len(hf.submitted) == 2
    assert first["sha256"]


def test_byo_image_still_costs_nothing(isolated_home: Path) -> None:
    plan = load_example("functional")
    src = image(isolated_home / "mine.png", color="0x884422")
    plan["visual"] = {"tier": "byo", "byo_path": str(src)}
    job = make_job(isolated_home, plan)
    state = run_still(job, plan, providers(FakeHiggs()))
    assert state["source"] == "byo"
    assert (job / "visual" / "byo.png").exists()
    assert "entries" not in StateStore(job).read("cost")


def test_cinemagraph_chain_with_closing_clip(isolated_home: Path) -> None:
    plan = load_example("ambient")
    plan["visual"]["n_clips"] = 2
    job = make_job(isolated_home, plan)
    hf = FakeHiggs()
    run_still(job, plan, providers(hf))
    approve(job, plan)
    state = VisualStep(job, plan, providers(hf)).run()
    clips = [p for m, p in hf.submitted if m == "kling3_0"]
    assert len(clips) == 3  # 2 chained clips + the closing clip
    assert clips[0]["start-image"].endswith("still.png")
    assert clips[1]["start-image"].endswith("clip_01-last.png")
    assert clips[2]["end-image"].endswith("clip_01-first.png")
    assert state["kind"] == "loop" and Path(state["output"]).exists()

    again = FakeHiggs()
    VisualStep(job, plan, providers(again)).run()
    assert again.submitted == []  # resume pays nothing


def test_visual_requires_approval(isolated_home: Path) -> None:
    plan = load_example("ambient")
    job = make_job(isolated_home, plan)
    run_still(job, plan, providers(FakeHiggs()))
    with pytest.raises(NeedsApproval):
        VisualStep(job, plan, providers(FakeHiggs())).run()


def test_resume_polls_submitted_job(isolated_home: Path) -> None:
    plan = load_example("functional")
    job = make_job(isolated_home, plan)
    hf = FakeHiggs()
    from rl.hashing import stable_hash, still_hash

    item_hash = stable_hash([still_hash(plan["visual"], "nano_banana_2", "2k"), 0])
    store = StateStore(job)
    store.update(
        "cost",
        lambda s: s.setdefault("entries", []).append(
            {
                "id": "r1",
                "provider": "higgsfield",
                "label": "x",
                "usd": 0.1,
                "status": "reserved",
                "month": "2026-10",
                "at": "now",
            }
        ),
    )
    store.update(
        "still",
        lambda s: s.update(
            items={
                "still": {
                    "hash": item_hash,
                    "status": "submitted",
                    "provider_job_id": "job-old",
                    "reservation": "r1",
                }
            }
        ),
    )
    run_still(job, plan, providers(hf))
    assert hf.submitted == [] and hf.polled == ["job-old"]


def test_changed_still_makes_paid_clips_stale(isolated_home: Path) -> None:
    plan = load_example("ambient")
    plan["visual"]["n_clips"] = 1
    job = make_job(isolated_home, plan)
    hf = FakeHiggs()
    run_still(job, plan, providers(hf))
    approve(job, plan)
    VisualStep(job, plan, providers(hf)).run()
    image(job / "visual" / "still.png", color="0xaa0000")  # a different still
    StateStore(job).update("still", lambda s: s.update(sha256="new"))
    approve(job, plan)
    with pytest.raises(StaleItems):
        VisualStep(job, plan, providers(FakeHiggs())).run()


def test_media_loop_encode_drops_duplicate_frame(tmp_path: Path) -> None:
    base = concat_xfade(
        [video(tmp_path / "a.mp4", 3), video(tmp_path / "b.mp4", 3)], tmp_path / "base.mp4"
    )
    assert ffmpeg.duration(base) == pytest.approx(5.5, abs=0.15)
    assert ffmpeg.video_size(base) == (1920, 1080)
    loop = final_loop_encode(base, tmp_path / "loop.mp4")
    assert ffmpeg.duration(loop) == pytest.approx(5.5 - 1 / 24, abs=0.1)
    assert last_frame(loop, tmp_path / "last.png").exists()


@pytest.mark.skipif(not stab.available(), reason="OpenCV not installed")
def test_stabilize_close_outputs_loop(tmp_path: Path) -> None:
    src = concat_xfade([video(tmp_path / "a.mp4", 3)], tmp_path / "base.mp4")
    report = stab.stabilize_close(src, tmp_path / "ring.mp4", k=6, crf=23)
    assert report.frames == 72 - 6
    assert ffmpeg.duration(tmp_path / "ring.mp4") == pytest.approx(66 / 24, abs=0.1)
