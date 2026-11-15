"""genpack_cut.py --wide (docs/specs/wider-generators.md): a synthetic pair of
files with a known cost per group reads back."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))

import genpack_cut as gc  # noqa: E402
import mutate_monsters as mm  # noqa: E402

MECHS = mm.WIDE_SPLIT["held_pairs"][:2] + mm.WIDE_SPLIT["whole_trigger"][:1] + mm.WIDE_SPLIT["train"][:1]


def _file(path, cost):
    """Elite rows where the net loses `cost(m) + noise` HP more than the heuristic on m, nothing on parent."""
    rows = []
    for i in range(40):
        noise = (i % 5) - 2
        mods = {m: {"heuristic": [[True, 40]], "one": [[True, 40 - cost(m) - noise]]} for m in MECHS}
        rows.append({"i": i, "floor": 1, "encounter": "x", "group": "elite", "hp": 50,
                     "parent": {"heuristic": [[True, 40]], "one": [[True, 40]]}, "mods": mods})
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"settings": {"mods": MECHS}, "rows": rows}, f)


def test_wide_cut(tmp_path):
    base, gen = str(tmp_path / "b.json"), str(tmp_path / "g.json")
    _file(base, lambda m: 8)
    _file(gen, lambda m: 2 if m in mm.WIDE_SPLIT["held_pairs"] else 8)
    out = gc.main(["--wide", "--pair", base, gen])
    assert set(out) == {"new held-out pairs", "whole trigger", "new training"}
    h = out["new held-out pairs"]
    assert abs(h["base"][0] - 8) < 1e-9 and abs(h["genpack"][0] - 2) < 1e-9 and h["n"] == 2
    assert abs(h["cut"][0] - 0.75) < 1e-9
    assert abs(out["whole trigger"]["cut"][0]) < 1e-9


def _product_file(path, cost, parent_loss=0, starts=40):
    """Old-split elite rows for the `product` player: it loses `cost(m) + noise` HP more than the
    heuristic on m, and `parent_loss` more on the parent."""
    rows = []
    for i in range(40):
        noise = (i % 5) - 2
        mods = {m: {"heuristic": [[True, 40]], "product": [[True, 40 - parent_loss - cost(m) - noise]]} for m in gc.HELD}
        row = {"i": i, "floor": 1, "encounter": "x", "group": "elite", "hp": 50,
               "parent": {"heuristic": [[True, 40]], "product": [[True, 40 - parent_loss]]}, "mods": mods}
        if i >= starts:  # past --two-starts: the deep player didn't play this start
            del row["parent"]["product"]
            for m in mods.values():
                del m["product"]
        rows.append(row)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"settings": {"mods": list(gc.HELD)}, "rows": rows}, f)


def test_product_player(tmp_path):
    """docs/specs/genpack-product-depth.md: --player product reads the product player's
    costs; the fail-fast fires under 1.0 HP of base cost (exit 1 with --gate)."""
    base, gen = str(tmp_path / "b.json"), str(tmp_path / "g.json")
    _product_file(base, lambda m: 4)
    _product_file(gen, lambda m: 1, parent_loss=1)
    out = gc.main(["--player", "product", "--pair", base, gen])
    assert abs(out["base"][0] - 4) < 1e-9 and abs(out["cut"][0] - 0.75) < 1e-9
    assert abs(out["parent"][0] + 1) < 1e-9 and out["verdict"].startswith("go so far")
    _product_file(base, lambda m: 0.5)
    assert gc.main(["--player", "product", "--pair", base, gen])["verdict"].startswith("fail-fast")
    try:
        gc.main(["--player", "product", "--gate", "--pair", base, gen])
        raise AssertionError("no exit")
    except SystemExit as e:
        assert e.code == 1


def test_product_player_fewer_starts(tmp_path, capsys):
    """A genpack file played on fewer starts (--two-starts 100) reads on the starts both files share."""
    base, gen = str(tmp_path / "b.json"), str(tmp_path / "g.json")
    _product_file(base, lambda m: 4)
    _product_file(gen, lambda m: 1, starts=20)
    out = gc.main(["--player", "product", "--pair", base, gen])
    assert "20 elite starts shared" in capsys.readouterr().out
    assert abs(out["cut"][0] - 0.75) < 1e-9
