"""Recipe A (SPEC §4.3.A): three ring layers of coprime lengths, tiled to the full duration.

Layer A uses the N clips, layer B N-1 clips, layer C N+1 clips (one repeated), each in a
different order and each closed into a seamless ring. Looped together with different
offsets, the combined pattern only repeats after lcm(periods): hours, not minutes.
"""

import random
from pathlib import Path

from rl import ffmpeg
from rl.audio.common import SAMPLE_RATE, crossfade_concat, ring_close, trim_silence

CLIP_FADE_S = 2.0
RING_FADE_S = 3.0
LAYER_DELAYS_MS = (0, 8000, 15000)
LAYER_GAINS = (0.7, 0.5, 0.45)
LAYER_COMP = "acompressor=threshold=-18dB:ratio=3:attack=20:release=400"
MASTER = (
    "acompressor=threshold=-16dB:ratio=4:attack=10:release=500,highpass=f=40,alimiter=limit=0.85"
)


def layer_orders(n: int, seed: int) -> tuple[list[int], list[int], list[int]]:
    """Index orders for the three layers: N, N-1 and N+1 clips, all different orders."""
    rng = random.Random(seed)  # noqa: S311 - deterministic shuffling, not security
    a = list(range(n))
    b = rng.sample(a, n)[: n - 1]
    c = rng.sample(a, n)
    c.append(c[0] if n > 1 else 0)
    if n > 2:
        c[0], c[1] = c[1], c[0]
    return a, b, c


def build_layers(clips: list[Path], workdir: Path, seed: int) -> list[Path]:
    workdir.mkdir(parents=True, exist_ok=True)
    trimmed = [trim_silence(c, workdir / f"trim-{i:02d}.wav") for i, c in enumerate(clips)]
    layers = []
    for name, order in zip("abc", layer_orders(len(trimmed), seed), strict=True):
        chained = crossfade_concat(
            [trimmed[i] for i in order], workdir / f"layer-{name}-raw.wav", CLIP_FADE_S
        )
        layers.append(ring_close(chained, workdir / f"layer-{name}.wav", RING_FADE_S))
    return layers


def mix_layers(layers: list[Path], seconds: float, out: Path, events: Path | None = None) -> Path:
    """Loop the three rings with offsets and gains, add the optional event track, master once."""
    args: list[str] = []
    for layer in layers:
        args += ["-stream_loop", "-1", "-i", str(layer)]
    if events is not None:
        args += ["-i", str(events)]
    parts = []
    for i, (delay, gain) in enumerate(zip(LAYER_DELAYS_MS, LAYER_GAINS, strict=True)):
        parts.append(f"[{i}:a]adelay={delay}|{delay},volume={gain},{LAYER_COMP}[l{i}]")
    mix_inputs = "[l0][l1][l2]"
    n_inputs = 3
    if events is not None:
        parts.append("[3:a]anull[ev]")
        mix_inputs += "[ev]"
        n_inputs = 4
    parts.append(f"{mix_inputs}amix=inputs={n_inputs}:duration=first:normalize=0,{MASTER}[out]")
    args += [
        "-filter_complex",
        ";".join(parts),
        "-map",
        "[out]",
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
    ]
    ffmpeg.run(args, out)
    return out


def build_ambient(
    clips: list[Path],
    seconds: float,
    out: Path,
    workdir: Path,
    *,
    seed: int = 0,
    events: Path | None = None,
) -> Path:
    layers = build_layers(clips, workdir, seed)
    return mix_layers(layers, seconds, out, events)
