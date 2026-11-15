"""Boss replays swept by entry HP (docs/specs/boss-replay.md): rebuild each
boss fight of a headline gauntlet file (the deck the sequence brought, its
boss, its seed) and play it one turn deep at entry HP 30, 40, ..., 80 on
common seeds, so only HP varies. `read` gives the causal P(win | HP) per
boss and deck beside the observational curve (boss win by arrival HP),
which low arrival HP confounds with weaker decks.

    .venv/Scripts/python scripts/analysis/boss_replay.py play --file results/gauntlet/net1029-hpe0.01-two-starter-simboss.json \\
        --player runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpb0.01 --threads 3 [--limit 3]
    .venv/Scripts/python scripts/analysis/boss_replay.py read results/boss_replay/<out>.json
"""

import argparse
import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import gauntlet  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "results", "boss_replay")
HP = (30, 40, 50, 60, 70, 80)
PLAYER = "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpb0.01"
REFUSE = ("remove", "rest_choice", "elites")  # settings whose decks or fights the rebuild can't follow
BOSS_FLOOR = len(gauntlet.SHAPE) - 1


def rebuild(rows, settings, seqs):
    """(decks, skipped) of a gauntlet file's rows: one entry per row that
    holds all 11 floors, with the deck it brought to the boss (start deck
    plus every non-null `took`), its boss, arrival HP, outcome and boss
    seed; `seqs` = {i: sequence} from `gauntlet.sequences` (character and
    cell deck). Rows that died earlier are counted in `skipped`."""
    for k in REFUSE:
        if k in settings:
            raise SystemExit(f"the file's settings hold {k!r}: its decks or fights differ from this rebuild")
    out, skipped = [], 0
    for r in sorted(rows, key=lambda r: r["i"]):
        if len(r["floors"]) < len(gauntlet.SHAPE):
            skipped += 1
            continue
        s = seqs[r["i"]]
        if settings.get("start") == "starter":
            import sts
            deck = list(sts.starter_deck(s["character"]))
        else:
            deck = list(s["deck"])
        deck += [f["took"] for f in r["floors"] if f.get("took")]
        last = r["floors"][-1]
        out.append({"i": r["i"], "half": r["half"], "boss": last["encounter"], "character": s["character"],
                    "deck": deck, "hp_obs": last["hp_start"], "won_obs": bool(last["won"]),
                    "seed": gauntlet.SEED_BASE + r["i"] * 100 + BOSS_FLOOR})
    return out, skipped


def seed_of(row, j):
    """Replay seed j of a rebuilt row: the boss floor's own seed for j = 0,
    then seeds inside the sequence's 100-block above its 11 floor seeds."""
    return row["seed"] if j == 0 else row["seed"] - BOSS_FLOOR + len(gauntlet.SHAPE) + j


def specs_for(row, hps, seeds):
    """Play specs of one row: every HP level x seed index, seed shared across
    the HP levels of one index (common draws, only HP differs)."""
    return [{"encounter": row["boss"], "deck": list(row["deck"]), "seed": seed_of(row, j), "hp": int(hp),
             "character": row["character"], "group": "boss"} for hp in hps for j in range(seeds)]


def play_blocks(decks, hps, seeds, play, block=100):
    """Yields blocks of result rows {i, half, boss, deck, hp_obs, won_obs,
    won: {hp: [0/1 per seed]}}, one `play(specs)` call per block. `hps`
    "arrival" plays each deck at its own hp_obs (docs/specs/boss-replay-score.md):
    won {"arrival": [...]} and hp_end [per seed, 0 on a loss]."""
    arrival = hps == "arrival"
    for b in range(0, len(decks), block):
        chunk = decks[b:b + block]
        res = iter(play([s for d in chunk for s in specs_for(d, [d["hp_obs"]] if arrival else hps, seeds)]))
        rows = []
        for d in chunk:
            row = {k: d[k] for k in ("i", "half", "boss", "deck", "hp_obs", "won_obs")}
            if arrival:
                rs = [next(res) for _ in range(seeds)]
                row["won"] = {"arrival": [int(bool(r["won"])) for r in rs]}
                row["hp_end"] = [int(r["hp_end"]) if r["won"] else 0 for r in rs]
            else:
                row["won"] = {str(hp): [int(bool(next(res)["won"])) for _ in range(seeds)] for hp in hps}
            rows.append(row)
        yield rows


def load_done(out, settings):
    """{i: row} of an existing output file with the same settings; {} if
    none; refuses a file played under other settings."""
    if not os.path.exists(out):
        return {}
    with open(out, encoding="utf-8") as f:
        old = json.load(f)
    if old["settings"] != settings:
        raise SystemExit(f"{out} holds other settings; pass --out")
    return {r["i"]: r for r in old["rows"]}


def write(out, settings, skipped, rows):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"settings": settings, "skipped": skipped, "rows": rows}, f, indent=1)


def play_cmd(args):
    import ladder
    with open(args.file, encoding="utf-8") as f:
        src = json.load(f)
    hps = "arrival" if args.hp == "arrival" else [int(x) for x in args.hp.split(",")]
    settings = {"file": args.file, "player": args.player, "hp": hps, "seeds": args.seeds}
    stem = os.path.splitext(os.path.basename(args.file))[0]
    key = [hps, args.seeds] if hps == "arrival" else hps + [args.seeds]
    tag = gauntlet.tag(args.player, False) + "-" + hashlib.sha256(json.dumps(key).encode()).hexdigest()[:4]
    out = args.out or os.path.join(ROOT, f"{stem}-{tag}.json")
    done = load_done(out, settings)
    rows = src["sequences"]
    seqs = {s["i"]: s for s in gauntlet.sequences(max(r["i"] for r in rows) + 1, 0, ladder.pool_cells())}
    decks, skipped = rebuild(rows, src["settings"], seqs)
    if args.limit:
        decks = decks[:args.limit]
    todo = [d for d in decks if d["i"] not in done]
    print(f"{len(decks)} boss decks ({skipped} sequences died earlier), {len(todo)} to play, "
          f"{len(todo) * (1 if hps == 'arrival' else len(hps)) * args.seeds} fights", flush=True)
    for block in play_blocks(todo, hps, args.seeds, lambda specs: ladder.play_bench(specs, args.player, args.threads),
                             args.block):
        for r in block:
            done[r["i"]] = r
        write(out, settings, skipped, [done[d["i"]] for d in decks if d["i"] in done])
        print(f"{len(done)} / {len(decks)} decks played", flush=True)
    write(out, settings, skipped, [done[d["i"]] for d in decks if d["i"] in done])
    print(out)


def deck_curve(row, hps):
    return np.array([np.mean(row["won"][str(hp)]) for hp in hps], float)


def crossing(hps, p, level):
    """HP where the per-deck curve first reaches `level`, interpolated on the
    grid; the first grid HP if already there; None if never."""
    if p[0] >= level:
        return float(hps[0])
    for k in range(1, len(hps)):
        if p[k] >= level:
            return hps[k - 1] + (hps[k] - hps[k - 1]) * (level - p[k - 1]) / (p[k] - p[k - 1])
    return None


def step(row, hps):
    """(HP where the deck's win rate crosses 0.5, width from 0.25 to 0.75);
    None where it never gets there."""
    p = deck_curve(row, hps)
    lo, hi = crossing(hps, p, 0.25), crossing(hps, p, 0.75)
    return crossing(hps, p, 0.5), (hi - lo if lo is not None and hi is not None else None)


def causal(rows, hps):
    """{hp: (mean over decks of the deck's win rate, se over decks)}."""
    m = np.array([deck_curve(r, hps) for r in rows])
    return {hp: (float(m[:, k].mean()), float(m[:, k].std(ddof=1) / np.sqrt(len(m))) if len(m) > 1 else 0.0)
            for k, hp in enumerate(hps)}


def observational(rows):
    """{band: (win rate, n)} of boss-reaching gauntlet rows by 10-HP
    arrival band (hp_start // 10 * 10)."""
    by = {}
    for r in rows:
        if len(r["floors"]) < len(gauntlet.SHAPE):
            continue
        last = r["floors"][-1]
        by.setdefault(last["hp_start"] // 10 * 10, []).append(float(last["won"]))
    return {b: (float(np.mean(v)), len(v)) for b, v in sorted(by.items())}


def read_cmd(args):
    with open(args.out, encoding="utf-8") as f:
        d = json.load(f)
    hps, seeds, rows = d["settings"]["hp"], d["settings"]["seeds"], d["rows"]
    with open(d["settings"]["file"], encoding="utf-8") as f:
        src = {r["i"]: r for r in json.load(f)["sequences"]}
    print(f"{len(rows)} decks, {d['skipped']} sequences died before the boss; player {d['settings']['player']}, "
          f"{seeds} seeds x HP {hps}")
    bosses = sorted({r["boss"] for r in rows})
    for boss in ["all"] + bosses:
        sub = [r for r in rows if boss == "all" or r["boss"] == boss]
        obs = observational([src[r["i"]] for r in sub])
        cz = causal(sub, hps)
        print(f"\n{boss} ({len(sub)} decks)")
        print("  causal   " + "  ".join(f"{hp}: {m:.2f} ({se:.2f})" for hp, (m, se) in cz.items()))
        print("  observed " + "  ".join(f"{b}s: {p:.2f} (n {n})" for b, (p, n) in obs.items()))
        p40, p60 = cz.get(40, (None,))[0], cz.get(60, (None,))[0]
        o40, o60 = obs.get(40, (None,))[0], obs.get(60, (None,))[0]
        if None not in (p40, p60, o40, o60):
            print(f"  slope 40s -> 60s: observed {o60 - o40:+.2f}, causal {p60 - p40:+.2f}"
                  f" (causal share {(p60 - p40) / (o60 - o40):.2f})" if o60 != o40 else "")
        cross = [step(r, hps) for r in sub]
        xs = [c for c, _ in cross if c is not None]
        ws = [w for _, w in cross if w is not None]
        never = sum(c is None for c, _ in cross)
        q = lambda v: " / ".join(f"{x:.0f}" for x in np.percentile(v, [25, 50, 75])) if v else "-"  # noqa: E731
        sure = sum(np.mean(r["won"][str(hps[-1])]) >= 0.75 for r in sub)
        lost = sum(np.mean(r["won"][str(hps[0])]) <= 0.25 for r in sub)
        print(f"  per deck: crossing 0.5 at HP {q(xs)} (quartiles; {never} never), width 0.25->0.75 {q(ws)}; "
              f"sure at {hps[-1]}: {sure}, lost at {hps[0]}: {lost}")
        if len(sub) > 2:
            at60 = np.array([np.mean(r["won"][str(60)]) for r in sub]) if 60 in hps else None
            hp_obs = np.array([r["hp_obs"] for r in sub], float)
            if at60 is not None and at60.std() > 0 and hp_obs.std() > 0:
                print(f"  confound: corr(arrival HP, causal win at 60) = {np.corrcoef(hp_obs, at60)[0, 1]:+.2f}")


def pair_scores(ga, ra, gb, rb):
    """{name: (n, mean b - a, paired sd)} over the sequences both gauntlet row
    lists hold, for clears and end HP (the real run) and replay win and
    replay end HP (mean over an arrival-mode replay row's seeds, 0 for a
    sequence without one: it died before the boss)."""
    ga, gb = {r["i"]: r for r in ga}, {r["i"]: r for r in gb}
    ra, rb = {r["i"]: r for r in ra}, {r["i"]: r for r in rb}
    ids = sorted(set(ga) & set(gb))

    def score(g, rep, i):
        r, x = g[i], rep.get(i)
        return (float(r["cleared"]), float(r["floors"][-1]["hp_end"] if r["cleared"] else 0),
                float(np.mean(x["won"]["arrival"])) if x else 0.0, float(np.mean(x["hp_end"])) if x else 0.0)
    d = np.array([np.subtract(score(gb, rb, i), score(ga, ra, i)) for i in ids]).reshape(len(ids), 4)
    return {name: (len(ids), float(d[:, n].mean()), float(d[:, n].std(ddof=1)))
            for n, name in enumerate(("clears", "end_hp", "replay_win", "replay_hp"))}


def pair_cmd(args):
    files = []
    for path in (args.a, args.b):
        with open(path, encoding="utf-8") as f:
            rep = json.load(f)
        if rep["settings"]["hp"] != "arrival":
            raise SystemExit(f"{path} is an HP sweep; pair needs --hp arrival replays")
        with open(rep["settings"]["file"], encoding="utf-8") as f:
            files.append((json.load(f)["sequences"], rep["rows"]))
    got = pair_scores(files[0][0], files[0][1], files[1][0], files[1][1])
    for name, (n, mean, sd) in got.items():
        print(f"{name:10s} n {n}  mean b-a {mean:+.3f}  paired sd {sd:.3f}  se {sd / np.sqrt(n):.3f}")
    for real, rp in (("clears", "replay_win"), ("end_hp", "replay_hp")):
        print(f"sd {real} / sd {rp}: {got[real][2] / got[rp][2]:.2f}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("play")
    p.add_argument("--file", required=True, help="headline gauntlet file (starter start, no removal / rest / path)")
    p.add_argument("--player", default=PLAYER)
    p.add_argument("--hp", default=",".join(str(h) for h in HP),
                   help='entry HP levels, or "arrival": each deck at its own arrival HP')
    p.add_argument("--seeds", type=int, default=4)
    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--limit", type=int, default=0, help="first N decks only (smoke)")
    p.add_argument("--block", type=int, default=100, help="decks per play call; the file is written after each")
    p.add_argument("--out", default=None)
    r = sub.add_parser("read")
    r.add_argument("out")
    q = sub.add_parser("pair", help="paired sd of the replay score against real clears (docs/specs/boss-replay-score.md)")
    q.add_argument("a")
    q.add_argument("b")
    args = ap.parse_args(argv)
    {"play": play_cmd, "read": read_cmd, "pair": pair_cmd}[args.cmd](args)


if __name__ == "__main__":
    main()
