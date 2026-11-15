# Explorer v2: the game as the net plays it

Status: closed (2026-11-08, built and in use; decisions "Explorer v2 as built").

## Outcome

A local page where the owner opens any of today's tests (a gauntlet
sequence, a mutated-monster or mutated-card fight, a boss replay), steps
through it turn by turn as the player played it, seeing what the net saw
and every score it chose from, and can take over at any decision, inside a
fight or between floors, while the net keeps scoring the new line. It
looks and behaves like the dashboard.

Why: the averages (clears, paired HP, novelty cost) say how often the net
fails, not what its failures look like. The old explorer answered that for
solved puzzles only, and today it can't start (both solved databases hold
no rows of the current rules version).

**Non-goals:**

- Solving positions on the new views (the old solved-position views stay,
  for a current database).
- A side-by-side view of two result files (the owner didn't pick it,
  2026-11-07).
- Editing content or result files; starting jobs from the page.
- Hosting beyond 127.0.0.1; a phone layout.
- Relics, potions and the map (the engine doesn't model them).

## Behavior

### Running it

`python scripts/explore.py [--port 8765]`

Nothing else is chosen at start: `--db` and `--model` go (owner,
2026-11-07). The page offers both, and changes take effect without a
restart.

- Serves `http://127.0.0.1:8765`, as today. The `explore` entry in
  `.claude/launch.json` stays.
- **Database picker** (top bar): the `db/*.sqlite` files, each with its
  size and whether it holds rows of the current rules version (read
  through sqlite3 `mode=ro`, so listing writes nothing), plus "none". Only
  a current one can be opened; a stale one is listed greyed out, saying
  so. Opening runs in the background as today (`sts.SolvedDb` reads every
  row's hash: about 2.5 min on `db/solved.sqlite`) with its progress on
  the status line; picking another closes the first. One database is open
  at a time, shared by every tab of the page. Reopen stays.
- **Comparison players** (top bar): the heuristic is always on; the
  owner adds or removes nets from a searchable list of the runs that have
  a `model.pt` (386 today), newest first, with the product net
  (`configs/product.json`) and the nets of the open file listed on top. A
  net can take the player settings suffixes (`@hpb0.01`, `@tsl1`, ...,
  how/player-strings), typed or picked. Each added net's one-turn scores
  and pick show beside the heuristic's on every view: the puzzles (its
  picks and regret column, computed on first use, about a second over the
  2,000 puzzles, and cached under `cache/explore/` as today) and every new
  view (beside the player's own scores).
- The choices live in the page's URL (`?db=&with=`), so a reload or a
  shared link keeps them; the server keeps loaded nets in memory but no
  per-page choice, and every request names the players it wants.
- **Its own copy of `sts`.** Before anything imports `sts`, the explorer
  copies the installed module (`.venv/Lib/site-packages/sts/`) to
  `cache/explore/sts-<first 12 hex of the .pyd's sha256>/sts/` (once per
  build) and puts that folder first on `sys.path`. Rebuilding or swapping
  main's `sts` (AGENTS.md) is then never blocked by an open explorer. On
  start it deletes older copies it can delete (a copy another explorer
  still holds is locked and stays). The page header names the build
  (the hash) it runs.
- **No database needed.** Today `check_db` refuses to start without a
  current database, although the bench puzzles don't need one: all 2,000
  in `data/bench/puzzles.json` replay under today's rules with the same
  options (checked 2026-11-07). So:
  - The **Bench puzzles** tab always works, as today (set, turns to end,
    contested, dull and wrong-picks filters, sort by any header, paging,
    regret per player, reroll, back, the trail, Solve). Its exact values
    are the file's, solved under rules `39bfc65e541f073d`; the tab says so
    in its header, since today's rules version differs.
  - **Run positions**, **Row id**, database lookups and Reopen need a
    database of the current rules version. Until one is open they are
    hidden and the status line says why (none picked, or every database
    is stale); with one they work as today.
- Read-only as today: nothing writes a database, a result file or
  content. It writes only its own caches under `cache/explore/`.

### Look

- The dashboard's stylesheet (`dashboard.CSS`, imported, not copied) plus
  the explorer's own additions: the same top bar, cards, colours, light
  and dark themes, tooltips on every number. The page stays one static
  HTML file with plain JavaScript, no build step.
- The top bar links to the dashboard (`127.0.0.1:8766`); the dashboard's
  top bar gains an "Explorer" link back. That link is the dashboard's only
  change.
- Shapes over text where nothing is lost: HP as bars, a sequence as a strip
  of 11 floor cells, scores as bars beside their numbers.

### Entry points

1. **Gauntlet files** (`results/gauntlet/*.json`, every setting: cell or
   starter decks, card rewards of every chooser, packs, rest, removal,
   elite skip, mini-run's extra offers and mid-rest, one or two turns
   deep, one-turn floors).
   - The file list groups files by player and shows each file's setting
     tags, sequences played and clear rate; filter by text.
   - A file opens its sequence list: one row per sequence with its half,
     cell, boss, cleared or the floor it died on, end HP, and the strip of
     11 floor cells coloured by HP left (tooltip: encounter, HP in and out,
     card taken, rest, removal). Filter by half, cleared, died on floor k,
     encounter, a card in the final deck; sort by any column; 25 per page.
   - A sequence opens its run: the floors in order with each floor's
     events (offers, rest, removal, path); a floor opens its fight.
2. **Mutated monsters and mutated cards** (`results/mutate/*.json`, from
   `mutate_monsters.py` and `mutate_cards.py`, the generated-enemies
   batches included). A file lists its starts (sequence, floor, encounter)
   by modifier, with each player's wins and mean HP per modifier and the
   parent. A cell (start, modifier or parent, player, seed) opens that
   fight, rebuilt by the script's own functions.
3. **Boss replays** (`results/boss_replay/*.json`). A file lists its rows
   (sequence, boss, deck, observed arrival HP and outcome) with the
   win grid by entry HP and seed; a cell (HP, seed) opens that fight,
   rebuilt by `boss_replay.py`'s own functions.
4. **Content browser.** Every card, monster and power the build can load:
   official (`content/*.json`), the packs in `content/packs/`, the
   mutated-card pack, the generated-enemy pack (`mutate_monsters.gen_pack`),
   with their numbers as the content files give them, each labelled by
   source. With a gauntlet file open, a card links to the sequences whose
   deck held it and a monster to the floors that fought it.
5. **Solved positions** (only with a current database): the old views,
   unchanged in behaviour, restyled.

### Replays

- A fight is replayed by the player that played it, with the file's own
  settings: the player string, `--two-turn`, line seed, step line, one-turn
  floors, the pack. One turn deep it is `sts.run("search", record=True)`;
  two turns deep it is `depth_paired.guarded_fight` with `record`. The
  explorer never re-implements a player.
- **Fidelity check.** Each replayed floor's win and end HP are compared
  with the file's row, and each offer and the card taken with the file's.
  A difference shows as a banner on that floor ("this build plays floor 6
  differently: file 42 HP, replay 38 HP") and a mark on its strip cell;
  the replay is still shown. Likely causes the banner names when it can:
  the pack's hash differs from the one in the file's settings, or the
  player's `model.pt` is missing.
- A missing player net (`runs/<id>/` gone) or a file whose seed or shape
  differs from today's `gauntlet.py` opens its lists but refuses replays,
  saying why.
- Replays are cached under `cache/explore/replays/`, keyed by the file's
  settings, sequence, floor, deck, HP and the build hash, so a second
  opening is instant. Waits: one-turn floors under a second; a two-turn
  floor about 8 s (7.2 stepped fights per thread-minute at 400k nodes,
  how/two-turn-games); the page shows a working indicator. One thread per
  replay: a fight's decisions are sequential.

### The state view

- **Drawn board** from a new read-only binding method `Combat.board()`
  (see Build steps): each living monster as a panel (name, HP bar, block,
  intent with damage and hits, powers as badges with amounts); the player
  (HP bar, block, energy, powers); the hand as card tiles (cost, name,
  upgraded mark; the card's numbers on hover); draw, discard and exhaust as
  counts that open their contents on click. A toggle shows `render()`'s
  text instead.
- **What the net sees.** The draw pile is shown as its contents sorted by
  name, never in order, plus a card known to be on top when there is one
  (the net's input has it). A collapsible "net inputs" panel lists the
  input rows the player's net gets for this state (`Features.encode` with
  the net's own layout), each by its row and column names, with values.
  The net's static value of the state shows beside the board. For the
  heuristic player the panel lists `heuristic_parts`.
- **Options table** (as the old explorer): each option's action group and
  kind (deterministic, chance, divergent), the player's own score (the
  search's value for that option at that decision: one turn deep from the
  record's values, two turns deep from the two-turn search the player
  ran), a mark on the player's pick and on the recorded action, and the
  heuristic's one-turn score with a mark on its pick (plus each added
  comparison net's). Exact values only from a current solved database
  (`lookup`), when it holds the state.
- **Only what transfers** (owner, 2026-11-07): the new views carry over the
  solve mode's features that make sense without exact values (option
  table, step, reroll, back, the trail, plain-words tooltips) and add no
  substitutes for the ones that don't: no "wrong picks" or regret, no
  Solve. Decisions are listed only within a fight you open; there is no
  list of decisions across a whole file, so nothing is precomputed.
- Every column and field gets a plain-words tooltip, as the solve mode's
  `TIP` table does today (with the value scale where a score shows).
- Floor events show their own scores: a card offer shows each card's and
  "skip"'s score from the run's chooser (sim, vrun or value) and its pick;
  a rest or removal shows its options' scores the same way. These come
  from the chooser's own scoring function, the one it chose by.

### Taking over

- **Inside a fight:** clicking any option plays it (one sampled outcome
  for a chance option, seed `k`; "reroll" picks another) and shows the
  next decision with the player's scores for it, computed now with the
  file's settings. A breadcrumb leads back. While the line follows the
  recorded actions it is marked "as played"; from the first difference
  it is marked "your line".
- **Between floors:** at a card offer, rest or removal the owner can pick
  another choice. The next floors are then played by the file's player
  with the new deck and HP, one floor at a time, when opened, and are
  marked "your line" on the strip. A fight the owner took over and finished
  carries its end HP into the next floor.
- The page keeps no session on the server: the client sends the line
  (state bytes in hex, or the choices made since the file's row), as the
  old explorer did.

### Endpoints

JSON over GET, one handler function each, as today. New:
`/api/files?kind=gauntlet|mutate|boss_replay`, `/api/sequences?file=&...`,
`/api/run?file=&i=&choices=`, `/api/floor?file=&i=&k=&choices=`,
`/api/mutate?file=&...`, `/api/boss_replay?file=&...`,
`/api/fight?...` (a mutate or boss-replay cell), `/api/content?kind=`,
`/api/view?hex=&player=` (board, net inputs, options for any state),
`/api/step` gains `player=`; `/api/dbs` (the database list with each
one's status), `/api/open_db?path=` (replaces the start-time `--db`),
`/api/nets` (the net list). Every endpoint that shows comparison scores
takes `with=` (the players, heuristic first); `/api/status` reports the
open database and the nets loaded. Existing endpoints keep their shapes;
fields may be added.

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| `gauntlet.py play` / `read` | Files it writes are byte-identical after the player factoring and the chooser's score function | new `gauntlet_players_match_play_cmd` (step 1, passes on today's code against a stored fixture) |
| Gauntlet result files | Read only, format unchanged | `explore_read_only` extended to results files |
| `depth_paired.guarded_fight` record, `two_turn_games.py` datasets | Existing record keys and values unchanged; the new per-decision scores sit under a new key only `explore` reads | new `two_turn_record_pinned` (step 1) |
| `mutate_monsters.py`, `mutate_cards.py`, `boss_replay.py` | Their rebuilds and outputs unchanged; the explorer calls their functions | their existing tests (`test_mutate_monsters`, `test_mutate_cards`, `test_boss_replay`) |
| The binding (`py/src`) | Additive only; rules version (golden.txt hash) and golden games identical; `render()` unchanged | `test_render`, golden test, new `board_matches_render` |
| Dashboard | Unchanged except the nav link | `test_dashboard` |
| Rebuilding `sts` (AGENTS.md) | An open explorer never holds main's `.pyd` | new `explore_private_sts` |
| Old explorer views | Same numbers and controls (puzzle filters, header sort, paging, reroll, back, trail, Solve; positions, row id and Reopen on a current database) | the 7 tests in `test_explore.py` (pass today); new `explore_puzzles_without_db` |
| Jobs and pinned snapshots | Untouched; the explorer never reads or writes `sts-builds/` | none needed |

## When in doubt

Prefer showing the player's own number, or nothing, over a number
recomputed another way; prefer one more endpoint field over client-side
logic.

## Scope

- **May change:** `scripts/explore.py`, `scripts/explore.html` (rewrite
  allowed), `scripts/tests/test_explore.py`; in `scripts/gauntlet.py` a
  factoring of `play_cmd`'s player and hook construction into a function of
  a settings dict, and the choosers' scoring split out so the explorer can
  read it (no behaviour change); in `scripts/analysis/depth_paired.py` one
  new record key; small helpers in `mutate_monsters.py`, `mutate_cards.py`
  and `boss_replay.py` if a rebuild is not callable for one row as it
  stands (no behaviour change); one additive read-only method
  `Combat.board()` in `py/src` with its test; the dashboard's nav link;
  README, the explorer's docstring, decisions.
- **Interfaces it may change:** the explorer's endpoints and cache files.
- **Off limits:** `engine/` (rules, codec, search), the rules version and
  golden games, every result file format, `jobs.py` and the job queue,
  `kb` and `docs/claims/`, training and the gauntlet's play behaviour.
- **Outside the repo:** none (`cache/explore/` is inside, gitignored).

## Decisions taken (provisional)

- The explorer stays its own server (port 8765) with the dashboard's look
  imported from `dashboard.CSS`, rather than pages of the dashboard: it
  loads `sts` and torch, which the dashboard never does.
- Its own copy of `sts`, so main's rebuilds are never blocked (owner,
  2026-11-07). Replays run on the build current at start; differences from
  the file are flagged, not hidden (owner: faithful to the net wins).
- The board's data comes from a new `Combat.board()` in the binding, not
  from parsing `render()` (owner left it to the session: parsing breaks
  silently when the wording changes).
- The board hides what the net doesn't see (draw order) and shows the
  net's input rows (owner, 2026-11-07).
- No start-time choices (owner, 2026-11-07): the CLI keeps only `--port`;
  the database and the comparison nets are picked in the page, kept in its
  URL, and every request names its players, so the server holds no
  per-page choice.
- Heuristic one-turn scores beside the player's, plus each comparison net
  added in the page (owner).
- Taking over reaches across floors (owner).
- New views carry only the solve mode's features that transfer; no
  wrong-pick substitute and no file-wide decision list (owner).
- Bench puzzles work without a database, labelled with their rules
  fingerprint; positions, row ids and Reopen need a current database.

## Outside assumptions

- Replays reproduce the files: one-turn `sts.run` with `record=True` plays
  the same actions as without it, and two-turn guarded fights with line
  seed are deterministic. Expected: every floor of 20 sequences of a
  one-turn headline file and 5 of a two-turn file match (won, end HP,
  offers, took) on today's build. Checked in step 5; a mismatch on files
  from today's build is a stop point.
- Loading several packs in one process works: checked 2026-11-07 (act1-
  ironclad and act1-monsters loaded together, `loaded_content` listed
  both). The pack in the three pack gauntlet files has hash
  `1c7d392b4ed0173e`; today's `act1-ironclad.json` hashes to
  `58bcc37ab3ce0af4`, so those files will show the fidelity banner unless
  the replays still match.
- Copying the `sts` package folder and importing the copy works on
  Windows like the snapshots' `pyroot` (jobs.py does the same). Checked by
  `explore_private_sts`.
- Memory: the old explorer peaked at 0.4 GB working set / 1.0 GB commit
  with a net; a two-turn replay adds about 1.4-1.6 GB while it runs
  (approach review). Measured in step 11.

## Verification

Tests first (in `scripts/tests/test_explore.py` unless named otherwise):

- `gauntlet_players_match_play_cmd` (test_gauntlet.py): `play_cmd` on 4
  cell sequences with the heuristic and sim rewards, and the same through
  the factored function, give byte-identical files, equal to a fixture
  stored from today's code.
- `two_turn_record_pinned`: a guarded fight with `record` returns exactly
  today's keys and values for a fixed spec (fixture from today's code);
  after step 4 the only addition is the scores key.
- `board_matches_render` (test_render.py): over 200 states from several
  encounters (packs loaded included), every number and name in `board()`
  appears in `render()` at the same place; turn, HP, block, energy, pile
  counts equal.
- `explore_private_sts`: after import, `sts.__file__` is under
  `cache/explore/`, and renaming main's `.pyd` aside and back succeeds while
  the explorer's module is loaded.
- `explore_starts_without_db`: the explorer starts with no database open;
  `/api/dbs` lists the test folder's databases with current or stale
  marked; opening a stale one is refused with the reason and writes
  nothing (bytes and mtime unchanged); the status says the database views
  are off and why; the gauntlet endpoints work.
- `explore_pick_db`: opening the current test database through the
  endpoint, then another, gives the same `/api/state?id=` answers as the
  old start-time `--db` did (the existing fixture); the first is closed.
- `explore_players_param`: `/api/puzzles?with=heuristic,<test net>` gives
  the picks and regrets `bench.search_puzzles` gives for that net (as
  `explore_picks_match_bench` does today); dropping the net from `with`
  drops its columns; a second request with it runs no search (cache).
- `explore_net_list`: `/api/nets` lists the runs with a `model.pt` in a
  test registry folder, newest first, the product net and the open file's
  nets on top; a bad player suffix is refused with the bench's message.
- `explore_puzzles_without_db`: with no database, `/api/puzzles` and
  `/api/state?puzzle=` give the same rows, values, picks and regrets as
  with the test database; the status names the puzzle file's rules
  fingerprint.
- `explore_gauntlet_replay_matches_file`: on a small file made in the test
  (one-turn, sim rewards, rest and removal on), every floor's replay
  matches the row; with one row edited in a copy, that floor is flagged.
- `explore_two_turn_replay`: one two-turn floor (low node cap) matches its
  row, and its option scores equal the scores key of the record.
- `explore_sequence_filters`: half, cleared, died-on-floor, encounter,
  card filters, sort and paging over a hand-made file.
- `explore_offer_scores`: the chooser's shown scores pick the card the row
  took, on every floor of the test file.
- `explore_takeover`: choosing the recorded option at every decision
  reproduces the floor; a different card at floor 2 puts that card in
  floor 3's deck and the floor is marked as the owner's line.
- `explore_net_inputs`: the inputs panel equals `ev.features.encode` of
  the state for a test net; no endpoint returns the draw pile's order.
- `explore_mutate_replay` / `explore_boss_replay`: a cell's replay matches
  the file's win and HP for that seed (small files made by the scripts in
  the test).
- `explore_content`: counts per kind equal the content and pack files'
  entries; card-to-sequence links equal a direct scan of the test file.
- `explore_server_smoke` extended: every endpoint answers 200 on the
  fixture; the page and `/ui.css` load. `test_dashboard`: the nav link.

End-to-end: start the explorer in the browser pane while a job runs; open
today's product headline file, filter to sequences lost at the boss, open
one, check its floors carry no fidelity banner, open the boss fight, step
three decisions as played, take a different option, reroll, go back; at an
earlier card offer take another card and open the next floor; open a
mutated-monster cell and the content browser. While it runs, rename main's
`.pyd` aside and back (no lock). Screenshots of each view in light and dark.

## Don't guard

Two explorers writing the same cache entry (one user; writes are atomic
renames anyway), malformed hex or choices from the page, result files
edited while open, a `.pyd` copy deleted while the explorer runs.

## Build steps

1. **Pins.** `gauntlet_players_match_play_cmd`, `two_turn_record_pinned`,
   with fixtures from today's code. Check: both pass on unchanged code.
2. **Own `sts`, no start-time choices.** The copy at import, old copies
   cleared; `--db` and `--model` replaced by `/api/dbs`, `/api/open_db`,
   `/api/nets` and the `with=` parameter; database views optional; the
   old tests moved from constructor arguments to these endpoints. Check:
   `explore_private_sts`, `explore_starts_without_db`, `explore_pick_db`,
   `explore_players_param`, `explore_net_list`,
   `explore_puzzles_without_db`, the 7 old tests.
3. **`Combat.board()`** in `py/src`, rebuilt and installed per AGENTS.md
   (`jobs.py impact sts` first, recorded in the commit). Check:
   `board_matches_render`, `test_render`, golden test, rules version
   unchanged.
4. **Players from settings, chooser scores, two-turn scores.** Factor
   `play_cmd`'s construction; split the choosers' scoring; add the record
   key in `guarded_fight`. Check: step 1's pins, `test_gauntlet`,
   `explore_offer_scores` (data layer only).
5. **Gauntlet data layer.** File list, sequence list, run, floor replay
   with cache and the fidelity check. Check:
   `explore_gauntlet_replay_matches_file`, `explore_two_turn_replay`,
   `explore_sequence_filters`; then the outside assumption on 20 + 5 real
   sequences (**stop point** if today's files don't replay).
6. **State view data: net's view and comparison.** Board, hidden draw
   order, net inputs, static value, comparison scores. Check:
   `explore_net_inputs`.
7. **Taking over.** Inside fights and between floors. Check:
   `explore_takeover`.
8. **Mutate and boss-replay files.** Check: `explore_mutate_replay`,
   `explore_boss_replay`, the scripts' own tests.
9. **Content browser data.** Check: `explore_content`.
10. **Page, part 1.** Shell with the dashboard's style, nav both ways,
    file and sequence lists with the floor strip, run view, drawn board,
    options table. Check: `explore_server_smoke`, `test_dashboard`, the
    browser pane on a real file (screenshots light and dark).
11. **Page, part 2.** Take-over controls, net inputs panel, offer scores,
    mutate, boss-replay and content views, solved views restyled. Check:
    the end-to-end run; memory peak measured with a two-turn replay.
12. **Docs.** README line, docstring, decisions "Explorer v2 as built".
    Check: spec-reviewer.

No step is a long run (the longest test replays one two-turn floor at a
low node cap).

## Amendment 1 (2026-11-08) · built cd72667

The owner's corrections after the build (2026-11-08). They keep
the direction; they change how the explorer decides that the owner's line
left the recorded run, and add undo and reset.

### Behavior (replaces the matching parts of "Taking over")

- **Afterstates decide, not decisions.** Whether the owner's line is still
  the recorded run is judged by the state it reaches, never by the choice
  that reached it (docs/concept.md: different actions that lead to
  identical states are one option). The comparison is exact: the engine's
  state (`CombatState`, which already derives equality and hashing), the
  random-number generator left out.
  - **Inside a fight:** after every step the new state is compared with
    the fight's recorded decision states. If it equals recorded decision m,
    the line is "as played" again from m: the page shows the record's
    scores and follows the record from there, with no new search. Two card
    orders that reach the same state count as the recorded line. States
    with pack content are compared the same way (no encoding needed).
  - **At a fight's end:** the floor's result is what the fight finished
    with. If the carried state (won, end HP, deck) equals the row's, the
    run stays on the file's line and no later fight is replayed.
  - **Between floors:** after every fight and every event (offer, extra
    offer, rest, removal, path) the carried state (HP and the deck as a
    multiset of cards) is compared with the file's at the same point. While
    they differ, later floors are the owner's line, played by the file's
    player when opened. As soon as they are equal again, the line rejoins
    the file's: later floors use the row's results and events, with no
    replay and no chooser call.
  - Finishing a floor's fight again replaces that floor's earlier result,
    so going back and finishing it as played restores the file's line.
- **Undo and reset.** Every change the owner makes is one entry in an
  ordered history kept in the URL: a step inside a fight, a fight's
  result, a pick at an event. Undo removes the last entry; Reset removes
  them all and shows the recorded run. Both are buttons in the run view and
  the fight view, and the browser's own back button also steps back, since
  each change is one URL. A short list ("your changes") names each entry,
  and the page marks the entries that changed nothing (the afterstate
  equalled the record's).
- **Click where you read.** A floor row opens its fight (or plays it, on
  the owner's line) when clicked anywhere on the row; the separate "open
  fight" button goes. Other clickable rows and cards behave the same.
- **Controls grouped by kind.** The board's text/board toggle sits on the
  board panel, as a view control. The line controls (Back, Reroll, Undo,
  Reset) sit together, apart from it.
- **A tooltip says what its label doesn't, or there is none.** Text that
  repeats the label, or names what kind of thing it is ("move name"), is
  removed. The content-backed tooltips say what the thing does, generated
  from the content files' own data (`content/*.json` and the packs), so
  they stay right when content changes:
  - an encounter: its monsters with their HP ranges, and its group
    (hallway, elite, boss);
  - a monster: HP range, starting powers and block, and its moves (each
    move as below), plus how it picks them when the pattern is simple to
    say (first turn, then repeats);
  - a move (the intent): every effect in order, in plain words ("deal 6
    damage", "deal 5 damage 2 times", "gain 6 block", "apply 2 Weak to
    you", "gain 3 Ritual"); damage only when the move deals some, with
    the shown number explained when it differs from the base (Strength,
    Weak and the like change it);
  - a power: what it does per stack, from its statics, hooks and
    replacements ("adds 1 damage per stack to attacks", "at the end of
    its turn, gains Strength equal to its stacks"), and whether it is a
    debuff;
  - a card tile: cost, type and its effects the same way.
  Every other tooltip on the page is audited by the same rule; the build
  lists each one it removed or rewrote.
- **Long descriptions in a hover card** (owner, 2026-11-08): text longer
  than one short line (a monster's moves, an encounter's monsters, a card's
  effects) shows in a hover card (also called a popover): a styled panel
  in the page's look that opens beside the element on hover or keyboard
  focus, with a heading and one line per move, monster or effect, and
  closes when the pointer leaves. It never moves the layout around it.
  Short texts stay plain tooltips.

### Fits with (added)

| Neighbour | Must stay true | Test |
|---|---|---|
| The binding | Equality is additive; `render()`, `board()`, golden games and the rules version unchanged | `combat_eq` (new), test_render, golden test |
| Replays of the file's line | Unchanged numbers; a line that rejoins uses the row's results and the record's scores | `explore_gauntlet_replay_matches_file`, the new tests below |

### Scope (added)

May change: `scripts/explore.py`, `scripts/explore.html`,
`scripts/tests/test_explore.py`, `scripts/tests/test_render.py` (or a
binding test file), one additive pair `Combat.__eq__` / `__hash__` in
`py/src` over the engine state without the RNG (rebuild and swap per
AGENTS.md), decisions. Off limits as before.

### Verification (added; each must fail on today's code where it tests behaviour)

- `combat_eq`: a clone equals its source; a stepped state doesn't; two
  card orders that reach the same state are equal; the same state with
  another seed (`with_seed`) is equal; equal states hash the same; a pack
  state compares without encoding.
- `explore_fight_redo_same_afterstate` (the owner's report): on the pinned
  file, finish floor k's fight with an end HP one off the row's, then
  finish it again with the row's result; the run is on the file's line,
  and no later floor is replayed (the outcome function is stubbed and
  counted: zero calls).
- `explore_event_rejoins`: a different pick at an offer, then a removal of
  that card at the removal floor, leaves the deck equal to the row's; the
  floors after it are the file's line with zero replays and zero chooser
  calls.
- `explore_step_rejoins`: inside a recorded fight, play two cards in the
  other order than the record; the state after the second equals recorded
  decision m, so it is "as played" with the record's scores and no search
  (stubbed and counted).
- `explore_history`: the choices list in order; Undo's request (the list
  without its last entry) gives the run before that entry; an empty list
  gives the recorded run.
- Browser: the owner's sequence of actions (finish a fight slightly
  differently, go back, finish it as played) shows the file's line with no
  "playing" indicator on later floors; Undo and Reset work from the run
  and fight views; a floor opens by clicking its row; the toggle sits on
  the board panel. Screenshots light and dark.

### Build steps

A1. **`Combat.__eq__` / `__hash__`** in `py/src`, rebuilt and swapped
    (`jobs.py impact sts` recorded). Check: `combat_eq`, test_render,
    golden test, rules version unchanged.
A2. **Afterstates between floors and at a fight's end** in the line
    walker. Check: `explore_fight_redo_same_afterstate`,
    `explore_event_rejoins`, `explore_history`, the existing take-over and
    replay tests.
A3. **Afterstates inside a fight.** Check: `explore_step_rejoins`,
    `explore_takeover`.
A4. **Page:** history with Undo and Reset (steps inside a fight join the
    URL), clickable floor rows, the toggle on the board panel. Check: the
    browser run above; `explore_server_smoke`.
A5. **Tooltips.** Plain-words describers for encounters, monsters, moves,
    powers and cards, from the content data, served with the board and
    the content endpoints, long ones in hover cards; the page's tooltips audited and rewritten or
    removed. Check: `explore_describe` (Cultist's Incantation reads "gain
    3 Ritual" with no damage; Dark Strike "deal 6 damage"; a multi-hit
    move names its hits; Strength's text names damage per stack; every
    official and pack monster, move, power and card gets a non-empty text
    that differs from its name, and no describer raises on any of them);
    the browser: hover an encounter, an enemy, a non-damage intent, a
    power, a card; the list of tooltips removed or rewritten in the
    report.

## Amendment 2 (2026-11-08) · built 154a913

Corrects Amendment 1's hover-card bullet (owner): "long" meant a kind of
thing whose description *can* be long, not a description that happens to
be long. Judging each description by its length showed the same kind
sometimes as a plain tooltip and sometimes as a hover card.

- **Fixed per kind.** Every encounter, monster, move (intent, the damage
  pill included), power and card shows its description in a hover card,
  however short it is ("Gain 3 Ritual." too). Everything else (column
  headers, field explanations, controls, truncated names) stays a plain
  tooltip, whose text is short by design. No description picks its form
  by its length.
- **Check:** in the browser, every element carrying a content description
  (enemy names, intents, power pills, card tiles, pile lists, encounter
  names in every view, content-view rows) opens a hover card, and none of
  them has a `title`; Incantation's intent is the short case. The page has
  no length rule left (`tipAttr` has no length or line-count branch).

A6. **Hover card per kind.** `tipAttr` always gives content descriptions
    a hover card; the damage pill's text joins the intent's card. Check:
    the browser check above (fails today on Incantation's intent).

## Amendment 3 (2026-11-08) · built d013d78

The owner's readability corrections to the mutations, boss-replay and
content views, the card text and the hover card.

### Behavior

- **Group by, one mechanism for every table.** The page has one
  group-by control that any list table can offer: pick a column, and
  rows are grouped under a header per value of it (sorting, filters and
  paging work inside the grouping). A table whose columns grow with the
  data (one column per modifier, per HP level, per seed) turns that
  dimension into rows instead and must offer it; other tables offer it on
  their categorical columns (a sequence's half or boss, a card's type or
  class, a file's player).
  - *Mutations:* modifiers become rows, never columns. Group by parent
    (one group per start, headed by the parent's row, and the official
    card's for mutated cards, then one row per modifier) or by modifier
    (one group per modifier, the parent first, one row per start). Each
    row shows each player's wins and mean HP (seed marks on hover as
    today) and opens that cell's fight on click. The "group" column is
    renamed **encounter type**.
  - *Boss replays:* group by sequence (one row per sequence, as today) or
    by HP (one group per entry HP level or "at arrival", one row per
    sequence with its boss, deck size and per-seed wins); a cell opens its
    fight.
- **Content: a table per kind**, each with its own columns, every column
  sortable (click a header; again to reverse), plus the search box and
  source filter:
  - cards: name, cost (numbers in order, then X, then Unplayable), type,
    class, keywords (Exhaust, Ethereal, Retain, Innate), source, text;
  - monsters: name, HP range, moves, start powers, source;
  - powers: name, buff or debuff, source, text;
  - encounters: name, type (hallway, elite, boss), monsters, source.
- **Card text in the game's own words.**
  - Head: `Name · N Cost · [Rarity · Class ·] Type`, with the floating dot
    as separator. Cost reads `X Cost` for an X-cost card and `Unplayable`
    for an unplayable one. Rarity and class show only when relevant:
    class for class cards (not Colorless or Status); rarity once the
    content carries it (today's content files have no rarity, so none
    shows).
  - Effects are written the way the game writes them: no explanations in
    parentheses ("X times", "lose 2 HP"), and keywords stay keywords
    (Vulnerable, Weak, Exhaust, Ethereal), never replaced by their full
    description. The same applies to move and power text.
  - Keyword hover (a keyword's meaning on hover) is not built (owner:
    probably excessive); kept as an idea.
- **Monster hover card.** A divider separates the move set from the pick
  rules. All pick rules show, Hexaghost's 17 included; no rule count
  stands in for them.
- **Hover card behaviour.** The card stays open while the pointer is over
  the element or the card itself (a short grace period covers the gap
  between them), so its text can be selected; it closes when the pointer
  leaves both. A card taller than about two thirds of the window shows
  what fits and a "show all" control that opens a modal with the whole
  text (closed by Esc, its close button or a click outside).

### Verification (added; fails on today's code where it tests behaviour)

- `explore_mutate_grouping`: `/api/mutate` with `group=parent` and
  `group=modifier` returns groups whose rows are modifiers or starts, with
  the same per-row numbers as today's cells; the response names the
  column "encounter type".
- `explore_boss_grouping`: `group=hp` returns one group per level, rows
  per sequence, numbers equal today's grid.
- `explore_content_tables`: each kind's rows carry its own columns; cost
  sorts as numbers, then X, then Unplayable.
- `explore_card_text`: Whirlwind's head is "Whirlwind · X Cost · Ironclad ·
  Attack"; Burn's is "Burn · Unplayable · Status"; no card, move or power
  text contains "(" ; Bash's text names "Vulnerable" without its meaning.
- `explore_describe` still holds; Hexaghost's monster text lists all its
  rules after a divider entry.
- Browser: mutations both ways, boss replays by HP, each content table
  sorted by a column, a card's hover card, Hexaghost's hover card with
  "show all" and its modal, text selected inside a hover card.

### Build steps

A7. **Group by:** the shared mechanism, mutations and boss replays with
    their dimension as rows, group-by on the other tables' categorical
    columns, the "encounter type" rename. Check: `explore_mutate_grouping`,
    `explore_boss_grouping`, browser (every list table offers it).
A8. **Content tables per kind.** Check: `explore_content_tables`, browser.
A9. **Card, move and power text** in the game's words, the card head.
    Check: `explore_card_text`, `explore_describe`.
A10. **Hover card:** divider, all rules, stays open over the card, "show
    all" modal. Check: browser (text selected, modal opened and closed).

## Amendment 4 (2026-11-08) · built a4b7f6e

Corrects Amendment 3's group-by (owner): a grouped table headed each group
with its bare value in a faint row ("0 · 37 rows"), and nothing showed
which groups exist, so grouping looked like it did nothing.

- **Group headers say what they group.** Each header names the grouping
  and the value ("cost: 0", "set: train", "entry HP: 40"), with the
  group's row count, styled to stand out from data rows (accent edge,
  larger text). A group whose label already says what it is (a mutation
  start's "seq 0 · floor 6 · ...") keeps it, prefixed by the grouping's
  name.
- **Jump to any group.** Above a grouped table, a bar lists every group
  with its row count; clicking one scrolls to its header, turning the
  page first when the group starts on another page. With more than 24
  groups the bar is a "Jump to" dropdown instead of a row of buttons.
- The server tells each group the page its first row is on
  (`groups[].page` from `group_page`).

### Verification

- `explore_group_pages`: `group_page` gives each group the page of its
  first row; with groups spanning pages, every group's first row is on
  the page it names.
- Browser: cards by cost, sequences by set (paged) and mutations by
  start: headers read "cost: 0" etc.; a jump scrolls to the group, and a
  jump to a group on a later page opens that page at its header.

### Build steps

A11. **Group headers and jump bar.** Check: `explore_group_pages`,
     browser.

## Amendment 5 (2026-11-08) · built 8b4f278

The owner's correction: a long table's column headers scrolled away.

- **Sticky column headers.** Every list table's header row stays in view
  just below the top bar while the page scrolls past it; a grouped
  table's jump bar stays with it, so any group can be reached from
  anywhere in the table. Tables scroll with the page, not inside a box of
  their own; a table wider than its card widens the page instead of
  hiding columns behind a scrollbar of its own.
- **Check:** browser: scrolled deep into the cards table and a gauntlet
  sequence list, the header row (and the jump bar when grouped) sits
  just under the top bar, at the window's normal and narrow widths.

A12. **Sticky headers.** Check: the browser check above.

## Amendment 6 (2026-11-08) · built e02e19e

The owner's correction: every table with a group-by offers "nothing".

- **Mutations:** "nothing" lists one row per (start, modifier): the
  start's columns, then the modifier, then each player's results, sorted
  by any column and paged. Grouping by start stays the default.
- **Boss replays:** the ungrouped view (one row per sequence, a column
  per entry HP) is labelled "nothing" instead of "sequence".
- **Check:** `explore_mutate_grouping`: `by=none` returns every row of
  the grouped views, ungrouped, with the same per-row numbers; sorted by
  a player's wins it stays sorted across the whole list. Browser: both
  tables offer "nothing" first.

A13. **Nothing grouping.** Check: `explore_mutate_grouping`, browser.

## Amendment 7 (2026-11-09) · built b338406

The owner's correction: an HP bar's size must not change when block,
powers or the HP number change, since a resized bar reads as HP gained or
lost.

- Every HP bar on the board (yours and each monster's) has a fixed width;
  only its fill moves. The HP number beside it has a fixed width too
  (tabular digits), so "8/80" and "80/80" leave the bar where it is.
- **Check:** browser: the bar's width is the same with and without block
  and powers, and at one- and two-digit HP.

A14. **Fixed HP bars.** Check: the browser check above.

## Amendment 8 (2026-11-09) · built 95a0c23

Corrects Amendment 7 (owner): a fixed 200px bar is too short. Your HP bar
fills the first line of your panel (after "You" and before the HP
number), and energy, block, powers and the fight's result go on a second
line, so nothing beside the bar can resize it. Monster bars fill their
card's width again; their block, intent and powers were already on their
own line. The HP numbers keep fixed-width digits.

- **Check:** browser: your bar is as wide as the panel allows and keeps
  its width with and without block and powers, at one- and two-digit HP.

A15. **HP bar on its own line.** Check: the browser check above.
