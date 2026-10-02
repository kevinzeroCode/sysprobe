import re


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
