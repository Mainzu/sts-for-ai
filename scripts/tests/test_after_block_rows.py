"""After-block replacements as net rows (docs/specs/after-block.md): a held
pack power's after-block row writes its event as the replacement trigger
(`Replace(AttackedAfterBlock)` and the rest), `upTo` as the condition
`AmountAtMost` with its value in `condition_param`, and `AtLeast` in the
row-only `replace_at_least`. Run with pytest or
`python scripts/tests/test_after_block_rows.py`."""

import os
import sys
from pathlib import Path

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import sts  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "content" / "packs" / "act1-relics.json"
DECK = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]


def replacement_rows(relic):
    sts.load_content(PACK.read_text(encoding="utf-8"))
    c = sts.Combat(DECK, "jaw_worm", seed=1, relics=[f"gen:{relic}"])
    f = sts.Features("effects", extra_rows=True)
    b = f.encode([c])
    rows = [dict(zip(f.row_names, r)) for r in b["rows"]]
    return [r for r in rows if any(r.get(f"trigger_Replace({e})") == 1 for e in EVENTS)]


EVENTS = ["DealtAfterBlock", "TakenAfterBlock", "AttackedAfterBlock", "HpLossLast"]


def test_torii_row():
    (r,) = replacement_rows("Torii")
    assert r["trigger_Replace(AttackedAfterBlock)"] == 1 and r["condition_AmountAtMost"] == 1, r
    assert r["condition_Always"] == 0 and r["condition_param"] == 5 and r["replace_cap"] == 1, r
    assert r["replace_at_least"] == 0 and r["replace_stacks"] == 1, r


def test_boot_row():
    (r,) = replacement_rows("The Boot")
    assert r["trigger_Replace(DealtAfterBlock)"] == 1 and r["condition_Always"] == 1, r
    assert r["replace_at_least"] == 5 and r["condition_param"] == 0, r


def test_rod_and_buffer_rows():
    (r,) = replacement_rows("Tungsten Rod")
    assert r["trigger_Replace(HpLossLast)"] == 1 and r["replace_add"] == -1, r
    (r,) = replacement_rows("Fossilized Helix")
    assert r["trigger_Replace(TakenAfterBlock)"] == 1 and r["replace_cancel"] == 1 and r["reduce_self"] == 1, r


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
