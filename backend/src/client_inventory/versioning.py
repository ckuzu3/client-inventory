"""Comparing Windows build numbers.

A build number is not a number and it is not a string either. Comparing
'10.0.9600' with '10.0.26100' as text puts the older build first, because '9' sorts
after '2'. Every version check in this project goes through this module so that bug
cannot come back somewhere else.
"""

from __future__ import annotations


class InvalidVersionError(ValueError):
    """Raised when a version string is not a dotted sequence of numbers."""


def parse_version(value: str) -> tuple[int, ...]:
    """Turn '10.0.26100.1742' into (10, 0, 26100, 1742).

    Raises:
        InvalidVersionError: if the value is empty or contains a non-numeric part.
    """
    stripped = value.strip()
    if not stripped:
        raise InvalidVersionError("A version string cannot be empty.")

    parts: list[int] = []
    for segment in stripped.split("."):
        if not segment.isdigit():
            raise InvalidVersionError(
                f"'{value}' is not a dotted sequence of numbers: '{segment}' is not numeric."
            )
        parts.append(int(segment))

    return tuple(parts)


def _padded(version: tuple[int, ...], length: int) -> tuple[int, ...]:
    """Pad a version with zeros so two versions of different length compare correctly."""
    return version + (0,) * (length - len(version))


def is_at_least(candidate: str, minimum: str) -> bool:
    """Tell whether candidate is the same as or newer than minimum.

    Missing segments count as zero, so '10.0' and '10.0.0' are the same version and
    '10.0.26100.1742' is newer than '10.0.26100'.

    Raises:
        InvalidVersionError: if either value cannot be parsed.
    """
    parsed_candidate = parse_version(candidate)
    parsed_minimum = parse_version(minimum)
    length = max(len(parsed_candidate), len(parsed_minimum))

    return _padded(parsed_candidate, length) >= _padded(parsed_minimum, length)
