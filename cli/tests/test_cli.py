import json
from pathlib import Path

import pytest
from conftest import load_example

from rl import __version__
from rl.cli import EXIT_USAGE, main
from rl.exitcodes import ExitCode


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_unknown_flag_exits_with_usage_code() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--nope"])
    assert exc.value.code == EXIT_USAGE


def test_new_validate_status_flow(capsys: pytest.CaptureFixture[str], isolated_home: Path) -> None:
    assert main(["new", "Lluvia sobre una carpa, 2 horas", "--json"]) == ExitCode.OK
    created = json.loads(capsys.readouterr().out)
    job_id, job = created["job_id"], Path(created["path"])
    assert job_id.endswith("lluvia-sobre-una-carpa-2-horas")

    assert main(["validate", job_id, "--json"]) == ExitCode.VALIDATION
    assert json.loads(capsys.readouterr().out)["ok"] is False

    (job / "plan.json").write_text(json.dumps(load_example("ambient")))
    assert main(["validate", job_id, "--json"]) == ExitCode.OK
    capsys.readouterr()

    assert main(["status", job_id, "--json"]) == ExitCode.OK
    assert json.loads(capsys.readouterr().out)["stage"] == "validated"

    assert main(["new", "Lluvia sobre una carpa, 2 horas", "--json"]) == ExitCode.OK
    assert json.loads(capsys.readouterr().out)["job_id"].endswith("-2")


def test_missing_job_returns_config_code(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["status", "nope", "--json"]) == ExitCode.CONFIG
    assert "Job not found" in json.loads(capsys.readouterr().out)["error"]
