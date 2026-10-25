"""Environment diagnostics (SPEC §5): what is missing and exactly how to fix it.

`--report` produces a sanitized summary for bug reports: no keys, no prompts, no channel
name, and the home directory replaced by `~`.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests

from rl import __version__
from rl.config import channel, enabled_providers
from rl.exitcodes import RlError
from rl.paths import jobs_dir, rl_config, rl_home
from rl.providers.elevenlabs import ElevenLabs
from rl.providers.higgsfield import TESTED_CLI, Higgsfield
from rl.run import on_battery
from rl.secrets import has_secret, mask
from rl.visual import stabilize_close as stab

MIN_FREE_GB = 10
SYNCED_DIRS = ("Mobile Documents", "Google Drive", "GoogleDrive", "Dropbox", "OneDrive", "/mnt/c/")
UPDATE_CACHE_S = 24 * 3600
PYPI_URL = "https://pypi.org/pypi/resonance-lite/json"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str | None = None
    severity: str = "fail"  # fail | warn


def _cmd(args: list[str]) -> str | None:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=20).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def check_ffmpeg() -> list[Check]:
    encoders = _cmd(["ffmpeg", "-hide_banner", "-encoders"])
    if encoders is None:
        fix = "brew install ffmpeg" if sys.platform == "darwin" else "sudo apt install ffmpeg"
        return [Check("ffmpeg", False, "not installed", fix)]
    filters = _cmd(["ffmpeg", "-hide_banner", "-filters"]) or ""
    checks = [Check("ffmpeg", True, "installed")]
    checks.append(
        Check(
            "ffmpeg libx264",
            "libx264" in encoders,
            "H.264 encoder",
            "Install a full ffmpeg build (brew install ffmpeg)",
        )
    )
    for f in ("loudnorm", "ebur128", "acrossfade", "xfade"):
        checks.append(
            Check(f"ffmpeg {f}", f in filters, f"{f} filter", "Install a full ffmpeg build")
        )
    return checks


def check_keys() -> list[Check]:
    checks = [
        Check(
            "ElevenLabs key",
            has_secret("elevenlabs"),
            "your own key, stored on this computer",
            "In a separate terminal: rlite key set elevenlabs",
        )
    ]
    if "suno" in enabled_providers():
        checks.append(
            Check(
                "Apiframe key",
                has_secret("apiframe"),
                "needed because Suno is enabled",
                "In a separate terminal: rlite key set apiframe",
            )
        )
    return checks


def check_higgsfield(hf: Higgsfield | None = None) -> list[Check]:
    hf = hf or Higgsfield()
    try:
        version = hf.version()
    except RlError:
        return [
            Check(
                "Higgsfield CLI",
                False,
                "not installed (optional: only for generated visuals)",
                "brew install higgsfield-ai/tap/higgsfield, then: higgsfield auth login",
                "warn",
            )
        ]
    low, high = TESTED_CLI
    in_range = version is not None and low <= version <= high
    checks = [
        Check(
            "Higgsfield CLI version",
            in_range,
            f"{version}",
            "Update or pin the tested version",
            "warn",
        )
    ]
    try:
        account = hf.account()
        checks.append(
            Check(
                "Higgsfield session", True, f"{account['credits']} credits, plan {account['plan']}"
            )
        )
    except RlError as err:
        checks.append(Check("Higgsfield session", False, str(err), err.hint, "warn"))
    return checks


def check_disk() -> list[Check]:
    home = rl_home()
    target = home if home.exists() else home.parent
    free_gb = shutil.disk_usage(target).free / 1e9
    checks = [
        Check(
            "free disk space",
            free_gb >= MIN_FREE_GB,
            f"{free_gb:.0f} GB free at {target}",
            f"Free space or move RL_HOME (a 2-hour job peaks around {MIN_FREE_GB} GB)",
            "warn",
        )
    ]
    synced = any(token in str(home) for token in SYNCED_DIRS)
    checks.append(
        Check(
            "jobs folder not synced",
            not synced,
            str(home),
            "Set RL_HOME to a local folder (cloud-synced folders break large media files)",
            "warn",
        )
    )
    return checks


def check_power() -> list[Check]:
    battery = on_battery()
    if battery is None:
        return []
    return [
        Check(
            "power",
            not battery,
            "on battery" if battery else "plugged in",
            "Plug in and keep the lid open during long runs",
            "warn",
        )
    ]


def check_update(now: float | None = None) -> Check | None:
    if os.environ.get("RL_NO_UPDATE_CHECK"):
        return None
    cache = rl_config() / "update-check.json"
    now = now or time.time()
    latest = None
    try:
        data = json.loads(cache.read_text())
        if now - float(data["checked"]) < UPDATE_CACHE_S:
            latest = data.get("latest")
    except (OSError, ValueError, KeyError):
        data = None
    if data is None or latest is None:
        try:
            resp = requests.get(PYPI_URL, timeout=5)
            latest = resp.json()["info"]["version"] if resp.status_code == 200 else None
        except (requests.RequestException, ValueError, KeyError):
            latest = None
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"checked": now, "latest": latest}))
    if not latest or latest == __version__:
        return None
    return Check(
        "rlite version",
        False,
        f"{__version__} installed, {latest} available",
        "uv tool upgrade resonance-lite",
        "warn",
    )


def calibrate() -> dict[str, float]:
    """Encode 10 s of synthetic 1080p to estimate this machine's speed; cached for estimates."""
    start = time.monotonic()
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=1920x1080:rate=24:duration=10",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-f",
            "null",
            "-",
        ],
        check=False,
        timeout=300,
    )
    speed = round(10 / max(time.monotonic() - start, 0.01), 2)
    result = {"x264_veryfast_realtime_factor": speed, "at": time.time()}
    path = rl_config() / "calibration.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result))
    return result


def run_doctor(*, quick: bool) -> dict[str, Any]:
    checks: list[Check] = [Check("python", sys.version_info >= (3, 12), platform.python_version())]
    checks += check_ffmpeg()
    checks.append(
        Check(
            "OpenCV (best loop quality)",
            stab.available(),
            "optional",
            "uv tool install --force 'resonance-lite[stabilize]'",
            "warn",
        )
    )
    checks += check_keys()
    checks += check_higgsfield()
    checks += check_disk()
    checks += check_power()
    checks.append(
        Check(
            "channel config",
            bool(channel()),
            str(rl_config() / "channel.yaml"),
            "Run /resonance-lite setup (or rlite init)",
            "warn",
        )
    )
    if not quick:
        if has_secret("elevenlabs"):
            try:
                remaining = ElevenLabs().remaining_credits()
                checks.append(
                    Check(
                        "ElevenLabs balance",
                        remaining is None or remaining > 0,
                        f"~{remaining} credits left" if remaining is not None else "unknown",
                        None,
                        "warn",
                    )
                )
            except RlError as err:
                checks.append(Check("ElevenLabs balance", False, str(err), err.hint, "fail"))
        calibrate()
    update = check_update()
    if update:
        checks.append(update)
    ok = all(c.ok for c in checks if c.severity == "fail")
    return {"ok": ok, "version": __version__, "checks": [asdict(c) for c in checks]}


def report() -> dict[str, Any]:
    """Sanitized diagnostics for issues: never keys, prompts, channel name or personal paths."""
    home = str(Path.home())
    doctor = run_doctor(quick=True)
    errors = []
    root = jobs_dir()
    if root.is_dir():
        for job in sorted(root.iterdir())[-5:]:
            run = job / "state" / "run.json"
            if run.exists():
                data = json.loads(run.read_text())
                if data.get("error"):
                    errors.append(
                        {"code": data["error"].get("code"), "message": data["error"].get("message")}
                    )
    text = json.dumps(
        {
            "rlite": __version__,
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()} {platform.machine()}",
            "optional_providers": sorted(enabled_providers()),
            "checks": [{k: c[k] for k in ("name", "ok", "detail")} for c in doctor["checks"]],
            "recent_errors": errors,
        },
        indent=2,
    )
    return {"report": json.loads(mask(text.replace(home, "~")))}
