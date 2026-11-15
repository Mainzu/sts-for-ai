"""Relics as net rows (docs/specs/relic-entity.md, step 5): the opt-in
`relic` row kind writes each held relic's hooks in the power row format,
marked `grant_relic`, with the relic's counter in `relic_counter` and its
counter effects in `counter_set` / `counter_set_to` / `counter_add`; ids
mode counts held relics in `relic_<name>` player columns. Without the kind
nothing of a relic reaches the net. The Python binding takes a relic's
starting counter (`(name, counter)`) and reads the list back
(`Combat.relics`). Run with pytest or `python scripts/tests/test_relic_rows.py`."""

import os
import sys
from pathlib import Path

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import sts  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "content" / "packs" / "act1-relics.json"
DECK = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]


def load():
    sts.load_content(PACK.read_text(encoding="utf-8"))


def relic_rows(c, **kw):
    f = sts.Features("effects", **kw)
    b = f.encode([c])
    names = f.row_names
    rows = [dict(zip(names, r)) for r in b["rows"]]
    return [r for r in rows if r.get("grant_relic") == 1], names


def test_relic_rows_with_kind():
    load()
    c = sts.Combat(DECK, "jaw_worm", seed=1, relics=["gen:Lantern", ("gen:Ancient Tea Set", -1)])
    rows, _ = relic_rows(c, extra_rows=True)
    assert len(rows) == 2, rows
    lantern = [r for r in rows if r["condition_param"] == 0][0]
    tea = [r for r in rows if r["condition_param"] == -2][0]
    # Turn 1 has started: Lantern has fired (counter 1); the tea set starts at -1.
    assert lantern["trigger_OwnerTurnStart"] == 1 and lantern["condition_CounterIs"] == 1
    assert lantern["relic_counter"] == 1 and lantern["counter_set"] == 1 and lantern["counter_set_to"] == 1
    assert lantern["energy"] == 1 and lantern["grant_own"] == 0
    assert tea["relic_counter"] == -1 and tea["counter_set_to"] == -1 and tea["energy"] == 2


def test_add_counter_and_combat_start_columns():
    load()
    c = sts.Combat(DECK, "jaw_worm", seed=1, relics=["gen:Red Skull"])
    rows, names = relic_rows(c, extra_rows=True)
    assert "trigger_CombatStart" in names and "trigger_CombatStartPreDraw" in names
    assert len(rows) == 5, rows
    assert sum(r["trigger_CombatStart"] for r in rows) == 3
    assert [r["counter_add"] for r in rows if r["counter_add"]] == [2]


def test_no_relic_rows_without_kind():
    load()
    c = sts.Combat(DECK, "jaw_worm", seed=1, relics=["gen:Lantern"])
    rows, _ = relic_rows(c)
    assert rows == []
    f = sts.Features("effects", extra_rows=True, row_kinds=[k for k in sts.ROW_KINDS if k != "relic"])
    b = f.encode([c])
    assert not any(dict(zip(f.row_names, r)).get("grant_relic") == 1 for r in b["rows"])


def test_relic_free_rows_equal():
    """A fight without relics writes the same rows with the kind on or off,
    the new columns all zero."""
    c = sts.Combat(DECK, "jaw_worm", seed=1)
    off = sts.Features("effects", extra_rows=False)
    on = sts.Features("effects", extra_rows=True)
    a, b = off.encode([c]), on.encode([c])
    new = [n for n in on.row_names if n in ("grant_relic", "relic_counter", "counter_set", "counter_set_to", "counter_add")]
    assert len(new) == 5
    for r in b["rows"]:
        d = dict(zip(on.row_names, r))
        assert all(d[n] == 0 for n in new)
    assert len(a["rows"]) <= len(b["rows"])


def test_ids_relic_columns():
    load()
    c = sts.Combat(DECK, "jaw_worm", seed=1, relics=["Burning Blood", "gen:Lantern"])
    f = sts.Features("ids", extra_rows=True)
    p = dict(zip(f.player_names, f.encode([c])["player"][0]))
    assert p["relic_Burning Blood"] == 1 and p["relic_unknown"] == 1
    assert not any(n.startswith("relic_") for n in sts.Features("ids").player_names)
    assert not any(n.startswith("relic_") for n in sts.Features("effects", extra_rows=True).player_names)


def test_binding_counters_in_and_out():
    load()
    c = sts.Combat(DECK, "jaw_worm", seed=1, relics=[("gen:Ancient Tea Set", -1), "gen:Lantern"])
    assert c.relics == [("gen:Ancient Tea Set", -1), ("gen:Lantern", 1)]
    assert sts.Combat(DECK, "jaw_worm", seed=1).relics == []
    res = sts.run("greedy", [{"encounter": "jaw_worm", "deck": DECK, "seed": 1, "relics": [("gen:Lantern", 1)]}], threads=1)
    assert len(res) == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
