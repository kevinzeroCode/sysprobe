from collections.abc import Sequence
import subprocess
import time

from sysprobe.result import CommandResult


def run_command(
    command: Sequence[str],
    *,
    timeout_seconds: float | None = 30.0,
) -> CommandResult:
    """Run one local command and capture its observable result."""

    recorded_command = tuple(command)
    started_at = time.perf_counter()
    completed = subprocess.run(
        recorded_command,
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout_seconds,
    )
    duration_seconds = time.perf_counter() - started_at

    return CommandResult(
        command=recorded_command,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=duration_seconds,
        timed_out=False,
    )
