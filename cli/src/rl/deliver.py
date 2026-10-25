"""UPLOAD.md (paste sheet for YouTube Studio) and provenance.json (SPEC §4.7, §13.3)."""

import json
from pathlib import Path
from typing import Any

from rl import __version__
from rl.config import channel, plans
from rl.plan import Plan, resolve_title
from rl.state import StateStore, now_iso

TITLE_MAX = 100


def build_description(plan: Plan, chapters: list[str]) -> str:
    parts = [plan["metadata"]["description"].strip()]
    if chapters:
        parts.append("Chapters\n" + "\n".join(chapters))
    footer = (channel().get("footer") or "").strip()
    if footer:
        parts.append(footer)
    if plans().get("elevenlabs") == "free":
        parts.append("Audio generated with ElevenLabs (elevenlabs.io).")
    return "\n\n".join(p for p in parts if p)


def write_upload_sheet(job_dir: Path, plan: Plan, seconds: float, out: Path) -> dict[str, Any]:
    audio = StateStore(job_dir).read("audio").get("assemble", {})
    chapters: list[str] = []
    if audio.get("timestamps") and Path(audio["timestamps"]).exists():
        chapters = Path(audio["timestamps"]).read_text(encoding="utf-8").splitlines()
    meta = plan["metadata"]
    title = resolve_title(meta["title"], int(seconds))
    description = build_description(plan, chapters)
    tags = meta["tags"]
    synthetic = meta.get("synthetic_media", plan["visual"]["tier"] in ("cinemagraph", "still"))
    warnings = []
    if len(title) > TITLE_MAX:
        warnings.append(
            f"Title is {len(title)} characters; YouTube allows {TITLE_MAX}. Shorten it."
        )
    lines = [
        f"# Upload sheet — {title}",
        "",
        "Copy each field into YouTube Studio (Create → Upload videos → `video.mp4`).",
        "",
        "## Title",
        "```",
        title,
        "```",
        "## Description",
        "```",
        description,
        "```",
        "## Tags",
        "```",
        ", ".join(tags),
        "```",
        "## Settings",
        "- Thumbnail: `thumbnail.png` (custom thumbnails need a phone-verified channel)",
        "- Category: Music",
        f"- Made for kids: {'Yes' if meta.get('made_for_kids') else 'No'}",
        f"- Altered or synthetic content: {'Yes' if synthetic else 'No'}",
        f"- Video language: {meta.get('default_language', 'en')}",
        "",
        "## Checklist",
        "1. Upload `video.mp4` and paste title, description and tags.",
        "2. Set the thumbnail and the settings above.",
        "3. Add it to the channel playlist for this niche, then publish or schedule.",
        "4. In 7 days, check retention and CTR in YouTube Analytics;",
        "   note what worked in your backlog.",
    ]
    if warnings:
        lines += ["", "## Warnings", *[f"- {w}" for w in warnings]]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"title": title, "chars": len(title), "warnings": warnings}


def write_provenance(job_dir: Path, plan: Plan, out: Path) -> None:
    store = StateStore(job_dir)
    audio_items = store.read("audio").get("items", {})
    visual_items = {**store.read("still").get("items", {}), **store.read("visual").get("items", {})}
    record = {
        "generated_at": now_iso(),
        "tool": f"resonance-lite {__version__}",
        "declared_plans": plans(),
        "audio": {
            "engine": plan["engine"],
            "model_version": plan["audio"].get("model_version"),
            "items": {
                k: {"provider": v.get("provider"), "at": v.get("at")}
                for k, v in audio_items.items()
            },
        },
        "visual": {
            "tier": plan["visual"]["tier"],
            "items": {
                k: {"provider": "higgsfield", "at": v.get("at")} for k, v in visual_items.items()
            },
        },
    }
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
