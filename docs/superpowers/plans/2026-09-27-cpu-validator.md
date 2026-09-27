# Day 4 CPU Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Linux CPU validator that normalizes the one-minute load average by available CPU count and returns an evidence-backed PASS or FAIL.

**Architecture:** Keep CPU handling in `sysprobe/validators/cpu.py`. Two independent `CommandRunner` calls collect `/proc/loadavg` and `nproc`; focused parsers validate each output, and `validate_cpu` combines them into `CpuMetrics` before applying the threshold. Keep the result CPU-specific and preserve both command records instead of introducing a shared validator hierarchy.

**Tech Stack:** Python 3.10+, standard-library dataclasses, `math`, typing, pytest 9, deterministic SVG

---

## File Structure

- Create `sysprobe/validators/cpu.py`: load parser, CPU-count parser, metrics, result model, command-failure aggregation, and threshold policy.
- Create `tests/test_cpu.py`: parser, decision, evidence, failure, aggregation, and configuration tests.
- Modify `README.md`: Day 4 concepts, commands, usage, comparison with Day 3, and focused test command.
- Create `docs/day4-cpu-validator-summary.svg`: colored beginner summary of the two-input CPU flow.

### Task 1: Parse Linux Load Average

**Files:**
- Create: `tests/test_cpu.py`
- Create: `sysprobe/validators/cpu.py`

- [ ] **Step 1: Write the failing load parser tests**

Create `tests/test_cpu.py`:

```python
import pytest

from sysprobe.validators.cpu import parse_loadavg


def test_parse_loadavg_reads_three_time_windows() -> None:
    assert parse_loadavg("0.42 0.58 0.61 2/123 4567\n") == (
        0.42,
        0.58,
        0.61,
    )


@pytest.mark.parametrize(
    ("output", "message"),
    [
        ("", "loadavg output must contain three load averages"),
        ("0.1 nope 0.3 1/10 123\n", "load averages must be numbers"),
        (
            "-0.1 0.2 0.3 1/10 123\n",
            "load averages must be finite non-negative numbers",
        ),
        (
            "nan 0.2 0.3 1/10 123\n",
            "load averages must be finite non-negative numbers",
        ),
        (
            "inf 0.2 0.3 1/10 123\n",
            "load averages must be finite non-negative numbers",
        ),
    ],
)
def test_parse_loadavg_rejects_malformed_values(
    output: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_loadavg(output)
```

- [ ] **Step 2: Run the load parser tests and verify RED**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_cpu.py -v
```

Purpose: run only the new Day 4 module so the first failure is easy to read.

Expected: test collection fails because `sysprobe.validators.cpu` does not yet
exist. This proves the new tests are exercising missing Day 4 behavior rather
than passing accidentally.

- [ ] **Step 3: Add the minimal load parser**

Create `sysprobe/validators/cpu.py`:

```python
import math


def parse_loadavg(output: str) -> tuple[float, float, float]:
    """Parse the 1-, 5-, and 15-minute values from `/proc/loadavg`."""

    fields = output.split()
    if len(fields) < 3:
        raise ValueError("loadavg output must contain three load averages")

    try:
        load_1m, load_5m, load_15m = (
            float(fields[0]),
            float(fields[1]),
            float(fields[2]),
        )
    except ValueError as error:
        raise ValueError("load averages must be numbers") from error

    loads = (load_1m, load_5m, load_15m)
    if any(not math.isfinite(load) or load < 0 for load in loads):
        raise ValueError("load averages must be finite non-negative numbers")

    return loads
```

- [ ] **Step 4: Re-run the load parser tests and verify GREEN**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_cpu.py -v
```

Purpose: confirm the parser accepts standard Linux output and rejects missing,
nonnumeric, negative, `NaN`, and infinite values.

Expected: 6 tests pass.

- [ ] **Step 5: Commit the load parser slice**

```powershell
git add -- sysprobe/validators/cpu.py tests/test_cpu.py
git commit -m "feat: parse Linux CPU load averages"
```

Purpose: save one small, independently tested unit before adding CPU-count
behavior.

### Task 2: Parse the Available CPU Count

**Files:**
- Modify: `tests/test_cpu.py`
- Modify: `sysprobe/validators/cpu.py`

- [ ] **Step 1: Add failing `nproc` parser tests**

Update the import in `tests/test_cpu.py`:

```python
from sysprobe.validators.cpu import parse_cpu_count, parse_loadavg
```

Append:

```python
def test_parse_cpu_count_reads_positive_integer() -> None:
    assert parse_cpu_count("  8\n") == 8


@pytest.mark.parametrize("output", ["", "0\n", "-1\n", "4.0\n", "4 8\n"])
def test_parse_cpu_count_rejects_malformed_values(output: str) -> None:
    with pytest.raises(
        ValueError,
        match="CPU count must be one positive integer",
    ):
        parse_cpu_count(output)
```

- [ ] **Step 2: Run only the CPU-count tests and verify RED**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_cpu.py -k cpu_count -v
```

Purpose: `-k cpu_count` selects tests whose names contain `cpu_count`, keeping
the feedback focused on the new parser.

Expected: collection fails because `parse_cpu_count` does not exist.

- [ ] **Step 3: Add the minimal CPU-count parser**

Append to `sysprobe/validators/cpu.py`:

```python
def parse_cpu_count(output: str) -> int:
    """Parse the positive processing-unit count returned by `nproc`."""

    fields = output.split()
    if len(fields) != 1 or not fields[0].isdigit():
        raise ValueError("CPU count must be one positive integer")

    cpu_count = int(fields[0])
    if cpu_count <= 0:
        raise ValueError("CPU count must be one positive integer")

    return cpu_count
```

- [ ] **Step 4: Re-run all parser tests and verify GREEN**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_cpu.py -v
```

Purpose: check both parsers together before adding command execution.

Expected: 12 tests pass.

- [ ] **Step 5: Commit the CPU-count parser slice**

```powershell
git add -- sysprobe/validators/cpu.py tests/test_cpu.py
git commit -m "feat: parse available CPU count"
```

### Task 3: Normalize Load and Apply the Threshold

**Files:**
- Modify: `tests/test_cpu.py`
- Modify: `sysprobe/validators/cpu.py`

- [ ] **Step 1: Add command helpers and failing decision tests**

Replace the imports at the top of `tests/test_cpu.py` with:

```python
from collections.abc import Callable, Sequence

import pytest

from sysprobe.result import CommandResult
from sysprobe.validators.cpu import (
    CpuMetrics,
    CpuValidationResult,
    parse_cpu_count,
    parse_loadavg,
    validate_cpu,
)
```

Add below the imports:

```python
LOAD_COMMAND = ("cat", "/proc/loadavg")
CPU_COUNT_COMMAND = ("nproc",)


def make_command_result(
    command: tuple[str, ...],
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = 0,
    timed_out: bool = False,
) -> CommandResult:
    return CommandResult(
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.01,
        timed_out=timed_out,
    )


def make_executor(
    load_result: CommandResult,
    cpu_count_result: CommandResult,
) -> tuple[
    Callable[[Sequence[str]], CommandResult],
    list[tuple[str, ...]],
]:
    calls: list[tuple[str, ...]] = []
    results = {
        LOAD_COMMAND: load_result,
        CPU_COUNT_COMMAND: cpu_count_result,
    }

    def execute(command: Sequence[str]) -> CommandResult:
        recorded_command = tuple(command)
        calls.append(recorded_command)
        return results[recorded_command]

    return execute, calls
```

Append the decision test:

```python
@pytest.mark.parametrize(
    (
        "load_output",
        "cpu_count",
        "threshold",
        "expected_normalized",
        "expected_passed",
        "expected_reason",
    ),
    [
        (
            "3.00 1.50 0.75 2/100 1234\n",
            4,
            1.0,
            0.75,
            True,
            "Normalized CPU load 0.75 is below threshold 1.00",
        ),
        (
            "4.00 2.00 1.00 2/100 1234\n",
            4,
            1.0,
            1.0,
            False,
            "Normalized CPU load 1.00 reached or exceeded threshold 1.00",
        ),
        (
            "5.00 2.00 1.00 2/100 1234\n",
            4,
            1.0,
            1.25,
            False,
            "Normalized CPU load 1.25 reached or exceeded threshold 1.00",
        ),
        (
            "1.00 9.00 12.00 2/100 1234\n",
            2,
            1,
            0.5,
            True,
            "Normalized CPU load 0.50 is below threshold 1.00",
        ),
    ],
)
def test_validate_cpu_normalizes_one_minute_load(
    load_output: str,
    cpu_count: int,
    threshold: float,
    expected_normalized: float,
    expected_passed: bool,
    expected_reason: str,
) -> None:
    load_result = make_command_result(LOAD_COMMAND, stdout=load_output)
    cpu_count_result = make_command_result(
        CPU_COUNT_COMMAND,
        stdout=f"{cpu_count}\n",
    )
    executor, calls = make_executor(load_result, cpu_count_result)

    result = validate_cpu(threshold=threshold, command_executor=executor)

    load_1m, load_5m, load_15m = parse_loadavg(load_output)
    assert result == CpuValidationResult(
        passed=expected_passed,
        reason=expected_reason,
        metrics=CpuMetrics(
            load_1m=load_1m,
            load_5m=load_5m,
            load_15m=load_15m,
            logical_cpu_count=cpu_count,
            normalized_load_1m=expected_normalized,
        ),
        threshold=float(threshold),
        load_command_result=load_result,
        cpu_count_command_result=cpu_count_result,
    )
    assert calls == [LOAD_COMMAND, CPU_COUNT_COMMAND]
```

The fourth case deliberately gives very high 5- and 15-minute loads. It proves
that Day 4 records those values but bases status only on the one-minute value.

- [ ] **Step 2: Run the decision test and verify RED**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_cpu.py::test_validate_cpu_normalizes_one_minute_load -v
```

Purpose: isolate the new orchestration and policy test.

Expected: collection fails because `CpuMetrics`, `CpuValidationResult`, and
`validate_cpu` do not exist.

- [ ] **Step 3: Add the result models and successful-path policy**

Replace the existing top-level `import math` in
`sysprobe/validators/cpu.py` with these imports:

```python
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import math

from sysprobe.command_runner import run_command
from sysprobe.result import CommandResult


CommandExecutor = Callable[[Sequence[str]], CommandResult]
```

Keep the existing parsers, then place these dataclasses after them:

```python
@dataclass(frozen=True, slots=True)
class CpuMetrics:
    """Raw Linux load values plus the normalized one-minute load."""

    load_1m: float
    load_5m: float
    load_15m: float
    logical_cpu_count: int
    normalized_load_1m: float


@dataclass(frozen=True, slots=True)
class CpuValidationResult:
    """The CPU decision plus both command records behind it."""

    passed: bool
    reason: str
    metrics: CpuMetrics | None
    threshold: float
    load_command_result: CommandResult
    cpu_count_command_result: CommandResult
```

Append:

```python
def validate_cpu(
    *,
    threshold: float = 1.0,
    command_executor: CommandExecutor = run_command,
) -> CpuValidationResult:
    """Check normalized Linux one-minute load against a threshold."""

    threshold_value = float(threshold)
    load_result = command_executor(["cat", "/proc/loadavg"])
    cpu_count_result = command_executor(["nproc"])

    load_1m, load_5m, load_15m = parse_loadavg(load_result.stdout)
    logical_cpu_count = parse_cpu_count(cpu_count_result.stdout)
    normalized_load_1m = load_1m / logical_cpu_count
    passed = normalized_load_1m < threshold_value

    if passed:
        reason = (
            f"Normalized CPU load {normalized_load_1m:.2f} is below "
            f"threshold {threshold_value:.2f}"
        )
    else:
        reason = (
            f"Normalized CPU load {normalized_load_1m:.2f} reached or "
            f"exceeded threshold {threshold_value:.2f}"
        )

    return CpuValidationResult(
        passed=passed,
        reason=reason,
        metrics=CpuMetrics(
            load_1m=load_1m,
            load_5m=load_5m,
            load_15m=load_15m,
            logical_cpu_count=logical_cpu_count,
            normalized_load_1m=normalized_load_1m,
        ),
        threshold=threshold_value,
        load_command_result=load_result,
        cpu_count_command_result=cpu_count_result,
    )
```

- [ ] **Step 4: Run the focused and complete suites and verify GREEN**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_cpu.py::test_validate_cpu_normalizes_one_minute_load -v
python -m pytest -v
```

Purpose: the first command verifies the new CPU decision cases; the second is
a regression check for Days 1 through 3.

Expected: 4 focused cases pass and 45 total tests pass.

- [ ] **Step 5: Commit the CPU policy slice**

```powershell
git add -- sysprobe/validators/cpu.py tests/test_cpu.py
git commit -m "feat: validate normalized CPU load"
```

### Task 4: Classify and Aggregate Command Failures

**Files:**
- Modify: `tests/test_cpu.py`
- Modify: `sysprobe/validators/cpu.py`

- [ ] **Step 1: Add failing individual failure tests**

Append to `tests/test_cpu.py`:

```python
@pytest.mark.parametrize(
    ("load_result", "cpu_count_result", "expected_reason"),
    [
        (
            make_command_result(
                LOAD_COMMAND,
                stdout="partial output",
                exit_code=None,
                timed_out=True,
            ),
            make_command_result(CPU_COUNT_COMMAND, stdout="4\n"),
            "CPU check failed: load average command timed out",
        ),
        (
            make_command_result(LOAD_COMMAND, exit_code=2),
            make_command_result(CPU_COUNT_COMMAND, stdout="4\n"),
            "CPU check failed: load average command failed with exit code 2",
        ),
        (
            make_command_result(
                LOAD_COMMAND,
                stdout="1.0 0.5 0.2 1/10 123\n",
            ),
            make_command_result(
                CPU_COUNT_COMMAND,
                stdout="partial",
                exit_code=None,
                timed_out=True,
            ),
            "CPU check failed: nproc timed out",
        ),
        (
            make_command_result(
                LOAD_COMMAND,
                stdout="1.0 0.5 0.2 1/10 123\n",
            ),
            make_command_result(CPU_COUNT_COMMAND, exit_code=1),
            "CPU check failed: nproc failed with exit code 1",
        ),
        (
            make_command_result(LOAD_COMMAND, stdout="not loadavg\n"),
            make_command_result(CPU_COUNT_COMMAND, stdout="4\n"),
            "CPU check failed: malformed /proc/loadavg output",
        ),
        (
            make_command_result(
                LOAD_COMMAND,
                stdout="1.0 0.5 0.2 1/10 123\n",
            ),
            make_command_result(CPU_COUNT_COMMAND, stdout="zero\n"),
            "CPU check failed: malformed nproc output",
        ),
    ],
)
def test_validate_cpu_reports_command_or_parse_failure(
    load_result: CommandResult,
    cpu_count_result: CommandResult,
    expected_reason: str,
) -> None:
    executor, calls = make_executor(load_result, cpu_count_result)

    result = validate_cpu(command_executor=executor)

    assert result.passed is False
    assert result.reason == expected_reason
    assert result.metrics is None
    assert result.load_command_result is load_result
    assert result.cpu_count_command_result is cpu_count_result
    assert calls == [LOAD_COMMAND, CPU_COUNT_COMMAND]
```

- [ ] **Step 2: Add the failing simultaneous-failure test**

Append:

```python
def test_validate_cpu_reports_both_failures_in_stable_order() -> None:
    load_result = make_command_result(LOAD_COMMAND, stdout="not loadavg\n")
    cpu_count_result = make_command_result(CPU_COUNT_COMMAND, exit_code=1)
    executor, calls = make_executor(load_result, cpu_count_result)

    result = validate_cpu(command_executor=executor)

    assert result.reason == (
        "CPU check failed: malformed /proc/loadavg output; "
        "nproc failed with exit code 1"
    )
    assert result.metrics is None
    assert result.load_command_result is load_result
    assert result.cpu_count_command_result is cpu_count_result
    assert calls == [LOAD_COMMAND, CPU_COUNT_COMMAND]
```

- [ ] **Step 3: Run the failure tests and verify RED**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_cpu.py -k "failure or failures" -v
```

Purpose: select the seven new error cases. The current implementation assumes
both commands succeeded and lets parser errors escape.

Expected: all selected cases fail because structured failure aggregation has
not been implemented.

- [ ] **Step 4: Add command classification and replace `validate_cpu`**

Add this private helper above `validate_cpu`:

```python
def _command_failure(
    result: CommandResult,
    *,
    description: str,
) -> str | None:
    if result.timed_out:
        return f"{description} timed out"
    if result.exit_code != 0:
        return f"{description} failed with exit code {result.exit_code}"
    return None
```

Replace `validate_cpu` with:

```python
def validate_cpu(
    *,
    threshold: float = 1.0,
    command_executor: CommandExecutor = run_command,
) -> CpuValidationResult:
    """Check normalized Linux one-minute load against a threshold."""

    threshold_value = float(threshold)
    load_result = command_executor(["cat", "/proc/loadavg"])
    cpu_count_result = command_executor(["nproc"])
    failures: list[str] = []

    loads: tuple[float, float, float] | None = None
    load_failure = _command_failure(
        load_result,
        description="load average command",
    )
    if load_failure is not None:
        failures.append(load_failure)
    else:
        try:
            loads = parse_loadavg(load_result.stdout)
        except ValueError:
            failures.append("malformed /proc/loadavg output")

    logical_cpu_count: int | None = None
    cpu_count_failure = _command_failure(
        cpu_count_result,
        description="nproc",
    )
    if cpu_count_failure is not None:
        failures.append(cpu_count_failure)
    else:
        try:
            logical_cpu_count = parse_cpu_count(cpu_count_result.stdout)
        except ValueError:
            failures.append("malformed nproc output")

    if failures:
        return CpuValidationResult(
            passed=False,
            reason="CPU check failed: " + "; ".join(failures),
            metrics=None,
            threshold=threshold_value,
            load_command_result=load_result,
            cpu_count_command_result=cpu_count_result,
        )

    assert loads is not None
    assert logical_cpu_count is not None
    load_1m, load_5m, load_15m = loads
    normalized_load_1m = load_1m / logical_cpu_count
    passed = normalized_load_1m < threshold_value

    if passed:
        reason = (
            f"Normalized CPU load {normalized_load_1m:.2f} is below "
            f"threshold {threshold_value:.2f}"
        )
    else:
        reason = (
            f"Normalized CPU load {normalized_load_1m:.2f} reached or "
            f"exceeded threshold {threshold_value:.2f}"
        )

    return CpuValidationResult(
        passed=passed,
        reason=reason,
        metrics=CpuMetrics(
            load_1m=load_1m,
            load_5m=load_5m,
            load_15m=load_15m,
            logical_cpu_count=logical_cpu_count,
            normalized_load_1m=normalized_load_1m,
        ),
        threshold=threshold_value,
        load_command_result=load_result,
        cpu_count_command_result=cpu_count_result,
    )
```

- [ ] **Step 5: Re-run the failure and complete tests and verify GREEN**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_cpu.py -k "failure or failures" -v
python -m pytest -v
```

Purpose: prove individual and simultaneous errors become results while all
earlier behavior remains intact.

Expected: 7 focused cases pass and 52 total tests pass.

- [ ] **Step 6: Commit failure aggregation**

```powershell
git add -- sysprobe/validators/cpu.py tests/test_cpu.py
git commit -m "feat: report CPU validation failures"
```

### Task 5: Reject Invalid Threshold Configuration

**Files:**
- Modify: `tests/test_cpu.py`
- Modify: `sysprobe/validators/cpu.py`

- [ ] **Step 1: Add failing threshold-validation tests**

Append to `tests/test_cpu.py`:

```python
@pytest.mark.parametrize(
    "threshold",
    [0, -0.1, float("nan"), float("inf"), True, "1.0"],
)
def test_validate_cpu_rejects_invalid_threshold(threshold: object) -> None:
    def unexpected_runner(_command: Sequence[str]) -> CommandResult:
        raise AssertionError("invalid configuration must fail before execution")

    with pytest.raises(
        ValueError,
        match="threshold must be a finite number greater than zero",
    ):
        validate_cpu(
            threshold=threshold,  # type: ignore[arg-type]
            command_executor=unexpected_runner,
        )
```

- [ ] **Step 2: Run the threshold tests and verify RED**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_cpu.py::test_validate_cpu_rejects_invalid_threshold -v
```

Purpose: prove invalid configuration is rejected before either Linux command
can run.

Expected: cases fail because the current validator converts or executes before
performing explicit validation.

- [ ] **Step 3: Validate and normalize the threshold before execution**

At the start of `validate_cpu`, replace the direct conversion with:

```python
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(threshold)
        or threshold <= 0
    ):
        raise ValueError("threshold must be a finite number greater than zero")

    threshold_value = float(threshold)
```

Keep both command calls immediately after this block.

- [ ] **Step 4: Run the focused CPU and complete suites and verify GREEN**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_cpu.py -v
python -m pytest -v
```

Purpose: verify all parser, policy, failure, and configuration behavior, then
check Days 1 through 3 for regressions.

Expected: 29 Day 4 cases pass and 58 total tests pass.

- [ ] **Step 5: Commit threshold validation**

```powershell
git add -- sysprobe/validators/cpu.py tests/test_cpu.py
git commit -m "feat: validate CPU load threshold"
```

### Task 6: Document Day 4 Behavior

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the project introduction**

Extend the introduction so its final sentence reads:

```markdown
Day 3 adds a memory validator based on Linux available-memory semantics. Day 4
adds a CPU validator that normalizes Linux load average by available CPU count.
```

- [ ] **Step 2: Add the Day 4 section before Requirements**

Insert:

````markdown
## Day 4 behavior

`validate_cpu` runs `cat /proc/loadavg` and `nproc` on Linux. It divides the
one-minute load average by the available CPU count, then compares that
normalized value with a configurable threshold. The default is `1.0`.

```python
from sysprobe.validators.cpu import validate_cpu

result = validate_cpu()

print("PASS" if result.passed else "FAIL")
print(result.reason)
```

Load average is not CPU utilization percentage. It includes runnable work and
tasks waiting in uninterruptible sleep. The 5- and 15-minute values are kept
for context, but only the 1-minute value decides Day 4 status.

Unlike the Day 3 memory check, Day 4 needs two Linux commands. The result keeps
both `CommandResult` records so command, timeout, exit-code, stdout, and stderr
evidence remain available for debugging.

The real commands require Linux. Deterministic tests run on Windows with
representative `/proc/loadavg` and `nproc` output.

Run only the Day 4 tests:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/test_cpu.py -v
```
````

- [ ] **Step 3: Verify the documentation change**

```powershell
git diff --check
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -v
```

Purpose: `git diff --check` detects whitespace errors; the test command proves
documentation edits did not disturb the 58-test suite.

Expected: diff check exits with code 0 and 58 tests pass.

- [ ] **Step 4: Commit the Day 4 documentation**

```powershell
git add -- README.md
git commit -m "docs: explain Day 4 CPU validation"
```

### Task 7: Add the Colored Day 4 Learning Summary

**Files:**
- Create: `docs/day4-cpu-validator-summary.svg`
- Modify: `README.md`

- [ ] **Step 1: Create the deterministic SVG**

Create `docs/day4-cpu-validator-summary.svg` with this exact structure and
content. The code-native format keeps commands, formulas, and inequalities
exact while still producing a colored image:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="800" viewBox="0 0 1400 800" role="img" aria-labelledby="title desc">
  <title id="title">SysProbe Day 4 CPU Validator</title>
  <desc id="desc">Two Linux commands provide load average and CPU count, which are normalized and compared with threshold 1.0.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#eff6ff"/>
      <stop offset="1" stop-color="#faf5ff"/>
    </linearGradient>
    <filter id="shadow"><feDropShadow dx="0" dy="7" stdDeviation="7" flood-opacity="0.14"/></filter>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#475569"/></marker>
    <style>
      text{font-family:"Segoe UI","Microsoft JhengHei",sans-serif;fill:#0f172a}.title{font-size:36px;font-weight:700}.sub{font-size:18px;fill:#475569}.head{font-size:21px;font-weight:700}.body{font-size:16px}.code{font:700 17px Consolas,monospace}.card{stroke-width:2;filter:url(#shadow)}.arrow{stroke:#475569;stroke-width:4;fill:none;marker-end:url(#arrow)}
    </style>
  </defs>
  <rect width="1400" height="800" fill="url(#bg)"/>
  <text x="60" y="60" class="title">SysProbe Day 4｜CPU 負載檢查器</text>
  <text x="60" y="94" class="sub">Load average 是系統工作壓力，不是 CPU 使用率百分比</text>
  <rect class="card" x="60" y="150" width="270" height="150" rx="22" fill="#dbeafe" stroke="#60a5fa"/>
  <text x="85" y="190" class="head">① 讀取 Load Average</text>
  <text x="85" y="228" class="code">cat /proc/loadavg</text>
  <text x="85" y="264" class="body">保留 1、5、15 分鐘數值</text>
  <rect class="card" x="60" y="365" width="270" height="150" rx="22" fill="#ede9fe" stroke="#a78bfa"/>
  <text x="85" y="405" class="head">② 讀取 CPU 數量</text>
  <text x="85" y="443" class="code">nproc</text>
  <text x="85" y="479" class="body">取得環境可用的 CPU 數量</text>
  <path class="arrow" d="M330 225 C410 225 420 310 500 330"/>
  <path class="arrow" d="M330 440 C410 440 420 355 500 340"/>
  <rect class="card" x="515" y="240" width="390" height="200" rx="22" fill="#fef3c7" stroke="#f59e0b"/>
  <text x="545" y="285" class="head">③ 正規化一分鐘負載</text>
  <text x="545" y="333" class="code">normalized_load_1m =</text>
  <text x="545" y="367" class="code">load_1m ÷ CPU count</text>
  <text x="545" y="409" class="body">例：3.00 ÷ 4 = 0.75</text>
  <path class="arrow" d="M905 340 L1000 340"/>
  <rect class="card" x="1015" y="225" width="320" height="230" rx="22" fill="#fff7ed" stroke="#fb923c"/>
  <text x="1045" y="270" class="head">④ 比較 threshold = 1.0</text>
  <rect x="1045" y="303" width="260" height="55" rx="18" fill="#dcfce7"/>
  <text x="1070" y="338" class="body" fill="#15803d">load &lt; 1.0 → PASS</text>
  <rect x="1045" y="376" width="260" height="55" rx="18" fill="#fee2e2"/>
  <text x="1070" y="411" class="body" fill="#b91c1c">load ≥ 1.0 → FAIL</text>
  <rect class="card" x="60" y="590" width="600" height="145" rx="22" fill="#ffffff" stroke="#93c5fd"/>
  <text x="90" y="632" class="head" fill="#1d4ed8">今天和昨天的差別</text>
  <text x="90" y="672" class="body">Day 3：一條指令，計算記憶體可用量</text>
  <text x="90" y="706" class="body">Day 4：兩條指令，必須用 CPU 數量解釋 Load</text>
  <rect class="card" x="705" y="590" width="630" height="145" rx="22" fill="#fff1f2" stroke="#fb7185"/>
  <text x="735" y="632" class="head" fill="#be123c">失敗仍保留證據</text>
  <text x="735" y="672" class="body">timeout／非零 exit code／格式錯誤 → FAIL + reason</text>
  <text x="735" y="706" class="body">兩份 CommandResult 都保留，方便往上排錯</text>
</svg>
```

- [ ] **Step 2: Link the image under the Day 4 README section**

Add:

```markdown
### Day 4 visual summary

![Day 4 CPU Validator flow](docs/day4-cpu-validator-summary.svg)
```

- [ ] **Step 3: Validate the SVG and pending paths**

```powershell
$svg = [xml](Get-Content -Encoding UTF8 -Raw 'docs\day4-cpu-validator-summary.svg')
if ($svg.DocumentElement.Name -ne 'svg') { throw 'SVG root is missing' }
git diff --check
git status --short
```

Purpose: parse the image as XML, check whitespace, and verify that only the SVG
and README change are pending.

Expected: XML parsing and diff check succeed; status lists only
`README.md` and `docs/day4-cpu-validator-summary.svg`.

- [ ] **Step 4: Commit the learning artifact**

```powershell
git add -- docs/day4-cpu-validator-summary.svg README.md
git commit -m "docs: add Day 4 visual summary"
```

### Task 8: Final Day 4 Verification

**Files:**
- Verify only; no planned modifications.

- [ ] **Step 1: Run the complete test and compile checks**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m compileall -q sysprobe
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git diff --check
```

Purpose: prove all four days work together, every Python file compiles, and no
whitespace error remains.

Expected: 58 tests pass and every command exits with code 0.

- [ ] **Step 2: Verify the branch is clean and review its scope**

```powershell
git status --short --branch
git log --oneline main..HEAD
git diff --stat main...HEAD
git diff --name-only main...HEAD
```

Purpose: confirm all Day 4 work is committed and inspect exactly what would be
merged.

Expected changed paths:

```text
README.md
docs/day4-cpu-validator-summary.svg
docs/superpowers/plans/2026-09-27-cpu-validator.md
sysprobe/validators/cpu.py
tests/test_cpu.py
```

- [ ] **Step 3: Review against the design before integration**

Check each acceptance criterion in
`docs/superpowers/specs/2026-09-27-cpu-validator-design.md` against the tests,
implementation, README, and SVG. Record any discrepancy before claiming Day 4
complete.

After gathering fresh verification evidence, use the
finishing-a-development-branch workflow to merge, push, retain, or discard the
feature branch.
