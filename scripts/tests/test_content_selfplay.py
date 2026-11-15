"""Registry-lite step 5 (docs/specs/registry-lite.md): self-play with
generated power cards. Config keys `content` (a pack path, or {"seed",
"powers"} generated at run start) and `content_share` (share of training
decks holding 1-2 generated train-split power cards; default 0 = today's
data bit for bit); dataset manifests carry `content_hash`, and replay
refuses a dataset whose pack isn't loaded.

    python scripts/tests/test_content_selfplay.py
"""

import hashlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

import learn
import registry
import selfplay

QUIET = dict(log=lambda *a: None)
BASE = {"name": "t", "mode": "effects", "n_train": 4, "n_val": 1, "train_seed": 3, "val_seed": 2,
        "search": {"limit": 8}, "setups": "varied"}
# Recorded on 4c48014 (before step 5) for BASE's round-0 training dataset:
# its games' sha256 and a sha256 over its effects-mode cache arrays.
GAMES_PIN = "968dad6655a16ed184652d0ebbadf4e97f3fa3620b0308617872cbc12380cef4"
# Re-pinned 2026-11-02: the default feature layout gained the rules-engine
# series' columns (games unchanged: GAMES_PIN); 2026-11-04: mutated-monsters
# stage B's powers and trigger; 2026-11-06: exhaust-cards (C1) columns;
# 2026-11-07: the exhaust-triggers (C2) trigger column (rows column 7, zero
# on these states; dropping it gives the old pin back); 2026-11-07: the
# quantity-amounts (C4) scalars block_of_k and apply_of_k (zero here;
# dropping them gives the old pin back); 2026-11-09: the CardDrawn trigger
# column (C3, rows column 21) and the cost_less_per_hp_loss card column (C5,
# cards column 13), both zero here (dropping them gives the old pin back);
# 2026-11-10: card upgrades (C6) add the effect scalars pick_upgrade and
# upgrade_hand and the player column pick_upgrade_from_hand, all zero here
# (old columns equal by name); 2026-11-11: card rules add the row trigger
# columns Rule(Forbids), Rule(SetsCost), Rule(ExhaustsPlayed), zero here (old
# columns equal by name; games unchanged); later the same day Clash's play
# condition drops the only_attacks_in_hand card column and adds the
# Rule(PlayableIf) and HandAll(...) row columns (the rest equal by name);
# then Red Skull's crossing triggers add the OwnerBloodied and OwnerUnbloodied
# row trigger columns, zero here (docs/specs/red-skull-strength.md);
# 2026-11-11: relics as their own entity add the CombatStartPreDraw,
# CombatStart, CounterIs, grant_relic and relic row-only columns, zero here
# (old columns equal by name; docs/specs/relic-entity.md); 2026-11-12:
# potions add the Potion(Use) trigger and potion_potency row columns, zero
# here (old columns equal by name; docs/specs/potions.md); 2026-11-12: the
# fight vocabulary adds the OpponentDied, CombatWon, OwnerBlockIs and
# Applying(...) row columns, zero here (old columns equal by name;
# docs/specs/fight-vocabulary.md); 2026-11-12: the after-block passes add
# four Replace(...) triggers, AmountAtMost and replace_at_least, zero here
# (old columns equal by name; docs/specs/after-block.md); 2026-11-13:
# Champion Belt adds the OwnerApplied row trigger column, zero here (old
# columns equal by name; docs/specs/act1-singles.md).
ARRAYS_PIN = "582baccd6a597f344952cd4ebb577826f59e75cfa63fca9eaad49430beda0547"
PACK = {"seed": 7, "powers": 64}


def tmp():
    return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)


def arrays_hash(d):
    h = hashlib.sha256()
    for k in sorted(vars(d)):
        v = getattr(d, k)
        if isinstance(v, np.ndarray):
            h.update(k.encode())
            h.update(np.ascontiguousarray(v).tobytes())
    return h.hexdigest()


def test_no_content_is_bit_identical():
    """Without `content` (or with content_share 0) the dataset's games and
    its cache arrays match the pre-step-5 pin, and the manifest has no
    content_hash."""
    for cfg in (BASE, {**BASE, "content": PACK, "content_share": 0.0}):
        with tmp() as root:
            ds = learn.dataset(cfg, "train", root, **QUIET)
            m = registry.load_manifest(ds, root)
            assert m["games_sha256"] == GAMES_PIN
            assert "content_hash" not in m and "content" not in m["config"]
            d = registry.examples(ds, "effects", root=root)
            assert arrays_hash(d) == ARRAYS_PIN
            del d


def test_share_half_uses_train_cards_only():
    """content_share 0.5: about half of 2,000 decks hold 1-2 generated
    cards, every one from the pack's train split, none from test."""
    pack, _ = selfplay.load_content(PACK)
    train, test = selfplay.content_cards(pack, "train"), selfplay.content_cards(pack, "test")
    assert train and test
    deck = selfplay.content_deck(selfplay.varied_deck, train, 0.5)
    rng = np.random.default_rng(0)
    decks = [deck(rng) for _ in range(2000)]
    gens = [[c for c in d if c.startswith("gen:")] for d in decks]
    share = np.mean([bool(g) for g in gens])
    assert 0.46 < share < 0.54, share
    assert all(len(g) <= 2 for g in gens)
    assert {c for g in gens for c in g} <= set(train)
    assert not {c for g in gens for c in g} & set(test)


def test_dataset_with_content_records_hash_and_replays():
    """A tiny content dataset: its config and manifest carry the pack's
    hash, some games hold generated cards, and its cache builds (codec
    bytes of generated states are empty)."""
    cfg = {**BASE, "n_train": 6, "content": PACK, "content_share": 1.0}
    with tmp() as root:
        ds = learn.dataset(cfg, "train", root, **QUIET)
        m = registry.load_manifest(ds, root)
        h = selfplay.load_content(PACK)[1]
        assert m["content_hash"] == h and m["config"]["content"]["hash"] == h
        games = registry.load_games(ds, root)
        assert all(any(c.startswith("gen:") for c in g["deck"]) for g in games)
        d = registry.examples(ds, "effects", root=root)
        assert len(d) > 0
        assert (d.codec_len == 0).any()
        del d
        # The validation set stays official.
        val = learn.dataset(cfg, "val", root, **QUIET)
        assert "content_hash" not in registry.load_manifest(val, root)


def test_replay_refuses_without_the_pack():
    """A manifest whose content_hash isn't loaded in this process can't be
    replayed, with a message naming the hash."""
    with tmp() as root:
        ds = learn.dataset(BASE, "train", root, **QUIET)
        p = os.path.join(registry.datasets_dir(root), ds, "manifest.json")
        import json
        with open(p, encoding="utf-8") as f:
            m = json.load(f)
        m["content_hash"] = "0123456789abcdef"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(m, f)
        try:
            registry.examples(ds, "effects", root=root)
        except registry.ContentError as e:
            assert "0123456789abcdef" in str(e)
        else:
            raise AssertionError("replay without the pack was allowed")


def test_content_split_test_uses_test_cards():
    """`content_split: "test"` (oracle arm): training decks get the pack's
    test-split cards only, and the dataset key records the split."""
    cfg = {**BASE, "n_train": 6, "content": PACK, "content_share": 1.0, "content_split": "test"}
    test = set(selfplay.content_cards(selfplay.load_content(PACK)[0], "test"))
    with tmp() as root:
        ds = learn.dataset(cfg, "train", root, **QUIET)
        assert registry.load_manifest(ds, root)["config"]["content"]["split"] == "test"
        gen = [c for g in registry.load_games(ds, root) for c in g["deck"] if c.startswith("gen:")]
        assert gen and set(gen) <= test


def fnv1a(b):
    h = 0xcbf29ce484222325
    for x in b:
        h = ((h ^ x) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def content_dataset(root):
    cfg = {**BASE, "n_train": 6, "content": PACK, "content_share": 1.0}
    ds = learn.dataset(cfg, "train", root, **QUIET)
    return ds, registry.load_manifest(ds, root)["content_hash"]


def fresh(code, *args):
    """Runs `code` in a new Python process (no pack loaded) with scripts/ on
    the path; returns its stdout."""
    import subprocess
    here = os.path.join(os.path.dirname(__file__), "..")
    r = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {here!r})\n" + code, *args],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_pack_store_round_trip():
    """Content identity (docs/specs/runtime-registry.md stage 2): a content dataset
    stores its pack as packs/<hash>.json, whose bytes hash to the name; a
    dataset without content stores nothing."""
    with tmp() as root:
        ds, h = content_dataset(root)
        p = os.path.join(registry.packs_dir(root), h + ".json")
        with open(p, "rb") as f:
            assert fnv1a(f.read()) == h
        assert not os.path.exists(os.path.join(registry.datasets_dir(root), "packs", "manifest.json"))
        assert registry.find(registry.load_manifest(ds, root)["config"], root=root) == ds
    with tmp() as root:
        learn.dataset(BASE, "train", root, **QUIET)
        assert not os.path.exists(registry.packs_dir(root))


RECOVER = """
import registry, sts
root, ds = sys.argv[1], sys.argv[2]
assert sts.loaded_content() == []
d = registry.examples(ds, "effects", root=root)
print(len(d), int((d.codec_len == 0).any()), ",".join(sts.loaded_content()))
"""


def test_replay_recovers_from_store():
    """End-to-end: a fresh process that never generated the pack replays a
    content dataset, loading the pack from the store by its hash."""
    with tmp() as root:
        ds, h = content_dataset(root)
        n, gen, loaded = fresh(RECOVER, root, ds).splitlines()[-1].split()
        assert int(n) > 0 and gen == "1" and loaded == h


TAMPER = """
import registry, sts
root, ds = sys.argv[1], sys.argv[2]
try:
    registry.examples(ds, "effects", root=root)
except registry.ContentError as e:
    print("refused" if "packs" in str(e) else "other", ",".join(sts.loaded_content()) or "-")
"""


def test_tampered_pack_refused():
    """A stored pack whose text no longer hashes to its name is refused,
    naming the file, and never loaded."""
    with tmp() as root:
        ds, h = content_dataset(root)
        p = os.path.join(registry.packs_dir(root), h + ".json")
        with open(p, encoding="utf-8") as f:
            text = f.read()
        with open(p, "w", encoding="utf-8", newline="") as f:
            tampered = text.replace('"version": ', '"version":  ', 1)
            assert tampered != text
            f.write(tampered)
        assert fresh(TAMPER, root, ds).splitlines()[-1].split() == ["refused", "-"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
