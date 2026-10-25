"""Stabilization + loop closure + micro-blend in a single warp and a single encode.

Ported from the /cinemagraph V2 technique. Chaining separate stabilize/close passes stacked
three bilinear warps and four encodes (-59% sharpness); here every transform is composed and
applied once per frame with LANCZOS4, then encoded once. Requires opencv-python-headless
(the `stabilize` extra). The output starts at frame K, with the tail blended into the head.
"""

import importlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FEATURES: dict[str, Any] = {
    "maxCorners": 500,
    "qualityLevel": 0.01,
    "minDistance": 8,
    "blockSize": 7,
}


@dataclass
class StabilizeReport:
    frames: int
    max_correction_px: float
    closure_cc: float | None


def available() -> bool:
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False
    return True


def stabilize_close(
    src: Path, out: Path, *, k: int = 12, crf: int = 14, zoom: float = 1.04
) -> StabilizeReport:
    # OpenCV's stubs are stricter than its runtime API; treat it dynamically here.
    cv2: Any = importlib.import_module("cv2")
    np: Any = importlib.import_module("numpy")

    lk = {
        "winSize": (21, 21),
        "maxLevel": 3,
        "criteria": (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    }
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cx, cy = w / 2.0, h / 2.0
    zoom3 = np.array(
        [[zoom, 0, cx * (1 - zoom)], [0, zoom, cy * (1 - zoom)], [0, 0, 1]], np.float64
    )

    # Pass 1: cumulative camera motion of each frame relative to frame 0 (nothing written).
    cums: list[Any] = []
    cum = np.eye(3)
    prev = None
    first_bgr = last_bgr = None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if first_bgr is None:
            first_bgr = frame.copy()
        last_bgr = frame
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            p0 = cv2.goodFeaturesToTrack(prev, mask=None, **FEATURES)
            m = None
            if p0 is not None and len(p0) >= 12:
                p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, gray, p0, None, **lk)
                if p1 is not None:
                    g0, g1 = p0[st == 1], p1[st == 1]
                    if len(g0) >= 12:
                        m, _ = cv2.estimateAffinePartial2D(
                            g1, g0, method=cv2.RANSAC, ransacReprojThreshold=3.0
                        )
            if m is not None:
                cum = cum @ np.vstack([m, [0, 0, 1]])
        cums.append(cum.copy())
        prev = gray
    cap.release()
    n = len(cums)
    if n <= 2 * k or first_bgr is None or last_bgr is None:
        raise ValueError(f"clip too short to close a loop ({n} frames, K={k})")

    def warp(img: Any, matrix: Any) -> Any:
        return cv2.warpAffine(
            img, matrix[:2], (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT
        )

    # Residual closure between the stabilized first and last frames (geometry + color).
    sf, sl = warp(first_bgr, zoom3 @ cums[0]), warp(last_bgr, zoom3 @ cums[-1])
    g1 = cv2.cvtColor(cv2.resize(sf, None, fx=0.5, fy=0.5), cv2.COLOR_BGR2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(cv2.resize(sl, None, fx=0.5, fy=0.5), cv2.COLOR_BGR2GRAY).astype(np.float32)
    rw = np.eye(2, 3, dtype=np.float32)
    closure_cc = None
    try:
        closure_cc, rw = cv2.findTransformECC(
            g1,
            g2,
            rw,
            cv2.MOTION_EUCLIDEAN,
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-7),
        )
        rw[:, 2] /= 0.5
    except cv2.error:
        rw = np.eye(2, 3, dtype=np.float32)
    # ECC returns the inverse convention; invert to compose with forward maps.
    r3 = np.linalg.inv(np.vstack([rw, [0, 0, 1]]).astype(np.float64))
    gain = sf.reshape(-1, 3).mean(0) / np.maximum(sl.reshape(-1, 3).mean(0), 1e-6)

    # Pass 2: one composed warp per frame, tail blended into the head, one encode.
    partial = out.with_name(f"{out.stem}.partial{out.suffix}")
    encoder = subprocess.Popen(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{w}x{h}",
            "-r",
            f"{fps}",
            "-i",
            "-",
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            "slow",
            "-pix_fmt",
            "yuv420p",
            str(partial),
        ],
        stdin=subprocess.PIPE,
    )
    if encoder.stdin is None:
        raise RuntimeError("could not open ffmpeg for encoding")
    eye = np.eye(3)
    heads: list[Any] = []
    cap = cv2.VideoCapture(str(src))
    i = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            a = i / max(n - 1, 1)
            ramp = eye * (1 - a) + r3 * a
            corrected = np.clip(
                warp(frame, ramp @ zoom3 @ cums[i]).astype(np.float32) * ((1 - a) + gain * a),
                0,
                255,
            )
            if i < k:
                heads.append(corrected.copy())
            else:
                if i >= n - k:
                    blend = (i - (n - k) + 1) / (k + 1)
                    corrected = corrected * (1 - blend) + heads[i - (n - k)] * blend
                encoder.stdin.write(corrected.astype(np.uint8).tobytes())
            i += 1
    finally:
        cap.release()
        encoder.stdin.close()
        code = encoder.wait()
    if code != 0:
        partial.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg failed while encoding the stabilized loop")
    partial.replace(out)
    max_corr = float(max(abs(c[0, 2]) for c in cums))
    return StabilizeReport(
        n - k, round(max_corr, 2), None if closure_cc is None else round(float(closure_cc), 4)
    )
