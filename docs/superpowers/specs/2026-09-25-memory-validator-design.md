# Day 3 Memory Validator Design

## Goal

Add a Linux memory validator that reads `/proc/meminfo`, calculates RAM usage
from `MemTotal` and `MemAvailable`, and reports PASS when usage is below a
configurable threshold or FAIL otherwise.

The default threshold is 90 percent. Callers may select an integer threshold
from 1 through 100.

## Scope

Day 3 validates system RAM only. It records swap information for diagnostic
context, but swap usage does not affect PASS or FAIL. It does not introduce a
shared validator base class; that decision waits until the CPU validator gives
the project a third concrete validator to compare.

The production validator uses `cat /proc/meminfo`. The human-oriented `free -h`
command remains a manual learning tool rather than a parsing dependency.

## Linux Memory Semantics

Low `MemFree` alone does not mean Linux is short on usable memory. Linux uses
otherwise idle RAM for caches that can be reclaimed. `MemAvailable` estimates
the memory that can be supplied to applications without swapping.

The validator therefore calculates:

```text
used_kb = MemTotal - MemAvailable
usage_percent = used_kb / MemTotal * 100
```

`MemFree`, `Buffers`, and `Cached` remain visible as learning and diagnostic
metrics, but they do not directly determine status.

## Architecture

The implementation keeps command execution, text parsing, and health policy
separate:

1. `CommandRunner` executes `cat /proc/meminfo` and returns `CommandResult`.
2. `parse_meminfo` converts required named fields into `MemoryMetrics`.
3. `validate_memory` calculates usage, applies the threshold, and constructs a
   `MemoryValidationResult`.

```text
validate_memory(threshold=90)
              |
              v
run_command(["cat", "/proc/meminfo"])
              |
              +-- timeout or nonzero exit --------+
              |                                    |
              v                                    v
parse_meminfo(stdout)                         FAIL with reason
              |
              +-- malformed or missing field ------+
              |
              v
MemoryMetrics
              |
              v
(MemTotal - MemAvailable) / MemTotal * 100
              |
              +-- usage < threshold  -> PASS
              +-- usage >= threshold -> FAIL
```

This separation lets parser tests use deterministic Linux samples on Windows
and keeps memory policy independent of text formatting.

## Metrics Model

`MemoryMetrics` records values reported by `/proc/meminfo`:

- `total_kb` from `MemTotal`;
- `free_kb` from `MemFree`;
- `available_kb` from `MemAvailable`;
- `buffers_kb` from `Buffers`;
- `cached_kb` from `Cached`;
- `swap_total_kb` from `SwapTotal`;
- `swap_free_kb` from `SwapFree`;
- `used_kb`, calculated as total minus available;
- `usage_percent`, calculated from used and total without using `MemFree`.

Field names use `_kb` to match the label exposed by `/proc/meminfo`. Values are
kept as integers except for `usage_percent`, which is a floating-point value.

## Validation Result

`MemoryValidationResult` records:

- `passed`: whether RAM usage is below the threshold;
- `reason`: a human-readable explanation;
- `metrics`: parsed and calculated memory measurements, or `None` when parsing
  or command execution fails;
- `threshold_percent`: the configured threshold;
- `command_result`: original stdout, stderr, exit code, duration, and timeout
  evidence.

## Decision and Error Rules

- RAM usage below the threshold is PASS.
- RAM usage equal to or above the threshold is FAIL.
- Swap usage is recorded but never changes the Day 3 decision.
- A command timeout is FAIL.
- A nonzero command exit code is FAIL.
- Missing required fields, non-integer values, unexpected units, or
  `MemTotal <= 0` are malformed input and produce FAIL.
- An available-memory value outside `0..MemTotal` is malformed input and
  produces FAIL.
- A threshold that is not an integer from 1 through 100 is caller misuse and
  raises `ValueError` before command execution.

The calculation retains its unrounded floating-point value for comparison.
Human-readable reasons format the percentage to one decimal place so display
rounding does not change the PASS/FAIL boundary.

## Testing

Tests will cover:

1. parsing the required `/proc/meminfo` fields;
2. PASS below the threshold;
3. FAIL equal to or above the threshold;
4. low `MemFree` with sufficient `MemAvailable` still passing;
5. swap metrics being recorded without affecting the decision;
6. malformed or missing fields returning FAIL with command evidence;
7. timeout and nonzero exit returning distinct failure reasons;
8. invalid thresholds being rejected before command execution.

Tests inject a command executor because `/proc/meminfo` is Linux-specific and
the current development host is Windows. Parser tests use realistic captured
text rather than mocking the parser.

## Documentation and Learning Artifact

The README will explain the difference between free and available memory, show
basic usage, and include a focused Day 3 test command. After implementation is
verified, a colored summary image will show the data flow, memory calculation,
decision boundary, swap role, and failure paths.
