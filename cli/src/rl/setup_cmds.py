"""init, purge and next (SPEC §5, §10.2, §3.3)."""

import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from rl.config import channel
from rl.exitcodes import ConfigError
from rl.paths import rl_config, rl_home
from rl.secrets import KNOWN_KEYS, delete_secret

NICHES = [
    (
        "Fireplace crackling for sleep",
        "ambient",
        "fireplace, crackling fire, cozy fire, sleep sounds",
    ),
    ("Rain on a tent", "ambient", "rain sounds, rain on tent, camping ambience, sleep"),
    ("Night ocean waves", "ambient", "ocean waves, sea sounds, beach sleep, waves at night"),
    ("Distant thunderstorm", "ambient", "thunderstorm, rain and thunder, storm sounds, sleep"),
    ("Deep sleep piano", "functional", "sleep music, deep sleep, piano, insomnia relief"),
    ("Forest birds at dawn", "ambient", "forest sounds, birdsong, nature ambience, relax"),
    ("Coffee shop ambience", "ambient", "coffee shop, cafe ambience, study, work"),
    ("Brown noise", "ambient", "brown noise, white noise, focus, sleep, baby sleep"),
    ("Binaural focus music", "functional", "focus music, binaural beats, deep work, study"),
    ("Winter cabin by the fire", "ambient", "winter cabin, snow, fireplace, cozy ambience"),
    ("Night crickets", "ambient", "crickets, night sounds, nature, sleep"),
    ("Lofi study playlist", "playlist", "lofi, study music, chill beats, focus"),
]
PLANS = {
    "elevenlabs": ("free", "starter", "creator", "pro"),
    "higgsfield": ("none", "starter", "plus", "ultra"),
    "apiframe": ("none", "basic"),
}
_IDEA = re.compile(r"^## (IDEA-\d+) · (.+)$")


def seed_backlog(path: Path) -> None:
    if path.exists():
        return
    lines = [
        "# Backlog",
        "",
        "Ideas for your channel. `/resonance-lite next` takes the first `queued` one.",
        "",
    ]
    for i, (title, mode, seo) in enumerate(NICHES, 1):
        lines += [
            f"## IDEA-{i:03d} · {title}",
            "- status: queued",
            f"- mode: {mode}",
            f"- seo: {seo}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_channel(values: dict[str, Any]) -> Path:
    path = rl_config() / "channel.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = channel()
    data.update({k: v for k, v in values.items() if v is not None})
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def init(args: Any) -> dict[str, Any]:
    """Create config and data folders. Keys are NEVER handled here: use `rlite key set`."""
    for provider, allowed in PLANS.items():
        value = getattr(args, f"{provider}_plan", None)
        if value is not None and value not in allowed:
            raise ConfigError(f"Unknown {provider} plan '{value}'. Options: {', '.join(allowed)}")
    home = rl_home()
    (home / "jobs").mkdir(parents=True, exist_ok=True)
    seed_backlog(home / "backlog.md")
    plans = {p: getattr(args, f"{p}_plan", None) for p in PLANS}
    plans = {k: v for k, v in plans.items() if v and v != "none"}
    values: dict[str, Any] = {
        "channel_name": args.channel_name,
        "default_language": args.language,
        "footer": args.footer,
        "default_visual_tier": args.visual_tier,
    }
    if plans:
        values["plans"] = {**(channel().get("plans") or {}), **plans}
    if args.budget_job is not None or args.budget_month is not None:
        current = channel().get("budget") or {}
        values["budget"] = {
            "per_job_usd": args.budget_job
            if args.budget_job is not None
            else current.get("per_job_usd", 15),
            "per_month_usd": args.budget_month
            if args.budget_month is not None
            else current.get("per_month_usd", 120),
        }
    path = write_channel(values)
    return {
        "channel_yaml": str(path),
        "rl_home": str(home),
        "backlog": str(home / "backlog.md"),
        "next": "Add your key in a separate terminal: rlite key set elevenlabs",
    }


def purge(force_tty: bool = True) -> dict[str, Any]:
    if force_tty and not sys.stdin.isatty():
        raise ConfigError(
            "Purging needs your confirmation in your own terminal.",
            hint="Run `rlite purge` yourself in a separate terminal.",
        )
    answer = input(
        "This deletes your saved keys and Resonance Lite config (jobs are kept). Type 'purge': "
    )
    if answer.strip() != "purge":
        raise ConfigError("Confirmation did not match; nothing deleted.")
    for name in KNOWN_KEYS:
        delete_secret(name)
    config = rl_config()
    if config.exists():
        shutil.rmtree(config)
    return {
        "deleted_keys": list(KNOWN_KEYS),
        "deleted_config": str(config),
        "kept_jobs": str(rl_home() / "jobs"),
    }


def next_idea() -> dict[str, str]:
    """Take the first queued idea from the backlog and mark it taken."""
    path = rl_home() / "backlog.md"
    if not path.exists():
        raise ConfigError(
            "No backlog yet.", hint="Run `rlite init` to create one with starter niches."
        )
    lines = path.read_text(encoding="utf-8").splitlines()
    current: dict[str, Any] | None = None
    for i, line in enumerate(lines):
        if m := _IDEA.match(line):
            current = {"code": m.group(1), "title": m.group(2).strip(), "fields": {}}
            continue
        if current is None or not line.startswith("- "):
            continue
        key, _, value = line[2:].partition(":")
        current["fields"][key.strip()] = value.strip()
        if key.strip() == "status" and value.strip() == "queued":
            lines[i] = "- status: taken"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            j = i + 1
            while j < len(lines) and lines[j].startswith("- "):
                k, _, v = lines[j][2:].partition(":")
                current["fields"][k.strip()] = v.strip()
                j += 1
            return {
                "code": current["code"],
                "title": current["title"],
                "mode": current["fields"].get("mode", ""),
                "seo": current["fields"].get("seo", ""),
            }
    raise ConfigError("The backlog has no queued ideas left.", hint=f"Add ideas to {path}")
