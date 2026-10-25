"""Optional providers the user enables explicitly, after reading their risks."""

import sys
from typing import Any

from rl.config import OPTIONAL_PROVIDERS, load_providers, save_providers
from rl.exitcodes import ConfigError
from rl.state import now_iso

RISKS = {
    "suno": [
        "Suno has no official API. Apiframe is an unofficial intermediary that can change "
        "or be blocked.",
        "Suno grants usage rights, not ownership, and the generating account is Apiframe's, "
        "not yours.",
        "That makes monetized channels high-risk (Content ID claims, rights disputes).",
        "Requests can be blocked by Cloudflare. Credits are billed by Apiframe and do not "
        "roll over.",
    ]
}
CONFIRMATION = "I UNDERSTAND"


def status() -> list[dict[str, Any]]:
    data = load_providers()
    return [
        {
            "name": name,
            "enabled": bool((data.get(name) or {}).get("enabled")),
            "acknowledged_risks_at": (data.get(name) or {}).get("acknowledged_risks_at"),
        }
        for name in OPTIONAL_PROVIDERS
    ]


def enable(name: str) -> None:
    """Enable an optional provider. Requires the user to type a confirmation in their terminal."""
    if name not in OPTIONAL_PROVIDERS:
        raise ConfigError(f"Unknown optional provider: {name}")
    if not sys.stdin.isatty():
        raise ConfigError(
            f"Enabling {name} needs the user's confirmation in their own terminal.",
            hint=f"Ask the user to run in a separate terminal: rlite providers enable {name}",
        )
    print(f"Before enabling {name}, read the risks:\n")
    for line in RISKS[name]:
        print(f"  - {line}")
    answer = input(f"\nType '{CONFIRMATION}' to enable {name}: ")
    if answer.strip() != CONFIRMATION:
        raise ConfigError("Confirmation did not match; nothing changed.")
    data = load_providers()
    data[name] = {"enabled": True, "acknowledged_risks_at": now_iso()}
    save_providers(data)


def disable(name: str) -> None:
    data = load_providers()
    entry = data.get(name) or {}
    entry["enabled"] = False
    data[name] = entry
    save_providers(data)
