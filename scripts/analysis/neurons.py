"""Neuron microscope: what each neuron of a value net's card and monster
encoders responds to, how the head reacts to piled-up copies, how the
neurons formed over training and how they match another net's.

`report` reads a saved net (and optionally a snapshot series and other nets)
and writes `<out>/data.json` and `<out>/index.html`, a page that shows it:

    python scripts/analysis/neurons.py report runs/<run>/model.pt --series results/neurons/<name>/snapshots \\
        --compare runs/<other>/model.pt ... --out results/neurons/<name>

- Card neurons: each card alone in hand (vs Cultist), its card encoder
  output (phi, before x copies) per neuron.
- Monster neurons: the monster encoder's output per live enemy, averaged
  over the first decisions of `--fights` greedy-played fights of each
  Act 1 encounter, per enemy kind.
- Copies: the score (x100, HP-like) as copies of one card fill the draw
  pile, and how many head neurons stay on; and each attack's value over a
  Defend in hand as Strikes fill the draw pile (Perfected Strike's
  damage grows with them).
- Training: a snapshot series of one training run (same initial weights,
  so neuron j is the same neuron throughout): each card neuron's
  profile over cards at every snapshot, and its correlation with its
  final profile.
- Nets: each card neuron's best-correlated neuron (over the cards both
  nets know) in each `--compare` net.

`retrain` trains a fresh net the way `learn.fit` trained a registry run
(its config, datasets, rounds and seed; today's solved DB and encoder) and
saves snapshots at steps 0, 1, 2, 4, ... and at each epoch's first step,
plus the best-validation net as `final.pt`; no registry run is made. A run
whose datasets no longer replay (another rules version) can still give its
config: `--fresh N` plays a new round-0 dataset, N games per group (kept
in datasets/ like any other), and trains on that:

    python scripts/analysis/neurons.py retrain runs/<run> --out results/neurons/<name>/snapshots --threads 3

Everything goes under `--out`; delete that folder to clean up (snapshots
are ~1 MB each).
"""

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import numpy as np
import torch

import sts
import stsnet

COPIES = [0, 1, 2, 3, 5, 8, 12, 20, 30, 50, 80]
COPY_CARDS = ["Strike", "Defend", "Perfected Strike", "Inflame", "Wound"]
STRIKES = [0, 1, 2, 3, 4, 6, 8, 10, 14, 20]
STRIKE_CARDS = ["Perfected Strike", "Wild Strike", "Pommel Strike", "Twin Strike", "Inflame", "Strike"]
HAND = {"Defend": 3, "Bash": 1}
DRAW = {"Defend": 2}


class Net:
    """A loaded net with its encoder, and taps on its layers."""

    def __init__(self, path):
        self.path = path
        self.model, self.norm, self.meta = stsnet.load(path)
        self.feats = stsnet.features_for(self.meta)
        known = self.meta.get("known_cards")
        self.known = set(known) if known else set(sts.all_card_names())
        self.head_on = None
        self.model.head[0].register_forward_hook(lambda m, i, o: setattr(self, "head_on", int((o > 0).sum())))

    def tensors(self, c):
        return self.norm.tensors(self.feats.encode([c]))

    def pooled_rows(self, t, index, n):
        m = self.model
        psi = m.row(t["rows"])
        out = torch.zeros(n, m.row_width)
        on = index >= 0
        return out.index_add_(0, index[on], psi[on])

    @torch.no_grad()
    def card_phi(self, name):
        t = self.tensors(sts.Combat([name], "cultist", seed=1))
        rows = self.pooled_rows(t, t["row_card"], t["cards"].shape[0])
        return self.model.card(torch.cat([t["cards"], rows], 1))[0].numpy()

    @torch.no_grad()
    def monsters(self, c):
        """Monster encoder outputs [slots, width] and the live mask."""
        t = self.tensors(c)
        ent = self.pooled_rows(t, t["row_entity"], sts.ENTITIES)
        out = self.model.monster(torch.cat([t["monsters"][0], ent[1:1 + sts.MAX_MONSTERS]], 1)).numpy()
        return out, t["alive"][0].numpy() > 0

    @torch.no_grad()
    def score(self, c):
        return float(self.model(self.tensors(c)).item())


def card_list(nets):
    """Cards every net knows, Ironclad first, then Silent, then the rest."""
    known = set.intersection(*(n.known for n in nets))
    order = []
    for ch in sts.character_names():
        order += [c for c in sts.class_card_names(ch) if c in known and c not in order]
    order += [c for c in sts.all_card_names() if c in known and c not in order]
    owner = {}
    for ch in sts.character_names():
        for c in sts.class_card_names(ch):
            owner.setdefault(c, ch)
    return order, [owner.get(c, "other") for c in order]


def card_matrix(net, cards):
    rows, ok = [], []
    for c in cards:
        try:
            rows.append(net.card_phi(c))
            ok.append(True)
        except Exception:
            rows.append(None)
            ok.append(False)
    w = next(r for r in rows if r is not None).shape[0]
    return np.stack([r if r is not None else np.zeros(w, np.float32) for r in rows]), ok


def monster_matrix(net, fights, decisions=8):
    acts = {}
    for enc in sts.encounter_names():
        for seed in range(fights):
            c = sts.Combat(list(sts.starter_deck("ironclad")), enc, seed=seed)
            seen = 0
            for _ in range(200):
                if c.is_over() or seen >= decisions:
                    break
                if c.awaiting_action():
                    out, alive = net.monsters(c)
                    for i, m in enumerate(c.view()["monsters"]):
                        if i < len(alive) and alive[i]:
                            acts.setdefault(m["name"], []).append(out[i])
                    seen += 1
                c.step(sts.greedy_action(c))
    names = sorted(acts)
    return names, np.stack([np.mean(acts[n], 0) for n in names]), [len(acts[n]) for n in names]


def state(v0, hand, draw):
    v = json.loads(json.dumps(v0))
    v["hand"], v["draw"], v["discard"], v["exhaust"] = hand, draw, {}, {}
    return sts.Combat.from_view(v, seed=1)


def copies(net, encounter):
    v0 = sts.Combat(list(sts.starter_deck("ironclad")), encounter, seed=1).view()
    out = {"copies": COPIES, "cards": {}, "strikes": STRIKES, "strike_cards": {}}
    for x in COPY_CARDS:
        if x not in net.known:
            continue
        sc, on = [], []
        for k in COPIES:
            sc.append(round(100 * net.score(state(v0, HAND, {**DRAW, **({x: DRAW.get(x, 0) + k} if k else {})})), 2))
            on.append(net.head_on)
        out["cards"][x] = {"score": sc, "head_on": on}
    for x in STRIKE_CARDS:
        if x not in net.known:
            continue
        d = []
        for k in STRIKES:
            draw = {**DRAW, **({"Strike": k} if k else {})}
            d.append(round(100 * (net.score(state(v0, {**HAND, x: HAND.get(x, 0) + 1}, draw))
                                  - net.score(state(v0, {**HAND, "Defend": HAND["Defend"] + 1}, draw))), 2))
        out["strike_cards"][x] = d
    out["head_width"] = net.model.head[0][-2].out_features  # the hooked layer: head[0]'s last ReLU
    return out


def corr_cols(a, b):
    """Correlation of every column of a with every column of b over rows
    (columns that never vary give 0)."""
    def z(m):
        s = m.std(0)
        return np.where(s > 1e-6, (m - m.mean(0)) / np.where(s > 1e-6, s, 1), 0)
    return z(a).T @ z(b) / len(a)


def snapshots(folder):
    """[(step, epoch, path)] in step order."""
    out = []
    for p in glob.glob(os.path.join(folder, "snap-*.pt")):
        m = re.match(r"snap-(\d+)-e(\d+)\.pt$", os.path.basename(p))
        if m:
            out.append((int(m.group(1)), int(m.group(2)), p))
    return sorted(out)


def r3(m):
    return np.round(np.asarray(m, np.float64), 3).tolist()


def report(args):
    main = Net(args.net)
    others = [Net(p) for p in args.compare]
    series = snapshots(args.series) if args.series else []
    snap_nets = [Net(p) for _, _, p in series]
    cards, owner = card_list([main] + others + snap_nets)
    M, ok = card_matrix(main, cards)
    keep = [i for i, k in enumerate(ok) if k]
    if len(keep) < len(cards):
        print(f"cards that didn't encode, left out: {[c for c, k in zip(cards, ok) if not k]}")
    cards, owner, M = [cards[i] for i in keep], [owner[i] for i in keep], M[keep]
    print(f"{len(cards)} cards, card width {M.shape[1]}")
    data = {"net": args.net, "cards": cards, "owner": owner, "card_acts": r3(M)}
    names, MM, counts = monster_matrix(main, args.fights)
    print(f"{len(names)} enemy kinds")
    data.update(enemies=names, enemy_counts=counts, enemy_acts=r3(MM))
    # An HP-histogram net's output is a histogram, not a score: no copies probe.
    data["copies"] = None if main.model.hp_loss else copies(main, args.encounter)
    data["encounter"] = args.encounter
    data["compare"] = []
    for o in others:
        Mo, _ = card_matrix(o, cards)
        C = corr_cols(M, Mo)
        best = C.argmax(1)
        data["compare"].append({"net": o.path, "best": best.tolist(), "corr": r3(C.max(1)),
                                "acts": r3(Mo[:, best].T)})
    if series:
        S = [card_matrix(n, cards)[0] for n in snap_nets]
        final = S[-1]
        data["series"] = {"steps": [s for s, _, _ in series], "epochs": [e for _, e, _ in series],
                          "acts": [r3(s.T) for s in S],
                          "settle": [r3(np.diag(corr_cols(s, final))) for s in S],
                          "final_path": series[-1][2]}
        if os.path.abspath(series[-1][2]) != os.path.abspath(args.net):
            print(f"note: the series ends at {series[-1][2]}, not the reported net; 'settle' compares to the series' end")
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "data.json"), "w") as f:
        json.dump(data, f)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "neurons.html"), encoding="utf-8") as f:
        page = f.read()
    with open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as f:
        f.write(page.replace("/*DATA*/null", json.dumps(data)))
    print(f"wrote {args.out}/index.html")


def game_states(n_games, seed=7):
    """Decision states of `n_games` greedy-played fights with varied decks
    and HP over every encounter group (selfplay.make_specs)."""
    import selfplay
    specs, _ = selfplay.make_specs(n_games // 15 + 1, seed, selfplay.varied_deck, hp_fn=selfplay.varied_hp)
    out = []
    for enc, deck, sd, hp in specs[:n_games]:
        c = sts.Combat([str(x) for x in deck], enc, seed=int(sd), hp=int(hp))
        for _ in range(300):
            if c.is_over():
                break
            if c.awaiting_action():
                out.append(c.clone())
            c.step(sts.greedy_action(c))
    return out


def dead_counts(net, states):
    """{layer: (units never above 0 before the activation, units)} over
    `states`, for every hidden layer (each Linear followed by an
    activation); the head's output layer is left out. Live monster slots
    only."""
    pre, hooks = {}, []
    m = net.model
    for name, mod in m.named_modules():
        if isinstance(mod, torch.nn.Linear) and not name.startswith("head.1"):
            hooks.append(mod.register_forward_hook(
                lambda mod, i, o, name=name: pre.__setitem__(name, torch.maximum(pre.get(name, o.new_full(o.shape[-1:], -1e9)), o.detach().reshape(-1, o.shape[-1]).max(0).values) if o.numel() else pre.get(name))))
    t = net.norm.tensors(net.feats.encode(states))
    alive = t["alive"]
    with torch.no_grad():
        m(t)
    for h in hooks:
        h.remove()
    # the monster layers saw dead slots too: redo them on live slots only
    live = t["monsters"][alive > 0]
    ent = torch.zeros(t["player"].shape[0] * sts.ENTITIES, m.row_width)
    psi = m.row(t["rows"]); on = t["row_entity"] >= 0
    ent.index_add_(0, t["row_entity"][on], psi[on])
    ent = ent.view(-1, sts.ENTITIES, m.row_width)[:, 1:1 + sts.MAX_MONSTERS][alive > 0]
    x = torch.cat([live, ent], 1)
    with torch.no_grad():
        for i, mod in enumerate(m.monster):
            x = mod(x)
            if isinstance(mod, torch.nn.Linear):
                pre[f"monster.{i}"] = x.max(0).values
    return {k: (int((v <= 0).sum()), int(v.numel())) for k, v in pre.items()}


def dead(args):
    states = game_states(args.games)
    print(f"{len(states)} decision states from {args.games} greedy fights")
    rows = {p: dead_counts(Net(p), states) for p in args.nets}
    layers = list(next(iter(rows.values())))
    print("net".ljust(52) + "".join(l.ljust(11) for l in layers))
    for p, r in rows.items():
        print(p[-52:].ljust(52) + "".join(f"{r[l][0]}/{r[l][1]}".ljust(11) for l in layers))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rows, f, indent=1)


def retrain(args):
    import learn
    import train
    import registry
    cfg = json.load(open(os.path.join(args.run, "config.json")))
    if args.fresh:
        # Round 0 of the run's config with n_train = --fresh games per group
        # (validation a fifth of it), played now under today's rules.
        cfg = {**cfg, "n_train": args.fresh, "n_val": max(1, args.fresh // 5)}
        parts, val, k = [(learn.dataset(cfg, "train"), 0)], [learn.dataset(cfg, "val")], 0
        samples = learn.d0_samples(cfg, 0, parts[0][0])
    else:
        ids = json.load(open(os.path.join(args.run, "run.json")))["datasets"]
        sets = {d: registry.load_manifest(d)["config"] for d in ids}
        val = [d for d in ids if sets[d].get("set") == "val"]
        parts = [(d, sets[d].get("round") or 0) for d in ids if sets[d].get("set") != "val"]
        if len(val) != 1:
            raise SystemExit(f"{args.run}: expected one validation dataset, found {val}")
        k = max(r for _, r in parts)
        d0 = [d for d, r in parts if r == 0]
        samples = learn.d0_samples(cfg, k, d0[0]) if d0 else {}
    mode = learn.feature_mode(cfg)
    print(f"parts {parts}, val {val[0]}, round {k}, samples {samples}, mode {mode}")
    train.THREADS = args.threads
    os.makedirs(args.out, exist_ok=True)
    meta = learn.net_meta(cfg, mode)
    last = {"epoch": -1}

    def snap(step, epoch, model, norm):
        if step & (step - 1) == 0 or epoch != last["epoch"]:
            stsnet.save(os.path.join(args.out, f"snap-{step:06d}-e{epoch}.pt"), model, norm, meta)
        last.update(epoch=epoch, step=step, norm=norm, state={k: v.clone() for k, v in model.state_dict().items()})

    # The seed learn's round loop gives round k (round 0 has its own key).
    seed = cfg.get("round0_seed", cfg.get("seed", 0)) if k == 0 else cfg.get("seed", 0)
    train_ds, _, _ = learn.training_set(cfg, parts, samples=samples, log=print)
    try:
        val_ds = learn.load_examples(cfg, val[0], None, log=print)
        model, norm, hist = train.train(mode, train_ds, val_ds, seed if args.seed is None else args.seed,
                                        print, None, rank_weight=learn.RANK_WEIGHT, hp_loss=learn.hp_loss(cfg),
                                        score_rule=learn.score_rule(cfg), snapshot=snap, act=args.act)
    finally:
        train_ds.close()
    end = stsnet.ValueNet(model.dims, width=model.width, row_width=model.row_width, hp_loss=model.hp_loss,
                          act=model.act)
    end.load_state_dict(last["state"])  # the last step's weights (model holds the best epoch's)
    stsnet.save(os.path.join(args.out, f"snap-{last['step']:06d}-e{last['epoch']}.pt"), end, last["norm"], meta)
    stsnet.save(os.path.join(args.out, "final.pt"), model, norm, {**meta, "val_mse": min(hist)})
    print(f"val MSE {min(hist):.4f}; snapshots in {args.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("net")
    r.add_argument("--series", help="a retrain folder of snap-*.pt")
    r.add_argument("--compare", nargs="*", default=[])
    r.add_argument("--encounter", default="gremlin_nob")
    r.add_argument("--fights", type=int, default=6)
    r.add_argument("--out", required=True)
    t = sub.add_parser("retrain")
    t.add_argument("run")
    t.add_argument("--out", required=True)
    t.add_argument("--threads", type=int, default=3)
    t.add_argument("--seed", type=int)
    t.add_argument("--act", default="relu", choices=sorted(stsnet.ACTS), help="a fresh net's hidden activation")
    t.add_argument("--fresh", type=int, help="play a new round-0 dataset of this many games per group instead "
                                             "(for runs whose data no longer replays)")
    d = sub.add_parser("dead")
    d.add_argument("nets", nargs="+")
    d.add_argument("--games", type=int, default=200)
    d.add_argument("--json")
    args = ap.parse_args()
    torch.set_num_threads(1)
    {"report": report, "retrain": retrain, "dead": dead}[args.cmd](args)


if __name__ == "__main__":
    main()
