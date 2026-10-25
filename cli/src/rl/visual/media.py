"""Frame extraction, clip concatenation and loop encoding with ffmpeg."""

from pathlib import Path

from rl import ffmpeg

FPS = 24
OUT_W, OUT_H = 1920, 1080


def first_frame(video: Path, out: Path) -> Path:
    ffmpeg.run(["-i", str(video), "-frames:v", "1", str(out)], out)
    return out


def last_frame(video: Path, out: Path) -> Path:
    ffmpeg.run(
        ["-sseof", "-0.3", "-i", str(video), "-update", "1", "-frames:v", "1", str(out)], out
    )
    return out


def normalize_image(src: Path, out: Path) -> Path:
    """Scale/crop any image to 1920x1080 PNG (for bring-your-own backgrounds)."""
    vf = f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,crop={OUT_W}:{OUT_H}"
    ffmpeg.run(["-i", str(src), "-vf", vf, "-frames:v", "1", str(out)], out)
    return out


def concat_xfade(clips: list[Path], out: Path, xfade_s: float = 0.5, crf: int = 16) -> Path:
    """Concatenate clips with micro crossfades into one high-quality base (SPEC §4.6 step 4)."""
    inputs: list[str] = []
    for clip in clips:
        inputs += ["-i", str(clip)]
    scale = (
        f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
        f"crop={OUT_W}:{OUT_H},fps={FPS},format=yuv420p"
    )
    parts = [f"[{i}:v]{scale},setpts=PTS-STARTPTS[v{i}]" for i in range(len(clips))]
    if len(clips) == 1:
        graph = parts[0].replace("[v0]", "[vout]")
    else:
        prev, offset = "[v0]", 0.0
        for i in range(1, len(clips)):
            offset += ffmpeg.duration(clips[i - 1]) - xfade_s
            label = "[vout]" if i == len(clips) - 1 else f"[x{i}]"
            parts.append(
                f"{prev}[v{i}]xfade=transition=fade:duration={xfade_s}:offset={offset:.3f}{label}"
            )
            prev = label
        graph = ";".join(parts)
    ffmpeg.run(
        [
            *inputs,
            "-filter_complex",
            graph,
            "-map",
            "[vout]",
            "-an",
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            str(out),
        ],
        out,
    )
    return out


def close_loop_crossfade(src: Path, out: Path, fade_s: float = 1.0, crf: int = 16) -> Path:
    """Fallback loop closure without OpenCV: blend the tail into the head.

    Used only for bring-your-own clips or when OpenCV is not installed; the V2 ring closure
    (closing clip + stabilize_close) is preferred because a blend can show a micro-jump.
    """
    total = ffmpeg.duration(src)
    body = total - fade_s
    graph = (
        f"[0:v]split[a][b];[a]trim=start={body},setpts=PTS-STARTPTS[tail];"
        f"[b]trim=0:{body},setpts=PTS-STARTPTS[main];"
        f"[tail][main]xfade=transition=fade:duration={fade_s}:offset=0,format=yuv420p[v]"
    )
    ffmpeg.run(
        [
            "-i",
            str(src),
            "-filter_complex",
            graph,
            "-map",
            "[v]",
            "-an",
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            "medium",
            str(out),
        ],
        out,
    )
    return out


def final_loop_encode(src: Path, out: Path, crf: int = 20) -> Path:
    """Encode the loop once at delivery quality, dropping the duplicated last frame.

    The ring's last frame equals its first; keeping it would freeze one frame per lap.
    The result is tiled later with `-c copy`, so this is the only lossy pass at full length.
    """
    keep = ffmpeg.duration(src) - 1 / FPS
    ffmpeg.run(
        [
            "-i",
            str(src),
            "-t",
            f"{keep:.3f}",
            "-an",
            "-vf",
            f"fps={FPS},format=yuv420p",
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            "veryfast",
            "-g",
            str(FPS * 2),
            "-movflags",
            "+faststart",
            str(out),
        ],
        out,
    )
    return out
