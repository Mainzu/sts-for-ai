import sys,os
sys.path.insert(0, r"scripts")
os.chdir(r".")
import real_game_report as R
runs=R.all_runs()
for i in (8,16): r=runs[i-1]; print(i, r["folder"], R.ending(r), r["fights"][-1])
