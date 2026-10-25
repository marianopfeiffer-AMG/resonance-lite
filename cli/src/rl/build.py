"""Build step (SPEC §4.7): final video by tiling the loop with -c copy, plus deliverables."""

from pathlib import Path
from typing import Any

from rl import ffmpeg
from rl.deliver import write_provenance, write_upload_sheet
from rl.exitcodes import ConfigError, RlError
from rl.hashing import build_hash, file_sha256, stable_hash
from rl.locks import step_lock
from rl.plan import Plan
from rl.stage import require_approval
from rl.state import State, StateStore, now_iso
from rl.thumbnail import make_thumbnail

DURATION_TOLERANCE_S = 0.5


class BuildStep:
    def __init__(self, job_dir: Path, plan: Plan) -> None:
        self.job = job_dir
        self.plan = plan
        self.store = StateStore(job_dir)
        self.final = job_dir / "final"

    def run(self) -> State:
        require_approval(self.job, self.plan)
        audio, visual = self.store.read("audio"), self.store.read("visual")
        if audio.get("status") != "done" or visual.get("status") != "done":
            raise ConfigError(
                "Audio and visual must both be done before building.",
                hint="Run `rlite run <job>` (or `rlite audio` / `rlite visual`).",
            )
        assemble = audio["assemble"]
        audio_path, visual_path = Path(assemble["output"]), Path(visual["output"])
        seconds = float(assemble.get("duration_s") or self.plan["target_duration_s"])
        b_hash = build_hash(
            assemble["hash"],
            stable_hash([visual.get("kind"), file_sha256(visual_path)]),
            self.plan["metadata"],
        )
        current = self.store.read("build")
        video = self.final / "video.mp4"
        if current.get("status") == "done" and current.get("hash") == b_hash and video.exists():
            return current

        with step_lock(self.job, "build"):
            self.final.mkdir(parents=True, exist_ok=True)
            self.store.update(
                "build", lambda s: s.update(status="running", started=now_iso(), error=None)
            )
            try:
                info = self._build(audio_path, visual_path, visual["kind"], seconds, video)
            except RlError as err:
                message = str(err)
                self.store.update("build", lambda s: s.update(status="failed", error=message))
                raise
            return self.store.update(
                "build", lambda s: s.update(status="done", hash=b_hash, finished=now_iso(), **info)
            )

    def _build(
        self, audio: Path, visual: Path, kind: str, seconds: float, video: Path
    ) -> dict[str, Any]:
        if kind == "loop":
            ffmpeg.run(
                [
                    "-stream_loop",
                    "-1",
                    "-i",
                    str(visual),
                    "-i",
                    str(audio),
                    "-t",
                    f"{seconds:.3f}",
                    "-map",
                    "0:v",
                    "-map",
                    "1:a",
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(video),
                ],
                video,
            )
        else:
            ffmpeg.run(
                [
                    "-loop",
                    "1",
                    "-framerate",
                    "6",
                    "-i",
                    str(visual),
                    "-i",
                    str(audio),
                    "-t",
                    f"{seconds:.3f}",
                    "-vf",
                    "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p",
                    "-c:v",
                    "libx264",
                    "-tune",
                    "stillimage",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "24",
                    "-g",
                    "300",
                    "-map",
                    "0:v",
                    "-map",
                    "1:a",
                    "-c:a",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(video),
                ],
                video,
            )
        actual = ffmpeg.duration(video)
        if abs(actual - seconds) > DURATION_TOLERANCE_S:
            video.unlink(missing_ok=True)
            raise ffmpeg.FfmpegError(
                f"Built video is {actual:.1f}s, expected {seconds:.1f}s; it was discarded."
            )

        still = self.job / "visual" / "still.png"
        thumb = make_thumbnail(
            still,
            self.final / "thumbnail.png",
            title=self.plan["metadata"]["title"],
            seconds=seconds,
            mode=self.plan["mode"],
            use=self.plan["use"],
            seed_text=self.plan["idea"],
        )
        sheet = write_upload_sheet(self.job, self.plan, seconds, self.final / "UPLOAD.md")
        write_provenance(self.job, self.plan, self.final / "provenance.json")
        return {
            "video": str(video),
            "thumbnail": str(thumb),
            "upload_sheet": str(self.final / "UPLOAD.md"),
            "duration_s": round(actual, 2),
            "size_mb": round(video.stat().st_size / 1e6, 1),
            "title": sheet["title"],
            "warnings": sheet["warnings"],
        }
