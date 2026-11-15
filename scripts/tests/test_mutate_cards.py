"""Tests for the mutated-card bench (scripts/analysis/mutate_cards.py,
docs/specs/mutated-cards.md). Run with pytest."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import mutate_cards as mc  # noqa: E402
import sts  # noqa: E402

STARTER = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]


def test_pack_loads():
    p = mc.pack()
    sts.load_content(json.dumps(p))
    cards = {c["id"]: c for c in p["cards"]}
    off = mc.official_cards()
    for m, (parent, change) in mc.MODS.items():
        cp = cards[mc.copy_id(parent)]
        assert {k: cp[k] for k in ("cost", "type", "effects")} == {k: off[parent][k] for k in ("cost", "type", "effects")}
        var = cards[m]
        changed = {k for k in ("cost", "type", "effects") if var[k] != cp[k]}
        assert changed == set(change), m
    # every variant plays in a deck
    for m, (parent, _) in mc.MODS.items():
        c = mc.start({"encounter": "gremlin_nob", "hp": 70, "character": "ironclad"}, STARTER + ["gen:" + m], 3)
        assert not c.is_over()


def test_swap():
    assert mc.swapped(["Bash", "Bash+", "Strike", "Bash"], "Bash", "gen:x") == ["gen:x", "Bash+", "Strike", "gen:x"]


def specs():
    base = {"encounter": "gremlin_nob", "hp": 70, "character": "ironclad", "group": "elite", "seed": 1}
    return [dict(base, i=0, floor=3, deck=STARTER + ["Inflame", "Demon Form"]),
            dict(base, i=1, floor=5, deck=STARTER + ["Metallicize"], group="boss", encounter="hexaghost", hp=60)]


def test_play_tiny(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mc.ba, "fights", lambda product, n: specs())
    product = tmp_path / "product.json"
    product.write_text("{}")
    out = tmp_path / "cards.json"
    argv = ["play", "--product", str(product), "--starts", "2", "--seeds", "1", "--players", "heuristic",
            "--mods", "bash-c1-d5,inflame-turn1,df-c2-s1,metal-c0-a2", "--threads", "1", "--out", str(out)]
    mc.main(argv)
    d = json.loads(out.read_text())
    by = {(r["i"], r["card"]): r for r in d["rows"]}
    assert set(by) == {(0, "Bash"), (1, "Bash"), (0, "Inflame"), (0, "Demon Form"), (1, "Metallicize")}
    assert set(by[(0, "Bash")]["mods"]) == {"bash-c1-d5"} and set(by[(1, "Metallicize")]["mods"]) == {"metal-c0-a2"}
    r = by[(0, "Inflame")]
    assert len(r["official"]["heuristic"]) == len(r["parent"]["heuristic"]) == len(r["mods"]["inflame-turn1"]["heuristic"]) == 1
    capsys.readouterr()
    mc.main(argv)  # a rerun plays nothing more
    assert "starts" not in capsys.readouterr().out
    assert json.loads(out.read_text()) == d
    mc.main(["read", str(out)])


def test_read():
    # two starts of one power pair and the control; outcomes picked so the
    # contrasts are easy to compute by hand (hp 50: a loss costs 50)
    def row(i, card, mod, par, mods):
        return {"i": i, "floor": 0, "encounter": "e", "group": "elite", "hp": 50, "card": card,
                "official": par, "parent": par, "mods": {mod: mods}}
    W = lambda hp: [[True, hp]]  # noqa: E731
    rows = [row(0, "Inflame", "inflame-turn1", {"heuristic": W(40), "one": W(40)}, {"heuristic": W(40), "one": W(30)}),
            row(1, "Inflame", "inflame-turn1", {"heuristic": W(40), "one": W(40)}, {"heuristic": W(36), "one": W(30)}),
            row(0, "Demon Form", "df-c2-s1", {"heuristic": W(40), "one": W(40)}, {"heuristic": W(40), "one": [[False, 0]]}),
            row(1, "Demon Form", "df-c2-s1", {"heuristic": W(40), "one": W(40)}, {"heuristic": W(40), "one": W(40)}),
            row(0, "Bash", "bash-c1-d5", {"heuristic": W(40), "one": W(40)}, {"heuristic": W(38), "one": W(38)}),
            row(1, "Bash", "bash-c1-d5", {"heuristic": W(40), "one": W(40)}, {"heuristic": W(38), "one": W(38)})]
    s = mc.summary(rows, ["bash-c1-d5", "inflame-turn1", "df-c2-s1"])
    # inflame: one loses 10 HP more on both, heuristic 0 and 4: novelty HP lost (10-0 + 10-4) / 2 = 8
    assert s["inflame-turn1"]["novelty_one"]["lost"][0] == 8.0
    assert s["inflame-turn1"]["novelty_one"]["win"][0] == 0.0
    # df: one loses start 0 (win -1, HP lost +40), level on start 1: novelty wins -0.5, HP lost +20
    assert s["df-c2-s1"]["novelty_one"]["win"][0] == -0.5 and s["df-c2-s1"]["novelty_one"]["lost"][0] == 20.0
    assert s["bash-c1-d5"]["novelty_one"]["lost"] == (0.0, 0.0)
    assert s["inflame-turn1"]["one"]["copy_win"] == (0.0, 0.0)
    pl = mc.pooled(s)["one"]
    assert pl["pairs"] == 2 and pl["win"][0] == -0.25 and pl["lost"][0] == 14.0
    assert pl["control"]["lost"] == (0.0, 0.0)
    assert "tsl" not in mc.pooled(s)


PACK_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "bench", "mutated_cards_pack.json")
CONFIGS = os.path.join(os.path.dirname(__file__), "..", "..", "configs")


def test_pack_file():
    with open(PACK_FILE, encoding="utf-8") as f:
        assert json.load(f) == mc.pack()


def test_net_glob(tmp_path):
    for name in ("a-x-1", "a-x-2", "b-y-1"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "model.pt").write_text("")
    assert mc.resolve_net(str(tmp_path / "b-*" / "model.pt")).endswith("model.pt")
    for pat in ("a-*", "c-*"):
        try:
            mc.resolve_net(str(tmp_path / pat / "model.pt"))
        except SystemExit:
            continue
        raise AssertionError(pat)
    assert mc.resolve_net("plain/path/model.pt") == "plain/path/model.pt"  # no glob: as given


def test_adapted():
    W = lambda hp: [[True, hp]]  # noqa: E731
    L = [[False, 0]]

    def row(i, group, off, par, mod):
        return {"i": i, "floor": 0, "encounter": "e", "group": group, "hp": 50, "card": "Inflame",
                "official": off, "parent": par, "mods": {"inflame-turn1": mod}}
    zero = {"rows": [row(0, "elite", {"one": W(40), "heuristic": W(40)}, {"one": W(40), "heuristic": W(40)},
                         {"one": L, "heuristic": W(40)}),
                     row(1, "boss", {"one": W(30), "heuristic": W(30)}, {"one": W(30), "heuristic": W(30)},
                         {"one": W(20), "heuristic": W(30)})]}
    b1 = {"rows": [row(0, "elite", {"one": W(40)}, {"one": W(40)}, {"one": W(40)}),
                   row(1, "boss", {"one": W(30)}, {"one": W(28)}, {"one": W(30)})]}
    b2 = {"rows": [row(0, "elite", {"one": W(40)}, {"one": W(40)}, {"one": L}),
                   row(1, "boss", {"one": W(30)}, {"one": W(30)}, {"one": W(26)})]}
    s = mc.adapted_summary(zero, [b1, b2], "inflame-turn1", "one")
    # variant: start 0 bursts win 0.5 vs 0 (HP lost 30 vs 50: -20); start 1 HP lost (20+24)/2=22 vs 30: -8
    assert s["mod"]["win"][0] == 0.25 and s["mod"]["lost"][0] == -14.0
    # parent: start 1 HP lost (22+20)/2 = 21 vs 20: +1; start 0 level
    assert s["parent"]["lost"][0] == 0.5 and s["official"]["lost"] == (0.0, 0.0)
    # zero-shot novelty: start 0 net -1 win (+50 lost), heuristic 0; start 1 +10 lost: wins -0.5, lost +25
    assert s["novelty"]["win"][0] == -0.5 and s["novelty"]["lost"][0] == 25.0
    assert [round(x["win"][0], 3) for x in s["per_burst"]] == [0.5, 0.0]
    assert s["n"] == 2
    other = {"rows": [dict(row(0, "elite", {}, {}, {}), card="Metallicize", mods={"metal-c2-a5": {"one": W(40)}})]}
    assert mc.adapted_summary(zero, [b1, other, b2], "inflame-turn1", "one") == s  # files of both modifiers in one call


def test_burst_configs():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import finetune
    names = sorted(n for n in os.listdir(CONFIGS) if n.startswith("cadapt-"))
    # six variant bursts (two cards x three seeds) plus copy-rehearsal bursts (variant and parent copy)
    assert len([n for n in names if "-copy-" not in n]) == 6
    ids = {c["id"] for c in mc.pack()["cards"]}
    for n in names:
        with open(os.path.join(CONFIGS, n), encoding="utf-8") as f:
            cfg = json.load(f)
        assert cfg["content"]["cards"][0] in ids and cfg["name"] == n[:-5]
        assert finetune.generated(cfg["content"])[1] == ["gen:" + c for c in cfg["content"]["cards"]]
