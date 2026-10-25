import json
from pathlib import Path

import pytest
from conftest import load_example

from rl.cli import main
from rl.estimate import estimate
from rl.exitcodes import ExitCode


def test_ambient_cinemagraph_estimate() -> None:
    result = estimate(load_example("ambient"))
    assert set(result["providers"]) == {"elevenlabs", "higgsfield"}
    # 6 clips + 1 closing clip at 7.5 + still at 2
    assert result["providers"]["higgsfield"]["credits"] == 2 + 7 * 7.5
    assert result["disk_gb"]["peak"] > result["disk_gb"]["master"]


def test_playlist_suno_uses_apiframe_with_margin() -> None:
    plan = load_example("playlist")
    plan["engine"] = "suno"
    result = estimate(plan)
    assert result["providers"]["apiframe"]["credits"] == round(36 * 11 * 1.15)


def test_byo_has_no_visual_cost() -> None:
    plan = load_example("functional")
    plan["visual"] = {"tier": "byo", "byo_path": "bg.png"}
    assert "higgsfield" not in estimate(plan)["providers"]


def _make_job(isolated_home: Path, mode: str) -> str:
    job = isolated_home / "home" / "jobs" / "j-est"
    job.mkdir(parents=True)
    (job / "plan.json").write_text(json.dumps(load_example(mode)))
    return job.name


def test_estimate_command(capsys: pytest.CaptureFixture[str], isolated_home: Path) -> None:
    job = _make_job(isolated_home, "functional")
    assert main(["estimate", job, "--offline", "--monthly", "4", "--json"]) == ExitCode.OK
    out = json.loads(capsys.readouterr().out)
    assert out["monthly"]["videos"] == 4
    assert out["total_usd"] > 0


def test_key_set_refuses_without_terminal(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main(["key", "set", "elevenlabs", "--json"]) == ExitCode.CONFIG
    assert "not through Claude" in json.loads(capsys.readouterr().out)["error"]


def test_providers_enable_refuses_without_terminal(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main(["providers", "enable", "suno", "--json"]) == ExitCode.CONFIG
    capsys.readouterr()
    assert main(["providers", "--json"]) == ExitCode.OK
    assert json.loads(capsys.readouterr().out)["providers"][0]["enabled"] is False
