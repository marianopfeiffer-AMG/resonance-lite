"""User configuration files under RL_CONFIG (channel.yaml, providers.yaml)."""

from pathlib import Path
from typing import Any

import yaml

from rl.exitcodes import ConfigError
from rl.paths import rl_config

OPTIONAL_PROVIDERS = ("suno",)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} must be a mapping")
    return data


def enabled_providers() -> set[str]:
    """Optional providers the user explicitly enabled (with acknowledged risks)."""
    data = _load_yaml(rl_config() / "providers.yaml")
    enabled: set[str] = set()
    for name in OPTIONAL_PROVIDERS:
        entry = data.get(name) or {}
        if entry.get("enabled") is True and entry.get("acknowledged_risks_at"):
            enabled.add(name)
    return enabled
