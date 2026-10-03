from dataclasses import dataclass
import re


_REQUIRED_PROPERTIES = frozenset({"LoadState", "ActiveState", "SubState"})
_MALFORMED_PROPERTIES_ERROR = "malformed systemctl property output"


@dataclass(frozen=True, slots=True)
class ServiceMetrics:
    """The load, active, and substate values reported for a systemd service."""

    load_state: str
    active_state: str
    sub_state: str


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
