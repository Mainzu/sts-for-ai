"""Does the value net misjudge states where the monster's hidden move pattern matters?

Labels: exact solver values from db/train.sqlite (read-only). For each sampled
state we measure how the monsters' NEXT intent (after this turn's move)
differs in damage from the CURRENT intent: decode the state with a few RNG
seeds, end the turn, read the new intents' damage, average. Then we compare
the net's error (prediction - exact value) and the heuristic's error between
states where the next move hits much harder ("up"), much softer ("down"), or
about the same ("same"), per encounter, with cluster-robust standard errors
(cluster = one fight: deck + monster max HPs, since the solver's states come
in subtrees of one fight).

Single-threaded, read-only. Usage:
    OMP_NUM_THREADS=1 RAYON_NUM_THREADS=1 .venv/Scripts/python.exe scripts/analysis/pattern_value_error.py
"""
import collections
import json
import os
import random
import re
import sqlite3
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("RAYON_NUM_THREADS", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
import torch

torch.set_num_threads(1)
import sts
import stsnet

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB = os.path.join(ROOT, "db", "train.sqlite")
NETS = {
    "champion r2 s1": "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt",
    "lean s1 r2": "runs/2026-10-30-lean-s1-r2-9952dd3/model.pt",
}
OUT = os.path.join(ROOT, "scripts", "analysis", "out")
CANDIDATES = int(os.environ.get("PATTERN_CANDIDATES", 200000))
PER_ENC = int(os.environ.get("PATTERN_PER_ENC", 500))
SEEDS = 4
UP, SAME = 6.0, 2.0  # next - current damage: >= UP "up", <= -UP "down", |d| <= SAME "same"
NAME_RE = re.compile(r"^\s+\[\d\] (.+?)  HP (\d+)/(\d+)")


def monsters_of(text):
    return [m.group(1) for m in (NAME_RE.match(l) for l in text.splitlines()) if m]


def base(name):
    return re.sub(r" \((S|M|L)\)$", "", name)


def end_action(c):
    for a in c.legal_actions():
        if a.is_end_turn:
            return a
    return None


INTENT_RE = re.compile(r"intent: (.+?)(?: \(|  \[|$)")
GAMES = ["2b0fc6fa6d56", "52043f3ad82a"]  # lean s101 round-2 self-play: neither net trained on them
GAMES_PER_ENC = {"slime_boss": 700, "gremlin_nob": 350, "lagavulin": 350, "three_sentries": 350}
STATES_PER_GAME = 3


def intents_of(text):
    return "/".join(m.group(1) for m in (INTENT_RE.search(l) for l in text.splitlines() if NAME_RE.match(l)) if m)


def sample_db(rng):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    max_id = con.execute("select max(id) from states").fetchone()[0]
    ids = sorted(rng.sample(range(1, max_id + 1), CANDIDATES))
    pool = collections.defaultdict(list)
    for k in range(0, len(ids), 900):
        chunk = ids[k:k + 900]
        q = f"select id, state, value, turns_left from states where id in ({','.join(map(str, chunk))})"
        for sid, blob, value, tl in con.execute(q):
            c = sts.Combat.decode(blob, 0)
            if not c.awaiting_action() or c.is_over() or end_action(c) is None:
                continue
            names = monsters_of(c.render())
            if not names:
                continue
            enc = "+".join(sorted(set(base(n) for n in names)))
            pool[enc].append((sid, bytes(blob), value, tl, None))
    print(f"pass 1: {sum(map(len, pool.values()))} decision states in {len(pool)} monster sets", flush=True)
    sample = []
    for enc, rows in sorted(pool.items()):
        rng.shuffle(rows)
        sample += [(enc, *r) for r in rows[:PER_ENC]]
    return sample


def sample_games(rng):
    """Main (non-branch) self-play games; label = the game's real final score.
    Cluster = the game."""
    import gzip
    import action_text
    by_enc = collections.defaultdict(list)
    for ds in GAMES:
        with gzip.open(os.path.join(ROOT, "datasets", ds, "games.jsonl.gz"), "rt", encoding="utf-8") as fh:
            for line in fh:
                g = json.loads(line)
                if "branch_at" in g or g.get("no_death"):
                    continue
                by_enc[g["encounter"]].append(g)
    sample = []
    gid = 0
    for enc, games in sorted(by_enc.items()):
        rng.shuffle(games)
        for g in games[:GAMES_PER_ENC.get(enc, 150)]:
            gid += 1
            c = action_text.combat_of(g)
            states = []
            for a in g["actions"]:
                if c.awaiting_action() and end_action(c) is not None:
                    states.append(bytes(c.encode()))
                c.step(action_text.decode_action(a))
            for blob in rng.sample(states, min(STATES_PER_GAME, len(states))):
                sample.append((enc, gid, blob, g["outcome"]["score"], -1, gid))
    print(f"games: {gid} games, {len(sample)} states", flush=True)
    return sample


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else "db"
    t0 = time.time()
    rng = random.Random(7)
    feats = sts.Features("effects")
    mcols = feats.monster_names
    i_dmg, i_alive, i_max = mcols.index("intent_damage"), mcols.index("alive"), mcols.index("max_hp")
    sample = sample_db(rng) if source == "db" else sample_games(rng)
    print(f"sample: {len(sample)} states, {time.time() - t0:.0f}s", flush=True)

    # Pass 2: current vs next intent damage, fight cluster key.
    recs = []
    for enc, sid, blob, value, tl, cluster in sample:
        c = sts.Combat.decode(blob, 0)
        text = c.render()
        b = feats.encode([c], True)
        mon = b["monsters"][0]
        alive = mon[:, i_alive] > 0
        cur = float(mon[alive, i_dmg].sum())
        nexts, nxt_int = [], ""
        for seed in range(1, SEEDS + 1):
            d = sts.Combat.decode(blob, seed)
            d.step(end_action(d))
            while not d.is_over() and not d.awaiting_action():
                d.advance()
            if d.is_over():
                continue
            if not nxt_int:
                nxt_int = intents_of(d.render())
            m2 = feats.encode([d], False)["monsters"][0]
            nexts.append(float(m2[m2[:, i_alive] > 0, i_dmg].sum()))
        if not nexts:
            continue
        nxt = float(np.mean(nexts))
        piles = c.piles()
        deck = collections.Counter()
        for p in piles.values():
            deck.update(p)
        key = (tuple(sorted(deck.items())), tuple(sorted(mon[:, i_max].astype(int).tolist())))
        recs.append(dict(enc=enc, sid=sid, label=value, tl=tl, cur=cur, nxt=nxt, delta=nxt - cur,
                         heur=float(b["heuristic"][0]), hp=float(b["hp"][0]), cluster=hash(key) if cluster is None else cluster, blob=blob,
                         intent=intents_of(text), next_intent=nxt_int))
    print(f"pass 2: {len(recs)} states with a next intent, {time.time() - t0:.0f}s", flush=True)

    # Pass 3: net predictions.
    for tag, path in NETS.items():
        model, norm, meta = stsnet.load(os.path.join(ROOT, path))
        f = stsnet.features_for(meta)
        ev = stsnet.Evaluator(model, norm)
        for k in range(0, len(recs), 256):
            part = recs[k:k + 256]
            combats = [sts.Combat.decode(r["blob"], 0) for r in part]
            preds = ev(f.encode(combats, model.hp_loss))
            for r, p in zip(part, preds):
                r[tag] = float(p)
    print(f"pass 3: nets done, {time.time() - t0:.0f}s", flush=True)

    for r in recs:
        d = r["delta"]
        r["group"] = "up" if d >= UP else "down" if d <= -UP else "same" if abs(d) <= SAME else "mid"
    report(recs, list(NETS) + ["heuristic"], t0, source)


def cl_mean(x, clusters):
    """Mean and cluster-robust se (clusters = fights)."""
    x = np.asarray(x, float)
    n = len(x)
    if n == 0:
        return float("nan"), float("nan"), 0, 0
    m = x.mean()
    by = collections.defaultdict(float)
    for v, c in zip(x - m, clusters):
        by[c] += v
    g = len(by)
    se = np.sqrt(sum(s * s for s in by.values())) / n * (np.sqrt(g / (g - 1)) if g > 1 else float("nan"))
    return m, se, n, g


def cl_diff(a, ca, b, cb):
    """Difference of two cluster means with a conservative se (groups treated
    as independent, which overstates the se when they share fights)."""
    ma, sa, na, _ = cl_mean(a, ca)
    mb, sb, nb, _ = cl_mean(b, cb)
    return ma - mb, float(np.hypot(sa, sb)), na, nb


def report(recs, preds, t0, source):
    lines = []
    say = lambda s="": (print(s), lines.append(s))
    if source == "db":
        say(f"pattern_value_error: {len(recs)} exact-labelled decision states from db/train.sqlite "
            f"(rules version 1), next-intent damage over {SEEDS} RNG seeds")
    else:
        say(f"pattern_value_error: {len(recs)} decision states from main self-play games {GAMES}, "
            f"label = the game's real final score (noisy), next-intent damage over {SEEDS} RNG seeds")
    say(f"groups by next - current intent damage: up >= +{UP}, down <= -{UP}, same |d| <= {SAME}, mid otherwise")
    say("err = prediction - label (exact value for db, real final score for games; score units 0..2; + = too optimistic). se is cluster-robust by fight.")
    say()
    err = {p: np.array([r[p if p != "heuristic" else "heur"] - r["label"] for r in recs]) for p in preds}
    groups = np.array([r["group"] for r in recs])
    cl = np.array([r["cluster"] for r in recs])
    encs = sorted(set(r["enc"] for r in recs))
    out = {"n": len(recs), "rows": []}
    for p in preds:
        say(f"== {p}")
        say(f"{'monsters':34s} {'grp':5s} {'n':>5s} {'fights':>6s} {'bias':>8s} {'se':>6s} {'|err|':>7s} {'se':>6s}")
        for enc in encs + ["ALL"]:
            sel_e = np.array([enc == "ALL" or r["enc"] == enc for r in recs])
            for g in ("up", "same", "down", "mid"):
                s = sel_e & (groups == g)
                if s.sum() < 15:
                    continue
                m, se, n, k = cl_mean(err[p][s], cl[s])
                am, ase, _, _ = cl_mean(np.abs(err[p][s]), cl[s])
                say(f"{enc[:34]:34s} {g:5s} {n:5d} {k:6d} {m:+8.3f} {se:6.3f} {am:7.3f} {ase:6.3f}")
                out["rows"].append(dict(pred=p, enc=enc, group=g, n=n, fights=k, bias=m, se=se, abs=am, abs_se=ase))
            su, ss = sel_e & (groups == "up"), sel_e & (groups == "same")
            if su.sum() >= 15 and ss.sum() >= 15:
                d, dse, _, _ = cl_diff(err[p][su], cl[su], err[p][ss], cl[ss])
                say(f"{'':34s} up-same bias diff {d:+.3f} (se {dse:.3f})")
                out["rows"].append(dict(pred=p, enc=enc, group="up-same", bias=d, se=dse))
        say()
    # The net against the heuristic on the same states: does the net's error
    # in "up" states exceed the heuristic's (which sees 4 moves ahead)?
    say("== net minus heuristic, per state |err| difference (negative = net closer)")
    for p in preds[:-1]:
        for g in ("up", "same", "down"):
            s = groups == g
            m, se, n, k = cl_mean(np.abs(err[p][s]) - np.abs(err["heuristic"][s]), cl[s])
            say(f"{p:16s} {g:5s} n={n:5d} fights={k:5d} {m:+.3f} (se {se:.3f})")
    say()
    # Within-group regression check: does the net's error grow with delta?
    say("== slope of net error on (next - current damage), per 10 damage, all states")
    d = np.array([r["delta"] for r in recs])
    for p in preds:
        X = np.c_[np.ones_like(d), d / 10]
        beta, *_ = np.linalg.lstsq(X, err[p], rcond=None)
        res = err[p] - X @ beta
        bread = np.linalg.inv(X.T @ X)
        meat = np.zeros((2, 2))
        for c in set(cl):
            sc = X[cl == c].T @ res[cl == c]
            meat += np.outer(sc, sc)
        se = np.sqrt(np.diag(bread @ meat @ bread))
        say(f"{p:16s} slope {beta[1]:+.4f} (se {se[1]:.4f})")
        out[f"slope {p}"] = [float(beta[1]), float(se[1])]
    say()
    # Per current -> next intent for the elites, the boss and Cultist.
    say("== by current intent -> next intent (n >= 20): elites, boss, Cultist; bias (se)")
    focus = ("slime_boss", "gremlin_nob", "lagavulin", "three_sentries", "cultist",
             "Slime Boss", "Gremlin Nob", "Lagavulin", "Sentry", "Cultist")
    keys = collections.defaultdict(list)
    for i, r in enumerate(recs):
        if any(w in r["enc"] for w in focus):
            keys[(r["enc"], r["intent"], r["next_intent"])].append(i)
    say(f"{'monsters':16s} {'intent -> next':52s} {'n':>4s} {'dmg now':>7s} {'next':>5s} "
        + " ".join(f"{p[:16]:>16s}" for p in preds))
    for (enc, a, b), ix in sorted(keys.items()):
        if len(ix) < 20:
            continue
        ix = np.array(ix)
        cells = []
        for p in preds:
            m, se, _, _ = cl_mean(err[p][ix], cl[ix])
            cells.append(f"{m:+8.3f} ({se:.3f})")
            out["rows"].append(dict(pred=p, enc=enc, intent=a, next=b, n=len(ix), bias=m, se=se))
        cur = np.mean([recs[i]["cur"] for i in ix])
        nx = np.mean([recs[i]["nxt"] for i in ix])
        say(f"{enc[:16]:16s} {(a + ' -> ' + b)[:52]:52s} {len(ix):4d} {cur:7.1f} {nx:5.1f} " + " ".join(cells))
    say()
    say(f"group sizes: {collections.Counter(groups.tolist())}")
    say(f"elapsed {time.time() - t0:.0f}s")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f"pattern_value_error_{source}.txt"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(os.path.join(OUT, f"pattern_value_error_{source}.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=float)
    with open(os.path.join(OUT, f"pattern_value_error_{source}_states.jsonl"), "w") as fh:
        for r in recs:
            fh.write(json.dumps({k: v for k, v in r.items() if k != "blob"}, default=float) + "\n")


if __name__ == "__main__":
    main()
