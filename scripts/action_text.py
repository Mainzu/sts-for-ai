"""Action text and record specs, shared by every stored record (game records,
bench files, the solver's positions; docs/decisions.md "Contract as built" "Records").

Action text: `End`, a card key `Card`, `Card@slot` (target monster slot), as
records have always stored them; `Potion:<slot>`, `Potion:<slot>@<target>`
(the held potion in list position `slot`, docs/specs/potions.md). Reserved forms parse and format now, so no
record written later has to be migrated, but raise `NotSupported` when
replayed until their spec builds them:
- `Done`, `Choose:<candidate>` (a card key; built in spec 6), `Choose:#i`
  (an inline option: not built yet);
- a card key with per-copy overrides, `Card{field=value/lifetime,...}`
  (fields sorted), then `@slot`: built in spec 8, replayed through
  `decode_in` (a variant is named only within its combat).
No card name contains `| @ { } : #` (`names_safe` test), so the forms can't
be confused with a card key.

Record specs: a reader treats a missing key as its default (`SPEC_DEFAULTS`),
so an old record replays unchanged when newer keys are added."""

import sts

SPEC_DEFAULTS = {"hp": None, "character": "ironclad", "no_death": False, "potions": None, "ascension": 0}
RESERVED_CHARS = "|@{}:#"
# A generated card's key (registry-lite): `gen:<id>`, the id free of the
# reserved characters; parsed after `Choose:` and `Potion:`, so unambiguous.
GEN = "gen:"


class NotSupported(ValueError):
    """A reserved action form replayed before its spec is built."""


def encode_action(a):
    """An `sts.Action`'s text."""
    if a.is_end_turn:
        return "End"
    if a.kind == "done":
        return "Done"
    if a.kind == "choose":
        return f"Choose:{a.card}"
    if a.kind == "potion":
        return f"Potion:{a.slot}" + ("" if a.target is None else f"@{a.target}")
    return a.card if a.target is None else f"{a.card}@{a.target}"


def _int(s, text):
    if not s.isdigit():
        raise ValueError(f"bad action text {text!r}")
    return int(s)


def parse_action(text):
    """The action text as a dict: {"kind": "end"} / {"kind": "done"} /
    {"kind": "choose", "candidate": key} or {"kind": "choose", "option": i} /
    {"kind": "potion", "slot", "target"} /
    {"kind": "card", "card", "target", "overrides": [(field, value, lifetime)]}."""
    if text == "End":
        return {"kind": "end"}
    if text == "Done":
        return {"kind": "done"}
    if text.startswith("Choose:"):
        cand = text[len("Choose:"):]
        if cand.startswith("#"):
            return {"kind": "choose", "option": _int(cand[1:], text)}
        key = cand[len(GEN):] if cand.startswith(GEN) else cand
        # A variant candidate carries its overrides: `Card{field=value/lifetime}`.
        body, brace, rest = key.partition("{")
        if brace and not (rest.endswith("}") and rest[:-1]):
            raise ValueError(f"bad action text {text!r}")
        if not body or any(ch in body for ch in RESERVED_CHARS):
            raise ValueError(f"bad action text {text!r}")
        return {"kind": "choose", "candidate": cand}
    if text.startswith("Potion:"):
        slot, at, target = text[len("Potion:"):].partition("@")
        return {"kind": "potion", "slot": _int(slot, text), "target": _int(target, text) if at else None}
    body, at, target = text.partition("@")
    card, brace, rest = body.partition("{")
    overrides = []
    if brace:
        if not rest.endswith("}") or not rest[:-1]:
            raise ValueError(f"bad action text {text!r}")
        for part in rest[:-1].split(","):
            field, eq, vl = part.partition("=")
            value, slash, lifetime = vl.partition("/")
            if not (field and eq and value and slash and lifetime):
                raise ValueError(f"bad action text {text!r}")
            overrides.append((field, value, lifetime))
        overrides.sort()
    key = card[len(GEN):] if card.startswith(GEN) else card
    if not key or any(ch in key for ch in RESERVED_CHARS):
        raise ValueError(f"bad action text {text!r}")
    return {"kind": "card", "card": card, "target": _int(target, text) if at else None, "overrides": overrides}


def format_action(p):
    """`parse_action`'s inverse; overrides are written sorted by field."""
    kind = p["kind"]
    if kind == "end":
        return "End"
    if kind == "done":
        return "Done"
    if kind == "choose":
        return f"Choose:#{p['option']}" if "option" in p else f"Choose:{p['candidate']}"
    if kind == "potion":
        return f"Potion:{p['slot']}" + ("" if p["target"] is None else f"@{p['target']}")
    ov = sorted(p.get("overrides") or [])
    body = p["card"] + ("{" + ",".join(f"{f}={v}/{l}" for f, v, l in ov) + "}" if ov else "")
    return body + ("" if p["target"] is None else f"@{p['target']}")


def decode_action(text):
    """The `sts.Action` the text names; reserved forms raise `NotSupported`."""
    p = parse_action(text)
    kind = p["kind"]
    if kind == "end":
        return sts.Action()
    if kind == "done":
        return sts.Action.done()
    if kind == "choose" and "option" in p:
        raise NotSupported(f"{text!r}: inline options are not supported yet")
    if kind == "choose":
        return sts.Action.choose(p["candidate"])
    if kind == "potion":
        return sts.Action.potion(p["slot"], p["target"])
    if p["overrides"]:
        raise NotSupported(f"{text!r}: per-copy overrides are not supported until spec 8")
    return sts.Action(p["card"], p["target"])


def decode_in(combat, text):
    """`decode_action`, also for a generated card's action, which names a
    slot only `combat` binds: picked from its legal actions by text."""
    p = parse_action(text)
    # Named only within this combat: a generated card's slot, or a card with
    # per-copy overrides (a variant): picked among the legal actions.
    in_combat = (p["kind"] == "card" and (p["card"].startswith(GEN) or p["overrides"])) or (
        p["kind"] == "choose" and (p.get("candidate", "").startswith(GEN) or "{" in p.get("candidate", "")))
    if in_combat:
        for a in combat.legal_actions():
            if encode_action(a) == text:
                return a
        raise ValueError(f"{text!r} is not a legal action here")
    return decode_action(text)


def combat_of(record):
    """The starting `sts.Combat` of a stored spec (a game record, a bench
    decision), missing keys read as their defaults; `potions` (names) are
    the potions the fight starts holding."""
    get = lambda k: record.get(k, SPEC_DEFAULTS[k])  # noqa: E731
    return sts.Combat(record["deck"], record["encounter"], seed=record["seed"], hp=get("hp"),
                      character=get("character"), no_death=bool(get("no_death")), potions=get("potions"),
                      ascension=get("ascension"))
