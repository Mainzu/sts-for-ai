"""Pins for code the explorer reuses (docs/specs/explorer-v2.md, build step
1): the two-turn guarded fight's record stays as it is (its existing keys
and values) when the explorer adds its own key. STS_REGEN_PINS=1 rewrites
the fixture. Run with pytest or `python scripts/tests/test_explore_pins.py`."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import bench  # noqa: E402
import depth_paired  # noqa: E402

PIN_FILE = os.path.join(os.path.dirname(__file__), "data", "explore", "two_turn_record_pin.json")
SPEC = {"deck": ["Strike"] * 5 + ["Defend"] * 4 + ["Bash", "Inflame"], "encounter": "jaw_worm",
        "seed": 4242, "hp": 60, "character": "ironclad"}
TWO = {"limit": bench.LIMIT, "turns": 2, "sample_k": 2, "max_nodes": 20_000}


def record():
    # (spec, two, margin, evaluator, top_k, k_count, seed_per_turn, step_line, record): the product's flags
    return depth_paired.guarded_fight((SPEC, TWO, -1.0, "heuristic", 0, 3, True, True, True))


def test_two_turn_record_pinned():
    got = json.loads(json.dumps(record()))
    if os.environ.get("STS_REGEN_PINS"):
        os.makedirs(os.path.dirname(PIN_FILE), exist_ok=True)
        with open(PIN_FILE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(got, f, indent=1)
    with open(PIN_FILE, encoding="utf-8") as f:
        want = json.load(f)
    # step 4 adds one key the explorer reads; every key that exists today keeps its value
    assert {k: got[k] for k in want} == want
    assert set(got) - set(want) <= {"scores"}, f"unexpected new record keys {set(got) - set(want)}"


def test_two_turn_scores_key():
    # explorer-v2 step 4: asked for (a 10th job field), `scores` is the only
    # addition; one entry per action; a searched entry's pick indexes its
    # options and the played action is that option's first
    got = json.loads(json.dumps(depth_paired.guarded_fight((SPEC, TWO, -1.0, "heuristic", 0, 3, True, True, True, True))))
    with open(PIN_FILE, encoding="utf-8") as f:
        want = json.load(f)
    assert {k: got[k] for k in want} == want and set(got) - set(want) == {"scores"}
    assert len(got["scores"]) == len(got["actions"])
    assert got["scores"][0].get("line") is None
    for a, sc in zip(got["actions"], got["scores"]):
        if sc.get("line"):
            continue
        assert len(sc["options"]) == len(sc["one"]) and (sc["two"] is None or len(sc["two"]) == len(sc["one"]))
        assert sc["options"][sc["pick"]][0] == a


if __name__ == "__main__":
    test_two_turn_record_pinned()
    test_two_turn_scores_key()
    print("ok")
