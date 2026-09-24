from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Facts captured from one local command execution."""

    command: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool
