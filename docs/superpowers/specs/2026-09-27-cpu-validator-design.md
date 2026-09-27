# Day 4 CPU Validator Design

## Goal

Add a Linux CPU validator that reads load average and the number of CPUs
available to the current environment, normalizes the one-minute load, and
returns an explicit PASS or FAIL with the command evidence used for the
decision.

The validator teaches an important distinction: Linux load average measures
work that is running, waiting for CPU, or waiting in uninterruptible sleep. It
is not CPU utilization percentage.

## Scope

Day 4 will:

- run `cat /proc/loadavg` and `nproc` through the existing `CommandRunner`;
- record the 1-, 5-, and 15-minute load averages;
- parse the number of CPUs available to the current process environment;
- calculate `normalized_load_1m = load_1m / logical_cpu_count`;
- compare the unrounded normalized value with a configurable threshold;
- preserve both original `CommandResult` objects;
- classify timeout, nonzero exit, and malformed-output failures;
- document the difference between load average and CPU utilization;
- add a colored beginner learning summary.

Day 4 will not:

- sample `/proc/stat` to calculate CPU utilization percentage;
- inspect per-core utilization or process-level CPU use;
- introduce a shared validator base class or generic execution pipeline;
- add the Day 7 command-line integration;
- catch command-launch errors such as a missing executable, which remain part
  of the Day 12 error-classification work.

## Why Normalize by CPU Count

A raw load average cannot be interpreted without machine size. A load of 4 is
very different on a 4-CPU environment and a 16-CPU environment.

Day 4 therefore uses:

```text
normalized_load_1m = load_1m / logical_cpu_count
```

With the default threshold of `1.0`:

```text
normalized_load_1m < 1.0  -> PASS
normalized_load_1m >= 1.0 -> FAIL
```

For example, a one-minute load of 3 on a 4-CPU environment produces a
normalized load of `0.75`. This does not mean 75% CPU utilization.

`nproc` is used instead of assuming a hardware-wide CPU count because it
reports the processing units available to the current execution environment,
which is more useful when CPU availability is restricted.

## Architecture

Keep the same explicit learning-oriented separation established on Days 2 and
3:

```text
cat /proc/loadavg                 nproc
        |                           |
        v                           v
load CommandResult          CPU-count CommandResult
        |                           |
        v                           v
parse_loadavg              parse_cpu_count
        \                           /
         \                         /
          v                       v
             calculate normalized load
                       |
                       v
              compare threshold
                       |
                       v
             CpuValidationResult
```

The implementation belongs in `sysprobe/validators/cpu.py`. It stays
CPU-specific rather than refactoring Disk and Memory into a common base class.
The three validators share a broad sequence, but CPU has two commands and two
pieces of execution evidence while the existing validators each have one.
Forcing them behind one hierarchy now would hide these differences. A common
interface can be reconsidered during Day 7 integration using real usage
patterns.

## Data Models

### `CpuMetrics`

An immutable, slotted dataclass containing:

```text
load_1m: float
load_5m: float
load_15m: float
logical_cpu_count: int
normalized_load_1m: float
```

All three time windows are retained for context, but only the one-minute value
drives the Day 4 decision.

### `CpuValidationResult`

An immutable, slotted dataclass containing:

```text
passed: bool
reason: str
metrics: CpuMetrics | None
threshold: float
load_command_result: CommandResult
cpu_count_command_result: CommandResult
```

Both command results are always present because the validator runs both
read-only commands before classifying their outcomes. If either command or
parser fails, `metrics` is `None`; the result does not expose a partial metric
set as if validation had completed successfully.

## Parsing Rules

### `/proc/loadavg`

A representative value is:

```text
0.42 0.58 0.61 2/123 4567
```

`parse_loadavg` reads the first three whitespace-delimited fields. Each value
must:

- parse as a floating-point number;
- be finite, rejecting `NaN` and positive or negative infinity;
- be greater than or equal to zero.

Extra standard `/proc/loadavg` fields are retained in the original
`CommandResult` but are not needed for Day 4 metrics.

### `nproc`

`parse_cpu_count` trims surrounding whitespace and requires one positive
integer. Zero, negative values, decimals, empty output, and extra tokens are
malformed.

## Threshold Configuration

`validate_cpu` defaults to a normalized-load threshold of `1.0`.

The threshold may be an integer or float, but must be finite and greater than
zero. Booleans are rejected even though Python treats `bool` as a subtype of
`int`. There is no upper bound because deployments may intentionally allow a
normalized load above `1.0`.

Configuration is validated before either command runs. Invalid caller input
raises `ValueError`; it is a programming/configuration problem, not a measured
system-health result.

## Command and Error Flow

For a valid threshold, `validate_cpu`:

1. executes `cat /proc/loadavg`;
2. executes `nproc` even if the first command timed out or returned nonzero;
3. classifies each command in load-then-CPU order;
4. parses only successful command output;
5. collects every observed failure message;
6. returns FAIL with both command results if any failure exists;
7. otherwise creates `CpuMetrics` and applies the threshold.

Failure messages identify the failing source. Examples include:

```text
CPU check failed: load average command timed out
CPU check failed: nproc failed with exit code 1
CPU check failed: malformed /proc/loadavg output; malformed nproc output
```

When multiple problems exist, they are joined in deterministic load-then-CPU
order with `; `. This prevents the second failure from being hidden while
keeping one human-readable reason field.

On success, the decision uses the unrounded value. Formatting to two decimal
places is display-only:

```text
Normalized CPU load 0.75 is below threshold 1.00
Normalized CPU load 1.00 reached or exceeded threshold 1.00
```

## Testing Strategy

Tests use injected fake command executors and representative Linux output so
they remain deterministic on Windows.

The Day 4 test module will cover:

- parsing valid 1-, 5-, and 15-minute load values;
- rejecting missing, negative, nonnumeric, `NaN`, and infinite load values;
- parsing a positive CPU count and rejecting malformed or zero values;
- executing the exact argument vectors `['cat', '/proc/loadavg']` and
  `['nproc']` in order;
- normalization across different CPU counts;
- PASS below the threshold;
- FAIL exactly at and above the threshold;
- proving that 5- and 15-minute loads are recorded but do not decide status;
- timeout and nonzero exit handling for each command;
- aggregating simultaneous command or parse failures;
- preserving both original `CommandResult` objects;
- rejecting invalid thresholds before command execution;
- running the complete Day 1 through Day 4 regression suite.

Tests will be written before each production-code slice and observed failing
for the intended reason before implementation.

## Documentation

The README will explain:

- the exact commands used;
- why CPU count changes the meaning of raw load;
- why load average is not CPU utilization;
- the default threshold and boundary rule;
- why Day 4 stores two command results while Day 3 stores one;
- how to run only the Day 4 tests.

A deterministic colored SVG will show the two command paths converging into
normalization and threshold comparison. Code-native SVG is preferred for this
technical diagram so exact commands and formulas remain accurate.

## Acceptance Criteria

Day 4 is complete when:

- valid Linux load and CPU-count output produces correct metrics;
- normalized load below `1.0` passes by default;
- normalized load equal to or above `1.0` fails by default;
- all configured error paths return an explanatory result with both command
  records;
- invalid thresholds fail before command execution;
- focused CPU tests and the complete regression suite pass;
- compilation and Git diff checks pass;
- documentation and the visual summary match implemented behavior.
