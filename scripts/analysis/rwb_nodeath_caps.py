"""Random-world bench step 4: the no-death file read with HP lost capped per game (start HP, +30, 100, 150), against the plain and the capped sum of singles (docs/research/random-world-bench.md, Step 4)."""
import json, sys, numpy as np
sys.path.insert(0, "scripts/analysis")  # run from the main checkout
import random_world as rw
d = rw.load("results/mutate/rw-nodeath.json")
H0 = np.array(d["start_hp"], float)[:, None]
cells = d["cells"]
par = next(c for c in cells if c["kind"] == "parent"); sing = {c["items"][0]: c for c in cells if c["kind"] == "single"}
def L(c, p, cap):
    l = H0 - np.array([[h for _, h in r] for r in c["res"][p]], float)
    return np.minimum(l, cap(H0)) if cap else l
print("parent raw loss net/heur", L(par, "one", None).mean(), L(par, "heuristic", None).mean(), "start hp mean", H0.mean())
for name, cap in (("start HP", lambda H: H), ("start HP + 30", lambda H: H + 30), ("100", lambda H: 100), ("150", lambda H: 150)):
    pn, ph = L(par, "one", cap), L(par, "heuristic", cap)
    print("cap", name)
    for pool in ("main", "side"):
        for k in (2, 4, 8):
            g, I, C, S = [], [], [], []
            for c in cells:
                if c["kind"] != "world" or c["pool"] != pool or c["k"] != k: continue
                cost = ((L(c, "one", cap) - pn) - (L(c, "heuristic", cap) - ph)).mean()
                # additive prediction capped too: per player, parent + summed singles, then the cap
                Pn = np.minimum(pn + sum(L(sing[m], "one", cap) - pn for m in c["items"]), cap(H0))
                Ph = np.minimum(ph + sum(L(sing[m], "heuristic", cap) - ph for m in c["items"]), cap(H0))
                s_unc = sum(((L(sing[m], "one", cap) - pn) - (L(sing[m], "heuristic", cap) - ph)).mean() for m in c["items"])
                s_cap = ((Pn - pn) - (Ph - ph)).mean()
                C.append(cost); S.append((s_unc, s_cap))
            C = np.array(C); S = np.array(S)
            def ms(x): return f"{x.mean():+6.2f} ({x.std(ddof=1)/np.sqrt(len(x)):.2f})"
            print(f"  {pool} k{k}: cost {ms(C)} S {ms(S[:,0])} S_cap {ms(S[:,1])} g {ms(C-1.5*S[:,0])} g_cap {ms(C-1.5*S[:,1])} z {(C-1.5*S[:,0]).mean()/((C-1.5*S[:,0]).std(ddof=1)/np.sqrt(len(C))):+.1f} / {(C-1.5*S[:,1]).mean()/((C-1.5*S[:,1]).std(ddof=1)/np.sqrt(len(C))):+.1f}")
