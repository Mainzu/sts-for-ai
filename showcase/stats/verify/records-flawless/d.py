import sys,os
sys.path.insert(0,r"scripts")
os.chdir(r".")
import real_game_report as R
runs=R.all_runs()
for i in (31,60,86,64,87,65):
    r=runs[i-1]
    for f in r["fights"]:
        if f["decisions"]<=2: print(i,r["folder"],{k:f.get(k) for k in ("floor","group","hp_start","hp_end","hp_after","won","decisions","think_s","handed_over","predicted","matched")})
