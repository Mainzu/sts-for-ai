# What new golden games would invalidate (2026-11-14)

Question: since the rules version became e47bcfcdb6b2777a (fc124b67), six
rule fixes went in without changing `engine/tests/data/golden.txt` (kb
`cause/rules-changes-outside-golden`): Perfected Strike played from limbo
(6f6a6438), The Guardian's Mode Shift block at turn end (626955c6),
Regeneration and Orichalcum acting first at turn end (cd9a501d), Feed's max
HP on a kill (67267557), Blood for Blood's cost per copy and Rupture on the
player's own Burn/Decay (6c4f392b). Before it, under 7042d1d6a6149ba0,
49600d01 let Artifact block Flex's Strength loss. Adding golden games that
cover these mechanics changes the golden hash, so the rules version moves.
What recorded data would that make stale?

The other engine/content commits since fc124b67 only add content (relics
steps 4-7, the curses, Battle Trance, Reaper, Dual Wield, Juggernaut) or
ascension, which plays A0 as before (725e8675, 90665f89); none changes how
an existing recorded game replays. (`git log fc124b67..HEAD -- engine
content`, read commit by commit.)

## Short answer

Nothing more than is stale already. No dataset, run or solved-DB row is
recorded under e47bcfcdb6b2777a; all of them carry 7042d1d6a6149ba0 (the
version SAME_RULES maps e9c10f64df68a215 to), which main already refuses
to replay since fc124b67. The solved DB uses a fingerprint of its own that
golden does not feed. Only the two job snapshots and gauntlet results are
worth a note, and neither depends on the golden hash.

## Datasets (`datasets/*/manifest.json`)

286 datasets, 4,477,336 games, all `rules_version` 7042d1d6a6149ba0; none at
e47bcfcdb6b2777a; one directory has no manifest. (A Python loop over the
manifests counting `rules_version` and `n_games`.)

- 194 datasets (2,346,205 games) are the starter plus the built-in training
  pool (`selfplay.train_deck`/`varied_deck`; 24 card names, Perfected
  Strike, Rupture, Combust and Flex among them, no Havoc, Double Tap, Feed
  or Blood for Blood), against every Act 1 encounter group, bosses
  included, and with no relics or potions. They can hold Combust breaking
  The Guardian's Mode Shift at turn end and Rupture with Hexaghost's Burns,
  so some games would replay differently.
- 34 datasets (1,610,710 games) use the act1-ironclad and act1-monsters
  packs with `deck_pool: all` (the packnet/widepack runs). By 9fcf17ce
  the pack held Blood for Blood, Feed, Havoc and Double Tap, so these can
  hold every card-side fix (Perfected Strike from Havoc or Double Tap
  included). The datasets made on 2026-11-08 had Feed and Double Tap but
  not Blood for Blood or Havoc.
- 58 datasets (520,421 games) use other content (generated powers,
  mutated monsters, `both`/`ironclad`/`varied` pools): they overlap in the
  official cards and bosses above.

None holds relics or potions, so Regeneration, Orichalcum and Artifact on
Flex can't appear in any of them.

These datasets already fail `registry.examples` with RulesVersionError when
replayed, since main's version is e47bcfcdb6b2777a. Ones with an encoded
cache under `cache/` (18 entries, 13 GB) still load, because the cache path
does not include the rules version; a new golden would not change that.

## Runs (`runs/*/run.json`, `runs/index.csv`)

535 run directories; 526 have `run.json`, all with `rules_version`
7042d1d6a6149ba0; 9 have none. `runs/index.csv` has no rules-version
column. (`grep -o '"rules_version": *"[^"]*"' runs/*/run.json | sort |
uniq -c`.) learn.py and sweep.py already skip these runs when they look for
a finished round to reuse, as the version differs from main's. A run
replays nothing itself; its models were trained on the datasets above.

## Solved DB (`db/`)

`db/solved.sqlite`: 2,434,201 states, `db/train.sqlite`: 2,893,615 states,
all under fingerprint 39bfc65e541f073d (read-only `SELECT fingerprint,
count(*) FROM states JOIN versions GROUP BY version`). The fingerprint is
`solvedb/src/fingerprint.rs`: a hash of the engine's rule files (state.rs,
cards.rs, ...) and content/*.json, not of golden.txt. Every one of the six
fixes edited state.rs or a pack, so each already gave a new fingerprint;
golden games add nothing here. solved.sqlite's positions are the 12,625
`bench` positions (official Act 1 fights); they can hold Combust against
The Guardian and Rupture against Hexaghost.

## Gauntlet results (`results/gauntlet/`)

347 files; none records a rules version or engine commit (`grep -l
'"rules' results/gauntlet/*.json` finds none), so nothing there is keyed
to golden. They are tallies, not replays. A rerun of a starter or
sim-reward gauntlet can differ where Combust meets The Guardian or Rupture
meets Hexaghost; pack gauntlets also where Blood for Blood, Feed or Havoc
and Double Tap with Perfected Strike are drafted.

## Job snapshots (`sts-builds/`, `jobs.py pins`)

10 snapshots. 9 hold golden e9c10f64df68a215, so rules 7042d1d6a6149ba0
(2b77368e5a26, 32924fd97b53, 5c71bae918c6, 78f723207273, 817da2e9daa6,
872a7bbe4925, 9fcf17ce8219, c5bf088dbbcf, d08ef5a4390f); fc124b67a77c
holds e47bcfcdb6b2777a. (`git show <commit>:engine/tests/data/golden.txt`
hashed as registry.rules_version does.) Each snapshot runs its own engine
and golden, so a golden change on main does not touch them. Parked on
them: 1008-1012 (learn, mutate-monsters, gauntlet) on 9fcf17ce8219, and
1016-1017 (gauntlets named `-re47b`) on fc124b67a77c. Those two play the
fc124b67 engine, without the six fixes: their starter/sim-boss sequences
can meet Combust against The Guardian and Rupture against Hexaghost.

## What this means

Adding the golden games costs no data today. It would protect data
recorded from now on: once main has a new version, datasets and runs made
after it are checked against these mechanics. Data made between fc124b67
and that golden change would be the only data a new golden refuses; today
there is none.
