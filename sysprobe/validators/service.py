from dataclasses import dataclass
from collections.abc import Callable, Sequence
import re

from sysprobe.command_runner import run_command
from sysprobe.result import CommandErrorKind, CommandResult, ValidationStatus


_REQUIRED_PROPERTIES = frozenset({"LoadState", "ActiveState", "SubState"})
_MALFORMED_PROPERTIES_ERROR = "malformed systemctl property output"
_SYSTEMD_UNAVAILABLE_DIAGNOSTICS = (
    "System has not been booted with systemd",
    "Failed to connect to bus: Host is down",
    "Failed to connect to bus: No such file or directory",
)


@dataclass(frozen=True, slots=True)
class ServiceMetrics:
    """The load, active, and substate values reported for a systemd service."""

    load_state: str
    active_state: str
    sub_state: str


CommandExecutor = Callable[[Sequence[str]], CommandResult]


@dataclass(frozen=True, slots=True)
class ServiceValidationResult:
    """A service health classification with the evidence used to make it."""

    status: ValidationStatus
    reason: str
    service_name: str
    metrics: ServiceMetrics | None
    command_result: CommandResult


def validate_service(
    service_name: str,
    *,
    command_executor: CommandExecutor = run_command,
) -> ServiceValidationResult:
    """Check whether a systemd service is loaded and active."""
    normalized_name = normalize_service_name(service_name)
    command = [
        "systemctl",
        "show",
        normalized_name,
        "--property=LoadState",
        "--property=ActiveState",
        "--property=SubState",
        "--no-pager",
    ]
    command_result = command_executor(command)

    if command_result.error_kind is CommandErrorKind.NOT_FOUND:
        status = ValidationStatus.UNSUPPORTED
        reason = "Service check unsupported: systemctl executable was not found"
        metrics = None
    elif command_result.error_kind is not None:
        detail = command_result.error_message or command_result.error_kind.value
        status = ValidationStatus.ERROR
        reason = (
            f"Service check error for {normalized_name}: "
            f"systemctl could not start: {detail}"
        )
        metrics = None
    elif command_result.timed_out:
        status = ValidationStatus.ERROR
        reason = f"Service check error for {normalized_name}: systemctl timed out"
        metrics = None
    elif command_result.exit_code != 0:
        if any(
            diagnostic in command_result.stderr
            for diagnostic in _SYSTEMD_UNAVAILABLE_DIAGNOSTICS
        ):
            status = ValidationStatus.UNSUPPORTED
            reason = "Service check unsupported: systemd is unavailable"
        else:
            status = ValidationStatus.ERROR
            reason = (
                f"Service check error for {normalized_name}: "
                f"systemctl failed with exit code {command_result.exit_code}"
            )
        metrics = None
    else:
        try:
            metrics = parse_service_properties(command_result.stdout)
        except ValueError:
            status = ValidationStatus.ERROR
            reason = (
                f"Service check error for {normalized_name}: "
                "malformed systemctl output"
            )
            metrics = None
        else:
            if metrics.load_state == "not-found":
                status = ValidationStatus.FAIL
                reason = f"Required service {normalized_name} was not found"
            elif metrics.active_state == "active":
                status = ValidationStatus.PASS
                reason = (
                    f"Service {normalized_name} is active ({metrics.sub_state})"
                )
            else:
                status = ValidationStatus.FAIL
                reason = (
                    f"Service {normalized_name} is not active: "
                    f"{metrics.active_state} ({metrics.sub_state})"
                )

    return ServiceValidationResult(
        status=status,
        reason=reason,
        service_name=normalized_name,
        metrics=metrics,
        command_result=command_result,
    )


def parse_service_properties(output: str) -> ServiceMetrics:
    """Parse the required systemctl properties regardless of line order."""
    properties: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        if "=" not in line:
            raise ValueError(_MALFORMED_PROPERTIES_ERROR)

        key, value = line.split("=", 1)
        if (
            key not in _REQUIRED_PROPERTIES
            or key in properties
            or not value.strip()
        ):
            raise ValueError(_MALFORMED_PROPERTIES_ERROR)
        properties[key] = value

    if properties.keys() != _REQUIRED_PROPERTIES:
        raise ValueError(_MALFORMED_PROPERTIES_ERROR)

    return ServiceMetrics(
        load_state=properties["LoadState"],
        active_state=properties["ActiveState"],
        sub_state=properties["SubState"],
    )


_SERVICE_SUFFIX = ".service"
_OTHER_UNIT_SUFFIXES = (
    ".automount",
    ".device",
    ".mount",
    ".path",
    ".scope",
    ".slice",
    ".socket",
    ".swap",
    ".target",
    ".timer",
)
_SERVICE_STEM = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.@-]*")
_ERROR_MESSAGE = "service_name must be a safe systemd service name"


def normalize_service_name(service_name: object) -> str:
    """Normalize a safe systemd service name to its `.service` form."""
    if not isinstance(service_name, str) or not service_name:
        raise ValueError(_ERROR_MESSAGE)

    if service_name.endswith(_OTHER_UNIT_SUFFIXES):
        raise ValueError(_ERROR_MESSAGE)

    normalized = (
        service_name
        if service_name.endswith(_SERVICE_SUFFIX)
        else service_name + _SERVICE_SUFFIX
    )
    stem = normalized[: -len(_SERVICE_SUFFIX)]
    if not _SERVICE_STEM.fullmatch(stem):
        raise ValueError(_ERROR_MESSAGE)

    if len(normalized.encode("ascii")) > 255:
        raise ValueError(_ERROR_MESSAGE)

    return normalized
