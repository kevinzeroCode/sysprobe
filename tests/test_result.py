from sysprobe.result import (
    CommandErrorKind,
    CommandResult,
    ValidationStatus,
)


def test_validation_status_values_are_stable() -> None:
    assert [status.value for status in ValidationStatus] == [
        "pass",
        "fail",
        "error",
        "unsupported",
    ]


def test_command_result_defaults_to_no_launch_error() -> None:
    result = CommandResult(
        command=("true",),
        exit_code=0,
        stdout="",
        stderr="",
        duration_seconds=0.01,
        timed_out=False,
    )

    assert result.error_kind is None
    assert result.error_message is None
    assert [kind.value for kind in CommandErrorKind] == [
        "not_found",
        "permission_denied",
        "os_error",
    ]
