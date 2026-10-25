"""Access to the bundled pricing table."""

from functools import cache
from importlib import resources
from typing import Any

import yaml


@cache
def pricing() -> dict[str, Any]:
    text = resources.files("rl").joinpath("pricing.yaml").read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.safe_load(text)
    return data


def usd_per_credit(provider: str, plan: str | None) -> float:
    table: dict[str, float] = pricing()[provider]["usd_per_credit"]
    if isinstance(table, (int, float)):
        return float(table)
    if plan and plan in table:
        return float(table[plan])
    return float(max(table.values()))  # unknown plan: assume the most expensive per credit
