"""The real-game bridge (docs/specs/real-game-bridge.md): plays the fights of
a real Slay the Spire run through CommunicationMod with the product's policy.

    python scripts/real_game.py launch <player>    # start the game (real_game_launch.py's guards)
    python scripts/real_game.py launch --loop <player> --runs 1 --act1-only   # relaunch after each run
    python scripts/real_game.py play <player> [--runs N] [--ascension A] [--act1-only]   # the controller; CommunicationMod starts it

--act1-only: a run stops when Act 2 starts (the engine models Act 1 only) and
is recorded as stopped there; when its runs are played the controller closes
the game, so an outer loop can launch the next one.

CommunicationMod writes one JSON state per line on the controller's stdin and
reads one command per line from its stdout, so stdout carries commands only;
everything else goes to results/real-game/<stamp>/ (gitignored, kept as the
run's record): states.jsonl, decisions.jsonl, fights.jsonl, log.txt and
status.txt (one line: what the controller is doing, for the owner to watch).

It plays whole runs: from the main menu it starts an Ironclad run (only while
no Ironclad save exists), and outside fights it follows real_game_run.py's
rules (map, events, rewards, card picks by the sim chooser, rest, shops).
In a fight it rebuilds the engine fight from the game's state (`translate`),
picks actions with depth_paired's policy (`decide` + `planned`) and sends
them; it checks each predicted (chance-free) step against the game's next
state. A card or monster the engine doesn't load, or a command the game
refuses, hands the rest of the fight to a simple fallback (status.txt and
fights.jsonl say why). runs.jsonl holds one line per finished run."""

import functools
import json
import os
import random
import sys
import time

import real_game_run

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ACT1_PACKS = ["act1-ironclad", "act1-colorless", "act1-monsters", "act1-relics", "act1-potions"]
STARTER_RELIC = "Burning Blood"
EMPTY_POTION = "Potion Slot"
# Rebuilds a fight's hidden parts (move positions, rolled damage, engine-only
# powers) from this many samples of the engine's own last step.
SAMPLES = 32
# The controller runs under pythonw (no console): a console program it starts
# would open a window of its own, so each one starts without.
NO_WINDOW = 0x08000000
# The fighter's version beside the product's search, recorded with each run
# like the run rules: 0, the search's pick as it is; 1, the best option that
# wins the fight at once whenever one exists (`winning_options`; the search
# passed such wins when the net's score for carrying on beat them, as run 56
# left a Blue Slaver at 6 HP for ten turns).
FIGHT_GUARD = 1
# After a potion command, how many "wait"s a state from before the potion
# acted gets before the controller asks for the state instead.
POTION_WAITS = 3
PICK_SCREENS = ("HAND_SELECT", "GRID")
# Monsters that split: the game keeps the dead one in its list and adds the
# halves at the end, where the engine reuses slots; a dead one is left out of
# the view, and actions reach the game's list through the slot map.
SPLITTERS = {"SlimeBoss", "AcidSlime_L", "SpikeSlime_L"}
# Powers whose amount can really be negative (game_number: their -1 is a
# number). The engine holds power amounts as plain signed numbers and sts
# exposes no flag for this, so the list lives here;
# test_negative_powers_cover_the_packs checks that every pack effect that
# applies a negative amount names one of these.
NEGATIVE_POWERS = {"Strength", "Dexterity", "Focus"}


def game_number(v, may_be_negative=False):
    """A number CommunicationMod shows, or None for the game's "no number":
    -1 on a relic without a counter (Art of War) or a power without an
    amount (Barricade). A power that can be negative shows a real -1."""
    return None if v == -1 and not may_be_negative else v


def run_mark():
    """The file the controller writes when it starts a run, removed when the run ends."""
    return os.path.join(ROOT, "results", "real-game", "ironclad-run-started")


class HandOver(Exception):
    """The engine can't play this fight; the message says why."""


def setup_paths():
    for p in (HERE, os.path.join(HERE, "analysis")):
        if p not in sys.path:
            sys.path.insert(0, p)


def load_packs():
    import sts
    for p in ACT1_PACKS:
        sts.load_content(os.path.join(ROOT, "content", "packs", p + ".json"))


# ---------------------------------------------------------------- translate

def engine_only_powers():
    import game_ids
    return set(game_ids.tables().get("engine_only", {}).get("powers", {}))


def card_of(card):
    """A CommunicationMod card's engine name, or HandOver."""
    import game_ids
    name = game_ids.card_name(card["id"], card.get("upgrades", 0))
    if name is None:
        raise HandOver("card %s%s not loaded" % (card["id"], "+" * card.get("upgrades", 0)))
    return name


def marked_of(card, marks):
    """A game card's engine name with the mark this fight gave its copy
    (Rampage{damage=13/combat}): `marks` maps the game's card uuid to it."""
    n = card_of(card)
    m = (marks or {}).get(card.get("uuid"))
    return m if m and m.split("{")[0] == n else n


def with_cost(name, cost):
    """`name` with its combat cost mark set to `cost`, or taken off when
    `cost` is None (the engine's mark order: damage, then cost)."""
    base, _, rest = name.partition("{")
    marks = [m for m in rest.rstrip("}").split(",") if m and not m.startswith("cost=")]
    if cost is not None:
        marks.append("cost=%d/combat" % cost)
    return "%s{%s}" % (base, ",".join(marks)) if marks else base


@functools.lru_cache(maxsize=1)
def cost_rules():
    """What the engine works out itself about costs, from the packs:
    {power: card type (the game's word)} for powers that set a type's cost
    (Corruption: skills cost 0), and the cards whose cost drops with each
    HP loss (Blood for Blood): {name without "gen:" and "+": (cost,
    upgraded cost)}."""
    sets, dynamic = {}, {}
    for name in ACT1_PACKS:
        with open(os.path.join(ROOT, "content", "packs", name + ".json"), encoding="utf-8") as f:
            pack = json.load(f)
        for e in pack.get("powers", []):
            if "sets_cost" in e:
                sets[e["id"]] = e["sets_cost"]["type"].upper()
        for e in pack.get("cards", []):
            if e.get("cost_less_per_hp_loss"):
                up = (e.get("upgrade") or {}).get("cost", 0)
                dynamic[e["id"]] = (e["cost"], max(e["cost"] + up, 0) if isinstance(up, int) else None)
    return sets, dynamic


def namer(gs, marks=None, cost_ignored=()):
    """card -> its engine name in game state `gs`: the mark its uuid carries
    (Rampage's damage), and a cost mark where the game shows a cost other
    than the master deck's copy (Snecko Oil rolls them; free-this-turn cards
    are told apart in merge). A card whose cost drops with each HP loss
    (Blood for Blood) is compared with its own cost from the pack, so each
    copy carries its drops, in the deck or not (the engine drops each copy
    as the game does). A power that sets a type's cost (Corruption) is left
    to the engine; other cards not in the deck keep their name, and so do
    the copies in `cost_ignored` (uuids)."""
    import game_ids
    costs = {}
    for c in gs.get("deck", []):
        costs.setdefault((c["id"], c.get("upgrades", 0)), set()).add(c.get("cost"))
    pl = (gs.get("combat_state") or {}).get("player", {})
    held = {game_ids.engine_name("powers", x["id"]) for x in pl.get("powers", [])}
    sets, dynamic = cost_rules()
    keep = {t for power, t in sets.items() if power in held}

    def name(card):
        n = marked_of(card, marks)
        base = costs.get((card["id"], card.get("upgrades", 0)), set())
        own = dynamic.get(n.split("{")[0].removeprefix("gen:").rstrip("+"))
        if own is not None and own[card.get("upgrades", 0) > 0] is not None:
            base = {own[card.get("upgrades", 0) > 0]}
        shown = card.get("cost")
        if (len(base) != 1 or shown is None or shown < 0 or min(base) is None or min(base) < 0
                or card.get("uuid") in cost_ignored or card.get("type") in keep):
            return n
        return with_cost(n, None if shown == min(base) else shown)
    return name


def lost_hp_seen(gs):
    """The least HP-loss count the game's cards show, or None: a card whose
    cost drops with each HP loss (Blood for Blood) shows its drops as its
    own cost minus the cost it shows. A copy in play when damage lands
    (Sharp Hide's thorns on it) misses that drop and an upgrade in the
    fight resets it, so this is the largest drop a copy shows; the count
    only sets the cost of a copy made in the fight (the game's `makeCopy`).
    A copy at cost 0 shows only that the count is at least its cost."""
    _, dynamic = cost_rules()
    cs = gs.get("combat_state") or {}
    drops = []
    for k in ("hand", "draw_pile", "discard_pile"):
        for c in cs.get(k, []):
            try:
                n = card_of(c)
            except HandOver:
                continue
            own = dynamic.get(n.removeprefix("gen:").rstrip("+"))
            b = own and own[c.get("upgrades", 0) > 0]
            shown = c.get("cost")
            if b is not None and shown is not None and shown > 0:
                drops.append(b - shown)
    return max(drops) if drops else None


def pile(cards, name=None):
    out = {}
    for c in cards:
        n = (name or card_of)(c)
        out[n] = out.get(n, 0) + 1
    return out


def new_mark(before, after, card):
    """The name a played copy of `card` took in this step (its combat mark
    changed: Rampage's damage), from the engine's piles before and after,
    or None when it kept its name."""
    def total(piles):
        out = {}
        for p in piles.values():
            for n, k in p.items():
                out[n] = out.get(n, 0) + k
        return out
    b, a = total(before), total(after)
    if a.get(card, 0) >= b.get(card, 0):
        return None
    base = card.split("{")[0]
    grew = [n for n in a if n.split("{")[0] == base and a[n] > b.get(n, 0) and n != card]
    return grew[0] if len(grew) == 1 else None


def powers_of(game_powers, left_out, who, shown_none=None):
    """{engine power: amount} of a creature's game powers; a power with no
    engine name is left out and noted (unless the engine models it elsewhere).
    A power the game shows without an amount is 1 here and named in
    `shown_none`, so merge can keep the engine's own count (No Draw)."""
    import game_ids
    out = {}
    for p in game_powers:
        name = game_ids.engine_name("powers", p["id"])
        if name is None:
            if not game_ids.modelled_elsewhere("powers", p["id"]):
                left_out.add("power %s on %s" % (p["id"], who))
            continue
        amount = game_number(p["amount"], name in NEGATIVE_POWERS)
        if amount is None and shown_none is not None:
            shown_none.add(name)
        out[name] = out.get(name, 0) + (1 if amount is None else amount)  # held, no amount: the engine's 1
    return out


def group_of(game_state):
    room = game_state.get("room_type", "")
    return "boss" if "Boss" in room else "elite" if "Elite" in room else "hallway"


def observed(gs, fight):
    """The view of the game's state as far as the game shows it (no hidden
    parts yet): monsters carry `candidates`, the engine move positions their
    shown move can be, and `game_index`, their place in the game's list (a
    dead splitter is left out). Notes what it leaves out in fight["left_out"]."""
    import game_ids
    cs = gs["combat_state"]
    left = fight["left_out"]
    naming = namer(gs, fight.get("marks"))
    # A free copy played this turn shows its turn's cost in the discard pile
    # until its flight there lands (Soul.update -> clearPowers): out of the
    # hand, its shown cost is ignored for the rest of the turn.
    away = namer(gs, fight.get("marks"), fight.get("turn_free") or ())
    pl = cs["player"]
    alive_len = fight.setdefault("alive_len", {})  # splitter index -> the game's list length while it lived
    no_amount = set()
    relics = []
    for r in gs.get("relics", []):
        if r["id"] == STARTER_RELIC:
            continue
        name = game_ids.engine_name("relics", r["id"])
        if name is None:
            left.add("relic " + r["id"])
            continue
        # No counter shown: merge keeps the engine's own value (Art of War's flag).
        counter = game_number(r.get("counter", 0))
        relics.append((name, None if counter is None else max(counter, 0)))
    potions = []
    for p in gs.get("potions", []):
        if p["id"] == EMPTY_POTION:
            continue
        name = game_ids.engine_name("potions", p["id"])
        if name is None:
            left.add("potion " + p["id"])
            continue
        potions.append(name)
    monsters = []
    for i, m in enumerate(cs["monsters"]):
        name = game_ids.engine_name("monsters", m["id"])
        if name is None:
            raise HandOver("monster %s not loaded" % m["id"])
        gone = m.get("is_gone", False) or m["current_hp"] <= 0
        if m["id"] in SPLITTERS:
            # A split adds the halves at the end of the game's list; a
            # splitter killed outright (an attack on all, run 27) stays a
            # dead monster, as in the engine.
            if not gone:
                alive_len[i] = len(cs["monsters"])
            elif len(cs["monsters"]) > alive_len.get(i, i + 1):
                continue
        escaped = gone and m["current_hp"] > 0  # Looter: left with its HP
        mv = {"name": name, "hp": m["current_hp"] if escaped else 0 if gone else m["current_hp"], "max_hp": m["max_hp"],
              "block": m["block"], "powers": powers_of(m.get("powers", []), left, name), "escaped": escaped,
              "game_index": i}
        if not gone:
            moves = game_ids.moves(m["id"])
            if m.get("move_id") not in moves:
                raise HandOver("move %s of %s not mapped" % (m.get("move_id"), m["id"]))
            mv["candidates"] = moves[m["move_id"]]
            mv["shown_damage"] = m.get("move_base_damage", -1)
        monsters.append(mv)
    return {
        "turn": cs["turn"],
        "cards_played_this_turn": fight["played_this_turn"],
        "start_hp": fight["start_hp"],
        "player": {"hp": pl["current_hp"], "max_hp": pl["max_hp"], "block": pl["block"], "energy": pl["energy"],
                   "powers": powers_of(pl.get("powers", []), left, "player", no_amount), "relics": relics,
                   "potions": sorted(potions)},
        "no_amount": sorted(no_amount),
        "hand": pile(cs["hand"], naming), "draw": pile(cs["draw_pile"], away),
        "discard": pile(cs["discard_pile"], away), "exhaust": pile(cs["exhaust_pile"], away),
        # Whether the game showed the costs (merge then takes no cost marks
        # from the engine's own guesses).
        "costs_shown": bool(gs.get("deck")) and any("cost" in c for c in cs["hand"]),
        # Hand cards the game shows at cost 0 this turn (merge keeps the
        # engine's free marks only on those); a card without a cost counts.
        "zero_cost": pile([c for c in cs["hand"] if c.get("cost", 0) == 0]),
        "lost_hp_seen": lost_hp_seen(gs),
        # Cards made in the fight (not in the master deck) that the game shows
        # at cost 0: a potion's or Infernal Blade's card, free this turn.
        # (by id: a deck card upgraded in the fight, Anger+ by Armaments, isn't one)
        "made_free": pile([c for c in cs["hand"] if c.get("cost") == 0 and gs.get("deck")
                           and c["id"] not in {d["id"] for d in gs["deck"]}]),
        "monsters": monsters,
        # The game's ascension level, only above 0 as the engine's views
        # write it: Combat.from_view plays the monsters at it.
        **({"ascension": gs["ascension_level"]} if gs.get("ascension_level") else {}),
    }


def merge(obs, priors, last_moves, notes):
    """The full view: `obs` with each hidden part taken from the first prior
    view (the engine's own predictions) that agrees with what the game shows;
    `last_moves` ((slot, monster) -> its move position last turn; a split
    puts new monsters where the engine's slots differ) where none does."""
    hidden = engine_only_powers()
    view = plain(obs)
    zero = view.pop("zero_cost", None)
    costs_shown = view.pop("costs_shown", False)
    no_amount = view.pop("no_amount", [])
    made_free = view.pop("made_free", {})
    lost_seen = view.pop("lost_hp_seen", None)
    for i, m in enumerate(view["monsters"]):
        m.pop("game_index", None)
        cands = m.pop("candidates", None)
        shown = m.pop("shown_damage", None)
        if cands is None:  # gone: its hidden parts as the engine last had them
            same = [pv["monsters"][i] for pv in priors if i < len(pv["monsters"]) and pv["monsters"][i]["name"] == m["name"]]
            if same:
                for k in ("moves", "rolled_damage", "just_applied", "powers"):
                    m[k] = same[0].get(k, m.get(k))
            else:
                m["moves"] = [None, None]
            continue
        match = None
        for pv in priors:
            pm = pv["monsters"][i] if i < len(pv["monsters"]) else None
            if pm and pm["name"] == m["name"] and pm["moves"][0] in cands:
                match = pm
                break
        if match is None:
            if len(cands) > 1:
                notes.append("slot %d: move %s ambiguous, took %s" % (i, cands, cands[0]))
            m["moves"] = [cands[0], last_moves.get((i, m["name"]))]
        else:
            m["moves"] = list(match["moves"])
            m["rolled_damage"] = match.get("rolled_damage", 0)
            for p in hidden & set(match.get("powers", {})):
                m["powers"][p] = match["powers"][p]
            m["just_applied"] = [p for p in match.get("just_applied", []) if p in m["powers"]]
        if "Louse" in m["name"] and shown and shown > 0:
            m["rolled_damage"] = shown
    pl = view["player"]
    if priors:
        pp = priors[0]["player"]
        for p in hidden & set(pp.get("powers", {})):
            pl["powers"][p] = pp["powers"][p]
        # Shown without an amount (a flag in the game): the engine's own
        # count where it holds the power (No Draw stacks there).
        for p in no_amount:
            if pp.get("powers", {}).get(p, 0) > 0:
                pl["powers"][p] = pp["powers"][p]
        pl["just_applied"] = [p for p in pp.get("just_applied", []) if p in pl["powers"]]
        # The fight holds only the relics that act in its kind (Pantograph in
        # boss fights): those the engine kept.
        kept = {r[0]: r[1] for r in pp.get("relics", [])}
        pl["relics"] = [[r[0], kept[r[0]] if r[1] is None else r[1]] for r in pl["relics"] if r[0] in kept]
        # Copies changed in this fight (Rampage's damage) keep their marks:
        # the game's card list doesn't show them.
        for k in ("hand", "draw", "discard", "exhaust"):
            for marked, n in priors[0].get(k, {}).items():
                base = marked.split("{")[0]
                if costs_shown and "cost=" in marked:
                    continue  # the game's own costs named those copies
                if marked != base and view[k].get(base, 0) > 0:
                    moved = min(n, view[k][base])
                    view[k][base] -= moved
                    if not view[k][base]:
                        del view[k][base]
                    view[k][marked] = view[k].get(marked, 0) + moved
        # The game doesn't show it, and it counts cards Havoc plays: the
        # engine's count, not the controller's own plays.
        view["cards_played_this_turn"] = priors[0].get("cards_played_this_turn", view["cards_played_this_turn"])
        view["times_lost_hp"] = max(priors[0].get("times_lost_hp", 0), lost_seen or 0)
        view["boss_fight"] = priors[0].get("boss_fight", False)
        # Free this turn (Liquid Memories) only where the game agrees: its
        # card-flight animation resets the cost of a card taken back from the
        # discard pile before it landed there (Soul.update -> clearPowers).
        # A card free this turn shows cost 0, which the translator read as a
        # combat cost mark: where the engine marked it free, it is that.
        for c, n in priors[0].get("free", {}).items():
            z = with_cost(c, 0)
            if c not in view["hand"] and z != c and view["hand"].get(z, 0) > 0:
                k = min(n, view["hand"][z])
                view["hand"][z] -= k
                if not view["hand"][z]:
                    del view["hand"][z]
                view["hand"][c] = view["hand"].get(c, 0) + k
        view["free"] = {}
        left = dict(zero) if zero is not None else None
        for c, n in priors[0].get("free", {}).items():
            if c not in view["hand"]:
                continue
            if left is not None:
                base = c.split("{")[0]
                n = min(n, left.get(base, 0))
                left[base] = left.get(base, 0) - n
            if n > 0:
                view["free"][c] = n
        for c, n in made_free.items():
            if c in view["hand"]:
                view["free"][c] = max(view["free"].get(c, 0), min(n, view["hand"][c]))
        # What the player knows of the draw pile's order (Headbutt), while
        # those cards are still in it.
        top = priors[0].get("top", [])
        floaters = priors[0].get("top_floaters", [])
        if all(view["draw"].get(c, 0) >= top.count(c) for c in top):
            view["top"], view["top_floaters"] = top, [list(x) for x in floaters if x[0] in view["draw"]]
    pl["relics"] = [[n, v or 0] for n, v in pl["relics"]]  # no engine value to keep: 0
    return view


def plain(v):
    """A view as JSON gives it back (tuples as lists), so views compare equal
    whether they came from the engine or through the translator."""
    return json.loads(json.dumps(v))


def compare(a, b):
    """The top-level and nested keys where views `a` and `b` differ (for the
    fidelity record)."""
    out = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            if isinstance(a.get(k), dict) and isinstance(b.get(k), dict):
                out += ["%s.%s" % (k, s) for s in compare(a[k], b[k])]
            elif isinstance(a.get(k), list) and isinstance(b.get(k), list) and len(a[k]) == len(b[k]):
                out += ["%s[%d].%s" % (k, i, s) for i, (x, y) in enumerate(zip(a[k], b[k]))
                        for s in (compare(x, y) if isinstance(x, dict) and isinstance(y, dict) else ["value"])
                        if x != y]
            else:
                out.append(k)
    return out


# ----------------------------------------------------------------- commands

def card_index(cards, name, namer_=None, playable=False):
    """The index of the game card for engine card `name`: the copy with the
    same marks first (Rampage{damage=13/combat}, a cost), else any copy of
    its base. `namer_` names the game's cards (namer)."""
    for exact in (True, False):
        for j, card in enumerate(cards):
            try:
                n = (namer_ or card_of)(card)
            except HandOver:
                continue
            if (n == name if exact else n.split("{")[0] == name.split("{")[0]) and (
                    not playable or card.get("is_playable", True)):
                return j
    return None


def command_for(action, gs, view, slots=None, marks=None):
    """The CommunicationMod command for an engine action in the game's state;
    `slots` maps the view's monster slots to the game's list (identity when None);
    `marks` maps game card uuids to their marked engine names."""
    cs = gs["combat_state"]
    kind = action.kind
    target = None if action.target is None else (slots[action.target] if slots else action.target)
    if kind == "end":
        return "end"
    if kind == "play":
        j = card_index(cs["hand"], action.card, namer(gs, marks), playable=True)
        if j is not None:
            cmd = "play %d" % ((j + 1) % 10 if j == 9 else j + 1)
            return cmd if target is None else "%s %d" % (cmd, target)
        raise HandOver("card %s not in the game's hand" % action.card)
    if kind == "potion":
        import game_ids
        name = view["player"]["potions"][action.slot]
        for j, p in enumerate(gs.get("potions", [])):
            if game_ids.engine_name("potions", p["id"]) == name:
                return "potion use %d" % j + ("" if target is None else " %d" % target)
        raise HandOver("potion %s not held in the game" % name)
    if kind == "choose":
        screen = gs.get("screen_type")
        cards = cs["hand"] if screen == "HAND_SELECT" else gs.get("screen_state", {}).get("cards", [])
        j = card_index(cards, action.card, namer(gs, marks))
        if j is not None:
            return "choose %d" % j
        raise HandOver("pick %s not offered by the game" % action.card)
    if kind == "done":
        return "confirm"
    raise HandOver("action kind %s" % kind)


def pick_offer(gs):
    """The engine names (base, no marks) of the cards the game's pick offers,
    or None when one isn't loaded."""
    cards = gs["combat_state"]["hand"] if gs.get("screen_type") == "HAND_SELECT" else gs.get("screen_state", {}).get("cards", [])
    names = [card_of_or_none(c) for c in cards]
    return None if None in names else set(names)


def offers(e, offered):
    """Whether engine state `e` waits at a pick whose cards are all among
    `offered` (the game may list cards the pick can't take)."""
    if e is None or not e.awaiting_action():
        return False
    picks = {a.card.split("{")[0] for a in e.legal_actions() if a.kind == "choose"}
    return bool(picks) and picks <= offered


def pick_sample(e, samples, gs, offered):
    """The engine state to answer the game's pick from: best the one (kept
    `e` first) whose piles are the game's (Warcry+ drew those two cards),
    else any whose pick offers only the game's cards, else `e`."""
    if offered is None:
        return e
    cands = [x for x in [e] + list(samples) if offers(x, offered)]
    return next((x for x in cands if same_piles(x, gs)), cands[0] if cands else e)


def same_piles(e, gs):
    """Whether engine state `e` holds the cards the game shows in each pile
    (by name, marks aside): the sample that drew what the game drew."""
    def bases(names):
        out = {}
        for n, k in names.items():
            b = n.split("{")[0]
            out[b] = out.get(b, 0) + k
        return out
    try:
        mine = e.piles()
    except ValueError:
        return False
    cs = gs["combat_state"]
    game = {"hand": cs["hand"], "draw": cs["draw_pile"], "discard": cs["discard_pile"], "exhaust": cs["exhaust_pile"]}
    try:
        return all(bases(dict(mine[k])) == bases(pile(v)) for k, v in game.items())
    except HandOver:
        return False


# --------------------------------------------------------------- controller

class Bridge:
    ascension = 0  # the level each run starts at (0-20); set by __init__
    act1_only = False  # stop each run when Act 2 starts; close the game when done
    def __init__(self, player, out, record_dir, runs=1, ascension=0):
        setup_paths()
        self.dir = record_dir
        import sts
        if not hasattr(sts.Combat, "from_view"):  # a later swap built from an older tree
            self.status("main's sts has no Combat.from_view: rebuild it from main (20735467 or later); playing nothing")
            raise SystemExit(1)
        import bench
        import ladder
        load_packs()
        self.ev = bench.load_evaluator(player)
        self.chooser = player  # the sim chooser's trial fights: the same net, one turn deep
        self.commit = code_commit()  # the code this controller loaded, for each run's record
        self.two = {"limit": bench.LIMIT, **ladder.TWO_TURN}
        self.player = player
        self.out = out
        self.dir = record_dir
        self.fight = None
        self.files = {k: open(os.path.join(record_dir, k + ".jsonl"), "a", encoding="utf-8")
                      for k in ("states", "decisions", "fights", "runs")}
        self.runs_left = runs
        self.ascension = ascension
        self.run = None  # the run in play: {seed, started, fights: [...]}
        self.card_done = None  # (floor, screen visit) whose card reward was looked at
        self.errors = 0  # refused commands in a row (outside fights)
        self.status("waiting for the main menu")

    def log(self, msg):
        print(time.strftime("%H:%M:%S"), msg, flush=True)  # stdout is the log file

    def status(self, msg):
        with open(os.path.join(self.dir, "status.txt"), "w", encoding="utf-8") as f:
            f.write(msg + "\n")
        self.log("status: " + msg)

    def write(self, kind, row):
        self.files[kind].write(json.dumps(row) + "\n")
        self.files[kind].flush()

    def send(self, cmd):
        self.log("send: " + cmd)
        self.out.write(cmd + "\n")
        self.out.flush()

    # A fight's memory: the game's floor, its kind, HP at the start, whether
    # it was handed over, what was left out, the engine's prediction for the
    # next state, the planned line, the fidelity counts.
    def new_fight(self, gs):
        import sts  # noqa: F401
        self.close_fight(gs)
        self.fight = {"floor": gs["floor"], "group": group_of(gs), "start_hp": gs["combat_state"]["player"]["current_hp"],
                      "seed": random.randrange(1 << 30), "handed_over": None, "left_out": set(), "played_this_turn": 0,
                      "turn": None, "n": 0, "queue": [], "engine": None, "expected": None, "priors": [],
                      "last_moves": {}, "marks": {}, "predicted": 0, "matched": 0, "mismatches": [], "decisions": 0,
                      "guarded": 0, "monsters": [m["id"] for m in gs["combat_state"]["monsters"]], "think_s": []}
        self.status("fight on floor %d (%s)" % (gs["floor"], self.fight["group"]))

    def close_fight(self, gs):
        f = self.fight
        if f is None:
            return
        # hp_after: the HP after the fight, end-of-fight relics included
        # (Burning Blood's +6); hp_end: the HP in the last state the game
        # showed during the fight (0 for a loss), before those relics.
        hp = gs.get("current_hp") if gs else None
        won = bool(hp and hp > 0)
        end = f.get("last_hp", hp) if won else 0
        self.write("fights", {"floor": f["floor"], "group": f["group"], "monsters": f["monsters"], "hp_start": f["start_hp"],
                              "hp_end": end, "hp_after": hp, "won": won, "handed_over": f["handed_over"],
                              "left_out": sorted(f["left_out"]), "decisions": f["decisions"], "guarded": f.get("guarded", 0),
                              "predicted": f["predicted"],
                              "matched": f["matched"], "mismatches": f["mismatches"][:50],
                              "think_s": [round(t, 2) for t in f["think_s"]]})
        if self.run is not None:
            self.run["fights"].append({"floor": f["floor"], "monsters": f["monsters"], "hp_end": end, "hp_after": hp,
                                       "handed_over": f["handed_over"]})
        self.fight = None
        self.status("playing the run (floor %s, A%s)" % (gs.get("floor") if gs else "?", self.ascension))

    def answer_error(self, msg, e):
        """After a controller error the game still waits for a command: in a
        fight, the fallback's (the fight is handed over); outside, "state"
        with the error counted, so the other ways out are tried next."""
        if self.fight and not self.fight["handed_over"]:
            self.hand_over("controller error: %s" % e)
        if not msg.get("ready_for_command"):
            return
        gs = msg.get("game_state") or {}
        if self.fight:
            try:
                cmd = real_game_run.fallback_command(gs, msg.get("available_commands", []), gs.get("choice_list", []))
            except Exception:
                cmd = None
            self.send(cmd or "state")
        else:
            self.errors += 1
            self.send("state")

    def hand_over(self, why):
        self.fight["handed_over"] = why
        self.status("fight on floor %d handed to you: %s" % (self.fight["floor"], why))

    def handle(self, msg):
        if "error" in msg:
            # The mod waits after an error: ask for the state again, and
            # outside fights try the next way out (errors count in a row).
            self.log("game error: %s" % msg["error"])
            if self.fight and not self.fight["handed_over"]:
                self.hand_over("the game refused a command: %s" % msg["error"])
            else:
                self.errors += 1
            self.send("state")
            return
        gs = msg.get("game_state")
        avail = msg.get("available_commands", [])
        if not msg.get("in_game") or gs is None:
            if self.fight:
                self.close_fight(gs or {})
            if msg.get("ready_for_command") and "start" in avail:
                self.main_menu()
            return
        if self.run is None and gs.get("screen_type") != "GAME_OVER":  # the death screen comes more than once
            self.run = {"seed": gs.get("seed"), "ascension": gs.get("ascension_level"),
                        "commit": getattr(self, "commit", None), "run_rules": real_game_run.RUN_RULES,
                        "fight_guard": FIGHT_GUARD, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "fights": []}
        # The death screen comes while the room is still in combat.
        if "combat_state" not in gs or gs.get("room_phase") != "COMBAT" or gs.get("screen_type") == "GAME_OVER":
            if self.fight:
                self.close_fight(gs)
            if msg.get("ready_for_command"):
                self.outside(gs, avail)
            return
        if self.fight is None or self.fight["floor"] != gs["floor"]:
            self.new_fight(gs)
        f = self.fight
        f["last_hp"] = gs["combat_state"]["player"]["current_hp"]
        if not msg.get("ready_for_command"):
            return
        if f["handed_over"]:
            cmd = real_game_run.fallback_command(gs, avail, gs.get("choice_list", []))
            if cmd:
                self.send(cmd)
            return
        try:
            if gs.get("screen_type") == "CARD_REWARD":  # a potion's card choice (Attack Potion)
                # The first card the engine loads (one it doesn't would hand
                # the fight over: Secret Technique, run 30), else skip.
                cards = gs.get("screen_state", {}).get("cards", [])
                ok = [j for j, c in enumerate(cards) if card_of_or_none(c)]
                f["left_out"].add("a potion's card choice (took the first the engine loads)")
                f["expected"], f["queue"] = None, []
                self.send("choose %d" % ok[0] if ok else "skip" if "skip" in avail else "choose 0")
                return
            if gs.get("screen_type") in PICK_SCREENS:
                self.pick(gs, avail)
            elif "play" in avail or "end" in avail:
                self.turn(gs)
        except HandOver as e:
            self.hand_over(str(e))
            cmd = real_game_run.fallback_command(gs, avail, gs.get("choice_list", []))
            if cmd:
                self.send(cmd)

    # ------------------------------------------------------------ run layer

    def main_menu(self):
        """Starts the next Ironclad run, while runs are left, the outer loop
        isn't stopping (results/real-game/stop-loop) and no Ironclad save
        exists (a saved run of the owner's is never touched). After a death
        the game stays open for the next run (it takes a while to start)."""
        import real_game_launch
        stopping = os.path.exists(stop_loop_file())
        if self.runs_left <= 0 or stopping:
            self.status("stopped at the main menu (results/real-game/stop-loop exists); %d runs left" % self.runs_left
                        if stopping and self.runs_left > 0 else "done: the runs asked for are played")
            if self.act1_only:
                close_game()
            return
        if os.path.exists(os.path.join(ROOT, "results", "real-game", "hold")):
            # Someone wants the game restarted between runs (new code or
            # content loads only at game start): wait here, start nothing.
            self.status("held at the main menu (results/real-game/hold exists); %d runs left" % self.runs_left)
            return
        save = ironclad_save()
        # The controller marks each run it starts (and removes the mark when
        # the run ends): a save newer than the mark is its own run (left by a
        # restart) and may be replaced.
        mark = run_mark()
        ours = os.path.exists(mark) and os.path.exists(save) and os.path.getmtime(save) >= os.path.getmtime(mark) - 5
        if os.path.exists(save) and not ours:
            self.status("an Ironclad save exists that the bridge didn't start; not starting a run over it")
            return
        self.runs_left -= 1
        self.run = None
        os.makedirs(os.path.dirname(mark), exist_ok=True)
        with open(mark, "w", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
        self.status("starting an Ironclad run at ascension %d" % self.ascension)
        self.send("start ironclad %d" % self.ascension)

    def outside(self, gs, avail):
        """One command outside fights (real_game_run.py's rules)."""
        if self.act1_only and (gs.get("act") or 1) >= 2 and self.run is not None:
            self.stop_run(gs, "after the Act 1 boss (Act 2 isn't modelled)")
            return
        screen = gs.get("screen_type")
        choices = gs.get("choice_list", [])
        key = (screen, gs.get("floor"), tuple(choices))
        if key != getattr(self, "last_screen", None):
            self.errors = 0  # a new screen: earlier refusals don't steer it
            self.last_screen = key
        # After refused commands or controller errors, the other ways out, in
        # turn, before the screen's own command (which may be what failed).
        if self.errors:
            if self.errors > 12:
                self.status("stuck on screen %s after %d refused commands; waiting" % (screen, self.errors))
                return
            ways = [w for w in ("proceed", "skip", "leave", "return", "confirm", "choose 0") if w.split()[0] in avail]
            if ways:
                self.send(ways[(self.errors - 1) % len(ways)])
                return
        cmd = None
        if screen == "GAME_OVER":
            self.end_run(gs)
            cmd = "proceed"
        elif screen == "EVENT":
            cmd = real_game_run.event_command(gs)
        elif screen == "MAP":
            cmd = real_game_run.map_command(gs, choices)
        elif screen == "COMBAT_REWARD":
            visit = gs.get("floor")
            cmd = real_game_run.reward_command(gs, self.card_done == visit)
            if cmd.startswith("choose") and gs["screen_state"]["rewards"][int(cmd.split()[1])]["reward_type"] == "CARD":
                self.card_done = visit
        elif screen == "CARD_REWARD":
            cmd = self.card_pick(gs, avail)
        elif screen == "REST":
            cmd = real_game_run.rest_command(gs, choices)
        elif screen == "CHEST":
            cmd = "choose 0" if choices else "proceed"
        elif screen == "BOSS_REWARD":
            self.run["act1_boss_beaten"] = True
            cmd = real_game_run.boss_relic_command(gs, choices)
        elif screen == "GRID":
            cmd = real_game_run.grid_command(gs, choices)
        elif screen == "HAND_SELECT":
            cmd = "choose 0" if choices else "confirm"
        elif screen in ("SHOP_ROOM", "SHOP_SCREEN"):
            cmd = "proceed" if "proceed" in avail else "leave"
        if cmd is None:
            for w in ("proceed", "confirm", "skip"):
                if w in avail:
                    cmd = w
                    break
        if cmd:
            self.send(cmd)

    def card_pick(self, gs, avail):
        """A card reward by the sim chooser: skip and each offered card the
        engine loads, scored by one-turn trial fights with the net against
        the next floor's pool and this act's boss (gauntlet.sim_score)."""
        import gauntlet
        import ladder
        ss = gs.get("screen_state", {})
        offered = [card_of_or_none(c) for c in ss.get("cards", [])]
        deck = [n for n in (card_of_or_none(c) for c in gs.get("deck", [])) if n]
        options = [None] + [n for n in offered if n]
        if len(options) == 1:
            return "skip" if "skip" in avail else "choose 0"
        floor, hp = gs.get("floor", 1), gs.get("current_hp", 80)
        boss = real_game_run.BOSS_ENCOUNTER.get(gs.get("act_boss"), "hexaghost")
        rng = random.Random(floor * 7919 + (self.run or {}).get("seed", 0) % 100000)
        pool = gauntlet.POOLS[real_game_run.next_kind(floor)]
        parts = [[(rng.choice(pool), "hallway", hp) for _ in range(gauntlet.SIM_FIGHTS)],
                 [(boss, "boss", gauntlet.rest(hp)) for _ in range(gauntlet.SIM_FIGHTS)]]
        specs = []
        for o in options:
            d = deck + ([o] if o else [])
            for p, part in enumerate(parts):
                for m, (e, group, start) in enumerate(part):
                    specs.append({"encounter": e, "deck": d, "seed": 9_000_000 + floor * 1000 + p * 100 + m,
                                  "hp": start, "character": "ironclad", "group": group,
                                  "ascension": gs.get("ascension_level") or 0})  # the run's own level
        t0 = time.time()
        res = ladder.play_bench(specs, self.chooser, 4)
        n = gauntlet.SIM_FIGHTS
        scores = []
        for k in range(len(options)):
            chunk = res[k * 2 * n:(k + 1) * 2 * n]
            scores.append(gauntlet.sim_score([chunk[:n], chunk[n:]]))
        best = max(range(len(options)), key=lambda i: (scores[i], -i))  # ties: skip, then the earlier card
        self.write("decisions", {"floor": floor, "card_reward": [c.get("id") for c in ss.get("cards", [])],
                                 "options": options, "scores": scores, "pick": options[best],
                                 "seconds": round(time.time() - t0, 2)})
        if options[best] is None:
            return "skip" if "skip" in avail else "choose 0"
        j = offered.index(options[best])
        return "choose %d" % j

    def stop_run(self, gs, why):
        """Ends the run here by choice: recorded as stopped, the game closed
        (an outer loop launches the next), then this run's own save deleted
        and the run mark removed (clear_own_save)."""
        if self.run.get("ascension") is None:
            self.run["ascension"] = gs.get("ascension_level")
        self.run.update({"ended": time.strftime("%Y-%m-%d %H:%M:%S"), "floor": gs.get("floor"), "act": gs.get("act"),
                         "stopped": why, "act1_boss_beaten": True})
        self.write("runs", self.run)
        self.run, self.card_done = None, None
        self.status("run stopped on floor %s %s; %d more to play" % (gs.get("floor"), why, self.runs_left))
        # CommunicationMod can't abandon a run, so the game closes (the outer
        # loop relaunches it), then this run's own save goes, so no mark or
        # bot save is left for the owner's Ironclad runs.
        seed = gs.get("seed")
        close_game()
        self.log(clear_own_save(seed))

    def end_run(self, gs):
        if self.run is None:
            return
        ss = gs.get("screen_state", {})
        if self.run.get("ascension") is None:
            self.run["ascension"] = gs.get("ascension_level")
        self.run.update({"ended": time.strftime("%Y-%m-%d %H:%M:%S"), "floor": gs.get("floor"),
                         "victory": ss.get("victory"), "score": ss.get("score"), "act": gs.get("act")})
        self.write("runs", self.run)
        self.status("run over on floor %s (A%s); %d more to play" % (gs.get("floor"), self.run.get("ascension"), self.runs_left))
        self.run = None
        self.card_done = None
        # The run is over: a later Ironclad save is no longer ours.
        try:
            os.remove(run_mark())
        except FileNotFoundError:
            pass

    def turn(self, gs):
        import sts
        f = self.fight
        if self.potion_unresolved(gs):
            return
        cs = gs["combat_state"]
        if cs["turn"] != f["turn"]:
            # Each monster's intent last turn: its move before this one.
            for i, m in enumerate((f.get("last_view") or {}).get("monsters", [])):
                if m["moves"][0] is not None:
                    f["last_moves"][(i, m["name"])] = m["moves"][0]
            f["turn"], f["played_this_turn"] = cs["turn"], 0
            f["turn_free"] = set()
        notes = []
        obs = observed(gs, f)
        f["slots"] = [m["game_index"] for m in obs["monsters"]]
        view = merge(obs, f["priors"] or self.fresh_priors(gs, f), f["last_moves"], notes)
        f["last_view"] = view
        expected = f["expected"]
        waited = f.pop("waited", False)  # after a "wait": the same step again, not a new prediction
        if expected is not None:
            diff = compare(expected, view)
            if not waited:
                f["predicted"] += 1
                if diff:
                    f["mismatches"].append({"turn": cs["turn"], "keys": diff})
                    self.log("prediction missed: %s" % diff)
                else:
                    f["matched"] += 1
            if diff:
                f["queue"] = []
        if expected is not None and not compare(expected, view) and f["queue"]:
            c = f["engine"]
        else:
            f["queue"] = []
            c = sts.Combat.from_view(view, seed=f["seed"], group=f["group"])
            self.plan(c, view, notes)
        self.act(c, gs, view)

    def plan(self, c, view, notes):
        import depth_paired
        f = self.fight
        t0 = time.time()
        seed = depth_paired.decision_seed(f["seed"], c.turn(), f["n"], True)
        d = depth_paired.decide(c, self.ev, self.two, None, seed, 0, 3, -1.0)
        win = guard_pick(c, d, seed) if FIGHT_GUARD else None
        if win is None:
            f["queue"] = depth_paired.planned(d, True)
        else:
            notes.append("took a winning option the search passed over (%d, not %d)" % (win, d["pick"]))
            d["pick"] = win
            f["queue"] = [d["r1"]["options"][win][0][0]]
            f["guarded"] = f.get("guarded", 0) + 1
        f["think_s"].append(time.time() - t0)
        f["decisions"] += 1
        import action_text
        self.write("decisions", {"floor": f["floor"], "turn": c.turn(), "view": view, "notes": notes,
                                 "options": [[action_text.encode_action(a) for a in acts] for acts, _ in d["r1"]["options"]],
                                 "one": [float(v) for v in d["v1"]], "two": None if d["v2"] is None else [float(v) for v in d["v2"]],
                                 "pick": int(d["pick"]), "cut": bool(d["cut"]),
                                 "line": [action_text.encode_action(a) for a in f["queue"]],
                                 "seconds": round(f["think_s"][-1], 2)})

    def act(self, c, gs, view):
        """Sends the queue's next action; keeps the engine's prediction of
        the next state (a view when the step has no chance in it, else
        samples for the hidden parts)."""
        f = self.fight
        if f["queue"][0].kind == "potion" and f.get("just_played"):
            # A card just played is still flying to the discard pile, and its
            # landing resets its cost: a potion that takes it back (Liquid
            # Memories) would be wasted (runs 1 and 38). Let it land first.
            f["just_played"], f["waited"] = False, True
            self.send("wait 30")
            return
        a = f["queue"].pop(0)
        f["just_played"] = a.kind == "play"
        cmd = command_for(a, gs, view, f["slots"], f["marks"])
        f["n"] += 1
        if a.kind == "play":
            f["played_this_turn"] += 1
        before = c.piles()
        self.predict(c, a)
        if a.kind == "play":
            # The played copy's new combat mark (Rampage's damage) follows
            # its uuid through shuffles; the game's list doesn't show it.
            j = int(cmd.split()[1])
            uuid = gs["combat_state"]["hand"][9 if j == 0 else j - 1].get("uuid")
            m = new_mark(before, f["engine"].piles(), a.card)
            if uuid and m:
                f["marks"][uuid] = m
            if uuid and view.get("free", {}).get(a.card):
                f.setdefault("turn_free", set()).add(uuid)
        if a.kind == "potion":
            f["potion_sent"] = {"snap": potion_snapshot(gs), "waits": 0}
        self.send(cmd)

    def potion_unresolved(self, gs):
        """After a potion command the game can answer with a state from
        before the potion acted (run 70: Snecko Oil still in its slot, the
        same hand and energy), and a new plan from it sends the potion again,
        which the game refuses. Such a state gets "wait 30" (at most
        POTION_WAITS times, then "state"); True when it was answered so."""
        f = self.fight
        ps = f.get("potion_sent")
        if ps is None:
            return False
        if potion_snapshot(gs) != ps["snap"]:
            f.pop("potion_sent")
            return False
        if ps["waits"] < POTION_WAITS:
            ps["waits"] += 1
            self.send("wait 30")
        else:
            f.pop("potion_sent")
            self.send("state")
        return True

    def predict(self, c, a):
        """The engine's prediction after action `a` from `c`: the expected view
        when every sample agrees (no chance in the step), and the samples'
        views as priors for the hidden parts (the last ones kept while the
        step stops at a pick, which has no view)."""
        f = self.fight
        samples = []
        for k in range(SAMPLES):
            e = c.with_seed(f["seed"] + 7919 * (k + 1))
            e.step(a)
            samples.append(e)
        views = []
        for e in samples:
            try:
                views.append(plain(e.view()))
            except ValueError:
                views.append(None)
        same = views[0] is not None and all(v == views[0] for v in views)
        f["engine"] = samples[0]
        f["samples"] = samples
        f["expected"] = views[0] if same else None
        f["priors"] = [v for v in views if v is not None] or f["priors"]
        if views[0] is not None and not same:
            f["queue"] = []  # chance in the step: search again on the game's state

    def pick(self, gs, avail):
        """A hand or grid pick inside a card: the planned line's choice, else a
        search from the engine's own state at that pick."""
        f = self.fight
        e = f["engine"]
        if e is None and "confirm" in avail:  # a pick before the first turn (Gambling Chip): keep the hand
            self.send("confirm")
            return
        # A step with chance in it (Havoc playing the top card) reaches this
        # pick in some samples only: take one whose pick offers the game's cards.
        offered = pick_offer(gs)
        best = pick_sample(e, f.get("samples") or [], gs, offered)
        if best is not e:
            e = best
            f["engine"], f["queue"] = e, []
        if e is None or e.awaiting_action() is False:
            raise HandOver("a pick the engine didn't reach")
        # The game asks even when every card offered is a copy of one card
        # (Armaments with two Defends); the engine took that one option
        # itself, and any copy reaches the same state.
        if offered is not None and len(offered) == 1 and not offers(e, offered) and "choose" in avail:
            self.send("choose 0")
            return
        if e.legal_actions() and not f["queue"]:
            import depth_paired
            d = depth_paired.decide(e, self.ev, self.two, None, f["seed"] + f["n"], 0, 3, -1.0)
            f["queue"] = depth_paired.planned(d, True)
        if not f["queue"]:
            if "confirm" in avail:
                self.send("confirm")
                return
            raise HandOver("a pick with nothing planned")
        a = f["queue"][0]
        if a.kind not in ("choose", "done"):
            if "confirm" in avail:  # the engine's pick ended; the game wants the button
                self.send("confirm")
                return
            raise HandOver("the plan has no pick here")
        f["queue"].pop(0)
        cmd = command_for(a, gs, None, marks=f["marks"])
        self.predict(e, a)
        self.send(cmd)

    def fresh_priors(self, gs, f):
        """Turn 1's priors: fresh engine fights against the game's monsters,
        whose first moves and rolls the engine drew itself."""
        import sts
        obs = observed(gs, f)
        bare = json.loads(json.dumps(obs))
        bare.pop("zero_cost", None)
        bare.pop("costs_shown", None)
        bare.pop("no_amount", None)
        bare.pop("made_free", None)
        bare.pop("lost_hp_seen", None)
        bare["player"]["relics"] = [[n, v or 0] for n, v in bare["player"]["relics"]]
        for m in bare["monsters"]:
            m.pop("game_index", None)
            m.pop("candidates", None)
            m.pop("shown_damage", None)
            m.pop("powers", None)
        # The powers the game doesn't show (a relic's effect the engine
        # holds as a power: Tungsten Rod, Torii, The Boot, ...) come from a
        # fresh fight's own start, which the view's player powers replace.
        start = dict(bare["player"])
        start.pop("powers", None)
        start.pop("just_applied", None)
        try:
            fresh = plain(sts.Combat.from_view(dict(bare, player=start), seed=f["seed"], group=f["group"]).view())
        except ValueError as e:
            raise HandOver("the engine can't build this fight: %s" % e)
        hidden = engine_only_powers()
        for p, n in fresh["player"].get("powers", {}).items():
            if p in hidden:
                bare["player"]["powers"].setdefault(p, n)
        out = []
        for k in range(SAMPLES):
            try:
                c = sts.Combat.from_view(bare, seed=f["seed"] + k, group=f["group"])
                out.append(plain(c.view()))
            except ValueError as e:
                raise HandOver("the engine can't build this fight: %s" % e)
        return out


def code_commit():
    """The checkout's commit (short hash), or None."""
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, creationflags=NO_WINDOW,
                              text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def ironclad_save():
    import real_game_launch
    return os.path.join(real_game_launch.paths()["game"], "saves", "IRONCLAD.autosave")


def save_seed(path):
    """The seed in a Slay the Spire autosave (base64 of JSON XORed with
    "key"), or None when it can't be read."""
    import base64
    try:
        raw = base64.b64decode(open(path, "rb").read())
        return json.loads(bytes(b ^ b"key"[i % 3] for i, b in enumerate(raw)).decode("utf-8")).get("seed")
    except (OSError, ValueError):
        return None


def clear_own_save(seed):
    """After a run stopped by choice and the game closed: deletes the
    Ironclad save (and its .backUp) only when it holds this run's `seed`,
    and removes the run mark either way. Returns what it did, for the log."""
    save = ironclad_save()
    found = save_seed(save) if os.path.exists(save) else None
    if found is not None and found == seed:
        for path in (save, save + ".backUp"):
            if os.path.exists(path):
                os.remove(path)
        done = "deleted this run's Ironclad save (seed %s)" % seed
    elif os.path.exists(save):
        done = "kept the Ironclad save: its seed %s isn't this run's %s" % (found, seed)
    else:
        done = "no Ironclad save to delete"
    try:
        os.remove(run_mark())
    except FileNotFoundError:
        pass
    return done + "; run mark removed"


def potion_snapshot(gs):
    """What a potion command changes at once: the potion slots, the hand and
    the energy."""
    cs = gs.get("combat_state") or {}
    return ([p.get("id") for p in gs.get("potions", [])], [c.get("uuid") or c.get("name") for c in cs.get("hand", [])],
            (cs.get("player") or {}).get("energy"))


def winning_options(c, options, seed, k=4):
    """Indices of the root `options` ([(actions, value)], a search's) whose
    first action wins the fight at once, in each of `k` sampled seeds."""
    out = []
    for i, (acts, _) in enumerate(options):
        for j in range(k):
            e = c.with_seed(seed + 7919 * (j + 1))
            e.step(acts[0])
            if not (e.is_over() and e.won()):
                break
        else:
            out.append(i)
    return out


def guard_pick(c, d, seed):
    """FIGHT_GUARD's pick for decision `d` (depth_paired.decide's at `c`):
    the winning option the search valued most (two-turn values where its
    tree didn't cut) when the search's own pick doesn't win at once, else
    None (the search's pick stands)."""
    wins = winning_options(c, d["r1"]["options"], seed)
    if not wins or d["pick"] in wins:
        return None
    vals = d["v2"] if d["v2"] is not None else d["v1"]
    return max(wins, key=lambda i: vals[i])


def close_game():
    """Closes the game (ModTheSpire's java), which ends this controller too."""
    import subprocess
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='java.exe'\" | "
          "Where-Object { $_.CommandLine -match 'ModTheSpire' } | ForEach-Object { $_.ProcessId }")
    pids = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                          creationflags=NO_WINDOW).stdout.split()
    for pid in pids:
        subprocess.run(["taskkill", "/PID", pid], capture_output=True, creationflags=NO_WINDOW)
    time.sleep(20)
    for pid in pids:
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, creationflags=NO_WINDOW)


def record_dir():
    d = os.path.join(ROOT, "results", "real-game", time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(d, exist_ok=True)
    return d


def card_of_or_none(card):
    try:
        return card_of(card)
    except HandOver:
        return None


def play(player, stdin=None, out=None, runs=1, ascension=0, act1_only=False):
    """The controller loop over CommunicationMod's states."""
    stdin = stdin or sys.stdin
    out = out or sys.stdout
    d = record_dir()
    log = open(os.path.join(d, "log.txt"), "a", encoding="utf-8")
    real_stdout = out
    sys.stdout = log  # anything printed is logged, never sent as a command
    bridge = Bridge(player, real_stdout, d, runs=runs, ascension=ascension)
    bridge.act1_only = act1_only
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        bridge.write("states", {"t": round(time.time(), 3), "msg": msg})
        try:
            bridge.handle(msg)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as e:  # never die mid-run (a Rust panic too): log, hand the fight over
            import traceback
            bridge.log("controller error: %s\n%s" % (e, traceback.format_exc()))
            bridge.answer_error(msg, e)


def stop_loop_file():
    return os.path.join(ROOT, "results", "real-game", "stop-loop")


def launch_loop(launcher, args, max_launches=1000, wait=time.sleep):
    """Launches the game again each time it exits (a controller with
    --act1-only closes it at an Act 2 stop, after its runs, or at the main
    menu once stop-loop exists), until results/real-game/stop-loop exists;
    waits for the closing game to leave the process list first."""
    for _ in range(max_launches):
        if os.path.exists(stop_loop_file()):
            print("stop-loop exists: not launching again", flush=True)
            return
        for _ in range(60):
            if not launcher.running_game(launcher.list_processes()):
                break
            wait(2)
        launcher.main(["launch"] + args)
        wait(5)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("play", "launch"):
        raise SystemExit(__doc__)
    if argv[0] == "launch":
        setup_paths()
        import real_game_launch
        if "--loop" not in argv:
            raise SystemExit(real_game_launch.main(["launch"] + argv[1:]))
        launch_loop(real_game_launch, [a for a in argv[1:] if a != "--loop"])
        return
    os.chdir(ROOT)  # CommunicationMod starts us in the game's folder
    setup_paths()
    args = argv[1:]
    opts = {"--runs": 1, "--ascension": 0}
    for o in opts:
        if o in args:
            k = args.index(o)
            opts[o] = int(args[k + 1])
            del args[k:k + 2]
    if not 0 <= opts["--ascension"] <= 20:
        raise SystemExit("--ascension is 0-20")
    act1_only = "--act1-only" in args
    if act1_only:
        args.remove("--act1-only")
    play(" ".join(args), runs=opts["--runs"], ascension=opts["--ascension"], act1_only=act1_only)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "play":
        print("ready", flush=True)  # CommunicationMod waits for one line before its timeout
    main()
