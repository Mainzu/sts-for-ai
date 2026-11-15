"""Skeptic check on pattern_info_gap: does a cheap 'previous move' input
(the effects of the move used last turn, no kind id) also close the
within-kind gap that lookahead columns close? Reuses pattern_info_gap's
move tables and gap() without rewriting its output. Zero CPU."""
import os
src = open(os.path.join(os.path.dirname(__file__), "pattern_info_gap.py")).read()
src = src.split("SETS = {")[0]
g = {"__file__": __file__}
exec(src, g)
rows, gap, K = g["rows"], g["gap"], g["K"]
sig = lambda kind, m: "none" if m is None else K[kind][0][m][0]
SETS = {
    "today (intent + turn)": lambda r: (r[5], r[2]),
    "ids (kind + intent + turn)": lambda r: (r[0], r[5], r[2]),
    "prev effects (intent + prev move effects + turn)": lambda r: (r[5], sig(r[0], r[3][1]), r[2]),
    "prev effects, no turn": lambda r: (r[5], sig(r[0], r[3][1])),
    "kind + intent id + prev id": lambda r: (r[0], r[3][0], r[3][1]),
}
print("pooled, k=1/2/3")
for n, f in SETS.items():
    print(f"{n:50s}", " ".join(f"{x:6.2f}" for x in gap(f)))
print("\nper kind, k=1/2/3: today | prev effects + turn | kind+intent id+prev id")
for kind in K:
    a = gap(SETS["today (intent + turn)"], {kind})
    b = gap(SETS["prev effects (intent + prev move effects + turn)"], {kind})
    c = gap(SETS["kind + intent id + prev id"], {kind})
    fm = lambda v: "/".join(f"{x:4.2f}" for x in v)
    print(f"{kind:12s} {fm(a):>16s} | {fm(b):>16s} | {fm(c):>16s}")
