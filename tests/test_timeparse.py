"""Tests for duration parsing, including strict rejection of trailing garbage."""

from __future__ import annotations

from datetime import timedelta

import pytest

from src.core.timeparse import parse_duration


def test_parses_single_and_compound_tokens():
    assert parse_duration("10m") == timedelta(minutes=10)
    assert parse_duration("2h30m") == timedelta(hours=2, minutes=30)
    assert parse_duration("1d") == timedelta(days=1)
    assert parse_duration("1w") == timedelta(weeks=1)


def test_allows_whitespace_between_tokens():
    assert parse_duration("2h 30m") == timedelta(hours=2, minutes=30)
    assert parse_duration("  10m  ") == timedelta(minutes=10)


def test_case_insensitive():
    assert parse_duration("2H30M") == timedelta(hours=2, minutes=30)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "soon",
        "10",  # bare number, no unit
        "10mins",  # trailing garbage after a valid token
        "10m please",
        "5x10m",
        "abc10m",
    ],
)
def test_rejects_non_duration_strings(text):
    with pytest.raises(ValueError):
        parse_duration(text)
