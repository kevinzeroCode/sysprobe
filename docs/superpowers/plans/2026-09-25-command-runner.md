# CommandRunner Day 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and document a safe local command runner that records stdout, stderr, exit code, elapsed time, and timeout state in a structured immutable result.

**Architecture:** `run_command` accepts an argument vector and delegates one process execution to `subprocess.run` with `shell=False`. It returns a frozen `CommandResult`; higher-level validators, rather than the runner, will interpret the recorded facts as PASS or FAIL.

**Tech Stack:** Python 3.10+, standard-library `subprocess`, `dataclasses`, and pytest 8/9.

---

## File Map

- Modify `.gitignore` to exclude Python virtual environments, caches, and bytecode.
- Create `sysprobe/__init__.py` as the package boundary.
- Create `sysprobe/result.py` for the immutable `CommandResult` data contract.
- Create `sysprobe/command_runner.py` for input validation and local process execution.
- Create `tests/test_command_runner.py` for real, platform-independent subprocess tests.
- Create `pytest.ini` for deterministic test discovery.
- Create `requirements.txt` for the Day 1 test dependency.
- Create `README.md` for setup, usage, behavior, and current limitations.

### Task 1: Capture a successful command

**Concept:** A process is a running program. A successful process normally exits with code `0`; its normal output is available on stdout.

**Files:**
- Modify: `.gitignore`
- Create: `tests/test_command_runner.py`
- Create: `sysprobe/__init__.py`
- Create: `sysprobe/result.py`
- Create: `sysprobe/command_runner.py`

- [ ] **Step 1: Add Python-generated files to `.gitignore`**

Keep the existing worktree rule and make the complete file:

```gitignore
.worktrees/
.venv/
__pycache__/
.pytest_cache/
*.py[cod]
```

This is repository hygiene, not production behavior; it prevents test runs from polluting `git status`.

- [ ] **Step 2: Write the first failing behavior test**

Create `tests/test_command_runner.py`:

```python
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
```

`sys.executable` means “use the same Python interpreter that is running pytest.” This creates a real child process without depending on a Windows- or Linux-only command.

- [ ] **Step 3: Run the test and observe RED**

Run in PowerShell:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_command_runner.py::test_run_command_captures_successful_process_output -v
```

Expected: test collection fails with `ModuleNotFoundError: No module named 'sysprobe'`. The failure is expected because no implementation package exists yet.

- [ ] **Step 4: Add the minimal package and immutable result model**

Create `sysprobe/__init__.py`:

```python
"""SysProbe Linux validation package."""
```

Create `sysprobe/result.py`:

```python
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
```

`frozen=True` prevents recorded execution facts from changing later. `slots=True` keeps this small value object explicit and prevents accidental new attributes.

- [ ] **Step 5: Add the smallest successful-command implementation**

Create `sysprobe/command_runner.py`:

```python
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
```

`time.perf_counter()` is monotonic, so system clock corrections cannot make the measured duration go backward. `check=True` is intentionally sufficient only for the current success test; the next failing test will expose why SysProbe needs different behavior.

- [ ] **Step 6: Run the test and observe GREEN**

Run:

```powershell
python -m pytest tests/test_command_runner.py::test_run_command_captures_successful_process_output -v
```

Expected: `1 passed`.

- [ ] **Step 7: Commit the successful-command slice**

```powershell
git add .gitignore sysprobe tests/test_command_runner.py
git commit -m "feat: capture successful command results"
```

### Task 2: Preserve nonzero exit results

**Concept:** A nonzero exit code means the child process completed and reported a problem. That is diagnostic evidence, not necessarily a Python programming exception.

**Files:**
- Modify: `tests/test_command_runner.py`
- Modify: `sysprobe/command_runner.py`

- [ ] **Step 1: Add a failing nonzero-exit test**

Append to `tests/test_command_runner.py`:

```python
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
```

- [ ] **Step 2: Run the test and observe RED**

Run:

```powershell
python -m pytest tests/test_command_runner.py::test_run_command_preserves_nonzero_exit_and_stderr -v
```

Expected: FAIL with `subprocess.CalledProcessError` because the current `check=True` converts a normal nonzero process result into an exception.

- [ ] **Step 3: Make nonzero completion return structured data**

In `sysprobe/command_runner.py`, change the subprocess option to:

```python
        check=False,
```

No other production change is needed. `subprocess.run` will now return a `CompletedProcess` for both exit code `0` and nonzero exit codes.

- [ ] **Step 4: Run both tests and observe GREEN**

Run:

```powershell
python -m pytest tests/test_command_runner.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the nonzero-exit behavior**

```powershell
git add sysprobe/command_runner.py tests/test_command_runner.py
git commit -m "feat: preserve nonzero command results"
```

### Task 3: Convert timeout into a structured result

**Concept:** A timeout means the process did not complete before the deadline, so it has no trustworthy exit code. Partial stdout and stderr are still useful diagnostic evidence.

**Files:**
- Modify: `tests/test_command_runner.py`
- Modify: `sysprobe/command_runner.py`

- [ ] **Step 1: Add a failing timeout test**

Append to `tests/test_command_runner.py`:

```python
def test_run_command_returns_timeout_with_partial_output() -> None:
    command = [
        sys.executable,
        "-c",
        (
            "import sys, time; "
            "sys.stdout.write('started'); "
            "sys.stdout.flush(); "
            "time.sleep(1)"
        ),
    ]

    result = run_command(command, timeout_seconds=0.2)

    assert result.command == tuple(command)
    assert result.exit_code is None
    assert result.stdout == "started"
    assert result.stderr == ""
    assert result.duration_seconds >= 0.2
    assert result.timed_out is True
```

The child flushes stdout before sleeping so the partial output is available when the timeout occurs.

- [ ] **Step 2: Run the test and observe RED**

Run:

```powershell
python -m pytest tests/test_command_runner.py::test_run_command_returns_timeout_with_partial_output -v
```

Expected: FAIL with `subprocess.TimeoutExpired` because the runner does not yet translate the timeout into `CommandResult`.

- [ ] **Step 3: Add timeout handling and partial-output normalization**

Replace `sysprobe/command_runner.py` with:

```python
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
```

Python can expose partial timeout streams as `bytes` even when `text=True`; `_to_text` keeps the public result fields consistently typed as `str`.

- [ ] **Step 4: Run all behavior tests and observe GREEN**

Run:

```powershell
python -m pytest tests/test_command_runner.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Commit timeout handling**

```powershell
git add sysprobe/command_runner.py tests/test_command_runner.py
git commit -m "feat: return structured timeout results"
```

### Task 4: Reject ambiguous or empty command input

**Concept:** A string such as `"free -m"` does not preserve argument boundaries, while an empty sequence cannot start a process. Rejecting both early produces a clear caller error.

**Files:**
- Modify: `tests/test_command_runner.py`
- Modify: `sysprobe/command_runner.py`

- [ ] **Step 1: Add a failing string-command test**

First add the pytest import near the top of `tests/test_command_runner.py`:

```python
import pytest
```

Then append:

```python
def test_run_command_rejects_a_string_command() -> None:
    with pytest.raises(ValueError, match="non-empty sequence of arguments"):
        run_command("echo hello")
```

- [ ] **Step 2: Run the string test and observe RED**

Run:

```powershell
python -m pytest tests/test_command_runner.py::test_run_command_rejects_a_string_command -v
```

Expected: FAIL because the current code treats the string as a sequence of individual characters and attempts to execute it.

- [ ] **Step 3: Reject string and bytes inputs**

Add this validation at the beginning of `run_command`, before converting the command to a tuple:

```python
    if isinstance(command, (str, bytes)):
        raise ValueError("command must be a non-empty sequence of arguments")
```

- [ ] **Step 4: Run the string test and observe GREEN**

Run:

```powershell
python -m pytest tests/test_command_runner.py::test_run_command_rejects_a_string_command -v
```

Expected: `1 passed`.

- [ ] **Step 5: Add a failing empty-command test**

Append to `tests/test_command_runner.py`:

```python
def test_run_command_rejects_an_empty_command() -> None:
    with pytest.raises(ValueError, match="non-empty sequence of arguments"):
        run_command([])
```

- [ ] **Step 6: Run the empty-command test and observe RED**

Run:

```powershell
python -m pytest tests/test_command_runner.py::test_run_command_rejects_an_empty_command -v
```

Expected: FAIL because `subprocess.run` receives no executable instead of the runner raising the documented `ValueError`.

- [ ] **Step 7: Extend validation to empty sequences**

Replace `sysprobe/command_runner.py` with the complete validated implementation:

```python
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
```

- [ ] **Step 8: Run the entire test file and observe GREEN**

Run:

```powershell
python -m pytest tests/test_command_runner.py -v
```

Expected: `5 passed`.

- [ ] **Step 9: Commit input validation**

```powershell
git add sysprobe/command_runner.py tests/test_command_runner.py
git commit -m "feat: validate command arguments"
```

### Task 5: Add reproducible test setup and beginner documentation

**Concept:** Code is not reproducible unless another person can install its dependencies, run its tests, and understand the intended API. These documentation and configuration files do not change production behavior, so they are verified directly rather than through a red-green cycle.

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `README.md`

- [ ] **Step 1: Declare the test dependency**

Create `requirements.txt`:

```text
pytest>=8,<10
```

- [ ] **Step 2: Constrain pytest discovery**

Create `pytest.ini`:

```ini
[pytest]
testpaths = tests
addopts = -ra
```

`testpaths` prevents pytest from scanning unrelated directories. `-ra` prints a concise summary for skipped, failed, or otherwise non-passing tests.

- [ ] **Step 3: Document Day 1 setup, API, and design choices**

Create `README.md`:

````markdown
# SysProbe

SysProbe is a learning-focused Linux validation framework. Day 1 builds the
local command-execution boundary that later CPU, memory, disk, network, and
service validators will share.

## Day 1 behavior

`run_command`:

- accepts an argument vector instead of a shell command string;
- captures stdout, stderr, exit code, and elapsed time;
- returns nonzero exit codes as structured evidence;
- turns a timeout into a structured result with `timed_out=True`.

The runner records what happened. Future validators decide whether those facts
mean PASS or FAIL.

## Requirements

- Python 3.10 or newer

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On Linux or WSL, activate the environment with:

```bash
source .venv/bin/activate
```

## Run the tests

```powershell
python -m pytest -v
```

If unrelated globally installed pytest plugins interfere with collection, run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -v
```

## Usage

```python
from sysprobe.command_runner import run_command

result = run_command(["free", "-m"], timeout_seconds=5.0)

print(result.exit_code)
print(result.stdout)
print(result.stderr)
print(result.timed_out)
```

The argument-vector API and `shell=False` avoid shell injection and keep
argument boundaries explicit. Shell pipelines, SSH, retries, validators, and
command-launch error classification are intentionally outside the Day 1 scope.
````

- [ ] **Step 4: Verify the complete Day 1 deliverable**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -v
python -m compileall -q sysprobe
git diff --check
```

Expected:

- pytest reports `5 passed`;
- `compileall` exits with code `0` and no output;
- `git diff --check` exits with code `0` and no whitespace errors.

- [ ] **Step 5: Commit documentation and test configuration**

```powershell
git add README.md requirements.txt pytest.ini
git commit -m "docs: explain Day 1 command runner"
```

### Task 6: Final acceptance check

**Files:**
- Verify only; no production files change.

- [ ] **Step 1: Run fresh verification from the feature worktree**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -v
python -m compileall -q sysprobe
git status --short --branch
```

Expected:

- `5 passed` and no warnings from the project;
- Python compilation succeeds;
- the branch is `feature/day1-command-runner` with a clean working tree.

- [ ] **Step 2: Review the learning outcomes aloud**

Be able to explain, without reading the implementation:

1. Why exit code `0` differs from a nonzero exit code.
2. Why stdout and stderr are captured separately.
3. Why timeout has `exit_code=None`.
4. Why `shell=False` and an argument vector are safer than a shell string.
5. Why CommandRunner records facts while validators decide PASS or FAIL.
