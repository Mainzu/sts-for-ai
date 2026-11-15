"""A20 runs that reached the Act 1 boss: boss win rate by card in the final deck (all run-rule versions pooled)."""
import sys
from collections import Counter
sys.path.insert(0, "scripts")
import real_game_report as g
runs = sorted(g.all_runs(), key=lambda r: r["t0"])
rs = [r for r in runs if (r.get("ascension") or 0) == 20 and (r["last"].get("floor") or 0) >= 16]
won = [r for r in rs if g.ending(r).startswith("beat the Act 1 boss")]
print("reached", len(rs), "won", len(won), Counter(r["last"].get("floor") for r in rs))
have = Counter(); hw = Counter()
for r in rs:
    names = {c["name"].rstrip("+") for c in r["last"].get("deck", [])}
    w = r in won
    for n in names: have[n] += 1; hw[n] += w
for n, k in sorted(have.items(), key=lambda x: -hw[x[0]]/x[1]):
    if k >= 7 and n not in ("Strike","Defend","Bash","Ascender's Bane"):
        print("%-18s %d/%d %.0f%%   without: %d/%d" % (n, hw[n], k, 100*hw[n]/k, len(won)-hw[n], len(rs)-k))
