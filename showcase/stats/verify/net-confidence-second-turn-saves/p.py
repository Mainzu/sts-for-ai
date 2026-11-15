import sys, os, json
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R
runs = R.all_runs()
r = runs[33]; print(r["folder"], R.setting_tag(r), [ (f["floor"],f["monsters"],f["hp_start"],f["hp_end"],f.get("hp_after"),f["won"]) for f in r["fights"] if f["floor"] in (13,14)])
with open(os.path.join(R.RECORDS, r["folder"], "decisions.jsonl"), encoding="utf-8") as f:
    for line in f:
        d=json.loads(line)
        if d.get("floor")==14 and "card_reward" not in d and d.get("turn")==1:
            print(d["view"]["player"]["potions"], d["view"]["player"]["relics"], d["options"], d["one"], d["two"], d["pick"], d.get("line")); break
