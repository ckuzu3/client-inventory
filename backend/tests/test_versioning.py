"""Build number comparison, including the case that made this module necessary."""

from __future__ import annotations

import pytest

from client_inventory.versioning import InvalidVersionError, is_at_least, parse_version


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10.0.26100.1742", (10, 0, 26100, 1742)),
        ("10.0", (10, 0)),
        ("15", (15,)),
        ("  10.0.19045  ", (10, 0, 19045)),
    ],
)
def test_parse_version_reads_each_segment(value: str, expected: tuple[int, ...]) -> None:
    assert parse_version(value) == expected


@pytest.mark.parametrize("value", ["", "   ", "10.0.x", "win11", "10..0", "10.0-rc1", "-1.0"])
def test_parse_version_rejects_anything_that_is_not_dotted_numbers(value: str) -> None:
    with pytest.raises(InvalidVersionError):
        parse_version(value)


def test_a_higher_build_is_not_a_lower_one_just_because_it_sorts_earlier() -> None:
    """The bug this module exists for: as text, '9600' sorts after '26100'."""
    assert "10.0.9600" > "10.0.26100"
    assert is_at_least("10.0.9600", "10.0.26100") is False
    assert is_at_least("10.0.26100", "10.0.9600") is True


@pytest.mark.parametrize(
    ("candidate", "minimum", "expected"),
    [
        ("10.0.26100", "10.0.26100", True),
        ("10.0.26100.1742", "10.0.26100", True),
        ("10.0.26100", "10.0.26100.1742", False),
        ("10.0", "10.0.0", True),
        ("10.0.0", "10.0", True),
        ("10.0.22631.4169", "10.0.26100", False),
        ("11.0", "10.0.26100", True),
    ],
)
def test_is_at_least_pads_missing_segments_with_zero(
    candidate: str, minimum: str, expected: bool
) -> None:
    assert is_at_least(candidate, minimum) is expected


def test_is_at_least_reports_which_value_was_unreadable() -> None:
    with pytest.raises(InvalidVersionError, match="not numeric"):
        is_at_least("15.1-beta", "10.0.26100")
