"""Command-line entrypoint for `rlite`."""

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

from rl import __version__
from rl.audio.step import AudioStep
from rl.budget import Budget
from rl.build import BuildStep
from rl.config import enabled_providers
from rl.estimate import estimate
from rl.exitcodes import ConfigError, ExitCode, RlError
from rl.hashing import plan_hash
from rl.paths import jobs_dir, resolve_job
from rl.plan import load_plan, new_job_id, skeleton
from rl.providers import registry
from rl.providers.higgsfield import Higgsfield
from rl.qc import run_qc
from rl.secrets import KNOWN_KEYS, delete_secret, has_secret, prompt_secret, set_secret
from rl.stage import derive_stage
from rl.state import StateStore, now_iso
from rl.validate import validate_plan
from rl.visual.step import VisualStep, run_still

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


def cmd_estimate(args: argparse.Namespace) -> int:
    job = resolve_job(args.job)
    plan = load_plan(job)
    result = estimate(plan, live=None if args.offline else Higgsfield())
    if args.monthly:
        result["monthly"] = {
            "videos": args.monthly,
            "usd": round(result["total_usd"] * args.monthly, 2),
            "credits": {k: v["credits"] * args.monthly for k, v in result["providers"].items()},
        }
    lines = [f"Estimate for {job.name}: ~USD {result['total_usd']:.2f}"]
    lines += [
        f"  {name}: {p['credits']} credits ≈ USD {p['usd']:.2f}"
        for name, p in result["providers"].items()
    ]
    lines.append(f"  time: {result['time_minutes']['low']}-{result['time_minutes']['high']} min")
    lines.append(
        f"  disk: master {result['disk_gb']['master']} GB, peak {result['disk_gb']['peak']} GB"
    )
    if "monthly" in result:
        lines.append(
            f"  {args.monthly} videos/month ≈ USD {result['monthly']['usd']:.2f} "
            "(plus subscriptions)"
        )
    lines += [f"  note: {n}" for n in result["notes"]]
    _emit(args, result, "\n".join(lines))
    return ExitCode.OK


def cmd_key(args: argparse.Namespace) -> int:
    if args.action == "status":
        state = {name: has_secret(name) for name in KNOWN_KEYS}
        human = "\n".join(f"{n}: {'configured' if ok else 'missing'}" for n, ok in state.items())
        _emit(args, {"keys": state}, human)
        return ExitCode.OK
    if not args.provider:
        raise ConfigError("Name the provider, e.g. `rlite key set elevenlabs`.")
    if args.action == "delete":
        delete_secret(args.provider)
        _emit(
            args, {"deleted": args.provider}, f"Deleted the {args.provider} key from this computer."
        )
        return ExitCode.OK
    value = prompt_secret(args.provider, from_clipboard=args.from_clipboard)
    where = set_secret(args.provider, value, allow_file=args.allow_file_storage)
    note = " (0600 file: no OS keychain on this system)" if where == "file" else ""
    _emit(
        args, {"saved": args.provider, "storage": where}, f"Saved your {args.provider} key{note}."
    )
    return ExitCode.OK


def cmd_providers(args: argparse.Namespace) -> int:
    if args.action == "enable":
        registry.enable(args.name)
    elif args.action == "disable":
        registry.disable(args.name)
    rows = registry.status()
    human = "\n".join(f"{r['name']}: {'enabled' if r['enabled'] else 'disabled'}" for r in rows)
    _emit(args, {"providers": rows}, human)
    return ExitCode.OK


def cmd_budget(args: argparse.Namespace) -> int:
    budget = Budget(resolve_job(args.job))
    if args.action == "allow":
        if args.usd is None or args.usd <= 0:
            raise ConfigError("Pass a positive amount with --usd.")
        budget.allow_extra(args.usd)
    summary = budget.summary()
    human = (
        f"job: USD {summary['job_usd']:.2f} of {summary['job_cap_usd']:.2f}  |  "
        f"month: USD {summary['month_usd']:.2f} of {summary['month_cap_usd']:.2f}"
    )
    _emit(args, summary, human)
    return ExitCode.OK


def cmd_audio(args: argparse.Namespace) -> int:
    job = resolve_job(args.job)
    state = AudioStep(job, load_plan(job)).run(
        assemble_only=args.assemble_only, regen_stale=args.regen_stale
    )
    assemble = state.get("assemble", {})
    human = f"Audio ready: {assemble.get('output')} ({assemble.get('duration_s')} s)"
    for warning in assemble.get("warnings", []):
        human += f"\n  warning: {warning}"
    _emit(args, {"status": state.get("status"), "assemble": assemble}, human)
    return ExitCode.OK


def cmd_still(args: argparse.Namespace) -> int:
    job = resolve_job(args.job)
    state = run_still(job, load_plan(job), reroll=args.reroll)
    _emit(args, state, f"Still ready: {state.get('output')}")
    return ExitCode.OK


def cmd_approve(args: argparse.Namespace) -> int:
    job = resolve_job(args.job)
    plan = load_plan(job)
    store = StateStore(job)
    validated, still = store.read("validate"), store.read("still")
    current = plan_hash(plan)
    if not (validated.get("ok") and validated.get("plan_hash") == current):
        raise ConfigError("The current plan is not validated.", hint="Run `rlite validate <job>`.")
    if still.get("status") != "done":
        raise ConfigError(
            "There is no still yet.", hint="Run `rlite still <job>` and show it to the user."
        )
    record = {
        "plan_hash": current,
        "still_sha256": still["sha256"],
        "approved_at": now_iso(),
        "by": "user",
    }
    store.replace("approval", record)
    _emit(args, record, f"Approved {job.name}. Production can start.")
    return ExitCode.OK


def cmd_visual(args: argparse.Namespace) -> int:
    job = resolve_job(args.job)
    state = VisualStep(job, load_plan(job)).run(regen_stale=args.regen_stale)
    _emit(args, state, f"Visual ready ({state.get('kind')}): {state.get('output')}")
    return ExitCode.OK


def cmd_build(args: argparse.Namespace) -> int:
    job = resolve_job(args.job)
    state = BuildStep(job, load_plan(job)).run()
    human = (
        f"Video ready: {state.get('video')} "
        f"({state.get('duration_s')} s, {state.get('size_mb')} MB)"
    )
    for warning in state.get("warnings", []):
        human += f"\n  warning: {warning}"
    _emit(args, state, human)
    return ExitCode.OK


def cmd_qc(args: argparse.Namespace) -> int:
    job = resolve_job(args.job)
    state = run_qc(job, load_plan(job))
    lines = [f"QC {'PASSED' if state['passed'] else 'FAILED'} for {job.name}"]
    for c in state["checks"]:
        mark = "ok  " if c["ok"] else ("FAIL" if c["severity"] == "fail" else "warn")
        lines.append(f"  {mark} {c['name']}: {c['value']} (expected {c['threshold']})")
    lines.append("  frames: " + ", ".join(state["frames"]))
    _emit(args, state, "\n".join(lines))
    if not state["passed"]:
        return ExitCode.QC_FAILED
    return ExitCode.PARTIAL if any(not c["ok"] for c in state["checks"]) else ExitCode.OK


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

    p_est = add("estimate", cmd_estimate, "estimate cost, time and disk for a job")
    p_est.add_argument("job")
    p_est.add_argument("--monthly", type=int, metavar="N", help="project N videos per month")
    p_est.add_argument("--offline", action="store_true", help="skip live Higgsfield cost lookup")

    p_key = add("key", cmd_key, "manage YOUR provider API keys (run in your own terminal)")
    p_key.add_argument("action", choices=["set", "status", "delete"])
    p_key.add_argument("provider", nargs="?", choices=list(KNOWN_KEYS))
    p_key.add_argument(
        "--from-clipboard", action="store_true", help="read the key from the clipboard"
    )
    p_key.add_argument("--allow-file-storage", action="store_true", help="0600 file if no keychain")

    p_prov = add("providers", cmd_providers, "list, enable or disable optional providers")
    p_prov.add_argument("action", nargs="?", default="list", choices=["list", "enable", "disable"])
    p_prov.add_argument("name", nargs="?", default="suno")

    p_still = add("still", cmd_still, "generate the still image shown at the checkpoint")
    p_still.add_argument("job")
    p_still.add_argument("--reroll", action="store_true", help="generate a new still (~2 credits)")
    add("approve", cmd_approve, "record the user's approval of plan + still").add_argument("job")
    p_vis = add("visual", cmd_visual, "generate the animated loop (after approval)")
    p_vis.add_argument("job")
    p_vis.add_argument("--regen-stale", action="store_true", help="regenerate changed paid clips")

    p_aud = add("audio", cmd_audio, "generate missing audio items and assemble the bed/mix")
    p_aud.add_argument("job")
    p_aud.add_argument("--assemble-only", action="store_true", help="re-assemble, generate nothing")
    p_aud.add_argument("--regen-stale", action="store_true", help="regenerate changed paid items")

    add("build", cmd_build, "assemble the final video, thumbnail and upload sheet").add_argument(
        "job"
    )
    add("qc", cmd_qc, "quality checks + frames for review").add_argument("job")

    p_bud = add("budget", cmd_budget, "show a job's spend or raise its cap (your terminal only)")
    p_bud.add_argument("action", choices=["show", "allow"])
    p_bud.add_argument("job")
    p_bud.add_argument("--usd", type=float)
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
