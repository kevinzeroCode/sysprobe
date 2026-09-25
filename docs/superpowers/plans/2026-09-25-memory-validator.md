# Day 3 Memory Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Linux RAM validator that parses `/proc/meminfo`, calculates usage from `MemTotal - MemAvailable`, records swap context, and returns PASS/FAIL with original command evidence.

**Architecture:** Keep the established three-stage flow: `CommandRunner` captures facts, `parse_meminfo` converts named Linux fields into `MemoryMetrics`, and `validate_memory` applies the threshold. Keep the result memory-specific for Day 3 and postpone a shared validator hierarchy until the CPU validator provides a third concrete comparison.

**Tech Stack:** Python 3.10+, standard-library dataclasses and typing, pytest 9

---

## File Structure

- Create `sysprobe/validators/memory.py`: memory metrics, `/proc/meminfo` parser, result model, and validation policy.
- Create `tests/test_memory.py`: parser, policy, failure-path, and configuration tests.
- Modify `README.md`: Day 3 concepts, usage, and focused test command.
- Create `docs/day3-memory-validator-summary.png`: colored beginner learning summary.

### Task 1: Parse Valid `/proc/meminfo`

**Files:**
- Create: `tests/test_memory.py`
- Create: `sysprobe/validators/memory.py`

- [ ] **Step 1: Write the failing parser test**

Create `tests/test_memory.py`:

```python
MEMINFO_OUTPUT = """MemTotal:       16000000 kB
MemFree:         1000000 kB
MemAvailable:    6000000 kB
Buffers:          200000 kB
Cached:          4000000 kB
SwapTotal:       2000000 kB
SwapFree:        1500000 kB
"""


def test_parse_meminfo_reads_required_metrics() -> None:
    from sysprobe.validators.memory import MemoryMetrics, parse_meminfo

    assert parse_meminfo(MEMINFO_OUTPUT) == MemoryMetrics(
        total_kb=16_000_000,
        free_kb=1_000_000,
        available_kb=6_000_000,
        buffers_kb=200_000,
        cached_kb=4_000_000,
        swap_total_kb=2_000_000,
        swap_free_kb=1_500_000,
        used_kb=10_000_000,
        usage_percent=62.5,
    )
```

- [ ] **Step 2: Run the parser test and verify RED**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_memory.py::test_parse_meminfo_reads_required_metrics -v
```

Expected: FAIL inside the test because `sysprobe.validators.memory` does not exist.

- [ ] **Step 3: Add the minimal valid-input parser**

Create `sysprobe/validators/memory.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemoryMetrics:
    """Raw and calculated values from Linux `/proc/meminfo`."""

    total_kb: int
    free_kb: int
    available_kb: int
    buffers_kb: int
    cached_kb: int
    swap_total_kb: int
    swap_free_kb: int
    used_kb: int
    usage_percent: float


def parse_meminfo(output: str) -> MemoryMetrics:
    """Parse the Day 3 fields from `/proc/meminfo`."""

    wanted_fields = {
        "MemTotal",
        "MemFree",
        "MemAvailable",
        "Buffers",
        "Cached",
        "SwapTotal",
        "SwapFree",
    }
    values: dict[str, int] = {}

    for line in output.splitlines():
        if ":" not in line:
            continue
        name, raw_value = line.split(":", maxsplit=1)
        if name not in wanted_fields:
            continue
        value_text, _unit = raw_value.split()
        values[name] = int(value_text)

    total_kb = values["MemTotal"]
    available_kb = values["MemAvailable"]
    used_kb = total_kb - available_kb

    return MemoryMetrics(
        total_kb=total_kb,
        free_kb=values["MemFree"],
        available_kb=available_kb,
        buffers_kb=values["Buffers"],
        cached_kb=values["Cached"],
        swap_total_kb=values["SwapTotal"],
        swap_free_kb=values["SwapFree"],
        used_kb=used_kb,
        usage_percent=used_kb / total_kb * 100,
    )
```

- [ ] **Step 4: Run the parser test and verify GREEN**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_memory.py::test_parse_meminfo_reads_required_metrics -v
```

Expected: PASS.

- [ ] **Step 5: Commit the parser slice**

```powershell
git add -- sysprobe/validators/memory.py tests/test_memory.py
git commit -m "feat: parse Linux memory metrics"
```

### Task 2: Apply the RAM Threshold

**Files:**
- Modify: `sysprobe/validators/memory.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Add test helpers and the failing decision test**

Move the memory imports to module scope and add:

```python
from collections.abc import Sequence

import pytest

from sysprobe.result import CommandResult
from sysprobe.validators.memory import MemoryMetrics, parse_meminfo


def make_meminfo(
    *,
    total_kb: int = 1_000,
    free_kb: int = 50,
    available_kb: int = 400,
    buffers_kb: int = 100,
    cached_kb: int = 200,
    swap_total_kb: int = 500,
    swap_free_kb: int = 250,
) -> str:
    return f"""MemTotal:       {total_kb} kB
MemFree:        {free_kb} kB
MemAvailable:   {available_kb} kB
Buffers:        {buffers_kb} kB
Cached:         {cached_kb} kB
SwapTotal:      {swap_total_kb} kB
SwapFree:       {swap_free_kb} kB
"""


def make_command_result(
    *,
    stdout: str = MEMINFO_OUTPUT,
    stderr: str = "",
    exit_code: int | None = 0,
    timed_out: bool = False,
) -> CommandResult:
    return CommandResult(
        command=("cat", "/proc/meminfo"),
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.01,
        timed_out=timed_out,
    )
```

Keep the parser test without its function-local import, then append:

```python
@pytest.mark.parametrize(
    (
        "free_kb",
        "available_kb",
        "swap_free_kb",
        "threshold",
        "expected_passed",
        "expected_reason",
    ),
    [
        (50, 400, 250, 70, True, "Memory usage 60.0% is below threshold 70%"),
        (50, 100, 250, 90, False, "Memory usage 90.0% reached or exceeded threshold 90%"),
        (50, 50, 250, 90, False, "Memory usage 95.0% reached or exceeded threshold 90%"),
        (1, 600, 0, 50, True, "Memory usage 40.0% is below threshold 50%"),
    ],
)
def test_validate_memory_applies_available_memory_threshold(
    free_kb: int,
    available_kb: int,
    swap_free_kb: int,
    threshold: int,
    expected_passed: bool,
    expected_reason: str,
) -> None:
    from sysprobe.validators.memory import MemoryValidationResult, validate_memory

    command_result = make_command_result(
        stdout=make_meminfo(
            free_kb=free_kb,
            available_kb=available_kb,
            swap_free_kb=swap_free_kb,
        ),
    )

    def fake_runner(command: Sequence[str]) -> CommandResult:
        assert tuple(command) == ("cat", "/proc/meminfo")
        return command_result

    result = validate_memory(threshold=threshold, command_executor=fake_runner)

    assert result == MemoryValidationResult(
        passed=expected_passed,
        reason=expected_reason,
        metrics=parse_meminfo(command_result.stdout),
        threshold_percent=threshold,
        command_result=command_result,
    )
    assert result.metrics is not None
    assert result.metrics.free_kb == free_kb
    assert result.metrics.available_kb == available_kb
    assert result.metrics.swap_free_kb == swap_free_kb
```

- [ ] **Step 2: Run the decision test and verify RED**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_memory.py::test_validate_memory_applies_available_memory_threshold -v
```

Expected: FAIL inside the test because `MemoryValidationResult` and
`validate_memory` do not exist. Test collection must succeed.

- [ ] **Step 3: Add the result model and successful-command policy**

Add the imports at the top of `sysprobe/validators/memory.py`, define
`CommandExecutor` below the imports, and place `MemoryValidationResult` directly
after the existing `MemoryMetrics` class:

```python
from collections.abc import Callable, Sequence

from sysprobe.command_runner import run_command
from sysprobe.result import CommandResult


CommandExecutor = Callable[[Sequence[str]], CommandResult]


@dataclass(frozen=True, slots=True)
class MemoryValidationResult:
    """The memory decision plus the metrics and command evidence behind it."""

    passed: bool
    reason: str
    metrics: MemoryMetrics | None
    threshold_percent: int
    command_result: CommandResult
```

Append:

```python
def validate_memory(
    *,
    threshold: int = 90,
    command_executor: CommandExecutor = run_command,
) -> MemoryValidationResult:
    """Check Linux available-memory usage against a percentage threshold."""

    command_result = command_executor(["cat", "/proc/meminfo"])
    metrics = parse_meminfo(command_result.stdout)
    passed = metrics.usage_percent < threshold
    displayed_usage = f"{metrics.usage_percent:.1f}"

    if passed:
        reason = (
            f"Memory usage {displayed_usage}% is below threshold {threshold}%"
        )
    else:
        reason = (
            f"Memory usage {displayed_usage}% reached or exceeded "
            f"threshold {threshold}%"
        )

    return MemoryValidationResult(
        passed=passed,
        reason=reason,
        metrics=metrics,
        threshold_percent=threshold,
        command_result=command_result,
    )
```

- [ ] **Step 4: Move imports to module scope and verify GREEN**

Once the production names exist, use this complete module-level import in
`tests/test_memory.py` and remove the function-local import:

```python
from sysprobe.validators.memory import (
    MemoryMetrics,
    MemoryValidationResult,
    parse_meminfo,
    validate_memory,
)
```

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_memory.py::test_validate_memory_applies_available_memory_threshold -v
python -m pytest -v
```

Expected: four decision cases PASS and 20 total tests PASS. The fourth case
proves that low `MemFree` and fully used swap do not override sufficient
`MemAvailable`.

- [ ] **Step 5: Commit the policy slice**

```powershell
git add -- sysprobe/validators/memory.py tests/test_memory.py
git commit -m "feat: validate available memory threshold"
```

### Task 3: Reject Malformed Memory Data

**Files:**
- Modify: `sysprobe/validators/memory.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Add failing parser-validation tests**

Append:

```python
@pytest.mark.parametrize(
    ("output", "message"),
    [
        (
            MEMINFO_OUTPUT.replace("MemAvailable", "MissingAvailable"),
            "missing required memory fields",
        ),
        (
            MEMINFO_OUTPUT.replace("16000000 kB", "16000000 MB"),
            "memory values must use kB units",
        ),
        (
            MEMINFO_OUTPUT.replace("16000000 kB", "0 kB"),
            "MemTotal must be greater than zero",
        ),
        (
            MEMINFO_OUTPUT.replace(
                "MemAvailable:    6000000 kB",
                "MemAvailable:   17000000 kB",
            ),
            "MemAvailable must be between zero and MemTotal",
        ),
    ],
)
def test_parse_meminfo_rejects_malformed_metrics(
    output: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_meminfo(output)
```

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_memory.py::test_parse_meminfo_rejects_malformed_metrics -v
```

Expected: FAIL because missing fields currently raise `KeyError`, units are
ignored, zero total divides by zero, and out-of-range available memory is
accepted.

- [ ] **Step 2: Make parser errors explicit and verify GREEN**

Replace the loop and calculation section inside `parse_meminfo` with:

```python
    for line in output.splitlines():
        if ":" not in line:
            continue
        name, raw_value = line.split(":", maxsplit=1)
        if name not in wanted_fields:
            continue

        parts = raw_value.split()
        if len(parts) != 2:
            raise ValueError("memory values must contain a number and kB unit")
        value_text, unit = parts
        if unit != "kB":
            raise ValueError("memory values must use kB units")
        if not value_text.isdigit():
            raise ValueError("memory values must be non-negative integers")
        values[name] = int(value_text)

    missing_fields = wanted_fields.difference(values)
    if missing_fields:
        raise ValueError("missing required memory fields")

    total_kb = values["MemTotal"]
    available_kb = values["MemAvailable"]
    if total_kb <= 0:
        raise ValueError("MemTotal must be greater than zero")
    if not 0 <= available_kb <= total_kb:
        raise ValueError("MemAvailable must be between zero and MemTotal")

    used_kb = total_kb - available_kb
```

Keep the existing `MemoryMetrics` return unchanged. Run the four focused cases
again. Expected: all PASS.

- [ ] **Step 3: Add the failing malformed-result test**

Append:

```python
def test_validate_memory_returns_fail_for_malformed_output() -> None:
    command_result = make_command_result(stdout="not meminfo output\n")

    result = validate_memory(command_executor=lambda _command: command_result)

    assert result.passed is False
    assert result.reason == "Could not parse memory metrics from /proc/meminfo"
    assert result.metrics is None
    assert result.command_result is command_result
```

Run the focused test. Expected: FAIL because `ValueError` currently escapes
from the validator.

- [ ] **Step 4: Convert parser failure to a result and verify GREEN**

Wrap the parser call in `validate_memory`:

```python
    try:
        metrics = parse_meminfo(command_result.stdout)
    except ValueError:
        return MemoryValidationResult(
            passed=False,
            reason="Could not parse memory metrics from /proc/meminfo",
            metrics=None,
            threshold_percent=threshold,
            command_result=command_result,
        )
```

Run the focused malformed-result test. Expected: PASS.

- [ ] **Step 5: Commit malformed-data handling**

```powershell
git add -- sysprobe/validators/memory.py tests/test_memory.py
git commit -m "feat: reject malformed memory metrics"
```

### Task 4: Handle Command and Configuration Failures

**Files:**
- Modify: `sysprobe/validators/memory.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Add failing timeout and nonzero-exit tests**

Append:

```python
def test_validate_memory_returns_fail_for_timeout() -> None:
    command_result = make_command_result(
        stdout="partial output",
        exit_code=None,
        timed_out=True,
    )

    result = validate_memory(command_executor=lambda _command: command_result)

    assert result.passed is False
    assert result.reason == "Memory check timed out"
    assert result.metrics is None
    assert result.command_result is command_result


def test_validate_memory_returns_fail_for_nonzero_exit() -> None:
    command_result = make_command_result(
        stdout="",
        stderr="cat: /proc/meminfo: Permission denied\n",
        exit_code=1,
    )

    result = validate_memory(command_executor=lambda _command: command_result)

    assert result.passed is False
    assert result.reason == "cat /proc/meminfo failed with exit code 1"
    assert result.metrics is None
    assert result.command_result is command_result
```

Run both focused tests. Expected: FAIL because both are currently classified as
malformed output.

- [ ] **Step 2: Classify command failures before parsing**

Immediately after receiving `command_result`, add:

```python
    if command_result.timed_out:
        return MemoryValidationResult(
            passed=False,
            reason="Memory check timed out",
            metrics=None,
            threshold_percent=threshold,
            command_result=command_result,
        )

    if command_result.exit_code != 0:
        return MemoryValidationResult(
            passed=False,
            reason=(
                "cat /proc/meminfo failed with exit code "
                f"{command_result.exit_code}"
            ),
            metrics=None,
            threshold_percent=threshold,
            command_result=command_result,
        )
```

Run both focused tests again. Expected: PASS.

- [ ] **Step 3: Add the failing threshold test**

Append:

```python
@pytest.mark.parametrize("threshold", [0, 101])
def test_validate_memory_rejects_threshold_outside_percentage_range(
    threshold: int,
) -> None:
    def unexpected_runner(_command: Sequence[str]) -> CommandResult:
        raise AssertionError("invalid configuration must fail before execution")

    with pytest.raises(
        ValueError,
        match="threshold must be an integer from 1 to 100",
    ):
        validate_memory(threshold=threshold, command_executor=unexpected_runner)
```

Run the focused test. Expected: FAIL because the command executor is called.

- [ ] **Step 4: Validate threshold before command execution**

At the start of `validate_memory`, add:

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
python -m pytest tests/test_memory.py -v
python -m pytest -v
```

Expected: 14 Day 3 cases PASS and 29 total tests PASS.

- [ ] **Step 5: Commit failure handling**

```powershell
git add -- sysprobe/validators/memory.py tests/test_memory.py
git commit -m "feat: report memory validation failures"
```

### Task 5: Document and Verify Day 3

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add Day 3 documentation**

Update the introduction to mention Day 3 and add before Requirements:

````markdown
## Day 3 behavior

`validate_memory` runs `cat /proc/meminfo` on Linux and calculates RAM usage
from `MemTotal - MemAvailable`. The default failure threshold is 90%.

```python
from sysprobe.validators.memory import validate_memory

result = validate_memory()

print("PASS" if result.passed else "FAIL")
print(result.reason)
```

Linux may use otherwise idle RAM for reclaimable caches, so low `MemFree` does
not by itself mean memory pressure. SysProbe uses `MemAvailable` for its
decision. Swap totals are recorded for context but do not affect Day 3 status.

Running the real validator requires Linux. Its deterministic tests run on
Windows with representative `/proc/meminfo` samples.

Run only the Day 3 tests:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_memory.py -v
```
````

- [ ] **Step 2: Run documentation verification**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -v
python -m compileall -q sysprobe
git diff --check
```

Expected: 29 tests PASS; compilation and diff checks exit with code 0.

- [ ] **Step 3: Commit documentation**

```powershell
git add -- README.md
git commit -m "docs: explain Day 3 memory validation"
```

### Task 6: Create the Colored Learning Summary

**Files:**
- Create: `docs/day3-memory-validator-summary.png`
- Modify: `README.md`

- [ ] **Step 1: Generate and inspect the infographic**

Use the built-in image generator with this specification:

```text
Use case: infographic-diagram
Asset type: beginner learning summary for the SysProbe repository
Primary request: explain the Day 3 Memory Validator from /proc/meminfo to PASS/FAIL
Layout: 16:9 landscape, left-to-right main flow with two small learning panels
Required flow: cat /proc/meminfo -> CommandRunner -> parse named fields -> used = MemTotal - MemAvailable -> compare threshold 90% -> PASS or FAIL
Learning panel 1: MemFree is immediately unused RAM; MemAvailable includes reclaimable memory and drives the decision
Learning panel 2: SwapTotal and SwapFree are recorded only and do not change Day 3 PASS/FAIL
Failure panel: timeout, nonzero exit, or malformed fields -> FAIL + reason + CommandResult
Color palette: blue for data, amber for calculation and decision, green for PASS, red for FAIL, purple for swap context
Text: concise Traditional Chinese labels with exact English field names
Constraints: large readable type, accurate inequality usage < threshold is PASS and usage >= threshold is FAIL, no logo, no watermark, no clutter
```

Inspect the image for readable labels, correct use of `MemAvailable`, swap's
non-decision role, and the correct threshold inequalities. Save the selected
asset as `docs/day3-memory-validator-summary.png`.

- [ ] **Step 2: Link the image from README**

Add under the Day 3 section:

```markdown
### Day 3 visual summary

![Day 3 Memory Validator flow](docs/day3-memory-validator-summary.png)
```

- [ ] **Step 3: Verify and commit the learning artifact**

```powershell
git diff --check
git status --short
git add -- docs/day3-memory-validator-summary.png README.md
git commit -m "docs: add Day 3 visual summary"
```

Before committing, verify that only the new image and README update are
pending.

### Task 7: Final Branch Verification

**Files:**
- Verify only; no planned modifications.

- [ ] **Step 1: Run the complete suite from a clean branch**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -v
python -m compileall -q sysprobe
git diff --check
git status --short --branch
```

Expected: 29 tests PASS; compile and diff checks succeed; no uncommitted feature
changes remain.

- [ ] **Step 2: Review commits and changed paths**

```powershell
git log --oneline main..HEAD
git diff --stat main...HEAD
git diff --name-only main...HEAD
```

Expected changed paths:

```text
README.md
docs/day3-memory-validator-summary.png
docs/superpowers/plans/2026-09-25-memory-validator.md
sysprobe/validators/memory.py
tests/test_memory.py
```

After gathering this evidence, use the finishing-a-development-branch workflow
to select merge, push, retain, or discard.
