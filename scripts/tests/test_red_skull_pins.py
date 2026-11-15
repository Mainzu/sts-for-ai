"""Pins for the red-skull-strength spec (docs/specs/red-skull-strength.md,
build step 1): official fights without Red Skull, written on the code
before the spec. Red Skull's change (and the new HP-crossing triggers) must
leave them as they are:

- `test_states_unchanged`: every decision state's codec bytes and the
  fight results.
- `test_product_layout_unchanged`: the product net's own layout
  (`stsnet.features_for` of its meta) on those states.

`python scripts/tests/test_red_skull_pins.py` rewrites the pins; only do
that on purpose."""

import hashlib
import json
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import sts  # noqa: E402
from test_card_rules_pins import hashes, product_net  # noqa: E402

PINS = os.path.join(HERE, "data", "red_skull_pins.json")
# Official cards that read Strength or lose HP, so HP crosses half often.
DECK = ["Strike"] * 4 + ["Defend"] * 3 + ["Bash", "Heavy Blade", "Hemokinesis", "Bloodletting", "Inflame",
                                           "Flex", "Twin Strike", "Shrug It Off"]
FIGHTS = ["jaw_worm", "cultist", "gremlin_nob", "lagavulin", "slime_boss"]


def fights():
    """Greedy play from low and high starting HP: (decision states, results)."""
    states, results = [], []
    for i, enc in enumerate(FIGHTS):
        for seed, hp in ((0, 80), (1, 45), (2, 30)):
            c = sts.Combat(DECK, enc, seed=10 * i + seed, hp=hp)
            n0 = len(states)
            while not c.is_over() and len(states) < n0 + 40:
                states.append(c.clone())
                c.step(sts.greedy_action(c))
            results.append([enc, seed, hp, c.is_over(), c.render().splitlines()[0]])
    return states, results


def state_part(states, results):
    h = hashlib.sha256()
    for s in states:
        h.update(bytes(s.encode()))
    return {"states": len(states), "codec_sha256": h.hexdigest(), "results": results}


def product_part(states):
    import stsnet
    _, _, meta = stsnet.load(str(product_net()))
    return hashes(stsnet.features_for(meta).encode(states, heuristic=True))


def load_pins():
    with open(PINS, encoding="utf-8") as f:
        return json.load(f)


def test_states_unchanged():
    states, results = fights()
    assert state_part(states, results) == load_pins()["states"]


def test_product_layout_unchanged():
    states, _ = fights()
    assert product_part(states) == load_pins()["product"]


if __name__ == "__main__":
    states, results = fights()
    pins = {"states": state_part(states, results), "product": product_part(states)}
    with open(PINS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(pins, f, indent=1, sort_keys=True)
        f.write("\n")
    print(PINS, pins["states"]["states"])
