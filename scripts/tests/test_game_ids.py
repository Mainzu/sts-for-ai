"""The real-game bridge's name tables (docs/specs/real-game-bridge.md, build
step 2): content/game_ids.json against the engine and the game's jar."""

import json
import os
import sys

import pytest

import sts

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import game_ids  # noqa: E402

ROOT = game_ids.ROOT
ACT1_PACKS = ["act1-ironclad", "act1-colorless", "act1-monsters", "act1-relics", "act1-potions"]
DECK = ["Strike"] * 5


def content(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module", autouse=True)
def packs():
    for p in ACT1_PACKS:
        sts.load_content(os.path.join(ROOT, "content", "packs", p + ".json"))


def official():
    """The engine's official names by kind: content/*.json and the Act 1
    packs (pack ids with gen:, pack powers bare)."""
    out = {k: set() for k in game_ids.KINDS}
    for kind in game_ids.KINDS:
        for r in content("content/%s.json" % kind)[kind]:
            out[kind].add(r["id"])
    for p in ACT1_PACKS:
        pack = content("content/packs/%s.json" % p)
        for kind in game_ids.KINDS:
            for r in pack.get(kind, []):
                out[kind].add(r["id"] if kind == "powers" else "gen:" + r["id"])
    return out


def mapped(kind):
    return {game_ids.engine_name(kind, g) for g in game_ids.tables()[kind]}


def test_card_names_exist():
    # Statuses with no upgrade, and the curses (never upgraded).
    no_upgrade = {"Wound", "Slimed", "Dazed"} | {
        "gen:" + c["id"] for p in ACT1_PACKS for c in content("content/packs/%s.json" % p).get("cards", []) if c.get("type") == "Curse"}
    for name in mapped("cards"):
        sts.Combat.versus([name], ["Jaw Worm"])
        if name not in no_upgrade:
            sts.Combat.versus([name + "+"], ["Jaw Worm"])


def test_monster_names_and_moves_exist():
    names = {}
    for f, prefix in (("content/monsters.json", ""), ("content/packs/act1-monsters.json", "gen:")):
        for m in content(f)["monsters"]:
            names[prefix + m["id"]] = [x["name"] for x in m["moves"]]
    for gid, v in game_ids.tables()["monsters"].items():
        sts.Combat.versus(DECK, [v["engine"]])
        engine_moves = names[v["engine"]]
        ids = [i for m in v["moves"].values() for i in m["engine"]]
        assert sorted(ids) == list(range(len(engine_moves))), gid  # every engine move, once
        for m in v["moves"].values():
            assert {engine_moves[i] for i in m["engine"]} == {m["name"]}, (gid, m)


def test_power_relic_potion_names_exist():
    pack_powers = {r["id"] for p in ACT1_PACKS for r in content("content/packs/%s.json" % p).get("powers", [])}
    for name in mapped("powers"):
        assert name in sts.power_names() or name in pack_powers, name
    for name in mapped("relics") - {"Burning Blood"}:  # the starter relic is the character's
        sts.Combat.versus(DECK, ["Jaw Worm"], relics=[name])
    for name in mapped("potions"):
        sts.Combat.versus(DECK, ["Jaw Worm"], potions=[name])


def test_every_official_name_is_mapped_or_engine_only():
    engine_only = game_ids.tables()["engine_only"]
    for kind, names in official().items():
        covered = mapped(kind)
        if kind == "cards":  # an upgrade written as its own id (FTL+, True Grit+): card_name(id, 1)
            covered |= {n + "+" for n in covered}
        missing = names - covered - set(engine_only.get(kind, {}))
        assert not missing, (kind, sorted(missing))


def test_translation():
    assert game_ids.engine_name("monsters", "JawWorm") == "Jaw Worm"
    assert game_ids.moves("JawWorm") == {1: [0], 2: [2], 3: [1]}
    assert game_ids.card_name("Strike_R") == "Strike"
    assert game_ids.card_name("Bash", 1) == "Bash+"
    assert game_ids.card_name("True Grit", 1) == "gen:True Grit+"
    assert game_ids.card_name("Searing Blow", 2) is None
    assert game_ids.card_name("WaveOfTheHand") is None  # a card no pack loads (Watcher)
    assert game_ids.game_ids("powers", "Intangible") == ["Intangible", "IntangiblePlayer"]
    assert game_ids.modelled_elsewhere("powers", "Split")


def test_ids_exist_in_the_game_jar():
    if not os.path.exists(game_ids.GAME_JAR):
        pytest.skip("the game isn't installed at %s" % game_ids.GAME_JAR)
    assert game_ids.check() == []


def test_check_reports_a_miss(monkeypatch):
    if not os.path.exists(game_ids.GAME_JAR):
        pytest.skip("the game isn't installed at %s" % game_ids.GAME_JAR)
    t = json.loads(json.dumps(game_ids.tables()))
    t["cards"]["No Such Card"] = "Strike"
    t["monsters"]["JawWorm"]["moves"]["1"]["game"] = "NO_SUCH_MOVE"
    monkeypatch.setattr(game_ids, "_tables", t)
    misses = game_ids.check()
    assert any("No Such Card" in m for m in misses)
    assert any("NO_SUCH_MOVE" in m for m in misses)
