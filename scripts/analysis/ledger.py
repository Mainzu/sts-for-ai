"""The ledger (review 2026-11-06 direction 3; docs/specs/session-free-reads.md):
per recipe and net, the paired end-HP and clears edge against the 10-29 net
one turn deep on the same cell book (sequences 0-499 against
net1029-hpb0.01.json, 500-999 against net1029-hpb0.01-b500.json), its se over
sequences; per recipe the mean over its (net, book) files, the between-seed
sd of the nets' means, the seeds, and the thread-hours of the jobs that wrote
the files; and the two-turn read against the two-turn control where one
exists ("none" where not). A file under 500 sequences counts as missing.

    python scripts/analysis/ledger.py [--root <main checkout>] [--md]
"""
import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

from cards_by_half import GROUPS, STRATA_GROUPS, load, mean_se
from gauntlet_protocol import end_hp

SEQUENCES = 500
BOOKS = {"": "net1029-hpb0.01", "-b500": "net1029-hpb0.01-b500"}
TWO_TURN = ("a", "b", "c")  # cell books of the two-turn files, against net1029-hpe0.01-two-<x>
RECIPES = [g for g in GROUPS if g[0] != "product recipe"] + [STRATA_GROUPS[-1],
                                                             ("1029 seed twins", r"net1029(s101|s201)-hpb0\.01")]
RERANK = re.compile(r"rerank-(.+?)-s\d+-.*-hpb0\.01")


def edge(net, ref):
    """(HP edge, se over sequences, clears edge, n) over the sequences both hold."""
    ks = [k for k in net if k in ref]
    if not ks:
        return None
    hp = mean_se([end_hp(net[k]) - end_hp(ref[k]) for k in ks])
    cl = mean_se([float(net[k]["cleared"]) - float(ref[k]["cleared"]) for k in ks])
    return hp[0], hp[1], cl[0], len(ks)


def groups(names):
    """[(label, [net base names])]: the recipe groups, then any other rerank-* recipe."""
    out, seen = [], set()
    for label, pat in RECIPES:
        bases = sorted(n for n in names if re.fullmatch(pat, n))
        seen.update(bases)
        out.append((label, bases))
    other = {}
    for n in sorted(names):
        m = RERANK.fullmatch(n)
        if m and n not in seen:
            other.setdefault(m.group(1), []).append(n)
    return out + sorted(other.items())


def thread_hours(root):
    """{results/gauntlet/<file>.json: thread-hours} from the done job records' --out."""
    out = {}
    for p in (root / "jobs" / "done").glob("*.json"):
        if p.name.endswith(".check.json"):
            continue
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
            words = [w for a in j["cmd"] for w in a.split()]
            target = words[words.index("--out") + 1].replace("\\", "/")
            h = j["threads"] * (datetime.fromisoformat(j["ended"]) - datetime.fromisoformat(j["started"])).total_seconds() / 3600
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            continue
        out[Path(target).name] = out.get(Path(target).name, 0.0) + h
    return out


def ledger(root):
    """[(label, group dict, [net dict])]."""
    g = root / "results" / "gauntlet"
    names = {p.stem for p in g.glob("*.json")}
    ctl = {b: load(g / f"{f}.json") for b, f in BOOKS.items()}
    two_ctl = {x: load(g / f"net1029-hpe0.01-two-{x}.json") for x in TWO_TURN
               if (g / f"net1029-hpe0.01-two-{x}.json").exists()}
    th = thread_hours(root)
    rows = []
    for label, bases in groups(names):
        nets, files = [], []
        for base in bases:
            per = []
            for b in BOOKS:
                if base + b not in names:
                    continue
                recs = load(g / f"{base}{b}.json")
                if len(recs) < SEQUENCES:
                    continue
                e = edge(recs, ctl[b])
                per.append((b, e, th.get(f"{base}{b}.json", 0.0)))
            stem = base[:-len("-hpb0.01")]
            two = [edge(load(g / f"{stem}-hpe0.01-two-{x}.json"), two_ctl[x]) for x in two_ctl
                   if (g / f"{stem}-hpe0.01-two-{x}.json").exists()]
            if per:
                nets.append({"net": base, "books": ["500-999" if b else "0-499" for b, _, _ in per],
                             "hp": sum(e[0] for _, e, _ in per) / len(per),
                             "se": [e[1] for _, e, _ in per], "clears": sum(e[2] for _, e, _ in per) / len(per),
                             "thread_h": sum(h for _, _, h in per), "two": two})
                files += [e for _, e, _ in per]
        if not files:
            rows.append((label, None, nets))
            continue
        sd = (math.sqrt(sum((n["hp"] - sum(m["hp"] for m in nets) / len(nets)) ** 2 for n in nets) / (len(nets) - 1))
              if len(nets) > 1 else float("nan"))
        two = [e for n in nets for e in n["two"]]
        rows.append((label, {"hp": sum(e[0] for e in files) / len(files), "clears": sum(e[2] for e in files) / len(files),
                             "files": len(files), "seeds": len(nets), "sd_seeds": sd,
                             "se_seq": sum(e[1] for e in files) / len(files),
                             "thread_h": sum(n["thread_h"] for n in nets),
                             "two": (sum(e[0] for e in two) / len(two), sum(e[2] for e in two) / len(two), len(two))
                             if two else None}, nets))
    return rows


def print_md(rows, out=print):
    out("### Ledger: paired edge over the one-turn 10-29 net (@hpb0.01, cell books 0-499 and 500-999)\n")
    out("| recipe | seeds | (net, book) files | end-HP edge | se over sequences (mean) | sd between seeds | "
        "clears edge | thread-h | two-turn HP, clears (files) |")
    out("|---|---|---|---|---|---|---|---|---|")
    for label, r, _ in rows:
        if r is None:
            out(f"| {label} | 0 | 0 | | | | | | none |")
            continue
        two = f"{r['two'][0]:+.2f}, {r['two'][1]:+.3f} ({r['two'][2]})" if r["two"] else "none"
        out(f"| {label} | {r['seeds']} | {r['files']} | {r['hp']:+.2f} | {r['se_seq']:.2f} | {r['sd_seeds']:.2f} | "
            f"{r['clears']:+.3f} | {r['thread_h']:.1f} | {two} |")
    out("\nPer net (mean over its books; se over sequences per book):\n")
    out("| recipe | net | books | end-HP edge | se | clears edge | thread-h | two-turn |")
    out("|---|---|---|---|---|---|---|---|")
    for label, _, nets in rows:
        for n in nets:
            two = ", ".join(f"{e[0]:+.2f}" for e in n["two"]) or "none"
            out(f"| {label} | {n['net']} | {' + '.join(n['books'])} | {n['hp']:+.2f} | "
                f"{' / '.join(f'{s:.2f}' for s in n['se'])} | {n['clears']:+.3f} | {n['thread_h']:.1f} | {two} |")


def main():
    ap = argparse.ArgumentParser()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import jobs  # the main checkout's data, also from a lane worktree
    ap.add_argument("--root", default=jobs.REPO)
    ap.add_argument("--md", action="store_true", help="print the table for the results doc (the default)")
    a = ap.parse_args()
    root = Path(a.root)
    if not (root / "results" / "gauntlet").exists():
        sys.exit(f"ledger: no results/gauntlet under {root}")
    print_md(ledger(root))


if __name__ == "__main__":
    main()
