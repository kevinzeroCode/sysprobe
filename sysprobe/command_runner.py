from collections.abc import Sequence
import locale
import subprocess
import time

from sysprobe.result import CommandErrorKind, CommandResult


def _to_text(output: bytes | str | None, *, encoding: str) -> str:
    """Normalize timeout output into the public string representation."""

    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(encoding=encoding, errors="replace")
    return output


def _launch_error_result(
    command: tuple[str, ...],
    started_at: float,
    error: OSError,
    error_kind: CommandErrorKind,
) -> CommandResult:
    return CommandResult(
        command=command,
        exit_code=None,
        stdout="",
        stderr="",
        duration_seconds=time.perf_counter() - started_at,
        timed_out=False,
        error_kind=error_kind,
        error_message=str(error) or error_kind.value,
    )


def run_command(
    command: Sequence[str],
    *,
    timeout_seconds: float | None = 30.0,
) -> CommandResult:
    """Run one local command and capture its observable result."""

    if isinstance(command, (str, bytes)) or not command:
        raise ValueError("command must be a non-empty sequence of arguments")

    recorded_command = tuple(command)
    output_encoding = locale.getpreferredencoding(False)
    started_at = time.perf_counter()

    try:
        completed = subprocess.run(
            recorded_command,
            capture_output=True,
            text=True,
            encoding=output_encoding,
            errors="replace",
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        return CommandResult(
            command=recorded_command,
            exit_code=None,
            stdout=_to_text(error.stdout, encoding=output_encoding),
            stderr=_to_text(error.stderr, encoding=output_encoding),
            duration_seconds=time.perf_counter() - started_at,
            timed_out=True,
        )
    except FileNotFoundError as error:
        return _launch_error_result(
            recorded_command, started_at, error, CommandErrorKind.NOT_FOUND
        )
    except PermissionError as error:
        return _launch_error_result(
            recorded_command, started_at, error, CommandErrorKind.PERMISSION_DENIED
        )
    except OSError as error:
        return _launch_error_result(
            recorded_command, started_at, error, CommandErrorKind.OS_ERROR
        )

    return CommandResult(
        command=recorded_command,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=time.perf_counter() - started_at,
        timed_out=False,
    )
