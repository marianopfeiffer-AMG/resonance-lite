"""Still and visual steps (SPEC §4.6) on top of the user's own Higgsfield CLI login.

Every Higgsfield job is resumable: the job id is stored in state BEFORE polling, so a resume
polls the same job instead of paying for a new one.
"""

import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rl.budget import Budget
from rl.config import plans
from rl.exitcodes import ConfigError, ProviderError, RlError, StaleItems
from rl.hashing import clip_hash, file_sha256, plan_hash, stable_hash, still_hash
from rl.locks import step_lock
from rl.plan import Plan
from rl.pricing import pricing, usd_per_credit
from rl.providers.base import download
from rl.providers.higgsfield import Higgsfield
from rl.stage import require_approval
from rl.state import State, StateStore, now_iso
from rl.visual import stabilize_close as stab
from rl.visual.media import (
    close_loop_crossfade,
    concat_xfade,
    final_loop_encode,
    first_frame,
    last_frame,
    normalize_image,
)

STILL_MODEL, STILL_RES = "nano_banana_2", "2k"
CLIP_MODEL, CLIP_SECONDS = "kling3_0", 5
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


@dataclass
class VisualProviders:
    higgsfield: Any = None
    downloader: Callable[[str, Path], Path] = download
    sleep: Callable[[float], None] = time.sleep
    poll_interval_s: float = 10.0
    poll_timeout_s: float = 900.0


def _credits_usd(credits: float) -> float:
    return credits * usd_per_credit("higgsfield", plans().get("higgsfield"))


class HiggsJobs:
    """Run one Higgsfield job per item, resumably, with budget reservation."""

    def __init__(self, job_dir: Path, step: str, providers: VisualProviders) -> None:
        self.store = StateStore(job_dir)
        self.step = step
        self.p = providers
        self.hf = providers.higgsfield or Higgsfield()
        self.budget = Budget(job_dir)

    def item(self, key: str) -> State:
        items: dict[str, State] = self.store.read(self.step).get("items", {})
        return items.get(key, {})

    def set_item(self, key: str, **fields: Any) -> None:
        def _apply(state: State) -> None:
            state.setdefault("items", {}).setdefault(key, {}).update(fields)

        self.store.update(self.step, _apply)

    def run(
        self,
        key: str,
        item_hash: str,
        model: str,
        params: dict[str, Any],
        credits: float,
        out: Path,
    ) -> Path:
        st = self.item(key)
        if st.get("status") == "done" and st.get("hash") == item_hash and out.exists():
            return out
        resuming = st.get("status") == "submitted" and st.get("hash") == item_hash
        if resuming:
            job_id, reservation = st["provider_job_id"], st["reservation"]
        else:
            reservation = self.budget.reserve("higgsfield", _credits_usd(credits), f"{model} {key}")
            try:
                job_id = self.hf.submit(model, params)
            except RlError:
                self.budget.release(reservation)  # creation failed: nothing was charged
                self.set_item(key, hash=item_hash, status="failed")
                raise
            self.set_item(
                key,
                hash=item_hash,
                status="submitted",
                provider_job_id=job_id,
                reservation=reservation,
            )
        started = time.monotonic()
        while True:
            result = self.hf.poll(job_id)
            if result.status == "done":
                break
            if result.status == "failed":
                self.budget.release(reservation)
                self.set_item(key, status="failed", error=result.error)
                raise ProviderError(f"Higgsfield job failed for {key}: {result.error}")
            if time.monotonic() - started > self.p.poll_timeout_s:
                raise ProviderError(
                    f"Higgsfield is still working on {key}; resume later.", retryable=True
                )
            self.p.sleep(self.p.poll_interval_s)
        if not result.urls:
            raise ProviderError(f"Higgsfield finished {key} without a result URL.")
        self.p.downloader(result.urls[0], out)
        self.budget.commit(reservation)
        self.set_item(key, status="done", output=str(out), at=now_iso())
        return out


def run_still(
    job_dir: Path, plan: Plan, providers: VisualProviders | None = None, *, reroll: bool = False
) -> State:
    """Generate (or reuse) the still. Allowed before approval: it is part of the checkpoint."""
    validated = StateStore(job_dir).read("validate")
    if not (validated.get("ok") and validated.get("plan_hash") == plan_hash(plan)):
        raise ConfigError("Validate the plan first.", hint="Run `rlite validate <job>`.")
    tier = plan["visual"]["tier"]
    store = StateStore(job_dir)
    vdir = job_dir / "visual"
    vdir.mkdir(parents=True, exist_ok=True)
    out = vdir / "still.png"
    with step_lock(job_dir, "still"):
        if tier == "byo":
            src = _byo_source(job_dir, plan)
            if src.suffix.lower() in VIDEO_EXT:
                first_frame(src, out)
            else:
                normalize_image(src, out)
            state = {
                "status": "done",
                "source": "byo",
                "sha256": file_sha256(out),
                "output": str(out),
            }
            return store.replace("still", state)
        current = store.read("still")
        rerolls = int(current.get("rerolls", 0)) + (1 if reroll else 0)
        item_hash = stable_hash([still_hash(plan["visual"], STILL_MODEL, STILL_RES), rerolls])
        p = providers or VisualProviders()
        jobs = HiggsJobs(job_dir, "still", p)
        credits = pricing()["higgsfield"]["credits"]["nano_banana_2_2k"]
        params = {
            "prompt": plan["visual"]["image_prompt"],
            "aspect_ratio": "16:9",
            "resolution": STILL_RES,
        }
        if reroll:
            out.unlink(missing_ok=True)
        store.update("still", lambda s: s.update(status="running", rerolls=rerolls))
        try:
            jobs.run("still", item_hash, STILL_MODEL, params, credits, out)
        except RlError as err:
            message = str(err)
            store.update("still", lambda s: s.update(status="failed", error=message))
            raise
        return store.update(
            "still",
            lambda s: s.update(status="done", sha256=file_sha256(out), output=str(out), error=None),
        )


def _byo_source(job_dir: Path, plan: Plan) -> Path:
    raw = plan["visual"].get("byo_path") or ""
    src = Path(raw).expanduser()
    if not src.is_absolute():
        src = job_dir / src
    if not src.is_file():
        raise ConfigError(f"Bring-your-own file not found: {raw}")
    # Keep a private copy so the job does not depend on a file the user may move or delete.
    copy = job_dir / "visual" / f"byo{src.suffix.lower()}"
    if not copy.exists() or file_sha256(copy) != file_sha256(src):
        shutil.copy2(src, copy)
    return copy


class VisualStep:
    def __init__(self, job_dir: Path, plan: Plan, providers: VisualProviders | None = None) -> None:
        self.job = job_dir
        self.plan = plan
        self.p = providers or VisualProviders()
        self.store = StateStore(job_dir)
        self.dir = job_dir / "visual"

    def run(self, *, regen_stale: bool = False) -> State:
        require_approval(self.job, self.plan)
        with step_lock(self.job, "visual"):
            self.store.update(
                "visual", lambda s: s.update(status="running", started=now_iso(), error=None)
            )
            try:
                result = self._run(regen_stale)
            except RlError as err:
                message = str(err)
                self.store.update("visual", lambda s: s.update(status="failed", error=message))
                raise
            return self.store.update(
                "visual", lambda s: s.update(status="done", finished=now_iso(), **result)
            )

    def _run(self, regen_stale: bool) -> dict[str, Any]:
        tier = self.plan["visual"]["tier"]
        still = self.dir / "still.png"
        if tier == "still" or (
            tier == "byo" and _byo_source(self.job, self.plan).suffix.lower() not in VIDEO_EXT
        ):
            return {"kind": "still", "output": str(still)}
        if tier == "byo":
            return self._byo_clip()
        return self._cinemagraph(still, regen_stale)

    def _byo_clip(self) -> dict[str, Any]:
        src = _byo_source(self.job, self.plan)
        base = concat_xfade([src], self.dir / "ring_base.mp4")
        ring = close_loop_crossfade(base, self.dir / "ring_loop.mp4")
        loop = final_loop_encode(ring, self.dir / "loop.mp4")
        return {"kind": "loop", "output": str(loop), "closure": "crossfade (bring-your-own clip)"}

    def _cinemagraph(self, still: Path, regen_stale: bool) -> dict[str, Any]:
        visual = self.plan["visual"]
        motion, mode = visual["motion_prompt"], visual.get("mode", "pro")
        n = int(visual.get("n_clips", 6))
        jobs = HiggsJobs(self.job, "visual", self.p)
        credits = pricing()["higgsfield"]["credits"][f"kling3_0_5s_{mode}"]
        base_params = {
            "prompt": motion,
            "duration": CLIP_SECONDS,
            "mode": mode,
            "sound": "off",
            "aspect_ratio": "16:9",
        }
        frames = self.dir / "frames"
        frames.mkdir(exist_ok=True)

        clips: list[Path] = []
        start = still
        for i in range(1, n + 1):
            key = f"clip_{i:02d}"
            h = clip_hash(motion, CLIP_MODEL, mode, file_sha256(start))
            self._guard_stale(jobs, key, h, regen_stale)
            out = self.dir / f"{key}.mp4"
            jobs.run(key, h, CLIP_MODEL, {**base_params, "start-image": str(start)}, credits, out)
            clips.append(out)
            start = last_frame(out, frames / f"{key}-last.png")

        head = first_frame(clips[0], frames / "clip_01-first.png")
        h = clip_hash(motion, CLIP_MODEL, mode, file_sha256(start), file_sha256(head))
        self._guard_stale(jobs, "clip_close", h, regen_stale)
        close = self.dir / "clip_close.mp4"
        jobs.run(
            "clip_close",
            h,
            CLIP_MODEL,
            {**base_params, "start-image": str(start), "end-image": str(head)},
            credits,
            close,
        )
        clips.append(close)

        base = concat_xfade(clips, self.dir / "ring_base.mp4")
        ring = self.dir / "ring_loop.mp4"
        info: dict[str, Any] = {}
        if stab.available():
            report = stab.stabilize_close(base, ring)
            info = {
                "closure": "stabilize_close",
                "max_correction_px": report.max_correction_px,
                "closure_cc": report.closure_cc,
            }
        else:
            close_loop_crossfade(base, ring)
            info = {"closure": "crossfade (OpenCV missing: install the 'stabilize' extra)"}
        loop = final_loop_encode(ring, self.dir / "loop.mp4")
        return {"kind": "loop", "output": str(loop), **info}

    @staticmethod
    def _guard_stale(jobs: HiggsJobs, key: str, item_hash: str, regen_stale: bool) -> None:
        st = jobs.item(key)
        if st.get("status") == "done" and st.get("hash") != item_hash and not regen_stale:
            raise StaleItems(
                f"{key} was generated (and paid for) from a different still or prompt.",
                hint="Show the user the cost of regenerating the chain; "
                "if they agree, use --regen-stale.",
            )
