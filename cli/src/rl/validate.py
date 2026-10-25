"""Plan validation (SPEC §4.4): everything checkable by code is checked by code.

Errors block spending; warnings are shown to the user at the checkpoint.
"""

import json
import math
import re
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from rl.plan import Plan, resolve_title
from rl.rules import find_terms, load_terms

DURATION_MIN_S, DURATION_MAX_S = 30 * 60, 240 * 60
DEMO_MIN_S, DEMO_MAX_S = 10 * 60, 15 * 60
AMBIENT_CLIPS = (6, 12)
SECONDS_PER_TRACK = 200  # ~3:20 net per track after crossfade (SPEC §4.3.C)
BPM_BAND_MAX_WIDTH = 8
BPM_MAX_STEP = 4
TITLE_MAX = 100
DESCRIPTION_MAX = 5000
TAGS_MAX_CHARS = 500
_BPM = re.compile(r"(\d{2,3})\s*bpm", re.IGNORECASE)
_FOUR_K = re.compile(r"\b4\s?k\b", re.IGNORECASE)
_LOCKED_CAMERA = re.compile(r"\b(static|locked|tripod)\b", re.IGNORECASE)
_EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿⌀-⏿⬀-⯿\U0001f1e6-\U0001f1ff]")


@dataclass
class Issue:
    path: str
    message: str


@dataclass
class Report:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, path: str, message: str) -> None:
        self.errors.append(Issue(path, message))

    def warn(self, path: str, message: str) -> None:
        self.warnings.append(Issue(path, message))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [vars(i) for i in self.errors],
            "warnings": [vars(i) for i in self.warnings],
        }


@cache
def _schema_validator() -> Draft202012Validator:
    text = resources.files("rl").joinpath("schemas", "plan.v1.json").read_text(encoding="utf-8")
    return Draft202012Validator(json.loads(text))


def _json_path(parts: Any) -> str:
    out = "$"
    for part in parts:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"
    return out


def validate_plan(plan: Plan, enabled_providers: set[str], job_dir: Path | None = None) -> Report:
    """Validate a plan. Schema errors stop further checks (the shape is unknown)."""
    report = Report()
    for err in sorted(_schema_validator().iter_errors(plan), key=lambda e: list(e.path)):
        report.error(_json_path(err.absolute_path), err.message)
    if not report.ok:
        return report

    _check_engine(plan, enabled_providers, report)
    _check_duration(plan, report)
    _check_audio(plan, report)
    _check_visual(plan, report, job_dir)
    _check_metadata(plan, report)
    return report


def _check_engine(plan: Plan, enabled: set[str], report: Report) -> None:
    mode, engine = plan["mode"], plan["engine"]
    if mode == "ambient" and engine != "elevenlabs":
        report.error("$.engine", "ambient mode only supports the elevenlabs engine (sound effects)")
    if engine == "suno" and "suno" not in enabled:
        report.error(
            "$.engine",
            "Suno is an optional provider and is not enabled. Run `rlite providers enable suno` "
            "to read the risks and enable it, or use engine 'elevenlabs'.",
        )
    if engine != "suno" and "model_version" in plan["audio"]:
        report.warn("$.audio.model_version", "model_version only applies to the suno engine")


def _check_duration(plan: Plan, report: Report) -> None:
    seconds = plan["target_duration_s"]
    if plan.get("demo"):
        if not DEMO_MIN_S <= seconds <= DEMO_MAX_S:
            report.error("$.target_duration_s", "demo videos must be 10-15 minutes")
        if plan["visual"]["tier"] not in ("still", "byo"):
            report.error("$.visual.tier", "demo videos must use the 'still' or 'byo' visual tier")
    elif not DURATION_MIN_S <= seconds <= DURATION_MAX_S:
        report.error("$.target_duration_s", "duration must be 30-240 minutes")


def _scan_prompt(text: str, path: str, report: Report, *, allow_events: bool) -> None:
    for term in find_terms(text, load_terms("hard-block")):
        report.error(path, f"'{term}' produces booms; remove it or negate it ('no {term}')")
    for term in find_terms(text, load_terms("warn")):
        report.warn(path, f"'{term}' may produce jolts; prefer soft wording or negate it")
    if not allow_events:
        for term in find_terms(text, load_terms("events")):
            report.error(
                path, f"'{term}' is a discrete event: put it in audio.events, not continuous audio"
            )


def _check_audio(plan: Plan, report: Report) -> None:
    mode, audio = plan["mode"], plan["audio"]
    {"ambient": _check_ambient, "functional": _check_functional, "playlist": _check_playlist}[mode](
        plan, audio, report
    )
    constant_intensity = mode == "playlist" or plan["use"] in ("focus", "relax")
    if constant_intensity:
        for path, text in _audio_texts(audio):
            for term in find_terms(text, load_terms("energy")):
                report.warn(path, f"'{term}' breaks constant intensity for this use")
            if mode == "playlist" or plan["use"] == "focus":
                for genre in find_terms(text, load_terms("genres-banned")):
                    report.error(path, f"style lock: '{genre}' is not allowed in background music")


def _audio_texts(audio: dict[str, Any]) -> list[tuple[str, str]]:
    texts = [
        (f"$.audio.clips[{i}].prompt", c["prompt"]) for i, c in enumerate(audio.get("clips", []))
    ]
    texts += [
        (f"$.audio.sections[{i}].prompt", s["prompt"])
        for i, s in enumerate(audio.get("sections", []))
    ]
    texts += [
        (f"$.audio.tracks[{i}].style", t["style"]) for i, t in enumerate(audio.get("tracks", []))
    ]
    return texts


def _check_unique_ids(items: list[dict[str, Any]], path: str, report: Report) -> None:
    seen: set[str] = set()
    for i, item in enumerate(items):
        if item["id"] in seen:
            report.error(f"{path}[{i}].id", f"duplicate id '{item['id']}'")
        seen.add(item["id"])


def _check_ambient(plan: Plan, audio: dict[str, Any], report: Report) -> None:
    clips = audio.get("clips", [])
    low, high = AMBIENT_CLIPS
    if not low <= len(clips) <= high:
        report.error("$.audio.clips", f"ambient needs {low}-{high} clips, got {len(clips)}")
    _check_unique_ids(clips, "$.audio.clips", report)
    for i, clip in enumerate(clips):
        _scan_prompt(clip["prompt"], f"$.audio.clips[{i}].prompt", report, allow_events=False)
    for i, event in enumerate(audio.get("events", [])):
        lo, hi = event["every_s"]
        if lo > hi:
            report.error(f"$.audio.events[{i}].every_s", "every_s must be [min, max]")
        _scan_prompt(event["prompt"], f"$.audio.events[{i}].prompt", report, allow_events=True)
    for key in ("sections", "tracks"):
        if key in audio:
            report.error(f"$.audio.{key}", f"ambient mode does not use audio.{key}")


def _check_functional(plan: Plan, audio: dict[str, Any], report: Report) -> None:
    sections = audio.get("sections", [])
    if not sections:
        report.error("$.audio.sections", "functional mode needs at least one section")
    _check_unique_ids(sections, "$.audio.sections", report)
    bed_min = audio.get("bed_min_s")
    target = plan["target_duration_s"]
    if bed_min is None:
        report.error("$.audio.bed_min_s", "functional mode needs bed_min_s (>= 50% of duration)")
    else:
        if bed_min < target / 2:
            report.error("$.audio.bed_min_s", "bed_min_s must be at least 50% of the duration")
        total = sum(s["duration_s"] for s in sections)
        if total < bed_min:
            report.error("$.audio.sections", f"sections add up to {total}s, below bed_min_s")
    for i, section in enumerate(sections):
        _scan_prompt(section["prompt"], f"$.audio.sections[{i}].prompt", report, allow_events=False)
    for key in ("clips", "events", "tracks"):
        if key in audio:
            report.error(f"$.audio.{key}", f"functional mode does not use audio.{key}")


def _check_playlist(plan: Plan, audio: dict[str, Any], report: Report) -> None:
    tracks = audio.get("tracks", [])
    _check_unique_ids(tracks, "$.audio.tracks", report)
    excluded = set(plan["assembly"].get("exclude", []))
    active = [t for t in tracks if t["id"] not in excluded]
    needed = math.ceil(plan["target_duration_s"] / SECONDS_PER_TRACK)
    if len(active) < needed:
        report.error(
            "$.audio.tracks", f"{len(active)} active tracks; this duration needs at least {needed}"
        )
    unknown = excluded - {t["id"] for t in tracks}
    if unknown:
        report.error("$.assembly.exclude", f"unknown track ids: {sorted(unknown)}")
    for i, track in enumerate(tracks):
        path = f"$.audio.tracks[{i}]"
        _scan_prompt(track["style"], f"{path}.style", report, allow_events=False)
        if track["instrumental"] and track.get("lyrics"):
            report.error(f"{path}.lyrics", "instrumental tracks must have lyrics: null")
        if plan["engine"] != "suno" and (track.get("lyrics") or track.get("vocal_gender")):
            report.error(path, "lyrics and vocal_gender are only supported with the suno engine")
    _check_bpm(audio, active, tracks, report)
    for key in ("clips", "events", "sections"):
        if key in audio:
            report.error(f"$.audio.{key}", f"playlist mode does not use audio.{key}")


def _check_bpm(
    audio: dict[str, Any],
    active: list[dict[str, Any]],
    tracks: list[dict[str, Any]],
    report: Report,
) -> None:
    band = audio.get("bpm_band")
    if band is None:
        report.error("$.audio.bpm_band", "playlist needs bpm_band [min, max]")
        return
    low, high = band
    if low > high or high - low > BPM_BAND_MAX_WIDTH:
        report.error(
            "$.audio.bpm_band", f"bpm_band must be ascending and at most {BPM_BAND_MAX_WIDTH} wide"
        )
    previous: int | None = None
    for track in active:
        i = tracks.index(track)
        match = _BPM.search(track["style"])
        if not match:
            report.error(f"$.audio.tracks[{i}].style", "style must declare a tempo, e.g. '70 BPM'")
            previous = None
            continue
        bpm = int(match.group(1))
        if not low <= bpm <= high:
            report.error(f"$.audio.tracks[{i}].style", f"{bpm} BPM is outside bpm_band {band}")
        if previous is not None and abs(bpm - previous) > BPM_MAX_STEP:
            report.error(
                f"$.audio.tracks[{i}].style",
                f"tempo jumps {abs(bpm - previous)} BPM from the previous track "
                f"(max {BPM_MAX_STEP})",
            )
        previous = bpm


def _check_visual(plan: Plan, report: Report, job_dir: Path | None) -> None:
    visual = plan["visual"]
    tier = visual["tier"]
    if tier in ("cinemagraph", "still") and not visual.get("image_prompt", "").strip():
        report.error("$.visual.image_prompt", f"the {tier} tier needs an image_prompt")
    if tier == "cinemagraph":
        motion = visual.get("motion_prompt", "")
        if not motion.strip():
            report.error("$.visual.motion_prompt", "the cinemagraph tier needs a motion_prompt")
        elif not _LOCKED_CAMERA.search(motion):
            report.error(
                "$.visual.motion_prompt", "motion_prompt must ask for a static/locked camera"
            )
        for term in find_terms(motion, load_terms("motion-banned")):
            report.error(
                "$.visual.motion_prompt", f"'{term}' is not loop-safe (it needs to reverse)"
            )
    if tier == "byo":
        raw = visual.get("byo_path")
        if not raw:
            report.error("$.visual.byo_path", "the byo tier needs byo_path")
        else:
            path = Path(raw).expanduser()
            if not path.is_absolute() and job_dir is not None:
                path = job_dir / path
            if not path.is_file():
                report.error("$.visual.byo_path", f"file not found: {raw}")
    if tier in ("cinemagraph", "still") and plan["metadata"].get("synthetic_media") is False:
        report.warn(
            "$.metadata.synthetic_media",
            "photorealistic AI visuals should be disclosed as altered or synthetic content",
        )


def _check_metadata(plan: Plan, report: Report) -> None:
    meta = plan["metadata"]
    title = resolve_title(meta["title"], plan["target_duration_s"])
    if len(title) > TITLE_MAX:
        report.error(
            "$.metadata.title", f"title is {len(title)} chars after resolving (max {TITLE_MAX})"
        )
    if len(_EMOJI.findall(title)) > 1:
        report.error("$.metadata.title", "use at most one emoji in the title")
    if _FOUR_K.search(title) or _FOUR_K.search(meta["description"]):
        report.error("$.metadata", "do not claim 4K: the master is 1080p")
    if len(meta["description"]) > DESCRIPTION_MAX:
        report.error("$.metadata.description", f"description exceeds {DESCRIPTION_MAX} chars")
    tags = meta["tags"]
    if sum(len(t) for t in tags) > TAGS_MAX_CHARS:
        report.error("$.metadata.tags", f"tags exceed {TAGS_MAX_CHARS} characters in total")
    if any(c in t for t in tags for c in "<>"):
        report.error("$.metadata.tags", "tags cannot contain < or >")
