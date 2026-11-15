# Exact puzzles (10-26): heuristic's one-turn search vs exact solver values, by horizon, both halves pooled.
import json, sys
d = json.load(open(sys.argv[1] + "/results/exact-puzzles/heuristic.json"))
h = d["sets"]["puzzles"]["halves"]
for cell in ["h0", "h1", "h2+", "contested"]:
    n = sum(h[x]["counts"]["puzzles." + cell] for x in h)
    ok = sum(h[x]["counts"]["puzzles." + cell] * h[x]["metrics"]["accuracy." + cell][0] for x in h)
    reg = sum(h[x]["counts"]["puzzles." + cell] * h[x]["metrics"]["regret." + cell][0] for x in h) / n
    print(cell, n, round(ok), round(ok / n, 3), "regret", round(reg, 4))
print(d["sets"]["puzzles"]["settings"])
