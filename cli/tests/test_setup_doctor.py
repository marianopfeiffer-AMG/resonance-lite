import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
import yaml

from rl.cli import main
from rl.doctor import check_disk, check_higgsfield, check_update, report, run_doctor
from rl.exitcodes import ExitCode
from rl.providers.higgsfield import Higgsfield
from rl.secrets import set_secret


def test_init_writes_config_and_backlog_without_keys(
    isolated_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "init",
            "--channel-name",
            "Calm Hours",
            "--elevenlabs-plan",
            "creator",
            "--budget-job",
            "12",
            "--json",
        ]
    )
    assert code == ExitCode.OK
    out = json.loads(capsys.readouterr().out)
    assert "rlite key set elevenlabs" in out["next"]
    data = yaml.safe_load((isolated_home / "config" / "channel.yaml").read_text())
    assert data["channel_name"] == "Calm Hours"
    assert data["plans"] == {"elevenlabs": "creator"}
    assert data["budget"]["per_job_usd"] == 12
    assert "IDEA-001" in (isolated_home / "home" / "backlog.md").read_text()
    assert not (isolated_home / "config" / "secrets").exists()


def test_init_rejects_unknown_plan(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["init", "--elevenlabs-plan", "gold", "--json"]) == ExitCode.CONFIG


def test_next_takes_first_queued_idea(
    isolated_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["init", "--json"])
    capsys.readouterr()
    assert main(["next", "--json"]) == ExitCode.OK
    first = json.loads(capsys.readouterr().out)
    assert first["code"] == "IDEA-001"
    plan = json.loads((Path(first["path"]) / "plan.json").read_text())
    assert plan["mode"] == "ambient" and "Fireplace" in plan["idea"]
    assert main(["next", "--json"]) == ExitCode.OK
    assert json.loads(capsys.readouterr().out)["code"] == "IDEA-002"


def test_purge_requires_terminal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main(["purge", "--json"]) == ExitCode.CONFIG


def test_doctor_flags_missing_key_with_fix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RL_NO_UPDATE_CHECK", "1")
    result = run_doctor(quick=True)
    key = next(c for c in result["checks"] if c["name"] == "ElevenLabs key")
    assert key["ok"] is False and "rlite key set elevenlabs" in key["fix"]
    assert result["ok"] is False
    set_secret("elevenlabs", "configured-in-test")
    key = next(c for c in run_doctor(quick=True)["checks"] if c["name"] == "ElevenLabs key")
    assert key["ok"] is True


def test_higgsfield_missing_is_only_a_warning() -> None:
    from rl.exitcodes import ConfigError

    def missing(args: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
        raise ConfigError("not installed")

    checks = check_higgsfield(Higgsfield(runner=missing))
    assert len(checks) == 1 and checks[0].severity == "warn" and not checks[0].ok


def test_synced_folder_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    synced = tmp_path / "Library" / "Mobile Documents" / "jobs"
    synced.mkdir(parents=True)
    monkeypatch.setenv("RL_HOME", str(synced))
    check = next(c for c in check_disk() if c.name == "jobs folder not synced")
    assert check.ok is False


def test_update_check_respects_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RL_NO_UPDATE_CHECK", "1")
    assert check_update() is None


def test_report_has_no_keys_or_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RL_NO_UPDATE_CHECK", "1")
    set_secret("elevenlabs", "super-secret-value-123")
    text = json.dumps(report())
    assert "super-secret-value-123" not in text
    assert str(Path.home()) not in text
