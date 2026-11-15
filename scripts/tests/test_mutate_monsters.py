"""Tests for the mutated-monster bench, stage A
(scripts/analysis/mutate_monsters.py, docs/specs/mutated-monsters-a.md).
Run with `python scripts/tests/test_mutate_monsters.py` or pytest."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import mutate_monsters as mm  # noqa: E402
import sts  # noqa: E402

DECK = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]


OLD_HELD = ("GE-AttackLoss-Damage", "GE-AttackLoss-Weak", "GE-OppCard-PlainDamage",
            "GE-OppCard-Damage", "GE-TurnEnd-Weak", "GE-TurnEnd-Frail")


def start(encounter):
    return mm.start_state({"deck": DECK, "encounter": encounter, "seed": 7, "hp": 60, "character": "ironclad"})


def powers_of(c, slot):
    """{power name: amount} of monster `slot` (the board's words)."""
    return {p["name"]: p["amount"] for m in c.board()["monsters"] if m["slot"] == slot for p in m["powers"]}


def test_hp_scale():
    c = start("three_sentries")
    before = mm.living(c)
    assert len(before) == 3
    v = mm.with_hp_scale(c, 0.8)
    after = mm.living(v)
    for x, y in zip(before, after):
        assert y == (x[0], max(1, round(x[1] * 0.8)), max(1, round(x[2] * 0.8)))
        assert powers_of(v, x[0]) == powers_of(c, x[0])
    # only the monsters' HP changed: undoing it gives the same bytes back
    back = v
    for slot, hp, max_hp in before:
        back = back.with_monster_hp(slot, hp, max_hp)
    assert bytes(back.encode()) == bytes(c.encode())
    up = mm.living(mm.with_hp_scale(c, 1.25))
    assert all(y[1] == round(x[1] * 1.25) for x, y in zip(before, up))


def test_with_monster_hp_refuses():
    c = start("cultist")
    for slot, hp, max_hp in ((3, 10, 10), (0, 0, 10), (0, 11, 10)):
        with pytest_raises(ValueError):
            c.with_monster_hp(slot, hp, max_hp)
    assert mm.living(c.with_monster_hp(0, 7, 9)) == [(0, 7, 9)]


def test_mods_patch():
    c = start("three_sentries")
    names = sts.power_names()
    for m, patches in mm.MODS.items():
        for p in patches:
            if p[0] == "power":
                assert p[1] in names, p
        b = mm.mutate(c, patches)
        v = sts.Combat.decode(b)
        assert bytes(v.encode()) == b, m
        for p in patches:
            if p[0] == "power":
                for slot, _, _ in mm.living(v):
                    assert powers_of(v, slot).get(p[1], 0) >= p[2], (m, p)
    stack = mm.mutate(c, mm.MODS["metal4-hp0.85+sharp2-hp0.9"])
    two = mm.mutate(sts.Combat.decode(mm.mutate(c, mm.PAIRS["metal4-hp0.85"])), mm.PAIRS["sharp2-hp0.9"])
    assert stack == two
    lone = start("gremlin_nob")
    b = mm.mutate(lone, mm.MODS["str2"])
    assert len(mm.living(sts.Combat.decode(b))) == 1


def test_summary():
    def res(wins, hp_end):
        return [(w, hp_end if w else 0) for w in wins]
    rows = []
    for i in range(2):
        rows.append({"i": i, "floor": 5, "encounter": "x", "group": "elite", "hp": 50,
                     "parent": {"heuristic": res([1, 1], 40), "one": res([1, 1], 45), "two": res([1, 1], 46)},
                     "mods": {"hp1.25": {"heuristic": res([1, 0], 30), "one": res([0, 0], 30), "two": res([1, 1], 40)},
                              "hp0.8": {"heuristic": res([1, 1], 45), "one": res([1, 1], 48)}}})
    s = mm.summary(rows, ["hp1.25", "hp0.8"])
    h = s["hp1.25"]
    assert h["heuristic"]["win"][0] == -0.5 and h["one"]["win"][0] == -1.0 and h["two"]["win"][0] == 0.0
    assert h["novelty"]["win"][0] == -0.5 and h["repair"]["win"][0] == 1.0
    assert abs(h["heuristic"]["lost"][0] - ((50 - 30 + 50) / 2 - 10)) < 1e-9
    assert s["hp0.8"]["heuristic"]["win"][0] == 0.0 and s["hp0.8"]["verdict"] == "level" and "two" not in s["hp0.8"]
    assert mm.verdict({"heuristic": {"win": (-0.3, 0.05)}, "two": {"win": (-0.2, 0.05)}}) == "harder"
    assert mm.verdict({"heuristic": {"win": (-0.3, 0.05)}, "two": {"win": (0.2, 0.05)}}) == "mixed"
    assert mm.verdict({"heuristic": {"win": (0.3, 0.05)}}) == "easier"
    assert mm.outcome([(True, 30), (False, 0)], 50) == (0.5, 35.0)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


def test_split_intent_features():
    """Split Hits shows in the features' intent atoms as it lands: Jaw
    Worm's Chomp (11 x 1) as 5 x 2, a louse's rolled Bite as a plain attack
    at half its roll x 2 (docs/specs/mutated-monsters-b.md)."""
    f = sts.Features("effects")
    col = {n: f.monster_names.index(n) for n in ("intent_damage", "intent_damage_single", "intent_hits_single",
                                                  "intent_rolled_attack")}

    def intent(c):
        m = f.encode([c])["monsters"][0, 0]
        return {k: float(m[i]) for k, i in col.items()}

    c = sts.Combat(["Strike"] * 5 + ["Defend"] * 5, "jaw_worm", seed=1)
    plain = intent(c)
    split = intent(sts.Combat.decode(mm.mutate(c, mm.MODS["split"])))
    assert (plain["intent_damage_single"], plain["intent_hits_single"]) == (11, 1), plain
    assert (split["intent_damage_single"], split["intent_hits_single"], split["intent_damage"]) == (10, 2, 10), split
    for seed in range(40):
        c = sts.Combat(["Strike"] * 5 + ["Defend"] * 5, "two_louse", seed=seed)
        rolled = intent(c)["intent_rolled_attack"]
        if rolled > 0:
            s = intent(sts.Combat.decode(mm.mutate(c, mm.MODS["split"])))
            assert s["intent_rolled_attack"] == 0 and s["intent_hits_single"] == 2, s
            assert s["intent_damage_single"] == 2 * (rolled // 2), (rolled, s)
            break
    else:
        raise AssertionError("no louse Bite in 40 seeds")


def test_compare():
    W, L = (1, 40), (0, 0)

    def row(i, parent, mod):
        return {"i": i, "floor": 5, "encounter": "x", "group": "elite", "hp": 50, "parent": parent, "mods": {"sharp2": mod}}
    base = {"settings": {"mods": ["sharp2"]}, "rows": [
        row(0, {"heuristic": [W, L], "one": [W, W]}, {"heuristic": [L, L], "one": [L, L]}),
        row(1, {"heuristic": [W, W], "one": [W, W]}, {"heuristic": [W, L], "one": [L, L]})]}
    burst = {"settings": {"mods": ["sharp2", "ritual2"], "net": "b.pt"}, "rows": [
        row(0, {"one": [W, L]}, {"one": [W, W]}),
        row(1, {"one": [W, W]}, {"one": [W, L]}),
        row(2, {"one": [W, W]}, {"one": [W, W]})]}  # no base row: left out
    out = mm.compare(base, burst)
    assert list(out) == ["sharp2"]
    v = out["sharp2"]
    assert v["n"] == 2
    assert abs(v["gain"][0] - 1.0) < 1e-12 and abs(v["gain"][1] - 0.5) < 1e-12
    assert abs(v["cost"][0] + 0.5) < 1e-12 and abs(v["cut"] - 2.0) < 1e-12
    assert abs(v["parent"][0] + 0.25) < 1e-12


def test_odds():
    W, L = (1, 40), (0, 0)

    def row(i, parent, mod):
        return {"i": i, "floor": 5, "encounter": "x", "group": "boss", "hp": 50, "parent": parent, "mods": {"str2": mod}}
    # start 0: parent net 2/2 vs heuristic 1/2 (a*d/n = 2*1/4, b*c/n = 0); str2: net 1/2 vs heuristic 1/2 (1/4, 1/4)
    # start 1: parent net 1/2 vs heuristic 2/2 (0, 1*2/4); str2: both 0/2 (uninformative)
    rows = [row(0, {"heuristic": [W, L], "one": [W, W]}, {"heuristic": [W, L], "one": [W, L]}),
            row(1, {"heuristic": [W, W], "one": [W, L]}, {"heuristic": [L, L], "one": [L, L]})]
    o = mm.odds(rows, ["str2"], boot=50)
    assert abs(o["parent"]["lor"]) < 1e-12  # 0.5 / 0.5
    assert abs(o["str2"]["lor"]) < 1e-12  # log(0.25 / 0.25) - 0
    assert o["str2"]["informative"] == 1


def test_selected():
    specs = [{"group": g} for g in ("elite", "boss", "elite", "boss", "boss")]
    assert [n for n, _ in mm.selected(specs)] == [0, 1, 2, 3, 4]
    assert [n for n, _ in mm.selected(specs, 2, ["boss"])] == [3, 4]


# ---- generated enemies bench (docs/specs/generated-enemies-bench.md) ----

def _step(c, card=None):
    c = c.clone()
    c.step(sts.Action() if card is None else [a for a in c.legal_actions() if a.card == card][0])
    while not c.is_over() and not c.awaiting_action():
        c.advance()
    return c


def _main_path(rel):
    """`rel` in this checkout, else in the main checkout (data lives there)."""
    import subprocess
    here = os.path.join(os.path.dirname(__file__), "..", "..", rel)
    if os.path.exists(here):
        return here
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True,
                            text=True, cwd=os.path.dirname(__file__)).stdout.strip()
    return os.path.join(os.path.dirname(common), rel)


def test_gen_mechanics_rule():
    assert len(mm.GEN) == 24 and all(m.startswith("GE-") for m in mm.GEN)
    pairs = {tuple(m.split("-")[1:]) for m in mm.GEN}
    assert not pairs & mm.GEN_OFFICIAL and len(pairs) == 24
    assert len(mm.GEN_BATCH1) == 8 and len(set(mm.GEN_BATCH1)) == 8
    for t in mm.GEN_TRIGGERS:
        assert sum(m.split("-")[1] == t for m in mm.GEN_BATCH1) == 2
    assert mm.GEN_BATCH1[:2] == ["GE-TurnStart-Strength", "GE-TurnStart-Damage"]  # sha256 order is stable
    assert mm.GEN["GE-TurnStart-Block"] == [("pack", "GE-TurnStart-Block", 4)]
    assert mm.GEN["GE-OppCard-Damage"] == [("pack", "GE-OppCard-Damage", 1)]
    assert sts.load_content(mm.gen_pack()) == sts.load_content(mm.gen_pack())


def test_wide_grid_rule():
    # docs/specs/wider-generators.md: 100 mechanics, the old 24 unchanged.
    assert len(mm.GEN_ALL) == 100 and len(mm.WIDE) == 76 and not set(mm.WIDE) & set(mm.GEN)
    assert all(mm.GEN_ALL[m] == mm.GEN[m] for m in mm.GEN)
    pairs = {tuple(m.split("-")[1:]) for m in mm.GEN_ALL}
    assert len(pairs) == 100 and not pairs & mm.WIDE_OFFICIAL
    s = mm.WIDE_SPLIT
    assert sorted(sum(s.values(), [])) == sorted(mm.WIDE)
    assert len(s["whole_trigger"]) == 11 and len(s["whole_effect"]) == 8
    assert all(m.split("-")[1] == "Attacked" for m in s["whole_trigger"])
    assert all(m.split("-")[2] == "Wound" for m in s["whole_effect"])
    train = [m for m in mm.GEN if m not in OLD_HELD] + s["train"]
    seen_t = {m.split("-")[1] for m in train}
    seen_e = {m.split("-")[2] for m in train}
    held = list(OLD_HELD) + s["held_pairs"]
    assert held and all(m.split("-")[1] in seen_t and m.split("-")[2] in seen_e for m in held)
    assert "Attacked" not in seen_t and "Wound" not in seen_e
    assert mm.WIDE["GE-RoundEnd-Block"] == [("pack", "GE-RoundEnd-Block", 4)]
    assert mm.WIDE["GE-OppSkill-Damage"] == [("pack", "GE-OppSkill-Damage", 1)]
    assert mm.gen_power("GE-OppAttack-Wound")["hooks"][0]["condition"] == {"CardType": "Attack"}
    assert len(json.loads(mm.gen_pack())["powers"]) == 100
    sts.load_content(mm.gen_pack())


def test_wide_mechanics_fire():
    # Each new trigger and effect changes some play-out on Cultist (the probe of 2026-11-11).
    sts.load_content(mm.gen_pack())
    for m in ("GE-RoundEnd-Damage", "GE-Attacked-StrDown", "GE-AttackHit-Damage", "GE-OppAttack-Damage",
              "GE-OppAttack-Artifact", "GE-TurnStart-Dazed"):
        c = start("cultist")
        v = c.with_monster_power(0, m, 2)
        diff = 0
        for seed in range(6):
            r = sts.play_on([c.with_seed(seed), v.with_seed(seed)], limit=8, threads=1)
            diff += (r[0]["hp_end"], r[0]["won"]) != (r[1]["hp_end"], r[1]["won"])
        assert diff, m
    # OppSkill: a Skill gives the monster block, an Attack doesn't (the heuristic rarely blocks a Cultist).
    c = mm.start_state({"deck": ["Defend"] * 5 + ["Strike"] * 5, "encounter": "cultist", "seed": 7, "hp": 60,
                        "character": "ironclad"}).with_monster_power(0, "GE-OppSkill-Block", 2)
    c.step(next(a for a in c.legal_actions() if "Defend" in repr(a)))
    assert c.board()["monsters"][0]["block"] == 2
    c.step(next(a for a in c.legal_actions() if "Strike" in repr(a)))
    assert c.board()["monsters"][0]["block"] == 0
    # Wound: one card per firing (AddCard doesn't scale with stacks, Effect::scaled).
    c = mm.start_state({"deck": ["Strike"] * 10, "encounter": "cultist", "seed": 7, "hp": 60,
                        "character": "ironclad"}).with_monster_power(0, "GE-OppCard-Wound", 2)
    c.step(c.legal_actions()[0])
    assert dict(c.board()["piles"]["discard"]["cards"]).get("Wound") == 1


def test_with_monster_power_pack():
    sts.load_content(mm.gen_pack())
    c = start("cultist")
    with pytest_raises(ValueError):
        c.with_monster_power(0, "GE-NoSuchPower", 1)
    # turn start: PlainDamage 3 stacks hits the player for 3 more
    v = c.with_monster_power(0, "GE-TurnStart-PlainDamage", 3)
    assert _step(c).player_hp() - _step(v).player_hp() == 3
    # per hit: Block to the monster after a Strike lands; Strength likewise
    s = _step(c.with_monster_power(0, "GE-OppCard-Block", 1), "Strike")
    assert s.monster_numbers()[0][2] == 1
    s = _step(c.with_monster_power(0, "GE-AttackLoss-Strength", 1), "Strike")
    assert s.monster_numbers()[0][4] == 1
    # per card: Weak on the player before the card resolves (the Strike deals 4, not 6)
    s = _step(c.with_monster_power(0, "GE-OppCard-Weak", 1), "Strike")
    assert "[Weak 1]" in s.render().splitlines()[0] and s.monster_numbers()[0][1] == _step(c, "Strike").monster_numbers()[0][1] + 2
    # official names unchanged; pack content does not encode
    assert c.with_monster_power(0, "Strength", 2).monster_numbers()[0][4] == 2
    with pytest_raises(Exception):
        v.encode()
    # two pack powers on one monster share the binding; the same one twice stacks
    w = v.with_monster_power(0, "GE-TurnStart-PlainDamage", 1).with_monster_power(0, "GE-TurnEnd-Weak", 1)
    assert _step(c).player_hp() - _step(w).player_hp() == 4


def test_fickle_cycle():
    """docs/specs/fickle-enemy.md: an Attack opening punishes Attacks only;
    at the monster's turn start it loses n HP and names Power next."""
    sts.load_content(mm.fickle_pack())
    c = start("gremlin_nob")
    _, hp, max_hp = mm.living(c)[0]
    n = mm.fickle_n(max_hp)
    assert n == -(-max_hp * 5 // 100) and 1 <= n <= mm.FICKLE_MAX_N
    v = mm.variant(c, mm.FICKLE["FE-Attack"])
    assert _step(v, "Strike").monster_numbers()[0][4] == 1
    assert _step(v, "Defend").monster_numbers()[0][4] == 0
    s = _step(v)
    assert s.monster_numbers()[0][1] == hp - n
    assert f"FE-Power-{n}" in s.render() and f"FE-Attack-{n}" not in s.render()
    # a Skill opening punishes Defend; the Power opening's heal stops at max HP
    assert _step(mm.variant(c, mm.FICKLE["FE-Skill"]), "Defend").monster_numbers()[0][4] == 1
    assert _step(mm.variant(c, mm.FICKLE["FE-Power"])).monster_numbers()[0][1] == min(max_hp, hp + n)


def pytest_raises(exc):
    import contextlib

    @contextlib.contextmanager
    def cm():
        try:
            yield
        except exc:
            return
        raise AssertionError(f"{exc.__name__} not raised")
    return cm()


def test_with_seed_matches_decode():
    c = start("gremlin_nob")
    b = bytes(c.encode())
    seeds = [3, 11, 2**40 + 5]
    a = sts.play_on([sts.Combat.decode(b, seed=s) for s in seeds], limit=8)
    w = sts.play_on([sts.Combat.decode(b).with_seed(s) for s in seeds], limit=8)
    assert a == w


def test_bench_bytes_path_identical():
    """Parent and official mods through Combat variants play as the bytes path did."""
    for enc in ("gremlin_nob", "three_sentries"):
        c = start(enc)
        mods = ["str1", "sharp2", "c-hp1.5-str2"]
        seeds = [5, 17]
        old = [bytes(c.encode())] + [mm.mutate(c, mm.ALL[m]) for m in mods]
        ref = sts.play_on([sts.Combat.decode(b, seed=s) for b in old for s in seeds], limit=mm.bench.LIMIT, threads=1)
        ref = [[(bool(r["won"]), int(r["hp_end"])) for r in ref[i * 2:(i + 1) * 2]] for i in range(len(old))]
        new = [sts.Combat.decode(bytes(c.encode()))] + [mm.variant(c, mm.ALL[m]) for m in mods]
        assert mm.play_variants(new, seeds, "heuristic", 1) == ref


def test_gen_net_plays_pack_powers():
    """The 10-29 net (effects rows) plays a fight with a pack power on the monsters, and its leaf sees the power."""
    net = _main_path(mm.NET)
    if not os.path.exists(net):
        return  # no net in this checkout or the main one
    sts.load_content(mm.gen_pack())
    c = start("three_sentries")
    v = mm.variant(c, mm.GEN["GE-TurnStart-Strength"])
    ev = mm.bench.load_evaluator(net + "@hpb0.01@tsl1")
    res = sts.play_on([v.with_seed(1), c.with_seed(1)], evaluator=ev.evaluator, features=ev.features, limit=mm.bench.LIMIT, threads=1)
    assert all(r["turns"] > 0 for r in res)
    rows = list(ev.features.encode([v, c])["row_state"])
    assert rows.count(0) == rows.count(1) + 3  # a power row per Sentry


def test_gen_table():
    """A synthetic file: the net loses 3 HP more than the heuristic on one mechanic and not on its control."""
    rows = []
    for i in range(40):
        hp = 50
        same = [(True, 40 + i % 3)] * 2
        r = {"i": i, "floor": 1, "encounter": "gremlin_nob", "group": "elite", "hp": hp,
             "parent": {"heuristic": same, "one": same}, "mods": {}}
        for m in mm.LADDER:
            r["mods"][m] = {"heuristic": [(True, 30 + i % 3)] * 2, "one": [(True, 30 + i % 3)] * 2}
        r["mods"]["GE-TurnStart-Strength"] = {"heuristic": [(True, 31 + i % 3)] * 2, "one": [(True, 28 + i % 2)] * 2}
        r["mods"]["GE-TurnStart-Damage"] = {"heuristic": [(True, 40 + i % 3)] * 2, "one": [(True, 40 + i % 3)] * 2}
        rows.append(r)
    mods = list(mm.LADDER) + ["GE-TurnStart-Strength", "GE-TurnStart-Damage"]
    t = mm.gen_table(rows, mods)
    a, b = t["mechanics"]["GE-TurnStart-Strength"], t["mechanics"]["GE-TurnStart-Damage"]
    assert a["control"] == "c-hp0.8" and not a["outside"]  # 30-32 HP lost: the first ladder entry at that level
    assert b["control"] == "parent"
    assert 2.5 < a["cost"][0] < 3.5 and abs(b["cost"][0]) < 1e-9
    assert t["beyond_2se"] == 1 and not t["fail_fast"]



def test_start_combat_matches_variant():
    """docs/specs/genpack-product-depth.md: a start sent to depth_paired as (state, seed,
    powers) plays exactly as mm.variant(...).with_seed(seed), official and pack mods."""
    import depth_paired
    sts.load_content(mm.gen_pack())
    c = start("three_sentries")
    for m in ("str1", "GE-TurnEnd-Weak", "GE-OppCard-PlainDamage"):
        b, powers = mm.variant_parts(c, mm.ALL[m])
        for s in (5, 17):
            a = sts.play_on([depth_paired.start_combat({"state": b.hex(), "seed": s, "powers": powers})], limit=8, threads=1)
            w = sts.play_on([mm.variant(c, mm.ALL[m]).with_seed(s)], limit=8, threads=1)
            assert a == w, m
    k = mm.ALL["GE-TurnEnd-Weak"][0][2]
    assert mm.variant_parts(c, mm.ALL["GE-TurnEnd-Weak"])[1] == [[s, "GE-TurnEnd-Weak", k] for s in range(3)]


def test_guarded_fight_from_pack_start():
    """The product player's fight (stepped two-turn line) runs from a pack-power start in a
    worker that loads the pack, and plays the same fight twice."""
    import depth_paired
    c = start("cultist")
    b, powers = mm.variant_parts(c, mm.ALL["GE-TurnEnd-Weak"])
    spec = {"state": b.hex(), "seed": 3, "powers": powers}
    two = {"limit": 8, "turns": 2, "sample_k": 2, "max_nodes": 20_000}
    r = depth_paired.run_guarded([spec, spec], two, -1.0, "heuristic", 1, seed_per_turn=True, step_line=True,
                                 content=[mm.gen_pack()])
    assert r[0] == r[1] and r[0]["decisions"] > 0 and r[0]["hp_start"] == c.player_hp()
