# Two-turn search (cap 400k, k 4, 10-29 net) on 20 fights: nodes per search by the decision's place in the turn (11-02),
# and the tree-reuse ("step") comparison (11-03).
import json, sys
R = sys.argv[1] + "/results/depth/"
d = json.load(open(R + "line-probe.json")); s = d["summary"]
print("searches", s["searches"], "turns", s["turns"], "first-decision share of nodes", round(s["index0_share"]["nodes"], 3))
for r in s["per_index"]: print(r["idx"] + 1, r["n"], round(r["nodes"]), round(r["leaves"]), round(r["ms"], 1))
c = json.load(open(R + "line-step-compare.json"))["summary"]
print("step compare", c["compared"], "identical", c["identical_share"], c["totals"]["nodes"], "ratio", round(c["ratio"]["nodes"], 3))
