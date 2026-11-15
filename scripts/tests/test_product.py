"""Tests for the product registry (scripts/product.py). Run with
`python scripts/tests/test_product.py` or with pytest."""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import product  # noqa: E402


def make(d):
    reg, dec = os.path.join(d, "product.json"), os.path.join(d, "decisions.md")
    shutil.copy(product.REGISTRY, reg)
    with open(dec, "w", encoding="utf-8") as f:
        f.write("# Decisions\n\n## New product (owner away, 2026-12-01)\n\nText.\n")
    return reg, dec


def test_set_moves_the_old_player_to_previous():
    with tempfile.TemporaryDirectory() as d:
        reg, dec = make(d)
        old = product.load(reg)
        new = product.promote("runs/x/model.pt@hpe0.01", "--two-turn", "New product (owner away, 2026-12-01)",
                              headline="results/gauntlet/x.json", path=reg, decisions=dec, today="2026-12-01")
        assert product.load(reg) == new
        assert new["player"] == "runs/x/model.pt@hpe0.01" and new["since"] == "2026-12-01"
        assert new["headline_control"] == "results/gauntlet/x.json"
        assert new["one_turn_control"] == old["one_turn_control"]
        assert new["previous"][0] == {"player": old["player"], "flags": old["flags"], "since": old["since"],
                                      "decision": old["decision"], "until": "2026-12-01"}
        assert new["previous"][1:] == old["previous"]
        assert product.player_string(new) == "runs/x/model.pt@hpe0.01 --two-turn"


def test_set_refuses_an_unknown_decision():
    with tempfile.TemporaryDirectory() as d:
        reg, dec = make(d)
        before = open(reg, "rb").read()
        try:
            product.promote("runs/x/model.pt", "", "No such entry", path=reg, decisions=dec)
            assert False, "should refuse"
        except SystemExit as e:
            assert "No such entry" in str(e)
        assert open(reg, "rb").read() == before


def test_registry_names_the_product():
    reg = product.load()
    assert product.player_string(reg) == "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01 --two-turn --line-seed --step-line"
    assert product.has_heading(reg["decision"])
    assert all(product.has_heading(p["decision"]) for p in reg["previous"])
    json.dumps(reg)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
