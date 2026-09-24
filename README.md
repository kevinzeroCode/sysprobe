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
