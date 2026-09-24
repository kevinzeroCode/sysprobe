from collections.abc import Sequence
import subprocess
import time

from sysprobe.result import CommandResult


def _to_text(output: bytes | str | None) -> str:
    """Normalize timeout output into the public string representation."""

    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output


def run_command(
    command: Sequence[str],
    *,
    timeout_seconds: float | None = 30.0,
) -> CommandResult:
    """Run one local command and capture its observable result."""

    if isinstance(command, (str, bytes)) or not command:
        raise ValueError("command must be a non-empty sequence of arguments")

    recorded_command = tuple(command)
    started_at = time.perf_counter()

    try:
        completed = subprocess.run(
            recorded_command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        return CommandResult(
            command=recorded_command,
            exit_code=None,
            stdout=_to_text(error.stdout),
            stderr=_to_text(error.stderr),
            duration_seconds=time.perf_counter() - started_at,
            timed_out=True,
        )

    return CommandResult(
        command=recorded_command,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=time.perf_counter() - started_at,
        timed_out=False,
    )
