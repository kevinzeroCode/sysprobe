import pytest

from sysprobe.validators.service import (
    ServiceMetrics,
    normalize_service_name,
    parse_service_properties,
)


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (
            "LoadState=loaded\nActiveState=active\nSubState=running\n",
            ServiceMetrics("loaded", "active", "running"),
        ),
        (
            "SubState=exited\nLoadState=loaded\nActiveState=active\n",
            ServiceMetrics("loaded", "active", "exited"),
        ),
        (
            "LoadState=not-found\nActiveState=inactive\nSubState=dead\n",
            ServiceMetrics("not-found", "inactive", "dead"),
        ),
    ],
)
def test_parse_service_properties_reads_required_states(output: str, expected: ServiceMetrics) -> None:
    assert parse_service_properties(output) == expected


@pytest.mark.parametrize(
    "output",
    [
        "",
        "LoadState=loaded\nActiveState=active\n",
        "LoadState=loaded\nLoadState=loaded\nActiveState=active\nSubState=running\n",
        "LoadState=\nActiveState=active\nSubState=running\n",
        "LoadState=loaded\nActiveState=active\nSubState=running\nOther=value\n",
        "LoadState=loaded\nActiveState=active\nSubState\n",
    ],
)
def test_parse_service_properties_rejects_malformed_output(output: str) -> None:
    with pytest.raises(ValueError, match="malformed systemctl property output"):
        parse_service_properties(output)


@pytest.mark.parametrize(
    ("service_name", "expected"),
    [
        ("cron", "cron.service"),
        ("cron.service", "cron.service"),
        ("systemd-networkd", "systemd-networkd.service"),
        ("ssh@worker", "ssh@worker.service"),
        ("_helper", "_helper.service"),
    ],
)
def test_normalize_safe_service_names(service_name, expected):
    assert normalize_service_name(service_name) == expected


@pytest.mark.parametrize(
    "service_name",
    [
        "",
        " ",
        " cron",
        "cron ",
        "-cron",
        "../cron",
        "bad service",
        "cron;reboot",
        "cron\n",
        "cr繹n",
        123,
        True,
    ],
)
def test_rejects_unsafe_service_names(service_name):
    with pytest.raises(
        ValueError, match="service_name must be a safe systemd service name"
    ):
        normalize_service_name(service_name)


@pytest.mark.parametrize(
    "suffix",
    [
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
    ],
)
def test_rejects_other_unit_suffixes(suffix):
    with pytest.raises(
        ValueError, match="service_name must be a safe systemd service name"
    ):
        normalize_service_name("cron" + suffix)


def test_accepts_maximum_length_normalized_service_name():
    assert normalize_service_name("a" * 247) == "a" * 247 + ".service"


def test_rejects_service_name_over_maximum_length():
    with pytest.raises(
        ValueError, match="service_name must be a safe systemd service name"
    ):
        normalize_service_name("a" * 248)
