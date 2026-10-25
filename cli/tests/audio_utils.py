"""Synthetic audio for tests (no network, no real providers)."""

import subprocess
from pathlib import Path


def tone(path: Path, seconds: float, freq: int = 440, lead_silence: float = 0.0) -> Path:
    """A sine tone, optionally preceded by silence (to test trimming)."""
    src = f"sine=frequency={freq}:sample_rate=48000:duration={seconds}"
    graph = f"adelay={int(lead_silence * 1000)}|{int(lead_silence * 1000)},apad=pad_dur=0.5"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            src,
            "-af",
            graph,
            "-ac",
            "2",
            str(path),
        ],
        check=True,
    )
    return path


def noise(path: Path, seconds: float, color: str = "pink", amplitude: float = 0.3) -> Path:
    src = f"anoisesrc=color={color}:amplitude={amplitude}:sample_rate=48000:duration={seconds}"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            src,
            "-ac",
            "2",
            str(path),
        ],
        check=True,
    )
    return path
