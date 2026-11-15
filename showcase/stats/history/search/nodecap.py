# Two-turn minus one-turn win rate, held-out elite+boss (1,336 paired fights), by node cap and evaluator (10-30..10-31).
import json, sys
R = sys.argv[1] + "/results/depth/"
for f in ["paired-held_out", "paired-held_out-cap400k", "paired-held_out-cap400k-fallback-m0", "paired-net-held_out", "paired-net-held_out-cap400k-fallback"]:
    d = json.load(open(R + f + ".json")); w = d["summary"]["all"]["won"]; c = d["cut_probe"]
    print(f, d["args"].get("evaluator", "heuristic"), d["two"]["max_nodes"], w["n"], "one", round(w["a"], 3), "two", round(w["b"], 3),
          "diff", round(w["diff"], 3), "se", round(w["se"], 3), "probe mean nodes", round(c["mean_nodes"]), "cut share", round(c["cut_share"], 3))
