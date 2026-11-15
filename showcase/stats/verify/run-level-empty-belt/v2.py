import sys
sys.path.insert(0, "scripts")
import real_game_report as R
runs = R.all_runs("results/real-game")
for i, r in enumerate(runs, 1):
    e = r["end"]
    if e is None or e.get("victory"): continue
    lost = [f for f in r["fights"] if not f["won"]]
    ho = [(f["floor"], f.get("handed_over")) for f in r["fights"] if f.get("handed_over")]
    print(i, R.asc(r), "lostfights", [(f["floor"], f["group"], f.get("handed_over")) for f in lost], "handed", ho[:4])
