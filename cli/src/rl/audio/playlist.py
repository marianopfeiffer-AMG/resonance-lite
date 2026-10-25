"""Playlist assembly (SPEC §4.3.C): per-track loudness, crossfades, -14 LUFS, chapters."""

from dataclasses import dataclass
from pathlib import Path

from rl import ffmpeg
from rl.audio.common import SAMPLE_RATE, crossfade_concat, edge_levels, trim_silence
from rl.audio.takes import MAX_JUMP_DB, choose_takes


@dataclass
class TrackAudio:
    id: str
    title: str
    takes: list[Path]


@dataclass
class PlaylistResult:
    audio: Path
    timestamps: Path
    duration_s: float
    chosen_takes: dict[str, int]
    max_jump_db: float
    warnings: list[str]


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_playlist(
    tracks: list[TrackAudio],
    out: Path,
    workdir: Path,
    *,
    exclude: set[str],
    crossfade_s: float,
    lufs: float,
    acts: dict[str, str],
) -> PlaylistResult:
    workdir.mkdir(parents=True, exist_ok=True)
    active = [t for t in tracks if t.id not in exclude]
    if not active:
        raise ValueError("every track is excluded")

    normalized: list[list[Path]] = []
    for t in active:
        takes = []
        for k, take in enumerate(t.takes):
            trimmed = trim_silence(take, workdir / f"{t.id}-take{k}-trim.wav")
            norm = workdir / f"{t.id}-take{k}-norm.wav"
            ffmpeg.run(
                [
                    "-i",
                    str(trimmed),
                    "-af",
                    f"loudnorm=I={lufs}:TP=-1.5:LRA=11",
                    "-ar",
                    str(SAMPLE_RATE),
                    "-ac",
                    "2",
                    "-c:a",
                    "pcm_s16le",
                    str(norm),
                ],
                norm,
            )
            takes.append(norm)
        normalized.append(takes)

    choice = choose_takes([[edge_levels(p) for p in takes] for takes in normalized])
    chosen = [normalized[i][k] for i, k in enumerate(choice.takes)]
    mix = crossfade_concat(chosen, workdir / "mix.wav", crossfade_s)
    ffmpeg.run(
        [
            "-i",
            str(mix),
            "-af",
            f"loudnorm=I={lufs}:TP=-1.0:LRA=11",
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

    # One chapter per track, strictly ascending (YouTube rejects duplicate timestamps).
    # An act name is folded into the line of the track that opens it. The first is 0:00.
    lines: list[str] = []
    cursor = 0.0
    for t, path in zip(active, chosen, strict=True):
        label = f"{acts[t.id]} — {t.title}" if t.id in acts else t.title
        lines.append(f"{format_timestamp(cursor)} {label}")
        cursor += ffmpeg.duration(path) - crossfade_s
    timestamps = out.with_name("timestamps.txt")
    timestamps.write_text("\n".join(lines) + "\n", encoding="utf-8")

    warnings: list[str] = []
    if choice.max_jump_db > MAX_JUMP_DB and choice.worst_join is not None:
        a, b = active[choice.worst_join].id, active[choice.worst_join + 1].id
        warnings.append(
            f"level jump of {choice.max_jump_db:.1f} dB between {a} and {b}; "
            "consider regenerating one of them"
        )
    return PlaylistResult(
        out,
        timestamps,
        ffmpeg.duration(out),
        {t.id: k for t, k in zip(active, choice.takes, strict=True)},
        choice.max_jump_db,
        warnings,
    )
