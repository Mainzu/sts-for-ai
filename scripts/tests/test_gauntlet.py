"""Tests for the Act-1 gauntlet (scripts/gauntlet.py, docs/specs/gauntlet.md).
Run with `python scripts/tests/test_gauntlet.py` (plain asserts; every
`test_*` function runs) or with pytest."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import gauntlet  # noqa: E402

CELLS = [{"half": h, "cell": c, "deck": ["Strike"] * 5, "character": "ironclad"}
         for h in gauntlet.HALVES for c in range(5)]


def test_sequences_deterministic():
    a = gauntlet.sequences(50, cells=CELLS)
    assert a == gauntlet.sequences(50, cells=CELLS)
    for s in a:
        kinds = [f["kind"] for f in s["fights"]]
        assert kinds == list(gauntlet.SHAPE) and len(kinds) == 11 and kinds[-1] == "boss"
        encs = [f["encounter"] for f in s["fights"]]
        assert all(x != y for x, y in zip(encs, encs[1:]))
        elites = [f["encounter"] for f in s["fights"] if f["kind"] == "elite"]
        assert len(set(elites)) == 2
        for f in s["fights"]:
            assert f["encounter"] in gauntlet.POOLS[f["kind"]]
        assert s["half"] == gauntlet.HALVES[s["i"] % 2]
    assert len({f["seed"] for s in a for f in s["fights"]}) == 50 * 11
    assert gauntlet.sequences(3, first=10, cells=CELLS) == gauntlet.sequences(13, cells=CELLS)[10:]


def fake_play(lose_floor=None):
    calls = []

    def play(specs):
        calls.append(specs)
        k = len(calls) - 1
        return [{"won": k != lose_floor, "hp_start": s["hp"], "hp_end": min(80, s["hp"] - 10 + 6)} for s in specs]
    return play, calls


def test_hp_carries():
    seqs = gauntlet.sequences(3, cells=CELLS)
    play, calls = fake_play()
    rows = gauntlet.run(seqs, play)
    for r in rows:
        f = r["floors"]
        assert len(f) == 11 and r["cleared"]
        assert f[0]["hp_start"] == 80
        for k in range(10):
            want = f[k]["hp_end"] if k < 9 else gauntlet.rest(f[k]["hp_end"])
            assert f[k + 1]["hp_start"] == want, (k, f)
        assert f[10]["hp_start"] == min(80, f[9]["hp_end"] + 24)
    play, calls = fake_play(lose_floor=3)
    rows = gauntlet.run(seqs, play)
    assert all(len(r["floors"]) == 4 and not r["cleared"] and not r["floors"][-1]["won"] for r in rows)
    assert len(calls) == 4


REWARD_CELLS = [{"half": "train", "cell": 0, "deck": ["Strike", "Anger", "Clash+", "Cleave"], "character": "ironclad"},
                {"half": "train", "cell": 1, "deck": ["Bash", "Inflame", "Flex", "Anger+"], "character": "ironclad"},
                {"half": "held_out", "cell": 0, "deck": ["Defend", "Rage", "FTL", "Metallicize+"], "character": "ironclad"},
                {"half": "held_out", "cell": 1, "deck": ["Strike+", "Demon Form", "Rage+", "Anger"], "character": "ironclad"}]


def test_skip_reproduces():
    seqs = gauntlet.sequences(6, cells=CELLS)
    pools = gauntlet.reward_pools(REWARD_CELLS)
    for lose in (None, 3):
        play, _ = fake_play(lose_floor=lose)
        plain = gauntlet.run(seqs, play)
        play, _ = fake_play(lose_floor=lose)
        hooked = gauntlet.run(seqs, play, reward=gauntlet.chooser("skip", pools))
        for a, b in zip(plain, hooked):
            assert all(f["took"] is None and len(f["offer"]) == 3 for f in b["floors"] if "offer" in f)
            strip = [{k: v for k, v in f.items() if k not in ("offer", "took")} for f in b["floors"]]
            assert {**b, "floors": strip} == a


def test_offers_deterministic():
    pools = gauntlet.reward_pools(REWARD_CELLS)
    assert pools == {"train": ["Anger", "Clash", "Cleave", "Flex", "Inflame"],
                     "held_out": ["Anger", "Demon Form", "FTL", "Metallicize", "Rage"]}
    seqs = gauntlet.sequences(20, cells=CELLS)
    a = [[gauntlet.offer(s["i"], k, pools[s["half"]]) for k in range(10)] for s in seqs]
    assert a == [[gauntlet.offer(s["i"], k, pools[s["half"]]) for k in range(10)] for s in seqs]
    for s, offers in zip(seqs, a):
        for o in offers:
            assert len(set(o)) == 3 and all("+" not in c and c in pools[s["half"]] for c in o)
            if s["half"] == "train":
                assert not set(o) & {"Demon Form", "FTL", "Metallicize", "Rage"}
    for kind in ("skip", "random"):  # the offer doesn't depend on the chooser
        play, _ = fake_play()
        rows = gauntlet.run(seqs, play, reward=gauntlet.chooser(kind, pools))
        assert [[f["offer"] for f in r["floors"][:10]] for r in rows] == a


def test_deck_grows():
    seqs = gauntlet.sequences(3, cells=CELLS)
    pools = gauntlet.reward_pools(REWARD_CELLS)

    def take_first(k, items):
        offers = [gauntlet.offer(s["i"], k, pools[s["half"]]) for s, _, _ in items]
        return [(o, o[0]) for o in offers]
    play, calls = fake_play()
    rows = gauntlet.run(seqs, play, reward=take_first)
    for j, s in enumerate(seqs):
        want = list(s["deck"]) + [gauntlet.offer(s["i"], k, pools[s["half"]])[0] for k in range(10)]
        assert calls[10][j]["deck"] == want
        assert [f["took"] for f in rows[j]["floors"][:10]] == want[len(s["deck"]):]
        assert "offer" not in rows[j]["floors"][10]  # no reward after the boss
        assert calls[0][j]["deck"] == list(s["deck"])
    assert seqs[0]["deck"] == ["Strike"] * 5  # the input sequences are not changed


def test_sim_choose():
    """The sim chooser scores options on the same fights; ties go to skip."""
    seqs = gauntlet.sequences(2, cells=CELLS)
    pools = gauntlet.reward_pools(REWARD_CELLS)
    seen = []

    def sim_play(specs):
        seen.append(specs)
        # a deck holding "Flex" or "Rage" wins with 70 HP, others lose
        return [{"won": any(c in ("Flex", "Rage") for c in s["deck"]), "hp_end": 70} for s in specs]
    items = [(s, 40, list(s["deck"])) for s in seqs]
    offers = [["Anger", "Flex", "Clash"], ["Cleave", "Clash", "Anger"]]
    out = gauntlet.sim_choose(9, items, offers, sim_play)
    assert out == [(offers[0], "Flex"), (offers[1], None)]
    specs = seen[0]
    assert len(specs) == 2 * 4 * gauntlet.SIM_FIGHTS
    assert all(sp["hp"] == gauntlet.rest(40) and sp["encounter"] in gauntlet.BOSSES for sp in specs)
    per = gauntlet.SIM_FIGHTS
    opts = [specs[o * per:(o + 1) * per] for o in range(4)]
    assert all([sp["seed"] for sp in x] == [sp["seed"] for sp in opts[0]] for x in opts)
    assert all([sp["encounter"] for sp in x] == [sp["encounter"] for sp in opts[0]] for x in opts)
    assert opts[2][0]["deck"] == list(seqs[0]["deck"]) + ["Flex"] and opts[0][0]["deck"] == list(seqs[0]["deck"])
    assert all(sp["seed"] >= gauntlet.SIM_SEED_BASE for sp in specs)


def test_sim_boss():
    """With boss on, each option adds common boss-pool fights at rest(hp);
    a card that only wins boss fights beats skip; at k 9 nothing changes."""
    seqs = gauntlet.sequences(1, cells=CELLS)
    items = [(seqs[0], 40, list(seqs[0]["deck"]))]
    offers = [["Anger", "Inflame", "Clash"]]
    seen = []

    def sim_play(specs):
        seen.append(specs)
        # hallways always won at 40 HP; boss fights won only with Inflame
        return [{"won": s["group"] != "boss" or "Inflame" in s["deck"], "hp_end": 40} for s in specs]
    assert gauntlet.sim_choose(0, items, offers, sim_play) == [(offers[0], None)]
    plain = seen[-1]
    assert gauntlet.sim_choose(0, items, offers, sim_play, boss=True) == [(offers[0], "Inflame")]
    specs, per = seen[-1], gauntlet.SIM_FIGHTS
    assert len(specs) == 4 * 2 * per
    opts = [specs[o * 2 * per:(o + 1) * 2 * per] for o in range(4)]
    assert [(sp["encounter"], sp["seed"]) for sp in opts[0][:per]] == [(sp["encounter"], sp["seed"]) for sp in plain[:per]]
    boss = opts[0][per:]
    assert all(sp["encounter"] in gauntlet.BOSSES and sp["group"] == "boss" and sp["hp"] == gauntlet.rest(40) for sp in boss)
    assert [sp["seed"] for sp in boss] == [gauntlet.SIM_SEED_BASE + seqs[0]["i"] * 10_000 + 50 + m for m in range(per)]
    assert all([(sp["encounter"], sp["seed"]) for sp in x] == [(sp["encounter"], sp["seed"]) for sp in opts[0]] for x in opts)
    gauntlet.sim_choose(9, items, offers, sim_play)
    a = seen[-1]
    gauntlet.sim_choose(9, items, offers, sim_play, boss=True)
    assert seen[-1] == a


STARTER = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]


def test_rest_choose():
    """The rest chooser plays the sequence's boss, the same seeds per option;
    heal at rest(hp), upgrades at hp; ties go to heal."""
    seqs = gauntlet.sequences(2, cells=CELLS)
    items = [(s, 70, list(STARTER)) for s in seqs]
    seen = []

    def sim_play(specs):
        seen.append(specs)
        return [{"won": "Bash+" in s["deck"], "hp_end": 50} for s in specs]
    assert gauntlet.rest_choose(items, sim_play) == ["Bash", "Bash"]
    specs, per = seen[0], gauntlet.REST_FIGHTS
    assert per == 16 and len(specs) == 2 * 4 * per
    for j, s in enumerate(seqs):
        opts = [specs[(j * 4 + o) * per:(j * 4 + o + 1) * per] for o in range(4)]
        assert all(sp["encounter"] == s["fights"][-1]["encounter"] and sp["group"] == "boss" for x in opts for sp in x)
        assert all(sp["hp"] == gauntlet.rest(70) and sp["deck"] == STARTER for sp in opts[0])
        for x, name in zip(opts[1:], ("Strike", "Defend", "Bash")):
            want = list(STARTER)
            want[want.index(name)] = name + "+"
            assert all(sp["hp"] == 70 and sp["deck"] == want for sp in x)
        base = gauntlet.SIM_SEED_BASE + s["i"] * 10_000 + 1000
        assert [sp["seed"] for sp in opts[0]] == list(range(base, base + per))
        assert all([sp["seed"] for sp in x] == [sp["seed"] for sp in opts[0]] for x in opts)
    assert gauntlet.rest_choose(items, lambda specs: [{"won": True, "hp_end": 50} for _ in specs]) == [None, None]
    n = len(seen)
    assert gauntlet.rest_choose([(seqs[0], 70, ["Strike+", "Wound"])], sim_play) == [None]
    assert len(seen) == n  # nothing upgradable: heal without simulating


def test_rest_hook_run():
    seqs = gauntlet.sequences(2, cells=CELLS)
    play, calls = fake_play()
    rows = gauntlet.run(seqs, play, rest_hook=lambda items: ["Strike", None])
    assert calls[10][0]["deck"] == ["Strike+"] + ["Strike"] * 4
    assert calls[10][0]["hp"] == rows[0]["floors"][9]["hp_end"]
    assert calls[10][1]["hp"] == gauntlet.rest(rows[1]["floors"][9]["hp_end"])
    assert rows[0]["floors"][10]["rest"] == "Strike" and rows[1]["floors"][10]["rest"] == "heal"
    assert all("rest" not in f for r in rows for f in r["floors"][:10])
    play, _ = fake_play()
    assert all("rest" not in f for r in gauntlet.run(seqs, play) for f in r["floors"])


def test_remove_hook_run():
    """A removal after floor REMOVE_FLOOR leaves later decks one card short
    and is recorded on that floor's row; no hook leaves rows unchanged."""
    seqs = gauntlet.sequences(2, cells=CELLS)
    play, calls = fake_play()
    rows = gauntlet.run(seqs, play, remove_hook=lambda items: ["Strike", None])
    k = gauntlet.REMOVE_FLOOR
    assert k == 5
    assert calls[k][0]["deck"] == ["Strike"] * 5
    assert all(c[0]["deck"] == ["Strike"] * 4 for c in calls[k + 1:])
    assert all(c[1]["deck"] == ["Strike"] * 5 for c in calls)
    assert rows[0]["floors"][k]["removed"] == "Strike" and rows[1]["floors"][k]["removed"] is None
    assert all("removed" not in f for r in rows for j, f in enumerate(r["floors"]) if j != k)
    play, _ = fake_play()
    assert all("removed" not in f for r in gauntlet.run(seqs, play) for f in r["floors"])
    play, _ = fake_play(lose_floor=2)
    asked = []
    gauntlet.run(seqs, play, remove_hook=lambda items: asked.append(items) or [None] * len(items))
    assert not asked  # nobody alive at the removal: the hook isn't asked


def test_path_alt_deterministic():
    """The hallway that replaces a skipped elite is hard, never the previous
    floor's encounter, fixed by (i, k), and not the same at both elite floors."""
    for i in range(6):
        for k in (5, 8):
            a = gauntlet.alt_fight(i, k, "three_louse")
            assert a in gauntlet.HARD and a != "three_louse"
            assert a == gauntlet.alt_fight(i, k, "three_louse")
    assert any(gauntlet.alt_fight(i, 5, "looter") != gauntlet.alt_fight(i, 8, "looter") for i in range(6))


def test_path_hook_run():
    """A hook that skips every elite fights alt_fight's hallway on the elite
    floors with the elite fight's seed, everything else as without a hook;
    a hook that always fights gives the no-hook rows plus path: elite."""
    seqs = gauntlet.sequences(3, cells=CELLS)
    play, base_calls = fake_play()
    base = gauntlet.run(seqs, play)
    play, calls = fake_play()
    rows = gauntlet.run(seqs, play, path_hook=lambda k, items: [False] * len(items))
    for k in range(11):
        for s, spec, b in zip(seqs, calls[k], base_calls[k]):
            if gauntlet.SHAPE[k] == "elite":
                prev = s["fights"][k - 1]["encounter"]
                assert spec["encounter"] == gauntlet.alt_fight(s["i"], k, prev) and spec["encounter"] != prev
                assert spec["encounter"] in gauntlet.HARD and spec["group"] == "hallway"
                assert spec["seed"] == b["seed"] and spec["hp"] == b["hp"] and spec["deck"] == b["deck"]
            else:
                assert spec == b
    keys = ("hp_start", "hp_end", "won")
    for r, b in zip(rows, base):
        for k, (f, g) in enumerate(zip(r["floors"], b["floors"])):
            if gauntlet.SHAPE[k] == "elite":
                assert f["path"] == "hallway" and f["encounter"] in gauntlet.HARD
                assert {x: f[x] for x in keys} == {x: g[x] for x in keys}
            else:
                assert f == g and "path" not in f
    play, _ = fake_play()
    kept = gauntlet.run(seqs, play, path_hook=lambda k, items: [True] * len(items))
    for r, b in zip(kept, base):
        for k, (f, g) in enumerate(zip(r["floors"], b["floors"])):
            assert f == ({**g, "path": "elite"} if gauntlet.SHAPE[k] == "elite" else g)
    assert all("path" not in f for r in base for f in r["floors"])


def test_path_hp_rule():
    seqs = gauntlet.sequences(2, cells=CELLS)
    items = [(seqs[0], 40, list(STARTER)), (seqs[1], 39, list(STARTER))]
    assert gauntlet.path_hp(40)(5, items) == [True, False]
    assert gauntlet.path_skip(5, items) == [False, False]


def test_remove_strike():
    seqs = gauntlet.sequences(3, cells=CELLS)
    items = [(seqs[0], 50, list(STARTER)), (seqs[1], 50, ["Defend", "Strike+"]), (seqs[2], 50, ["Defend", "Bash"])]
    assert gauntlet.remove_strike(items) == ["Strike", "Strike+", None]


def test_remove_sim():
    """Options keep + each distinct name, scored like sim_choose on common
    seeds clear of the reward chooser's; ties keep."""
    seqs = gauntlet.sequences(2, cells=CELLS)
    items = [(s, 60, list(STARTER)) for s in seqs]
    seen = []

    def sim_play(specs):
        seen.append(specs)
        return [{"won": s["deck"].count("Defend") < 4, "hp_end": 50} for s in specs]
    k = gauntlet.REMOVE_FLOOR
    assert gauntlet.remove_sim(k, items, sim_play, boss=True) == ["Defend", "Defend"]
    specs, per = seen[0], gauntlet.SIM_FIGHTS
    assert len(specs) == 2 * 4 * 2 * per  # 2 sequences x (keep, Strike, Defend, Bash) x (next floor, boss)
    for j, s in enumerate(seqs):
        opts = [specs[(j * 4 + o) * 2 * per:(j * 4 + o + 1) * 2 * per] for o in range(4)]
        assert all(sp["deck"] == STARTER for sp in opts[0])
        for x, name in zip(opts[1:], ("Strike", "Defend", "Bash")):
            want = list(STARTER)
            del want[want.index(name)]
            assert all(sp["deck"] == want for sp in x)
        assert all([(sp["encounter"], sp["seed"]) for sp in x] == [(sp["encounter"], sp["seed"]) for sp in opts[0]]
                   for x in opts)
        base = gauntlet.SIM_SEED_BASE + s["i"] * 10_000 + k * 100
        assert [sp["seed"] for sp in opts[0]] == [base + 70 + m for m in range(per)] + [base + 80 + m for m in range(per)]
    # seeds disjoint from the reward chooser's for the same sequences and floor
    gauntlet.sim_choose(k, items, [["Anger", "Flex", "Clash"]] * 2, sim_play, boss=True)
    assert not {sp["seed"] for sp in seen[0]} & {sp["seed"] for sp in seen[-1]}
    assert gauntlet.remove_sim(k, items, lambda specs: [{"won": True, "hp_end": 50} for _ in specs]) == [None, None]


def test_read_pairs():
    def res(cleared_floors):
        seqs = []
        for i, n in enumerate(cleared_floors):
            floors = [{"encounter": f"e{k}", "hp_start": 50, "hp_end": 50, "won": True} for k in range(n)]
            if n < 11:
                floors.append({"encounter": f"e{n}", "hp_start": 20, "hp_end": 0, "won": False})
            seqs.append({"i": i, "half": gauntlet.HALVES[i % 2], "cell": 0, "floors": floors, "cleared": n == 11})
        return {"settings": {}, "sequences": seqs}
    a = res([11, 11, 11, 3])
    b = res([11, 5, 10, 3])
    s = gauntlet.summary(a, b)["all"]
    assert s["n"] == 4 and s["clear_a"] == 0.75 and s["clear_b"] == 0.25 and s["diff"] == 0.5
    assert s["deaths_floor_a"][3] == 1 and sum(s["deaths_floor_a"]) == 1
    assert s["deaths_floor_b"][5] == 1 and s["deaths_floor_b"][10] == 1 and s["deaths_floor_b"][3] == 1
    assert s["deaths_enc_b"] == {"e5": 1, "e10": 1, "e3": 1}
    assert s["boss_both"] == 2 and s["floors_a"] == (33 + 3) / 4


def test_run_specs_mixed_hp_order():
    """bench.run_specs groups specs by (hp, character); a floor's mixed HPs
    must come back in input order (fake engine, no fights played)."""
    import bench
    real = bench.sts.run

    def fake(kind, fights, hp=None, character=None, **kw):
        return [{"seed": seed, "hp": hp} for _, _, seed in fights]
    bench.sts.run = fake
    try:
        hps = [80, 50, 80, 30, 50]
        specs = [{"encounter": "cultist", "deck": ["Strike"], "seed": i, "hp": h, "character": "ironclad"}
                 for i, h in enumerate(hps)]
        res = bench.run_specs(specs)
    finally:
        bench.sts.run = real
    assert [(r["seed"], r["hp"]) for r in res] == list(enumerate(hps))


class FakeLadder:
    """Stands in for ladder in play_cmd: CELLS, and a player that wins every
    fight losing `loss` HP (heal 6 on a win, as the engine does)."""
    def __init__(self, loss):
        self.loss, self.calls, self.line = loss, 0, None

    def pool_cells(self):
        return [{**c, "deck": ["Strike", "Anger", "Flex", "Inflame"]} for c in CELLS]

    def play_bench(self, specs, player, threads):
        self.calls += 1
        return self._play(specs)

    def play_two_turn(self, specs, player, threads, seed_per_turn=False, step_line=False, content=None):
        self.line = seed_per_turn
        self.step = step_line
        self.content = content
        return self._play(specs)

    def _play(self, specs):
        return [{"won": s["hp"] > self.loss, "hp_start": s["hp"], "hp_end": min(80, s["hp"] - self.loss + 6)}
                for s in specs]


def play_cmd(tmp, loss, *argv):
    fake = FakeLadder(loss)
    real = sys.modules.get("ladder")
    sys.modules["ladder"] = fake
    writes = []
    real_dump = gauntlet.json.dump

    def dump(obj, f, **kw):
        writes.append(len(obj["sequences"]))
        real_dump(obj, f, **kw)
    gauntlet.json.dump = dump
    try:
        gauntlet.main(["play", "p", "--out", tmp, *argv])
    finally:
        gauntlet.json.dump = real_dump
        if real is None:
            del sys.modules["ladder"]
        else:
            sys.modules["ladder"] = real
    with open(tmp, encoding="utf-8") as f:
        return gauntlet.json.load(f), writes


def tmpfile(name):
    import tempfile
    return os.path.join(tempfile.mkdtemp(), name)


def test_blocks_same_rows():
    for extra in ([], ["--rewards", "random"]):
        one, w1 = play_cmd(tmpfile("a.json"), 9, "--sequences", "23", "--block", "100", *extra)
        many, w2 = play_cmd(tmpfile("b.json"), 9, "--sequences", "23", "--block", "5", *extra)
        assert one == many
        assert w1 == [23, 23] and w2 == [5, 10, 15, 20, 23, 23], (w1, w2)


def test_against_stops():
    import gauntlet_protocol as gp
    weak, _ = play_cmd(tmpfile("weak.json"), 12, "--sequences", "300", "--block", "300")
    strong, _ = play_cmd(tmpfile("strong.json"), 7, "--sequences", "300", "--block", "300")
    ctl = tmpfile("ctl.json")
    with open(ctl, "w", encoding="utf-8") as f:
        gauntlet.json.dump(weak, f)
    got, writes = play_cmd(tmpfile("c.json"), 7, "--sequences", "300", "--block", "20", "--against", ctl)
    rows = {r["i"]: r for r in strong["sequences"]}
    wr = {r["i"]: r for r in weak["sequences"]}
    dh = [gp.end_hp(rows[i]) - gp.end_hp(wr[i]) for i in range(300)]
    dc = [float(rows[i]["cleared"]) - float(wr[i]["cleared"]) for i in range(300)]
    want = gp.sprt(dh, dc, 1.5, 50)
    assert want[0] == "pass", want
    assert (got["protocol"]["verdict"], got["protocol"]["n"]) == want
    blocks = -(-want[1] // 20)
    assert len(got["sequences"]) == 20 * blocks and len(writes) == blocks + 1, (len(got["sequences"]), writes)
    # the other way round fails; a resumed play checks before playing more
    fail, _ = play_cmd(tmpfile("d.json"), 12, "--sequences", "300", "--block", "20", "--against", got_path(got, ctl))
    assert fail["protocol"]["verdict"] == "fail"


def got_path(body, ctl):
    p = ctl.replace("ctl.json", "strong-ctl.json")
    with open(p, "w", encoding="utf-8") as f:
        gauntlet.json.dump(body, f)
    return p


def test_against_resume_and_refuse():
    ctl = tmpfile("ctl.json")
    body, _ = play_cmd(ctl, 12, "--sequences", "100", "--block", "100")
    out = tmpfile("c.json")
    first, _ = play_cmd(out, 7, "--sequences", "100", "--block", "20", "--against", ctl)
    assert first["protocol"]["verdict"] != "open"
    lad = FakeLadder(7)
    real = sys.modules.get("ladder")
    sys.modules["ladder"] = lad
    try:
        gauntlet.main(["play", "p", "--out", out, "--sequences", "100", "--block", "20", "--against", ctl])
    finally:
        if real is None:
            del sys.modules["ladder"]
        else:
            sys.modules["ladder"] = real
    assert lad.calls == 0
    body["settings"]["seed"] += 1
    with open(ctl, "w", encoding="utf-8") as f:
        gauntlet.json.dump(body, f)
    try:
        play_cmd(tmpfile("e.json"), 7, "--sequences", "10", "--against", ctl)
    except SystemExit as e:
        assert "seed or shape" in str(e)
    else:
        raise AssertionError("mismatched control accepted")


def test_against_refuses_other_settings():
    """kb-adoption probes: a one-turn screen against a two-turn file, or a
    headline read against a cell file, must not pair silently."""
    ctl = tmpfile("ctl.json")
    body, _ = play_cmd(ctl, 12, "--sequences", "20", "--block", "20")

    def refused(*argv):
        try:
            play_cmd(tmpfile("r.json"), 7, "--sequences", "20", "--against", ctl, *argv)
        except SystemExit as e:
            return str(e)
        raise AssertionError(f"mismatched control accepted: {argv}")
    msg = refused("--two-turn", "--one-turn-floors", "3")
    assert "two_turn (control False, this run True)" in msg and "one_turn_floors (control None, this run 3)" in msg, msg
    msg = refused("--start", "starter", "--rewards", "sim", "--sim-boss")
    assert all(f in msg for f in ("start", "rewards", "sim_boss")), msg
    # a declared field is allowed, the others are still named
    msg = refused("--rewards", "sim", "--sim-boss", "--vary", "rewards")
    assert "sim_boss" in msg and "rewards (" not in msg, msg
    got, _ = play_cmd(tmpfile("v.json"), 7, "--sequences", "20", "--against", ctl,
                      "--rewards", "random", "--vary", "rewards")
    assert got["protocol"]["vary"] == ["rewards"] and got["protocol"]["n"] == 20, got["protocol"]
    # the price after the player's @ is a setting; the net itself is the arm
    body["settings"]["player"] = "q@hpe0.01"
    with open(ctl, "w", encoding="utf-8") as f:
        gauntlet.json.dump(body, f)
    assert "price (control hpe0.01, this run None)" in refused()
    got, _ = play_cmd(tmpfile("w.json"), 7, "--sequences", "20", "--against", ctl, "--vary", "price")
    assert got["protocol"]["vary"] == ["price"]
    body["settings"]["player"] = "q"
    with open(ctl, "w", encoding="utf-8") as f:
        gauntlet.json.dump(body, f)
    got, _ = play_cmd(tmpfile("x.json"), 7, "--sequences", "20", "--against", ctl)
    assert "vary" not in got["protocol"]


def test_line_seed_seeds():
    """docs/specs/line-seed.md: with seed_per_turn every two-turn search of a
    combat turn gets one seed (the turn's), without it the decision index's."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
    import json
    import depth_paired
    import bench
    spec = depth_paired.fights("held_out", ("hallway",), 1)[0]
    two = {"limit": bench.LIMIT, "turns": 2, "sample_k": 2, "max_nodes": 2000}
    real = depth_paired.sts.search

    def run(seed_per_turn):
        calls = []

        def rec(c, *a, **kw):
            if "seed" in kw:
                calls.append((c.turn(), kw["seed"]))
            return real(c, *a, **kw)
        depth_paired.sts.search = rec
        try:
            depth_paired.guarded_fight((spec, two, -1.0, "heuristic", 0, 3, seed_per_turn))
        finally:
            depth_paired.sts.search = real
        return calls

    base = spec["seed"] * 1009
    per_turn = run(True)
    assert len(per_turn) > 1
    turns = {}
    for t, seed in per_turn:
        turns.setdefault(t, set()).add(seed)
    assert all(seeds == {(base + t) % 2**64} for t, seeds in turns.items()), turns
    assert len({next(iter(s)) for s in turns.values()}) == len(turns)
    per_decision = run(False)
    assert [seed for _, seed in per_decision] == [(base + n) % 2**64 for n in range(len(per_decision))]
    key = lambda flag: depth_paired.row_key(two, -1.0, "heuristic", 0, flag)  # noqa: E731
    assert key(False) == json.dumps([two, -1.0, "heuristic"], sort_keys=True)  # old partial rows still match
    assert key(True) != key(False)


def test_line_seed_flag():
    try:
        play_cmd(tmpfile("x.json"), 9, "--sequences", "3", "--line-seed")
    except SystemExit as e:
        assert "--two-turn" in str(e)
    else:
        raise AssertionError("--line-seed without --two-turn accepted")
    for flags, want in (([], None), (["--two-turn"], None), (["--two-turn", "--line-seed"], True)):
        fake = FakeLadder(9)
        real = sys.modules.get("ladder")
        sys.modules["ladder"] = fake
        out = tmpfile("y.json")
        try:
            gauntlet.main(["play", "p", "--out", out, "--sequences", "3", *flags])
        finally:
            if real is None:
                del sys.modules["ladder"]
            else:
                sys.modules["ladder"] = real
        with open(out, encoding="utf-8") as f:
            body = gauntlet.json.load(f)
        assert body["settings"].get("line_seed") == want, (flags, body["settings"])
        assert fake.line == (want or False) if "--two-turn" in flags else fake.line is None


class FakeStepCombat:
    """A combat of four decisions (two per turn) that records what was stepped."""
    def __init__(self):
        self.steps = []

    def turn(self):
        return 1 + len(self.steps) // 2

    def is_over(self):
        return len(self.steps) >= 4

    def step(self, a):
        assert not self.is_over()
        self.steps.append(a)

    def player_hp(self):
        return 50

    def score(self):
        return 1.5

    def won(self):
        return True


class FakeStepSts:
    """Stands in for sts in depth_paired: one-turn search prefers A, two-turn
    search prefers B with the line B, A and no cut. With `tie`, one-turn
    prefers B and two-turn ties A and B (line A, B): at margin 0 the guard
    keeps one-turn's B, so no line may be stepped."""
    def __init__(self, tie=False):
        self.calls = []
        self.tie = tie

    def Combat(self, *a, **kw):  # noqa: N802
        return FakeStepCombat()

    def search(self, c, ev, features=None, limit=None, seed=None, **two):
        self.calls.append(seed)
        if self.tie:
            if seed is None:
                return {"action": "B", "options": [(["A"], 0.5), (["B"], 1.0)], "nodes": 1, "leaves": 1,
                        "cuts": 0, "line": ["B"]}
            return {"action": "A", "options": [(["A"], 1.0), (["B"], 1.0)], "nodes": 9, "leaves": 3, "cuts": 0,
                    "line": ["A", "B"]}
        if seed is None:
            return {"action": "A", "options": [(["A"], 1.0), (["B"], 0.5)], "nodes": 1, "leaves": 1, "cuts": 0,
                    "line": ["A"]}
        return {"action": "B", "options": [(["A"], 0.5), (["B"], 1.0)], "nodes": 9, "leaves": 3, "cuts": 0,
                "line": ["B", "A"]}


def test_step_line_steps():
    """docs/specs/line-step.md: with step_line the whole line of an uncut
    two-turn search is played without further searches; every stepped action
    counts as a decision, the first as the override; off, every decision
    searches. Needs seed_per_turn and top_k 0 and margin <= 0; row_key differs."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
    import json
    import depth_paired
    two = {"limit": 16, "turns": 2, "sample_k": 2, "max_nodes": 2000}
    spec = {"deck": ["Strike"], "encounter": "jaw_worm", "seed": 7, "hp": 50, "character": "ironclad"}
    real = depth_paired.sts

    def run(step_line, seed_per_turn=True, top_k=0, margin=-1.0, tie=False):
        fake = FakeStepSts(tie)
        depth_paired.sts = fake
        try:
            r = depth_paired.guarded_fight((spec, two, margin, "heuristic", top_k, 3, seed_per_turn, step_line))
        finally:
            depth_paired.sts = real
        return r, fake

    r, fake = run(True)
    assert len(fake.calls) == 4 and [s is None for s in fake.calls] == [True, False, True, False], fake.calls
    assert r["decisions"] == 4 and r["override"] == 2 and r["cut"] == 0 and r["won"], r
    r, fake = run(False)
    assert len(fake.calls) == 8, fake.calls
    assert r["decisions"] == 4 and r["override"] == 4, r
    # margin 0, two-turn ties with one-turn's choice: the guard keeps one-turn's
    # pick, so every decision is today's single step and searches again
    r, fake = run(True, margin=0.0, tie=True)
    assert len(fake.calls) == 8 and r["decisions"] == 4 and r["override"] == 0, (fake.calls, r)
    for kw in ({"seed_per_turn": False}, {"top_k": 2}, {"margin": 0.1}):
        try:
            run(True, **kw)
        except ValueError:
            pass
        else:
            raise AssertionError(f"step_line accepted with {kw}")
    key = lambda **kw: depth_paired.row_key(two, -1.0, "heuristic", 0, True, **kw)  # noqa: E731
    assert key() == json.dumps([two, -1.0, "heuristic", "turn"], sort_keys=True)  # stage-1 rows still match
    assert key(step_line=True) != key()
    assert depth_paired.row_key(two, -1.0, "heuristic") == json.dumps([two, -1.0, "heuristic"], sort_keys=True)


def test_step_line_flag():
    try:
        play_cmd(tmpfile("x.json"), 9, "--sequences", "3", "--two-turn", "--step-line")
    except SystemExit as e:
        assert "--line-seed" in str(e)
    else:
        raise AssertionError("--step-line without --line-seed accepted")
    for flags, want in ((["--two-turn", "--line-seed"], None), (["--two-turn", "--line-seed", "--step-line"], True)):
        fake = FakeLadder(9)
        real = sys.modules.get("ladder")
        sys.modules["ladder"] = fake
        out = tmpfile("z.json")
        try:
            gauntlet.main(["play", "p", "--out", out, "--sequences", "3", *flags])
        finally:
            if real is None:
                del sys.modules["ladder"]
            else:
                sys.modules["ladder"] = real
        with open(out, encoding="utf-8") as f:
            body = gauntlet.json.load(f)
        assert body["settings"].get("step_line") == want, (flags, body["settings"])
        assert fake.step == bool(want)
    assert "step_line" in gauntlet.VARY


def test_chooser_player():
    """docs/specs/chooser-player.md: --chooser sends the sim chooser's fights
    to its own player; floors and the rest-site chooser keep the fight player."""
    class Recording(FakeLadder):
        def __init__(self, loss):
            super().__init__(loss)
            self.players = []

        def play_bench(self, specs, player, threads):
            self.players.append(player)
            return self._play(specs)

    def run(*argv):
        lad = Recording(7)
        real = sys.modules.get("ladder")
        sys.modules["ladder"] = lad
        try:
            gauntlet.main(["play", "p", *argv])
        finally:
            if real is None:
                del sys.modules["ladder"]
            else:
                sys.modules["ladder"] = real
        return lad.players

    out = tmpfile("ch.json")
    players = run("--out", out, "--sequences", "4", "--start", "starter", "--rewards", "sim", "--sim-boss",
                  "--chooser", "other", "--rest", "sim")
    assert len(players) == 22 and players[0::2] == ["p"] * 11 and players[1:20:2] == ["other"] * 10, players
    assert players[20] == "p"  # the rest-site chooser keeps the fight player
    with open(out, encoding="utf-8") as f:
        ch = gauntlet.json.load(f)
    assert ch["settings"]["chooser"] == "other"
    plain = tmpfile("plain.json")
    assert set(run("--out", plain, "--sequences", "4", "--start", "starter", "--rewards", "sim", "--sim-boss")) == {"p"}
    same = tmpfile("same.json")
    run("--out", same, "--sequences", "4", "--start", "starter", "--rewards", "sim", "--sim-boss", "--chooser", "p")
    with open(plain, encoding="utf-8") as f, open(same, encoding="utf-8") as g:
        a, b = gauntlet.json.load(f), gauntlet.json.load(g)
    assert a["sequences"] == b["sequences"] and "chooser" not in a["settings"] and b["settings"]["chooser"] == "p"
    try:
        run("--out", tmpfile("bad.json"), "--sequences", "2", "--chooser", "other")
    except SystemExit as e:
        assert "--rewards sim" in str(e)
    else:
        raise AssertionError("--chooser without --rewards sim accepted")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


def test_rest_choose_margin():
    """--rest-fights sets fights per option; --rest-margin keeps heal unless
    the best upgrade beats it by z paired standard errors."""
    seqs = gauntlet.sequences(1, cells=CELLS)
    items = [(seqs[0], 70, list(STARTER))]
    seen = []

    def noisy(specs):  # Bash+ wins 5 of 8 seeds, heal 4 of 8: a lucky edge
        seen.append(specs)
        base = gauntlet.SIM_SEED_BASE + seqs[0]["i"] * 10_000 + 1000
        return [{"won": (s["seed"] - base) < (5 if "Bash+" in s["deck"] else 4), "hp_end": 50} for s in specs]
    assert gauntlet.rest_choose(items, noisy, fights=8) == ["Bash"]
    assert len(seen[0]) == 4 * 8
    assert gauntlet.rest_choose(items, noisy, fights=8, margin=2.0) == [None]

    def clear(specs):  # Bash+ wins every seed, heal none: well past the margin
        return [{"won": "Bash+" in s["deck"], "hp_end": 50} for s in specs]
    assert gauntlet.rest_choose(items, clear, fights=8, margin=2.0) == ["Bash"]


def test_elite_offers():
    """Mini-run (docs/specs/mini-run.md): a won elite pays elite_offers card
    picks, a skipped elite and a hallway one; 1 gives today's rows."""
    seqs = gauntlet.sequences(3, cells=CELLS)
    pools = gauntlet.reward_pools(REWARD_CELLS)
    seen = []

    def take_first(k, items, j=0):
        seen.append((k, j, [deck for _, _, deck in items]))
        return [(o, o[0]) for o in (gauntlet.offer(s["i"], k, pools[s["half"]], j) for s, _, _ in items)]
    play, _ = fake_play()
    base = gauntlet.run(seqs, play, reward=take_first)
    play, _ = fake_play()
    assert gauntlet.run(seqs, play, reward=take_first, elite_offers=1) == base
    seen.clear()
    play, calls = fake_play()
    rows = gauntlet.run(seqs, play, reward=take_first, elite_offers=2)
    elite = [k for k, x in enumerate(gauntlet.SHAPE) if x == "elite"]
    assert [(k, j) for k, j, _ in seen if j] == [(k, 1) for k in elite]
    for n, (s, r) in enumerate(zip(seqs, rows)):
        pool = pools[s["half"]]
        for k in elite:
            extra = r["floors"][k]["extra"]
            assert extra == [{"offer": gauntlet.offer(s["i"], k, pool, 1), "took": gauntlet.offer(s["i"], k, pool, 1)[0]}]
        assert all("extra" not in f for k, f in enumerate(r["floors"]) if k not in elite)
        assert len(calls[10][n]["deck"]) == len(s["deck"]) + 10 + len(elite)
    # the extra pick sees the deck with the first pick in it
    first = next(x for x in seen if x[1] == 1)
    assert all(d[-1] == gauntlet.offer(s["i"], first[0], pools[s["half"]])[0] for s, d in zip(seqs, first[2]))
    assert any(gauntlet.offer(s["i"], 5, pools[s["half"]], 1) != gauntlet.offer(s["i"], 5, pools[s["half"]])
               for s in gauntlet.sequences(20, cells=CELLS))
    play, calls = fake_play()
    skipped = gauntlet.run(seqs, play, reward=take_first, elite_offers=2, path_hook=gauntlet.path_skip)
    assert all("extra" not in f for r in skipped for f in r["floors"])
    assert all(len(c["deck"]) == len(s["deck"]) + 10 for s, c in zip(seqs, calls[10]))


def test_mid_rest():
    seqs = gauntlet.sequences(3, cells=CELLS)
    play, _ = fake_play()
    base = gauntlet.run(seqs, play)
    play, _ = fake_play()
    assert gauntlet.run(seqs, play, mid_rest=None) == base
    hps = []

    def reward(k, items, j=0):
        if k == 5:
            hps.append([hp for _, hp, _ in items])
        return [([], None)] * len(items)
    play, _ = fake_play()
    rows = gauntlet.run(seqs, play, mid_rest=5, reward=reward)
    for r in rows:
        f = r["floors"]
        assert f[5]["mid_rest"] == gauntlet.rest(f[5]["hp_end"]) and f[6]["hp_start"] == f[5]["mid_rest"]
        assert all("mid_rest" not in g for k, g in enumerate(f) if k != 5)
    assert hps == [[r["floors"][5]["mid_rest"] for r in rows]]


def test_mini_run_settings():
    ctl = tmpfile("mctl.json")
    body, _ = play_cmd(ctl, 12, "--sequences", "20", "--block", "20", "--elite-offers", "2", "--mid-rest", "5")
    assert body["settings"]["elite_offers"] == 2 and body["settings"]["mid_rest"] == 5
    plain = tmpfile("mplain.json")
    pb, _ = play_cmd(plain, 12, "--sequences", "20", "--block", "20")
    assert "elite_offers" not in pb["settings"] and "mid_rest" not in pb["settings"]
    try:
        play_cmd(tmpfile("mr.json"), 7, "--sequences", "20", "--against", plain, "--elite-offers", "2")
        raise AssertionError("control without elite_offers accepted")
    except SystemExit as e:
        assert "elite_offers (control None, this run 2)" in str(e), e
    got, _ = play_cmd(tmpfile("ms.json"), 7, "--sequences", "20", "--against", plain, "--elite-offers", "2",
                      "--vary", "elite_offers")
    assert got["protocol"]["vary"] == ["elite_offers"]
    for bad in ("10", "11", "-1"):
        try:
            play_cmd(tmpfile("mb.json"), 7, "--sequences", "20", "--mid-rest", bad)
            raise AssertionError(bad)
        except (SystemExit, IndexError) as e:
            assert isinstance(e, SystemExit), bad


def _pick(pools, which):
    asked = []

    def hook(k, items, j=0):
        asked.append((k, j, [s["i"] for s, _, _ in items]))
        return [(o, o[which]) for o in (gauntlet.offer(s["i"], k, pools[s["half"]], j) for s, _, _ in items)]
    return hook, asked


def test_match_replays_picks():
    """docs/specs/deck-matched-reads.md: a matched run takes the recorded
    file's picks (extra elite picks too) and never asks its own chooser."""
    seqs = gauntlet.sequences(3, cells=CELLS)
    pools = gauntlet.reward_pools(REWARD_CELLS)
    first, _ = _pick(pools, 0)
    play, _ = fake_play()
    rec = gauntlet.run(seqs, play, reward=first, elite_offers=2)
    last, asked = _pick(pools, -1)
    reward, _, _ = gauntlet.matched(rec, reward=last)
    play, calls = fake_play()
    rows = gauntlet.run(seqs, play, reward=reward, elite_offers=2)
    assert not asked
    for r, q in zip(rows, rec):
        assert [f.get("took") for f in r["floors"]] == [f.get("took") for f in q["floors"]]
        assert [f.get("extra") for f in r["floors"]] == [f.get("extra") for f in q["floors"]]
        assert all(f["matched"] for f in r["floors"][:10]) and "matched" not in r["floors"][10]
    play, base = fake_play()
    gauntlet.run(seqs, play, reward=first, elite_offers=2)
    assert [[c["deck"] for c in fl] for fl in calls] == [[c["deck"] for c in fl] for fl in base]


def test_match_falls_back():
    """Where the recorded file has no pick (it died at floor 3), the run's
    own chooser decides; sequences missing from the file too."""
    seqs = gauntlet.sequences(3, cells=CELLS)
    pools = gauntlet.reward_pools(REWARD_CELLS)
    first, _ = _pick(pools, 0)
    play, _ = fake_play(lose_floor=3)
    rec = gauntlet.run(seqs[:2], play, reward=first)
    last, asked = _pick(pools, -1)
    reward, _, _ = gauntlet.matched(rec, reward=last)
    play, _ = fake_play()
    rows = gauntlet.run(seqs, play, reward=reward)
    assert asked[0] == (0, 0, [seqs[2]["i"]]) and [a[0] for a in asked] == list(range(10))
    assert asked[3][2] == [s["i"] for s in seqs]
    for n, r in enumerate(rows):
        for k, f in enumerate(r["floors"][:10]):
            want = gauntlet.offer(seqs[n]["i"], k, pools[seqs[n]["half"]])[0 if k < 3 and n < 2 else -1]
            assert f["took"] == want and f.get("matched", False) == (k < 3 and n < 2), (n, k, f)


def test_match_rest_remove():
    seqs = gauntlet.sequences(2, cells=CELLS)
    play, _ = fake_play()
    rec = gauntlet.run(seqs, play, rest_hook=lambda items: ["Strike", None],
                       remove_hook=lambda items: [None, "Strike"])
    asked = []
    _, rest_hook, remove_hook = gauntlet.matched(
        rec, rest_hook=lambda items: asked.append(items) or [None] * len(items),
        remove_hook=lambda items: asked.append(items) or ["Strike"] * len(items))
    play, calls = fake_play()
    rows = gauntlet.run(seqs, play, rest_hook=rest_hook, remove_hook=remove_hook)
    assert not asked
    k = gauntlet.REMOVE_FLOOR
    assert [r["floors"][k]["removed"] for r in rows] == [None, "Strike"]
    assert [r["floors"][10]["rest"] for r in rows] == ["Strike", "heal"]
    assert calls[10][0]["deck"] == ["Strike+"] + ["Strike"] * 4 and calls[10][1]["deck"] == ["Strike"] * 4


def test_match_cli():
    ctl = tmpfile("mt.json")
    body, _ = play_cmd(ctl, 12, "--sequences", "20", "--block", "20", "--rewards", "random")
    got, _ = play_cmd(tmpfile("m1.json"), 7, "--sequences", "20", "--rewards", "random", "--match", ctl,
                      "--against", ctl)
    assert got["settings"]["match"] == ctl and got["protocol"]["n"] == 20 and "vary" not in got["protocol"]
    ctl_rows = {r["i"]: r for r in body["sequences"]}
    for r in got["sequences"]:
        for f, g in zip(r["floors"], ctl_rows[r["i"]]["floors"]):
            if "offer" in g:
                assert f["took"] == g["took"] and f["matched"]
    try:
        play_cmd(tmpfile("m2.json"), 7, "--sequences", "20", "--rewards", "sim", "--match", ctl)
        raise AssertionError("match file with other rewards accepted")
    except SystemExit as e:
        assert "rewards (" in str(e), e
    got, _ = play_cmd(tmpfile("m3.json"), 7, "--sequences", "20", "--rewards", "random", "--two-turn",
                      "--match", ctl)
    assert got["settings"]["match"] == ctl
    plain, _ = play_cmd(tmpfile("m4.json"), 7, "--sequences", "20", "--rewards", "random")
    assert "match" not in plain["settings"]


def test_value_choose():
    """docs/specs/value-chooser.md: a value that rewards one card takes it; a flat one skips."""
    seqs = gauntlet.sequences(2, cells=CELLS)
    items = [(s, 40, list(s["deck"])) for s in seqs]
    offers = [["Anger", "Flex", "Clash"], ["Cleave", "Clash", "Anger"]]
    seen = []

    def value(specs):
        seen.append(specs)
        return [1.0 + ("Flex" in sp["deck"]) for sp in specs]
    assert gauntlet.value_choose(0, items, offers, value) == [(offers[0], "Flex"), (offers[1], None)]
    assert gauntlet.value_choose(0, items, offers, lambda specs: [0.5] * len(specs)) == [(o, None) for o in offers]
    # the same states for every option, k = 0: next floor 8, elites 3, boss 8
    per = 2 * gauntlet.SIM_FIGHTS + len(gauntlet.ELITES)
    specs = seen[0]
    assert len(specs) == 2 * 4 * per
    opts = [specs[o * per:(o + 1) * per] for o in range(4)]
    assert all([(sp["encounter"], sp["seed"], sp["hp"]) for sp in x] ==
               [(sp["encounter"], sp["seed"], sp["hp"]) for sp in opts[0]] for x in opts)
    assert opts[2][0]["deck"] == list(seqs[0]["deck"]) + ["Flex"]
    gauntlet.value_choose(0, items, offers, value, hands=3)
    assert len(seen[-1]) == 3 * len(specs)
    assert [sp["seed"] for sp in seen[-1][:3]] == [specs[0]["seed"] + gauntlet.VALUE_HAND_STEP * h for h in range(3)]


def test_value_parts():
    """Parts: the sim chooser's next-floor draw, elites while an elite floor
    lies after the next floor, the own boss at rest(hp); before the boss one part."""
    s = gauntlet.sequences(1, cells=CELLS)[0]
    boss = s["fights"][-1]["encounter"]
    for k in range(10):
        parts = gauntlet.value_parts(k, s, 40)
        nxt = gauntlet.SHAPE[k + 1]
        rng = gauntlet.np.random.default_rng([gauntlet.GAUNTLET_SEED, s["i"], 3000 + k])
        want = [str(e) for e in rng.choice(gauntlet.POOLS[nxt], gauntlet.SIM_FIGHTS)]
        if nxt == "boss":
            assert len(parts) == 1 and [e for e, _, _, _ in parts[0]] == [boss] * gauntlet.SIM_FIGHTS
            assert all(h == gauntlet.rest(40) for _, _, h, _ in parts[0])
            continue
        assert [e for e, _, _, _ in parts[0]] == want and all(h == 40 for _, _, h, _ in parts[0])
        assert len(parts) == (3 if k < 7 else 2), k
        if k < 7:
            assert [e for e, _, _, _ in parts[1]] == list(gauntlet.ELITES)
        assert all(e == boss and h == gauntlet.rest(40) and g == "boss" for e, _, h, g in parts[-1])
    seeds = [sd for k in range(10) for p in gauntlet.value_parts(k, s, 40) for _, sd, _, _ in p]
    assert all(sd >= gauntlet.SIM_SEED_BASE for sd in seeds)


def test_value_settings():
    """--rewards value: value_hands recorded only when not 1; the value net is
    --chooser else the player; --sim-boss and a stray --value-hands refused."""
    asked = []

    def fake_values(player, threads=1):
        asked.append(player)
        return lambda specs: [1.0] * len(specs)

    def run(*argv):
        lad = FakeLadder(7)
        real, real_nv = sys.modules.get("ladder"), gauntlet.net_values
        sys.modules["ladder"] = lad
        gauntlet.net_values = fake_values
        try:
            gauntlet.main(["play", "p", *argv])
        finally:
            gauntlet.net_values = real_nv
            if real is None:
                del sys.modules["ladder"]
            else:
                sys.modules["ladder"] = real

    out = tmpfile("v1.json")
    run("--out", out, "--sequences", "2", "--start", "starter", "--rewards", "value")
    with open(out, encoding="utf-8") as f:
        body = gauntlet.json.load(f)
    assert body["settings"]["rewards"] == "value" and "value_hands" not in body["settings"]
    assert all(f["took"] is None for r in body["sequences"] for f in r["floors"] if "offer" in f)  # flat: skip
    out4 = tmpfile("v4.json")
    run("--out", out4, "--sequences", "2", "--start", "starter", "--rewards", "value", "--value-hands", "4",
        "--chooser", "q")
    with open(out4, encoding="utf-8") as f:
        assert gauntlet.json.load(f)["settings"]["value_hands"] == 4
    assert asked == ["p", "q"]
    for bad in (["--rewards", "value", "--sim-boss"], ["--rewards", "sim", "--value-hands", "2"]):
        try:
            run("--out", tmpfile("bad.json"), "--sequences", "2", *bad)
        except SystemExit:
            continue
        raise AssertionError(bad)


PACK = os.path.join(os.path.dirname(__file__), "..", "..", "content", "packs", "act1-ironclad.json")


def test_pack_pools():
    """docs/specs/gauntlet-pack-offers.md: the pack's base cards join both
    halves' pools as gen:<id>; without a pack the pools are unchanged."""
    import json
    with open(PACK, encoding="utf-8") as f:
        pack = json.load(f)
    base = [c["id"] for c in pack["cards"] if not c["id"].endswith("+")]
    assert gauntlet.base_ids(pack) == base  # successors named by `successor`: the same set
    named = {"cards": [{"id": "A", "successor": "A sharp"}, {"id": "A sharp"}, {"id": "B"}, {"id": "B+"}]}
    assert gauntlet.base_ids(named) == ["A", "B"]
    assert len(base) == 32
    old = gauntlet.reward_pools(CELLS)
    assert gauntlet.pack_pools(old, None) == old
    new = gauntlet.pack_pools(old, pack)
    for h in gauntlet.HALVES:
        assert new[h] == sorted(old[h] + ["gen:" + b for b in base]), h
        assert not any(n.endswith("+") for n in new[h])


def test_pack_settings():
    """--pack is recorded as <path>@<hash>, refused without offers, and an
    --against read across it must declare --vary pack."""
    import re
    got, _ = play_cmd(tmpfile("p.json"), 7, "--sequences", "6", "--rewards", "random", "--pack", PACK)
    assert re.fullmatch(r".*act1-ironclad\.json@[0-9a-f]{16}", got["settings"]["pack"]), got["settings"]["pack"]
    took = [f["took"] for r in got["sequences"] for f in r["floors"] if f.get("took")]
    assert any(t.startswith("gen:") for t in took), took
    ctl = tmpfile("ctl.json")
    body, _ = play_cmd(ctl, 7, "--sequences", "6", "--rewards", "random")
    assert "pack" not in body["settings"]
    try:
        play_cmd(tmpfile("s.json"), 7, "--sequences", "6", "--pack", PACK)
        raise AssertionError("--pack without offers accepted")
    except SystemExit as e:
        assert "--pack needs --rewards" in str(e), e
    try:
        play_cmd(tmpfile("r.json"), 7, "--sequences", "6", "--rewards", "random", "--pack", PACK, "--against", ctl)
        raise AssertionError("pack-less control accepted")
    except SystemExit as e:
        assert "pack (control None" in str(e), e
    got, _ = play_cmd(tmpfile("v.json"), 7, "--sequences", "6", "--rewards", "random", "--pack", PACK,
                      "--against", ctl, "--vary", "pack")
    assert got["protocol"]["vary"] == ["pack"]


MONSTERS = os.path.join(os.path.dirname(__file__), "..", "..", "content", "packs", "act1-monsters.json")


def _pack(path):
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_sequences_unchanged_without_pack():
    """docs/specs/gauntlet-pack-encounters.md: no pack, or a pack without
    hallway encounters, gives today's sequences."""
    import hashlib
    import json
    base = gauntlet.sequences(200, 0, CELLS)
    assert gauntlet.sequences(200, 0, CELLS, _pack(PACK)) == base
    assert gauntlet.sequences(200, 0, CELLS, None) == base
    assert all(f["encounter"] in gauntlet.HARD for s in base for f in s["fights"] if f["kind"] == "hard")
    print(hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest()[:12])


def test_pack_hard_pool():
    """A pack's hallway encounters join the hard floors at 1/10 each; every
    other floor, and hard floors without a pack encounter, match pack-less."""
    pack = _pack(MONSTERS)
    rep, add = gauntlet.pack_hard(pack)
    assert rep == {"exordium_thugs": "gen:Exordium Thugs"}, rep
    assert sorted(add) == ["gen:Blue Slaver", "gen:Gremlin Gang", "gen:Red Slaver"], add
    pool = sorted(set(gauntlet.HARD) - {"exordium_thugs"} | set(add) | {"gen:Exordium Thugs"})
    assert len(pool) == 10
    n = 2000
    old, new = gauntlet.sequences(n, 0, CELLS), gauntlet.sequences(n, 0, CELLS, pack)
    counts, total = {e: 0 for e in pool}, 0
    for a, b in zip(old, new):
        assert (a["half"], a["cell"]) == (b["half"], b["cell"])
        prev = None
        for fa, fb in zip(a["fights"], b["fights"]):
            assert fa["seed"] == fb["seed"]
            if fa["kind"] != "hard":
                assert fa == fb
            else:
                assert fb["encounter"] in pool, fb
                assert fb["encounter"] != prev, (a["i"], fb)
                if not fb["encounter"].startswith("gen:"):
                    assert fa == fb
                counts[fb["encounter"]] += 1
                total += 1
            prev = fb["encounter"]
    se = (0.1 * 0.9 / total) ** 0.5
    for e, c in counts.items():
        assert abs(c / total - 0.1) < 4 * se + 0.01, (e, c / total)


def test_pack_encounters_settings():
    """A pack with hallway encounters needs no offers."""
    got, _ = play_cmd(tmpfile("m.json"), 7, "--sequences", "6", "--pack", MONSTERS)
    assert got["settings"]["pack"].split("@")[0].endswith("act1-monsters.json")
    encs = [f["encounter"] for r in got["sequences"] for f in r["floors"]]
    assert encs, got["sequences"][0]


def test_play_two_turn_content():
    """ladder.play_two_turn hands its content pack to run_guarded's workers."""
    import ladder
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
    import depth_paired
    seen = {}
    real = depth_paired.run_guarded

    def fake(specs, two, margin, player, threads, partial=None, **kw):
        seen.update(kw)
        return [{"won": True, "hp_start": 1, "hp_end": 1} for _ in specs]
    depth_paired.run_guarded = fake
    try:
        ladder.play_two_turn([{}], "p", 1, content="x.json")
        assert seen.get("content") == "x.json", seen
        seen.clear()
        ladder.play_two_turn([{}], "p", 1)
        assert seen.get("content") is None, seen
    finally:
        depth_paired.run_guarded = real


# --- pins (docs/specs/explorer-v2.md, build step 1) ---------------------------
# Real play (heuristic, cell decks, sim rewards, sim rest, strike removal) on 4
# sequences; the file must stay byte-identical to the fixture written from the
# code before the player factoring. STS_REGEN_PINS=1 rewrites the fixture.

PIN_ARGS = ["--sequences", "4", "--threads", "1", "--rewards", "sim", "--rest", "sim", "--remove", "strike"]
PIN_FILE = os.path.join(os.path.dirname(__file__), "data", "explore", "gauntlet_pin.json")


def play_pin(out):
    gauntlet.main(["play", "heuristic", "--out", out, *PIN_ARGS])
    with open(out, "rb") as f:
        return f.read()


def test_gauntlet_players_match_play_cmd():
    got = play_pin(tmpfile("pin.json"))
    if os.environ.get("STS_REGEN_PINS"):
        os.makedirs(os.path.dirname(PIN_FILE), exist_ok=True)
        with open(PIN_FILE, "wb") as f:
            f.write(got)
    with open(PIN_FILE, "rb") as f:
        assert got == f.read(), "gauntlet.py play's file changed for the pinned run"


def test_gauntlet_players_from_settings_match_file():
    # The factored players(settings), driven from the pinned file's own
    # settings through run(), plays the file's rows (explorer-v2 step 4).
    import json
    with open(PIN_FILE, encoding="utf-8") as f:
        pinned = json.load(f)
    p = gauntlet.players(pinned["settings"], threads=1)
    seqs = gauntlet.sequences(len(pinned["sequences"]))
    rows = gauntlet.run(seqs, p.play, reward=p.reward, rest_hook=p.rest_hook, remove_hook=p.remove_hook,
                        path_hook=p.path_hook, elite_offers=p.elite_offers, mid_rest=p.mid_rest)
    assert json.loads(json.dumps(rows)) == pinned["sequences"]


def test_rest_label_round_trip():
    for fights, margin in ((gauntlet.REST_FIGHTS, 0.0), (64, 2.0), (16, 1.5)):
        assert gauntlet.parse_rest_label(gauntlet.rest_label("sim", fights, margin)) == (fights, margin)
    assert gauntlet.rest_label("sim") == "sim"


def test_pack_picks_originals():
    """docs/specs/pack-pick-split.md: under --pack-picks originals the pack's
    cards are still offered but never taken; refused without a pack; the
    setting is recorded and must be declared with --vary."""
    args = ("--sequences", "8", "--rewards", "random", "--pack", PACK)
    anyp, _ = play_cmd(tmpfile("a.json"), 7, *args)
    orig, _ = play_cmd(tmpfile("o.json"), 7, *args, "--pack-picks", "originals")
    assert orig["settings"]["pack_picks"] == "originals" and "pack_picks" not in anyp["settings"]
    fl = [f for r in orig["sequences"] for f in r["floors"] if "offer" in f]
    assert any(c.startswith("gen:") for f in fl for c in f["offer"])
    assert not any((f.get("took") or "").startswith("gen:") for f in fl)
    assert any((f.get("took") or "").startswith("gen:") for r in anyp["sequences"] for f in r["floors"])
    assert all(f["took"] is None for f in fl if all(c.startswith("gen:") for c in f["offer"]))
    try:
        play_cmd(tmpfile("n.json"), 7, "--sequences", "4", "--rewards", "random", "--pack-picks", "originals")
        raise AssertionError("--pack-picks without --pack accepted")
    except SystemExit as e:
        assert "--pack-picks originals needs --pack" in str(e), e
    ctl = tmpfile("ctl.json")
    play_cmd(ctl, 7, *args)
    try:
        play_cmd(tmpfile("r.json"), 7, *args, "--pack-picks", "originals", "--against", ctl)
        raise AssertionError("control without pack_picks accepted")
    except SystemExit as e:
        assert "pack_picks (control None" in str(e), e
    got, _ = play_cmd(tmpfile("v.json"), 7, *args, "--pack-picks", "originals", "--against", ctl,
                      "--vary", "pack_picks")
    assert got["protocol"]["vary"] == ["pack_picks"]


def test_pack_picks_sim_chooser():
    """The sim chooser under a barred set scores only skip and the allowed
    cards, and keeps the full offer in its rows and scores."""
    pack = _pack(PACK)
    pools = gauntlet.pack_pools(gauntlet.reward_pools(CELLS), pack)
    barred = gauntlet.pack_names(pack)
    assert len(barred) == 32 and all(n.startswith("gen:") for n in barred)

    def sim_play(specs):  # a deck with a pack card wins with more HP
        return [{"won": True, "hp_start": s["hp"], "hp_end": 60 + 10 * any(c.startswith("gen:") for c in s["deck"])}
                for s in specs]
    seqs = gauntlet.sequences(40, 0, CELLS)
    items = [(s, 70, list(s["deck"])) for s in seqs]
    free = gauntlet.chooser("sim", pools, sim_play)(0, items)
    bar = gauntlet.chooser("sim", pools, sim_play, barred=barred)
    held = bar(0, items)
    assert [o for o, _ in free] == [o for o, _ in held]
    assert any(t in barred for _, t in free)
    assert not any(t in barred for _, t in held)
    for row, (o, t) in zip(bar.scores(0, items), held):
        assert row["offer"] == o and row["pick"] == t
        assert row["options"] == [None] + [c for c in o if c not in barred]
        assert len(row["scores"]) == len(row["options"])


def test_upgrades_of_pack_cards():
    """docs/specs/card-upgrades.md: the rest site upgrades pack cards with
    an upgrade (Searing Blow without limit) and never a status or a card at
    its max level; names keep their base through sts.base_name."""
    import sts
    sts.load_content(PACK)
    deck = ["Strike", "Bash+", "Wound", "gen:Flame Barrier", "gen:Searing Blow+", "gen:Searing Blow+", "gen:True Grit"]
    assert gauntlet.upgradable(deck) == ["Strike", "gen:Flame Barrier", "gen:Searing Blow+", "gen:True Grit"]
    assert gauntlet.upgrade(["gen:Searing Blow+", "Strike"], "gen:Searing Blow+") == ["gen:Searing Blow+2", "Strike"]
    assert gauntlet.upgrade(["Bash", "Bash"], "Bash") == ["Bash+", "Bash"]
    assert sts.upgrade_name("Bash") == "Bash+" and sts.upgrade_name("Bash+") is None and sts.upgrade_name("Wound") is None
    assert sts.upgrade_name("gen:Searing Blow+") == "gen:Searing Blow+2"
    assert sts.base_name("gen:Searing Blow+12") == "gen:Searing Blow" and sts.base_name("Bash+") == "Bash"
    assert gauntlet.base_name("gen:Searing Blow+3") == "gen:Searing Blow"


def test_resolve_player_glob(tmp_path, monkeypatch):
    import gauntlet
    (tmp_path / "2026-11-12-x-r1-abc").mkdir()
    (tmp_path / "2026-11-12-x-r1-abc" / "model.pt").write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    assert gauntlet.resolve_player("heuristic") == "heuristic"
    assert gauntlet.resolve_player("*-x-r1-*/model.pt@hpb0.01") == "2026-11-12-x-r1-abc/model.pt@hpb0.01"
    import pytest
    with pytest.raises(SystemExit):
        gauntlet.resolve_player("*-y-r1-*/model.pt@hpb0.01")
