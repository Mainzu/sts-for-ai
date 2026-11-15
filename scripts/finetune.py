"""Fine-tunes a trained value net on new content (docs/specs/warm-start.md):
the parent is widened to the new content's vocabulary (`stsnet.widen`),
then trained on the new content's games with a share of each batch
replayed from its own training distribution, so it keeps what it knew.

New games are search + heuristic games on the content's decks, labelled
with their final scores, stored once per (content, game seed) at the
ladder's top size; a smaller size is the first k games of each group of
that dataset (nested). The replay pool is the generalise pair's training
specs (`selfplay.all_sets`' train set) replayed with today's engine.
Validation: the content's own validation games plus as many Ironclad
validation games. Encoded sets are cached under cache/ (rebuildable).
Each fine-tune is a registry run whose run.json names its `parent`.

Generated content (docs/specs/adaptation-burst.md): `content` may instead be
{"pack": <pack path>, "cards": [<card ids>]}: Ironclad decks with
1-2 of those generated power cards added to every deck, the pack loaded
first; these games, the Ironclad validation games and the replay pool use
varied setups (`selfplay.varied_deck`, `varied_hp`), as learn.py trains.
Its games are played by `player`: "net" (default: search with the parent
net) or "heuristic". An effects parent keeps its vocabularies (the
cards bind to reserved power slots), so no column widens.

Mutated monsters (docs/specs/adaptation-curve.md): `content` may instead be
{"mutated": [<mutate_monsters.MODS names>], "skip": 200, "val_fights": 100}:
the gauntlet's elite and boss fights (`bias_audit.fights` of
`mutate_monsters.PRODUCT`) from their first decision with each modifier's
patch applied, played one turn deep by the parent at `@hpb0.01` in a
Python loop (a patched state isn't an `sts.run` spec). Training games:
fights [skip, skip + games) x every modifier; validation: the last
`val_fights` fights x every modifier. Their encoded sets are cached
under cache/ (not registry datasets); replay and Ironclad validation as for
generated content. Generated enemy mechanics (docs/specs/gen-adapted-burst.md):
`mutated` may name `mutate_monsters.GEN_ALL` pack mechanics (the old 24 and the wide grid) (the bench's pack
loaded, each applied as the bench's `variant`); `encounters` keeps only
fights on those (the parent elites), validation their last `val_fights`;
`repeat`: true cycles the training fights with fresh play seeds when
`games` exceeds them; `net_settings` (default `@hpb0.01`) are the parent's
search settings; the config's `player` "heuristic" plays them by the
heuristic instead.

Row kinds: every set (train, validation, replay) is encoded with the
layout the saved net reads: today's default kinds (triggered, threshold,
held) plus any kind the parent opted into, so a parent saved before
threshold and held rows gains those two.

Config keys (JSON): `name`, `content` (silent_a | silent_b | both, or a
generated-content dict) or instead `source` ({"kind": "two-turn" |
"one-turn", "player": <player string>}: elite and boss games on varied
training decks at run-like HP by that player at that depth, from
`two_turn_games.py`, docs/specs/two-turn-round.md; with "encounters": [<boss
encounter names>] boss games on those encounters only, `games` of them,
validation alike; with "decks": "held-out" decks holding the held-out cards,
selfplay.varied_held_out_deck, validation alike; validation and the
replay pool then use varied Ironclad setups), `player` (generated content only),
`games` (per group), `top` (the stored dataset's games per group; default
`games`), `game_seed`, `seed` (training and replay sampling), `share`
(default 0.5), `lr` (default train.LR), `epochs` (default train.EPOCHS),
`n_val` (validation games per group, default 300), `pool` (replay games per
group, default 10,000), `start` ("warm", default, or "fresh": a new
effects net on the new games only, no replay), `hp_weight` (w: every
target, replay and validation included, scores a win 2 - w x HP lost /
100 as learn.py's key; absent: unweighted), `extra_rows` (true: also train
on every opt-in row kind, static, countdown, replacement and pattern;
docs/decisions.md "Series row kinds are opt-in"), `row_kinds` (a list: also
train on these kinds), `anchor` (λ, default 0: adds λ x the summed squared
distance of the weights from the widened parent's to the loss,
docs/specs/burst-anchor.md; warm start only).

    python scripts/finetune.py --from models/value_effects.pt --config configs/finetune-silent.json
"""

import argparse
import hashlib
import json
import os
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")  # before torch; see stsnet.py
os.environ.setdefault("MKL_DISABLE_FAST_MM", "1")

import numpy as np

import registry
import selfplay
import stsnet
import sts
import train
import transfer

CHARACTER = "silent"
DECKS = {"silent_a": transfer.deck_a, "silent_b": transfer.deck_b,
         "both": lambda rng: (transfer.deck_a if rng.random() < 0.5 else transfer.deck_b)(rng)}
# Every card the content's decks can hold, for an ids parent's widened vocabulary.
CONTENT_CARDS = list(dict.fromkeys(sts.starter_deck(CHARACTER) + transfer.POOL_A + transfer.POOL_B))
# The powers those cards apply that Ironclad training doesn't (Deadly Poison,
# Poisoned Stab, Bouncing Flask). Only the content's own: adding every
# unknown power would move held-out Ironclad cards' powers (Demon Form, Rage)
# out of `unknown` too, changing how the net sees old content.
CONTENT_POWERS = ["Poison"]
VAL_OFFSET = 1  # the content's validation games: game_seed + this
IRONCLAD_VAL_SEED = 2  # selfplay.all_sets' val seed
POOL_SEED = 1  # selfplay.all_sets' train seed
PLAY_CHUNK = 400  # games per sts.run: records are small, recorded states aren't (2,000 held 3-4 GB of them)
SAMPLE_OFFSET = 12345  # as selfplay.generate


def vocab_for(meta, cards=CONTENT_CARDS, powers=CONTENT_POWERS):
    """`meta`'s vocabularies widened for new content: known cards plus
    `cards`, known powers plus `powers` (an effects net's power list is the
    fixed modifier list: unchanged), every other vocabulary plus whatever
    the full encoder knows that it doesn't; old entries keep their order,
    new ones follow."""
    full = sts.Features(meta["card_repr"]).vocab
    out = {"card_repr": meta["card_repr"]}
    for k in stsnet.VOCAB_KEYS:
        v = full[k[len("known_"):]]
        add = {"known_cards": cards, "known_powers": [p for p in powers if p in v]}.get(k, v)
        base = list(meta.get(k) or v)
        out[k] = base + [x for x in dict.fromkeys(add) if x not in base]
    return out


def generated(kind):
    """(pack hash, `gen:` deck names) of a generated-content dict, the pack
    loaded into the engine; a card id the pack lacks raises, naming it."""
    pack, h = selfplay.load_content(kind["pack"])
    ids = {c["id"] for c in pack["cards"]}
    missing = [c for c in kind["cards"] if c not in ids]
    if missing:
        raise ValueError(f"content cards not in {kind['pack']}: {missing}")
    return h, ["gen:" + c for c in kind["cards"]]


MUTATED_TURNS = 60  # a mutated game still running at this turn is stopped and scored 0 (a loss)


def _mutate_modules():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis"))
    import bias_audit
    import mutate_monsters
    return mutate_monsters, bias_audit


def mutated_fights(kind, games, fights=None):
    """(training fights, validation fights) of a mutated-content dict, out
    of `fights` (default: every elite and boss fight of
    `mutate_monsters.PRODUCT`); raises before any play on an unknown
    modifier or on too few training fights. With `encounters`, only fights
    on those count: validation is their last `val_fights`, training the rest
    from position `skip` on. With `repeat`, game g plays training fight
    g mod n and carries "rep" g div n (from 1 on) for a fresh play seed."""
    mm, ba = _mutate_modules()
    unknown = [m for m in kind["mutated"] if m not in mm.ALL]
    if unknown:
        raise ValueError(f"mutated content: unknown modifiers {unknown}")
    if fights is None:
        with open(os.path.join(registry.ROOT, mm.PRODUCT), encoding="utf-8") as f:
            fights = ba.fights(json.load(f), 10 ** 9)
    skip, nv = kind.get("skip", 200), kind.get("val_fights", 100)
    enc = kind.get("encounters")
    pos = [n for n, f in enumerate(fights) if not enc or f["encounter"] in enc]
    val = pos[len(pos) - nv:]
    pool = [n for n in pos[:len(pos) - nv] if n >= skip]
    if not kind.get("repeat"):
        if games > len(pool):
            raise ValueError(f"mutated content: training fights [{skip}, {skip + games}) reach the last {nv} "
                             f"(validation) of {len(pos)}")
        return [fights[n] for n in pool[:games]], [fights[n] for n in val]
    if not pool:
        raise ValueError(f"mutated content: no training fights from {skip} before the last {nv} (validation)")
    train = [fights[pool[g % len(pool)]] if g < len(pool) else {**fights[pool[g % len(pool)]], "rep": g // len(pool)}
             for g in range(games)]
    return train, [fights[n] for n in val]


def mutated_games(specs, mods, seed, evaluator, features=None):
    """(results, groups): one game per (fight, modifier) from the fight's
    first decision with the patch applied, played by search with
    `evaluator`, recorded like an `sts.run` result (states, actions, score)."""
    mm, _ = _mutate_modules()
    if any(m in mm.GEN_ALL for m in mods):
        sts.load_content(mm.gen_pack())  # the bench's pack powers, before any variant takes one
    kw = {"features": features} if features is not None else {}
    results, groups = [], []
    for spec in specs:
        c0 = mm.start_state(spec)
        for j, m in enumerate(mods):
            key = [seed, spec["i"], spec["floor"], j] + ([spec["rep"]] if spec.get("rep") else [])
            s = int(np.random.default_rng(key).integers(2 ** 62))
            patches = mm.ALL[m]
            if any(p[0] == "pack" for p in patches):
                c = mm.variant(c0, patches).with_seed(s)
            else:
                c = sts.Combat.decode(mm.mutate(c0, patches), seed=s)
            states, actions = [], []
            while not c.is_over() and c.turn() < MUTATED_TURNS:
                if not c.awaiting_action():
                    c.advance()
                    continue
                a = sts.search_action(c, evaluator=evaluator, limit=selfplay.LIMIT, **kw)
                states.append(c.clone())
                actions.append(a)
                c.step(a)
            results.append({"states": states, "actions": actions, "score": c.score() if c.is_over() else 0.0})
            groups.append(selfplay.GROUPS.index(spec["group"]))
    return results, groups


def mutated_ident(kind, which, games, seed, meta, parent_sha, player="net"):
    """The cache identity of a mutated set; the keys added for generated
    mechanics appear only when set, so older sets keep their identity."""
    ident = {"mutated": kind["mutated"], "skip": kind.get("skip", 200), "val_fights": kind.get("val_fights", 100),
             "which": which, "games": games if which == "train" else None, "seed": seed, "parent": parent_sha,
             "card_repr": meta["card_repr"], "layout": stsnet.layout_of(meta), "rules": registry.rules_version()}
    ident.update({k: kind[k] for k in ("encounters", "repeat", "net_settings") if k in kind})
    if player != "net":
        ident["player"] = player
    mm, _ = _mutate_modules()
    if any(m in mm.GEN_ALL for m in kind["mutated"]):
        ident["pack"] = sts.load_content(mm.gen_pack())
    return ident


def mutated_set(kind, which, games, game_seed, meta, parent, root=registry.ROOT, log=print, player="net"):
    """The encoded training (`which` "train") or validation set of mutated
    content, games by the parent at `net_settings` (default `@hpb0.01`), or
    by the heuristic with `player` "heuristic"; cached under cache/."""
    train, val = mutated_fights(kind, games)
    specs, seed = (train, game_seed) if which == "train" else (val, game_seed + VAL_OFFSET)
    ident = mutated_ident(kind, which, games, seed, meta, sha256(parent), player)
    key = hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()[:16]
    path = os.path.join(registry.cache_dir(root), f"mutated-{which}-{key}.npz")
    if os.path.exists(path):
        return stsnet.Dataset.load(path)
    import bench
    ev = bench.load_evaluator("heuristic" if player == "heuristic" else parent + kind.get("net_settings", "@hpb0.01"))
    feats = stsnet.features_for(meta)
    rng = np.random.default_rng(seed + SAMPLE_OFFSET)
    parts, targets, grps, t = [], [], [], time.perf_counter()
    for i in range(0, len(specs), 100):
        res, gr = mutated_games(specs[i:i + 100], kind["mutated"], seed, ev.evaluator, ev.features)
        states, tg, g = selfplay.sample_states(res, gr, rng)
        parts.append(feats.encode(states))
        targets += tg
        grps += g
    out = stsnet.Dataset.from_batches(parts, targets, grps)
    os.makedirs(registry.cache_dir(root), exist_ok=True)
    out.save(path)
    log(f"  mutated {which}: {len(specs) * len(kind['mutated'])} games, {len(out)} states in {time.perf_counter() - t:.0f}s")
    return stsnet.Dataset.load(path)


# Card columns that left the default layout but stay for the nets that read
# them (docs/specs/card-rules.md: only_attacks_in_hand, read from playable_if).
LEGACY_CARD_COLUMNS = ("only_attacks_in_hand",)


def keep_legacy_columns(meta, pmeta):
    """`meta` with the parent's legacy card columns kept in place (after the
    column the parent has before each), so `widen` keeps their weights and
    the encoder writes them; `meta` itself when the parent has none."""
    old = stsnet.layout_of(pmeta)["columns"]["cards"]
    keep = [c for c in LEGACY_CARD_COLUMNS if c in old]
    if not keep:
        return meta
    lay = stsnet.layout_of(meta)
    cards = list(lay["columns"]["cards"])
    for c in keep:
        if c not in cards:
            prev = old[old.index(c) - 1] if old.index(c) > 0 else None
            cards.insert(cards.index(prev) + 1 if prev in cards else len(cards), c)
    return {**meta, "columns": {**lay["columns"], "cards": cards}}


def kept_vocab(meta):
    """An effects parent's vocabularies as they are, for generated content
    (its cards bind to reserved power slots; nothing to widen)."""
    if meta["card_repr"] != "effects":
        raise ValueError("generated content needs an effects parent")
    return {"card_repr": meta["card_repr"], **{k: meta.get(k) for k in stsnet.VOCAB_KEYS}}


def games(kind, n_per_group, seed, threads=None, log=print, root=registry.ROOT, player="heuristic", parent=None,
          ascension=0):
    """The registry dataset of `n_per_group` search games per group of
    `kind` (a DECKS key, "ironclad" for train_deck, "varied" for Ironclad
    varied setups, or a generated-content dict: varied setups plus its
    cards), played PLAY_CHUNK at a time with the heuristic or, for generated
    content with `player` "net", the net at `parent`; stored once and
    reused. At an `ascension` level (docs/specs/ascension.md) every game is
    played at it and the config records it."""
    gen = isinstance(kind, dict)
    character = "ironclad" if gen or kind in ("ironclad", "varied") else CHARACTER
    config = {"kind": "warm-start games", "content": kind, "n_per_group": n_per_group, "seed": seed,
              "character": character, **({"ascension": ascension} if ascension else {})}
    ev = {}
    if gen:
        h, cards = generated(kind)
        config["content"] = {"pack": kind["pack"], "hash": h, "cards": sorted(kind["cards"])}
        config["player"] = player
        if player == "net":
            if parent is None:
                raise ValueError("player net needs a parent net")
            config["parent_sha256"] = sha256(parent)
    ds = registry.find(config, root=root)
    if ds is not None:
        return ds
    hp_fn = selfplay.varied_hp if gen or kind == "varied" else None
    if gen:
        deck_fn = selfplay.content_deck(selfplay.varied_deck, cards, 1.0 if cards else 0.0)  # no cards: the control burst
        if player == "net":
            import bench
            e = bench.load_evaluator(parent)
            ev = {"evaluator": e.evaluator, "features": e.features}
    else:
        deck_fn = {"ironclad": selfplay.train_deck, "varied": selfplay.varied_deck}.get(kind) or DECKS[kind]
    specs, groups = selfplay.make_specs(n_per_group, seed, deck_fn, character=character, hp_fn=hp_fn, ascension=ascension)
    run_specs = [registry.keyed_spec(s, ascension) for s in specs] if ascension else specs
    recs, t = [], time.perf_counter()
    for i in range(0, len(specs), PLAY_CHUNK):
        res = sts.run("search", run_specs[i:i + PLAY_CHUNK], record=True, limit=selfplay.LIMIT, character=character,
                      **ev, **stsnet.job_threads({"threads": threads}))
        recs += registry.records(specs[i:i + PLAY_CHUNK], groups[i:i + PLAY_CHUNK], res,
                                {"character": character, **({"ascension": ascension} if ascension else {})})
        del res
    log(f"  {'generated' if gen else kind}: {len(specs)} games in {time.perf_counter() - t:.0f}s")
    return registry.write_dataset(recs, config, root=root)


def first_per_group(ds, k, root=registry.ROOT):
    """The dataset's games, the first `k` of each group (nested sizes)."""
    seen = {}
    for g in registry.iter_games(ds, root):
        n = seen.get(g["group"], 0)
        if n < k:
            seen[g["group"]] = n + 1
            yield g


def encoded(ds, k, meta, root=registry.ROOT, log=print, mapped=False):
    """The first `k` games per group of `ds`, states sampled as
    selfplay.generate does and encoded with `meta`'s encoder; cached.
    `mapped` (the replay pool): cached as a DatasetWriter directory, written
    a chunk at a time (an .npz cache of the same set is converted), and
    returned memory-mapped, so the set is never whole in memory."""
    m = registry.load_manifest(ds, root)
    layout = stsnet.layout_of(meta)
    key = hashlib.sha256(json.dumps([ds, k, meta["card_repr"], layout], sort_keys=True).encode()).hexdigest()[:16]
    npz = os.path.join(registry.cache_dir(root), f"warm-{ds}-{k}-{key}.npz")
    path = npz[:-len(".npz")] if mapped else npz
    if os.path.exists(path):
        return stsnet.Dataset.load(path)
    os.makedirs(registry.cache_dir(root), exist_ok=True)
    if mapped and os.path.exists(npz):
        stsnet.npz_to_dir(npz, path)
        log(f"  converted {os.path.basename(npz)} to a mapped cache")
        return stsnet.Dataset.load(path)
    feats = stsnet.features_for(meta)
    rng = np.random.default_rng(m["config"]["seed"] + SAMPLE_OFFSET)
    parts, targets, grps, n = [], [], [], 0
    writer = stsnet.DatasetWriter(path) if mapped else None
    it = first_per_group(ds, k, root)
    while True:
        chunk = [g for _, g in zip(range(registry.CHUNK), it)]
        if not chunk:
            break
        states, tg, gr = selfplay.sample_states([registry.replay(g) for g in chunk], [g["group"] for g in chunk], rng)
        if writer is not None:
            writer.append(stsnet.Dataset.from_batches([feats.encode(states)], tg, gr))
            n += len(tg)
        else:
            parts.append(feats.encode(states))
            targets += tg
            grps += gr
    if writer is not None:
        writer.close()
    else:
        out = stsnet.Dataset.from_batches(parts, targets, grps)
        out.save(path)
        n = len(out)
    log(f"  encoded {ds} (first {k} per group): {n} states")
    return stsnet.Dataset.load(path)


def weigh_targets(d, w):
    """`d`'s targets (game scores) with HP lost weighted by `w`, as learn.py's
    `hp_weight` (docs/specs/hp-weight.md); in place."""
    import learn
    d.target = learn.hp_scale(d.target, w)


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def row_kinds(cfg, today, parent_kinds):
    """The row kinds a fine-tune trains on and saves: `today`'s (the
    encoder's defaults), then the parent's, then the config's `extra_rows`
    (every kind) or `row_kinds`, each once. Refuses a name that is no kind."""
    extra = list(sts.ROW_KINDS) if cfg.get("extra_rows") else list(cfg.get("row_kinds") or [])
    unknown = [x for x in cfg.get("row_kinds") or [] if x not in sts.ROW_KINDS]
    if unknown:
        raise ValueError(f"finetune: row_kinds {unknown} are not row kinds (sts.ROW_KINDS: {list(sts.ROW_KINDS)})")
    return list(dict.fromkeys([*today, *parent_kinds, *extra]))


SOURCE_DEPTH = {"two-turn": "two", "one-turn": "one"}  # `source` kinds (docs/specs/two-turn-round.md)


def source_depth(source):
    """The two_turn_games depth of a `source` config, refusing an unknown kind."""
    kind = (source or {}).get("kind")
    if kind not in SOURCE_DEPTH:
        raise ValueError(f"finetune: source kind must be one of {sorted(SOURCE_DEPTH)}, not {kind!r}")
    return SOURCE_DEPTH[kind]


def finetune(parent, cfg, root=registry.ROOT, log=print, threads=None, max_nodes=None):
    """One fine-tune (or, with cfg["start"] == "fresh", a fresh effects net
    on the new games only); returns the finished registry.Run. `parent`: a
    saved net's path (None for fresh). `max_nodes` (smoke runs only): a
    smaller node cap for a two-turn `source`'s games; it is part of those
    datasets' identity, never of the run's config."""
    fresh = cfg.get("start", "warm") == "fresh"
    if fresh and cfg.get("anchor"):
        raise ValueError("finetune: anchor needs a parent (start: warm)")
    source = cfg.get("source")
    if source is not None and "content" in cfg:
        raise ValueError("finetune: a config takes `source` or `content`, not both")
    depth = source_depth(source) if source is not None else None
    content = None if source is not None else cfg["content"]
    gen = isinstance(content, dict)
    mut = gen and "mutated" in content
    if mut and fresh:
        raise ValueError("finetune: mutated content needs a parent")
    play = {"player": cfg.get("player", "net"), "parent": parent} if gen and not mut else {}
    top, k = cfg.get("top", cfg["games"]), cfg["games"]
    n_val, pool = cfg.get("n_val", 300), cfg.get("pool", 10_000)
    if fresh:
        meta = {"card_repr": "effects", **selfplay.meta_vocab("effects")}
        model = norm = None
    else:
        model, norm, pmeta = stsnet.load(parent)
        meta = keep_legacy_columns(kept_vocab(pmeta) if gen else vocab_for(pmeta), pmeta)
    parent_kinds = [] if fresh else stsnet.layout_of(pmeta)["row_kinds"]
    meta["row_kinds"] = row_kinds(cfg, stsnet.layout_of(meta)["row_kinds"], parent_kinds)
    asc = cfg.get("ascension", 0)  # the game's level every fight is played at (docs/specs/ascension.md)
    if asc and (source is not None or mut):
        raise ValueError("finetune: ascension needs the warm-start games (no two-turn source, no mutated content)")
    if source is not None:  # games by a net player at a depth (two_turn_games), the same for validation
        import two_turn_games
        enc, decks = source.get("encounters"), source.get("decks", "varied")
        new_ds = two_turn_games.dataset(source["player"], top, cfg["game_seed"], depth, threads, root, log,
                                        max_nodes=max_nodes, encounters=enc, decks=decks)
        val_ds = two_turn_games.dataset(source["player"], n_val, cfg["game_seed"] + VAL_OFFSET, depth, threads,
                                        root, log, max_nodes=max_nodes, encounters=enc, decks=decks)
    elif mut:
        mutated_fights(content, k)  # refuses before any play
        if cfg.get("player", "net") not in ("net", "heuristic"):
            raise ValueError(f"finetune: mutated content's player must be net or heuristic, not {cfg['player']!r}")
        new_ds = val_ds = None
    else:
        new_ds = games(content, top, cfg["game_seed"], threads, log, root, ascension=asc, **play)
        val_ds = games(content, n_val, cfg["game_seed"] + VAL_OFFSET, threads, log, root, ascension=asc, **play)
    iron = "varied" if gen or source is not None else "ironclad"  # the parent's own training setups
    iron_val = games(iron, n_val, IRONCLAD_VAL_SEED, threads, log, root, ascension=asc)
    datasets = [d for d in (new_ds, val_ds, iron_val) if d is not None]
    pool_ds = None
    if not fresh:
        pool_ds = games(iron, pool, POOL_SEED, threads, log, root, ascension=asc)
        datasets.append(pool_ds)
    data_layout = stsnet.layout_of(meta)
    if mut:
        who = cfg.get("player", "net")
        train_ds = mutated_set(content, "train", k, cfg["game_seed"], meta, parent, root, log, who)
        new_val = mutated_set(content, "val", k, cfg["game_seed"], meta, parent, root, log, who)
    else:
        train_ds = encoded(new_ds, k, meta, root, log)
        new_val = encoded(val_ds, n_val, meta, root, log)
    val = stsnet.Dataset.concat([new_val, encoded(iron_val, n_val, meta, root, log)])
    kw = {}
    if not fresh:
        model, norm, meta = stsnet.widen(model, norm, pmeta, meta, stsnet.Normalizer.fit(train_ds))
        if stsnet.layout_of(meta) != data_layout:
            raise ValueError("finetune: the widened net's layout differs from the layout its sets were encoded in")
        kw = {"start": (model, norm), "replay": encoded(pool_ds, pool, meta, root, log, mapped=True), "share": cfg.get("share", 0.5),
              "anchor": cfg.get("anchor", 0.0)}
    if cfg.get("hp_weight"):
        for d in [train_ds, val] + ([kw["replay"]] if kw else []):
            weigh_targets(d, cfg["hp_weight"])
    curves = {}
    model, norm, hist = train.train(meta["card_repr"], train_ds, val, cfg.get("seed", 0), log, curves,
                                    lr=cfg.get("lr"), epochs=cfg.get("epochs"), **kw)
    parent_info = None if fresh else {"path": os.path.relpath(parent, root).replace("\\", "/"), "sha256": sha256(parent)}
    run = registry.Run.create(cfg.get("name", "finetune"), cfg, datasets, root, parent=parent_info)
    meta = {**meta, "held_out": selfplay.HELD_OUT, "held_out_check9": sts.held_out_card_names(),
            "val_mse": min(hist), "format": selfplay.FORMAT}
    run.save_model(model, norm, meta)
    run.save_curves(curves)
    run.finish(min(hist), meta["card_repr"])
    return run


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="parent", help="the parent net (.pt); omit with start: fresh")
    ap.add_argument("--config", required=True)
    ap.add_argument("--threads", type=int, default=None, help="search threads for self-play")
    args = ap.parse_args(argv)
    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    run = finetune(args.parent, cfg, threads=args.threads)
    print(f"run {run.id}: {run.model_path}")


if __name__ == "__main__":
    main()
