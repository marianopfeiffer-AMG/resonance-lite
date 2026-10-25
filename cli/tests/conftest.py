import copy
import json
from pathlib import Path
from typing import Any

import pytest

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
