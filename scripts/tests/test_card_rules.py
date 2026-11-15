"""Card rules the net can read (docs/specs/card-rules.md): a power's
forbids, sets_cost and exhausts_played and a card's playable_if (Clash) as
`rule` rows (opt-in, like the other extra row kinds), each worded in
content/wording.json; Clash's old only_attacks_in_hand column as a legacy
read for layouts that name it; the guards that fail when a power or card
rule key has no words or nothing the net reads. Run with
`python scripts/tests/test_card_rules.py` (plain asserts) or with pytest."""

import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import sts  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PACKS = [ROOT / "content" / "packs" / "act1-monsters.json", ROOT / "content" / "packs" / "act1-ironclad.json"]
WORDING = json.loads((ROOT / "content" / "wording.json").read_text(encoding="utf-8"))
RULES = ["Rule(Forbids)", "Rule(SetsCost)", "Rule(ExhaustsPlayed)"]
# One sample value per power rule key; a new key without a sample fails the guard.
SAMPLES = {"forbids": "Attack", "sets_cost": {"type": "Skill", "cost": 2}, "exhausts_played": "Skill"}


def load_packs():
    for p in PACKS:
        sts.load_content(p.read_text(encoding="utf-8"))


def player_rows(c, extra=True):
    """The player's own power rows (no card, no grant) as {column: value}."""
    f = sts.Features("effects", extra_rows=extra)
    b = f.encode([c])
    names = f.row_names
    return [dict(zip(names, r)) for r, e, k in zip(b["rows"], b["row_entity"], b["row_card"])
            if e == 0 and k == -1]


def rule_rows(rows):
    return [r for r in rows if any(r.get(f"trigger_{t}") == 1 for t in RULES)]


def entangled_state():
    load_packs()
    deck = ["Strike"] * 5 + ["Defend"] * 5
    for seed in range(20):
        c = sts.Combat.versus(deck, ["gen:Red Slaver"], seed=seed, hp=60)
        while not c.is_over():
            if "Entangled" in c.render().split("Hand:")[0]:
                return c
            c.step(sts.greedy_action(c))
    raise AssertionError("no state with Entangled on the player")


def corruption_state():
    load_packs()
    c = sts.Combat(["gen:Corruption"] * 5 + ["Defend"] * 5, "cultist", seed=1, hp=60)
    c.step(next(a for a in c.legal_actions() if a.card == "gen:Corruption"))
    assert "Corruption" in c.render().split("Hand:")[0], c.render()
    return c


def test_rule_rows_entangled():
    rows = rule_rows(player_rows(entangled_state()))
    assert len(rows) == 1, rows
    r = rows[0]
    assert r["trigger_Rule(Forbids)"] == 1 and r["condition_CardType(Attack)"] == 1 and r["grant_own"] == 1


def test_rule_rows_corruption():
    rows = rule_rows(player_rows(corruption_state()))
    assert len(rows) == 2, rows
    cost = [r for r in rows if r["trigger_Rule(SetsCost)"] == 1]
    ex = [r for r in rows if r["trigger_Rule(ExhaustsPlayed)"] == 1]
    assert len(cost) == 1 and len(ex) == 1
    assert cost[0]["condition_CardType(Skill)"] == 1 and cost[0]["condition_param"] == 0
    assert ex[0]["condition_CardType(Skill)"] == 1 and ex[0]["condition_param"] == 0


def test_rule_rows_off_by_default():
    for c in (entangled_state(), corruption_state()):
        f = sts.Features("effects")
        assert "rule" not in f.row_kinds
        b = f.encode([c])
        names = f.row_names
        assert not any(dict(zip(names, r)).get(f"trigger_{t}") == 1 for r in b["rows"] for t in RULES)


def test_rule_keys_read():
    """Every power rule key the registry accepts has words under power_rule
    and gives the holder a rule row (the guard: a new key can't land unread)."""
    assert list(sts.POWER_RULE_KEYS) == list(SAMPLES), "add a sample for the new key"
    for key in sts.POWER_RULE_KEYS:
        assert key in WORDING["power_rule"], key
        pid, rid = f"GuardRule_{key}", f"Guard Rule {key}"
        sts.load_content(json.dumps({"version": 2, "powers": [{"id": pid, "debuff": False, "hooks": [], key: SAMPLES[key]}],
                                     "relics": [{"id": rid, "rarity": "common", "powers": [{"power": pid, "amount": 1}]}]}))
        c = sts.Combat(["Strike"] * 5 + ["Defend"] * 5, "cultist", seed=1, relics=[f"gen:{rid}"])
        rows = rule_rows(player_rows(c))
        assert len(rows) == 1, key
        if key == "sets_cost":
            assert rows[0]["condition_param"] == 2, rows  # the cap rides in condition_param


def test_unknown_power_key_is_an_error():
    try:
        sts.load_content(json.dumps({"version": 2, "powers": [{"id": "GuardTypo", "hooks": [], "forbid": "Attack"}]}))
    except Exception as e:  # noqa: BLE001
        assert "forbid" in str(e), e
    else:
        raise AssertionError("an unknown power key loads")


def clash_rows(deck, extra=True):
    """Every card row with a rule trigger, as {column: value}, in a fight
    with `deck`."""
    c = sts.Combat(deck, "cultist", seed=1, hp=60)
    f = sts.Features("effects", extra_rows=extra)
    b = f.encode([c])
    names = f.row_names
    return [dict(zip(names, r)) for r, k in zip(b["rows"], b["row_card"]) if k != -1
            and any(dict(zip(names, r)).get(f"trigger_{t}") == 1 for t in RULES + ["Rule(PlayableIf)"])]


def test_rule_rows_clash():
    rows = clash_rows(["Clash"] * 5 + ["Strike"] * 5)
    assert rows and all(r["trigger_Rule(PlayableIf)"] == 1 and r["condition_HandAll(Attack)"] == 1
                        and r["grant_own"] == 1 for r in rows), rows
    assert not clash_rows(["Strike"] * 5 + ["Defend"] * 5)
    assert not clash_rows(["Clash"] * 5 + ["Strike"] * 5, extra=False)


def test_legacy_clash_column():
    """`only_attacks_in_hand` left the default card columns; a layout that
    names it (a net trained before card-rules) reads 1 for Clash, 0 else."""
    old = "only_attacks_in_hand"
    assert old not in sts.Features("effects").card_names
    full = sts.Features("effects")
    cols = {"player": full.player_names, "monsters": full.monster_names, "rows": full.row_names,
            "cards": full.card_names[:9] + [old] + full.card_names[9:]}
    for deck, want in ((["Clash"] * 10, 1.0), (["Strike"] * 10, 0.0)):
        f = sts.Features("effects", columns=cols)
        assert f.card_names == cols["cards"]
        b = f.encode([sts.Combat(deck, "cultist", seed=1, hp=60)])
        at = f.card_names.index(old)
        assert len(b["cards"]) and all(v[at] == want for v in b["cards"]), (deck, [v[at] for v in b["cards"]])


def test_card_rule_keys_read():
    """Every card rule key has words under card_rule and reaches the net: a
    card column (cost_less_per_hp_loss) or a rule row (playable_if)."""
    assert list(sts.CARD_RULE_KEYS) == ["cost_less_per_hp_loss", "playable_if"], "a new card rule key needs a read"
    for key in sts.CARD_RULE_KEYS:
        assert key in WORDING["card_rule"], key
    assert "cost_less_per_hp_loss" in sts.Features("effects").card_names
    assert clash_rows(["Clash"] * 10)


def test_unknown_card_key_is_an_error():
    try:
        sts.load_content(json.dumps({"version": 2, "cards": [{"id": "GuardCardTypo", "cost": 0, "type": "Skill",
                                                              "playable_iff": {"HandAll": "Skill"}, "effects": []}]}))
    except Exception as e:  # noqa: BLE001
        assert "playable_iff" in str(e), e
    else:
        raise AssertionError("an unknown card key loads")


def test_explorer_words_clash():
    import explore
    explore.UNWORDED.clear()
    cards = {c["id"]: c for c in json.loads((ROOT / "content" / "cards.json").read_text(encoding="utf-8"))["cards"]}
    text = " ".join(explore.describe_card(cards["Clash"])["lines"])
    assert "Can only be played if every card in your hand is an Attack." in text, text
    old = {k: v for k, v in cards["Clash"].items() if k != "playable_if"} | {"only_attacks_in_hand": True}
    assert " ".join(explore.describe_card(old)["lines"]) == text
    assert not explore.UNWORDED, explore.UNWORDED


def test_explorer_words_power_rules():
    import explore
    explore.UNWORDED.clear()
    powers = {p["id"]: p for pk in PACKS for p in json.loads(pk.read_text(encoding="utf-8")).get("powers", [])}
    ent = " ".join(explore.describe_power(powers["Entangled"])["lines"])
    cor = " ".join(explore.describe_power(powers["Corruption"])["lines"])
    assert "can't play Attack cards" in ent, ent
    assert "Skill cards cost 0" in cor and "plays a Skill, exhaust it" in cor, cor
    assert not explore.UNWORDED, explore.UNWORDED


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
