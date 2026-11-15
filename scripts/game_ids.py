"""The real game's ids and the engine's names (docs/specs/real-game-bridge.md).

`content/game_ids.json` maps the game's own ids (the `ID`, `POWER_ID` and
`POTION_ID` constants of desktop-1.0.jar's classes, and each monster class's
move byte constants) to the engine's names, as the engine's constructors and
`Combat.board()` write them: pack cards, monsters, relics and potions carry
`gen:`, pack powers are bare ids.

    python scripts/game_ids.py check [--jar <desktop-1.0.jar>]

checks every game id and move byte in the tables against the game's jar and
prints any miss (exit 1 if one). The engine side is checked by
scripts/tests/test_game_ids.py.
"""
import argparse
import json
import os
import struct
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLES = os.path.join(ROOT, "content", "game_ids.json")
GAME_JAR = "C:/Program Files (x86)/Steam/steamapps/common/SlayTheSpire/desktop-1.0.jar"
KINDS = ("cards", "monsters", "powers", "relics", "potions")
# Where each kind's classes live in the jar, and the constant naming the id.
JAR_KIND = {
    "cards": ("com/megacrit/cardcrawl/cards/", "ID"),
    "monsters": ("com/megacrit/cardcrawl/monsters/", "ID"),
    "powers": ("com/megacrit/cardcrawl/powers/", "POWER_ID"),
    "relics": ("com/megacrit/cardcrawl/relics/", "ID"),
    "potions": ("com/megacrit/cardcrawl/potions/", "POTION_ID"),
}

_tables = None


def tables():
    """The tables, loaded once."""
    global _tables
    if _tables is None:
        with open(TABLES, encoding="utf-8") as f:
            _tables = json.load(f)
    return _tables


def engine_name(kind, game_id):
    """The engine's name for a game id of `kind` ("cards", "monsters",
    "powers", "relics", "potions"), or None when the engine has none."""
    v = tables()[kind].get(game_id)
    return v["engine"] if kind == "monsters" and v else v


def game_ids(kind, name):
    """Every game id of `kind` the engine name `name` stands for (Intangible
    has two)."""
    return sorted(g for g in tables()[kind] if engine_name(kind, g) == name)


def card_name(game_id, upgrades=0):
    """The engine name of a game card with `upgrades` upgrades (CommunicationMod's
    `upgrades`), or None: the engine has one upgrade at most."""
    base = engine_name("cards", game_id)
    if base is None or upgrades > 1:
        return None
    return base + "+" * upgrades


def moves(game_id):
    """A game monster's moves: {game move byte: [engine move ids]} (more than
    one where the engine counts turns; the fight's history decides)."""
    v = tables()["monsters"].get(game_id)
    return {} if v is None else {int(b): m["engine"] for b, m in v["moves"].items()}


def modelled_elsewhere(kind, game_id):
    """Why a game id needs no engine name (the engine models it otherwise), or None."""
    return tables().get("game_modelled_elsewhere", {}).get(kind, {}).get(game_id)


def class_constants(data):
    """The constant fields of a class file: {field name: value} (str or int),
    from each field's ConstantValue attribute."""
    pos = 10
    count = struct.unpack_from(">H", data, 8)[0]
    pool = [None] * count
    i = 1
    while i < count:
        tag = data[pos]
        pos += 1
        if tag == 1:
            n = struct.unpack_from(">H", data, pos)[0]
            pool[i] = ("utf8", data[pos + 2:pos + 2 + n].decode("utf-8", "replace"))
            pos += 2 + n
        elif tag == 3:
            pool[i] = ("int", struct.unpack_from(">i", data, pos)[0])
            pos += 4
        elif tag == 8:
            pool[i] = ("string", struct.unpack_from(">H", data, pos)[0])
            pos += 2
        elif tag in (5, 6):
            pos += 8
            i += 1
        elif tag in (4, 9, 10, 11, 12, 17, 18):
            pos += 4
        elif tag == 15:
            pos += 3
        elif tag in (7, 16, 19, 20):
            pos += 2
        else:
            raise ValueError("unknown constant pool tag %d" % tag)
        i += 1
    pos += 6
    n_if = struct.unpack_from(">H", data, pos)[0]
    pos += 2 + 2 * n_if
    n_fields = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    out = {}
    for _ in range(n_fields):
        _, name_i, _, n_attr = struct.unpack_from(">HHHH", data, pos)
        pos += 8
        for _ in range(n_attr):
            a_name, a_len = struct.unpack_from(">HI", data, pos)
            if pool[a_name] == ("utf8", "ConstantValue"):
                const = pool[struct.unpack_from(">H", data, pos + 6)[0]]
                if const is not None:  # a long, float or double: not an id or a move
                    kind, v = const
                    out[pool[name_i][1]] = pool[v][1] if kind == "string" else v
            pos += 6 + a_len
    return out


def jar_ids(jar=GAME_JAR):
    """The game's ids by kind: {kind: {id: class constants}} from the jar."""
    out = {k: {} for k in KINDS}
    with zipfile.ZipFile(jar) as z:
        for name in z.namelist():
            if not name.endswith(".class") or "$" in name:
                continue
            for kind, (prefix, key) in JAR_KIND.items():
                if name.startswith(prefix):
                    consts = class_constants(z.read(name))
                    if isinstance(consts.get(key), str):
                        out[kind].setdefault(consts[key], consts)
    return out


def check(jar=GAME_JAR):
    """Misses of the tables against the jar, as lines (empty: all found)."""
    game = jar_ids(jar)
    misses = []
    for kind in KINDS:
        for gid in tables()[kind]:
            if gid not in game[kind]:
                misses.append("%s: %r not in the game" % (kind, gid))
    for gid, v in tables()["monsters"].items():
        consts = game["monsters"].get(gid, {})
        for b, m in {**v["moves"], **v.get("unmapped_moves", {})}.items():
            if consts.get(m["game"]) != int(b):
                misses.append("monsters: %s move %s = %s not in the game (has %r)" % (gid, m["game"], b, consts.get(m["game"])))
    for kind, ids in tables().get("game_modelled_elsewhere", {}).items():
        for gid in ids:
            if gid not in game[kind]:
                misses.append("%s: %r (modelled elsewhere) not in the game" % (kind, gid))
    return misses


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check the tables against the game's jar")
    c.add_argument("--jar", default=GAME_JAR)
    args = ap.parse_args(argv)
    if not os.path.exists(args.jar):
        print("no game jar at %s" % args.jar)
        return 1
    misses = check(args.jar)
    for m in misses:
        print(m)
    n = sum(len(tables()[k]) for k in KINDS)
    print("%d game ids checked, %d missing" % (n, len(misses)))
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
