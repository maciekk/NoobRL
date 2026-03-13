"""Tests for dice rolling utilities."""
import pytest
from dice import parse, roll


def test_parse_1d6():
    assert parse("1d6") == (1, 6)


def test_parse_2d4():
    assert parse("2d4") == (2, 4)


def test_parse_5d2():
    assert parse("5d2") == (5, 2)


def test_roll_1d1_always_one():
    for _ in range(10):
        assert roll("1d1") == 1


def test_roll_1d6_in_range():
    for _ in range(50):
        result = roll("1d6")
        assert 1 <= result <= 6


def test_roll_2d6_in_range():
    for _ in range(50):
        result = roll("2d6")
        assert 2 <= result <= 12


def test_roll_5d2_in_range():
    for _ in range(50):
        result = roll("5d2")
        assert 5 <= result <= 10


def test_parse_invalid_raises():
    with pytest.raises((ValueError, AttributeError)):
        parse("nodice")
