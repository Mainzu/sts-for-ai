"""Product registry (docs/specs/kb-adoption.md): `configs/product.json` names
the product player, the decision that made it the product, its control
files, and the players before it. Promote only through `set`, which also
records the kb fact `product/net`.

    python scripts/product.py show
    python scripts/product.py player
    python scripts/product.py set "<net>@<price>" --flags "--two-turn" \\
        --decision "<docs/decisions.md entry heading>" [--headline F] [--one-turn F]

`results/ladder/champion.json` is the tight2 ladder's state, not the product.
"""

import argparse
import datetime
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
REGISTRY = os.path.join(ROOT, "configs", "product.json")
DECISIONS = os.path.join(ROOT, "docs", "decisions.md")
def find_kb():
    """kb.py: $KB_PY, else the skills folder, else the newest installed kb plugin."""
    if os.environ.get("KB_PY"):
        return os.environ["KB_PY"]
    home = os.path.expanduser("~")
    path = os.path.join(home, ".claude", "skills", "kb", "kb.py")
    if os.path.exists(path):
        return path
    found = glob.glob(os.path.join(home, ".claude", "plugins", "cache", "mainzu", "kb", "*", "skills", "kb", "kb.py"))
    return max(found, key=os.path.getmtime) if found else path


KB = find_kb()


def load(path=REGISTRY):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def player_string(entry):
    return " ".join(p for p in (entry["player"], entry.get("flags", "")) if p)


def has_heading(heading, decisions=DECISIONS):
    with open(decisions, encoding="utf-8") as f:
        return any(line.rstrip() == "## " + heading for line in f)


def promote(player, flags, decision, headline=None, one_turn=None, path=REGISTRY,
            decisions=DECISIONS, today=None):
    """Write the new product; the current one moves to `previous`."""
    if not has_heading(decision, decisions):
        raise SystemExit(f"product: no decisions entry headed '## {decision}'")
    reg = load(path)
    today = today or datetime.date.today().isoformat()
    old = {k: reg[k] for k in ("player", "flags", "since", "decision") if k in reg}
    reg["previous"] = [dict(old, until=today)] + reg.get("previous", [])
    reg.update(player=player, flags=flags, since=today, decision=decision)
    if headline:
        reg["headline_control"] = headline
    if one_turn:
        reg["one_turn_control"] = one_turn
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(reg, f, indent=1)
        f.write("\n")
    return reg


def kb_command(reg):
    rel = os.path.relpath(REGISTRY, ROOT).replace("\\", "/")
    return [sys.executable, "-I", KB, "set", "product/net", f"Product player: {player_string(reg)}.",
            "--from", rel, f"docs/decisions.md#{reg['decision']}", "--pin",
            "--check", "python scripts/product.py player", "--expect", player_string(reg)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("show")
    sub.add_parser("player")
    s = sub.add_parser("set")
    s.add_argument("player")
    s.add_argument("--flags", default="")
    s.add_argument("--decision", required=True)
    s.add_argument("--headline")
    s.add_argument("--one-turn")
    args = ap.parse_args()
    if args.action == "show":
        print(json.dumps(load(), indent=1))
    elif args.action == "player":
        print(player_string(load()))
    else:
        reg = promote(args.player, args.flags, args.decision, args.headline, args.one_turn)
        cmd = kb_command(reg)
        if os.path.exists(KB):
            sys.exit(subprocess.run(cmd, cwd=ROOT).returncode)
        print("kb not found; record the fact with:\n  " + subprocess.list2cmdline(cmd[1:]))


if __name__ == "__main__":
    main()
