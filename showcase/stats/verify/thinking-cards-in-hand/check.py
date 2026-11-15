import json, os, sys, collections, statistics
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as rg

runs = rg.all_runs()
print("runs", len(runs))
# run number per (folder, index within folder)
byfolder = collections.defaultdict(list)
for i, r in enumerate(runs, 1):
    byfolder[r["folder"]].append((i, r))

dec = []  # (runno, asc_run, asc_view, seconds, hand cards)
mismatch = 0
for folder, rr in byfolder.items():
    p = os.path.join(rg.RECORDS, folder, "decisions.jsonl")
    seg, prev = -1, None
    with open(p, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if prev is None or d["floor"] < prev:
                seg += 1
            prev = d["floor"]
            if "view" not in d:
                continue
            if seg >= len(rr):
                mismatch += 1; continue
            no, r = rr[seg]
            av = d["view"].get("ascension")
            dec.append((no, rg.asc(r), av, d["seconds"], d["view"].get("hand", {})))
print("unmapped", mismatch, "decisions", len(dec))
print("asc disagreements", sum(1 for x in dec if x[2] is not None and x[1] != x[2]))
for a in (0, 20):
    sub = [x for x in dec if x[1] == a]
    print("A%d n=%d mean=%.3f runs=%s..%s" % (a, len(sub), statistics.mean(x[3] for x in sub), min(x[0] for x in sub), max(x[0] for x in sub)))
def norm(c):
    c = c.replace("gen:", "")
    return c.split("{")[0].rstrip("+")
for a in (20, 0):
    sub = [x for x in dec if x[1] == a]
    acc = collections.defaultdict(lambda: [0, 0.0, set()])
    names = collections.defaultdict(set)
    for no, _, _, s, hand in sub:
        seen = set()
        for c in hand:
            n = norm(c); names[n].add(c)
            if n in seen: continue
            seen.add(n)
            acc[n][0] += 1; acc[n][1] += s; acc[n][2].add(no)
    print("--- A%d" % a)
    for n, (k, t, rs) in sorted(acc.items(), key=lambda kv: -kv[1][1] / kv[1][0]):
        if k >= 30 and len(rs) >= 4:
            print("%-18s %.2f n=%d runs=%d %s" % (n, t / k, k, len(rs), sorted(names[n])))
    if a == 20:
        print("raw-name sample", sorted({c for x in sub for c in x[4]})[:60])
