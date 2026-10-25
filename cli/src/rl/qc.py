"""Objective quality checks (SPEC §3.2 step 10, §4.3.0): frames for Claude + measured metrics."""

import importlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rl import ffmpeg
from rl.audio.common import measure
from rl.exitcodes import ConfigError
from rl.plan import Plan
from rl.state import State, StateStore, now_iso
from rl.visual import stabilize_close as stab

SEAM_FACTOR = 1.1
SHARPNESS_MIN_RATIO = 0.75
SPREAD_LIMIT_LU = {"sleep": 6.0, "baby": 6.0, "focus": 2.0, "relax": 2.0}
_SHORT_TERM = re.compile(r"\bS:\s+(-?[\d.]+)")


@dataclass
class Check:
    name: str
    ok: bool
    value: Any
    threshold: Any
    severity: str  # "fail" blocks delivery, "warn" is shown to the user


def run_qc(job_dir: Path, plan: Plan) -> State:
    store = StateStore(job_dir)
    build = store.read("build")
    if build.get("status") != "done":
        raise ConfigError("Build the video first.", hint="Run `rlite build <job>`.")
    video = Path(build["video"])
    qc_dir = job_dir / "final" / "qc"
    qc_dir.mkdir(parents=True, exist_ok=True)
    checks: list[Check] = []
    total = ffmpeg.duration(video)

    frames = []
    for frac in (0.05, 0.4, 0.7, 0.95):
        t = total * frac
        out = qc_dir / f"frame-{int(t):05d}s.png"
        ffmpeg.run(["-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", str(out)], out)
        frames.append(str(out))

    report = measure(video)
    checks.append(Check("no silences over 2 s", not report.silences, report.silences, [], "fail"))
    peak = report.true_peak_db
    checks.append(
        Check("true peak below 0 dBTP", peak is not None and peak < 0.0, peak, "< 0", "fail")
    )
    if plan["mode"] == "playlist":
        target = float(plan["assembly"].get("lufs", -14))
        lufs = report.integrated_lufs
        ok = lufs is not None and abs(lufs - target) <= 2.0
        checks.append(Check("integrated loudness near target", ok, lufs, f"{target} ± 2", "warn"))
    spread = short_term_spread(video)
    limit = SPREAD_LIMIT_LU.get(plan["use"], 6.0) if plan["mode"] != "playlist" else 2.0
    if spread is not None:
        checks.append(
            Check(
                "loudness stays within its dynamic range",
                spread <= limit,
                spread,
                f"<= {limit} LU",
                "warn",
            )
        )

    visual = store.read("visual")
    if visual.get("kind") == "loop":
        checks += loop_checks(Path(visual["output"]), job_dir / "visual" / "clip_01.mp4")

    passed = all(c.ok for c in checks if c.severity == "fail")
    state = {
        "status": "done",
        "passed": passed,
        "at": now_iso(),
        "frames": frames,
        "checks": [asdict(c) for c in checks],
    }
    return store.replace("qc", state)


def short_term_spread(path: Path) -> float | None:
    """p95 - p5 of short-term loudness (3 s windows), ignoring the first 10 s."""
    out = ffmpeg.analyze(["-i", str(path), "-af", "ebur128=framelog=verbose"])
    values = [float(v) for v in _SHORT_TERM.findall(out)]
    values = [v for v in values[100:] if v > -70]  # 10 lines per second
    if len(values) < 50:
        return None
    values.sort()
    return round(values[int(len(values) * 0.95)] - values[int(len(values) * 0.05)], 2)


def loop_checks(loop: Path, raw_clip: Path) -> list[Check]:
    if not stab.available():
        return [
            Check("loop seam and sharpness", True, "skipped (OpenCV not installed)", None, "warn")
        ]
    cv2: Any = importlib.import_module("cv2")
    np: Any = importlib.import_module("numpy")
    cap = cv2.VideoCapture(str(loop))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(
            cv2.cvtColor(cv2.resize(frame, (480, 270)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        )
    cap.release()
    if len(frames) < 10:
        return [Check("loop seam", False, f"{len(frames)} frames", ">= 10", "fail")]
    diffs = [float(np.mean(np.abs(frames[i + 1] - frames[i]))) for i in range(len(frames) - 1)]
    seam = float(np.mean(np.abs(frames[0] - frames[-1])))
    baseline = max(diffs)
    checks = [
        Check(
            "loop seam is invisible",
            seam <= SEAM_FACTOR * baseline + 0.5,
            round(seam, 3),
            f"<= {SEAM_FACTOR} x {round(baseline, 3)}",
            "fail",
        )
    ]
    if raw_clip.exists():

        def sharpness(path: Path) -> float:
            c = cv2.VideoCapture(str(path))
            ok, f = c.read()
            c.release()
            return (
                float(cv2.Laplacian(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
                if ok
                else 0.0
            )

        raw, final = sharpness(raw_clip), sharpness(loop)
        ratio = round(final / raw, 3) if raw else None
        checks.append(
            Check(
                "loop keeps sharpness",
                ratio is not None and ratio >= SHARPNESS_MIN_RATIO,
                ratio,
                f">= {SHARPNESS_MIN_RATIO}",
                "warn",
            )
        )
    return checks
