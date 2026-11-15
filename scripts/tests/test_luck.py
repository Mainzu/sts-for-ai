"""Tests for luck logging (docs/specs/luck-corrected-labels.md): `sts.run`
with `luck=` plays the same games and gives one luck term per decision; a
priced luck net is refused; datasets and replays carry `luck`.
Run with `python scripts/tests/test_luck.py` or with pytest."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sts  # noqa: E402

SPECS = [("jaw_worm", ["Strike"] * 5 + ["Defend"] * 4 + ["Bash", "Pommel Strike"], s) for s in range(6)] + \
        [("gremlin_nob", ["Strike"] * 5 + ["Defend"] * 4 + ["Bash", "Shrug It Off"], s) for s in range(6)]


def _net(**kw):
    import stsnet
    from test_contract import tiny_trained
    meta = {"card_repr": "effects"}
    model, norm = tiny_trained(meta)
    return stsnet.rust_evaluator(model, norm, meta, **kw), stsnet.features_for(meta)


def test_run_luck_same_game():
    ev, feats = _net()
    plain = sts.run("search", SPECS, evaluator=ev, features=feats, record=True, threads=2)
    logged = sts.run("search", SPECS, evaluator=ev, features=feats, record=True, threads=2, luck=ev)
    for p, q in zip(plain, logged):
        assert [str(a) for a in p["actions"]] == [str(a) for a in q["actions"]]
        assert (p["score"], p["turns"], p["hp_end"]) == (q["score"], q["turns"], q["hp_end"])
        assert "luck" not in p
        assert len(q["luck"]) == len(q["actions"])
    assert any(abs(x) > 1e-6 for q in logged for x in q["luck"])
    unrec = sts.run("search", SPECS[:2], evaluator=ev, features=feats, threads=1, luck=ev)
    assert [u["luck"] for u in unrec] == [q["luck"] for q in logged[:2]], "luck without record, same terms"


def test_run_luck_refuses_priced_net():
    ev, feats = _net()
    priced, _ = _net(hp_bonus=0.01)
    try:
        sts.run("search", SPECS[:1], evaluator=ev, features=feats, luck=priced)
        raise AssertionError("accepted a priced luck net")
    except ValueError:
        pass


if __name__ == "__main__":
    for name, f in sorted(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
            print(f"ok  {name}")
