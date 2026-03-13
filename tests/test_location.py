"""Tests for Location NamedTuple."""
from location import Location


def test_creation():
    loc = Location(3, 7)
    assert loc.x == 3
    assert loc.y == 7


def test_unpacking():
    x, y = Location(4, 9)
    assert x == 4
    assert y == 9


def test_chebyshev_same_point():
    a = Location(5, 5)
    assert a.chebyshev_distance(a) == 0


def test_chebyshev_cardinal_adjacent():
    a = Location(0, 0)
    assert a.chebyshev_distance(Location(1, 0)) == 1
    assert a.chebyshev_distance(Location(0, 1)) == 1
    assert a.chebyshev_distance(Location(-1, 0)) == 1
    assert a.chebyshev_distance(Location(0, -1)) == 1


def test_chebyshev_diagonal_is_one():
    a = Location(0, 0)
    assert a.chebyshev_distance(Location(1, 1)) == 1
    assert a.chebyshev_distance(Location(-1, -1)) == 1


def test_chebyshev_dominated_by_larger_axis():
    a = Location(0, 0)
    assert a.chebyshev_distance(Location(3, 7)) == 7
    assert a.chebyshev_distance(Location(7, 3)) == 7


def test_chebyshev_symmetric():
    a = Location(2, 5)
    b = Location(8, 1)
    assert a.chebyshev_distance(b) == b.chebyshev_distance(a)
