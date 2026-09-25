# Day 2 Disk Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Linux root-filesystem validator that parses `df -P /`, applies a configurable percentage threshold, and returns PASS/FAIL with the original command evidence.

**Architecture:** Keep command execution in the existing `CommandRunner`, parse POSIX `df` output in a small pure function, and apply policy in `validate_disk`. Return an immutable disk-specific result for Day 2; defer a shared validator hierarchy until later validators reveal a stable common interface.

**Tech Stack:** Python 3.10+, standard library dataclasses and typing, pytest 9

---

## File Structure

- Create `sysprobe/validators/__init__.py`: mark the validators package.
- Create `sysprobe/validators/disk.py`: parse `df` output, define the Day 2 result, and apply the disk threshold.
- Create `tests/test_disk.py`: cover parsing, decisions, command failures, malformed output, and configuration errors.
- Modify `README.md`: document Day 2 behavior, usage, and focused test commands.
- Create `docs/day2-disk-validator-summary.png`: colored beginner-oriented summary generated after verification.

### Task 1: Parse POSIX `df` Output

**Files:**
- Create: `sysprobe/validators/__init__.py`
- Create: `sysprobe/validators/disk.py`
- Create: `tests/test_disk.py`

- [ ] **Step 1: Write the failing parser test**

Create `tests/test_disk.py` with the import inside the test so pytest reports the missing Day 2 module as this test's expected failure:

```python
DF_OUTPUT = """Filesystem 1024-blocks Used Available Capacity Mounted on
/dev/sda1 10000000 7200000 2800000 72% /
"""


def test_parse_disk_usage_reads_capacity_percent() -> None:
    from sysprobe.validators.disk import parse_disk_usage

    assert parse_disk_usage(DF_OUTPUT) == 72
```

- [ ] **Step 2: Run the parser test and verify RED**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_disk.py::test_parse_disk_usage_reads_capacity_percent -v
```

Expected: FAIL because `sysprobe.validators` does not exist yet. The failure proves the new behavior is not already present.

- [ ] **Step 3: Add the minimal parser implementation**

Create an empty `sysprobe/validators/__init__.py` and create `sysprobe/validators/disk.py`:

```python
def parse_disk_usage(output: str) -> int:
    """Extract the capacity percentage from POSIX `df -P /` output."""

    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("df output does not contain a data row")

    fields = lines[-1].split()
    if len(fields) < 6:
        raise ValueError("df data row does not contain the expected columns")

    usage_token = fields[-2]
    if not usage_token.endswith("%") or not usage_token[:-1].isdigit():
        raise ValueError("df capacity column is not a percentage")

    return int(usage_token[:-1])
```

- [ ] **Step 4: Run the parser test and verify GREEN**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_disk.py::test_parse_disk_usage_reads_capacity_percent -v
```

Expected: PASS.

- [ ] **Step 5: Commit the parser slice**

```powershell
git add -- sysprobe/validators/__init__.py sysprobe/validators/disk.py tests/test_disk.py
git commit -m "feat: parse POSIX disk usage"
```

### Task 2: Apply the Disk Threshold

**Files:**
- Modify: `sysprobe/validators/disk.py`
- Modify: `tests/test_disk.py`

- [ ] **Step 1: Add the failing decision-table test**

Move `parse_disk_usage` to the module imports, then append these imports and
helpers to `tests/test_disk.py`. Keep the not-yet-created Day 2 names out of the
module imports so the RED run reaches the test body instead of stopping during
test collection:

```python
from collections.abc import Sequence

import pytest

from sysprobe.result import CommandResult
from sysprobe.validators.disk import parse_disk_usage


def make_df_output(usage_percent: int) -> str:
    return DF_OUTPUT.replace("72%", f"{usage_percent}%")


def make_command_result(
    *,
    stdout: str = DF_OUTPUT,
    stderr: str = "",
    exit_code: int | None = 0,
    timed_out: bool = False,
) -> CommandResult:
    return CommandResult(
        command=("df", "-P", "/"),
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.01,
        timed_out=timed_out,
    )
```

Keep the parser test, remove its function-local import, and append:

```python
@pytest.mark.parametrize(
    ("usage_percent", "threshold", "expected_passed", "expected_reason"),
    [
        (72, 90, True, "Disk usage 72% is below threshold 90%"),
        (72, 70, False, "Disk usage 72% reached or exceeded threshold 70%"),
        (90, 90, False, "Disk usage 90% reached or exceeded threshold 90%"),
    ],
)
def test_validate_disk_applies_threshold_rule(
    usage_percent: int,
    threshold: int,
    expected_passed: bool,
    expected_reason: str,
) -> None:
    from sysprobe.validators.disk import DiskValidationResult, validate_disk

    command_result = make_command_result(stdout=make_df_output(usage_percent))

    def fake_runner(command: Sequence[str]) -> CommandResult:
        assert tuple(command) == ("df", "-P", "/")
        return command_result

    result = validate_disk(threshold=threshold, command_executor=fake_runner)

    assert result == DiskValidationResult(
        passed=expected_passed,
        reason=expected_reason,
        mount_point="/",
        usage_percent=usage_percent,
        threshold_percent=threshold,
        command_result=command_result,
    )
```

- [ ] **Step 2: Run the decision test and verify RED**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_disk.py::test_validate_disk_applies_threshold_rule -v
```

Expected: FAIL inside the test because `DiskValidationResult` and
`validate_disk` do not exist. Test collection itself must succeed.

- [ ] **Step 3: Add the result model and successful-command policy**

Replace `sysprobe/validators/disk.py` with:

```python
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sysprobe.command_runner import run_command
from sysprobe.result import CommandResult


CommandExecutor = Callable[[Sequence[str]], CommandResult]


@dataclass(frozen=True, slots=True)
class DiskValidationResult:
    """The disk decision plus the command evidence behind it."""

    passed: bool
    reason: str
    mount_point: str
    usage_percent: int | None
    threshold_percent: int
    command_result: CommandResult


def parse_disk_usage(output: str) -> int:
    """Extract the capacity percentage from POSIX `df -P /` output."""

    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("df output does not contain a data row")

    fields = lines[-1].split()
    if len(fields) < 6:
        raise ValueError("df data row does not contain the expected columns")

    usage_token = fields[-2]
    if not usage_token.endswith("%") or not usage_token[:-1].isdigit():
        raise ValueError("df capacity column is not a percentage")

    return int(usage_token[:-1])


def validate_disk(
    *,
    threshold: int = 90,
    command_executor: CommandExecutor = run_command,
) -> DiskValidationResult:
    """Check Linux root-filesystem usage against a percentage threshold."""

    command_result = command_executor(["df", "-P", "/"])
    usage_percent = parse_disk_usage(command_result.stdout)
    passed = usage_percent < threshold

    if passed:
        reason = f"Disk usage {usage_percent}% is below threshold {threshold}%"
    else:
        reason = (
            f"Disk usage {usage_percent}% reached or exceeded "
            f"threshold {threshold}%"
        )

    return DiskValidationResult(
        passed=passed,
        reason=reason,
        mount_point="/",
        usage_percent=usage_percent,
        threshold_percent=threshold,
        command_result=command_result,
    )
```

- [ ] **Step 4: Run the decision test and full suite**

First move `DiskValidationResult` and `validate_disk` from the function-local
import into the existing module-level disk import:

```python
from sysprobe.validators.disk import (
    DiskValidationResult,
    parse_disk_usage,
    validate_disk,
)
```

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_disk.py::test_validate_disk_applies_threshold_rule -v
python -m pytest -v
```

Expected: the three decision cases PASS, and the full suite reports 10 passed.

- [ ] **Step 5: Commit the decision slice**

```powershell
git add -- sysprobe/validators/disk.py tests/test_disk.py
git commit -m "feat: validate root disk threshold"
```

### Task 3: Preserve Evidence for Failure Paths

**Files:**
- Modify: `sysprobe/validators/disk.py`
- Modify: `tests/test_disk.py`

- [ ] **Step 1: Add the failing malformed-output test**

Append:

```python
def test_validate_disk_returns_fail_for_malformed_output() -> None:
    command_result = make_command_result(stdout="not df output\n")

    result = validate_disk(
        command_executor=lambda _command: command_result,
    )

    assert result.passed is False
    assert result.reason == "Could not parse disk usage from df output"
    assert result.usage_percent is None
    assert result.command_result is command_result
```

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_disk.py::test_validate_disk_returns_fail_for_malformed_output -v
```

Expected: FAIL because `parse_disk_usage` currently raises `ValueError` instead of returning a validation result.

- [ ] **Step 2: Catch parser failure and verify GREEN**

In `validate_disk`, wrap parsing with:

```python
    try:
        usage_percent = parse_disk_usage(command_result.stdout)
    except ValueError:
        return DiskValidationResult(
            passed=False,
            reason="Could not parse disk usage from df output",
            mount_point="/",
            usage_percent=None,
            threshold_percent=threshold,
            command_result=command_result,
        )
```

Run the focused malformed-output test again. Expected: PASS.

- [ ] **Step 3: Add failing timeout and nonzero-exit tests**

Append:

```python
def test_validate_disk_returns_fail_for_timeout() -> None:
    command_result = make_command_result(
        stdout="partial output",
        exit_code=None,
        timed_out=True,
    )

    result = validate_disk(command_executor=lambda _command: command_result)

    assert result.passed is False
    assert result.reason == "Disk check timed out"
    assert result.usage_percent is None
    assert result.command_result is command_result


def test_validate_disk_returns_fail_for_nonzero_exit() -> None:
    command_result = make_command_result(
        stdout="",
        stderr="df: /: Permission denied\n",
        exit_code=1,
    )

    result = validate_disk(command_executor=lambda _command: command_result)

    assert result.passed is False
    assert result.reason == "df command failed with exit code 1"
    assert result.usage_percent is None
    assert result.command_result is command_result
```

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_disk.py::test_validate_disk_returns_fail_for_timeout tests/test_disk.py::test_validate_disk_returns_fail_for_nonzero_exit -v
```

Expected: FAIL because both cases currently fall through to malformed-output handling.

- [ ] **Step 4: Handle command failures before parsing and verify GREEN**

Immediately after obtaining `command_result`, add:

```python
    if command_result.timed_out:
        return DiskValidationResult(
            passed=False,
            reason="Disk check timed out",
            mount_point="/",
            usage_percent=None,
            threshold_percent=threshold,
            command_result=command_result,
        )

    if command_result.exit_code != 0:
        return DiskValidationResult(
            passed=False,
            reason=f"df command failed with exit code {command_result.exit_code}",
            mount_point="/",
            usage_percent=None,
            threshold_percent=threshold,
            command_result=command_result,
        )
```

Run the two focused tests again. Expected: both PASS.

- [ ] **Step 5: Add the failing invalid-threshold test**

Append:

```python
@pytest.mark.parametrize("threshold", [0, 101])
def test_validate_disk_rejects_threshold_outside_percentage_range(
    threshold: int,
) -> None:
    def unexpected_runner(_command: Sequence[str]) -> CommandResult:
        raise AssertionError("invalid configuration must fail before execution")

    with pytest.raises(
        ValueError,
        match="threshold must be an integer from 1 to 100",
    ):
        validate_disk(threshold=threshold, command_executor=unexpected_runner)
```

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_disk.py::test_validate_disk_rejects_threshold_outside_percentage_range -v
```

Expected: FAIL because threshold validation does not exist and the unexpected runner is called.

- [ ] **Step 6: Validate configuration before command execution**

At the beginning of `validate_disk`, add:

```python
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, int)
        or not 1 <= threshold <= 100
    ):
        raise ValueError("threshold must be an integer from 1 to 100")
```

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_disk.py -v
python -m pytest -v
```

Expected: 9 Day 2 cases PASS and 15 total cases PASS.

- [ ] **Step 7: Commit the failure-handling slice**

```powershell
git add -- sysprobe/validators/disk.py tests/test_disk.py
git commit -m "feat: report disk validation failures"
```

### Task 4: Document and Verify Day 2

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the README**

Change the introduction to cover both days, keep the existing Day 1 behavior,
and add:

````markdown
## Day 2 behavior

`validate_disk` runs `df -P /` on Linux, extracts the root-filesystem usage
percentage, and compares it with a configurable threshold. The default is 90%.

```python
from sysprobe.validators.disk import validate_disk

result = validate_disk()

print("PASS" if result.passed else "FAIL")
print(result.reason)
```

The returned result keeps the original `CommandResult`, so failures retain
stdout, stderr, exit code, duration, and timeout evidence. Running the real
validator requires Linux, while its deterministic unit tests run on Windows.

Run only the Day 2 tests:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_disk.py -v
```
````

- [ ] **Step 2: Run final verification**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -v
python -m compileall -q sysprobe
git diff --check
```

Expected: 15 tests PASS; compilation and diff checks exit with code 0 and no output.

- [ ] **Step 3: Commit documentation**

```powershell
git add -- README.md
git commit -m "docs: explain Day 2 disk validation"
```

### Task 5: Create the Colored Learning Summary

**Files:**
- Create: `docs/day2-disk-validator-summary.png`
- Modify: `README.md`

- [ ] **Step 1: Generate the infographic**

Use the built-in image generator with this content specification:

```text
Use case: infographic-diagram
Asset type: beginner learning summary for the SysProbe repository
Primary request: explain the Day 2 Disk Validator from Linux command to PASS/FAIL
Layout: landscape, left-to-right flow
Required flow: df -P / -> CommandRunner -> parse 72% -> compare with threshold 90% -> PASS or FAIL
Required side panel: timeout, nonzero exit, and malformed output all become FAIL with evidence preserved
Color palette: blue for command/data, amber for decisions, green for PASS, red for FAIL
Text: concise Traditional Chinese labels with monospace English code terms
Constraints: large readable type, high contrast, no logos, no watermark, no decorative clutter
```

Inspect the output for correct flow, readable text, and correct inequality:
`usage < threshold` is PASS; `usage >= threshold` is FAIL. Save the selected
image as `docs/day2-disk-validator-summary.png`.

- [ ] **Step 2: Link the image from the README**

Add below the Day 2 explanation:

```markdown
### Day 2 visual summary

![Day 2 Disk Validator flow](docs/day2-disk-validator-summary.png)
```

- [ ] **Step 3: Verify and commit the learning artifact**

Run:

```powershell
git diff --check
git status --short
```

Expected: only the new image and README update are pending. Then run:

```powershell
git add -- docs/day2-disk-validator-summary.png README.md
git commit -m "docs: add Day 2 visual summary"
```

### Task 6: Final Branch Verification

**Files:**
- Verify only; no planned modifications.

- [ ] **Step 1: Run the complete verification suite from a clean branch**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -v
python -m compileall -q sysprobe
git diff --check
git status --short --branch
```

Expected: 15 tests PASS; compile and diff checks succeed; the feature branch has no uncommitted changes.

- [ ] **Step 2: Review commits and changed paths**

```powershell
git log --oneline main..HEAD
git diff --stat main...HEAD
git diff --name-only main...HEAD
```

Expected changed paths:

```text
README.md
docs/day2-disk-validator-summary.png
docs/superpowers/plans/2026-09-25-disk-validator.md
sysprobe/validators/__init__.py
sysprobe/validators/disk.py
tests/test_disk.py
```

After this evidence is collected, use the finishing-a-development-branch workflow to decide whether to merge, push, or retain the branch.
