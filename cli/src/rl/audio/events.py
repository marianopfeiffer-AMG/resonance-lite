"""Recipe A+ (SPEC §4.3.A+): sparse events (distant thunder) at random intervals, level-capped.

The event track is built with the concat demuxer: event clips separated by slices of one long
silence file (inpoint/outpoint), so a two-hour track needs no huge filter graph.
"""

import random
from dataclasses import dataclass
from pathlib import Path

from rl import ffmpeg
from rl.audio.common import SAMPLE_RATE, trim_silence

SILENCE_BLOCK_S = 600


@dataclass
class EventSpec:
    clips: list[Path]
    every_s: tuple[float, float]
    gain_db: float


def schedule(
    total_s: float, every_s: tuple[float, float], clip_lengths: list[float], seed: int
) -> list[tuple[float, int]]:
    """(start time, clip index) pairs; events never overlap and never run past the end."""
    rng = random.Random(seed)  # noqa: S311 - deterministic scheduling, not security
    low, high = every_s
    t = rng.uniform(low, high)
    out: list[tuple[float, int]] = []
    while True:
        idx = rng.randrange(len(clip_lengths))
        if t + clip_lengths[idx] > total_s:
            return out
        out.append((t, idx))
        t += clip_lengths[idx] + rng.uniform(low, high)


def build_event_track(
    spec: EventSpec, total_s: float, out: Path, workdir: Path, seed: int = 0
) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    clips = [trim_silence(c, workdir / f"event-{i:02d}.wav") for i, c in enumerate(spec.clips)]
    lengths = [ffmpeg.duration(c) for c in clips]
    silence = workdir / "silence.wav"
    ffmpeg.run(
        [
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={SAMPLE_RATE}:cl=stereo",
            "-t",
            str(SILENCE_BLOCK_S),
            "-c:a",
            "pcm_s16le",
            str(silence),
        ],
        silence,
    )
    lines, cursor = [], 0.0
    for start, idx in schedule(total_s, spec.every_s, lengths, seed):
        lines += _silence_entries(silence, start - cursor)
        lines.append(f"file '{clips[idx].as_posix()}'")
        cursor = start + lengths[idx]
    lines += _silence_entries(silence, total_s - cursor)
    listing = workdir / "events.txt"
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ffmpeg.run(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-af",
            f"volume={spec.gain_db}dB,alimiter=limit=0.5",
            "-t",
            f"{total_s:.3f}",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(out),
        ],
        out,
    )
    return out


def _silence_entries(silence: Path, gap: float) -> list[str]:
    entries = []
    while gap > 0.01:
        chunk = min(gap, SILENCE_BLOCK_S)
        entries += [f"file '{silence.as_posix()}'", "inpoint 0", f"outpoint {chunk:.3f}"]
        gap -= chunk
    return entries
