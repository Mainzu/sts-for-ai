import json, numpy as np, sys
sys.path.insert(0, "scripts/analysis")  # run from the main checkout
import random_world as rw
d = rw.load("results/mutate/rw-pilot.json"); base = rw.load(d["settings"]["base"])
by = {(r["i"], r["floor"]): r for r in base["rows"]}
def ms(x):
    x = np.asarray(x, float); return f"{x.mean():+6.2f} ({x.std(ddof=1)/np.sqrt(len(x)):.2f})"
out = {}
for w in d["worlds"]:
    acc = out.setdefault((w["pool"], w["k"]), {k: [] for k in "rawN predN rawH predH capcost capS cost S survC survS stallN stallH n_surv".split()})
    W = {k: [] for k in acc}
    for (i, f), net, heur in zip(w["starts"], w["res"]["one"], w["res"]["heuristic"]):
        row = by[(i, f)]; s = len(net); hp = row["hp"]
        pn, ph = rw.loss(row, row["parent"]["one"][:s]), rw.loss(row, row["parent"]["heuristic"][:s])
        Ln, Lh = rw.loss(row, net), rw.loss(row, heur)
        Pn = pn + sum(rw.loss(row, row["mods"][m]["one"][:s]) - pn for m in w["items"])
        Ph = ph + sum(rw.loss(row, row["mods"][m]["heuristic"][:s]) - ph for m in w["items"])
        W["rawN"] += list(Ln - pn); W["predN"] += list(Pn - pn)
        W["rawH"] += list(Lh - ph); W["predH"] += list(Ph - ph)
        W["cost"] += list((Ln - pn) - (Lh - ph)); W["S"] += list((Pn - pn) - (Ph - ph))
        cn, ch = np.minimum(Pn, hp), np.minimum(Ph, hp)
        W["capS"] += list((cn - pn) - (ch - ph))
        surv = np.array([a for a, _ in net]) & np.array([a for a, _ in heur]) & (Pn < hp) & (Ph < hp)
        W["survC"] += list(((Ln - pn) - (Lh - ph))[surv]); W["survS"] += list(((Pn - pn) - (Ph - ph))[surv])
        W["stallN"] += [(not a) and h > 0 for a, h in net]; W["stallH"] += [(not a) and h > 0 for a, h in heur]
        W["n_surv"].append(surv.mean())
    for k in acc: acc[k].append(np.mean(W[k]) if W[k] else np.nan)
print("pool k | net raw vs pred | heur raw vs pred | cost vs capped S (diff) | both-survive cost vs S (diff) | surv frac | stalls net/heur")
for (p, k), a in sorted(out.items()):
    A = {x: np.array(v) for x, v in a.items()}
    ok = ~np.isnan(A["survC"])
    print(p, k, "|", ms(A["rawN"]), ms(A["predN"]), "|", ms(A["rawH"]), ms(A["predH"]), "|", ms(A["cost"]), ms(A["capS"]), ms(A["cost"] - A["capS"]),
          "|", ms(A["survC"][ok]), ms(A["survS"][ok]), ms(A["survC"][ok] - A["survS"][ok]), "|", f"{A['n_surv'].mean():.2f}", "|", f"{A['stallN'].mean():.2f}/{A['stallH'].mean():.2f}")
print()
print("pool k | g_capped = cost - 1.5 capS (se) | z | cost/capS | deaths net-heur | pred-death-free starts frac")
for (p, k), a in sorted(out.items()):
    c, S = np.array(a["cost"]), np.array(a["capS"]); g = c - 1.5 * S
    m, se = g.mean(), g.std(ddof=1) / np.sqrt(len(g))
    print(p, k, f"| {m:+.2f} ({se:.2f}) | {m/se:+.1f} | {c.mean()/S.mean():.2f}")
