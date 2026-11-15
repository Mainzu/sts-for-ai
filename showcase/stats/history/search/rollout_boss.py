# Rollout leaf (product policy, 16 vs 64 playouts per option) replaying the product's boss fights (11-02).
import json, sys
R = sys.argv[1] + "/results/rollout/"
for f in ["never129", "never129-n64", "cleared30", "cleared30-n64"]:
    d = json.load(open(R + f + ".json")); x = d["fights"]
    print(f, "n", d["settings"]["n"], "fights", len(x), "won", sum(a["won"] for a in x),
          "playouts/fight", round(sum(a["playouts"] for a in x) / len(x)), "s/fight", round(sum(a["seconds"] for a in x) / len(x), 1))
