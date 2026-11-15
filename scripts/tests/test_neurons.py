"""Tests for scripts/analysis/neurons.py and train.train's snapshot hook.
Run with pytest."""

import json
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import selfplay  # noqa: E402
import stsnet  # noqa: E402
import train  # noqa: E402
import neurons  # noqa: E402
from test_net import train_dataset  # noqa: E402


def snapshot_series(folder):
    """Trains a tiny net for 2 epochs, saving a snapshot at every step the
    way `neurons.py retrain` names them; returns the steps seen."""
    meta = {"card_repr": "effects", **selfplay.meta_vocab("effects")}
    steps = []

    def snap(step, epoch, model, norm):
        steps.append((step, epoch))
        stsnet.save(os.path.join(folder, f"snap-{step:06d}-e{epoch}.pt"), model, norm, meta)

    ds = train_dataset()
    old = train.EPOCHS
    train.EPOCHS = 2
    try:
        train.train("effects", ds, ds, seed=0, log=lambda *a: None, snapshot=snap)
    finally:
        train.EPOCHS = old
    return steps


def test_snapshot_hook_and_report(tmp_path):
    snaps = tmp_path / "snaps"
    snaps.mkdir()
    steps = snapshot_series(str(snaps))
    assert steps[0] == (0, 0) and [s for s, _ in steps] == list(range(len(steps)))
    assert {e for _, e in steps} == {0, 1}
    series = neurons.snapshots(str(snaps))
    assert [s for s, _, _ in series] == [s for s, _ in steps]
    last = series[-1][2]
    out = tmp_path / "out"
    neurons.report(types.SimpleNamespace(net=last, compare=[last], series=str(snaps), encounter="gremlin_nob",
                                         fights=1, out=str(out)))
    data = json.loads((out / "data.json").read_text())
    n, w = len(data["cards"]), len(data["card_acts"][0])
    assert n > 50 and w == 64 and len(data["owner"]) == n
    assert data["enemies"] and len(data["enemy_acts"]) == len(data["enemies"])
    # A net compared with itself: every live neuron's best partner correlates 1.
    live = [j for j in range(w) if max(r[j] for r in data["card_acts"]) > 1e-3]
    assert live and all(data["compare"][0]["corr"][j] > 0.999 for j in live)
    s = data["series"]
    assert len(s["steps"]) == len(steps) and len(s["acts"][0]) == w and len(s["acts"][0][0]) == n
    assert all(abs(s["settle"][-1][j] - 1) < 1e-3 for j in live)  # the last snapshot is its own end
    c = data["copies"]
    assert set(c["cards"]) <= set(neurons.COPY_CARDS) and "Strike" in c["cards"]
    assert all(len(v["score"]) == len(neurons.COPIES) for v in c["cards"].values())
    assert c["head_width"] == 128 and all(0 <= h <= 128 for v in c["cards"].values() for h in v["head_on"])
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "/*DATA*/null" not in page and '"card_acts"' in page


def test_activation_saved_and_rust_refuses(tmp_path):
    """A non-ReLU net keeps its activation through save/load, the Rust
    evaluator refuses a SiLU net, and a ReLU net's file carries no `act`
    key (old nets and their pins stay as they were)."""
    import pytest
    import sts
    import torch
    meta = {"card_repr": "effects", **selfplay.meta_vocab("effects")}
    ds = train_dataset()
    norm = stsnet.Normalizer.fit(ds)
    for act in ("relu", "silu"):
        model = stsnet.ValueNet(sts.Features("effects").dims, act=act)
        path = str(tmp_path / f"{act}.pt")
        stsnet.save(path, model, norm, meta)
        assert ("act" in torch.load(path, weights_only=False)) == (act != "relu")
        back, n2, m2 = stsnet.load(path)
        assert back.act == act and isinstance(back.card[1], type(stsnet.ACTS[act]()))
        if act != "relu":
            with pytest.raises(ValueError, match="Rust search runs"):
                stsnet.rust_evaluator(back, n2, m2)
            net = neurons.Net(path)
            counts = neurons.dead_counts(net, neurons.game_states(2))
            assert {"card.0", "card.2", "monster.2", "head.0.0", "head.0.2"} <= set(counts)
            assert all(0 <= d <= n for d, n in counts.values())
