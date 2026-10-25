"""Cost, time and disk estimates for a plan, before anything is generated (SPEC §5, §13.1)."""

import math
from typing import Any

from rl.config import plans
from rl.exitcodes import RlError
from rl.plan import Plan
from rl.pricing import pricing, usd_per_credit
from rl.providers.higgsfield import Higgsfield

DEFAULT_TRACK_S = 240
VIDEO_MBPS = {"cinemagraph": 6.0, "byo": 6.0, "still": 0.3}  # 1080p loop tiled with -c copy
AUDIO_MBPS = 0.192


def _audio_credits(plan: Plan) -> tuple[str, float]:
    p = pricing()
    audio, mode, engine = plan["audio"], plan["mode"], plan["engine"]
    if engine == "suno":
        items = audio.get("sections", []) if mode == "functional" else _active_tracks(plan)
        a = p["apiframe"]
        return "apiframe", len(items) * a["suno_credits_per_generation"] * (
            1 + a["regeneration_margin"]
        )
    el = p["elevenlabs"]
    if mode == "ambient":
        n = len(audio.get("clips", [])) + len(audio.get("events", []))
        return "elevenlabs", n * el["sfx_clip_seconds"] * el["sfx_credits_per_second"]
    if mode == "functional":
        seconds = sum(s["duration_s"] for s in audio.get("sections", []))
    else:
        seconds = sum(t.get("duration_s", DEFAULT_TRACK_S) for t in _active_tracks(plan))
    return "elevenlabs", seconds / 60 * el["music_credits_per_minute"]


def _active_tracks(plan: Plan) -> list[dict[str, Any]]:
    excluded = set(plan["assembly"].get("exclude", []))
    return [t for t in plan["audio"].get("tracks", []) if t["id"] not in excluded]


def _visual_credits(plan: Plan, live: Higgsfield | None) -> tuple[float, str]:
    visual = plan["visual"]
    tier = visual["tier"]
    if tier == "byo":
        return 0.0, "none"
    table = pricing()["higgsfield"]["credits"]
    mode = visual.get("mode", "pro")
    still, clip, source = table["nano_banana_2_2k"], table[f"kling3_0_5s_{mode}"], "table"
    if live is not None:
        try:
            still = live.cost(
                "nano_banana_2", {"prompt": "estimate", "aspect_ratio": "16:9", "resolution": "2k"}
            )
            if tier == "cinemagraph":
                clip = live.cost(
                    "kling3_0", {"prompt": "estimate", "duration": 5, "mode": mode, "sound": "off"}
                )
            source = "live"
        except RlError:
            source = "table (live cost unavailable)"
    if tier == "still":
        return float(still), source
    return float(still + (visual.get("n_clips", 6) + 1) * clip), source


def estimate(plan: Plan, live: Higgsfield | None = None) -> dict[str, Any]:
    user_plans = plans()
    audio_provider, audio_cr = _audio_credits(plan)
    visual_cr, visual_source = _visual_credits(plan, live)
    providers: dict[str, dict[str, Any]] = {
        audio_provider: {
            "credits": round(audio_cr),
            "usd": round(
                audio_cr * usd_per_credit(audio_provider, user_plans.get(audio_provider)), 2
            ),
        }
    }
    if visual_cr:
        providers["higgsfield"] = {
            "credits": round(visual_cr, 2),
            "usd": round(visual_cr * usd_per_credit("higgsfield", user_plans.get("higgsfield")), 2),
            "source": visual_source,
        }
    total_usd = round(sum(p["usd"] for p in providers.values()), 2)

    duration = plan["target_duration_s"]
    if plan["mode"] == "playlist":
        duration = sum(t.get("duration_s", DEFAULT_TRACK_S) for t in _active_tracks(plan))
    master_gb = duration * (VIDEO_MBPS[plan["visual"]["tier"]] + AUDIO_MBPS) / 8 / 1000
    wav_gb = duration * 44100 * 4 / 1e9 * (2 if plan["mode"] == "playlist" else 1)
    clips = plan["visual"].get("n_clips", 6) + 1 if plan["visual"]["tier"] == "cinemagraph" else 0
    minutes = 3 + clips * 4 + (15 if plan["engine"] == "suno" else 5)
    return {
        "providers": providers,
        "total_usd": total_usd,
        "duration_s": duration,
        "time_minutes": {"low": minutes, "high": math.ceil(minutes * 2)},
        "disk_gb": {"master": round(master_gb, 2), "peak": round(2.5 * master_gb + wav_gb, 2)},
        "pricing_verified": pricing()["verified"],
        "notes": _notes(plan, user_plans),
    }


def _notes(plan: Plan, user_plans: dict[str, str]) -> list[str]:
    notes = []
    if plan["mode"] == "ambient":
        notes.append(
            "ElevenLabs sound-effect pricing is not yet calibrated; the estimate is conservative."
        )
    if user_plans.get("elevenlabs") == "free":
        notes.append("ElevenLabs free plan: no commercial use and attribution is required.")
    if not user_plans:
        notes.append(
            "No plans declared in channel.yaml; USD uses the most expensive rate per credit."
        )
    return notes
