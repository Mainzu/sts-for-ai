"""`@wc1` (backlog 82): the player setting parses to the evaluator's `win_cap`."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bench  # noqa: E402


def test_win_cap_setting_parses():
    assert bench.player_settings("m.pt@hpe0.01@tsl1@wc1") == ("m.pt", {"hp_end_bonus": 0.01, "turn_start_leaf": 1.0, "win_cap": 1.0})


def test_win_cap_setting_is_one_or_off():
    with pytest.raises(ValueError):
        bench.player_settings("m.pt@wc2")
