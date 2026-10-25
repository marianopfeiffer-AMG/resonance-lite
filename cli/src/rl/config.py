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
    data = load_providers()
    enabled: set[str] = set()
    for name in OPTIONAL_PROVIDERS:
        entry = data.get(name) or {}
        if entry.get("enabled") is True and entry.get("acknowledged_risks_at"):
            enabled.add(name)
    return enabled


DEFAULT_BUDGET = {"per_job_usd": 15.0, "per_month_usd": 120.0}


def channel() -> dict[str, Any]:
    """channel.yaml contents (empty dict if the user has not run init yet)."""
    return _load_yaml(rl_config() / "channel.yaml")


def budget_limits() -> dict[str, float]:
    configured = channel().get("budget") or {}
    return {k: float(configured.get(k, v)) for k, v in DEFAULT_BUDGET.items()}


def plans() -> dict[str, str]:
    """The user's declared plan per provider, used to convert credits to USD."""
    return {str(k): str(v) for k, v in (channel().get("plans") or {}).items()}


def providers_file() -> Path:
    return rl_config() / "providers.yaml"


def load_providers() -> dict[str, Any]:
    return _load_yaml(providers_file())


def save_providers(data: dict[str, Any]) -> None:
    path = providers_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
