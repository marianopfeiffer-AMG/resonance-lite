"""Thin, safe wrappers around ffmpeg/ffprobe.

Every output is written to a `.partial` file first and renamed only when ffmpeg succeeds,
so an interrupted run never leaves a truncated file that looks finished.
"""

import json
import re
import subprocess
from pathlib import Path

from rl.exitcodes import ConfigError, ExitCode, RlError


class FfmpegError(RlError):
    code = ExitCode.FFMPEG


def _partial(out: Path) -> Path:
    return out.with_name(f"{out.stem}.partial{out.suffix}")


def run(args: list[str], out: Path | None = None, timeout: float = 7200) -> None:
    """Run ffmpeg. If `out` is given, the last arg must be `out`; it is written atomically."""
    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error", *args]
    partial = None
    if out is not None:
        if args[-1] != str(out):
            raise ValueError("the output path must be the last ffmpeg argument")
        partial = _partial(out)
        cmd[-1] = str(partial)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise ConfigError(
            "ffmpeg is not installed.", hint="Install it: brew install ffmpeg"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise FfmpegError("ffmpeg took too long and was stopped.") from exc
    if proc.returncode != 0:
        if partial is not None:
            partial.unlink(missing_ok=True)
        raise FfmpegError(f"ffmpeg failed: {proc.stderr.strip()[-500:]}")
    if partial is not None and out is not None:
        partial.replace(out)


def analyze(args: list[str], timeout: float = 3600) -> str:
    """Run ffmpeg for analysis filters and return stderr (where filters print their stats)."""
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", *args, "-f", "null", "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise ConfigError(
            "ffmpeg is not installed.", hint="Install it: brew install ffmpeg"
        ) from exc
    if proc.returncode != 0:
        raise FfmpegError(f"ffmpeg analysis failed: {proc.stderr.strip()[-300:]}")
    return proc.stderr


def duration(path: Path) -> float:
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise ConfigError(
            "ffprobe is not installed.", hint="Install it: brew install ffmpeg"
        ) from exc
    if proc.returncode != 0:
        raise FfmpegError(f"ffprobe failed on {path.name}: {proc.stderr.strip()[-200:]}")
    return float(json.loads(proc.stdout)["format"]["duration"])


def video_size(path: Path) -> tuple[int, int]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    stream = json.loads(proc.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def number(pattern: str, text: str) -> float | None:
    """Last float captured by `pattern` in ffmpeg's stderr, or None."""
    matches = re.findall(pattern, text)
    if not matches:
        return None
    try:
        return float(matches[-1])
    except ValueError:
        return None
