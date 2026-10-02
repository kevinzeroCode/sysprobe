import pytest

from sysprobe.validators.service import normalize_service_name


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
