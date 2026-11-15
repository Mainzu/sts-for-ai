"""The real-game bridge's run layer (docs/specs/real-game-bridge.md): what the
controller does outside fights, so it plays whole runs by itself. Each
function takes CommunicationMod's game state (field names from the mod's
GameStateConverter / ChoiceScreenUtils) and returns one command, or None.

Rules, kept simple and stated where the project measured them:
- Map: below half HP a rest site first; an elite only when every next node
  is one. Otherwise each next node is judged by the paths below it up to the
  next rest site: a path survives when its fights and elites, at a
  pessimistic HP cost each, cost less than the HP now; the node whose best
  path survives with the most card picks (hallway fights; an elite counts
  none, since it costs more HP than it pays) wins, else the one whose
  cheapest path costs least. Ties (and a state without a map) go by
  MAP_RANK: monsters first, then events, treasure, rest, shop; elites last.
- Events (Neow too): the option whose words score best; never one that says
  lose, curse, fight, pay, gamble or trap when another exists. Words match
  whole (with an s, d, ed or number ending), so "golden" isn't gold.
- Combat rewards: gold, relics, potions (while a slot is empty), the card
  reward once (the chooser decides, skip included); then proceed.
- Rest: rest below 60% HP (75% before the boss), else upgrade.
- Shops: walk past. Chests: open. Boss relic: the first offered, except
  Runic Dome (it hides the enemies' moves, so no fight can be rebuilt).
- Card picks in a grid (upgrade / remove / transform): Bash first for an
  upgrade, else a card that isn't Strike or Defend; Strike, then Defend,
  for a removal or transform.
- Fights the engine can't play: the first playable card on the first
  living monster, else end the turn (`fallback_command`)."""

import re

# The run layer's rules version, recorded with each run so its numbers sit
# beside their setting: 1 until 8d7d529a (2026-11-14 14:10:02), 2 from it
# (below half HP a rest site first), 3 from e28d1215 (the map looks ahead to
# the next rest site), 4 from the event words matching whole words, with
# trap a bad word (run 52 took the Golden Idol: "golden" scored as gold),
# 5 from elites last again (rules 3 and 4 took four elites by choice at A20,
# costing 51, 35, 0 and 73 HP, the last a death from full HP in run 55).
# Raise it with any rule change here.
RUN_RULES = 5
MAP_RANK = {"M": 0, "?": 1, "T": 2, "R": 3, "$": 4, "E": 5}
LOW_HP = 0.5  # below this share of max HP the map takes a rest site first
# Pessimistic HP cost of a hallway fight and of an elite for the map's
# look-ahead: about the 90th percentile of HP lost per hallway fight (15) and
# the 75th-90th of an elite (38-44) in the A20 live records, after Burning
# Blood's heal (runs 28-49).
FIGHT_COST, ELITE_COST = 15, 40
GOOD_WORDS = (("max hp", 4), ("upgrade", 3), ("remove", 3), ("relic", 2), ("gold", 2), ("heal", 2),
              ("card", 1), ("leave", 1), ("ignore", 1), ("continue", 1), ("proceed", 1), ("talk", 1))
BAD_WORDS = ("lose", "curse", "fight", "pay", "gamble", "damage", "take", "wound", "attack", "decay",
             "regret", "doubt", "injury", "parasite", "trap")
BOSS_ENCOUNTER = {"Hexaghost": "hexaghost", "The Guardian": "the_guardian", "Slime Boss": "slime_boss"}
STARTER = ("Strike", "Defend")
# Boss relics the controller won't take while another is offered.
AVOID_BOSS_RELICS = ("Runic Dome",)


def says(text, word):
    """`word` (or phrase) in `text` as a whole word, with an s, d, ed or
    number ending: "lose" in "Lose 8 HP" and "cursed", "card" in "card2"
    (Match and Keep's face-down cards), not "lose" in "close" or "gold" in
    "golden"."""
    return re.search(r"\b%s(?:s|d|ed|\d+)?\b" % re.escape(word), text) is not None


def event_command(gs):
    """An event's option (Neow too) by its words: `choose <choice_index>`."""
    opts = [o for o in gs.get("screen_state", {}).get("options", []) if not o.get("disabled") and "choice_index" in o]
    if not opts:
        return None

    def score(o):
        text = (o.get("text", "") + " " + o.get("label", "")).lower()
        bad = any(says(text, w) for w in BAD_WORDS)
        return (not bad, sum(v for w, v in GOOD_WORDS if says(text, w)))
    best = max(opts, key=score)  # max keeps the first of equals
    return "choose %d" % best["choice_index"]


def segments(node, nodes, memo):
    """The (fights, elites) of each path from `node` up to the next rest site
    (or the map's end). `nodes`: the map by (x, y)."""
    k = (node["x"], node["y"])
    if k not in memo:
        s = node.get("symbol")
        kids = [nodes[(c["x"], c["y"])] for c in node.get("children", []) if (c["x"], c["y"]) in nodes]
        below = {(0, 0)} if s == "R" or not kids else set().union(*(segments(c, nodes, memo) for c in kids))
        memo[k] = {(m + (s == "M"), e + (s == "E")) for m, e in below} if s != "R" else below
    return memo[k]


def path_key(pairs, hp):
    """The best path of `pairs` at `hp`: one that survives the pessimistic
    costs with the most card picks (hallway fights; elites count none), else
    the cheapest."""
    def key(p):
        cost = p[0] * FIGHT_COST + p[1] * ELITE_COST
        return (1, p[0], -cost) if cost < hp else (0, 0, -cost)
    return max(key(p) for p in pairs)


def map_command(gs, choices):
    """The next map node: the boss when it's the only way; below half HP a
    rest site first (run 33 took a fight at 10 of 75 HP over one and died);
    else the node with the best path up to the next rest site (runs 37 and
    49 died on paths one node ahead couldn't see), never an elite while
    another node is offered (run 55 took Sentries over a rest site at 73 of
    75 HP and died); ties by MAP_RANK."""
    if choices == ["boss"]:
        return "choose 0"
    nodes = gs.get("screen_state", {}).get("next_nodes", [])
    if not nodes:
        return None
    rank = dict(MAP_RANK)
    hp, mx = gs.get("current_hp"), gs.get("max_hp")
    low = hp is not None and mx and hp < LOW_HP * mx
    if low:
        rank["R"] = -1
    order = [(rank.get(n.get("symbol"), 9), i) for i, n in enumerate(nodes)]
    graph = {(n["x"], n["y"]): n for n in gs.get("map") or []}
    if graph and hp is not None and not (low and any(n.get("symbol") == "R" for n in nodes)):
        memo = {}
        keys = [path_key(segments(graph.get((n["x"], n["y"]), n), graph, memo), hp) for n in nodes]
        cand = [i for i, n in enumerate(nodes) if n.get("symbol") != "E"] or range(len(nodes))
        return "choose %d" % max(cand, key=lambda i: (keys[i], -order[i][0], -i))
    return "choose %d" % min(range(len(nodes)), key=lambda i: order[i])


def potion_slot_free(gs):
    return any(p.get("id") == "Potion Slot" for p in gs.get("potions", []))


def reward_command(gs, card_done):
    """A combat reward to take, or proceed. `card_done`: the card reward was
    already looked at on this screen (taken or skipped)."""
    for i, r in enumerate(gs.get("screen_state", {}).get("rewards", [])):
        t = r.get("reward_type")
        if t in ("GOLD", "STOLEN_GOLD", "RELIC"):
            return "choose %d" % i
        if t == "POTION" and potion_slot_free(gs):
            return "choose %d" % i
        if t == "CARD" and not card_done:
            return "choose %d" % i
    return "proceed"


def rest_command(gs, choices):
    hp, mx = gs.get("current_hp", 0), max(1, gs.get("max_hp", 1))
    before_boss = gs.get("floor", 0) % 17 == 15
    low = hp / mx < (0.75 if before_boss else 0.6)
    if not choices:
        return "proceed"
    if "rest" in choices and (low or "smith" not in choices):
        return "choose %d" % choices.index("rest")
    if "smith" in choices:
        return "choose %d" % choices.index("smith")
    return "choose 0"


def unselected(ss):
    """Indices of a grid's cards not yet picked: the grid keeps picked cards
    in its list, and choosing one again unpicks it."""
    picked = {c.get("uuid") for c in ss.get("selected_cards", [])}
    return [i for i, c in enumerate(ss.get("cards", [])) if c.get("uuid") is None or c.get("uuid") not in picked]


def boss_relic_command(gs, choices):
    """The first boss relic offered that isn't in AVOID_BOSS_RELICS."""
    if not choices:
        return "proceed"
    relics = gs.get("screen_state", {}).get("relics", [])
    ok = [i for i, r in enumerate(relics) if r.get("id") not in AVOID_BOSS_RELICS]
    return "choose %d" % (ok[0] if ok else 0)


def grid_command(gs, choices):
    """A card from a grid outside fights (upgrade, removal, transform), or
    confirm once the pick is made (or nothing is left to pick)."""
    ss = gs.get("screen_state", {})
    free = unselected(ss)
    if ss.get("confirm_up") or not choices or not free:
        return "confirm"
    names = {i: ss["cards"][i].get("name", "") for i in free}
    if ss.get("for_upgrade"):
        order = [i for i in free if names[i].startswith("Bash")]
        order += [i for i in free if not names[i].startswith(STARTER)]
    else:
        order = [i for i in free if names[i].startswith("Strike")]
        order += [i for i in free if names[i].startswith("Defend")]
    return "choose %d" % (order + free)[0]


def fallback_command(gs, avail, choices):
    """A fight the engine can't play: picks take the first card; else the
    first playable card on the first living monster; else end the turn."""
    screen = gs.get("screen_type")
    if screen == "GAME_OVER":
        return "proceed" if "proceed" in avail else None
    if screen == "GRID":
        free = unselected(gs.get("screen_state", {}))
        if choices and free and "choose" in avail:
            return "choose %d" % free[0]
        return "confirm" if "confirm" in avail else None
    if screen in ("HAND_SELECT", "CARD_REWARD"):
        if choices and "choose" in avail:
            return "choose 0"
        return "confirm" if "confirm" in avail else ("skip" if "skip" in avail else None)
    if "play" not in avail:
        return "end" if "end" in avail else None
    cs = gs["combat_state"]
    alive = [i for i, m in enumerate(cs["monsters"]) if not m.get("is_gone") and m.get("current_hp", 0) > 0]
    for j, c in enumerate(cs["hand"]):
        if c.get("is_playable"):
            cmd = "play %d" % ((j + 1) % 10)
            if c.get("has_target"):
                if not alive:
                    continue
                cmd += " %d" % alive[0]
            return cmd
    return "end" if "end" in avail else None


def next_kind(floor):
    """The sim chooser's next-fight pool by floor (the gauntlet's shape: easy
    for the first three fights of an act, then hard)."""
    return "easy" if floor % 17 < 3 else "hard"
