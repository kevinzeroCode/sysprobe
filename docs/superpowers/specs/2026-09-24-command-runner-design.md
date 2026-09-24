# CommandRunner Day 1 Design

## Context

SysProbe needs a small, dependable boundary around operating-system process
execution before it can add Linux validators. Development starts with the
available Windows Python environment, while the public API remains suitable
for later Linux and WSL validation.

## Goals

- Execute one local process without invoking a shell.
- Preserve the command, exit code, standard output, standard error, duration,
  and timeout state in a structured result.
- Treat a normal nonzero exit code as data instead of raising an exception.
- Convert a timeout into a structured result and preserve partial output when
  Python makes it available.
- Prove success, nonzero-exit, and timeout behavior with platform-independent
  pytest tests.
- Provide enough setup and documentation to run the Day 1 test suite directly.

## Non-goals

Day 1 does not add shell command strings, pipelines, SSH, retries, validators,
diagnostic logging, JSON reporting, a CLI, or command-not-found
classification. Those features belong to later days in the 30-day plan.

## Chosen Approach

Use a small `run_command` function plus an immutable `CommandResult` dataclass.
Callers pass an argument vector such as `["free", "-m"]`; the implementation
uses `subprocess.run` with `shell=False`.

This design is preferred over string commands because argument boundaries are
explicit, shell injection is avoided, and behavior is more consistent between
Windows and Linux. A stateful runner class is intentionally deferred because
Day 1 has no configuration or dependency that requires object state.

## Public API

```python
@dataclass(frozen=True, slots=True)
class CommandResult:
    command: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool


def run_command(
    command: Sequence[str],
    *,
    timeout_seconds: float | None = 30.0,
) -> CommandResult:
    ...
```

The command must be a nonempty sequence of arguments rather than a `str` or
`bytes` value. Invalid caller input raises `ValueError`. A `None` timeout is
allowed for callers that deliberately want no deadline, although SysProbe will
normally use the 30-second default.

## Execution and Result Flow

1. Validate and copy the command into a tuple so the recorded command cannot
   change after execution starts.
2. Record a monotonic start time with `time.perf_counter`.
3. Run the command with output capture, text mode, `check=False`, and the
   supplied timeout.
4. On normal completion, return stdout, stderr, and the actual exit code with
   `timed_out=False`.
5. On `subprocess.TimeoutExpired`, return any captured output with
   `exit_code=None` and `timed_out=True`.
6. Record elapsed time on both paths.

The runner does not interpret exit codes as PASS or FAIL. That policy belongs
to validators, while this layer reports process facts faithfully.

## Error Boundaries

- Nonzero exit: return normally with the process exit code and captured
  streams.
- Timeout: return normally with an absent exit code and `timed_out=True`.
- Invalid API input: raise `ValueError` before starting a process.
- Missing executable, permission denial, and other launch failures remain
  exceptions on Day 1. Day 12 will introduce explicit error classification
  rather than adding a premature model now.

The timeout path must normalize partial output because Python may expose it as
`bytes`, `str`, or `None` depending on platform and version.

## Files

- `sysprobe/__init__.py`: expose the package without adding behavior.
- `sysprobe/result.py`: define `CommandResult` only.
- `sysprobe/command_runner.py`: validate input and execute one local process.
- `tests/test_command_runner.py`: platform-independent behavior tests using
  `sys.executable -c` child processes.
- `pytest.ini`: constrain discovery to `tests/` and show concise summaries.
- `requirements.txt`: declare pytest as the only Day 1 dependency.
- `README.md`: explain the current scope, setup, API, and test command.

## Test Strategy

Implementation follows red-green-refactor separately for each behavior:

1. A successful Python child writes to stdout and exits zero.
2. A failing Python child writes to stderr and exits with code 7.
3. A sleeping Python child exceeds a short deadline and returns a timeout
   result instead of raising.
4. Small input-validation tests reject empty and string commands before a
   child process is created.

The tests call the active Python interpreter through `sys.executable`, so they
exercise real subprocess behavior without depending on a Windows or Linux
utility. Later WSL work will add Linux integration checks rather than weakening
these deterministic unit tests.

## Completion Criteria

- Each behavior was first observed as a failing test for the expected reason.
- `python -m pytest` passes with third-party pytest plugin autoload disabled if
  the host plugin set remains unstable.
- The public result fields match the Day 1 plan.
- The README shows one safe argv-based usage example and explains why
  `shell=False` is the default.

