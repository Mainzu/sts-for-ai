"""Trains one value net on a self-play data set (MSE on the final score),
early-stopping on the validation set. Both nets in the generalisation test
use this with the same seed and budget; only the card features differ.

    python scripts/train.py effects|ids
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("OMP_NUM_THREADS", "1")  # before torch; see stsnet.py
os.environ.setdefault("MKL_DISABLE_FAST_MM", "1")  # likewise

import numpy as np
import torch

import selfplay
from progress import Progress
import sts
import stsnet

MODELS = os.path.join(os.path.dirname(__file__), "..", "models")
BATCH = 512
EPOCHS = 20
PATIENCE = 3
LR = 1e-3
# Small batches: past 4 threads on the dev machine, more torch
# threads made epochs slower (torch's default was ~30% slower).
THREADS = min(4, os.cpu_count() or 4)


def mse(model, norm, ds, batch=4096):
    """Validation loss: MSE on the score, or for an HP-loss net (switch 6)
    the cross-entropy of its histogram against the labels'."""
    model.eval()
    err, n = 0.0, 0
    hp = getattr(model, "hp_loss", False)
    with torch.no_grad():
        for i in range(0, len(ds), batch):
            b = ds.batch(np.arange(i, min(i + batch, len(ds))))
            y = model(norm.tensors(b))
            target = torch.from_numpy(b["target"])
            err += float(cross_entropy(y, target)) * len(y) if hp else float(((y - target) ** 2).sum())
            n += len(y)
    return err / n


def cross_entropy(logp, target):
    """Mean cross-entropy of predicted log-histograms logp [B, K] against
    target histograms [B, K] (one-hot or soft)."""
    return -(target * logp).sum(1).mean()


def value_loss(pred, target, weight, hp_loss, bounded=None):
    """Batch mean of each example's value-loss weight times its loss (squared
    error, or with switch 6 cross-entropy); `weight` None is every weight 1.
    `bounded` 1 marks a target that is an upper bound (solver bounds): its
    loss is one-sided, max(0, prediction - bound)^2."""
    per = -(target * pred).sum(1) if hp_loss else (pred - target) ** 2
    if bounded is not None and not hp_loss:
        per = torch.where(bounded == 1, torch.relu(pred - target) ** 2, per)
    if weight is None:
        return per.mean()
    return (weight * per).mean()


# Width (HP) of the sigmoid that smooths the external formula's win step in
# the ranking term (switch 3 with switch 6).
RANK_TAU = 2.0


RANK_FIELDS = ("decision", "option", "prob", "opt_const", "rank_value", "bounded")


def batches(ds, norm, chunks, pool, rank=False):
    """Yields (tensors, target, value-loss weight or None, ranking fields or
    None, `bounded` or None) per index array of `chunks`, building the next
    batch on `pool` while the caller trains on the current one."""
    def prep(idx):
        b = ds.batch(idx)
        bnd = torch.from_numpy(np.asarray(b["bounded"])) if "bounded" in b else None
        # Only `bounded` may be absent (parts without bounds); every other field must be there.
        zeros = torch.zeros(len(idx), dtype=torch.int8)
        r = tuple(zeros if k == "bounded" and k not in b else torch.from_numpy(np.asarray(b[k]))
                  for k in RANK_FIELDS) if rank else None
        w = torch.from_numpy(b["weight"]) if "weight" in b else None
        return norm.tensors(b), torch.from_numpy(b["target"]), w, r, bnd
    nxt = pool.submit(prep, chunks[0])
    for i in range(1, len(chunks) + 1):
        cur = nxt.result()
        if i < len(chunks):
            nxt = pool.submit(prep, chunks[i])
        yield cur


def ranking_loss(y, decision, option, prob, opt_const, rank_value, bounded=None):
    """Pairwise ranking term (learned-play switch 3): within each decision,
    an option's predicted value (its afterstates' predictions weighted by
    outcome probability, plus its finished outcomes' exact part) should
    order like its search value. Mean hinge max(0, v_worse - v_better) over
    pairs with different search values: 0 when every pair is in order.
    `bounded` nonzero marks an option whose value is an upper bound (solver
    bounds): it is the worse of a pair only with an exact option at or
    above its bound, and never the better; two bounded options aren't
    paired."""
    m = option >= 0
    if not bool(m.any()):
        return y.sum() * 0
    key = decision[m] * (int(option.max()) + 1) + option[m].long()
    keys, inv = torch.unique(key, return_inverse=True)
    v = torch.zeros(len(keys)).index_add(0, inv, prob[m] * y[m])
    v = v + torch.zeros(len(keys)).scatter(0, inv, opt_const[m])
    r = torch.zeros(len(keys)).scatter(0, inv, rank_value[m])
    d = torch.zeros(len(keys), dtype=torch.long).scatter(0, inv, decision[m])
    if bounded is None:
        pairs = (d[:, None] == d[None, :]) & (r[:, None] > r[None, :])
    else:
        b = torch.zeros(len(keys), dtype=torch.bool).scatter(0, inv, bounded[m] != 0)
        exact = (r[:, None] > r[None, :]) & ~b[None, :]
        under = (r[:, None] >= r[None, :]) & b[None, :]
        pairs = (d[:, None] == d[None, :]) & ~b[:, None] & (exact | under)
    if not bool(pairs.any()):
        return y.sum() * 0
    return torch.relu(v[None, :] - v[:, None])[pairs].mean()


def decision_order(decision, rng):
    """A shuffled order of the examples that keeps each decision's
    (contiguous) examples together."""
    starts = np.flatnonzero(np.r_[True, decision[1:] != decision[:-1]])
    ends = np.r_[starts[1:], len(decision)]
    return np.concatenate([np.arange(starts[i], ends[i]) for i in rng.permutation(len(starts))])


def decision_batches(decision, order, size):
    """Index arrays of about `size` examples from `order`, cut only between
    decisions."""
    d = decision[order]
    cuts = np.flatnonzero(d[1:] != d[:-1]) + 1
    out, start = [], 0
    for c in cuts:
        if c - start >= size:
            out.append(order[start:c])
            start = c
    out.append(order[start:])
    return out


def replay_batches(n_new, n_pool, share, rng, size=BATCH):
    """One epoch's index arrays into `Dataset.concat([new, pool])`: every
    new example once (shuffled), and in each batch about `share` of the
    examples drawn from the pool (indices n_new + j, fresh each epoch, with
    replacement only when the pool is too small)."""
    k_new = max(1, round(size * (1 - share)))
    order = rng.permutation(n_new)
    chunks = [order[i:i + k_new] for i in range(0, n_new, k_new)]
    n_rep = round(n_new * share / (1 - share))
    rep = n_new + rng.choice(n_pool, n_rep, replace=n_rep > n_pool)
    return [np.concatenate([c, r]) for c, r in zip(chunks, np.array_split(rep, len(chunks)))]


def pool_epoch(new, pool, chunks):
    """(dataset, chunks) for one epoch of `replay_batches` index arrays into
    `Dataset.concat([new, pool])`: the new examples followed by only the pool
    examples the chunks draw (each once, in pool order, read with
    `take_unmapped`), the chunks re-indexed into it. The batches hold the
    same examples in the same order as with the whole pool concatenated,
    without the pool ever whole in memory."""
    n_new = len(new)
    flat = np.concatenate(chunks)
    used = np.unique(flat[flat >= n_new] - n_new)
    ds = stsnet.Dataset.concat([new, pool.take_unmapped(used)])
    return ds, [np.where(c >= n_new, n_new + np.searchsorted(used, c - n_new), c) for c in chunks]


def rank_score(pred, x, hp_loss, rule=None):
    """The ranking term's scores of a batch's predictions `pred`: a score
    net's own, an HP-loss net's the external formula under its score
    `rule` with the win step smoothed (RANK_TAU)."""
    if not hp_loss:
        return pred
    return stsnet.external_score(pred.exp(), x["hp"], x["start_hp"], x["max_hp"], x["win_heal"], RANK_TAU,
                                 rule=rule)


def train(mode, train_ds, val_ds, seed=0, log=print, curves=None, rank_weight=0.0, hp_loss=False,
          start=None, replay=None, share=0.5, lr=None, epochs=None, score_rule=None, anchor=0.0, snapshot=None, act="relu"):
    """Returns (model, normalizer, history) with the best-validation weights.
    `curves`, when given, gets per-epoch "train" loss and "val" MSE lists.
    The value loss weights each example by `train_ds.weight` when set.
    `rank_weight` > 0 (switch 3): adds that
    times `ranking_loss`, with batches that keep decisions whole (the
    training set needs the ranking fields). `hp_loss` (switch 6): targets
    are histograms of HP lost, the net predicts one (cross-entropy), and the
    ranking term orders options by the external formula's score (smoothed,
    RANK_TAU); the datasets need the HP scalars.
    Warm start (docs/specs/warm-start.md): `start` (model, normaliser)
    trains that net on with its normaliser instead of a fresh one;
    `replay`, a dataset in the same layout, mixes about `share` of each
    batch from it (fresh draws each epoch; an epoch ends when the new
    examples are used up). `lr` / `epochs` override LR / EPOCHS.
    `score_rule` (switch 6, stsnet.score_rule; None: the engine rule) goes
    on a fresh net as its `score_rule`, which the ranking term scores by.
    `anchor` λ > 0 (docs/specs/burst-anchor.md, warm start only) adds λ x
    the summed squared distance of every weight from the start net's.
    `snapshot(step, epoch, model, norm)`, when given, is called after each
    optimiser step (from 1) and once before the first with step 0, for
    saving the net as it trains (scripts/analysis/neurons.py retrain).
    `act` is a fresh net's hidden activation (stsnet.ACTS)."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    rank = rank_weight > 0
    if replay is not None and (rank or not 0 < share < 1):
        raise ValueError("replay needs 0 < share < 1 and no ranking loss")
    if start is None:
        norm = stsnet.Normalizer.fit(train_ds)
        model = stsnet.ValueNet(selfplay.features(mode).dims, hp_loss=hp_loss, act=act)
        if score_rule is not None:
            model.score_rule = score_rule
    else:
        model, norm = start
    if anchor and start is None:
        raise ValueError("anchor needs a start net")
    theta0 = [p.detach().clone() for p in model.parameters()] if anchor else None
    n_new = len(train_ds)
    if rank and train_ds.decision is None:
        raise ValueError("the ranking loss needs a training set sampled with labels (ranking fields)")
    opt = torch.optim.Adam(model.parameters(), lr=LR if lr is None else lr, weight_decay=1e-5)
    best, best_state, bad, hist = float("inf"), None, 0, []
    threads = torch.get_num_threads()
    torch.set_num_threads(THREADS)
    step = 0
    if snapshot is not None:
        snapshot(0, 0, model, norm)
    with ThreadPoolExecutor(1) as pool:
        for epoch in range(EPOCHS if epochs is None else epochs):
            t = time.perf_counter()
            model.train()
            total, n = 0.0, 0
            epoch_ds = train_ds
            if replay is not None:
                epoch_ds, chunks = pool_epoch(train_ds, replay, replay_batches(n_new, len(replay), share, rng))
            elif rank:
                chunks = decision_batches(train_ds.decision, decision_order(train_ds.decision, rng), BATCH)
            else:
                order = rng.permutation(len(train_ds))
                chunks = [order[i:i + BATCH] for i in range(0, len(order), BATCH)]
            p = Progress(f"{mode} epoch {epoch + 1}", len(chunks), log, every_s=60, every_frac=1.0)
            for x, y, w, r, bnd in batches(epoch_ds, norm, chunks, pool, rank):
                p.update()
                pred = model(x)
                loss = value_loss(pred, y, w, hp_loss, bnd)
                if rank:
                    score = rank_score(pred, x, hp_loss, getattr(model, "score_rule", None))
                    loss = loss + rank_weight * ranking_loss(score, *r)
                if theta0 is not None:
                    loss = loss + anchor * sum(((p - p0) ** 2).sum() for p, p0 in zip(model.parameters(), theta0))
                opt.zero_grad()
                loss.backward()
                opt.step()
                step += 1
                if snapshot is not None:
                    snapshot(step, epoch, model, norm)
                total, n = total + loss.item() * len(y), n + len(y)
            p.close(final=False)
            v = mse(model, norm, val_ds)
            hist.append(v)
            if curves is not None:
                curves.setdefault("train", []).append(total / n)
                curves.setdefault("val", []).append(v)
            log(f"  {mode} epoch {epoch + 1}: val MSE {v:.4f} ({time.perf_counter() - t:.0f}s)")
            if v < best - 1e-5:
                best, bad = v, 0
                best_state = {k: x.clone() for k, x in model.state_dict().items()}
            else:
                bad += 1
                if bad >= PATIENCE:
                    break
    torch.set_num_threads(threads)
    model.load_state_dict(best_state)
    return model.eval(), norm, hist


def model_path(mode):
    return os.path.join(MODELS, f"value_{mode}.pt")


def train_and_save(mode, sets, seed=0):
    model, norm, hist = train(mode, sets["train"][mode], sets["val"][mode], seed)
    os.makedirs(MODELS, exist_ok=True)
    meta = {"card_repr": mode, **selfplay.meta_vocab(mode), "held_out": selfplay.HELD_OUT,
            "held_out_check9": sts.held_out_card_names(), "val_mse": min(hist), "format": selfplay.FORMAT}
    stsnet.save(model_path(mode), model, norm, meta)
    return model, norm, meta


if __name__ == "__main__":
    train_and_save(sys.argv[1], selfplay.all_sets())
