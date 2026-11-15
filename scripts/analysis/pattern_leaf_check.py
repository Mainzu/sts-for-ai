"""Per-slot check of the one-turn End-turn leaf: which monsters have not yet rolled.

pattern_identify.py marks every monster in a leaf 'paused' when the leaf waits on
any monster roll. The engine rolls slots in order (Stage::MonsterRolls), so at a
leaf paused at slot p, slots < p have their new move and slots >= p still show
the move just used. This counts per slot. Single thread, same play loop and seeds.
Output: scripts/analysis/out/pattern_leaf_check.txt
"""
import os, random, re, sys
from collections import defaultdict
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("RAYON_NUM_THREADS", "1")
import sts  # noqa: E402
ENCOUNTERS = ["cultist", "jaw_worm", "two_louse", "small_slimes", "large_slime", "lots_of_slimes", "three_louse",
              "two_fungi_beasts", "looter", "exordium_thugs", "exordium_wildlife", "gremlin_nob", "lagavulin",
              "three_sentries", "slime_boss", "hexaghost", "the_guardian"]
SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 40
LINE = re.compile(r"^\s*\[(\d)\] (.+?)  HP (-?\d+)/(\d+)  Block (\d+)  intent: (.*?)(  \[(.*)\])?$")
PAUSE = re.compile(r"paused at chance event: move roll for slot (\d)")
def kinds(c):
    out = {}
    for line in c.render().splitlines():
        m = LINE.match(line)
        if m: out[int(m.group(1))] = (m.group(2), m.group(6))
    return out
def mv(intent): return re.sub(r"\s*\(\d+(x\d+)?\)", "", intent)
rng = random.Random(7); deck = sts.starter_deck("ironclad")
# kind -> [leaves, any-pause, own slot unrolled, unrolled & same move name, unrolled & same full intent text]
st = defaultdict(lambda: [0, 0, 0, 0, 0])
for enc in ENCOUNTERS:
    for seed in range(SEEDS):
        c = sts.Combat(deck, enc, seed=seed, no_death=True); c.advance()
        while not c.is_over() and c.turn() <= 10:
            if not c.awaiting_action(): c.advance(); continue
            k = kinds(c)
            outs = [o for a, _, o in c.options(1) if any(x.is_end_turn for x in a)][0]
            t = outs[0][1]
            if not t.is_over():
                after = kinds(t); m = PAUSE.search(t.render()); p = int(m.group(1)) if m else None
                for slot, (name, before) in k.items():
                    if slot not in after: continue
                    s = st[name]; s[0] += 1
                    if p is not None:
                        s[1] += 1
                        if slot >= p:
                            s[2] += 1
                            if mv(after[slot][1]) == mv(before): s[3] += 1
                            if after[slot][1] == before: s[4] += 1
            c.step(rng.choice(c.legal_actions())); c.advance()
lines = ["kind: leaves | leaf paused at any roll | own slot not yet rolled (slot >= paused slot) | of those, same move name | same full intent text"]
for name, (n, a, u, sm, sf) in sorted(st.items()):
    lines.append(f"  {name}: {n} | {a} ({a/n:.3f}) | {u} ({u/n:.3f}) | {sm} | {sf}")
txt = "\n".join(lines); print(txt)
os.makedirs(os.path.join(os.path.dirname(__file__), "out"), exist_ok=True)
open(os.path.join(os.path.dirname(__file__), "out", "pattern_leaf_check.txt"), "w").write(txt + "\n")
