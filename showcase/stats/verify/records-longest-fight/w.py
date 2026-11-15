import sys, os, json
REPO = "."
sys.path.insert(0, REPO + "/scripts")
import real_game_report as R
runs = R.all_runs(REPO + "/results/real-game")
want = {83: 5, 18: 2, 56: 14}
for n, fl in want.items():
    r = runs[n - 1]; seed = r["seed"]
    print("== run", n, r["folder"], R.setting_tag(r))
    p = os.path.join(REPO, "results/real-game", r["folder"], "states.jsonl")
    last = None
    with open(p, encoding="utf-8") as f:
        for l in f:
            g = json.loads(l)["msg"].get("game_state")
            if not g or g.get("seed") != seed or g.get("floor") != fl or "combat_state" not in g: continue
            c = g["combat_state"]
            key = (c["turn"], c["player"]["current_hp"], tuple((m["id"], m["current_hp"], m["block"], m["is_gone"]) for m in c["monsters"]))
            if key != last and (n != 56 or True):
                last = key
                if n == 56 or c["turn"] < 18 or c["turn"] > 78 or c["turn"] % 10 == 0: print(key)
    # decisions: split runs in the folder by floor drop
    p = os.path.join(REPO, "results/real-game", r["folder"], "decisions.jsonl")
    k, prev = -1, None
    idx = [i for i, x in enumerate(R.runs_of(os.path.join(REPO, "results/real-game", r["folder"]))) if x["seed"] == seed]
    print("index in folder", idx, [x["seed"] for x in R.runs_of(os.path.join(REPO, "results/real-game", r["folder"]))])
