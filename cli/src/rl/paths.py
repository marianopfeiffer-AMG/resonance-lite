"""Filesystem locations. Nothing is hardcoded: everything derives from RL_HOME / RL_CONFIG."""

import os
from pathlib import Path

from rl.exitcodes import ConfigError


def rl_home() -> Path:
    """Directory holding jobs and the backlog (default ~/ResonanceLite)."""
    return Path(os.environ.get("RL_HOME", Path.home() / "ResonanceLite")).expanduser()


def rl_config() -> Path:
    """Directory holding channel.yaml and providers.yaml (default ~/.config/resonance-lite)."""
    return Path(
        os.environ.get("RL_CONFIG", Path.home() / ".config" / "resonance-lite")
    ).expanduser()


def jobs_dir() -> Path:
    return rl_home() / "jobs"


def resolve_job(ref: str) -> Path:
    """Resolve a job id or a path to an existing job directory."""
    candidate = Path(ref).expanduser()
    if not candidate.is_dir():
        candidate = jobs_dir() / ref
    if not (candidate / "plan.json").is_file():
        raise ConfigError(f"Job not found: {ref}", hint="Run `rlite status` to list jobs.")
    return candidate.resolve()
