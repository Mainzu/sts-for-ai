"""Per-encounter lead of the nets over the heuristic, and whether it tracks
how much each encounter's monsters follow a move pattern the net can't see.

Zero-CPU analysis (file reading only, no games). Question (owner,
2026-10-30): "we should move up enemy attack pattern soon so the AI can
distinguish enemies". The value nets see each monster's current intent, its
powers and a few scalars (py/src/features.rs), and the player's `turn`, but
no monster identity and no move pattern; the heuristic averages each
monster's damage over its next 4 moves (engine/src/heuristic.rs). If pattern
blindness costs the nets, they should trail the heuristic (or gain least) on
encounters whose next moves differ most from the intent on show.

Sources (read only):
- runs/seed-check/check.json: retrains of the night's s1 rounds 2/4/7/10 at
  seeds 1/101/201 on tight fights v2 (data/bench/tight2.json, 15
  encounters, ~40 cells of 20 fights per encounter and half), plus the
  heuristic's per-fight results on the same fights. r2 s1 is the ladder
  champion (results/ladder/tests/0001.json).
- runs/rung4-nightdb/check.json: arm B (3 seeds), same fights.
- runs/2026-10-30-lean*-r2-*/round.json: lean-loop round-2 nets, same fights.
- results/bosses/lead.json: r2 s1/s101/s201 on tight_bosses (Hexaghost, The
  Guardian) and Slime Boss.
- results/ladder/tests/0001.json: r2 s1 vs heuristic on fresh fights.
- results/depth/*.json: one-turn vs two-turn search on the same elite+boss
  fights, with heuristic leaves (50k and 400k node caps) and with r2 s1's
  net leaves (50k cap only).

Statistics: fights cluster by cell (same deck, encounter and HP), so the
unit is the cell: per-cell mean of the per-fight difference, then mean and
se = sd / sqrt(cells). For a 3-seed arm the fights are first averaged over
seeds; the seed-to-seed sd of the per-encounter lead is printed beside it.
The encounter-level test treats the encounters as the sample (Welch t over
encounters, and a permutation test of Spearman's rank correlation), which is
what "does pattern strength predict the lead" needs; with 6 vs 6 encounters
it is weak, and the script says so.

    OMP_NUM_THREADS=1 .venv/Scripts/python scripts/analysis/pattern_by_encounter.py
Writes scripts/analysis/out/pattern_by_encounter.json and .txt.
"""

import glob
import io
import json
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(os.path.dirname(__file__), "out")
HALVES = ("train", "held_out")
SEEDS = ("1", "101", "201")

# --- how strongly each encounter's moves follow a pattern the net can't see
# (engine/src/monsters.rs). 2: a fixed sequence or cycle whose coming moves
# differ sharply from the intent on show; 1: partly; 0: random moves with
# repeat limits, little to gain from knowing the pattern.
PATTERN = {
    "slime_boss": (2, "Goop Spray, Preparing, Slam (35) cycle; split at half HP"),
    "lagavulin": (2, "asleep 3 turns, then Attack, Attack, Siphon Soul"),
    "three_sentries": (2, "Bolt / Beam (Dazed) alternation, middle one offset"),
    "hexaghost": (2, "Activate, Divider, then a fixed 7-move cycle with Inferno"),
    "the_guardian": (2, "4-move cycle; Mode Shift threshold flips to Defensive mode"),
    "looter": (2, "Mug, Mug, Lunge/Smoke Bomb, then Escape (fight ends)"),
    "gremlin_nob": (1, "Bellow first, then 33% Skull Bash / 67% Rush"),
    "cultist": (1, "Incantation, then Dark Strike forever (Ritual visible)"),
    "large_slime": (1, "random moves; splits at half HP"),
    "exordium_thugs": (1, "louse or medium slime + Cultist or Looter"),
    "jaw_worm": (0, "Chomp first, then a roll with repeat limits"),
    "exordium_wildlife": (0, "Fungi Beast or Jaw Worm + louse or medium slime"),
    "two_louse": (0, "75% Bite / 25% Grow or Web, repeat limits"),
    "three_louse": (0, "as two_louse"),
    "small_slimes": (0, "medium + small slime; random or alternating"),
    "lots_of_slimes": (0, "five small slimes"),
    "two_fungi_beasts": (0, "60% Bite / 40% Grow, repeat limits"),
}
# The brief's split: strong vs light (Looter on the light side there).
BRIEF_STRONG = {"slime_boss", "lagavulin", "three_sentries", "gremlin_nob", "cultist", "hexaghost", "the_guardian"}
BRIEF_LIGHT = {"two_louse", "three_louse", "small_slimes", "lots_of_slimes", "two_fungi_beasts", "looter"}

buf = io.StringIO()


def say(*a):
    print(*a)
    print(*a, file=buf)


def p(*parts):
    return os.path.join(ROOT, *parts)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def bits(s):
    return (np.frombuffer(s.encode(), np.uint8) - ord("0")).astype(float)


def cluster(diff, cells):
    """(mean, se, n cells) of per-fight `diff`, clustered by cell."""
    diff = np.asarray(diff, float)
    ids, inv = np.unique(cells, return_inverse=True)
    m = np.bincount(inv, weights=diff) / np.bincount(inv)
    se = m.std(ddof=1) / np.sqrt(len(m)) if len(m) > 1 else float("nan")
    return float(m.mean()), float(se), int(len(m))


# --- tight2 ----------------------------------------------------------------

SPECS = load(p("data", "bench", "tight2.json"))["halves"]
CELL = {h: np.array([s["cell"] for s in SPECS[h]]) for h in HALVES}
ENC = {h: np.array([s["encounter"] for s in SPECS[h]]) for h in HALVES}
GROUP = {}
for h in HALVES:
    for s in SPECS[h]:
        GROUP[s["encounter"]] = s["group"]
ENCS = sorted(set(ENC["train"]), key=lambda e: (["hallway", "elite", "boss"].index(GROUP[e]), e))

sc = load(p("runs", "seed-check", "check.json"))
HEUR = {h: bits(sc["heuristic_fights"][h]) for h in HALVES}
for h in HALVES:
    assert len(HEUR[h]) == len(SPECS[h])

NETS = {}  # name -> {half: per-fight won}
ARMS = {}  # arm -> [names]


def add(name, arm, fights):
    NETS[name] = {h: bits(fights[h]) for h in HALVES}
    ARMS.setdefault(arm, []).append(name)


for k in ("2", "4", "7", "10"):
    for s in SEEDS:
        add(f"sc r{k} s{s}", f"seed-check r{k}", sc["rounds"][k]["seeds"][s]["fights"])
r4 = load(p("runs", "rung4-nightdb", "check.json"))
assert r4["heuristic_fights"] == sc["heuristic_fights"]
for s in SEEDS:
    add(f"rung4 B s{s}", "rung4 B", r4["seeds"][s]["fights"]["B"])
for path in sorted(glob.glob(p("runs", "2026-10-30-lean*-r2-*", "round.json"))):
    r = load(path)
    tr = r.get("tight_results")
    if not tr or r.get("tight_set") != "tight2":
        continue
    assert tr["heuristic"] == sc["heuristic_fights"], path
    name = os.path.basename(os.path.dirname(path)).split("-r2-")[0].replace("2026-10-30-", "")
    add(name + " r2", "lean r2", tr["net"])


def enc_lead(names, half, enc):
    """Lead of the seed-averaged fights of `names` on `enc`: (mean, se, cells),
    plus the per-net leads."""
    sel = ENC[half] == enc
    f = np.mean([NETS[n][half][sel] for n in names], axis=0)
    m = cluster(f - HEUR[half][sel], CELL[half][sel])
    per = [float((NETS[n][half][sel] - HEUR[half][sel]).mean()) for n in names]
    return m, per


def heur_rate(half, enc):
    sel = ENC[half] == enc
    return float(HEUR[half][sel].mean())


# --- bosses (tight_bosses + Slime Boss) ------------------------------------

BL = load(p("results", "bosses", "lead.json"))


def boss_lead(half, enc, names):
    fl = BL["fights"][half]
    sel = np.array([f["encounter"] == enc for f in fl])
    cells = np.array([f"{f['encounter']}:{f['cell']}" for f in fl])[sel]
    h = np.array(BL["won"][half]["heuristic"], float)[sel]
    nets = [np.array(BL["won"][half]["nets"][n], float)[sel] for n in names]
    m = cluster(np.mean(nets, axis=0) - h, cells)
    per = [float((x - h).mean()) for x in nets]
    return m, per, float(h.mean())


# --- encounter-level tests -------------------------------------------------

def welch(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a.mean() - b.mean()
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float(d), float(se)


def spearman(x, y):
    # average ranks for ties in x (the score has ties); y has none in practice
    xs = np.asarray(x, float)
    rx = np.array([np.mean(np.where(np.sort(xs) == v)[0]) for v in xs])
    ry = np.argsort(np.argsort(y)).astype(float)
    return float(np.corrcoef(rx, ry)[0, 1])


def perm_p(x, y, reps=20000, seed=1):
    rng = np.random.default_rng(seed)
    r0 = spearman(x, y)
    y = np.asarray(y, float)
    hits = sum(abs(spearman(x, rng.permutation(y))) >= abs(r0) - 1e-12 for _ in range(reps))
    return r0, (hits + 1) / (reps + 1)


def main():
    os.makedirs(OUT, exist_ok=True)
    res = {"pattern_score": {e: v[0] for e, v in PATTERN.items()}}

    main_arm = ARMS["seed-check r2"]
    champ = ["sc r2 s1"]
    all_nets = [n for a in ARMS for n in ARMS[a]]
    say(f"nets with per-fight tight2 results: {len(all_nets)}; arms {{{', '.join(f'{a}: {len(v)}' for a, v in ARMS.items())}}}")

    # 1. per-encounter table on tight2
    say("\n== 1. tight2: net minus heuristic win rate per encounter (cell-clustered se; n = cells) ==")
    say("   r2 = seed-check round-2 retrains, fights averaged over seeds 1/101/201 (seeds: per-seed leads);")
    say("   champ = r2 s1 alone; all = every net above averaged. heur = heuristic's own win rate.")
    tab = {}
    for h in HALVES:
        say(f"\n-- {h} --")
        say(f"{'encounter':18s} {'grp':7s} pat heur  | {'r2 lead (se) n':22s} seeds               | {'champ (se)':16s} | {'all nets (se)':16s}")
        for e in ENCS:
            (m, s, n), per = enc_lead(main_arm, h, e)
            (mc, sc_, _), _ = enc_lead(champ, h, e)
            (ma, sa, _), per_all = enc_lead(all_nets, h, e)
            tab[(h, e)] = {"r2": [m, s, n], "r2_seeds": per, "seed_sd": float(np.std(per, ddof=1)),
                           "champ": [mc, sc_], "all": [ma, sa], "all_per_net": per_all,
                           "heur": heur_rate(h, e)}
            say(f"{e:18s} {GROUP[e]:7s} {PATTERN[e][0]:3d} {heur_rate(h, e):.2f}  | {m:+.3f} ({s:.3f}) n{n:<3d}      "
                + "/".join(f"{x:+.3f}" for x in per)
                + f" | {mc:+.3f} ({sc_:.3f}) | {ma:+.3f} ({sa:.3f})")
    res["tight2"] = {f"{h}/{e}": v for (h, e), v in tab.items()}

    # 1b. are per-encounter differences stable? split-sample reliability:
    # leads from seed-check r4/r7/r10 + rung4 B (12 nets) vs r2 + lean (6 nets),
    # and seed s1 vs mean(s101, s201) within r2.
    say("\n== 1b. Do per-encounter leads repeat across independent nets? (Pearson r over 15 encounters) ==")
    rel = {}
    groupA = ARMS["seed-check r4"] + ARMS["seed-check r7"] + ARMS["seed-check r10"] + ARMS["rung4 B"]
    groupB = ARMS["seed-check r2"] + ARMS.get("lean r2", [])
    for h in HALVES:
        a = [enc_lead(groupA, h, e)[0][0] for e in ENCS]
        b = [enc_lead(groupB, h, e)[0][0] for e in ENCS]
        c = [enc_lead(["sc r2 s1"], h, e)[0][0] for e in ENCS]
        d = [enc_lead(["sc r2 s101", "sc r2 s201"], h, e)[0][0] for e in ENCS]
        hallway = [i for i, e in enumerate(ENCS) if GROUP[e] == "hallway"]
        rel[h] = {"later_vs_r2lean": float(np.corrcoef(a, b)[0, 1]),
                  "s1_vs_s101s201": float(np.corrcoef(c, d)[0, 1]),
                  "later_vs_r2lean_hallway": float(np.corrcoef(np.array(a)[hallway], np.array(b)[hallway])[0, 1])}
        say(f"{h:8s} r4/r7/r10/B (12 nets) vs r2+lean ({len(groupB)} nets): r = {rel[h]['later_vs_r2lean']:+.2f} "
            f"(hallway only, 11 enc: {rel[h]['later_vs_r2lean_hallway']:+.2f});  r2 s1 vs r2 s101+s201: r = {rel[h]['s1_vs_s101s201']:+.2f}")
    res["reliability"] = rel

    # 2. bosses
    say("\n== 2. Bosses (results/bosses/lead.json, r2 s1/s101/s201, cell-clustered se) ==")
    bos = {}
    names = list(BL["won"]["train"]["nets"].keys())
    for h in HALVES:
        for e in ("slime_boss", "hexaghost", "the_guardian"):
            (m, s, n), per, hr = boss_lead(h, e, names)
            bos[f"{h}/{e}"] = {"lead": [m, s, n], "per_net": per, "heur": hr}
            say(f"{h:8s} {e:13s} pat {PATTERN[e][0]} heur {hr:.2f}  lead {m:+.3f} (se {s:.3f}, n{n} cells)  nets "
                + "/".join(f"{x:+.3f}" for x in per))
    res["bosses"] = bos

    # 3. ladder 0001: champion vs heuristic on fresh fights
    say("\n== 3. Ladder test 0001 (r2 s1 vs heuristic, fresh fights, both halves pooled; se over pairs) ==")
    lt = load(p("results", "ladder", "tests", "0001.json"))
    lad = {}
    pairs = [q for q in lt["pairs_played"] if q.get("counted")]
    for e in ENCS:
        d = np.array([q["cand"] - q["champ"] for q in pairs if q["encounter"] == e], float)
        cells = np.array([f"{q['half']}:{q['cell']}" for q in pairs if q["encounter"] == e])
        m, s, n = cluster(d, cells)
        lad[e] = [m, s, len(d)]
        say(f"{e:18s} pat {PATTERN[e][0]}  {m:+.3f} (se {s:.3f}, n{len(d)} pairs)")
    res["ladder0001"] = lad

    # 4. encounter-level test: does the pattern score predict the lead?
    say("\n== 4. Does pattern strength predict the lead? (encounters are the sample) ==")
    tests = {}
    boss_extra = {h: {e: bos[f"{h}/{e}"]["lead"][0] for e in ("hexaghost", "the_guardian")} for h in HALVES}
    for h in HALVES:
        for label, getter in (("r2", lambda e: tab[(h, e)]["r2"][0]), ("all nets", lambda e: tab[(h, e)]["all"][0])):
            lead = {e: getter(e) for e in ENCS}
            lead17 = dict(lead, **boss_extra[h])  # with the two tight_bosses bosses (r2 nets)
            out = {}
            for setname, L in (("15 tight2", lead), ("17 with Hexaghost+Guardian", lead17)):
                es = list(L)
                x = [PATTERN[e][0] for e in es]
                y = [L[e] for e in es]
                r, pv = perm_p(x, y)
                strong = [L[e] for e in es if e in BRIEF_STRONG]
                light = [L[e] for e in es if e in BRIEF_LIGHT]
                d, se = welch(strong, light)
                s2 = [L[e] for e in es if PATTERN[e][0] == 2]
                s0 = [L[e] for e in es if PATTERN[e][0] == 0]
                d2, se2 = welch(s2, s0)
                hw = [e for e in es if GROUP.get(e, "boss") == "hallway"]
                rh, ph = perm_p([PATTERN[e][0] for e in hw], [L[e] for e in hw])
                out[setname] = {"spearman": r, "perm_p": pv, "brief_strong_minus_light": [d, se, len(strong), len(light)],
                                "score2_minus_score0": [d2, se2, len(s2), len(s0)],
                                "hallway_only_spearman": [rh, ph, len(hw)]}
                say(f"{h:8s} {label:8s} {setname:27s} Spearman(score, lead) {r:+.2f} (perm p {pv:.2f}); "
                    f"brief strong-light {d:+.3f} (se {se:.3f}, {len(strong)} v {len(light)}); "
                    f"score2-score0 {d2:+.3f} (se {se2:.3f}, {len(s2)} v {len(s0)}); hallway-only Spearman {rh:+.2f} (p {ph:.2f}, {len(hw)} enc)")
            tests[f"{h}/{label}"] = out
    res["tests"] = tests

    # 4b. the held-out drop (train lead - held-out lead) per encounter: does
    # the generalisation loss concentrate on pattern-strong encounters?
    say("\n== 4b. Held-out drop per encounter (r2 arm: train lead - held-out lead; se from both halves' cells) ==")
    drop = {}
    for e in ENCS + ["hexaghost", "the_guardian"]:
        if e in ("hexaghost", "the_guardian"):
            t, ho = bos[f"train/{e}"]["lead"], bos[f"held_out/{e}"]["lead"]
        else:
            t, ho = tab[("train", e)]["r2"], tab[("held_out", e)]["r2"]
        drop[e] = [t[0] - ho[0], float(np.hypot(t[1], ho[1]))]
        say(f"{e:18s} {GROUP.get(e, 'boss'):7s} pat {PATTERN[e][0]}  train {t[0]:+.3f}  held-out {ho[0]:+.3f}  drop {drop[e][0]:+.3f} (se {drop[e][1]:.3f})")
    for setname, es in (("15 tight2", ENCS), ("17 with Hexaghost+Guardian", list(drop))):
        r, pv = perm_p([PATTERN[e][0] for e in es], [drop[e][0] for e in es])
        say(f"   {setname}: Spearman(score, drop) {r:+.2f} (perm p {pv:.2f})")
    eb = [e for e in drop if GROUP.get(e, "boss") != "hallway"]
    say(f"   elites+bosses only ({len(eb)}): drops " + ", ".join(f"{e} {drop[e][0]:+.3f}" for e in eb))
    res["held_out_drop"] = drop

    # 5. depth: per encounter, two-turn minus one-turn, with heuristic and net leaves
    say("\n== 5. Depth per encounter (results/depth; same fights in every file of a half; cell-clustered se) ==")
    dep = {}
    for h in HALVES:
        hz = {"heur50k": load(p("results", "depth", f"paired-{h}.json")),
              "heur400k": load(p("results", "depth", f"paired-{h}-cap400k.json")),
              "net50k": load(p("results", "depth", f"paired-net-{h}.json"))}
        keys = {k: [(f["seed"], f["encounter"]) for f in v["fights"]] for k, v in hz.items()}
        assert keys["heur50k"] == keys["heur400k"] == keys["net50k"], h
        fl = hz["heur50k"]["fights"]
        enc = np.array([f["encounter"] for f in fl])
        cells = np.array([f"{f['encounter']}:{f['cell']}" for f in fl])
        W = {k: {arm: np.array([f[arm]["won"] for f in v["fights"]], float) for arm in ("one", "two")} for k, v in hz.items()}
        same_one = float((W["heur50k"]["one"] == W["heur400k"]["one"]).mean())
        say(f"\n-- {h} (heuristic one-turn identical across caps on {same_one:.1%} of fights) --")
        say(f"{'encounter':15s} pat | {'heur 2-1 @400k':17s} | {'heur 2-1 @50k':17s} | {'net 2-1 @50k':17s} | "
            f"{'net gain - heur gain @50k':26s} | {'net1 - heur1':17s} | {'net2 - heur2 @50k':17s}")
        for e in ("gremlin_nob", "lagavulin", "three_sentries", "slime_boss"):
            s = enc == e
            c = cells[s]
            row = {
                "heur_2m1_400k": cluster(W["heur400k"]["two"][s] - W["heur400k"]["one"][s], c),
                "heur_2m1_50k": cluster(W["heur50k"]["two"][s] - W["heur50k"]["one"][s], c),
                "net_2m1_50k": cluster(W["net50k"]["two"][s] - W["net50k"]["one"][s], c),
                "did_50k": cluster((W["net50k"]["two"][s] - W["net50k"]["one"][s])
                                   - (W["heur50k"]["two"][s] - W["heur50k"]["one"][s]), c),
                "net1_m_heur1": cluster(W["net50k"]["one"][s] - W["heur50k"]["one"][s], c),
                "net2_m_heur2_50k": cluster(W["net50k"]["two"][s] - W["heur50k"]["two"][s], c),
            }
            dep[f"{h}/{e}"] = row
            say(f"{e:15s} {PATTERN[e][0]:3d} | " + " | ".join(
                f"{row[k][0]:+.3f} ({row[k][1]:.3f})".ljust(w) for k, w in
                (("heur_2m1_400k", 17), ("heur_2m1_50k", 17), ("net_2m1_50k", 17), ("did_50k", 26),
                 ("net1_m_heur1", 17), ("net2_m_heur2_50k", 17))) + f" n{row['did_50k'][2]}")
    res["depth"] = dep
    say("\n   Pattern-blindness test on depth: if the net misses the coming moves, two-turn search (which plays the")
    say("   monster's real next move in the engine) should help net leaves more than heuristic leaves on the")
    say("   fixed-sequence encounters (pattern 2) than on Gremlin Nob (pattern 1). Contrast of 'net gain - heur gain':")
    for h in HALVES:
        s2 = [dep[f"{h}/{e}"]["did_50k"] for e in ("lagavulin", "three_sentries", "slime_boss")]
        nob = dep[f"{h}/gremlin_nob"]["did_50k"]
        m2 = np.mean([x[0] for x in s2])
        se2 = np.sqrt(sum(x[1] ** 2 for x in s2)) / 3
        say(f"   {h:8s} mean of 3 pattern-2 encounters {m2:+.3f} (se {se2:.3f}); Nob {nob[0]:+.3f} (se {nob[1]:.3f}); "
            f"difference {m2 - nob[0]:+.3f} (se {np.hypot(se2, nob[1]):.3f})")
        dep[f"{h}/contrast"] = [float(m2), float(se2), float(m2 - nob[0]), float(np.hypot(se2, nob[1]))]

    with open(os.path.join(OUT, "pattern_by_encounter.json"), "w") as f:
        json.dump(res, f, indent=1, default=float)
    with open(os.path.join(OUT, "pattern_by_encounter.txt"), "w") as f:
        f.write(buf.getvalue())
    print(f"\nwrote {OUT}/pattern_by_encounter.json and .txt")


if __name__ == "__main__":
    sys.exit(main())
