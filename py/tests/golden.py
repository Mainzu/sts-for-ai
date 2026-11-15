"""Golden feature batches on the triggers-and-conditions format (rows and
vocabularies). `python py/tests/golden.py` rewrites the file; only do that
on purpose, since test_sts.py checks new builds against it byte for byte."""

import os

import numpy as np
import sts

PATH = os.path.join(os.path.dirname(__file__), "data", "golden_rows.npz")
STARTER = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
# Hook-power cards, conditional cards and older ones, three per encounter.
EXTRAS = ["Demon Form", "Rage+", "Spot Weakness", "Combust", "Dropkick", "Metallicize", "Rupture", "Bloodletting",
          "Brutality+", "Go for the Eyes", "FTL", "Inflame", "Flex"]
HELD_OUT_POWERS = ["Metallicize", "DemonForm", "Rage"]
# Ids known lists as a check-9 ids net would save them: no held-out cards or powers.
KNOWN_CARDS = [n for n in sts.all_card_names() if n not in set(sts.held_out_card_names())]
KNOWN_POWERS = [p for p in sts.power_names() if p not in HELD_OUT_POWERS]


def states():
    """Greedy-play decision states over a few encounters and decks."""
    out = []
    for i, enc in enumerate(["jaw_worm", "cultist", "two_louse", "gremlin_nob", "lagavulin", "two_fungi_beasts",
                             "three_sentries", "slime_boss"]):
        c = sts.Combat(STARTER + EXTRAS[i:i + 3], enc, seed=i + 1)
        while not c.is_over() and len(out) < (i + 1) * 12:
            out.append(c.clone())
            c.step(sts.greedy_action(c))
    c = sts.Combat(sts.starter_deck("silent") + ["Deadly Poison", "Bouncing Flask"], "jaw_worm", seed=3,
                   character="silent")
    while not c.is_over() and len(out) < 8 * 12 + 8:
        out.append(c.clone())
        c.step(sts.greedy_action(c))
    return out


def encode():
    ss = states()
    out = {}
    for mode, kc, kp in (("effects", None, None), ("ids", KNOWN_CARDS, KNOWN_POWERS)):
        b = sts.Features(mode, known_cards=kc, known_powers=kp).encode(ss)
        for k, v in b.items():
            out[f"{mode}_{k}"] = v
    return out


if __name__ == "__main__":
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    g = encode()
    np.savez_compressed(PATH, **g)
    print(PATH, {k: v.shape for k, v in g.items()})
