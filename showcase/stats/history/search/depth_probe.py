# Elite depth probe: same elite fights replayed by 2-turn (k=4,16), 3-turn and rollout arms.
import json, sys
R = sys.argv[1] if len(sys.argv) > 1 else "results/depth_probe"
arms = {}
for n in ["two4-elite-all", "two16-elite-all", "three-elite-all", "rollout-elite", "rollout-elite-rest", "tiebreak-off", "tiebreak-on", "two-adapt-elite-all"]:
    try: d = json.load(open(f"{R}/{n}.json"))
    except Exception as e: print(n, "ERR", e); continue
    arms[n] = d
    f = d["fights"]
    key = lambda x: (x["i"], x["floor"], x["encounter"])
    won = sum(x["won"] for x in f); obs = sum(x["won_obs"] for x in f)
    secs = d["settings"].get("seconds")
    print(n, json.dumps({k: v for k, v in d["settings"].items() if k != "file"}), "n", len(f), "won", won, "obs", obs,
          "hp", round(sum(x["hp_end"] for x in f)/len(f), 1), "hp_obs", round(sum(x["hp_end_obs"] for x in f)/len(f), 1),
          "cut", sum(x.get("cut", 0) for x in f), "dec", sum(x["decisions"] for x in f), "s/fight", secs and round(secs/len(f), 2),
          "pl", sum(x.get("playouts", 0) for x in f), "rsec", round(sum(x.get("seconds", 0) for x in f), 1))
# three-turn arm on its 48 fights vs two16 on same fights
t = {(x["i"], x["floor"]): x for x in arms["three-elite-all"]["fights"]}
for a in ["two4-elite-all", "two16-elite-all"]:
    s = [x for x in arms[a]["fights"] if (x["i"], x["floor"]) in t]
    print("same48", a, len(s), sum(x["won"] for x in s), round(sum(x["hp_end"] for x in s)/len(s), 1))
