"""One arm of the two-turn self-play round (docs/specs/two-turn-round.md):
fine-tune the parent net on a `source` config's games (two_turn_games), then
play the new net one turn deep on the cell gauntlet against a control file
under the gauntlet protocol. One job per arm, so the queue never needs the
run id in advance.

    python scripts/two_turn_round.py arm --config configs/twoturn-s1.json \\
        --from runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt \\
        --against results/gauntlet/net1029-hpb0.01.json --out results/gauntlet/twoturn-s1-hpb0.01.json \\
        [--threads 6] [--sequences 500] [--price @hpb0.01]

Prints the run id, the gauntlet file and the protocol verdict (`verdict at
n`, or `none` when the file holds no protocol). `--max-nodes` and `--root`
are for smoke runs: a smaller two-turn node cap (part of the games'
identity, not of the run's config) and another registry root.
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import finetune  # noqa: E402
import registry  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
PRICE = "@hpb0.01"  # the one-turn read's price: the one-turn controls' (fact yardstick/one-turn-controls)


def arm(cfg_path, parent, against, out, threads=6, sequences=500, price=PRICE, max_nodes=None,
        root=registry.ROOT, log=print):
    """Fine-tune, then the one-turn gauntlet read; returns (run id, verdict text)."""
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    run = finetune.finetune(parent, cfg, root=root, log=log, threads=threads, max_nodes=max_nodes)
    log(f"run {run.id}: {run.model_path}")
    player = run.model_path.replace("\\", "/") + price
    cmd = [sys.executable, "-u", os.path.join(ROOT, "scripts", "gauntlet.py"), "play", player, "--against", against,
           "--sequences", str(sequences), "--threads", str(threads), "--out", out]
    log("  " + " ".join(cmd[2:]))
    subprocess.run(cmd, cwd=ROOT, check=True)
    with open(out, encoding="utf-8") as f:
        body = json.load(f)
    p = body.get("protocol")
    verdict = f"{p['verdict']} at n {p['n']}" if p else "none"
    log(f"arm {cfg.get('name', cfg_path)}: run {run.id}, {out}: protocol {verdict}")
    return run.id, verdict


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("arm", help="fine-tune on the config's source games, then read one turn deep")
    a.add_argument("--config", required=True)
    a.add_argument("--from", dest="parent", required=True, help="the parent net (.pt)")
    a.add_argument("--against", required=True, help="control gauntlet file (same price, one turn, cells)")
    a.add_argument("--out", required=True, help="the arm's gauntlet file")
    a.add_argument("--threads", type=int, default=6)
    a.add_argument("--sequences", type=int, default=500)
    a.add_argument("--price", default=PRICE, help="search-time price appended to the new net for the read")
    a.add_argument("--max-nodes", type=int, default=None, help="smoke runs only: a smaller two-turn node cap")
    a.add_argument("--root", default=registry.ROOT, help="smoke runs only: another registry root")
    args = ap.parse_args(argv)
    arm(args.config, args.parent, args.against, args.out, args.threads, args.sequences, args.price,
        args.max_nodes, args.root)


if __name__ == "__main__":
    main()
