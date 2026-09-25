# Day 2 Disk Validator Design

## Goal

Add the first SysProbe validator. It checks the Linux root filesystem (`/`)
with `df -P /` and reports PASS when disk usage is below a configurable
threshold, or FAIL otherwise.

The default threshold is 90 percent. Callers may choose another threshold
from 1 through 100.

## Scope

Day 2 checks only the root filesystem. It does not enumerate every mounted
filesystem, select arbitrary paths, or introduce a shared validator class.
Those abstractions should wait until later validators reveal a real common
pattern.

## Architecture

The implementation separates three responsibilities:

1. `CommandRunner` executes `df -P /` and records observable facts.
2. A disk-output parser extracts the integer usage percentage.
3. The disk validator applies the configured threshold and constructs a
   human-readable result.

```text
validate_disk(threshold=90)
          |
          v
run_command(["df", "-P", "/"])
          |
          v
CommandResult
          |
          +-- timeout or nonzero exit ----------------+
          |                                            |
          v                                            v
parse_disk_usage(stdout)                         FAIL with reason
          |
          +-- malformed output ------------------------+
          |
          v
usage_percent
          |
          +-- usage < threshold  -> PASS
          +-- usage >= threshold -> FAIL
```

The parser stays separate from command execution so its Linux text format can
be tested deterministically on Windows and CI.

## Result Model

`DiskValidationResult` records:

- `passed`: whether the check passed;
- `reason`: a human-readable explanation;
- `mount_point`: `/` for Day 2;
- `usage_percent`: parsed usage, or `None` when it could not be determined;
- `threshold_percent`: the threshold used for the decision;
- `command_result`: the original command evidence, including stdout, stderr,
  exit code, duration, and timeout state.

The validator returns FAIL when it cannot prove the disk is healthy. The
reason distinguishes a full disk from an execution, timeout, or parsing
failure. A future structured error model may split these cases into additional
statuses; Day 2 intentionally retains PASS and FAIL only.

## Decision Rules

- Usage below the threshold is PASS.
- Usage equal to or above the threshold is FAIL.
- A command timeout is FAIL.
- A nonzero command exit code is FAIL.
- Malformed `df` output is FAIL.
- A threshold outside 1 through 100 is caller misuse and raises `ValueError`.

## Error Evidence

Every returned result retains the underlying `CommandResult`. This lets a
caller inspect stdout, stderr, exit code, and timeout state instead of receiving
only a boolean with no explanation.

## Testing

Tests will cover:

1. parsing valid POSIX `df -P /` output;
2. PASS below the threshold;
3. FAIL at or above the threshold;
4. FAIL with preserved evidence for malformed output;
5. FAIL for command timeout and nonzero exit;
6. rejection of invalid thresholds.

Production behavior will be written test-first using RED, GREEN, and REFACTOR.
Command execution will be injected in validator tests because the development
host is Windows while the production command is Linux-specific. Parser tests
will use realistic `df -P /` text directly.

## Documentation and Learning Artifact

The README will explain Day 2 usage and how to run its tests. After the
implementation is verified, a colored summary image will document the command,
data flow, decision rule, failure paths, and file relationships for beginner
review.
