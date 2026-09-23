# Linux Server Validation Framework — Project Plan

## 1. Goal

Build a local **Linux Server Validation Framework** that demonstrates skills aligned with NVIDIA Enterprise Software Test / RDSS roles:

- Python automation
- Linux debugging
- pytest
- Bash / system commands
- CI/CD
- Jenkins
- Docker
- test reporting
- structured log collection
- failure triage

The project does **not** need real data-center hardware.  
You can build the first version entirely on your own computer using:

- Windows + WSL2 (recommended if your main PC is Windows), or
- Ubuntu/Linux directly, or
- Docker containers / local VMs

---

## 2. Final Architecture

```text
                    Git Repository
                          |
                          v
                    Jenkins CI
                          |
                          v
                 Python Test Runner
                    (pytest)
                          |
             +------------+------------+
             |                         |
             v                         v
       Local Linux / WSL          Docker / VM
             |                         |
             +------------+------------+
                          |
                          v
                 System Validation
        CPU / Memory / Disk / Network
        Services / Processes / Logs
                          |
                          v
                 Diagnostic Collector
        journalctl / dmesg / ps / df
        free / ss / systemctl / lscpu
                          |
                          v
                JSON + JUnit Reports
                          |
                          v
                   Failure Summary
```

---

# 3. Scope

## MVP

The first version should support:

- [ ] Linux system information collection
- [ ] CPU validation
- [ ] memory validation
- [ ] disk validation
- [ ] network validation
- [ ] process/service validation
- [ ] Linux log collection
- [ ] pytest test execution
- [ ] structured JSON output
- [ ] JUnit XML report
- [ ] Jenkins pipeline
- [ ] README with architecture and usage

## Stretch Goals

Only do these after MVP works:

- [ ] SSH remote server testing
- [ ] multiple-host configuration
- [ ] parallel test execution
- [ ] Docker-based test targets
- [ ] retry / timeout handling
- [ ] AI-assisted log summarization
- [ ] simple dashboard
- [ ] security checks
- [ ] Redfish / server-management simulation

---

# 4. Recommended Local Environment

## Option A — Windows + WSL2

Recommended for your current PC.

Install Ubuntu in WSL2 and treat it as your Linux server.

Architecture:

```text
Windows
  |
  +-- VS Code
  |
  +-- Git
  |
  +-- Docker Desktop
  |
  +-- WSL2 Ubuntu
         |
         +-- Python
         +-- pytest
         +-- Linux commands
```

You do not need AWS or a physical server for the MVP.

Later, you can add:

```text
WSL2
 |
 +-- SSH
      |
      +-- Ubuntu VM / EC2 / Raspberry Pi / another container
```

---

# 5. Repository Structure

```text
linux-server-validation/
|
|-- README.md
|-- requirements.txt
|-- pytest.ini
|-- Jenkinsfile
|-- .gitignore
|
|-- config/
|   |-- hosts.yaml
|   `-- thresholds.yaml
|
|-- src/
|   |-- __init__.py
|   |-- command_runner.py
|   |-- collector.py
|   |-- reporter.py
|   `-- validators/
|       |-- __init__.py
|       |-- cpu.py
|       |-- memory.py
|       |-- disk.py
|       |-- network.py
|       |-- service.py
|       `-- logs.py
|
|-- tests/
|   |-- test_cpu.py
|   |-- test_memory.py
|   |-- test_disk.py
|   |-- test_network.py
|   |-- test_service.py
|   `-- test_logs.py
|
|-- scripts/
|   `-- collect_diagnostics.sh
|
|-- reports/
|   `-- .gitkeep
|
`-- docs/
    `-- architecture.md
```

---

# 6. Core Design

## command_runner.py

Purpose:

- execute Linux commands
- capture stdout
- capture stderr
- record return code
- enforce timeout

Example interface:

```python
result = run_command("free -m")
```

Return structured data such as:

```python
{
    "command": "free -m",
    "return_code": 0,
    "stdout": "...",
    "stderr": "",
    "duration_ms": 12
}
```

---

## collector.py

Collect system diagnostics.

Commands to support:

```bash
uname -a
lscpu
free -m
df -h
ps aux
ss -tulpn
ip addr
systemctl --failed
journalctl -p err
dmesg
```

Do not worry if some commands behave differently inside WSL or containers.

The framework should handle errors instead of crashing.

---

# 7. Validation Tests

## CPU

Check:

- CPU information can be read
- system load is below configurable threshold
- command execution succeeds

Possible commands:

```bash
lscpu
uptime
```

---

## Memory

Check:

- total memory
- available memory
- memory usage percentage

Command:

```bash
free -m
```

Example rule:

```text
FAIL if available memory < 10%
```

---

## Disk

Check:

- filesystem usage
- root filesystem threshold

Command:

```bash
df -P
```

Example rule:

```text
WARN > 80%
FAIL > 90%
```

---

## Network

Check:

- network interface exists
- loopback works
- DNS or configured destination reachable

Commands:

```bash
ip addr
ping -c 1 127.0.0.1
```

Optional:

```bash
curl
ss
```

---

## Services

Check a configurable service.

Example:

```bash
systemctl is-active ssh
```

If WSL does not use systemd correctly, make service tests optional.

---

## Logs

Search logs for high-severity errors.

Commands:

```bash
journalctl -p err --since "10 minutes ago"
dmesg
```

Important:

Do not make every log line containing "error" automatically fail.

Store the logs first and define clear rules.

---

# 8. pytest Integration

Install:

```bash
pip install pytest pytest-json-report
```

Run:

```bash
pytest -v
```

Generate JUnit report:

```bash
pytest -v --junitxml=reports/junit.xml
```

Target:

```text
tests/test_cpu.py
tests/test_memory.py
tests/test_disk.py
tests/test_network.py
tests/test_service.py
tests/test_logs.py
```

---

# 9. Configuration

Use YAML instead of hardcoding thresholds.

Example:

```yaml
cpu:
  max_load_percent: 90

memory:
  min_available_percent: 10

disk:
  warning_percent: 80
  critical_percent: 90

network:
  ping_target: "127.0.0.1"
```

This gives you a good interview talking point:

> Test policy and test implementation are separated.

---

# 10. Reporting

Produce two forms of output.

## Machine-readable

```text
reports/results.json
reports/junit.xml
```

## Human-readable

Console:

```text
CPU       PASS
Memory    PASS
Disk      WARN
Network   PASS
Services  PASS
Logs      FAIL
```

For failures, include:

```text
Test:
Reason:
Command:
Return code:
Relevant output:
Timestamp:
```

---

# 11. Jenkins

Do not start Jenkins on Day 1.

Add Jenkins **after pytest works locally**.

Pipeline:

```text
Checkout
   |
   v
Create Python Environment
   |
   v
Install Dependencies
   |
   v
Run pytest
   |
   v
Publish JUnit
   |
   v
Archive Logs / Reports
```

Example stages:

```groovy
pipeline {
    agent any

    stages {
        stage('Setup') {
            steps {
                sh 'python3 -m pip install -r requirements.txt'
            }
        }

        stage('Test') {
            steps {
                sh 'pytest -v --junitxml=reports/junit.xml'
            }
        }
    }

    post {
        always {
            junit 'reports/junit.xml'
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
        }
    }
}
```

You do not need to become a Groovy expert.

You only need to understand:

- pipeline
- stage
- step
- agent
- exit code
- artifact
- credentials
- trigger
- test report

---

# 12. 7-Day Build Plan

## Day 1 — Environment + Linux Commands

Goals:

- [ ] create GitHub repository
- [ ] set up WSL2 Ubuntu
- [ ] create Python virtual environment
- [ ] install pytest
- [ ] practice Linux diagnostics

Commands to understand:

```bash
ps
top
free
df
du
ss
ip
lsof
journalctl
dmesg
systemctl
grep
awk
```

Deliverable:

```text
scripts/collect_diagnostics.sh
```

---

## Day 2 — Python Command Runner

Build:

```text
src/command_runner.py
```

Requirements:

- [ ] subprocess execution
- [ ] stdout/stderr capture
- [ ] return code
- [ ] timeout
- [ ] exception handling
- [ ] structured result

Tests:

```text
tests/test_command_runner.py
```

Interview concepts:

- process
- exit code
- stdout/stderr
- timeout
- subprocess

---

## Day 3 — System Validators

Implement:

- [ ] CPU
- [ ] Memory
- [ ] Disk
- [ ] Network

Add pytest tests.

Target:

```bash
pytest -v
```

should work locally.

---

## Day 4 — Logs + Failure Handling

Implement:

- [ ] log collection
- [ ] failed-command handling
- [ ] diagnostic snapshots
- [ ] configurable thresholds

Add:

```text
config/thresholds.yaml
```

Explain:

```text
test failure
     |
     v
collect diagnostics
     |
     v
save structured report
```

---

## Day 5 — Reporting

Implement:

- [ ] JSON report
- [ ] JUnit XML
- [ ] readable console summary
- [ ] reports directory

Deliverable example:

```text
reports/
|-- result.json
|-- junit.xml
`-- diagnostics/
```

---

## Day 6 — Jenkins

Install Jenkins locally with Docker or WSL.

Create:

```text
Jenkinsfile
```

Pipeline:

```text
Git push
   ->
Jenkins
   ->
pytest
   ->
JUnit report
   ->
artifact
```

You should be able to intentionally break one test and explain:

1. why pytest fails
2. why Jenkins marks the build failed
3. where the logs are
4. what you would inspect next

---

## Day 7 — README + Interview Preparation

README should contain:

- [ ] project motivation
- [ ] architecture diagram
- [ ] setup
- [ ] test categories
- [ ] example output
- [ ] CI pipeline
- [ ] design decisions
- [ ] future improvements

Prepare answers for:

1. Why pytest?
2. Why separate validators from test cases?
3. How does Jenkins know a test failed?
4. How do you avoid one bad command crashing the framework?
5. How would you scale from one server to 100 servers?
6. How would you handle an unreachable server?
7. What is the difference between test failure and infrastructure failure?
8. How would you debug intermittent failures?
9. How would you parallelize tests?
10. Where could an LLM help safely?

---

# 13. Phase 2 — Remote Server Testing

After local MVP works, add SSH.

Possible library:

```text
paramiko
```

Architecture:

```text
pytest
   |
   v
SSH Executor
   |
   +---- server01
   +---- server02
   `---- server03
```

hosts.yaml:

```yaml
hosts:
  - hostname: server01
    address: 192.168.1.10

  - hostname: server02
    address: 192.168.1.11
```

Do not commit passwords or SSH private keys.

Use:

- SSH keys
- environment variables
- Jenkins credentials

---

# 14. Phase 3 — AI Failure Triage

Only build this after deterministic testing works.

Good AI usage:

```text
Raw logs
   |
   v
Rule-based filtering
   |
   v
Relevant failure context
   |
   v
LLM
   |
   v
Failure summary
```

The LLM should **not decide PASS/FAIL**.

PASS/FAIL remains deterministic.

Example LLM output:

```text
Probable failure area:
- Network configuration

Evidence:
- eth0 unavailable
- ping command failed
- route table missing default route

Suggested next checks:
- ip addr
- ip route
- network service status
```

This is directly relevant to AI-assisted failure triage.

---

# 15. Resume Usage

Do not add the project to the resume while the repository is empty.

Once Day 3–4 is complete, you can safely write:

```text
Linux Server Validation Framework                         Sep. 2026 – Present

• Developing a Python and pytest-based automated validation framework
  for Linux systems, covering CPU, memory, disk, network, service,
  and system-log health checks.

• Implemented structured Linux diagnostic collection and configurable
  validation rules to support reproducible failure analysis.
```

After Jenkins is working:

```text
• Integrated automated regression tests into a Jenkins CI pipeline
  with JUnit reporting and archived diagnostic artifacts.
```

After SSH works:

```text
• Extended the framework to execute validation remotely over SSH
  and collect diagnostics from configurable Linux test targets.
```

Do not claim:

- large-scale distributed testing
- firmware validation
- production server deployment
- Jenkins experience

until those parts are actually implemented.

---

# 16. Definition of Done

The MVP is complete when:

- [ ] `pytest` runs all validations
- [ ] at least 5 system test categories exist
- [ ] failed commands are handled safely
- [ ] failure diagnostics are stored
- [ ] thresholds are configurable
- [ ] JUnit XML is generated
- [ ] Jenkins runs the test suite
- [ ] Jenkins publishes test results
- [ ] Jenkins archives diagnostics
- [ ] README explains architecture
- [ ] one failure can be intentionally reproduced and debugged

At this point the project is already strong enough to discuss in a software test / infrastructure interview.

---

# 17. Skills Demonstrated

By completing the MVP you can credibly discuss:

```text
Python
pytest
Linux
Bash
subprocess
system debugging
test automation
CI/CD
Jenkins
Git
Docker
JUnit
structured logging
failure triage
configuration management
```

Phase 2 adds:

```text
SSH
remote execution
multi-host validation
credentials management
parallelism
```

Phase 3 adds:

```text
LLM-assisted debugging
AI failure triage
evidence-grounded analysis
```

---

# 18. Priority Rule

When deciding what to implement next:

```text
Correctness
   >
Reliability
   >
Debuggability
   >
Automation
   >
Scale
   >
AI
```

Do not start with the AI feature.

The strongest interview story is:

> I first built deterministic Linux system validation, then integrated it
> into CI, then improved diagnostic collection, and only afterward added
> AI-assisted failure summarization.

That sounds like an engineer building reliable test infrastructure rather than a demo built around an LLM.
