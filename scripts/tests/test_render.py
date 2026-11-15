"""Render names the exhaust-cards chance event (docs/specs/exhaust-cards.md,
Fits with: Render). Picks are not rendered, as before C1. About 1 s."""

import os

import sts

PACK = os.path.join(os.path.dirname(__file__), "..", "..", "content", "packs", "act1-ironclad.json")


def test_render_names_random_exhaust():
    """True Grit with two distinct cards in hand pauses at RandomExhaust
    (limit 1 keeps its two outcomes unlisted), and render says so."""
    sts.load_content(PACK)
    c = sts.Combat(["gen:True Grit", "Strike", "Strike", "Defend", "Defend"], "jaw_worm", seed=1)
    (paused,) = [outs[0][1] for acts, kind, outs in c.options(1) if "True Grit" in str(acts[0]) and kind == "divergent"]
    assert paused.render().endswith("(paused at chance event: random exhaust from hand)")


MONSTERS = os.path.join(os.path.dirname(__file__), "..", "..", "content", "packs", "act1-monsters.json")
DECK = ["Strike"] * 4 + ["Defend"] * 4 + ["Bash", "Inflame", "Shrug It Off", "Pommel Strike", "Clothesline", "Bash+"]


def _pile_text(counts):
    """A pile as render writes it: names in board order, 'x<n>' past one."""
    return ", ".join(n if k == 1 else f"{n} x{k}" for n, k in counts) or "-"


def _powers_text(powers):
    return f"  [{', '.join(f'{p['name']} {p['amount']}' for p in powers)}]" if powers else ""


def _board_states():
    """About 200 states: greedy-ish walks (first legal option, seeded) over
    official encounters, the bosses and pack monsters (versus)."""
    sts.load_content(MONSTERS)
    starts = [sts.Combat(DECK, e, seed=s) for e in ("jaw_worm", "gremlin_nob", "three_sentries", "hexaghost",
                                                     "the_guardian", "lots_of_slimes", "three_louse") for s in (1, 2)]
    starts += [sts.Combat.versus(DECK, ["gen:Mad Gremlin", "gen:Fat Gremlin"], seed=3),
               sts.Combat.versus(DECK, ["gen:Blue Slaver"], seed=4)]
    out = []
    for k, c in enumerate(starts):
        for step in range(14):
            out.append(c)
            if c.is_over():
                break
            if not c.awaiting_action():
                c = c.clone()
                c.advance()
                continue
            opts = c.options(4)
            _, _, outs = opts[(k + step) % len(opts)]
            c = outs[0][1]
            if not c.is_over() and not c.awaiting_action():
                c.advance()
    return out


def test_board_matches_render():
    """Combat.board() (docs/specs/explorer-v2.md) holds render()'s numbers
    and names: rebuilt from board() line by line, render's text comes back."""
    states = _board_states()
    assert len(states) >= 150
    for c in states:
        b = c.board()
        p = b["player"]
        status = "" if not b["over"] else ("  WON" if b["won"] else "  LOST")
        lines = [f"Turn {b['turn']}  HP {p['hp']}/{p['max_hp']}  Block {p['block']}  Energy {p['energy']}"
                 f"{_powers_text(p['powers'])}{status}"]
        if p["potions"]:
            lines.append("Potions " + ", ".join(f"{i}:{q}" for i, q in enumerate(p["potions"])))
        for m in b["monsters"]:
            i = m["intent"]
            intent = "?" if i is None else (f"{i['name']} ({i['damage']})" if i["damage"] > 0 else i["name"])
            lines.append(f"  [{m['slot']}] {m['name']}  HP {m['hp']}/{m['max_hp']}  Block {m['block']}  intent: {intent}"
                         f"{_powers_text(m['powers'])}")
        lines.append("Hand: " + _pile_text([(h["name"], h["count"]) for h in b["hand"]]))
        piles = b["piles"]
        lines.append(f"Draw {piles['draw']['count']} | Discard {piles['discard']['count']} | Exhaust {piles['exhaust']['count']}")
        text = "\n".join(lines)
        if b["pending"] is not None:
            text += f"\n(paused at chance event: {b['pending']})"
        assert text == c.render(), (text, c.render())
        assert (p["hp"], (p["block"], p["energy"])) == (c.player_hp(), c.player_block_energy)
        assert b["turn"] == c.turn()
        named = c.piles()
        for pile in ("draw", "discard", "exhaust"):
            assert dict(piles[pile]["cards"]) == named[pile]
            assert piles[pile]["count"] == sum(named[pile].values())
            assert [n for n, _ in piles[pile]["cards"]] == sorted(named[pile])  # contents by name, never order
        assert {h["name"]: h["count"] for h in b["hand"]} == named["hand"]
        for h in b["hand"]:
            assert isinstance(h["cost"], int) and h["upgraded"] == h["name"].endswith("+")
        assert all(n in named["draw"] for n in piles["draw"]["known_top"])


def _play(c, name):
    """The child after playing `name` (first target), a deterministic option."""
    for acts, kind, outs in c.options(30):
        if len(acts) == 1 and str(acts[0]).startswith(f"Action({name}"):
            assert kind == "deterministic" and len(outs) == 1
            return outs[0][1]
    raise AssertionError(f"no option {name} in {c.legal_actions()}")


def test_combat_eq():
    """Combat equality and hash (docs/specs/explorer-v2.md Amendment 1):
    over the engine state, the RNG left out, so two card orders that reach
    the same state are one afterstate."""
    deck = ["Strike"] * 5 + ["Defend"] * 5
    c = next(x for x in (sts.Combat(deck, "jaw_worm", seed=s) for s in range(50))
             if x.piles()["hand"].get("Strike") and x.piles()["hand"].get("Defend"))
    assert c == c.clone() and hash(c) == hash(c.clone())
    a = _play(_play(c, "Strike"), "Defend")
    b = _play(_play(c, "Defend"), "Strike")
    assert a != c and _play(c, "Strike") != c
    assert a == b and hash(a) == hash(b)
    assert a.with_seed(12345) == a and hash(a.with_seed(12345)) == hash(a)
    assert (c == "not a combat") is False and c != None  # noqa: E711
    sts.load_content(MONSTERS)
    p = sts.Combat.versus(deck, ["gen:Blue Slaver"], seed=4)
    try:
        p.encode()
        raise AssertionError("a pack state should have no encoding")
    except ValueError:
        pass
    q = p.clone()
    assert p == q and hash(p) == hash(q)
    assert _play(p, "Defend") != p
