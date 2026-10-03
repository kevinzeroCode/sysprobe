from dataclasses import dataclass
from enum import Enum


class ValidationStatus(str, Enum):
    """Machine-stable outcomes shared by integrated validators."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    UNSUPPORTED = "unsupported"


class CommandErrorKind(str, Enum):
    """Why the operating system could not launch a command."""

    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    OS_ERROR = "os_error"


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Facts captured from one local command execution attempt."""

    command: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool
    error_kind: CommandErrorKind | None = None
    error_message: str | None = None
