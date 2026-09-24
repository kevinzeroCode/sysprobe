import sys

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
