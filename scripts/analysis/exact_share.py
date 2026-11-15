"""Question B of the 2026-10-30 big-picture review: in each round of the
2026-10-28 night (score+branch s0 and s1), what share of the value labels
came from the exact solver, and what share of the round's wall time was the
solve step?

Data:
- runs/<run>/round.json "rungs": examples per label rung in the round's
  training set (learn.rung_counts): "exact" = self-play examples found in the
  solved-position database (rung 1), "exact_drawn" = database decision states
  drawn as extra examples (learn.exact_examples), "search" = rung 3,
  "outcome" = rung 5, "ranking_only" = weight-0 examples (no value label).
- Value-loss weight: self-play examples with a value label weigh 1
  (ds.weight = played); the drawn exact decisions are weighted so they make
  up `exact_share` (0.2) of the total (learn.exact_examples), so the exact
  weight share is 0.2 + 0.8 x exact / (exact + search + outcome) (a lower
  bound: bounded options in the draw also carry weight; none in rung counts
  can be told apart).
- Logs: logs/night.log (s0 rounds 1-5; crashed in round 6's solve) and
  logs/night2.log (restart: s0 rounds 6-10, s1 rounds 1-10). Component times
  from "dataset ... Ns", "solve step ... Ns", "cache ... done in", "effects
  epoch ... (Ns)", "tight fights ... done in".
- Round wall time: round.json mtime of round k minus that of round k-1 (the
  run's previous round). s0 round 6's start is night2's start, taken as s1
  round 1's start minus the logged s0 total (93.7 min); s1 round 1 starts at
  s0 round 10's round.json mtime (s1 started right after s0 finished).

    .venv/Scripts/python scripts/analysis/exact_share.py
"""

import glob
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SHARE = 0.2  # the night's exact_share (config.json)


def mmss(s):
    m, s = re.match(r"(\d+)m(\d+)s", s).groups()
    return int(m) * 60 + int(s)


def parse_log(path):
    """{(run, round): {component: seconds}} from a sweep log."""
    out, run, cur = {}, None, None
    pend = {}  # components seen before the round's "run ..." line
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        m = re.match(r"started (\S+)", line)
        if m:
            run, pend = m.group(1), {}
            continue
        m = re.match(r"dataset (\w+) \(train, round (\d+)\): \d+ games, (\d+)s", line)
        if m:
            pend["selfplay"] = pend.get("selfplay", 0) + int(m.group(3))
            continue
        m = re.match(r"solve step (\w+) \(round (\d+)\): (\d+) games, (\d+) puzzles, (\d+) rows, (\d+)s", line)
        if m:
            pend["solve"] = int(m.group(6))
            pend["solve_ds"] = m.group(1)
            pend["puzzles"] = int(m.group(4))
            pend["db_rows"] = int(m.group(5))
            continue
        m = re.match(r"\s+cache \w+: \d+/\d+ done in (\S+)", line)
        if m:
            pend["cache"] = pend.get("cache", 0) + mmss(m.group(1))
            continue
        m = re.match(r"\s+effects epoch \d+: val MSE [\d.]+ \((\d+)s\)", line)
        if m:
            pend["train"] = pend.get("train", 0) + int(m.group(1))
            continue
        m = re.match(r"run \S+-r(\d+)-\w+: val MSE", line)
        if m:
            cur = (run, int(m.group(1)))
            out[cur] = pend
            pend = {}
            continue
        m = re.match(r"\s+tight fights.*done in (\S+)", line)
        if m and cur is not None:
            out[cur]["eval"] = out[cur].get("eval", 0) + mmss(m.group(1))
            continue
        m = re.match(r"\s+solve (\w+): (\d+)/(\d+) \(\d+%\), (\S+),", line)
        if m:
            pend["solve_partial"] = mmss(m.group(4))  # last progress line (crash)
    return out, pend


def main():
    runs = {}
    for d in sorted(glob.glob(os.path.join(ROOT, "runs", "2026-10-2[78]-score+branch-s*"))):
        m = re.search(r"score\+branch-(s\d)-r(\d+)-", d)
        rnd = json.load(open(os.path.join(d, "round.json"), encoding="utf-8"))
        runs[("score+branch-" + m.group(1), int(m.group(2)))] = {
            "dir": os.path.basename(d), "rungs": rnd["rungs"],
            "end": os.path.getmtime(os.path.join(d, "round.json")), "round0_in": rnd["window"]["round0_in"]}
    log1, crash = parse_log(os.path.join(ROOT, "logs", "night.log"))
    log2, _ = parse_log(os.path.join(ROOT, "logs", "night2.log"))
    s0_total = float(re.search(r"score\+branch-s0: run \S+, ([\d.]+) min",
                               open(os.path.join(ROOT, "logs", "night2.log"), encoding="utf-8").read()).group(1))
    night2_start = runs[("score+branch-s0", 10)]["end"] - s0_total * 60

    rows = []
    for key in sorted(runs, key=lambda k: (k[0], k[1])):
        run, r = key
        if r == 0:
            continue
        info = runs[key]
        comp = log2.get(key) or log1.get(key)
        src = "night2.log" if key in log2 else ("night.log" if key in log1 else None)
        if run.endswith("s0") and r == 6:
            start = night2_start
        elif run.endswith("s1") and r == 1:
            start = runs[("score+branch-s0", 10)]["end"]
        else:
            start = runs[(run, r - 1)]["end"]
        wall = info["end"] - start
        g = info["rungs"]
        w_self = g["exact"] + g["search"] + g["outcome"]
        valued = w_self + g["exact_drawn"]
        row = {
            "run": run, "round": r, "dir": info["dir"], "log": src, "round0_in": info["round0_in"],
            **{k: g[k] for k in ("exact", "exact_drawn", "search", "outcome", "ranking_only")},
            "value_labels": valued,
            "exact_count_share": (g["exact"] + g["exact_drawn"]) / valued,
            "exact_hit_share": g["exact"] / w_self,
            "exact_weight_share": SHARE + (1 - SHARE) * g["exact"] / w_self,
            "wall_s": wall, "start": datetime.fromtimestamp(start).isoformat(timespec="seconds"),
            "end": datetime.fromtimestamp(info["end"]).isoformat(timespec="seconds"),
            **({k: comp.get(k) for k in ("selfplay", "solve", "cache", "train", "eval", "puzzles", "db_rows")}
               if comp else {}),
        }
        if comp and comp.get("solve"):
            row["solve_share_wall"] = comp["solve"] / wall
            logged = sum(comp.get(k, 0) for k in ("selfplay", "solve", "cache", "train", "eval"))
            row["logged_s"] = logged
            row["solve_share_logged"] = comp["solve"] / logged
        rows.append(row)

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "exact_share.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "night_crash": crash, "night2_start":
                   datetime.fromtimestamp(night2_start).isoformat(timespec="seconds")}, f, indent=1)

    hdr = (f"{'run':16} {'r':>2} {'r0':>3} {'valued':>7} {'exact':>5} {'drawn':>5} {'cnt%':>5} {'hit%':>5} {'wt%':>5} "
           f"{'wall':>6} {'solve':>5} {'sol%':>5} {'self':>4} {'train':>5} {'cache':>5} {'eval':>4} {'unlog':>5}")
    print(hdr)
    for x in rows:
        unl = x["wall_s"] - x.get("logged_s", 0)
        print(f"{x['run']:16} {x['round']:>2} {'y' if x['round0_in'] else 'n':>3} {x['value_labels']:>7} {x['exact']:>5} "
              f"{x['exact_drawn']:>5} {100 * x['exact_count_share']:5.1f} {100 * x['exact_hit_share']:5.2f} "
              f"{100 * x['exact_weight_share']:5.1f} {x['wall_s']:6.0f} {x.get('solve') or 0:5d} "
              f"{100 * x.get('solve_share_wall', 0):5.1f} {x.get('selfplay') or 0:4d} {x.get('train') or 0:5d} "
              f"{x.get('cache') or 0:5d} {x.get('eval') or 0:4d} {unl:5.0f}")
    print("columns: valued = value labels; cnt% = (exact+drawn)/valued; hit% = exact/(self-play valued);"
          " wt% = exact share of value-loss weight (0.2 + 0.8 hit, lower bound); wall = round seconds"
          " (round.json mtimes); sol% = solve/wall; unlog = wall minus logged components")

    # Summary over rounds of the 10-28 night with a logged solve step.
    import statistics as st
    sel = [x for x in rows if x.get("solve") and x["dir"].startswith("2026-10-28")]
    def summ(name, vals):
        vals = sorted(vals)
        print(f"{name}: n={len(vals)} mean {st.mean(vals):.4f} median {st.median(vals):.4f} "
              f"min {vals[0]:.4f} max {vals[-1]:.4f}")
    print("\n2026-10-28 rounds (s0 r5-r10 and s1 r1-r10, solve logged):")
    summ("exact count share", [x["exact_count_share"] for x in sel])
    summ("exact hit share (self-play)", [x["exact_hit_share"] for x in sel])
    summ("exact weight share", [x["exact_weight_share"] for x in sel])
    summ("solve share of wall", [x["solve_share_wall"] for x in sel])
    tot_solve = sum(x["solve"] for x in sel)
    tot_wall = sum(x["wall_s"] for x in sel)
    print(f"pooled: solve {tot_solve} s of {tot_wall:.0f} s wall = {tot_solve / tot_wall:.3f}")
    allr = [x for x in rows if x.get("solve")]
    tot_solve = sum(x["solve"] for x in allr)
    tot_wall = sum(x["wall_s"] for x in allr)
    print(f"all logged rounds incl. 10-27 s0 r1-r4 (n={len(allr)}): solve {tot_solve} s of {tot_wall:.0f} s = "
          f"{tot_solve / tot_wall:.3f}")
    print(f"night.log crash: partial solve progress {crash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
