from pathlib import Path

import pytest
from conftest import load_example

from rl.plan import format_duration, resolve_title
from rl.validate import validate_plan


def messages(report_issues: list[object]) -> str:
    return " | ".join(f"{i.path}: {i.message}" for i in report_issues)  # type: ignore[attr-defined]


@pytest.mark.parametrize("mode", ["ambient", "functional", "playlist"])
def test_examples_are_valid(mode: str) -> None:
    report = validate_plan(load_example(mode), set())
    assert report.ok, messages(report.errors)


def test_unknown_top_level_field_is_rejected() -> None:
    plan = load_example("ambient")
    plan["steps"] = {}
    report = validate_plan(plan, set())
    assert not report.ok
    assert "steps" in messages(report.errors)


def test_hard_block_term_blocks_unless_negated() -> None:
    plan = load_example("ambient")
    plan["audio"]["clips"][0]["prompt"] = "fire with an explosion of sparks"
    assert not validate_plan(plan, set()).ok
    plan["audio"]["clips"][0]["prompt"] = "calm fire, no explosions, soft crackle"
    assert validate_plan(plan, set()).ok


def test_warn_term_only_warns() -> None:
    plan = load_example("ambient")
    plan["audio"]["clips"][0]["prompt"] = "waves crash softly on the sand, calm"
    report = validate_plan(plan, set())
    assert report.ok
    assert "crash" in messages(report.warnings)


def test_thunder_only_allowed_in_events() -> None:
    plan = load_example("ambient")
    plan["audio"]["clips"][0]["prompt"] = "rain with thunder far away"
    assert "audio.events" in messages(validate_plan(plan, set()).errors)
    plan["audio"]["clips"][0]["prompt"] = "steady rain, calm"
    plan["audio"]["events"] = [
        {"id": "e1", "prompt": "distant soft rolling thunder", "every_s": [90, 240], "gain_db": -14}
    ]
    assert validate_plan(plan, set()).ok


def test_ambient_clip_count() -> None:
    plan = load_example("ambient")
    plan["audio"]["clips"] = plan["audio"]["clips"][:4]
    assert "6-12 clips" in messages(validate_plan(plan, set()).errors)


def test_suno_requires_enabled_provider() -> None:
    plan = load_example("playlist")
    plan["engine"] = "suno"
    assert "not enabled" in messages(validate_plan(plan, set()).errors)
    assert validate_plan(plan, {"suno"}).ok


def test_ambient_rejects_suno() -> None:
    plan = load_example("ambient")
    plan["engine"] = "suno"
    assert "ambient mode only supports" in messages(validate_plan(plan, {"suno"}).errors)


def test_playlist_needs_enough_tracks_for_duration() -> None:
    plan = load_example("playlist")
    plan["assembly"]["exclude"] = [t["id"] for t in plan["audio"]["tracks"][:10]]
    assert "active tracks" in messages(validate_plan(plan, set()).errors)


def test_playlist_bpm_rules() -> None:
    plan = load_example("playlist")
    plan["audio"]["tracks"][3]["style"] = plan["audio"]["tracks"][3]["style"].replace(
        "70 BPM", "90 BPM"
    )
    errors = messages(validate_plan(plan, set()).errors)
    assert "outside bpm_band" in errors
    assert "tempo jumps" in errors


def test_playlist_style_lock() -> None:
    plan = load_example("playlist")
    plan["audio"]["tracks"][0]["style"] += ", deep house groove"
    assert "style lock" in messages(validate_plan(plan, set()).errors)


def test_functional_bed_minimum() -> None:
    plan = load_example("functional")
    plan["audio"]["bed_min_s"] = 1200
    assert "50%" in messages(validate_plan(plan, set()).errors)


def test_motion_must_be_locked_and_loop_safe() -> None:
    plan = load_example("ambient")
    plan["visual"]["motion_prompt"] = "a person walking through the rain"
    errors = messages(validate_plan(plan, set()).errors)
    assert "static/locked camera" in errors
    assert "not loop-safe" in errors


def test_title_rules() -> None:
    plan = load_example("ambient")
    plan["metadata"]["title"] = "Rain 4K ⛺🌧️ {duration}"
    errors = messages(validate_plan(plan, set()).errors)
    assert "4K" in errors
    assert "one emoji" in errors


def test_demo_limits() -> None:
    plan = load_example("ambient")
    plan["demo"] = True
    errors = messages(validate_plan(plan, set()).errors)
    assert "10-15 minutes" in errors
    assert "'still' or 'byo'" in errors
    plan["target_duration_s"] = 900
    plan["visual"] = {"tier": "still", "image_prompt": "rainy tent at night"}
    assert validate_plan(plan, set()).ok


def test_byo_path_must_exist(tmp_path: Path) -> None:
    plan = load_example("ambient")
    plan["visual"] = {"tier": "byo", "byo_path": str(tmp_path / "missing.png")}
    assert "file not found" in messages(validate_plan(plan, set()).errors)
    image = tmp_path / "bg.png"
    image.write_bytes(b"png")
    plan["visual"]["byo_path"] = str(image)
    assert validate_plan(plan, set()).ok


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(900, "15 Min"), (5400, "90 Min"), (7200, "2 Hours"), (9000, "2.5 Hours"), (8100, "135 Min")],
)
def test_format_duration(seconds: int, expected: str) -> None:
    assert format_duration(seconds) == expected


def test_resolve_title() -> None:
    assert resolve_title("Rain {duration} | Sleep", 7200) == "Rain 2 Hours | Sleep"
