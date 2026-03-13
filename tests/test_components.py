"""Smoke tests for game components that can run without a live engine."""
from unittest.mock import MagicMock

from components.fighter import Fighter
from components.level import Level


class TestFighter:
    def _make(self, hp=10, defense=2, power=3):
        f = Fighter(hp=hp, base_defense=defense, base_power=power)
        # Provide a minimal parent so the hp setter doesn't crash on ai check
        f.parent = MagicMock()
        f.parent.ai = None
        return f

    def test_initial_hp(self):
        f = self._make(hp=15)
        assert f.hp == 15
        assert f.max_hp == 15

    def test_initial_stats(self):
        f = self._make(defense=3, power=5)
        assert f.base_defense == 3
        assert f.base_power == 5

    def test_hp_clamped_below_zero(self):
        f = self._make(hp=10)
        f.hp = -99
        assert f.hp == 0

    def test_hp_clamped_above_max(self):
        f = self._make(hp=10)
        f.hp = 9999
        assert f.hp == 10

    def test_heal_restores_hp(self):
        f = self._make(hp=10)
        f.hp = 4
        recovered = f.heal(3)
        assert recovered == 3
        assert f.hp == 7

    def test_heal_does_not_exceed_max(self):
        f = self._make(hp=10)
        f.hp = 8
        recovered = f.heal(100)
        assert recovered == 2
        assert f.hp == 10

    def test_heal_at_full_hp_returns_zero(self):
        f = self._make(hp=10)
        assert f.heal(5) == 0


class TestLevel:
    def test_init_defaults(self):
        lvl = Level()
        assert lvl.current_level == 1
        assert lvl.current_xp == 0
        assert lvl.xp_given == 0

    def test_experience_to_next_level(self):
        lvl = Level(current_level=1, level_up_base=0, level_up_factor=150)
        assert lvl.experience_to_next_level == 150

    def test_experience_scales_with_level(self):
        lvl = Level(current_level=3, level_up_base=0, level_up_factor=150)
        assert lvl.experience_to_next_level == 450

    def test_level_up_base_adds_offset(self):
        lvl = Level(current_level=1, level_up_base=200, level_up_factor=100)
        assert lvl.experience_to_next_level == 300

    def test_requires_level_up_false(self):
        lvl = Level(current_level=1, current_xp=50, level_up_factor=150)
        assert not lvl.requires_level_up

    def test_requires_level_up_true(self):
        lvl = Level(current_level=1, current_xp=150, level_up_factor=150)
        assert lvl.requires_level_up

    def test_requires_level_up_exact_threshold(self):
        lvl = Level(current_level=2, current_xp=300, level_up_base=0, level_up_factor=150)
        assert lvl.requires_level_up
