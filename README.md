# SysProbe

SysProbe is a learning-focused Linux validation framework. Day 1 builds the
local command-execution boundary. Day 2 adds the first policy layer: a root
filesystem disk validator with an explicit PASS/FAIL threshold.

## Day 1 behavior

`run_command`:

- accepts an argument vector instead of a shell command string;
- captures stdout, stderr, exit code, and elapsed time;
- returns nonzero exit codes as structured evidence;
- turns a timeout into a structured result with `timed_out=True`.

The runner records what happened. Future validators decide whether those facts
mean PASS or FAIL.

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
