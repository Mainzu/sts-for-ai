"""Pins for the relics spec (docs/specs/relics.md, build step 1): what a fight
with no relics given must keep doing once the fight holds its own
combat-end heal and takes relics.

- `test_features_unchanged_on_golden`: every array of both feature modes,
  with the heuristic scalars (`heuristic`, `heuristic_hp_loss`, `win_heal`,
  ...), over contract_pins' fixed state set, as sha256 of its bytes.
- `test_no_relics_unchanged`: `sts.run` with the search agent on 20 fixed
  specs: won, hp_end, turns and score per spec.

`python scripts/tests/test_relic_pins.py` rewrites the pins; only do that on
purpose."""

import hashlib
import json
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import sts  # noqa: E402

PINS = os.path.join(HERE, "data", "relic_pins.json")


def feature_hashes():
    import contract_pins
    states = contract_pins.fixed_states()
    out = {}
    for mode in ("effects", "ids"):
        b = sts.Features(mode).encode(states, heuristic=True)
        for k, v in sorted(b.items()):
            out[f"{mode}/{k}"] = {"dtype": str(v.dtype), "shape": list(v.shape),
                                  "sha256": hashlib.sha256(v.tobytes()).hexdigest()}
    return out


def specs():
    """The 15 encounters with the starter deck, then 5 with extra cards and
    lower HP (seeds fixed)."""
    deck = list(sts.starter_deck("ironclad"))
    names = sts.encounter_names()
    out = [{"encounter": e, "deck": deck, "seed": 7000 + i} for i, e in enumerate(names)]
    extra = [["Inflame", "Pommel Strike"], ["Shrug It Off", "Bash+"], ["Clothesline", "Anger"],
             ["Iron Wave", "Cleave"], ["Twin Strike", "Flex"]]
    for i, cards in enumerate(extra):
        out.append({"encounter": names[(3 * i + 1) % len(names)], "deck": deck + cards, "seed": 7100 + i, "hp": 40 + 5 * i})
    return out


def run_results():
    res = sts.run("search", specs(), threads=4)
    return [{"won": bool(r["won"]), "hp_end": int(r["hp_end"]), "turns": int(r["turns"]), "score": float(r["score"])}
            for r in res]


def load_pins():
    with open(PINS, encoding="utf-8") as f:
        return json.load(f)


def test_features_unchanged_on_golden():
    assert feature_hashes() == load_pins()["features"]


def test_no_relics_unchanged():
    assert run_results() == load_pins()["run"]


if __name__ == "__main__":
    with open(PINS, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"features": feature_hashes(), "run": run_results()}, f, indent=1, sort_keys=True)
        f.write("\n")
    print(PINS)
