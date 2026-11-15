"""How much does a value net miss about a monster's coming moves, with
today's features versus with identity columns (option a) or lookahead
columns (option b)? Zero CPU: the Act-1 move AIs are re-written here from
engine/src/monsters.rs (moves and rules only; reactions such as splitting,
Mode Shift and Lagavulin's wake-on-hit are left out).

For each monster kind, the exact distribution over its move window
[intent, previous move] is enumerated turn by turn (turns 1..T, from combat
start). For each state the target is the expected damage (base numbers, no
Strength) of the k-th move after the intent on show, k = 1, 2, 3, given the
full history. That is what lookahead columns hand the net (option b, gap 0
by construction). The gap of a feature set is the root mean square
difference between that and the best guess from the features alone (the
probability-weighted mean of the target over states that look the same):
  today          : intent's effects + turn number (identity only through
                   hints such as max HP, not used here)
  today, no turn : intent's effects only (a net that doesn't decode turn)
  ids            : kind + intent + turn (option a)
  ids, no turn   : kind + intent
Output: scripts/analysis/out/pattern_info_gap.json and a table."""
import json
import os
from collections import defaultdict

T = 10  # turns 1..T, equal weight
DIVIDER = 6 * (80 // 12 + 1)  # Divider at 80 player HP: 6 hits of 7

NO = None
K = {}  # kind: (moves {name: (signature, damage)}, ai(window, slot) -> {move: p}, slots)


def add(name, moves, ai, slots=(0,)):
    K[name] = (moves, ai, slots)


def cultist(w, s):
    return {"Incantation": 1.0} if w[0] is NO else {"DarkStrike": 1.0}


add("Cultist", {"Incantation": ("buff Ritual 3", 0), "DarkStrike": ("attack 6", 6)}, cultist)


def jaw(w, s):
    if w[0] is NO:
        return {"Chomp": 1.0}
    d = defaultdict(float)
    last, two = w[0], (w[0] == w[1])
    if last == "Chomp":
        d["Bellow"] += .25 * .5625
        d["Thrash"] += .25 * (1 - .5625)
    else:
        d["Chomp"] += .25
    if two and last == "Thrash":
        d["Chomp"] += .30 * .357
        d["Bellow"] += .30 * (1 - .357)
    else:
        d["Thrash"] += .30
    if last == "Bellow":
        d["Chomp"] += .45 * .416
        d["Thrash"] += .45 * (1 - .416)
    else:
        d["Bellow"] += .45
    return dict(d)


add("JawWorm", {"Chomp": ("attack 11", 11), "Thrash": ("attack 7 block 5", 7), "Bellow": ("str 3 block 6", 0)}, jaw)


def louse(w, s):
    two = w[0] is not NO and w[0] == w[1]
    d = defaultdict(float)
    d["Bite" if (two and w[0] == "Other") else "Other"] += .25
    d["Other" if (two and w[0] == "Bite") else "Bite"] += .75
    return dict(d)


add("RedLouse", {"Bite": ("bite rolled", 6), "Other": ("str 3", 0)}, louse)
add("GreenLouse", {"Bite": ("bite rolled", 6), "Other": ("weak 2", 0)}, louse)


def acid_m(w, s):
    d = defaultdict(float)
    two = w[0] is not NO and w[0] == w[1]
    if two and w[0] == "Spit":
        d["Tackle"] += .15
        d["Lick"] += .15
    else:
        d["Spit"] += .3
    if w[0] == "Tackle":
        d["Spit"] += .2
        d["Lick"] += .2
    else:
        d["Tackle"] += .4
    if two and w[0] == "Lick":
        d["Spit"] += .3 * .4
        d["Tackle"] += .3 * .6
    else:
        d["Lick"] += .3
    return dict(d)


add("AcidSlimeM", {"Spit": ("attack 7 slimed 1", 7), "Tackle": ("attack 10", 10), "Lick": ("weak 1", 0)}, acid_m)
add("AcidSlimeL", {"Spit": ("attack 11 slimed 2", 11), "Tackle": ("attack 16", 16), "Lick": ("weak 2", 0)}, acid_m)


def acid_s(w, s):
    if w[0] is NO:
        return {"Tackle": .5, "Lick": .5}
    return {"Lick": 1.0} if w[0] == "Tackle" else {"Tackle": 1.0}


add("AcidSlimeS", {"Lick": ("weak 1", 0), "Tackle": ("attack 3", 3)}, acid_s)


def spike_m(w, s):
    two = w[0] is not NO and w[0] == w[1]
    d = defaultdict(float)
    d["Lick" if (two and w[0] == "Flame") else "Flame"] += .3
    d["Flame" if (two and w[0] == "Lick") else "Lick"] += .7
    return dict(d)


add("SpikeSlimeM", {"Flame": ("attack 8 slimed 1", 8), "Lick": ("frail 1", 0)}, spike_m)
add("SpikeSlimeL", {"Flame": ("attack 16 slimed 2", 16), "Lick": ("frail 2", 0)}, spike_m)
add("SpikeSlimeS", {"Tackle": ("attack 5", 5)}, lambda w, s: {"Tackle": 1.0})


def fungi(w, s):
    d = defaultdict(float)
    two = w[0] is not NO and w[0] == w[1]
    d["Grow" if (two and w[0] == "Bite") else "Bite"] += .6
    d["Bite" if w[0] == "Grow" else "Grow"] += .4
    return dict(d)


add("FungiBeast", {"Bite": ("attack 6", 6), "Grow": ("str 3", 0)}, fungi)


def looter(w, s):
    if w[0] is NO or (w[0] == "Mug" and w[1] is NO):
        return {"Mug": 1.0}
    if w[0] == "Mug":
        return {"Lunge": .5, "Smoke": .5}
    if w[0] == "Lunge":
        return {"Smoke": 1.0}
    return {"Escape": 1.0}


add("Looter", {"Mug": ("attack 10", 10), "Lunge": ("attack 12", 12), "Smoke": ("block 6", 0), "Escape": ("escape", 0)}, looter)


def nob(w, s):
    if w[0] is NO:
        return {"Bellow": 1.0}
    if w[0] == w[1] == "Rush":
        return {"Bash": 1.0}
    return {"Bash": .33, "Rush": .67}


add("GremlinNob", {"Bellow": ("enrage 2", 0), "Rush": ("attack 14", 14), "Bash": ("attack 6 vuln 2", 6)}, nob)


def laga(w, s):
    if w[0] is NO or (w[0] == "Sleep" and w[1] is NO):
        return {"Sleep": 1.0}
    if w[0] == "Sleep":
        return {"Wake": 1.0}
    if w[0] == w[1] == "Attack":
        return {"Siphon": 1.0}
    return {"Attack": 1.0}


add("Lagavulin", {"Sleep": ("nothing", 0), "Wake": ("metallicize -8", 0), "Attack": ("attack 18", 18), "Siphon": ("dex -1 str -1", 0)}, laga)


def sentry(w, s):
    if w[0] is NO:
        return {"Beam" if s == 1 else "Bolt": 1.0}
    return {"Bolt": 1.0} if w[0] == "Beam" else {"Beam": 1.0}


add("Sentry", {"Bolt": ("dazed 2", 0), "Beam": ("attack 9", 9)}, sentry, slots=(0, 1, 2))


def slime_boss(w, s):
    return {{"Goop": "Prep", "Prep": "Slam"}.get(w[0], "Goop"): 1.0}


add("SlimeBoss", {"Goop": ("slimed 3", 0), "Prep": ("nothing", 0), "Slam": ("attack 35", 35)}, slime_boss)

HEX_CYCLE = ["Sear", "Tackle", "Sear", "Inflame", "Tackle", "Sear", "Inferno"]
HEX_SIG = {"Sear": ("attack 6 burn 1", 6), "Tackle": ("attack 5x2", 10), "Inflame": ("block 12 str 2", 0),
           "Inferno": ("attack 2x6 burn+ 3", 12)}
hex_moves = {"Activate": ("nothing", 0), "Divider": ("divider rolled x6", DIVIDER)}
for up in ["", "+"]:
    for i, m in enumerate(HEX_CYCLE):
        sig, dmg = HEX_SIG[m]
        if up and m == "Sear":
            sig = "attack 6 burn+ 1"
        hex_moves[f"{m}{i}{up}"] = (sig, dmg)


def hexa(w, s):
    m = w[0]
    if m is NO:
        return {"Activate": 1.0}
    if m == "Activate":
        return {"Divider": 1.0}
    if m == "Divider":
        return {"Sear0": 1.0}
    if m.startswith("Inferno"):
        return {"Sear0+": 1.0}
    i = int(m.rstrip("+")[-1])
    up = "+" if m.endswith("+") else ""
    return {f"{HEX_CYCLE[i + 1]}{i + 1}{up}": 1.0}


add("Hexaghost", hex_moves, hexa)


def guardian(w, s):
    nxt = {"Charge": "Bash", "Bash": "Vent", "Vent": "Whirl", "CloseUp": "Roll", "Roll": "Twin", "Twin": "Whirl"}
    return {nxt.get(w[0], "Charge"): 1.0}


add("TheGuardian", {"Charge": ("block 9", 0), "Bash": ("attack 32", 32), "Vent": ("weak 2 vuln 2", 0),
                    "Whirl": ("attack 5x4", 20), "CloseUp": ("sharp hide 3", 0), "Roll": ("attack 9", 9),
                    "Twin": ("attack 8x2", 16)}, guardian)


def expected_next(kind, w, slot, k):
    """Expected damage of the k-th move after the intent on show w[0]."""
    moves, ai, _ = K[kind]
    dist = {w: 1.0}
    for _ in range(k):
        nd = defaultdict(float)
        for win, p in dist.items():
            for m, q in ai(win, slot).items():
                nd[(m, win[0])] += p * q
        dist = nd
    return sum(p * moves[win[0]][1] for win, p in dist.items())


def states(kind, slot):
    """[(turn, window, prob)] for turns 1..T; turn 1's intent is the first move."""
    moves, ai, _ = K[kind]
    out = []
    dist = defaultdict(float)
    for m, q in ai((NO, NO), slot).items():
        dist[(m, NO)] += q
    for t in range(1, T + 1):
        for win, p in dist.items():
            out.append((t, win, p))
        nd = defaultdict(float)
        for win, p in dist.items():
            for m, q in ai(win, slot).items():
                nd[(m, win[0])] += p * q
        dist = nd
    return out


rows = []  # (kind, slot, turn, window, weight, signature, targets[k])
for kind, (moves, ai, slots) in K.items():
    for slot in slots:
        for t, win, p in states(kind, slot):
            tg = [expected_next(kind, win, slot, k) for k in (1, 2, 3)]
            rows.append((kind, slot, t, win, p / (T * len(slots)), moves[win[0]][0], tg))


def gap(keyf, subset=None):
    """Per k: root mean square of target minus its mean within keyf groups."""
    rs = [r for r in rows if subset is None or r[0] in subset]
    res = []
    for k in range(3):
        sw, s1 = defaultdict(float), defaultdict(float)
        for r in rs:
            key = keyf(r)
            sw[key] += r[4]
            s1[key] += r[4] * r[6][k]
        num = den = 0.0
        for r in rs:
            mu = s1[keyf(r)] / sw[keyf(r)]
            num += r[4] * (r[6][k] - mu) ** 2
            den += r[4]
        res.append((num / den) ** 0.5)
    return res


SETS = {
    "today (intent + turn)": lambda r: (r[5], r[2]),
    "today, no turn (intent only)": lambda r: (r[5],),
    "ids (kind + intent + turn)": lambda r: (r[0], r[5], r[2]),
    "ids, no turn (kind + intent)": lambda r: (r[0], r[5]),
    "nothing (kind's mean)": lambda r: (r[0],),
}
out = {"T": T, "pooled": {}, "per_kind": {}}
print(f"Gap = RMS error (HP) of the best guess of the k-th next move's expected damage, turns 1..{T}.")
print("Lookahead columns (option b): 0 by construction.")
print(f"{'features':32s} {'k=1':>6s} {'k=2':>6s} {'k=3':>6s}   (all kinds pooled, equal weight)")
for name, f in SETS.items():
    g = gap(f)
    out["pooled"][name] = g
    print(f"{name:32s} " + " ".join(f"{x:6.2f}" for x in g))
print()
fm = lambda v: "/".join(f"{x:4.1f}" for x in v)
print(f"{'kind':12s} {'spread':>15s} | {'today':>15s} | {'today no turn':>15s} | {'ids no turn':>15s}")
for kind in K:
    s = gap(SETS["nothing (kind's mean)"], {kind})
    a = gap(SETS["today (intent + turn)"], {kind})
    b = gap(SETS["today, no turn (intent only)"], {kind})
    c = gap(SETS["ids, no turn (kind + intent)"], {kind})
    out["per_kind"][kind] = {"spread": s, "today": a, "today_no_turn": b, "ids_no_turn": c}
    print(f"{kind:12s} {fm(s):>15s} | {fm(a):>15s} | {fm(b):>15s} | {fm(c):>15s}")
os.makedirs(os.path.join(os.path.dirname(__file__), "out"), exist_ok=True)
json.dump(out, open(os.path.join(os.path.dirname(__file__), "out", "pattern_info_gap.json"), "w"), indent=1)
