"""What a value net sees about each monster, and whether it can tell kinds apart.

Plays every encounter with the Ironclad starter (no_death, random legal
actions, fixed RNG) and, at each decision state and at each one-turn search
End-turn leaf (the state right after EndTurn, before any chance event is
resolved), records the monster's feature vector exactly as the value net gets
it: the monster row (scalars, power dims, intent effects) plus the monster's
entity rows (effects mode). Reports, per kind: max HP range, visible starting
powers, first-turn intent; which kinds ever share an identical visible vector
(ignoring hp, block and intent_damage, which change within a kind too) and on
what share of states; and how often the End-turn leaf shows a stale intent
(the move just used, while pending_monster_move = 1).

Single thread, a few minutes. Output: scripts/analysis/out/pattern_identify.txt
"""
import os
import random
import re
import sys
from collections import defaultdict

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("RAYON_NUM_THREADS", "1")
import numpy as np  # noqa: E402
import sts  # noqa: E402

ENCOUNTERS = ["cultist", "jaw_worm", "two_louse", "small_slimes", "large_slime", "lots_of_slimes", "three_louse",
              "two_fungi_beasts", "looter", "exordium_thugs", "exordium_wildlife", "gremlin_nob", "lagavulin",
              "three_sentries", "slime_boss", "hexaghost", "the_guardian"]
SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 30
TURNS = 10
OUT = os.path.join(os.path.dirname(__file__), "out", "pattern_identify.txt")
LINE = re.compile(r"^\s*\[(\d)\] (.+?)  HP (-?\d+)/(\d+)  Block (\d+)  intent: (.*?)(  \[(.*)\])?$")


def kinds(c):
    out = {}
    for line in c.render().splitlines():
        m = LINE.match(line)
        if m:
            out[int(m.group(1))] = (m.group(2), m.group(6))
    return out


class View:
    def __init__(self, mode):
        self.f = sts.Features(mode)
        self.mode = mode
        self.mnames = list(self.f.monster_names)
        self.pnames = list(self.f.player_names)
        self.vary = {self.mnames.index(n) for n in ("hp", "block", "intent_damage")}

    def monsters(self, c):
        """Per living slot: (static key, intent key, full vector)."""
        b = self.f.encode([c])
        mon = np.asarray(b["monsters"])[0]
        rows = np.asarray(b["rows"])
        ent = np.asarray(b["row_entity"])
        player = np.asarray(b["player"])[0]
        out = {}
        for slot in range(mon.shape[0]):
            v = mon[slot]
            if v[0] == 0:
                continue
            ent_rows = tuple(sorted(tuple(np.round(r, 3)) for r in rows[ent == 1 + slot])) if len(rows) else ()
            nz = tuple((self.mnames[i], round(float(x), 3)) for i, x in enumerate(v) if x != 0 and i not in self.vary)
            intent = tuple((n, x) for n, x in nz if n.startswith("intent_"))
            static = tuple((n, x) for n, x in nz if not n.startswith("intent_"))
            out[slot] = (static, intent, ent_rows, nz)
        return out, player


def main():
    rng = random.Random(7)
    deck = sts.starter_deck("ironclad")
    lines = []
    views = {m: View(m) for m in ("effects", "ids")}
    pmm = views["effects"].pnames.index("pending_monster_move")
    # per mode: visible key (static + intent + rows) -> {kind: count}
    seen = {m: defaultdict(lambda: defaultdict(int)) for m in views}
    seen_static = {m: defaultdict(lambda: defaultdict(int)) for m in views}
    info = defaultdict(lambda: {"max_hp": set(), "first_intent": set(), "start_static": set(), "intents": set()})
    leaf = defaultdict(lambda: [0, 0, 0])  # kind -> [leaves, leaves paused at a monster roll, stale intent shown]
    n_states = 0
    for enc in ENCOUNTERS:
        for seed in range(SEEDS):
            c = sts.Combat(deck, enc, seed=seed, no_death=True)
            c.advance()
            first = True
            while not c.is_over() and c.turn() <= TURNS:
                if not c.awaiting_action():
                    c.advance()
                    continue
                k = kinds(c)
                for mode, v in views.items():
                    ms, _ = v.monsters(c)
                    for slot, (static, intent, ent_rows, nz) in ms.items():
                        name = k[slot][0]
                        seen[mode][(static, intent, ent_rows)][name] += 1
                        seen_static[mode][(static, ent_rows)][name] += 1
                        if mode == "effects":
                            info[name]["intents"].add(k[slot][1])
                            if first:
                                info[name]["first_intent"].add(k[slot][1])
                                info[name]["start_static"].add((static, len(ent_rows)))
                n_states += 1
                if first:
                    for line in c.render().splitlines():
                        mm = LINE.match(line)
                        if mm:
                            info[mm.group(2)]["max_hp"].add(int(mm.group(4)))
                first = False
                # The one-turn End-turn leaf.
                # options(1): every random event pauses, as search's End-turn leaf.
                outs = [o for acts_, _, o in c.options(1) if any(a.is_end_turn for a in acts_)][0]
                t = outs[0][1]
                if not t.is_over():
                    after = kinds(t)
                    _, player = views["effects"].monsters(t)
                    paused = player[pmm] == 1
                    for slot, (name, intent_before) in k.items():
                        if slot not in after:
                            continue
                        leaf[name][0] += 1
                        if paused:
                            leaf[name][1] += 1
                            if after[slot][1] == intent_before:
                                leaf[name][2] += 1
                acts = c.legal_actions()
                c.step(rng.choice(acts))
                c.advance()
    lines.append(f"states: {n_states} decision states, {len(ENCOUNTERS)} encounters x {SEEDS} seeds, "
                 f"random legal actions, turns <= {TURNS}, Ironclad starter, no_death")
    lines.append("")
    lines.append("== Per kind: max HP seen, visible start (effects mode: non-varying monster columns, entity rows), "
                 "first-turn intents, intents seen ==")
    for name, d in sorted(info.items()):
        lines.append(f"{name}: max_hp {min(d['max_hp'])}-{max(d['max_hp'])}; first intent {sorted(d['first_intent'])}; "
                     f"intents seen {sorted(d['intents'])}")
        for st, nr in sorted(d["start_static"]):
            lines.append(f"    start static {[(n, x) for n, x in st if n != 'alive']} entity rows {nr}")
    for mode in views:
        lines.append("")
        lines.append(f"== {mode}: visible keys (static + intent + entity rows, hp/block/intent_damage left out) "
                     "shared by more than one kind ==")
        amb = defaultdict(int)
        tot = defaultdict(int)
        for key, ks in seen[mode].items():
            for name, n in ks.items():
                tot[name] += n
            if len(ks) > 1:
                for name, n in ks.items():
                    amb[name] += n
                lines.append(f"  {dict(ks)}  key {[(n, x) for n, x in key[0] + key[1] if n != 'alive']}"
                             f" rows {len(key[2])}")
        lines.append(f"-- {mode}: share of a kind's states whose visible key some other kind also shows --")
        for name in sorted(tot):
            lines.append(f"  {name}: {amb[name]}/{tot[name]} = {amb[name] / tot[name]:.2f}")
        lines.append(f"-- {mode}: same without the intent (max_hp, powers, can_split, entity rows only) --")
        amb2 = defaultdict(int)
        for key, ks in seen_static[mode].items():
            if len(ks) > 1:
                for name, n in ks.items():
                    amb2[name] += n
        for name in sorted(tot):
            lines.append(f"  {name}: {amb2[name]}/{tot[name]} = {amb2[name] / tot[name]:.2f}")
    lines.append("")
    lines.append("== One-turn End-turn leaves: paused at a monster roll (pending_monster_move = 1), "
                 "and of those, how many show the move just used as the intent ==")
    for name, (n, p, s) in sorted(leaf.items()):
        lines.append(f"  {name}: leaves {n}, paused at roll {p} ({p / max(n, 1):.2f}), stale intent shown {s}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
