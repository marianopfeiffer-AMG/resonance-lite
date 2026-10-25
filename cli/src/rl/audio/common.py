"""Shared audio operations: trim silence, crossfade, ring closure, measurement, final encode."""

import re
from dataclasses import dataclass
from pathlib import Path

from rl import ffmpeg

SAMPLE_RATE = 48000
SILENCE_DB = -50
_SILENCE_START = re.compile(r"silence_start: (-?[\d.]+)")
_SILENCE_END = re.compile(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)")


def to_wav(src: Path, out: Path) -> Path:
    ffmpeg.run(
        ["-i", str(src), "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le", str(out)], out
    )
    return out


def trim_silence(src: Path, out: Path) -> Path:
    """Remove leading and trailing silence (ElevenLabs clips ship with fades and gaps).

    Nano's rule: no silence between elements. Trimming is applied before any chaining.
    """
    edge = f"silenceremove=start_periods=1:start_threshold={SILENCE_DB}dB:start_silence=0.05"
    chain = f"{edge},areverse,{edge},areverse"
    ffmpeg.run(
        [
            "-i",
            str(src),
            "-af",
            chain,
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


def crossfade_concat(files: list[Path], out: Path, fade_s: float) -> Path:
    """Chain clips with equal-power crossfades (no gaps, no hard cuts)."""
    if not files:
        raise ValueError("nothing to concatenate")
    inputs: list[str] = []
    for f in files:
        inputs += ["-i", str(f)]
    if len(files) == 1:
        ffmpeg.run(
            [*inputs, "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le", str(out)], out
        )
        return out
    graph, prev = [], "[0:a]"
    for i in range(1, len(files)):
        label = "[out]" if i == len(files) - 1 else f"[x{i}]"
        graph.append(f"{prev}[{i}:a]acrossfade=d={fade_s}:c1=qsin:c2=qsin{label}")
        prev = label
    ffmpeg.run(
        [
            *inputs,
            "-filter_complex",
            ";".join(graph),
            "-map",
            "[out]",
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


def ring_close(src: Path, out: Path, fade_s: float) -> Path:
    """Make a clip loop seamlessly: its tail is crossfaded into its own head.

    Output = head crossfaded with tail, followed by the middle. Played in a loop, the end
    flows into the start with no click and no level drop.
    """
    total = ffmpeg.duration(src)
    if total <= 3 * fade_s:
        raise ValueError(f"{src.name} is too short to ring-close with a {fade_s}s fade")
    body_end = total - fade_s
    graph = (
        f"[0:a]atrim=0:{fade_s},asetpts=PTS-STARTPTS[head];"
        f"[0:a]atrim={body_end},asetpts=PTS-STARTPTS[tail];"
        f"[0:a]atrim={fade_s}:{body_end},asetpts=PTS-STARTPTS[body];"
        f"[tail]afade=t=out:d={fade_s}:curve=qsin[tf];"
        f"[head]afade=t=in:d={fade_s}:curve=qsin[hf];"
        f"[tf][hf]amix=inputs=2:normalize=0[seam];"
        f"[seam][body]concat=n=2:v=0:a=1[out]"
    )
    ffmpeg.run(
        [
            "-i",
            str(src),
            "-filter_complex",
            graph,
            "-map",
            "[out]",
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


def encode_aac(src: Path, out: Path, seconds: float | None = None, loop: bool = False) -> Path:
    """Final encode, once: AAC 192k, 48 kHz, optionally looped/cut to an exact length."""
    args = ["-stream_loop", "-1"] if loop else []
    args += ["-i", str(src)]
    if seconds is not None:
        args += ["-t", f"{seconds:.3f}"]
    args += ["-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE), "-ac", "2", str(out)]
    ffmpeg.run(args, out)
    return out


@dataclass
class AudioReport:
    duration_s: float
    integrated_lufs: float | None
    true_peak_db: float | None
    silences: list[tuple[float, float]]

    def to_dict(self) -> dict[str, object]:
        return {
            "duration_s": round(self.duration_s, 2),
            "integrated_lufs": self.integrated_lufs,
            "true_peak_db": self.true_peak_db,
            "silences_over_2s": [[round(s, 1), round(d, 1)] for s, d in self.silences],
        }


def measure(path: Path, min_silence_s: float = 2.0) -> AudioReport:
    """Loudness (EBU R128), true peak and silences longer than `min_silence_s`."""
    stats = ffmpeg.analyze(
        [
            "-i",
            str(path),
            "-af",
            f"ebur128=peak=true,silencedetect=n={SILENCE_DB}dB:d={min_silence_s}",
        ]
    )
    lufs = ffmpeg.number(r"I:\s+(-?[\d.]+) LUFS", stats)
    peak = ffmpeg.number(r"Peak:\s+(-?[\d.]+) dBFS", stats)
    silences = [(float(e) - float(d), float(d)) for e, d in _SILENCE_END.findall(stats)]
    if _SILENCE_START.findall(stats) and len(_SILENCE_START.findall(stats)) > len(silences):
        start = float(_SILENCE_START.findall(stats)[-1])
        silences.append((start, ffmpeg.duration(path) - start))
    return AudioReport(ffmpeg.duration(path), lufs, peak, silences)


def edge_levels(path: Path, window_s: float = 8.0) -> tuple[float, float]:
    """RMS level (dB) of the first and last `window_s` seconds of a track."""
    total = ffmpeg.duration(path)
    window = min(window_s, total / 2)

    def rms(start: float) -> float:
        out = ffmpeg.analyze(
            [
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{window:.3f}",
                "-i",
                str(path),
                "-af",
                "astats=measure_overall=RMS_level:measure_perchannel=none",
            ]
        )
        level = ffmpeg.number(r"RMS level dB:\s+(-?[\d.]+|-inf)", out)
        return level if level is not None else -120.0

    return rms(0.0), rms(max(0.0, total - window))
