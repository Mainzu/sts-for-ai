"""Potions as net rows (docs/specs/potions.md, step 6): the opt-in `potion`
row kind writes each held potion's effects in the columns a card's effects
use, at its effective amounts (doubled under Sacred Bark), with trigger
`Potion(Use)` and the row-only `potion_potency` (its effective potency).
Sacred Bark's relic row carries `potion_potency` 2. Ids mode with the opt-in
kinds counts held potions in `potion_<name>` player columns (pack potions in
`potion_unknown`). Without the kind nothing of a potion reaches the net.
Run with pytest or `python scripts/tests/test_potion_rows.py`."""

import os
import sys
from pathlib import Path

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import sts  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
# The Ironclad pack first: its pool is what the discovery potions draw from.
PACKS = [ROOT / "content" / "packs" / n for n in ("act1-ironclad.json", "act1-relics.json", "act1-potions.json")]
DECK = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]


def load():
    for p in PACKS:
        sts.load_content(p.read_text(encoding="utf-8"))


def rows_of(c, **kw):
    f = sts.Features("effects", **kw)
    b = f.encode([c])
    return [dict(zip(f.row_names, r)) for r in b["rows"]], f


def potion_rows(rows):
    return [r for r in rows if r.get("trigger_Potion(Use)") == 1 and r.get("grant_own") == 1]


def test_fire_potion_row():
    load()
    c = sts.Combat(DECK, "jaw_worm", seed=1, potions=["gen:Fire Potion"])
    rows, _ = rows_of(c, extra_rows=True)
    (r,) = potion_rows(rows)
    assert r["damage_plain"] == 20 and r["potion_potency"] == 20, r


def test_fire_potion_row_under_bark():
    load()
    c = sts.Combat(DECK, "jaw_worm", seed=1, potions=["gen:Fire Potion"], relics=["gen:Sacred Bark"])
    rows, _ = rows_of(c, extra_rows=True)
    (r,) = potion_rows(rows)
    assert r["damage_plain"] == 40 and r["potion_potency"] == 40, r
    bark = [x for x in rows if x.get("grant_relic") == 1 and x.get("potion_potency")]
    assert len(bark) == 1 and bark[0]["potion_potency"] == 2 and bark[0]["trigger_Potion(Use)"] == 1, bark


def test_fairy_row_has_its_trigger():
    """A potion with a trigger (Fairy in a Bottle, docs/specs/would-die.md)
    writes it in the trigger column, not `Potion(Use)`: a net tells it from
    a drinkable heal."""
    load()
    c = sts.Combat(DECK, "jaw_worm", seed=1, potions=["gen:Fairy in a Bottle"])
    rows, _ = rows_of(c, extra_rows=True)
    assert potion_rows(rows) == []
    (r,) = [x for x in rows if x.get("potion_potency")]
    assert r["trigger_OwnerDied"] == 1 and r["grant_own"] == 1 and r["potion_potency"] == 30, r


def test_no_potion_rows_without_kind():
    load()
    c = sts.Combat(DECK, "jaw_worm", seed=1, potions=["gen:Fire Potion"])
    rows, _ = rows_of(c)
    assert potion_rows(rows) == []
    rows, _ = rows_of(c, extra_rows=True, row_kinds=[k for k in sts.ROW_KINDS if k != "potion"])
    assert potion_rows(rows) == []


def test_potion_free_rows_equal():
    """A fight without potions writes the same rows with the kind on or
    off, the new columns all zero."""
    c = sts.Combat(DECK, "jaw_worm", seed=1)
    for extra in (False, True):
        rows, f = rows_of(c, extra_rows=extra)
        assert "potion_potency" in f.row_names and "trigger_Potion(Use)" in f.row_names
        assert all(r["potion_potency"] == 0 and r["trigger_Potion(Use)"] == 0 for r in rows)


def test_ids_potion_columns():
    load()
    c = sts.Combat(DECK, "jaw_worm", seed=1, potions=["gen:Fire Potion", "gen:Block Potion"])
    f = sts.Features("ids", extra_rows=True)
    p = dict(zip(f.player_names, f.encode([c])["player"][0]))
    assert p["potion_unknown"] == 2
    assert not any(n.startswith("potion_") for n in sts.Features("ids").player_names)
    assert not any(n.startswith("potion_") for n in sts.Features("effects", extra_rows=True).player_names)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
