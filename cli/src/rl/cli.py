"""Command-line entrypoint for `rlite`."""

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

from rl import __version__
from rl.config import enabled_providers
from rl.exitcodes import ExitCode, RlError
from rl.hashing import plan_hash
from rl.paths import jobs_dir, resolve_job
from rl.plan import load_plan, new_job_id, skeleton
from rl.stage import derive_stage
from rl.state import StateStore, now_iso
from rl.validate import validate_plan

EXIT_USAGE = int(ExitCode.USAGE)


class _Parser(argparse.ArgumentParser):
    """Argument parser that exits with EX_USAGE (64) instead of argparse's default 2.

    Exit code 2 is not used for usage errors so Claude never confuses a flag typo
    with a plan validation error.
    """

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _emit(args: argparse.Namespace, payload: dict[str, Any], human: str) -> None:
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(human)


def cmd_new(args: argparse.Namespace) -> int:
    root = jobs_dir()
    root.mkdir(parents=True, exist_ok=True)
    base = new_job_id(args.idea)
    job_id, n = base, 2
    while (root / job_id).exists():
        job_id, n = f"{base}-{n}", n + 1
    job = root / job_id
    job.mkdir()
    (job / "plan.json").write_text(
        json.dumps(skeleton(args.idea, args.mode), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    StateStore(job)
    _emit(args, {"job_id": job_id, "path": str(job)}, f"Created job {job_id}\n  {job}/plan.json")
    return ExitCode.OK


def cmd_validate(args: argparse.Namespace) -> int:
    job = resolve_job(args.job)
    plan = load_plan(job)
    report = validate_plan(plan, enabled_providers(), job_dir=job)
    StateStore(job).replace(
        "validate",
        {
            "ok": report.ok,
            "plan_hash": plan_hash(plan),
            "errors": len(report.errors),
            "warnings": len(report.warnings),
            "at": now_iso(),
        },
    )
    lines = [f"{'OK' if report.ok else 'INVALID'}: {job.name}"]
    lines += [f"  error   {i.path}: {i.message}" for i in report.errors]
    lines += [f"  warning {i.path}: {i.message}" for i in report.warnings]
    _emit(args, report.to_dict(), "\n".join(lines))
    return ExitCode.OK if report.ok else ExitCode.VALIDATION


def _job_summary(job: Path) -> dict[str, Any]:
    plan = load_plan(job)
    store = StateStore(job)
    steps = {
        s: store.read(s).get("status", "pending")
        for s in ("still", "audio", "visual", "build", "qc")
    }
    return {
        "job_id": job.name,
        "stage": derive_stage(job, plan),
        "mode": plan.get("mode"),
        "idea": plan.get("idea"),
        "steps": steps,
    }


def cmd_status(args: argparse.Namespace) -> int:
    if args.job:
        summary = _job_summary(resolve_job(args.job))
        steps = "  ".join(f"{k}:{v}" for k, v in summary["steps"].items())
        _emit(
            args,
            summary,
            f"{summary['job_id']}  [{summary['stage']}]  {summary['mode']}\n  {steps}",
        )
        return ExitCode.OK
    root = jobs_dir()
    jobs = sorted(p for p in root.iterdir() if (p / "plan.json").is_file()) if root.is_dir() else []
    summaries = [_job_summary(j) for j in jobs]
    human = "\n".join(f"{s['job_id']:<50} {s['stage']:<12} {s['mode']}" for s in summaries)
    _emit(args, {"jobs": summaries}, human or 'No jobs yet. Create one with `rlite new "<idea>"`.')
    return ExitCode.OK


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="rlite", description="Resonance Lite CLI")
    parser.add_argument("--version", action="version", version=f"rlite {__version__}")
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)

    def add(
        name: str, func: Callable[[argparse.Namespace], int], help_: str
    ) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_)
        p.add_argument("--json", action="store_true", help="machine-readable output")
        p.set_defaults(func=func)
        return p

    p_new = add("new", cmd_new, "create a job with a plan skeleton")
    p_new.add_argument("idea")
    p_new.add_argument("--mode", choices=["ambient", "functional", "playlist"])
    add("validate", cmd_validate, "validate a job's plan").add_argument("job")
    add("status", cmd_status, "show one job or list all jobs").add_argument("job", nargs="?")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return ExitCode.OK
    try:
        return int(args.func(args))
    except RlError as err:
        payload = {"error": str(err), "code": int(err.code), "hint": err.hint}
        if getattr(args, "json", False):
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"error: {err}" + (f"\nhint: {err.hint}" if err.hint else ""), file=sys.stderr)
        return int(err.code)


if __name__ == "__main__":
    sys.exit(main())
