import sys, statistics as st, collections
sys.path.insert(0, "scripts")
import real_game_report as R
runs = R.all_runs()
print("runs", len(runs))
by = collections.defaultdict(list); byv = collections.defaultdict(lambda: collections.defaultdict(list))
asc = collections.Counter(); n=0; hand=0; noend=0
for i, r in enumerate(runs, 1):
    a = R.asc(r); asc[(a, i>=28)] += 1
    if a != 20: continue
    for f in r["fights"]:
        n += 1
        k = " + ".join(sorted(f["monsters"]))
        lost = f["hp_start"] - f["hp_end"]
        by[k].append(lost); byv[k][r["run_rules"]].append(lost)
        if f.get("handed_over"): hand += 1
print(asc, "A20 fights", n, "handed", hand)
for k, v in sorted(by.items(), key=lambda kv: -st.mean(kv[1])):
    if len(v) >= 5:
        print(f"{k:45s} n={len(v):3d} mean={st.mean(v):5.1f} med={st.median(v):5.1f} min={min(v)} max={max(v)}", {rr: round(st.mean(x),1) for rr, x in sorted(byv[k].items())})
