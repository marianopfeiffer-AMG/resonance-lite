# Contributing

Thanks for helping. Read [CODESTYLE.md](CODESTYLE.md) first: every rule there is enforced in review.

## Development setup

```bash
git clone https://github.com/marianopfeiffer-AMG/resonance-lite
cd resonance-lite/cli
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

Test the plugin locally from the repository root:

```bash
claude plugin validate --strict .
claude plugin marketplace add ./
```

## Rules

- One task from [ROADMAP.md](ROADMAP.md) per commit, using [Conventional Commits](https://www.conventionalcommits.org/).
- CI must be green. No network calls in tests: mock providers.
- Pull requests that touch `plugin/` get the `skill-change` label and require maintainer review. The plugin must stay Markdown-only (CI enforces it).
- Any paid provider call goes through the budget reservation (`rl.budget`). PRs that bypass it are not merged.
- By contributing you agree your contribution is licensed under the MIT License.
