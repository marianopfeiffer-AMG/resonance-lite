"""API keys for the end user's own provider accounts.

Keys live in the OS keychain (service "resonance-lite"). They are entered by the user in a
terminal of their own (hidden prompt) or read from the clipboard, never typed into the Claude
chat and never printed. Where no keychain backend exists (headless Linux, WSL), the user may
opt into a 0600 file with an explicit warning.
"""

import contextlib
import json
import os
import re
import subprocess
import sys
from getpass import getpass
from pathlib import Path

import keyring
from keyring.errors import KeyringError, NoKeyringError

from rl.exitcodes import ConfigError
from rl.paths import rl_config

SERVICE = "resonance-lite"
KNOWN_KEYS = ("elevenlabs", "apiframe")
_KEY_LIKE = re.compile(r"\b(sk_|afk_|xi-)[A-Za-z0-9_\-]{8,}")


def _fallback_file() -> Path:
    return rl_config() / "secrets"


def _env_name(name: str) -> str:
    # CI and tests only. Documented as unsafe for daily use because env vars leak to children.
    return f"RL_SECRET_{name.upper()}"


def _read_fallback() -> dict[str, str]:
    path = _fallback_file()
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items()}


def get_secret(name: str) -> str:
    """Return the user's key for a provider or raise a ConfigError telling them how to add it."""
    if value := os.environ.get(_env_name(name)):
        return value
    try:
        value = keyring.get_password(SERVICE, name)
    except (NoKeyringError, KeyringError):
        value = None
    if not value:
        value = _read_fallback().get(name)
    if not value:
        raise ConfigError(
            f"No {name} API key configured on this computer.",
            hint=f"Open a separate terminal (not the Claude chat) and run: rlite key set {name}",
        )
    return value


def has_secret(name: str) -> bool:
    try:
        get_secret(name)
    except ConfigError:
        return False
    return True


def set_secret(name: str, value: str, *, allow_file: bool = False) -> str:
    """Store a key. Returns where it was stored ("keychain" or "file")."""
    try:
        keyring.set_password(SERVICE, name, value)
        return "keychain"
    except (NoKeyringError, KeyringError) as exc:
        if not allow_file:
            raise ConfigError(
                "No OS keychain is available on this system.",
                hint="Re-run with --allow-file-storage to save it in a 0600 file instead.",
            ) from exc
    path = _fallback_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_fallback()
    data[name] = value
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return "file"


def delete_secret(name: str) -> None:
    with contextlib.suppress(NoKeyringError, KeyringError):
        keyring.delete_password(SERVICE, name)
    data = _read_fallback()
    if data.pop(name, None) is not None:
        _fallback_file().write_text(json.dumps(data), encoding="utf-8")


def prompt_secret(name: str, *, from_clipboard: bool) -> str:
    """Read a key from the clipboard or from a hidden prompt on a real terminal."""
    if from_clipboard:
        value = _read_clipboard()
    else:
        if not sys.stdin.isatty():
            raise ConfigError(
                "Keys must be entered in a terminal of your own, not through Claude.",
                hint=f"Open a separate terminal and run: rlite key set {name}  "
                f"(or copy the key and run: rlite key set {name} --from-clipboard)",
            )
        value = getpass(f"Paste your {name} API key (input hidden): ")
    value = value.strip()
    if not value or any(c.isspace() for c in value):
        raise ConfigError("That does not look like an API key (empty or contains spaces).")
    return value


def _read_clipboard() -> str:
    for cmd in (
        ["pbpaste"],
        ["wl-paste", "--no-newline"],
        ["xclip", "-o", "-selection", "clipboard"],
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
        return result.stdout
    raise ConfigError("Could not read the clipboard on this system.")


def mask(text: str) -> str:
    """Remove configured keys and key-like strings from text before logging or printing it."""
    for name in KNOWN_KEYS:
        try:
            value = get_secret(name)
        except ConfigError:
            continue
        text = text.replace(value, "***")
    return _KEY_LIKE.sub("***", text)
