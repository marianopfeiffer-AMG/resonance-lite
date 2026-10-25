"""Process exit codes and the typed error hierarchy that maps to them."""

from enum import IntEnum


class ExitCode(IntEnum):
    """Exit codes consumed by the Claude Code skill. Keep in sync with the README table."""

    OK = 0
    INTERNAL = 1
    VALIDATION = 10
    RUNNING = 11
    NEEDS_APPROVAL = 12
    STALE = 13
    CONFIG = 20
    BUDGET = 21
    QUOTA = 22
    PROVIDER = 30
    FFMPEG = 31
    DISK = 32
    STATE_CORRUPT = 33
    PARTIAL = 40
    QC_FAILED = 41
    USAGE = 64
    LOCKED = 75


class RlError(Exception):
    """Base error. Every expected failure carries the exit code the CLI returns."""

    code: ExitCode = ExitCode.INTERNAL

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class ConfigError(RlError):
    code = ExitCode.CONFIG


class ValidationFailed(RlError):
    code = ExitCode.VALIDATION


class LockedError(RlError):
    code = ExitCode.LOCKED


class StateCorrupt(RlError):
    code = ExitCode.STATE_CORRUPT


class NeedsApproval(RlError):
    code = ExitCode.NEEDS_APPROVAL


class BudgetExceeded(RlError):
    code = ExitCode.BUDGET


class QuotaExhausted(RlError):
    code = ExitCode.QUOTA


class ProviderError(RlError):
    """A provider call failed. `retryable` tells the orchestrator whether retrying is safe."""

    code = ExitCode.PROVIDER

    def __init__(self, message: str, *, hint: str | None = None, retryable: bool = False) -> None:
        super().__init__(message, hint=hint)
        self.retryable = retryable


class StaleItems(RlError):
    code = ExitCode.STALE
