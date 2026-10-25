"""Sync the CLI compatibility range from compat.toml into plugin.json and SKILL.md.

Usage: python3 scripts/sync_compat.py <plugin-version>
"""

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = ROOT / "plugin" / ".claude-plugin" / "plugin.json"
SKILL_MD = ROOT / "plugin" / "skills" / "resonance-lite" / "SKILL.md"


def main() -> None:
    version = sys.argv[1]
    requires = tomllib.loads((ROOT / "compat.toml").read_text())["cli"]["requires"]

    manifest = json.loads(PLUGIN_JSON.read_text())
    manifest["version"] = version
    manifest.setdefault("metadata", {})["requires_cli"] = requires
    PLUGIN_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    skill = SKILL_MD.read_text()
    skill = re.sub(r"in the range `[^`]+`", f"in the range `{requires}`", skill)
    SKILL_MD.write_text(skill)


if __name__ == "__main__":
    main()
