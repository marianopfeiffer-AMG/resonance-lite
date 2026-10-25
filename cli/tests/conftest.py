import copy
import json
from pathlib import Path
from typing import Any

import keyring
import pytest
from keyring.backend import KeyringBackend

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def load_example(mode: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXAMPLES / f"plan.{mode}.json").read_text(encoding="utf-8"))
    return copy.deepcopy(data)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test gets its own RL_HOME and RL_CONFIG; nothing touches the real user dirs."""
    monkeypatch.setenv("RL_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("RL_CONFIG", str(tmp_path / "config"))
    return tmp_path


class MemoryKeyring(KeyringBackend):
    """In-memory keychain so tests never read or write the developer's real keychain."""

    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.store.pop((service, username), None)


@pytest.fixture(autouse=True)
def memory_keyring(monkeypatch: pytest.MonkeyPatch) -> MemoryKeyring:
    for name in ("elevenlabs", "apiframe"):
        monkeypatch.delenv(f"RL_SECRET_{name.upper()}", raising=False)
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    return backend
