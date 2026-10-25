"""The plan: what Claude wants produced. rlite only reads it (it writes the skeleton once)."""

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from rl.exitcodes import ConfigError, ValidationFailed

Plan = dict[str, Any]
DURATION_PLACEHOLDER = "{duration}"


def load_plan(job_dir: Path) -> Plan:
    path = job_dir / "plan.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"plan.json not found in {job_dir.name}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationFailed(f"plan.json is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationFailed("plan.json must be a JSON object")
    return data


def format_duration(seconds: int) -> str:
    """Human duration for titles and thumbnails: '90 Min', '2 Hours', '2.5 Hours'."""
    minutes = round(seconds / 60)
    if minutes < 120:
        return f"{minutes} Min"
    hours = minutes / 60
    if hours.is_integer():
        return f"{int(hours)} Hours"
    if (hours * 2).is_integer():
        return f"{hours:g} Hours"
    return f"{minutes} Min"


def resolve_title(title: str, seconds: int) -> str:
    return title.replace(DURATION_PLACEHOLDER, format_duration(seconds))


def slugify(text: str, max_len: int = 40) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "job"


def new_job_id(idea: str, now: datetime | None = None) -> str:
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M")
    return f"{stamp}-{slugify(idea)}"


def skeleton(idea: str, mode: str | None) -> Plan:
    """Starting point for Claude to fill. Intentionally fails validation until completed."""
    return {
        "schema_version": 1,
        "idea": idea,
        "mode": mode or "ambient",
        "engine": "elevenlabs",
        "use": "sleep",
        "target_duration_s": 5400,
        "demo": False,
        "concept": "",
        "audio": {},
        "assembly": {"exclude": [], "crossfade_s": 8, "lufs": -14},
        "visual": {"tier": "still", "image_prompt": ""},
        "metadata": {
            "title": "",
            "description": "",
            "tags": [],
            "category_id": "10",
            "made_for_kids": False,
            "default_language": "en",
            "synthetic_media": True,
        },
    }
