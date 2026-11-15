import json, sys, time, random
sys.path.insert(0, "scripts")
import bench
d = json.load(open("data/bench/tight2.json"))["halves"]["held_out"]
eb = [s for s in d if s["group"] in ("elite", "boss")]
random.Random(0).shuffle(eb)
sub = eb[:60]
for name, srch in (("one_k4", {"limit": bench.LIMIT, "sample_k": 4, "threads": 4}), ("two_k1", {"limit": bench.LIMIT, "turns": 2, "sample_k": 1, "threads": 4})):
    pass
for name, srch in (("one_k4", {"limit": bench.LIMIT, "sample_k": 4, "threads": 4}),
                   ("two_k1", {"limit": bench.LIMIT, "turns": 2, "sample_k": 1, "threads": 4})):
    t = time.time()
    res = bench.run_specs(sub, search=srch)
    dt = time.time() - t
    print(name, f"{dt:.1f}s", f"{dt/len(sub):.2f}s/fight", "won", sum(1 for r in res if r.get("won")), "keys", list(res[0].keys())[:8], flush=True)
