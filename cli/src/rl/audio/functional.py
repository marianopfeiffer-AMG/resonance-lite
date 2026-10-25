"""Recipe B (SPEC §4.3.B): sections chained with crossfades, ring-closed, tiled to length."""

from pathlib import Path

from rl import ffmpeg
from rl.audio.common import SAMPLE_RATE, crossfade_concat, ring_close, trim_silence

SECTION_FADE_S = 4.0
RING_FADE_S = 8.0
MASTER = "acompressor=threshold=-14dB:ratio=3:attack=20:release=400,alimiter=limit=0.9"


def build_functional(sections: list[Path], seconds: float, out: Path, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    trimmed = [trim_silence(s, workdir / f"trim-{i:02d}.wav") for i, s in enumerate(sections)]
    bed = crossfade_concat(trimmed, workdir / "bed-raw.wav", SECTION_FADE_S)
    ring = ring_close(bed, workdir / "bed-ring.wav", RING_FADE_S)
    # Looping the whole ring keeps section order, so the same section is never contiguous
    # (unless there is only one section).
    ffmpeg.run(
        [
            "-stream_loop",
            "-1",
            "-i",
            str(ring),
            "-af",
            MASTER,
            "-t",
            f"{seconds:.3f}",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            str(out),
        ],
        out,
    )
    return out
