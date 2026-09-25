import locale
import subprocess
import sys

import pytest

from sysprobe.command_runner import run_command


def test_run_command_captures_successful_process_output() -> None:
    command = [sys.executable, "-c", "print('hello')"]

    result = run_command(command, timeout_seconds=1.0)

    assert result.command == tuple(command)
    assert result.exit_code == 0
    assert result.stdout == "hello\n"
    assert result.stderr == ""
    assert result.duration_seconds >= 0
    assert result.timed_out is False


def test_run_command_preserves_nonzero_exit_and_stderr() -> None:
    command = [
        sys.executable,
        "-c",
        "import sys; sys.stderr.write('problem\\n'); sys.exit(7)",
    ]

    result = run_command(command, timeout_seconds=1.0)

    assert result.command == tuple(command)
    assert result.exit_code == 7
    assert result.stdout == ""
    assert result.stderr == "problem\n"
    assert result.timed_out is False


def test_run_command_returns_timeout_with_partial_output() -> None:
    command = [
        sys.executable,
        "-c",
        (
            "import sys, time; "
            "sys.stdout.write('started'); "
            "sys.stdout.flush(); "
            "time.sleep(5)"
        ),
    ]

    # One second leaves startup margin on Windows and CI while still proving
    # that the five-second child is terminated by the runner's deadline.
    result = run_command(command, timeout_seconds=1.0)

    assert result.command == tuple(command)
    assert result.exit_code is None
    assert result.stdout == "started"
    assert result.stderr == ""
    assert result.duration_seconds >= 1.0
    assert result.timed_out is True


def test_run_command_decodes_timeout_output_using_preferred_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(locale, "getpreferredencoding", lambda _setlocale: "cp950")

    def raise_timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(
            cmd=("diagnostic",),
            timeout=1.0,
            output="測試".encode("cp950"),
            stderr=b"",
        )

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    result = run_command(["diagnostic"], timeout_seconds=1.0)

    assert result.stdout == "測試"
    assert result.stderr == ""
    assert result.exit_code is None
    assert result.timed_out is True


def test_run_command_rejects_a_string_command() -> None:
    with pytest.raises(ValueError, match="non-empty sequence of arguments"):
        run_command("echo hello")


def test_run_command_rejects_an_empty_command() -> None:
    with pytest.raises(ValueError, match="non-empty sequence of arguments"):
        run_command([])
