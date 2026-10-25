"""Lexical rule lists shipped with the package (rules/*.txt) and negation-aware matching."""

import re
from functools import cache
from importlib import resources

NEGATIONS = frozenset({"no", "not", "without", "never", "zero", "non", "nothing", "avoid"})
NEGATION_WINDOW = 3
_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@cache
def load_terms(name: str) -> tuple[str, ...]:
    """Load a rule list, ignoring comments and blank lines."""
    text = resources.files("rl").joinpath("rules", f"{name}.txt").read_text(encoding="utf-8")
    lines = (line.strip().lower() for line in text.splitlines())
    return tuple(line for line in lines if line and not line.startswith("#"))


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def find_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    """Return the terms present in text that are NOT negated by a nearby preceding word.

    "no sudden sounds" does not match "sudden"; "sudden thunder" does.
    Multi-word terms ("breaking waves") are matched as consecutive tokens.
    """
    tokens = tokenize(text)
    found: list[str] = []
    for term in terms:
        term_tokens = term.split()
        size = len(term_tokens)
        for i in range(len(tokens) - size + 1):
            if tokens[i : i + size] != term_tokens:
                continue
            window = tokens[max(0, i - NEGATION_WINDOW) : i]
            if not NEGATIONS.intersection(window):
                found.append(term)
                break
    return found
