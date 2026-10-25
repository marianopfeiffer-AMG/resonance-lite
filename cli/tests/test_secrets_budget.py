import json
from pathlib import Path

import keyring
import pytest
from conftest import MemoryKeyring, load_example
from keyring.errors import NoKeyringError

from rl import secrets
from rl.budget import Budget
from rl.exitcodes import BudgetExceeded, ConfigError


class NoKeyring(MemoryKeyring):
    def get_password(self, service: str, username: str) -> str | None:
        raise NoKeyringError()

    def set_password(self, service: str, username: str, password: str) -> None:
        raise NoKeyringError()


def test_missing_key_tells_user_to_use_their_own_terminal(memory_keyring: MemoryKeyring) -> None:
    with pytest.raises(ConfigError) as exc:
        secrets.get_secret("elevenlabs")
    assert "separate terminal" in (exc.value.hint or "")


def test_keys_go_to_keychain(memory_keyring: MemoryKeyring) -> None:
    assert secrets.set_secret("elevenlabs", "sk_test_value_1234") == "keychain"
    assert secrets.get_secret("elevenlabs") == "sk_test_value_1234"
    assert ("resonance-lite", "elevenlabs") in memory_keyring.store


def test_file_fallback_requires_opt_in_and_is_private(isolated_home: Path) -> None:
    keyring.set_keyring(NoKeyring())
    with pytest.raises(ConfigError):
        secrets.set_secret("elevenlabs", "sk_test_value_1234")
    assert secrets.set_secret("elevenlabs", "sk_test_value_1234", allow_file=True) == "file"
    path = isolated_home / "config" / "secrets"
    assert path.stat().st_mode & 0o777 == 0o600
    assert secrets.get_secret("elevenlabs") == "sk_test_value_1234"


def test_prompt_refuses_without_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(ConfigError) as exc:
        secrets.prompt_secret("elevenlabs", from_clipboard=False)
    assert "not through Claude" in str(exc.value)


def test_mask_hides_configured_and_key_like_values(memory_keyring: MemoryKeyring) -> None:
    secrets.set_secret("elevenlabs", "plainvalue123")
    fake_key = "sk_" + "x" * 20  # built at runtime so the repo never contains a key-like literal
    masked = secrets.mask(f"key plainvalue123 and {fake_key}")
    assert "plainvalue123" not in masked
    assert fake_key not in masked


def _job(tmp_path: Path) -> Path:
    job = tmp_path / "home" / "jobs" / "j1"
    job.mkdir(parents=True)
    (job / "plan.json").write_text(json.dumps(load_example("ambient")))
    return job


def test_budget_blocks_over_job_cap(isolated_home: Path) -> None:
    budget = Budget(_job(isolated_home))
    first = budget.reserve("elevenlabs", 10.0, "clips")
    budget.commit(first, 9.5)
    with pytest.raises(BudgetExceeded):
        budget.reserve("higgsfield", 6.0, "clip chain")
    assert budget.summary()["job_usd"] == 9.5


def test_released_reservations_do_not_count(isolated_home: Path) -> None:
    budget = Budget(_job(isolated_home))
    res = budget.reserve("higgsfield", 14.0, "chain")
    budget.release(res)
    budget.reserve("higgsfield", 14.0, "chain retry")


def test_monthly_cap_spans_jobs(isolated_home: Path) -> None:
    (isolated_home / "config").mkdir(parents=True)
    (isolated_home / "config" / "channel.yaml").write_text(
        "budget: {per_job_usd: 100, per_month_usd: 20}\n"
    )
    first = _job(isolated_home)
    second = first.parent / "j2"
    second.mkdir()
    (second / "plan.json").write_text((first / "plan.json").read_text())
    Budget(first).reserve("elevenlabs", 15.0, "a")
    with pytest.raises(BudgetExceeded):
        Budget(second).reserve("elevenlabs", 6.0, "b")


def test_raising_cap_needs_a_terminal(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(ConfigError):
        Budget(_job(isolated_home)).allow_extra(10)
