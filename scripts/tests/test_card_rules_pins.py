"""Pins for the card-rules spec (docs/specs/card-rules.md, build step 1):
feature arrays on fixed states holding Entangled, Corruption and Clash,
written on the code before the spec.

- `test_product_layout_unchanged`: the product net's own layout
  (`stsnet.features_for` of its meta). Must never change: today's nets
  read byte-identical inputs.
- `test_default_layout_unchanged`: the default effects and ids layouts.
  Step 3 re-pins this part on purpose (the `only_attacks_in_hand` card
  column leaves the default).

Each array is pinned as sha256 of its bytes, with dtype and shape.
`python scripts/tests/test_card_rules_pins.py [product|default]` rewrites
the pins (both when no part is named); only do that on purpose."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import sts  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PINS = os.path.join(HERE, "data", "card_rules_pins.json")
PRODUCT = Path("runs") / "2026-10-29-seed-check-r2-s1-1a789b2" / "model.pt"
PACKS = [ROOT / "content" / "packs" / "act1-monsters.json", ROOT / "content" / "packs" / "act1-ironclad.json"]
DECK = ["Strike"] * 4 + ["Defend"] * 3 + ["Bash", "Clash", "Clash", "gen:Corruption", "gen:Corruption",
                                           "Shrug It Off", "Pommel Strike"]


def product_net():
    """The product net, here or in the main checkout (a worktree has no runs/)."""
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    for base in (ROOT, Path(common).parent):
        if (base / PRODUCT).exists():
            return base / PRODUCT
    raise FileNotFoundError(PRODUCT)


def fixed_states():
    """Greedy play against Red Slaver (Entangle on the player) and two other
    fights, every decision state, with Clash in hand and piles and
    Corruption played (held) in some."""
    for p in PACKS:
        sts.load_content(p.read_text(encoding="utf-8"))
    out = []
    for i, (kind, foe) in enumerate([("versus", ["gen:Red Slaver"]), ("versus", ["gen:Red Slaver"]),
                                     ("encounter", "jaw_worm"), ("encounter", "cultist")]):
        for seed in range(3):
            c = (sts.Combat.versus(DECK, foe, seed=10 * i + seed, hp=60) if kind == "versus"
                 else sts.Combat(DECK, foe, seed=10 * i + seed, hp=60))
            n0 = len(out)
            while not c.is_over() and len(out) < n0 + 25:
                out.append(c.clone())
                c.step(sts.greedy_action(c))
    return out


def hashes(batch):
    return {k: {"dtype": str(v.dtype), "shape": list(v.shape), "sha256": hashlib.sha256(v.tobytes()).hexdigest()}
            for k, v in sorted(batch.items())}


def default_part(states):
    out = {}
    for mode in ("effects", "ids"):
        for k, v in hashes(sts.Features(mode).encode(states, heuristic=True)).items():
            out[f"{mode}/{k}"] = v
    return out


def product_part(states):
    import stsnet
    _, _, meta = stsnet.load(str(product_net()))
    return hashes(stsnet.features_for(meta).encode(states, heuristic=True))


def coverage(states):
    """What the states hold, so the pins cover what they claim to."""
    text = [s.render() for s in states]
    return {"states": len(states),
            "entangled": sum("Entangled" in t for t in text),
            "corruption_held": sum("Corruption" in t.split("Hand:")[0] for t in text),
            "clash": sum("Clash" in t for t in text)}


def load_pins():
    with open(PINS, encoding="utf-8") as f:
        return json.load(f)


def test_states_cover_the_rules():
    cov = coverage(fixed_states())
    assert cov == load_pins()["coverage"]
    assert cov["entangled"] > 0 and cov["corruption_held"] > 0 and cov["clash"] > 0


def test_product_layout_unchanged():
    assert product_part(fixed_states()) == load_pins()["product"]


def test_default_layout_unchanged():
    assert default_part(fixed_states()) == load_pins()["default"]


if __name__ == "__main__":
    parts = sys.argv[1:] or ["product", "default"]
    pins = load_pins() if os.path.exists(PINS) else {}
    states = fixed_states()
    pins["coverage"] = coverage(states)
    if "product" in parts:
        pins["product"] = product_part(states)
    if "default" in parts:
        pins["default"] = default_part(states)
    with open(PINS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(pins, f, indent=1, sort_keys=True)
        f.write("\n")
    print(PINS, pins["coverage"])
