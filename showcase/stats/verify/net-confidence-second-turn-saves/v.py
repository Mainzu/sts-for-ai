import sys, os, json
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R
runs = R.all_runs()
print("runs", len(runs))
rows = []
cnt = {}; cutc = {}; multi = {}
for i, r in enumerate(runs, 1):
    r["num"] = i
byfolder = {}
for r in runs:
    byfolder.setdefault(r["folder"], []).append(r)
for folder, rs in byfolder.items():
    wf = [r for r in rs if r["fights"]]
    k, prev = -1, None
    with open(os.path.join(R.RECORDS, folder, "decisions.jsonl"), encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            d = json.loads(line)
            fl = d.get("floor")
            if prev is None or fl < prev: k += 1
            prev = fl
            if k >= len(wf): print("extra decisions", folder); continue
            r = wf[k]
            if "card_reward" in d: continue
            a = R.asc(r)
            if len(d["options"]) < 2: continue
            key = (a,)
            cnt[a] = cnt.get(a, 0) + 1
            if d.get("cut") or d.get("two") is None:
                cutc[a] = cutc.get(a, 0) + 1; continue
            two = d["two"]; one = d["one"]
            if two[d["pick"]] is None: cutc[a]=cutc.get(a,0)+1; continue
            v = two[d["pick"]] - max(x for x in one if x is not None)
            fight = next((x for x in r["fights"] if x["floor"] == fl), None)
            mons = [m["name"] for m in d["view"]["monsters"]]
            rows.append((a, v, r["num"], fl, d.get("turn"), d["view"]["player"]["hp"], mons, d["options"][d["pick"]], fight and fight["won"], fight and fight["hp_start"], fight and fight.get("hp_end"), fight and fight.get("hp_after"), max(one), two[d["pick"]], R.setting_tag(r)))
print("decisions >=2 opts", cnt, "cut", cutc)
for a in (0, 20):
    rs = [x for x in rows if x[0] == a]
    print("asc", a, "n", len(rs), "runs", min(x[2] for x in rs), max(x[2] for x in rs))
    rs.sort(key=lambda x: x[1])
    for x in rs[-5:][::-1] + rs[:5]: print(x)
