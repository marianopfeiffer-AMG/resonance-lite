import json
from pathlib import Path
from typing import Any

import pytest
from audio_utils import noise, tone
from conftest import load_example

from rl.audio.step import AudioProviders, AudioStep
from rl.exitcodes import NeedsApproval, ProviderError, StaleItems
from rl.hashing import plan_hash
from rl.providers.base import PollResult
from rl.state import StateStore


class FakeEleven:
    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[str] = []
        self.fail_on = fail_on

    def generate_sfx(self, prompt: str, seconds: float, out: Path, *, loop: bool = True) -> Path:
        self.calls.append(prompt)
        if self.fail_on and self.fail_on in prompt:
            raise ProviderError("timeout", retryable=False)
        return noise(out.with_suffix(".wav"), 8).rename(out)

    def generate_music(
        self, prompt: str, seconds: int, out: Path, *, instrumental: bool = True
    ) -> Path:
        self.calls.append(prompt)
        return tone(out.with_suffix(".wav"), 12, freq=200 + 10 * len(self.calls)).rename(out)


class FakeApiframe:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.submitted: list[str] = []
        self.polls = 0

    def submit(self, track: dict[str, Any], model_version: str = "V4_5PLUS") -> str:
        self.submitted.append(track["id"])
        return f"job-{track['id']}"

    def poll(self, job_id: str) -> PollResult:
        self.polls += 1
        return PollResult("done", [f"https://x/{job_id}/a.mp3", f"https://x/{job_id}/b.mp3"])


def fake_download(url: str, out: Path) -> Path:
    freq = 200 + (hash(url) % 300)
    return tone(out.with_suffix(".wav"), 12, freq=freq).rename(out)


def make_job(tmp_path: Path, plan: dict[str, Any]) -> Path:
    job = tmp_path / "home" / "jobs" / "j-audio"
    job.mkdir(parents=True)
    (job / "plan.json").write_text(json.dumps(plan))
    store = StateStore(job)
    store.replace("still", {"status": "done", "sha256": "s"})
    store.replace("approval", {"plan_hash": plan_hash(plan), "still_sha256": "s"})
    return job


def short_ambient() -> dict[str, Any]:
    plan = load_example("ambient")
    plan["target_duration_s"] = 60
    return plan


def test_requires_approval(isolated_home: Path) -> None:
    plan = short_ambient()
    job = make_job(isolated_home, plan)
    plan["concept"] = "changed after approval"
    with pytest.raises(NeedsApproval):
        AudioStep(job, plan, AudioProviders(elevenlabs=FakeEleven())).run()


def test_ambient_end_to_end_and_resume_skips_paid_items(isolated_home: Path) -> None:
    plan = short_ambient()
    job = make_job(isolated_home, plan)
    eleven = FakeEleven()
    state = AudioStep(job, plan, AudioProviders(elevenlabs=eleven)).run()
    assert state["status"] == "done"
    assert len(eleven.calls) == 6
    assert state["assemble"]["duration_s"] == pytest.approx(60, abs=0.5)
    assert StateStore(job).read("cost")["entries"][0]["status"] == "spent"

    again = FakeEleven()
    AudioStep(job, plan, AudioProviders(elevenlabs=again)).run()
    assert again.calls == []  # nothing regenerated, nothing paid again


def test_timeout_counts_as_spent_and_resume_regenerates_only_missing(isolated_home: Path) -> None:
    plan = short_ambient()
    job = make_job(isolated_home, plan)
    with pytest.raises(ProviderError):
        AudioStep(job, plan, AudioProviders(elevenlabs=FakeEleven(fail_on="drips"))).run()
    entries = StateStore(job).read("cost")["entries"]
    assert [e["status"] for e in entries].count("spent") == 5  # 4 ok + the timed-out one
    retry = FakeEleven()
    AudioStep(job, plan, AudioProviders(elevenlabs=retry)).run()
    assert len(retry.calls) == 2  # the failed clip and the one after it


def test_changed_item_is_stale_until_user_agrees(isolated_home: Path) -> None:
    plan = short_ambient()
    job = make_job(isolated_home, plan)
    AudioStep(job, plan, AudioProviders(elevenlabs=FakeEleven())).run()
    plan["audio"]["clips"][0]["prompt"] = "even softer rain on canvas, calm"
    StateStore(job).replace("approval", {"plan_hash": plan_hash(plan), "still_sha256": "s"})
    with pytest.raises(StaleItems):
        AudioStep(job, plan, AudioProviders(elevenlabs=FakeEleven())).run()
    redo = FakeEleven()
    AudioStep(job, plan, AudioProviders(elevenlabs=redo)).run(regen_stale=True)
    assert redo.calls == ["even softer rain on canvas, calm"]


def short_playlist(engine: str) -> dict[str, Any]:
    plan = load_example("playlist")
    plan["engine"] = engine
    plan["audio"]["tracks"] = plan["audio"]["tracks"][:4]
    plan["target_duration_s"] = 1800  # validation is not part of this step
    return plan


def test_suno_resume_polls_saved_job_ids_instead_of_resubmitting(isolated_home: Path) -> None:
    plan = short_playlist("suno")
    job = make_job(isolated_home, plan)
    store = StateStore(job)
    first = plan["audio"]["tracks"][0]
    from rl.audio.step import plan_items

    item = next(i for i in plan_items(plan) if i.id == first["id"])
    reservation = "r0"
    store.update(
        "cost",
        lambda s: s.setdefault("entries", []).append(
            {
                "id": reservation,
                "provider": "apiframe",
                "label": "x",
                "usd": 0.1,
                "status": "reserved",
                "month": "2026-10",
                "at": "now",
            }
        ),
    )
    store.update(
        "audio",
        lambda s: s.setdefault("items", {}).update(
            {
                first["id"]: {
                    "hash": item.hash,
                    "status": "submitted",
                    "provider_job_id": "job-existing",
                    "reservation": reservation,
                }
            }
        ),
    )
    api = FakeApiframe(isolated_home)
    providers = AudioProviders(apiframe=api, downloader=fake_download, sleep=lambda s: None)
    state = AudioStep(job, plan, providers).run()
    assert first["id"] not in api.submitted
    assert len(api.submitted) == 3
    assert state["assemble"]["chosen_takes"]


def test_playlist_exclude_reassembles_without_generating(isolated_home: Path) -> None:
    plan = short_playlist("elevenlabs")
    job = make_job(isolated_home, plan)
    eleven = FakeEleven()
    AudioStep(job, plan, AudioProviders(elevenlabs=eleven)).run()
    plan["assembly"]["exclude"] = [plan["audio"]["tracks"][1]["id"]]
    StateStore(job).replace("approval", {"plan_hash": plan_hash(plan), "still_sha256": "s"})
    again = FakeEleven()
    state = AudioStep(job, plan, AudioProviders(elevenlabs=again)).run(assemble_only=True)
    assert again.calls == []
    assert len(Path(state["assemble"]["timestamps"]).read_text().splitlines()) == 3
