"""Stable content hashes used to decide whether a generated item is still valid.

Each item hashes exactly the inputs that determine its output (SPEC §4.1), so editing one
prompt invalidates only that item, and a regenerated still cascades to the clips that start
from it.
"""

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plan_hash(plan: dict[str, Any]) -> str:
    """Hash of the whole plan; recorded at approval time."""
    return stable_hash(plan)


def still_hash(visual: dict[str, Any], model: str, resolution: str) -> str:
    return stable_hash(
        {"image_prompt": visual.get("image_prompt"), "model": model, "resolution": resolution}
    )


def clip_hash(
    motion_prompt: str, model: str, mode: str, start_sha: str, end_sha: str | None = None
) -> str:
    return stable_hash(
        {"motion": motion_prompt, "model": model, "mode": mode, "start": start_sha, "end": end_sha}
    )


def audio_item_hash(item: dict[str, Any], engine: str, model_version: str | None) -> str:
    """Hash of one SFX clip, section or track: its own fields plus engine parameters."""
    return stable_hash({"item": item, "engine": engine, "model_version": model_version})


def assemble_hash(item_hashes: list[str], assembly: dict[str, Any]) -> str:
    return stable_hash({"items": item_hashes, "assembly": assembly})


def build_hash(assemble: str, visual_loop: str, metadata: dict[str, Any]) -> str:
    return stable_hash({"assemble": assemble, "visual": visual_loop, "metadata": metadata})
