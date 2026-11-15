import sys, os
sys.path.insert(0, "scripts")
import real_game_report as R
runs = R.all_runs("results/real-game")
print(len(runs))
def pots(gs):
    return [p.get("id") for p in gs.get("potions", []) if p.get("id") != "Potion Slot"]
for i, r in enumerate(runs, 1):
    last = r["last"]; e = r["end"]
    died = e is not None and not e.get("victory")
    print(i, R.asc(r), r["run_rules"], r["fight_guard"], "act", last.get("act"), "fl", last.get("floor"), "died" if died else ("stop" if R.stopped(r) else "other"),
          "screen", last.get("screen_type"), "pots", pots(last), "haspotkey", "potions" in last)
