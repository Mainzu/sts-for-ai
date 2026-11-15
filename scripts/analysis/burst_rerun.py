"""Fine-tune bursts from one parent, then play and read them on a bench (one job, so the read never starts early).

Usage: burst_rerun.py --from <model.pt> --configs a.json b.json --name <burst name> [--compare burst8]
"""
import argparse
import glob
import json
import subprocess
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--from", dest="parent", required=True)
ap.add_argument("--configs", nargs="+", required=True)
ap.add_argument("--name", required=True)
ap.add_argument("--compare", nargs="*", default=[])
ap.add_argument("--bench", default="data/bench/gen_powers12c3.json")
ap.add_argument("--threads", default="4")
args = ap.parse_args()
py = sys.executable
for c in args.configs:
    with open(c, encoding="utf-8") as f:
        assert json.load(f)["name"].startswith(args.name + "-"), c
    subprocess.run([py, "-u", "scripts/finetune.py", "--from", args.parent, "--config", c], check=True)
runs = sorted(glob.glob(f"runs/2026-1*-{args.name}-s*"))
print("runs:", runs, flush=True)
subprocess.run([py, "-u", "scripts/analysis/gen_powers_read.py", "play", "--bench", args.bench,
                "--threads", args.threads, "--nets", *runs], check=True)
subprocess.run([py, "-u", "scripts/analysis/gen_powers_read.py", "burst", "--bench", args.bench,
                "--arms", args.name, *args.compare, "--out", f"results/gen_powers/{args.name}.json"], check=True)
