# Manager archive

History moved out of `docs/manager.md` (run 10:03 2026-10-31) to keep
that file short. Nothing here is current state.

## Running, as of 08:35 2026-10-31


- **Job runner** live since 12:25 2026-10-30 (`jobs/runner.pid`,
  started detached; output `logs/jobs/runner.out`). Check
  `.venv/Scripts/python scripts/jobs.py status` each run; restart it if
  its pid is dead (see "Each manager run" 5). It still runs `jobs.py` from
  before dd3fad8: write `python.exe`, not `python`, in job commands until
  it is restarted (do it when no job runs; it adopts running jobs anyway).
- 0016-0039 done and read. 0038/0039 (fallback and guard players): depth-pilot
  doc "Fallback and guard players". Old `.pyd` deleted.
- 0041b (round-0 scores), 0041c (Demon Form probe), 0044b (net-leaf fallback, held-out), 0042-0044 + 0044c (lean-thr, results doc "Threshold rows") done and read.
- **Registry-lite merged** into main 05:50 (0e0046a, 7 commits, review
  clean after one test fix); `sts` rebuilt (old `.pyd` deleted). Worktree and
  branch removed. Step 6 result files copied to `results/gen_powers/`.
  Jobs started before 05:50 still run the old module (same behaviour with
  no pack).
- **Run 08:02 a2a020e7 (2026-10-31):**
  - **0049e (lean-distil-s1) is hung** (PID 24972 and its workers): its
    teacher's 6 worker processes ran out of memory (two-turn searches at
    cap 400k allocate up to 1.4 GB each, beside another job), and a dead
    `multiprocessing.Pool` worker loses its tasks, so it waits forever
    (last progress 1313/10000; log only "memory allocation ... failed").
    Ending it was refused by the permission check (For the owner). Until
    it ends it holds one of the two heavy slots: the queue runs one job at
    a time. Fixed in 75b16fe (teacher uses ProcessPoolExecutor, fails
    loudly; lean-distil configs at 3 teacher workers) and 48108eb (same
    for `depth_paired.py`).
  - 0049d (lean-rates-s201) died out of memory in r2 training at 07:18
    (same pressure); requeued as **0051a** (resumes after r1). Read
    lean-rates (Next D) when it ends.
  - Requeued distil s1 as **0052a** (3 teacher workers, mem 6 GB, est 180
    min) ahead of 0052b/0052c (same changes); 0057b now at 4 workers.
  - Gen arms: 0051b (control play), 0057a1-a6 (arms, ~45 min each).
- **Queued 02:30 by run 02:07:** 0044b / 0057b, two-turn **net-leaf**
  fallback vs one-turn net (champion r2 s1) on held-out / train elite+boss
  at cap 400k (Next C, ~2-4 h each, silent while playing; silence-min 400).
  Outputs `results/depth/paired-net-{held_out,train}-cap400k-fallback.json`.
  Read per encounter with override (= disagreement) share; compare with the
  cap-50k plain net-leaf run (-0.010 held-out, boss -0.064, 23% cuts).
  Two-turn net >= +0.02 on a half -> spec distilling two-turn values into
  the net (review direction 3); under that on both -> depth stays a
  boss-only test-time option.
- **Queued 00:40 by run 00:07** (behind 0039; all on the merged layout):
  - 0040 / 0041: `test_curriculum`, `test_rounds` on merged main (expect
    26 / 12 passed). A failure blocks reading 0042+.
  - 0041b-score-r0 (Next A; renamed in `jobs/pending` to sort before
    0042): the night r0 and nine cover r0 nets on tight2, saved to
    `results/r0-scores/`. Read: `score_r0.py read cover4 cover10 cover21`
    (r0 vs r1 per arm); the night r0 against lean r1 by hand. Then queue
    `score_r0.py play runs/*-data*-r0-*` once data scaling ends.
  - 0042-0044: `lean-thr-s{1,101,201}` (threshold-rows step 5), reuse the
    night round 0. Read per step 6 of the spec: paired against `lean-s*`
    r2 on `tight_bosses` per boss and half (held-out Guardian, baseline
    -0.131, MDE ~0.06) and tight2 per fight type, slime encounters apart.
  - 0045-0057: data scaling (`docs/specs/data-scaling.md`): data5k x5,
    data20k x5, data40k x3, fresh round 0s, judged at r1. Read with
    `scripts/analysis/coverage_read.py data5k data20k data40k cover21`.
    data5k vs cover21 (old layout) is also the layout check (~0.01).
    Note minutes per run; 40k jobs ask 6 GB.
  - 0058-0060: `lean-look-s{1,101,201}` (lookahead step 5, merged a57f338),
    against lean-thr r2 per the spec's adoption rule; compare round
    minutes too (encoder ~2.9x slower with lookahead on).

## Next: older ranking and items 0-9 (2026-10-30)

Older ranking (2026-10-30, `docs/research/big-picture-2026-10-30.md`): Rules from it, for every item: report results
by fight type (hallway / elite / boss) and keep the train half (strength)
apart from the held-out gap (generalisation); state each experiment's
minimum detectable effect (MDE ~ 2.8 x seed sd x sqrt(2/seeds); seed sd
on Ironclad is 0.0066 / 0.0076 for all cells but elite 0.017 / 0.019 and
boss 0.022 / 0.025, train / held-out) before running it; never call a
single-seed pass a result.

0. Done: the zero-CPU analyses are in the review doc's addendum (679350a;
   scripts in `scripts/analysis/`). They set item 3's parameters, add a
   low-HP-start slice to item 5, and make item 6's next experiment
   generated one-primitive card variants judged on Silent transfer. Also:
   check the boss lead against two-turn search (item 4) before claiming
   it as learned strength; old baseline nets beat the heuristic on
   bosses too.
1. **Warm start**: done. Gate FAIL: effects features beat ids only
   zero-shot; warm beats fresh in play with no forgetting; equal MSE hid
   a +0.05 win lead (results doc "Warm start on Silent"; ideas #70, #71).
2. **Job queue**: built and live (README "Job queue"). Left: a small
   test-size profile for the slow suites (ideas#69).
3. **Champion ladder with SPRT**: spec `docs/specs/champion-ladder.md`
   (confirmed 17:40); steps 1-2 built (6f927d6: `scripts/ladder.py`,
   `test_ladder.py` 9 passed, README "Champion ladder"; review's one
   must-fix, an unpinned held-out floor, fixed). Step 3 queued (0020-0022): `ladder.py test` r2 s1 vs heuristic, then r2 s101 and r2
   s201 vs the champion. Step 3 done (results doc "Champion ladder"):
   r2 s1 is champion (+0.037 vs heuristic, held-out only +0.011); its
   seed twins fail against it. Next: rung-4 B, the best lean r2 net, an
   ensemble evaluator (its own small spec), and the two-turn heuristic
   as a ladder entrant once the guarded player is settled.
4. **Depth and ceiling**: net leaves (0009/0010) -0.010 held-out /
   +0.013 train, below the 0.02 bar; Sentries at k 16 *worse* (-0.229)
   than k 4 (-0.167), which led to a real fault: at the 50k node cap the
   depth-first tree scores late options as mid-turn-1 states and picks
   them (depth-pilot doc, "the node-cap bias"). Every two-turn number so
   far is biased. **Cap-400k reruns done (0017/0018): two-turn heuristic
   beats one-turn +0.056 (se 0.014) train, +0.016 held-out; bosses
   +0.09-0.10 both halves** (depth-pilot doc). Depth stays. Queued: the
   Python fallback and guard players on held-out (0038/0039). Then the real fix
   (fallback to one-turn on a cut) and, if depth then leads by >= 0.02 on
   a half, the amplifier spec; else drop depth and do the ceiling check.
   **Before dropping depth, try the guarded override** from
   `docs/research/unseen-mechanics.md` (Hallak et al.'s BCTS): keep the
   one-turn choice unless two-turn prefers another option by > margin m;
   sweep m. `sts.search` already returns `options` with values, so it
   needs no rebuild (Python wrapper in `depth_paired.py`). Max over noisy
   leaf values is the likely cause of the loss left after the cap fix.
5. **Lean loop**: done (results doc "Lean loop", 4505474): no solve step
   is within ~1 se of the seed check; experiments use the lean configs,
   defaults unchanged (decisions "Lean recipe for experiments"). Low-HP
   slice: no held-out effect. Left: ladder-test the best lean r2 net
   (lean-lowhp s1 or s101; read per-seed leads with
   `scripts/analysis/lean_read.py`).
6. **Goal 1 by mechanics**: coverage pilot read (results doc "Coverage
   pilot"): held-out lead -0.074 / -0.039 / -0.025 at 4 / 10 / 21 kinds,
   falling returns, both halves alike. Generated content moved ahead of the
   fidelity specs (`docs/specs/queue.md`, decisions "Coverage pilot read").
   **6a. Data scaling first** (queued 0045-0057): lean at 20k led cover21
   at 5k by ~0.03, more than 10 -> 21 kinds. Its result sets the round-0
   size for every later experiment. If 20k > 5k and 40k > 20k, consider an
   80k arm (memory permitting) before anything else. **6b. Then** write a
   minimal runtime-registry + generated-cards spec (new mechanics in the
   generator), CPU-light, can start any time. Also: make the
   primitive-response probe a standing metric; the CPU-minutes-to-recover
   Guardian metric once lean-thr is read.
   **Methods note:** seed sd with fresh round 0s is ~0.014-0.017, about 2x
   the shared-round-0 figure the MDE rule above uses. Use the bigger sd
   whenever arms differ in round 0.
7. **The other two Act-1 bosses**: merged, calibrated (`tight_bosses`,
   dfe04b8) and measured (results doc "Boss lead per boss"): unseen bosses
   +0.07 on train cards, but **-0.131 Guardian / -0.042 Hexaghost on
   held-out cards** (unseen boss x unseen cards compounds; lead rises with
   start HP). Next goal-1 step from it: give Mode Shift (and Burn's
   turn-end damage) a feature, then check whether a net's value sees the
   shift coming. **Spec confirmed 22:35** (`docs/specs/threshold-and-held-rows.md`,
   83637be): general `threshold` rows (Mode Shift and the slimes' split)
   and `held` rows (Burn); steps 0-4 building in worktree branch
   `threshold-rows`: **merged 00:30 2026-10-31 (ad17de2), sts rebuilt;
   step 5 queued (0042-0044, after the slow suites 0040/0041)**; reuse of
   the night round 0 decided (decisions "Threshold rows step 5"). History:
   steps 0-4 built and reviewed (no must-fix; saved
   nets bit-identical on 5 real nets, fingerprint unchanged, encoder
   within 5%), rebased on main, pushed as branch `threshold-rows`;
   worktree `.claude/worktrees/agent-a2c8134c6563853c5` (own venv).
   **Merge only after 0037 ends** (the coverage pilot must finish on one
   feature layout; the merged registry keys caches by layout and slime
   states gain rows). Then: `git merge --ff-only threshold-rows`, rebuild
   main's `sts` with the rename-aside trick (0038/0039 hold it; they use
   the heuristic, so the new build doesn't affect them), queue
   `test_curriculum` and `test_rounds`, remove the worktree. Step 5's
   open question (reviewer): `--round0` reuses the old-layout round-0 net;
   check in `learn.py` whether r1 warm-starts from it. If it does, the
   lean-thr arm needs a fresh round 0 and so does a matching control
   (control must come from a pre-merge build or a switch); decide under
   the Away rules and write it in decisions.md. Then step 6; and report `tight_bosses` in every goal-1 result. Needs a rebuilt `sts`: build it in a gap in the queue (hold the runner: queue nothing that imports `sts` behind it), or in a worktree with its own venv.
7b. **Monster lookahead columns**: **built and merged a57f338** (review
   clean; fast suites pass; off is bit-identical; on, the encoder is ~2.9x
   slower, over the spec's 25% budget: the engine's `move_distribution`
   lookup, a rules file, so not optimised; decisions "Monster lookahead as
   built"). Test queued 0058-0060. Spec confirmed 00:30 2026-10-31
   (`docs/specs/monster-lookahead.md`, off by default behind a `lookahead`
   option, so pins and queued runs stay bit-identical; test `lean-look-s*`
   vs `lean-thr-s*`, ~3 x 50 min). Build next (code is CPU-light; its test
   queues behind data scaling). Open: encoder budget when on (25%, a
   guess), and check the feature-cache key covers the option. (Owner asked 2026-10-30 to move enemy
   patterns up; `docs/research/monster-patterns-2026-10-30.md`). Nets
   have no kind and no future moves, but on trained enemies they read
   the kind from max HP, powers and intent, and their value isn't fooled
   before big hits; the cost shows on held-out cards and unseen bosses,
   and at End-turn leaves where random-AI monsters haven't rolled (Jaw
   Worm, slimes, lice, Nob: 78-100% of leaves show the stale move). Not
   kind ids, not full spec 9: per-monster expected effects of the next 1
   and 2 moves plus the 4-move damage rate, from `move_distribution`, in
   `agent.rs` / `features.rs` (outside the fingerprinted files). Spec it
   now (CPU-light); build after threshold-rows merges (both edit
   `features.rs`); test against step 5's lean-thr arm, 3 seeds, design
   and decision rule in the doc (~15-17 thread-hours).
8. **Act-1 gauntlet** as goal 2's metric: hallway fights, elites and a
   random one of the three bosses in sequence with HP carried over,
   paired against the champion. Needs item 7.
9. Later: relics (as hooks and static modifiers), then the run layer
   (rewards, rest sites, shops, pathing). Relics spec is fine CPU-light
   work when nothing above is.


## Log, 2026-10-29 to 2026-10-31 00:00

- 2026-10-29 14:00 setup session: owner left the project to Claude; this
  file and the `sts-manager` task (every 2 h) set up.
- 2026-10-29 14:00 first sts-manager run: confirmed and committed the seed
  check spec (b076af5); cut short.
- 2026-10-29 setup session: owner says machine speed is the
  limit; added "Machine time is the bottleneck". Lock cleared.
- 2026-10-29 21:10-21:50 sts-manager b45116cb:
  Built seed check steps 1-2 (8837c83), started the run; confirmed the
  contract spec after a code check (8ff0ca0); label defaults reverted
  (uncommitted, tests pending).
- 2026-10-29 22:07-23:08 sts-manager (scheduled): took the free lock, waited on the seed check (CPU full); heartbeat lapsed while waiting, b45116cb retook it 23:06, so this run stood down.
- 2026-10-30 02:08-02:35 sts-manager d4bf197e: Took a lapsed lock (heartbeat 00:55, session idle) and forked contract step 3; b9fced62's fork was in fact alive and committed it (d9e5d7b), so the duplicate fork undid its own commit and this run gave the lock back. Added the fork check to "Each manager run" step 1.
- 2026-10-30 04:08 sts-manager (scheduled): lock held by b9fced62 (heartbeat 03:32, 36 min), stood down. `test_sweep.py` (PID 4968) alive at ~1 core, log unchanged since 02:35.
- 2026-10-30 06:06-07:05 sts-manager a16f0611: Took b9fced62's lapsed lock. Found `test_sweep.py` hung 4 h in a fight a weak net stalls forever; added a 100-turn play limit (341a00c), tested on the contract worktree's own build (Rust, contract suite, test_sweep 29 passed); merged contract + turn limit (f06e19e) and committed the label settings (352a338); rebuilt main's `sts` past the lock.
- 2026-10-30 07:37 a16f0611 (woken by its tests, no lock): `test_curriculum` 26 passed (485 s) and `test_rounds` 12 passed (2208 s) on merged main; the contract merge holds.
- 2026-10-30 08:08-09:45 sts-manager 3edd4057: Finished and confirmed the warm-start spec (48d6edd), built steps 1-4 with a review fix (ee25335..3e67cfd); started the Silent calibration (step 1's long run); `test_sweep.py` 29 passed on main (13d3b00, 2089 s), closing b45116cb's gap. Hung test processes gone (b45116cb stopped them).
- 2026-10-30 10:08-11:15 sts-manager f743248c: Took 3edd4057's lapsed lock. Removed the merged worktrees `contract` and `agent-a3262c38` with their branches. Added stall counts to curve and learn (653dbfa; test_curve 7 passed). The calibration ended 11:04 (176 cells). 3edd4057 woke from its own watcher, committed the set and started curve A; I stopped my duplicate timing cell, started curve B and told 3edd4057 to start nothing else.
- 2026-10-30 11:20-12:00 setup session bc0daa80: owner said progress is
  too slow and asked for data analysis and big-picture thinking. Ran the
  big-picture review (6 lenses, synthesis, 2 skeptics per claim), wrote
  `docs/research/big-picture-2026-10-30.md`, re-ranked Next, added
  "Big-picture reviews" and the analysis rule to the run protocol, saved
  the review as a workflow. Zero-CPU analyses running (Next 0).
- 2026-10-30 12:07-12:35 sts-manager local_10dd1a9a: CPU full (curve A+B, item-0 probe). Built Next 2, the job queue (spec 22f749b, 980f736, review fixes f37823a, folded 32b90a3): `scripts/jobs.py`, test_jobs 13 passed, runner live, end-to-end ok. The live run caught a crash on a relative program path that the reviewer had also flagged. Idea #69 (test-size profile). Depth pilot: two-turn search as built loses to one-turn (docs/research/depth-pilot-2026-10-30.md); Next 4 re-shaped to fix sampling and the node cap first.
- 2026-10-30 12:35-13:05 local_10dd1a9a (same run): curve sessions handed Next 1 over; wrote the warm-start results and decision (cb4cf01), ran test_curriculum (26) and test_rounds (12) through the queue, folded the spec (d1e24bf). Lock released; CPU idle, Next 4 first.
- 2026-10-30 16:06-17:25 sts-manager (scheduled, took the 14:07 run's lapsed lock): Read the full depth test (9d5023b: two-turn loses on heuristic leaves; Nob up, Sentries down); queued net-leaf and k-16 follow-ups (0009-0011). Merged the bosses branch, rebuilt, re-pinned (776f910); fast suites pass but test_bounds (empty current DB version, ideas#72). Spec tight-bosses (01a77cd) and step 1 (6269ec8); calibration queued (0012). Removed the merged worktree.
- 2026-10-30 17:33-18:15 sts-manager (scheduled): took the free lock. Tight-bosses step 2 pinned (dfe04b8) and step 3 read (7e73c4d: unseen bosses +0.07 train, Guardian -0.13 held-out). Depth: net leaves below bar; k16 worse led to the node-cap bias in two-turn search (03ead08); cap-400k reruns queued (0016-0018). Curriculum pin re-pinned after an additivity check (0019 to confirm). Champion ladder spec + build (2fecde9, 6f927d6); first tests queued (0020-0022).
- 2026-10-30 18:04-18:30 sts-manager (scheduled): took the free lock. Lean-loop spec + build (2da247b: low-HP slice, `--round0`, six configs, queued 0023-0028); coverage-pilot spec + build (9d0bfc6: `train_pool`, nine configs, queued 0029-0037); smoke run of both keys ok. Read 0016: Sentries two-turn at cap 400k -0.080 (se 0.029) vs -0.229 at 50k (b6b44b7). Mode Shift feature (Next 7) left: needs a rebuild while the queue holds `sts` for ~10 h.
- 2026-10-30 20:05-20:25 sts-manager (scheduled): took the free lock. 0017/0018 flagged STALLED but computing (silent two-turn pass, ~3-4 h at cap 400k), so the queue waits behind them. Ran an away-mode prior-art scan on unseen mechanics and depth pathology (5 scouts, 40 papers, 7 verified): `docs/research/unseen-mechanics.md`; guarded two-turn override added to Next 4.
- 2026-10-30 22:08-23:40 sts-manager 054eaf8f: took the free lock. Read depth cap 400k (two-turn +0.056 train, +0.016 held-out: depth stays), ladder 0001-0003 (r2 s1 champion), lean loop (solve step not needed), curriculum pins (26 passed). Added Python fallback/guard players to depth_paired.py (match Rust 15/15), queued 0038/0039. Threshold-rows spec confirmed (83637be) and steps 0-4 built by a fork on branch `threshold-rows`, reviewed clean; merge after 0037. Big-picture review due after the coverage pilot (~03:00).

## docs/manager.md at the cut-over, 2026-11-03

The whole file as the last manager run left it, headings one level down.
The operating model (`docs/operating.md`) replaced it.

## Manager state (owner away)

Since 2026-10-29 the owner has stepped back for a few days and left the
project to Claude. A scheduled task (`sts-manager`, every 2 hours) wakes a
fresh session that reads this file, runs the project for a while, and
writes this file back. This file is the hand-over between those sessions:
keep it current, short and true.

### Goals (owner, 2026-10-29)

1. An AI that plays well on randomly generated content (cards, powers,
   enemies), with first-class support for custom content: a new character,
   a new mechanic, a new entity.
2. On that system, a Slay the Spire AI as dominant in its field as
   Stockfish is in chess.

Subgoals: add relics; widen the scope beyond combat toward the full game.

Scope note: the out-of-combat parts (map, rewards, rest sites, shops,
events) are built as a headless rules simulator for training and testing,
like the combat engine: no playable front end, art or game text. Playing
the real game, if we get there, goes through a mod bridge to the owner's
own copy. StS1 is not installed on the dev machine (owner, 2026-10-29), so
that waits for the owner.

### Standing grants (owner, 2026-10-29)

- **Decisions.** AGENTS.md's "ask before decisions that are expensive to
  reverse" now means: decide, record it in `docs/decisions.md` marked
  "(owner away)" with the alternatives, prefer the reversible option, and
  list it under "For the owner" below. Spec confirmation is yours too.
- **Push.** Push finished commits on `main` to `origin` with a plain
  `git push`. Never force-push or rewrite history.
- **Disk.** When it runs low, delete only rebuildable files: caches, data a script regenerates,
  finished worktrees. Never `db/` databases, `models/`, `results/` or
  anything a commit references. Below 8 GB free, start no new run that
  writes much.
- Not granted: deleting non-rebuildable data, git history rewrites,
  spending money, system or security settings, anything outside this repo
  except `~/.claude` memory and the ideas issues (label
  `project:sts-for-ai`; adding and commenting is fine).

### Machine time is the bottleneck (owner, 2026-10-29)

CPU time is the scarce resource. The owner spends about half their
time waiting for training runs inside tests to finish. So:
- Keep the CPU busy with the most valuable run at all times. Have the
  next run ready before the current one ends.
- While a heavy run goes, do work that needs little CPU:
  specs, code, reviews, analysis of finished results, research, the
  next run's preparation. Hold back test suites that train nets until
  the CPU is free.
- Make runs cheaper: shrink slow tests (smaller fixtures, separate a fast
  suite from the slow one), take the exact-solver step out of training
  rounds (~70% of a round). Play and inference speed are already done
  (`perf`, `rust-inference` merged); self-play and tight fights are a
  small share of a round now.
- Before a run, check it can decide something: training-seed luck has
  sd ~0.010 train / ~0.013 held-out on tight2 (pooled over 66 runs,
  review 2026-10-31b; the old 0.006-0.0075 came from one shared-draw
  group). MDE = 2.8 x sd x sqrt(2/seeds), ~0.02-0.03 at 3 seeds, smaller
  only when arms share data (pairing corr 0.8-0.99 for data/rates arms).
  A run whose expected effect is below its MDE doesn't run.

### Training: when it runs and when it stops (owner, 2026-11-02)

Every gauntlet gain since 10-29 came from search or the run layer; more
of the same training plateaued after one self-play round (approach review
2026-11-02). So (decisions "Training: when it runs and when it stops"):
- A training job runs only when the net has something new to learn: a
  stronger teacher (games from the two-turn product), inputs it can't see
  today (a new layout, the survival histogram), or new content. Anything
  else doesn't get CPU. It is judged on the gauntlet protocol.
- It stops at the plateau. After each round, play its net on the one-turn
  cell gauntlet (500 sequences) and read it `--against` the file of the
  net from two rounds back with `--d1 4`: a pass (the two rounds gained
  more than about 2 HP) trains another round, a fail stops. Optional free
  pre-screen: if the new net changes far fewer picks on
  `data/bench/decisions.json` than round 0 -> 1 did, stop without
  playing (this signal can stop training, never promote a net). For
  cheap fine-tune bursts, look three rounds back with `--d1 6`.
- Goal 1 is the exception in kind, not in rule: how few games a net
  needs to adapt to new content is the goal-1 number, so there a curve of
  games against retention is worth measuring.

### Machine limits

- No usable GPU (torch runs on CPU).
- At most two CPU-heavy jobs at once; cap their threads. Check CPU and
  free memory before starting one. Size memory to what's free, avoid
  paging.
- Windows locks a loaded `sts` module: no `maturin develop` while any
  Python process uses `sts`.
- pytest is not installed in `.venv` (checked 22:20 2026-11-02). Run the
  tests with the system interpreter over the venv's packages:
  `PYTHONPATH=.venv/Lib/site-packages <system python>
  -m pytest -q -p no:cacheprovider scripts/tests/<file>` (Bash).

### Each manager run

1. **Lock.** Read "Active manager" below. If another session holds it,
   its heartbeat is under 45 minutes old, and `list_sessions` shows it
   running, don't start work. A session can show idle while its fork
   still works: also check for recent commits or file changes in its
   worktree (last 30 min) before calling it gone. If it's held, don't
   start work: check only for crashed runs and disk, add
   one line to the Log, and end. Otherwise write your session id and the
   time there, and refresh the heartbeat as you work (each commit or ~30
   min).
2. **Look.** `git log --oneline -15`, `git status`, running Python
   processes, `scripts/jobs.py status` (the job queue; README "Job
   queue"), background runs listed under "Running", new HANDOFF or
   NIGHT-REPORT files, and notifications (`ReadNotifications`). If the
   owner has written anything, their word wins over this file.
   Then `kb check` (the claims store, `docs/claims/`; STATUS.md at
   session start lists suspect facts): confirm, flag or re-set each
   suspect fact, source facts first.
3. Decide how much to start.
4. **Check results, then analyse them.** Anything finished: read it, and
   be suspicious. A result much better or worse than the last, a check
   that passes at exactly its bar, a number that disagrees with an
   earlier measurement, or a run far faster or slower than its estimate
   gets a look before anything is built on it (training luck has already
   faked two passes, see `docs/decisions.md`). Pass/fail is not enough:
   dig into the raw outputs (per encounter, per HP band, per decision
   kind, stalls, timing) for what the result says about *why*, and write
   that into the results doc. Ask what the result changes about the
   plan, not only whether the step passed.
   **Shadow mode (kb adoption stage 3, from 2026-11-02; spec
   `docs/specs/kb-adoption.md`):** record each read as `kb set
   measurement/<name> "<value>" --from <results-doc section as
   path#heading> <results file> jobs/done/<id>.json key:product/net
   key:yardstick/<...>` (all sources after one `--from`), each decision
   as `kb set decision/<name> ... --from "docs/decisions.md#<heading>"`,
   and re-set or retire facts a result changes. Before working a fact out
   from files, `kb find <words>`. Promote a player only with
   `scripts/product.py set` (registry `configs/product.json`, fact
   `product/net`; `results/ladder/champion.json` is the tight2 ladder's).
   Keep writing this file as before; stage 4 moves it over later.
5. **Work.** Take the top item of "Next" that isn't blocked. Follow the
   owner's workflow by reading the skill files directly (they can't be
   invoked by the model): `~/.claude/skills/spec/SKILL.md`, then
   `~/.claude/skills/build/SKILL.md` with its **Away rules** (section 5),
   `~/.claude/skills/handoff/SKILL.md` for hand-overs. Answer the
   interview questions yourself, as the owner would from AGENTS.md, the
   memory notes and this file. Use subagents, forks and workflows freely
   for independent parts. Long runs go through the job queue, not by
   hand: `jobs.py add --threads N --estimate-min M [--lane L] -- <cmd>`,
   with what to check written under "Running". Keep the next job queued
   before the current one ends. The queue's commands (README "Job queue"):
   - Order: `first <id>` starts a job next (no renaming); lanes and their
     shares are in `jobs/lanes.json`.
   - Conditions instead of notes and `bash -c "A && B"`: `--after a,b`,
     `--if-passed a,b` (with `--check "cmd"` on the job whose result
     decides), `--on-fail park|cancel`; `set <id>` changes a pending job,
     `unpark <id>` and `verdict <id> pass|fail` handle a parked chain.
   - Pinning: `add` pins to HEAD by default and refuses with uncommitted
     scripts, engine or configs (commit, or `--unpinned` for jobs that
     write tracked files or new files in `data/`). Before a swap, merge or
     landing, run `jobs.py impact sts|scripts` and record the result.
     `pins` lists snapshots; only `unpin` or the runner's 24 h sweep
     removes one.
   If `jobs/runner.pid` names a dead process, restart the runner detached
   (PowerShell `Start-Process .venv\Scripts\python.exe -ArgumentList
   '-u','scripts/jobs.py','run' -WindowStyle Hidden
   -RedirectStandardOutput logs/jobs/runner.out`); it adopts running jobs
   and still records their exit codes. To be woken by a job, run
   `jobs.py wait` in the background.
6. **Context.** When your context passes ~50%, or the next step is big,
   finish the current step, write the hand-over into this file (and a
   HANDOFF file if needed), and end. The next wake-up continues.
7. **Close.** Update this file (Active manager cleared or refreshed,
   Running, Next, Log line), commit only finished work plus this file, and
   push.

### Big-picture reviews (owner, 2026-10-30)

The owner found progress too slow and asked for more data analysis, big
picture reviews and abstract thinking, not only building the next spec.
So, besides the steps above:
- **Every ~24 hours, and after any major result,** run the saved
  workflow `big-picture-review` (in `.claude/workflows/`; the owner asked
  for it, so run it by name). It reads the data and docs through several
  lenses, synthesises, and has skeptics check the key claims. Write the
  outcome to `docs/research/big-picture-<date>.md` and re-rank "Next"
  from it. The newest such file outranks the queue's order.
- **Before starting any spec,** say in one paragraph in the spec how it
  moves goal 1 or goal 2 and how we'll know; if you can't, don't build it.
- **Idle thinking time is wasted capacity.** CPU-light thinking
  (analysis of existing data, prior-art research, design reviews,
  experiment design) can always run in parallel with a CPU-heavy run.


### Directions (keep looking for new ones)

The current picture and ranked directions are in the newest
`docs/research/big-picture-<date>.md` (first: 2026-10-30). In short: the
nets beat the heuristic on elites and bosses with training cards; nothing
is shown yet on unseen content, where new mechanics, not new cards, are
what hurts; the loop's teacher is no stronger than its student; label work
at one-turn depth is used up. Ideas not yet in "Next": an outside
yardstick (known StS bots, or the real game through a mod bridge once the
owner installs it); run-level play (card rewards, removal, rest sites);
a prior-art scan on game AI for stochastic card games with hidden draw
order (`~/.claude/skills/prior-art`).

### For the owner

Decisions made while away, and anything that needs you. Newest last.

- (owner away) Label-settings defaults back to the 10-28 night's; see
  docs/decisions.md "Label settings back to the night's".
- (owner away) Contract spec confirmed with changes (pre-contract nets
  load through a converted file beside them); docs/decisions.md.

- (owner away) A combat still running after 100 turns now ends as a
  loss in play (not in the solver); docs/decisions.md "Play turn limit".
  Found because a weak net stalled a fight forever and hung a test.
- (owner away) Warm-start spec confirmed with changes from the draft:
  parents are the generalise pair, not s1 r10 (no ids curriculum twin
  exists); widening uses the new vocabulary's natural column order;
  docs/decisions.md "Warm-start spec confirmed".
- (owner away) 2026-10-30 big-picture review re-ranked the work
  (`docs/research/big-picture-2026-10-30.md`): label and curriculum
  variants at one-turn depth stop; measurement (results by fight type, a
  champion ladder with sequential tests), search depth, a job queue and a
  lean loop come first; the rules-engine series waits behind them. The
  equal-weight held-out gate is no longer the only verdict.
- (owner away) Job queue built: managers queue long runs and a runner
  starts them when cores and memory are free; docs/decisions.md "Job
  queue spec confirmed" and "as built".
- (owner away) Depth: with the heuristic scoring the leaves, two-turn search
  loses to one-turn (-0.048 held-out, 0.000 train); the earlier +0.15
  pilot was a Gremlin-Nob-heavy sample. Net leaves and more samples are
  being tested before depth is dropped (depth-pilot doc).
- (owner away) Bosses merged (Hexaghost, The Guardian, Burn); feature
  fixtures re-pinned after checking the change is additive. Two gaps:
  effects nets can't see Mode Shift or Burn's turn-end damage; and the
  solved database's 2.43M rows sit under the old rules fingerprint, so
  `test_bounds` fails until it refills (ideas#72 proposes carrying
  rows over on additive changes). docs/decisions.md "Act-1 bosses merged".

- (owner away) Two-turn search's node cap was biasing it: options reached
  after the cap are scored mid-turn and get picked, so all depth results so
  far understate depth; reruns at a bigger cap are queued. One-turn play is
  unaffected. docs/decisions.md "Two-turn search: the node cap".
- (owner away) Champion ladder spec confirmed and built (heuristic as the
  first champion); docs/decisions.md "Champion ladder spec confirmed".
- New goal-1 evidence: nets keep half their boss lead on unseen bosses with
  training cards, but lose clearly (Guardian -0.13) when unseen bosses meet
  unseen cards (results doc "Boss lead per boss").

- (owner away) Two cheap experiments confirmed and queued: the lean loop
  (no solve step, with and without a low-HP start slice) and a coverage
  pilot (held-out play against 4 / 10 / 21 training card kinds), which
  decides whether generated content jumps the queue; docs/decisions.md
  "Lean loop spec confirmed", "Coverage pilot spec confirmed".
- Depth update: at a bigger node cap two-turn search on held-out Sentries
  loses -0.080 instead of -0.229; the cap bias was most of the loss, but
  not all (depth-pilot doc).

- Prior-art scan "playing well on unseen mechanics"
  (`docs/research/unseen-mechanics.md`): no method handles a genuinely new
  primitive zero-shot, so custom mechanics will need a feature plus a
  short adaptation burst; and tree search over noisy values is known to
  lose to the plain policy (fix: penalise overriding it), which fits our
  two-turn loss. Two framings listed for you, not adopted.

- Depth is back: at a node cap of 400k, two-turn search with the heuristic
  beats one-turn by +0.056 (se 0.014) on train elites and bosses, level on
  held-out; bosses +0.09 on both halves. Guarded variants queued
  (decisions "Depth stays").
- (owner away) Lean recipe: no solve step loses at most ~0.01-0.02 (not
  detected); experiments use it, defaults unchanged.
- (owner away) Threshold-rows spec confirmed and built on a branch:
  Mode Shift and the slimes' split share one general feature, so slimes
  in training might teach the Guardian zero-shot. Merge waits for the
  coverage pilot to end.

- (owner away) Coverage pilot: held-out play improves with training card
  kinds (4 / 10 / 21), with falling returns, so generated content moves
  ahead of the fidelity specs. Round-0 data size looks like a bigger lever
  (~+0.03 from 5k to 20k games); a data-scaling run (13 jobs) is queued.
  Also: all our seed-sd figures came from runs sharing one round-0 net;
  with fresh round 0s the sd is about twice as big. Decisions "Coverage
  pilot read", "Data scaling spec confirmed".
- (owner away) threshold-rows merged into main; monster-lookahead spec
  confirmed (off by default, so nothing re-pins).
- Big-picture review 2026-10-31 (`docs/research/big-picture-2026-10-31.md`):
  label-side work under one-turn search has never moved play; data,
  features and depth have. Next re-ranked: score round-0 nets, data
  scaling, a teacher check for depth, power features, generated power
  mechanics. Skeptics trimmed every claim; the doc keeps their verdicts.
- (owner away) Monster lookahead columns merged (off by default); with them
  on, feature encoding is ~2.9x slower; the test run will show whether
  rounds get slower too.
- (owner away) Depth: falling back to one-turn's choice where the two-turn
  tree cut (1% of decisions) gains +0.044 (se 0.011); two-turn heuristic
  search now beats one-turn by +0.061 on held-out elites and bosses (Slime
  Boss +0.165). A margin guard on top hurts (-0.14 on Slime Boss). The
  fallback player is the two-turn player from now on (decisions "Two-turn
  player: fallback"); net-leaf runs of it queued as the teacher check.

- (owner away) Rounds stay: scoring the round-0 nets shows round 1 beats
  round 0 by about +0.017 on both halves (~2.5 se over 9 runs).
- Demon Form probe: on held-out boss fights the heuristic plays Demon Form
  in 65% of fights, the r2 nets in 12-17%; the nets value it 0.09-0.15
  below their best other option and lose Hexaghost 0.07-0.11 vs the
  heuristic's 0.54. The nets see the mechanic but don't price it, so a
  rate-features spec (each power's worth per turn as columns, off by
  default) is confirmed and builds after registry-lite (decisions "Rate
  features spec confirmed").
- (owner away) Threshold rows (Mode Shift / slime split as one row kind)
  showed no transfer to the held-out Guardian: +0.038 vs the 0.06 bar,
  inside training luck; everything else within noise. The layout stays
  (decisions "Threshold rows: no transfer detected").
- (owner away) Registry-lite spec confirmed and built on branch
  `registry-lite` (steps 0-5): generated powers and power cards from a
  JSON pack, bound per combat to 8 + 8 reserved slots, a generator split
  by (trigger, effect) pair, and learn.py keys `content` /
  `content_share`. Two things to know: the solved DB's rules fingerprint
  changes on merge (it hashes rule-file source; the DB was already stale,
  ideas#72), and the generator's budget can price only ~25% of powers
  with the heuristic, so the rest get cost 1-2 unpriced. Decisions
  "Registry-lite spec confirmed".

- (owner away) Registry-lite merged (0e0046a). First check on 326
  held-out cells with Metallicize / Demon Form swapped for a generated
  test power card: the champion's lead over the heuristic is +0.021 (se
  0.011) higher on generated cards than on the originals, but mostly
  because the heuristic plays them worse (-0.058; it can price only
  Strength powers). On the 53 cells with Demon Form's own mechanic the
  lead is +0.005 (se 0.027). So the check can't yet show generalisation;
  the training arms will compare nets with nets. Optional review items
  (not done): `sts.solve` on a generated combat panics rather than
  erroring; the step 2 timing note isn't the spec's bench.py check; the
  bind error doesn't name the deck; Demon Form's twin costs 2 (no 3-cost
  test card).

- Three orphaned `find.exe / -name ...` searches (started 00:45 by some
  session, parents gone; PIDs 29584, 22984, 12240) each burn a full core,
  so the job runner sees too few idle cores and starts a second job less
  often. The manager's attempt to stop them was refused by the permission
  check. They are harmless to end if you see them.

- (owner away) Depth with the net at the leaves works: two-turn search
  with the champion's net beats its one-turn play by +0.055 (se 0.013) on
  held-out elites and bosses, the same size as with heuristic leaves, and
  the two add up (0.591 vs the heuristic's 0.498). Lagavulin gains most
  (+0.128). Next: a spec to train the net on two-turn values
  (distillation), since two-turn play is ~145x slower.

- (owner away) Rate features merged (each power's worth per turn as
  columns, off by default); three test runs queued. Encoding with them on
  is ~7x slower, so those runs will be slower too.

- (owner away) Distillation built and merged: in each self-play round,
  10,000 elite and boss decisions are searched two turns deep and their
  option order becomes the ranking term's target. Three test runs queued
  (0049e, 0052b, 0052c, ~150 min each).

- 0049e ended 10:40 2026-10-31 (owner's go-ahead, setup session; see Running).

- (owner away) Rate features stay off by default: they fix Demon Form
  (+0.10 to +0.20 on fights whose deck holds it; the nets now play it like
  the heuristic) but cost -0.06 to -0.10 on Guardian fights without it,
  because the rate nets hesitate just before Mode Shift. A fix is the next
  goal-1 step (decisions "Rate features: off by default for now").
- More round-0 games help, but less than the pilot said: 20k vs 5k is
  +0.015 train / +0.011 held-out over 5 paired seeds (elites +0.02-0.03).
  40k is running.

- (owner away) Data scaling: 40k games beat 20k by about +0.01 (train
  +0.013, held-out +0.009, 3 seeds; bosses +0.04), as much per doubling as
  5k to 20k, so 80k runs next (decisions "Data scaling: 80k next").
- (owner away) The rate features' Guardian cost may be seed luck (seeds
  -0.00 / -0.20 / -0.12): two more paired seeds run before any fix.

- (owner away) Generated power mechanics don't transfer: nets trained on
  16 or 128 generated powers play unseen generated powers no better than
  nets trained on none (-0.004 / -0.006, se ~0.01). Content stays out of
  the recipe; goal 1 moves to per-mechanic features plus a short
  adaptation burst (decisions "Generated-power arms: no transfer").

- Big-picture review 2026-10-31b (`docs/research/big-picture-2026-10-31b.md`),
  run after the gen-arms read: depth's gain is real but measured only on 4
  elite/boss encounters on one half, and doesn't add with the net per
  encounter; training-seed sd is ~0.010 / 0.013, not 0.006 (MDE ~0.02-0.03
  at 3 seeds); the effects-vs-ids thesis was never tested at current
  strength (ids twin queued). Next re-ranked.
- Ladder: none of 12 newer-recipe nets beats the 10-29 champion; the
  lean and data40k recipes look ~0.01 weaker than the night recipe, so
  the solve step may be worth ~0.01 after all. Product candidates must
  now pass the ladder.
- **Your decision (not started):** the review recommends re-scoping the
  rules-engine series: widen registry-lite to generated attacks, skills
  and monster patterns next, retrain after each spec instead of keeping
  old nets bit-identical, and defer specs aimed only at fidelity. I have
  not acted on it, because it reverses the series' design rule.

- Depth hint for goal 1 (post hoc, being checked): two-turn search with
  the net helps most on held-out fights with an unseen power card (+0.076
  vs +0.012 without), as if search repairs the net's mis-pricing of new
  mechanics (depth doc "Where net-leaf depth gains").

- (owner away) Distillation closed: 3 seeds lose on elites (-0.030 /
  -0.035), ladder fails. Ids twin (3 seeds): the effects encoding beats ids
  by 0.075 on held-out elites (every seed), 0.034 on train elites, so it
  earns its keep mostly on unseen cards. Two-turn search removes most of
  the rate nets' Guardian cost (-0.16 -> -0.03, all 3 seeds): depth looks
  like a general repair for mis-priced mechanics; rates under depth are
  being tested on all bosses (decisions "Distillation closed; rates
  retested under depth").
- (owner away) Oracle arm queued (train on the generated bench's own test
  powers): checks whether the generated-power bench can show learning at
  all before the adaptation-burst spec (decisions "Oracle arm").

- (owner away) Top-3 two-turn player: level with fallback (+0.005), no
  change. Rates under two-turn search: +0.033 on held-out bosses vs the
  +0.06 bar, rates stay off (they do lift the held-out Guardian +0.06).
- Prior-art scan "search in stochastic card games"
  (`docs/research/search-stochastic-cards.md`, 8 angles, 7 sources checked
  by me): strong systems keep search at play time and work on the leaf
  value; distilling search into a searchless net is the usual weak link
  (an StS MCTS bot failed six times). Checked: our two-turn search does
  not see the draw order. Three framings listed for you, none adopted.
- (owner away) Ensemble evaluator spec confirmed and built (4fda986):
  search can score leaves with the mean of several nets
  (`a.pt+b.pt+c.pt`). Champion + its two seed twins queued on the ladder
  and in two-turn play (decisions "Ensemble evaluator spec confirmed").

- (owner away) Ensemble evaluator closed: averaging three seed nets helps
  one-turn play on held-out elites and bosses (+0.021) but not two-turn
  play (+0.008, se 0.007): depth already fixes most of the same leaf
  errors. The champion alone stays the evaluator.

- (owner away) The generated-power bench was blind: even nets trained on
  its own test powers ("oracle") gain nothing there (+0.001), so the
  earlier "generated powers don't transfer" is not evidence. A 3-copy
  version of the bench sees a little (+0.013, all seeds; bosses +0.064)
  and is used from now on; next is a spec for the adaptation burst
  (decisions "Oracle arm read").
- Two-turn search's sample size is fine (only ~1 in 5 overrides flips under
  a reseed) and gating it by one-turn's top-2 gap would save little; also,
  on 54% of decisions one-turn's top two options tie exactly (results doc
  "Two-turn search: sample size and an offline gate").
- data80k s1 (one seed): +0.024 held-out over 40k on tight2, but it still
  loses to the 10-29 champion on the ladder (-0.018), like 40k did.

- (owner away) **New champion.** Fine-tuning the 10-29 net for ~10 minutes
  on games holding 8 generated power cards beats it on the ladder (+0.011,
  2 seeds; elites +0.03-0.04); the same fine-tune without the cards does
  nothing. burst8 s1 is the champion now (decisions "Burst8 s1 promoted").
- (owner away) **The nets waste HP.** At run-like start HP every net loses
  about twice the heuristic's HP per fight (11-12 vs 5.6) at the same win
  rate, mostly by dragging multi-monster hallways out. tight2 couldn't see
  this. An HP-weight label (spec `hp-weight.md`) is queued, 4 runs.
- (owner away) Big-picture review 2026-11-01: depth is the one large lever;
  stop list adopted (no more one-turn label/recipe arms, data scaling
  stops at 40k, monster lookahead stays off). Selective two-turn search
  failed its speed check and stays on a branch.
- `jobs.py kill` was refused by the permission classifier this run
  ("interfere with workloads") although the manager notes say it's
  allowed; the job (0060) finished on its own.

- (owner away) **New champion: burst8hp2 s1.** HP weight 2 in the labels
  makes nets lose ~2.4 HP less per fight at run-like HP with no loss in
  wins (lean arms, 2 seeds); the same weight in the champion's 10-minute
  burst saves +2.2 HP over burst8 at level win rate, so it was promoted.
  Promotion now also needs run-HP no worse than the champion by > 1 HP.
  The champion still loses 8.2 HP per fight vs the heuristic's 5.6
  (decisions "HP weight 2 passes", "Burst8hp2 s1 promoted").
- Goal 1: a burst on 8 generated train-split power cards lifts play on
  *unseen* generated power cards by ~+0.018 over a no-card burst (elites
  and bosses +0.05 to +0.08), 2 seeds sharing one game set. Its ladder
  result is level with the 10-29 net, so burst8's earlier ladder gain may
  be card-specific or luck; fresh card sets are running.

- (owner away) **Depth doesn't fix the HP gap.** Two-turn play saves only
  +0.59 HP per fight for the HP-weighted champion (rule bar 1.0, gap 2.6).
  A tempo probe shows the champion wins hallways faster than the heuristic
  but blocks too little; the next spec is an `unblocked_incoming` feature,
  not the planned tempo feature (decisions "Run-HP at two turns fails").
- (owner away) Adaptation burst measured on 5 seeds / 2 game sets: it
  teaches its own cards a little (+0.03 over other generated cards, under
  the +0.04 bar); most of its gain is general.

- (owner away) **The nets didn't price HP, and a search fix closes the HP
  gap.** The score counts HP lost from the fight's start, but no input
  column holds the start HP, so in hallways the nets valued an HP at
  1/10-1/100 of its label price and raced instead of blocking. Adding the
  missing price at search time (0.01 x win chance x HP lost so far) cuts
  the champion's HP loss from 8.2 to 5.4 per fight on fresh fights (the
  heuristic: 5.75) at level wins; promoted as the champion
  (`...burst8hp2-s1.../model.pt@hpb0.01`). A start-HP input column is
  built (off by default) and four training arms are queued to see whether
  nets that price HP themselves do better still (decisions "Start-HP
  column replaces unblocked_incoming", "HP bonus promoted").

- (owner away) **Act-1 gauntlet built** (goal 2's headline number): 11
  fights with HP carried over (Burning Blood, a rest before the boss), clear
  rate paired by sequence; first check and an HP-price sweep queued.
- **Your decision (new): which simulator carries goal 2.** Prior-art scan
  (`docs/research/sts-bots-and-runs.md`, 3 sources verified): the strongest
  reported StS1 bot (sts-ironclad-agent, MIT) wins ~50% of A20 Ironclad
  runs to the Heart in the real game, built on `sts_lightspeed` (MIT C++
  simulator with all Ironclad cards, relics, enemies); streamers win
  46-65%, LLM agents ~0-10%, BottledAI clears Act 1 20% of the time. A
  "dominant" claim needs that setting (A20, relics, rewards, Acts 1-4),
  which our engine lacks. Option: keep our engine for goal 1 (custom
  content) and build goal 2's run layer on, or checked against,
  `sts_lightspeed`. Not acted on.

- (owner away) **Gauntlet first read:** the champion with the HP bonus
  clears the 11-fight Act-1 gauntlet 61.6% of the time vs the heuristic's
  59.6% (+0.020, se 0.016; 500 more sequences running). It wins more boss
  fights but dies more on elites: the HP bonus makes it play skills into
  Gremlin Nob's Enrage (2.3 skills per fight vs the heuristic's 1.3; 4.1 at
  a 4x bonus, where Nob wins 17% of fights). c = 0.01 stays (sweep).
- (owner away) The start-HP column passes its spec rule (+2.5 HP saved) but
  does no better than the search bonus, so it stays off and the champion
  isn't retrained with it. Depth's gain on generated powers is the same as
  on the originals (not content-specific).

- (owner away) Big-picture review 2026-11-01b
  (`docs/research/big-picture-2026-11-01b.md`): over 1,000 gauntlet
  sequences the champion + bonus is level with the heuristic (+0.018, se
  0.011); depth is the strongest lever not yet in the product, so the
  two-turn gauntlet runs before the survival-score arms (your design; they
  stay queued, ~4-6 h later). Skeptics corrected every key claim; training
  wins exist (bursts, data, HP weight), label variants still never moved
  play.
- (owner away) Enemy-Strength price (`@esp`) built and tested: it fixes
  Gremlin Nob but loses -0.020 clears over a run, so it stays off. The job
  runner now records each job's peak memory.

- (owner away) **Two-turn search was pricing HP wrong in won fights.**
  Search scores a finished combat with the engine's score, which floors HP
  lost at 0 after Burning Blood's +6 heal, and adds no HP bonus; so in a
  won fight up to 6 HP of damage looked free. Two-turn search sees many
  more wins inside its horizon and lost ~0.9 HP per hallway to it against
  one-turn (both with the bonus). A fix (`@hpe<c>`: the same "HP after the
  coming heal" price on finished and unfinished leaves) is built and off
  by default; one-turn it plays level with `@hpb`, the two-turn read is
  queued (decisions "End-HP bonus spec confirmed").

- (owner away) **Two-turn search is ~2x faster, results unchanged.** A
  profile showed half of a two-turn decision was hashing whole game states
  with Rust's default (slow, attack-proof) hasher and the other half the
  net recomputing identical card and hook-row layers on every leaf. A fast
  hasher and a per-batch layer cache fix both; every search result is
  bit-identical (decisions "Fast search tables built", "Net leaf cache").

- Goal 1 (post hoc, being replicated): the nets' trouble with unseen
  generated powers sits on powers that fire at the owner's turn start,
  which a one-turn leaf never reaches (it stops at the next draw); depth
  repairs those (+0.14) and not card-played ones (-0.09). If the fresh-fight
  replication passes, a cheap "turn-start peek" at the leaves is the next
  goal-1 spec (results doc "Novelty cost sits past the one-turn horizon").

- Two-turn champion on the gauntlet (with the HP bonus that leaks HP at
  two turns): +0.024 clears over one-turn (se 0.016), under the +0.03 bar;
  it cuts first-elite deaths 12 -> 2 and Nob deaths 23 -> 15 but bosses
  don't move. The fixed-bonus version is queued behind its run-HP check.

- (owner away) Heuristic-leaf two-turn search is ~5x faster, results
  bit-identical: the heuristic re-walked each monster's move odds at every
  leaf; it now caches them per move history (decisions "Heuristic rate
  cache built"; review clean, one optional: the new test lists monster
  kinds by hand).

- (owner away) **Two-turn search is now the product player.** With the
  end-HP fix (`@hpe0.01`: two-turn search no longer gives away HP in won
  hallways, +1.41 HP per hallway), the champion searched two turns deep
  clears the Act-1 gauntlet 67.6% vs 61.6% one turn deep (+0.060, se
  0.016; bar +0.03) and 59.6% for the heuristic. Elite deaths fall most
  (Nob 23 -> 10, Sentries 22 -> 11). It is ~50x slower than one-turn, so
  cheaper depth is now the throughput lever (decisions "Two-turn @hpe is
  the product player").
- Goal 1, new character: on Silent the champion is level with the
  heuristic one turn deep (+0.008) and ahead two turns deep (+0.040). On
  Poison decks it is weak one turn deep (-0.19 on elites) and depth
  repairs it (+0.32): Poison's value lies mostly past the one-turn leaf,
  like the generated turn-start powers (results doc "Silent zero-shot
  number").

- Big-picture review 2026-11-02 (`docs/research/big-picture-2026-11-02.md`):
  every measured gauntlet gain came from search-time changes; tight2 can't
  see run-level effects (the HP bonus: -0.001 there, +0.17 clears on the
  gauntlet). (owner away) Goal-2 reads now use the gauntlet with a
  sequential end-HP test and a clears guard (decisions "Gauntlet
  protocol"; replayed over all files: same verdicts, ~1/4 of the CPU).
- **Training since 10-29 didn't reach run level.** With the HP bonus the
  10-29 net clears the gauntlet 0.640 vs the current champion's 0.616
  (best c each); its two-turn read runs now and may replace the champion
  in the product player.
- The fatal fight is rarely savable: a rollout player wins 7 of 117
  never-cleared fatal fights; losses are decided earlier (boss entered at
  46 HP vs 80). (owner away) Card-rewards spec confirmed and building: it
  measures how much deck choices move clears before any run layer, so it
  doesn't pre-empt your simulator decision.

- (owner away) **Sim-boss: +0.155 more clears.** Letting the card chooser
  also simulate the Act boss (which the real game shows on the map) lifts
  starter-deck clears 0.540 -> 0.695: it takes scaling cards (Inflame,
  Spot Weakness, Combust) and boss deaths fall by a third. Goal 2's
  headline is now the gauntlet from the starter deck with rewards
  (decisions "Sim-boss passes"). Starter deck: skip 0.00, random 0.36,
  sim 0.55, sim-boss 0.70.
- Big-picture review 2026-11-02b (`docs/research/big-picture-2026-11-02b.md`):
  run-level gains since 10-29 came from search objective, depth and card
  rewards; training-seed noise at run level was never measured (twins
  queued); the run layer (rest sites, removal, path) is next. Skeptics
  rejected "the combat player doesn't matter at the boss".
- (owner away) **Deck choice is the biggest goal-2 lever found.** Card
  rewards on the gauntlet: from the starter deck, a chooser that simulates
  8 fights per option beats random picks by +0.184 clears (0.548 vs
  0.364; se 0.027), more than depth gave (+0.060); from the cell decks it
  adds +0.05 over random, random +0.19 over none. So the cell gauntlet
  overstates a run, and the headline will move to starter deck + rewards.
  This strengthens your open simulator decision: rewards, removal and
  shops are where clears are. Next: the chooser also looks at the boss
  (queued). Decisions "Card rewards are a goal-2 lever", "Sim-boss spec
  confirmed".

- (owner away) **Product net: the 10-29 net.** Searched two turns deep
  with the end-HP price it beats the burst8hp2 champion on fresh gauntlet
  sequences (500-749): +3.0 HP at the end (z 4.1), clears 0.724 vs 0.672,
  mostly fewer elite deaths. No newer net beats it at run level, and tight2
  ranks nets wrongly for run-level play (data80k is best there and fourth
  on the gauntlet). Rest-site chooser closed (fails: lucky upgrades win
  over heal at 16 fights per option). Card removal spec'd and building.
- (owner away) **Card removal: a removal is worth ~1.8 HP, choosing it isn't.**
  Removing a Strike after the first elite gains +1.78 end-HP (se 0.83) and
  +0.038 clears on the headline setting, so shops and removal stay on the
  run-layer list; the sim chooser gives the whole gain back (it removes an
  earned reward card 24% of the time and keeps 23%: selection noise over
  ~9 options, like the rest site) and is closed. Mixed depth (floors 1-3
  one turn deep) is level with full two-turn play at 57% of the wall time
  and is the screening default on the cell gauntlet (decisions "Card
  removal read", "Mixed depth for screens").
- (owner away) Elite-skip spec confirmed and built (6669be1): `--elites
  skip|hp` fights a hard hallway instead of an elite. With no relics an
  elite has no payoff on this gauntlet, so `skip` measures the ceiling of
  what any path choice could be worth here (not a product rule); reads
  queued. It doesn't pre-empt your simulator decision (decisions
  "Elite-skip spec confirmed").

- (owner away) **Headline: 0.804.** The product player (10-29 net, two
  turns deep, end-HP price) on the headline setting (starter deck, sim
  rewards, sim-boss) clears 80.4% of 500 Act-1 gauntlet sequences, vs
  68.0% one turn deep (+0.124, se 0.022) and 53.4% for the heuristic.
  Depth's gain here is twice its cell-gauntlet gain and lands on the boss
  (won 0.85 vs 0.76 per arrival, +0.045 at matched entry HP) as well as
  the elites: reward decks hold scaling powers whose value sits past the
  one-turn leaf. Decisions "Headline number".
- **The approach review you asked for** (engine-next session,
  `docs/research/approach-review-2026-11-02.md`, brought onto main at 14:25) ends with
  seven decisions for you ("Decisions for the owner": what goal 1 means,
  simulator and arena, the engine-next landing rule, the survival arms,
  the lanes after 11-14, the manager cadence, db/ and the headline's unit).
  The manager re-ranked Next from it and adopted its stop list where
  that was the manager's call; not adopted without you: dropping the
  solved DB and solver, the manager cadence, the survival arms (still
  queued), the simulator / arena choice (decisions "Next re-ranked from
  the approach review").
- (owner away) Line-seed spec confirmed and built (b4dd041..429ba94): a
  two-turn player that re-searches each decision under the turn's first
  seed decides like one committing to the first tree's line; the first
  tree holds ~60% of a turn's two-turn cost (saving ~1.7x if committing
  costs no strength; read queued). Stage 2 (Rust) waits for your
  engine-next landing.
- (owner away) Elite skip read: skipping both elites (no payoff on this
  gauntlet) is worth +14 HP end-HP and +0.20 clears at n 50; the plain
  rule "skip an elite entered under 40 HP" is worth +1.5 HP (pass at n
  83). Path choice is a real run-layer lever, of a removal's size, but
  the headline keeps no path rule: measuring it honestly needs an elite
  payoff, which is your simulator decision (decisions "Elite-skip read"). Q6 one turn: the effects encoding's
  edge over ids is +0.154 on known power cards and +0.048 on generated
  twins; two turns deep (s1) it is +0.076 / +0.017: search does most of
  the generalising on unseen cards (decisions "Q6 two turns").
- (owner away) **The boss curve is causal.** Replaying each headline deck's
  own boss fight at entry HP 30-80 keeps 87% of the observational slope
  (arrival HP barely predicts a deck's win at fixed HP, corr +0.13), so
  your run-value plan (L2 b-d) proceeds at full size; the curve is per boss
  (Slime Boss near-sure from 40 HP, the Guardian a cliff around 50,
  Hexaghost a slow climb to 0.90) and per deck the step is sharp (median
  width 10 HP). Decisions "Boss replays: the boss curve is causal".
- (owner away) **Run-value chooser (your use b, card picks): fails.**
  Options scored by P(reach the boss at h) x P(win the sequence's own
  boss | h, deck) (the causal curve shifted to the deck's 8 boss fights)
  lose -0.044 clears / -1.45 HP to the sim chooser on both cross-fitted
  halves, with 22-24% of picks changed. The sim chooser stays; (c) and
  (d) keep their standing. Likely causes and two untried variants are in
  the results doc (decisions "Run-value chooser: fails").
- (owner away) The crossed chooser arms say the chooser holds ~0.09 of
  the 0.156 one-turn headline lead and nearly all of it on held-out cards
  (the heuristic can't price cards it doesn't know); the fighter ~0.06,
  on training cards.
- (owner away) **Goal-1 enemies rung, stage A (your paired-modifier
  yardstick on state-patch modifiers), one-turn half read:** the net is
  nearly as robust as the heuristic to stat changes (HP x0.8 / x1.25,
  Strength, Metallicize: -0.01 to -0.02 of a win beyond the heuristic's
  own drop) but loses -0.05 to -0.09 on SharpHide 2 and -0.04 on Ritual
  2, the SharpHide cost all on Three Sentries and Gremlin Nob and none on
  the Guardian (its training home): it learned the power as a Guardian
  thing. Balance measured: Metallicize 4 + HP x0.85 is easier than the
  parent, SharpHide 2 + HP x0.9 clearly harder; a stack is about the sum
  of its parts. The two-turn subset decides horizon vs burst (decisions
  "Mutated monsters stage A, one-turn read"). Pattern mutations wait for
  the landing.
- (owner away) **Headline re-rank: no standing net comes near the 10-29
  net once rewards are in the loop** (data40k -0.056, data80k -0.104,
  lean-thr -0.108, cover21 -0.096, burst8hp2 -0.148 = the heuristic).
  The cell gauntlet understated these gaps 3-5x (each net also picks its
  deck with its own sims). Product candidates are now read on the
  headline setting; tight2 / ladder standings from 10-29 to 11-02 don't
  rank nets for the product (decisions "Headline re-rank"). Why the
  10-29 net stands apart under rewards is open (the solve step is the
  suspect; a cheap check is listed).
- (owner away) Line seed passes (+0.60 HP, +0.024 clears vs plain
  two-turn on cell 0-249): stage 2 (export the principal line, Rust,
  ~1.7x cheaper two-turn play) is specified after the landing.
- (owner away) At run level the solve step is worth nothing (lean = the
  10-29 recipe on 3 seeds, +0.001 clears) and threshold rows nothing; the
  effects encoding's edge over ids sits on held-out cards (-2.5 HP, -0.04
  clears for ids). Evidence for the review's decision 7 (drop the solved
  DB and solver from training), still yours. Read by 3a78b41d, committed
  by 2b40a321.

- (owner away) **Goal-1 enemies rung, two-turn half: the product has no
  novelty cost on state-patch mutations.** On the matched 40-start subset
  the product net two turns deep loses nothing beyond the heuristic on any
  modifier (within +-0.025), while one turn deep it loses -0.03 to -0.09 on
  SharpHide (Three Sentries -0.19); depth repairs +0.04 to +0.06 on the
  power modifiers and ~0 on stat changes. By your yardstick's rule this is
  a horizon problem, so no adaptation burst on mutated monsters; the rung
  is read on the product player from now, and pattern mutations (stage B,
  after the landing) are the next enemies measurement. Two retuned pairs
  (Metallicize 4 + HP x0.75, SharpHide 1 + HP x0.9) are being measured so
  your pairs come out near the parent (decisions "Mutated monsters stage
  A, two-turn read").
- (owner away) Mixed depth (floors 1-3 one turn deep) is level with full
  depth on the headline setting by its bar (-0.012 clears, se 0.007; -0.3
  end-HP) with a small real HP cost on floors 1-3 that washes out, and
  saves ~30% of the time there (43% on the cell gauntlet). It is the
  screening default on the headline too; the headline number itself and
  product-candidate reads keep full depth (decisions "Mixed depth on the
  headline").
- (owner away) Why the 10-29 net stands apart under rewards: its twin
  without the solve step (lean s1, level with it on cells) is -0.05 clears
  / -2.5 HP below it on the headline one turn deep, at 1.5-2 se, all of it
  boss deaths. The solve step may matter once the net also picks its deck;
  three seed twins run tonight to settle it. This bears on the review's
  decision 7 (dropping the solver from training): wait for the twins.
- The survival arm 0059l8b (gates your engine-next landing) could not
  start for hours: it asked for 6 GB, more than was free. Its reservation
  is lowered to 3.5 GB (its twin peaked at 3.78) and it started 22:21.
- (owner present, session kb-adoption-5acbb5) The `kb` claims store is on
  here (stages 1-3 of `docs/specs/kb-adoption.md`): ~85 sourced facts in
  `docs/claims/`, STATUS.md at every session start, the product in
  `configs/product.json`, spec states on line 3. Managers record facts
  beside this file for now. Stage 4 would turn this file's "Next", "For
  the owner" and most of "Running" into facts and the job queue and
  shrink it toward 250 lines: that changes your hand-over, so it waits
  for a week of `kb stats` and your word. Decisions "kb adoption spec
  confirmed", "Product registry", "Spec status is line 3".

- (owner away) **Your survival-score arms fail.** Both seeds save ~2.6 HP
  per fight over a bare net but ~0.9 HP less than the same net with the
  constant search bonus, and they lose 0.06 of a win on tight2 held-out
  (bar 0.02); a play-time c sweep (2, 4) moves nothing. The HP price stays
  the end-HP bonus; use (d) of your run-value plan closes; the code stays,
  the spec is folded (results doc "Survival-score arms: fail", decisions of
  2026-11-03).
- (owner away) **The solve step at run level is not shown on three seeds:**
  pooled -0.032 clears (se 0.021) without it, between the pre-registered
  verdicts (s1 -0.05, s101 +0.03, s201 -0.07). Decision 7 of the approach
  review (drop the solver from training) is yours; 3 more pairs (~3 h
  light) would settle the +-0.02 question. Not queued.
- (owner away) **engine-next is landed** (your OK of 15:35 11-02; both arms
  had run): fast-forward c3f81f4, cargo and series_check green, `sts`
  swapped. The rules version is unchanged (datasets and the solved DB
  replay); new nets get the wider default layout; a training run compared
  against a pre-landing net must allow for it (Running). Unblocked: line
  seed stage 2 (building), mutated monsters stage B, the two-turn
  self-play round, the sampled-draw leaf.
- (owner away) **Line-step spec confirmed and building** (stage 2 of line
  seed): `sts.search` returns the principal line, `--step-line` plays it;
  identity with the stage-1 player and a 0.65 cost bar are the checks;
  the headline read at fixed n decides whether it becomes the play mode
  for two-turn reads (decisions "Line-step spec confirmed").
- (owner away) **Line step is the two-turn play mode.** The stepped
  committed-line player is level with plain two-turn on the headline at
  fixed n 250 (end-HP +0.04, clears -0.016; 0064 row-identical to stage 1)
  at ~0.55 of the wall time, so the product's flags are now `--two-turn
  --line-seed --step-line` (same net and price); the 0.804 headline number
  stays until the stepped file holds 500 sequences (0066) and becomes the
  control. The probe's missed 0.65 cost bar was an upper bound: on the
  headline the saving is ~45% (decisions "Line step is the two-turn play
  mode").
- (owner away) **Your two-turn self-play round is built and running**
  (spec `two-turn-round.md`, folded): 3000 elite and boss games on varied
  training decks at run-like HP from the stepped product, a burst fine-tune
  of the 10-29 net on 2 seeds plus a one-turn control arm on the same
  specs, each read with the protocol one turn deep against the 10-29 net
  (jobs 0067-0071, ~8-10 h). Decisions taken for you: the parent's encounter
  set (no Hexaghost or Guardian, so the run tests the teacher, not new
  content), varied setups rather than tight2 cells, 1500 games per group,
  the control arm, no hp_weight (decisions "Two-turn round spec confirmed").

### Active manager

4c7c253c (operating-model build, worktree sleepy-kirch-00c63b), cut-over 12:25 2026-11-03: this file moves to docs/manager-archive.md and the steward, navigator and lane worker take over (docs/operating.md).

### Running

- **engine-next landed 00:20 2026-11-03** (`git merge --ff-only`, c3f81f4;
  decisions "engine-next landed"): cargo tests green, `series_check` PASS,
  `sts` on main swapped to the branch's wheel (00:19; no process held it;
  `jobs.py impact sts`: none, the queue was empty), pushed. The rules
  version over the golden games is unchanged (7042d1d6a6149ba0), so
  datasets, recorded games and the solved DB still replay; the solvedb
  fingerprint over the engine sources changed, so cached solved states
  aren't reused by the new module. **Note for training runs:** new nets get
  the wider default layout (rows 92 -> 131, cards 60 -> 82; piles
  next_draw / known_later; the new row kinds opt-in via `extra_rows` /
  `row_kinds`), so a run compared against a pre-landing net has wider
  columns: account for it. Warm fine-tunes save today's row kinds plus the
  parent's; `registry.replay` raises on a game that replays differently
  (re-record such a generated dataset when a job needs it). The worktree
  is unregistered; its leftover `target/` folder (1.2 GB, no junctions:
  `models` was removed first) refused deletion at 00:35 ("busy"): `rm -rf
  .claude/worktrees/engine-next` when it lets go. Branch `engine-next`
  kept (merged). `docs/engine-next.md` on main describes the series.
- **Headline file:** `results/gauntlet/net1029-hpe0.01-two-starter-simboss.json`
  (500 sequences, 0.804 clears) is the control for every two-turn headline
  read (`--against`, or paired at fixed n for cost-savers). The one-turn
  file `net1029-hpb0.01-starter-simboss.json` (0.680) is the control for
  one-turn screens.
- Read 00:30 2026-11-03: 0059l8b with l8a
  (survival arms: **fail**; results doc "Survival-score arms: fail",
  decisions "Survival-score arms fail"), 0063 with 0061 (solve-step seed
  twins: pooled -0.032 clears, se 0.021, between the verdicts; results doc
  "Seed twins of the solve step on the headline", decisions "Solve step at
  run level"). Survival-score spec folded into README and decisions.
- **Line step built and folded (01:05 2026-11-03; decisions "Line seed and
  line step built and folded"):** c2a326e (`sts.search(...)["line"]`, the
  principal line), 7adb302 (`--line-seed --step-line` player, `line_probe.py
  --compare`), 9780a94 (review must-fix: margin-0 tie). Probe: 20 of 20
  fights identical, 526 of 526 decisions agree, cost 0.70 (bar 0.65 missed,
  reads go ahead: decisions "Line-step probe"). `sts` swapped at 00:45 (the
  line key); the fast Python suites (22 files, 228 tests) pass on it. The
  review's optional items are in the decisions entry; follow-up idea
  ideas#80 (continue the line through listed chance nodes).
- **Line step read 07:45 2026-11-03: pass** (results doc "Line step on the
  headline setting", decisions "Line step is the two-turn play mode"):
  0064 row-identical to the stage-1 file (544 floors); 0065 level with
  plain two-turn at fixed n 250 (end-HP +0.04, se 0.80; clears -0.016, se
  0.020; all of it Hexaghost deaths 14 vs 9 on the held-out half) at ~0.55
  of the wall time (69.5 min at 3 thr vs 127-128 at 2 thr per 250).
  `--line-seed --step-line` is the play mode for two-turn reads and the
  product's flags (`configs/product.json`, facts how/two-turn-search,
  yardstick/cost-savers). A control played without the flags needs `--vary
  line_seed --vary step_line` under `--against`.
  **0066-gauntlet** (lane depth, started 07:50, ~70-90 min): adds sequences
  250-499 to `results/gauntlet/net1029-hpe0.01-two-line-step-starter-simboss-a.json`.
  **Read 0066:** `gauntlet.py read <that file>
  results/gauntlet/net1029-hpe0.01-two-starter-simboss.json` on 0-499 at
  fixed n (level = within +-1 HP and +-0.02 clears; look at Hexaghost deaths
  per arrival: 0.831 vs 0.892 on 0-249). Level -> the stepped file is the
  headline control: set `headline_control` in `configs/product.json` to it
  (by hand; `product.py set` is for promotions), re-set facts
  yardstick/headline-control and measurement/headline@two-turn to its
  500-sequence clear rate (the plain file stays as its paired twin). Not
  level (a Hexaghost cost that holds at n 500) -> keep the plain control,
  re-open the play-mode decision with the numbers.
- **Two-turn round (L6; spec `two-turn-round.md` confirmed and built
  08:30 2026-11-03, folded; decisions "Two-turn round spec confirmed",
  "Two-turn round built"): jobs 0067-0071, lane train, pinned d3c6b75.**
  0067 (J1: 3000 elite+boss games on varied training decks at HP 40-100%
  from the stepped product `@hpe0.01`, 3 thr; the job record says est 360
  min but its first chunk ran at 7.2 fights per thread-minute (8.3 s per
  fight, 2.4x faster than the spec's guess), so expect ~140 min, ending
  ~10:40; `jobs.py set` has no estimate flag, the record was left;
  resumable from `cache/twoturn-*.partial.jsonl`), 0068 (J1v: 300
  validation games, after 0067), 0069 / 0070 (arms s1 / s101: burst
  fine-tune of the 10-29 net, then `gauntlet.py play <run>/model.pt@hpb0.01
  --against results/gauntlet/net1029-hpb0.01.json`, after 0067 + 0068),
  0071 (one-turn control arm: the same specs played by the same net one
  turn deep, seed 1; no wait, takes the heavy slot 0066 frees). **Read each
  arm:** the job log's last lines (run id, out file, protocol verdict) and
  `gauntlet.py read results/gauntlet/<arm>-hpb0.01.json
  results/gauntlet/net1029-hpb0.01.json` (deaths by encounter, halves).
  **Pass on a two-turn arm:** queue `<run>/model.pt@hpe0.01 --two-turn
  --line-seed --step-line --sequences 250 --threads 3 --against
  results/gauntlet/net1029-hpe0.01-two-line-a.json --vary step_line` (mem
  4.5); confirmed -> headline candidate (full depth, `--against` the
  headline control) and a second round as a new spec (may add Hexaghost and
  the Guardian under the "new content" rule). If 0071 passes too, the gain
  is fresh net-played elite/boss games, not the teacher's depth: say so.
  **Fail or open on both seeds:** decisions entry closing the
  outcome-label family (owner's rule), re-set `decision/two-turn-self-play`,
  extend `cause/teacher-equals-student` with the measured value; L7 is next.
- **Product player:** `runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01 --two-turn --line-seed --step-line`
  (`configs/product.json`; flags changed 07:50 2026-11-03, same net and price). Screens take `--one-turn-floors 3`; headline
  reads of product candidates keep full depth; **use `--against` for every
  goal-2 screen** (control = the product's file on the same sequences and
  setting). The HP price stays the end-HP bonus (survival arms failed).
- **Memory is the binding limit.** The runner admits a job only if
  `mem_gb` + 1 <= free. Peaks: two-turn at 2 thr ~3.0-3.5 GB, at 3 thr
  3.2-4.7 GB; one turn ~1 GB; a 6-thread training arm 3.8-4.3 GB. Set
  `mem_gb` from these; a heavy job that asks for more than ~3.5 GB may
  wait for memory.
- **Job runner** pid 30900 (restarted 22:37 2026-11-02 on lanes runner
  step 6); check `jobs.py status` each run; restart it if the pid is dead
  (Each manager run, step 5). `scripts/tests/test_jobs.py` is flaky on a
  free-memory assertion. The first `jobs.py add` after the landing builds
  a snapshot wheel for the new HEAD (a few minutes).

### Next

**Transition note (08:30 2026-11-03):** the owner-confirmed operating model
(`docs/specs/operating-model.md`; build session local_fb127636, steps 1-2 on
main: `scripts/health.py`, `docs/operating.md`, `docs/backlog.md`,
`docs/direction.md`, `docs/filler.md`, role tasks installed unscheduled)
archives this file in its cut-over step; until then this file is live and
the manager runs. Its backlog lists L6 below as a candidate: it is built
and running (0067-0071), so the first navigator run should open it as a
lane or read it as one.

**Re-ranked 14:30 2026-11-02 from the owner-requested approach review
(`docs/research/approach-review-2026-11-02.md`, on main since 7328936;
read "Approaches to try", "Stop or pause" and "Decisions for the owner"
first; decisions "Next re-ranked from the approach review"). Goal-2 reads
use the gauntlet protocol with `--against`; the headline setting is
starter deck + sim rewards + sim-boss, two turns deep.** In order:

K. **kb uptake, daily until 2026-11-09** (light, no CPU): `kb stats
    --since 2026-11-02` and one Log line (lookups, source re-opens,
    missed-lookup words, suspect facts left unworked). Stage 4 of
    `docs/specs/kb-adoption.md` (manager.md over to facts) is ready when
    lookups appear in most manager sessions and re-opens fall; re-opens or
    session length rising is the stop signal. Then tell the owner; don't
    move this file over without their word. **00:15 2026-11-03:** since
    11-02, 24 sessions, lookups 14 (13 in the kb-adoption session,
    managers 0-1 each), re-opens 801; the baseline. **07:30 2026-11-03:** 23
    sessions, lookups 20, re-opens 799 (this manager: 0 lookups, 13
    re-opens before them; the facts it needed were in STATUS.md).
L1. **Cheap depth** (review approach 1, p ~0.6): line-seed read b39b1
    passes (+0.60 HP, +0.024 clears vs plain two-turn); stage 2 (line
    step) **read 07:45 2026-11-03: pass, and `--line-seed --step-line` is
    the two-turn play mode** (Running; decisions "Line step is the two-turn
    play mode"); 0066 extends the stepped headline file to 500 sequences. Mixed depth on the
    headline is level by the bar and the screening default; headline
    reads keep full depth. The sampled-draw leaf (approach 2) is unblocked
    by the landing (main has the branch module): spec after L6's first read.
L2. **The run value along HP, used where the player trades HP** (approach
    3; plan approved by the owner 15:55 2026-11-02, decisions "Run value
    along HP: the plan"). Step 0 half-passed (results doc "Run value along
    HP": floors 6-8 pass the 3x slope gate, floor 5 fails). In order:
    (a) **Done 18:30, passes (manager 2b40a321):** the boss curve is causal
        (87% of the observational slope with only HP varied; corr of
        arrival HP with a deck's win at fixed HP +0.13) and per boss (Slime
        Boss near-sure from 40, the Guardian a cliff at ~50, Hexaghost a
        slow climb to 0.90); per deck the step is sharp (median width 10
        HP). (b)-(d) keep their full size; the unit is per boss, from
        `results/boss_replay/` (`boss_replay.py read`).
    (b) **Closed 19:40: fails for card picks** (-0.044 clears, -1.45 HP
        on both cross-fitted halves; decisions "Run-value chooser:
        fails"). The sim chooser with the sim-boss term stays; two cheap
        variants are ideas, not queued. Rest-site and elite uses not
        built. Original text: **Run decisions (use 1):** V_run(HP, floor, boss, deck) as the
        choosers' unit: card picks (the terminal value of the chooser's
        next-floor sims, factored as P(reach the boss at h) x P(win the
        boss | h) so the boss isn't counted twice), rest vs upgrade, fight
        vs skip an elite (the curve replaces the HP-40 rule; the
        always-skip ceiling is +14 HP). First check per the review
        (pick-change rate >= 10%; one-turn headline, fit 250-499 / play
        0-249 then mirrored, `--against` the one-turn headline file).
    (c) **Combat price by floor (use 2):** per-floor player strings
        (`net@hpb<c_k>`), no Rust, only after a (b) pass, so **not now**;
        a price by current HP inside a fight would need a search change.
    (d) **In the survival score (use 3): closed 2026-11-03**, the survival
        arms failed (decisions "Survival-score arms fail"); the constant
        end-HP bonus stays the HP price.
L3. **Result cache for run-layer reads** (approach 6, p ~0.8, 2-3 h,
    Python): per-player cache keyed by the fight spec in `gauntlet.py`
    plus a "reconstruct the state at floor k" helper; first check: strike
    removal replayed from the headline control row-identical at <= 50% of
    the fights. Build when the next run-layer read (a mini-map with L2) is
    specified.
L4. **Mutated-monster bench, stage A: done 22:20** (one turn: stat
    changes cheap, SharpHide on new enemies -0.05 to -0.09, Ritual -0.04;
    two turns: depth removes the whole cost, horizon not training, **no
    burst**; spec folded; retuned pairs queued as 0062, read under Running).
    Left: stage B (pattern mutations), **unblocked by the landing**, needs
    a spec (the engine's pattern rows: `docs/engine-next.md`); read on the
    product player (two turns) with the one-turn net's drop as the leaf's
    cost. Original text:** Whole-fight measure on state-patch modifiers (HP x0.8 /
    x1.25, Strength +1/+2, Metallicize 3, Ritual 2, SharpHide 2 for
    Thorns; the owner's pairs metal4-hp0.85, ritual2-hp0.7, sharp2-hp0.9;
    one stack), difficulty per modifier from the heuristic and the
    two-turn product, novelty cost = the one-turn net's drop beyond it.
    Stage B (pattern mutations: damage per hit, split hits, Weak on hit)
    needs the engine: after the landing. The leaf-ratio read is optional.
L5. **Generated character on the headline gauntlet** (approach 4, goal
    1's standing number): needs the branch module and the owner's
    bundles-vs-atoms answer (review decision 1): waits.
L6. **One two-turn self-play round** (approach 7, kept by the owner
    15:45 2026-11-02; decisions "Two-turn self-play round: kept, small
    and targeted"): **spec `two-turn-round.md` confirmed and built 08:30
    2026-11-03 (582dcd6, 8c51dd3, d3c6b75; folded), jobs 0067-0071 running
    and queued, read rules under Running.** Original text: both preconditions met 2026-11-03 (line-seed read,
    landing); needs a spec (two-turn product games recorded as a registry
    dataset with outcome labels: new tooling, since `selfplay.py` plays
    one turn deep and the fallback player lives in `depth_paired.py`);
    spec it once line-step's probe passes, so its games cost ~0.6x. One run: a few thousand games (burst size) on elite and
    boss cells only, played by the two-turn `@hpe0.01` product,
    outcome-labelled; fine-tune the 10-29 net (burst recipe, 2 seeds);
    read one turn deep `--against` the 10-29 net's one-turn cell file,
    confirm two turns deep. A null closes the outcome-label family on
    the dev machine (training rule: a stronger teacher is an allowed reason;
    no second round unless the first passes).
L7. **Rows-on vs rows-off burst** (review cheap read 7, the series'
    net-side verdict; the training rule allows it: inputs the net can't
    see today). Unblocked by the landing; needs a short spec: the burst
    recipe (`configs/burst8-s1.json`-style fine-tune of the 10-29 net)
    with `extra_rows: true` vs off, same games and seed, 2 seeds, read
    one turn deep `--against` the 10-29 net's one-turn file; the open
    question first: which content in the burst's games exercises the new
    row kinds (static, countdown, replacement, pattern), else the read is
    blind by construction. ~2 thread-hours of CPU.
Cheap reads from the review: 2, 3, 5 read (results doc "Effects vs ids,
the solve step and threshold rows at run level"); 4 and 10 read; 1
(heuristic two-turn anchor 250-749, 70 min, 4-5 GB) and 8 (matched-HP
replay probe: deep-search headroom; the old Q5; three-turn via
`turns=3`, a rollout leaf via `rollout_probe.py`) are still open and
cheap once the stepped player lands; 6 done (survival arms); 7 is L7; 9
is the owner's.

Q-items (06:45 ranking) status: Q1 done. Q2 **done 14:30: 0.804** (results
doc "Two-turn product on the headline setting"). Q3 rest-site closed,
removal read (+1.8 HP, chooser closed), elite-skip **read 14:35**: ceiling +14 HP, the HP-40 rule +1.5 HP; path
choice stays on the run-layer list, headline unchanged, spec folded. Q4 done (flat by floor; along HP see L2). Q5 ->
cheap read 8 above. Q6 one turn **read 14:20** (effects minus ids +0.048
on generated elite + boss cells, +0.154 on the originals: the edge is
mostly on known cards), two turns c1 running / c2 queued. Q7 thread
scaling done; the SPRT-in-ladder item is dropped (no goal-2 promotions on
the ladder: review stop list).
Older R-list below (still true for detail).

R1. Run-level value of the net: **10-29 net read (02:10): it beats the
    burst8hp2 champion one turn deep (0.640 vs 0.616 at best c; end-HP
    +1.82 at c 0.01)**, so training since 10-29 didn't reach run level;
    its two-turn `@hpe` read (b35) and the heuristic two-turn anchor
    (b3/b4) run now (Running).
R2. Gauntlet protocol: **done**: adopted, early stop built and checked
    (`--against`).
R3. Rollout ceiling probe: **done (03:05)**: 7 / 117 never-cleared fatal
    fights won at 64 play-outs (sanity 27 / 30); the fatal fight is rarely
    savable, losses are decided earlier (HP, deck). Goal-2 effort moves to
    HP on the way and deck choices (R6).
R4. Depth only where it pays: `--one-turn-floors 3` **read b45: level,
    57% of the wall time**; screening default on the cell gauntlet. Left:
    the same check on the headline setting (starter deck), then memory
    per two-turn thread (engine code: ask the engine-next session first).
R5. Bias audit: **slice 1 read** (Strength ~4x, Poison 2-6x under-priced); 10-29 net audit b37b (Running); next slices per spec.
R6. Card rewards: **pass (+0.184 clears, starter sim - random)**; now the
    top goal-2 lever. Sim-boss chooser read queued (b37c, Running). Then:
    headline on `--start starter --rewards sim[ --sim-boss]` with the
    product player (two turns); then removal / rest-site upgrades or a
    learned chooser.
R7. Goal 1: horizon replication **passes** (+0.274 cells / +0.243 cards);
    open: depth does *worse* on generated card-played powers (-0.16, both
    reads): a decision diff on those cells; then effects vs ids on the
    3-copy bench; mutated monsters.
R8. Runner: admit by fit **done (backfill, 5b47aa2)**; left: dry-run args, ledger.
R9. Only if R3 finds headroom: cheap deep search on boss floors.
Survival arms 0059l8a/b: run and read 2026-11-03, fail (decisions
"Survival-score arms fail").

Older order (2026-11-01b), kept for detail:

From `docs/research/big-picture-2026-11-01b.md`.
Status 22:35: (1) two-turn product on the gauntlet: `@hpb` halves read
+0.024 (se 0.016), under the bar, elites up, bosses level; and **two-turn + `@hpb` was found to lose ~0.9 HP per
hallway to the floored finish score**; the fix `@hpe` is built, its
two-turn read 0059l7r3a2 is queued and its gauntlet follows on a pass
(Running); (2)
runner peak memory: **done** (f753339); (3) profile a two-turn decision by
phase: **done 21:30** (results doc "Two-turn search: where the time goes"):
fast tables (f7bbe85) + net leaf cache (f2b42a9), bit-identical, net-leaf
two-turn search ~1.9-2x faster; left: the heuristic's own leaf estimate
(~180 us, more than the net) and the solver's SipHash tables (solve.rs,
~70% of a non-lean round) are the same kind of cheap exact win; (4) enemy-Strength price: **built,
fails at run level** (-0.020 clears; decisions "Enemy-Strength price fails
at run level"); (5) goal 1: novelty vs horizon: **post hoc slice 22:15 says the novelty cost sits on powers that pay at turn start (past the one-turn leaf) and depth repairs it (+0.20 over card-played powers, card se 0.098); pre-registered replication 0061 queued; Silent number queued (0059l7r3a3-a6)**; (6)
trinomial GSPRT replay: **done, no verdict changes** (results doc; switch
when ladder.py is next touched); (7) survival arms queued after the depth
reads; (8) heuristic two-turn gauntlet anchor: **queued 0062**; (9) owner's
N6. Items N0-N6 below carry the detail of the open threads.

N0. **Gauntlet (goal 2's headline): first check read 16:30 2026-11-01**
   (results doc "Act-1 gauntlet: first check and HP-price sweep"): shape
   fine (clears 0.45-0.62), c = 0.01 stays, champion + bonus level with the
   heuristic (+0.020, se 0.016): better on bosses, worse on elites
   (Gremlin Nob: the bonus makes it play skills into Enrage, `nob_probe.py`).
   Left: pool 0059l7p1/p2 (sequences 500-999), read 0062a (two-turn
   champion), fold the spec into README/decisions. Optional review items
   (not done): one-turn `play` writes nothing until all floors finish;
   "HP at boss" is after the rest heal.
N1. **HP price: the search bonus is the fix for now; survival score is the
   learned candidate.** Start-HP column passes its rule but doesn't beat
   the bonus (decisions "Start-HP column passes but the bonus stays").
   Left: (a) survival-score arms 0059l8a/l8b (see Running: must beat the
   bonus controls 0026/0027 and not feed Nob); (b) 0059l9: does depth add
   on top of the bonus? (c) Lagavulin and Nob are where the HP and the
   elite deaths are; a decision diff on Lagavulin is the next probe if the
   survival arms don't fix it.
N2. **Depth on generated powers: closed, not content-specific** (contrast
   +0.005, se 0.024; decisions of that name). Depth stays the general
   play-time lever: the two-turn gauntlet (0062a) and a two-turn product
   on the ladder are its next uses.
N3. Adaptation burst: closed as a measurement (5 seeds, 2 game sets:
   contrast ~+0.03, every seed positive, under the +0.04 bar). The burst
   stays the goal-1 tool; next use is with depth (N2) or on a new
   mechanic.
N4. Selective two-turn search failed its speed check (branch kept). Then
   the review's ranks 5-7: two-turn product on the ladder, three-turn
   probe, Act-1 gauntlet with HP carried over.
N5. Closed this run: data scaling (80k = 40k), monster lookahead (off),
   gen arms on 3-copy bench (match the oracle: general familiarity). The
   review's stop list is in decisions "Review 2026-11-01".
N6. Owner's decision: rules-engine re-scope. A session the owner started
   is coding the next engine version on branch `engine-next` (2026-11-01;
   see Running).

Older order (2026-10-31b), kept for detail:

0. **Ensemble evaluator: closed (02:15 2026-11-01)**: two-turn ens3 minus
   two-turn champion +0.008 (se 0.007) on held-out elites+bosses, no change
   (one-turn on the same fights +0.021: depth absorbs most of it); spec
   folded (decisions "Ensemble evaluator: no change at two turns"). Left
   from the prior-art report: the sample-size check and offline gate data
   (0057a8z8c queued; read as under Running). If overrides at k4 often
   flip under a reseed, test sample_k 8 vs 4 on the paired fights (wins).
1. **Ladder read (17:05): all 12 newer-recipe nets lose to the 10-29
   champion** (lean-thr mean -0.017, data40k r1 -0.019, distil s1
   -0.030, cover21 -0.063; results doc "Ladder: no newer recipe beats the
   10-29 champion"). Lean and data40k look ~0.01 weaker than the night
   recipe (solve step, r2). From now on a product candidate must beat the
   champion on the ladder; ladder distil s101 / s201 and data80k r1 when
   they end (one `ladder.py test <model.pt> --threads 6 --no-promote`
   each, ~1 min). Champion candidate (22:20): at 40k round 0 the
   expected lead over the best-of-3 champion is ~+0.003 (data +0.01,
   champion's pick ~+0.007), under the ladder's reach, so it waits for the
   data80k read; if 80k - 40k is again ~+0.01, run the night recipe
   (seed-check-r2-s1 config, solve step on, rounds 2) at 80k, 2 seeds,
   and ladder both. Open question for a spec: a data-scaled night recipe
   (solve step on, 40k round 0, r2) as the next champion candidate.
2. **Ids twin: done (20:20, 3 seeds; results doc "Ids twin (3 seeds)...")**:
   held-out elites -0.075 on every seed, train -0.034; effects stays.
   Old text: **Ids twin: s1 read** (results doc "Ids twin s1 and distillation
   s101"): ids minus effects, r1 tight2, all -0.010 train / -0.022
   held-out, but elites -0.058 / -0.088 on both halves, hallways level.
   s101 / s201 queued (0057a8z1/z2, configs `ids5k-s101/s201.json`). Read
   the 3 seeds the same way (paired per fight vs data5k-s<seed> r1, by
   group); if elites hold at <= -0.04 on both halves, the effects encoding
   earns its keep on elites generally (not only on unseen cards).
3. **Top-3 two-turn player: no change (22:15)**: topk3 - fallback +0.005
   (se 0.009), outside 3.4%; fallback stays, no Rust filter (decisions
   "Top-3 two-turn player: no change"). Old text: (0057a8z3; decisions "Top-3
   two-turn player: test without a Rust filter"): `depth_paired.py
   --policy topk` picks two-turn's best among one-turn's top 3, no Rust
   change needed. Read rule in that decision (topk3 - fallback on held-out
   >= +0.02 -> train-half check; also read the `outside` share).
4. **Depth where it's unmeasured:** hallways held-out done: +0.025 (se
   0.009), broad (depth doc "Hallways, held-out"). **Novelty slice
   (post hoc):** net-leaf depth gain is +0.076 on held-out fights with an
   unseen power card vs +0.012 without (heuristic leaves: reverse); check
   on fresh fights queued (0057a9a5, rule in depth doc "Where net-leaf
   depth gains"). If it holds, depth is our repair for mis-priced new
   mechanics: weigh distillation on power fights and the rules-engine
   re-scope with that. Train half pc4 (0057b) still queued.
5. **Distillation: closed (20:20)**, 3 seeds negative on elites, ladder
   s201 fails (decisions "Distillation closed"). Old text: **Distillation read** (C below): s1 elites +0.020 / +0.016, s101
   -0.019 / -0.025 (ladder 0016 fail, -0.013); s201 (0057a8) decides. If
   elites gain >= +0.01 over 3 seeds, spec search-labelled data at scale
   (~100k decisions, top-k teacher); looks unlikely. Ladder s201 too.
6. **Rates under depth: rule fails (22:20)**, held-out bosses rates2 -
   thr2 +0.033 (se 0.015) vs the +0.06 bar; rates stay off (decisions
   "Rates under depth: rule fails"). Train half still running in 0057a8z4:
   read it with `scripts/analysis/rates_depth_read.py train` for the
   record (results doc section of the same name). Old text: (20:20): two-turn search closes the Guardian gap
   -0.162 -> -0.031 (3 seeds). 0057a8z4 tests rates vs thr at two turns on
   all bosses: per seed, pair `results/depth/bosses-<half>-2026-10-31-lean-rates-s<seed>-*.json`
   with the matching lean-thr file by (cell, seed), read `two` won diff
   (adapt the Guardian pairing in the results doc's newest section).
   Rule in decisions "Distillation closed; rates retested under depth".
   Old text: **Rate features, 5 seeds read** (results doc "Rate features on 5
   seeds"): Demon Form fights +0.12 to +0.17 on every boss; Guardian
   without it -0.082 train (se 0.043) / -0.052 held-out (se 0.029). Hunt
   stopped. 0057a6i (queued) plays rates vs thr r2 nets of s101 / s201 /
   s301 on train Guardian at one and two turns
   (`results/depth/guardian-train-<run>.json`); read (rates2 - thr2) vs
   (rates1 - thr1) paired by seed. Gap closes -> test rates + depth on the
   adoption rule.
7. **Oracle arm read (03:00 2026-11-01; decisions "Oracle arm read")**:
   on `gen_powers12` the oracle shows nothing (+0.001), so the gen-arm null
   is not evidence; on the new 3-copy bench (`gen_powers12c3`) +0.013 (se
   0.009, all seeds, bosses +0.064), under the +0.03 bar: the oracle is too
   diluted (43 powers). Next goal-1 step: **spec the adaptation burst** and
   use it as its own check: fine-tune the champion briefly on games holding
   one or a few generated test powers, read those powers' cells on the
   3-copy bench against the champion (pre-register a bar from the MDE).
   0057a8z8e replays gen16 / gen128 on the 3-copy bench: read with
   `gen_powers_read.py arms --bench data/bench/gen_powers12c3.json
   --control lean-thr --arms lean-gen16 lean-gen128 --out
   results/gen_powers/arms-c3.json`.
8. data80k now 2 seeds (0057a9a/b; s201 parked in `jobs/parked/`);
   lean-look 0058-0060 (pre-register Lagavulin and Nob as target slices);
   score-r0 0061.
9. Throughput (G): heuristic tight2 cache dropped, it takes ~2 min of a
   100+ min learn run (0061c log), not 10%. Left:
   fast test tier, one-torch-at-a-time token.

Older order (2026-10-31 first review), kept for detail:

A. **Round-0 scoring**: done (results doc "Round 0 vs round 1"): r1 adds
   ~+0.02 over r0, rounds stay. Left: `score_r0.py play runs/*-data*-r0-*`
   once data scaling ends, read alongside data r1.
B. **Data scaling** (item 6a, queued 0045-0057): read *paired by seed
   index* (data5k-s1 and data20k-s1 share train_seed 1001 and round0_seed
   0; check whether the 5k games are a prefix of the 20k ones), r0 and r1
   both. 80k only on a clear slope. **20k vs 5k read (r1, 5 seeds,
   paired):** train all +0.015 (se 0.004), held-out all +0.011 (se
   0.006); elites +0.033 train / +0.021 held-out; bosses +0.026 / +0.009.
   Real but about half the pilot's ~+0.03. **40k vs 20k (3 seeds, read
   14:40; results doc "Data scaling"): +0.013 train / +0.009 held-out (se
   0.004 / 0.003), bosses +0.043 both halves; the per-doubling gain isn't
   shrinking.** 80k queued (0057a9a-c); read with the same paired script
   (copy it from the results doc's table: per-seed r1 tight2 differences).
   If 80k - 40k is again ~+0.01, raise the default `n_train`.
C. **Teacher check / distillation**: 0044b read (depth doc "Net leaves
   with the fallback player"): net two-turn +0.055 (se 0.013) over net
   one-turn on held-out, gains add to the net's (0.591 vs heuristic
   one-turn 0.498), 12.7% overrides. Passed the bar: **distillation spec
   confirmed** (`docs/specs/distill-two-turn.md`, 1a44b95), built and
   merged 20e94f8 (review: one must-fix, fixed). Queued `lean-distil-s1`
   as 0049e, s101 / s201 as 0052b / 0052c (later, so they reuse s1's
   cached labels of the shared round-1 dataset instead of labelling it
   three times at once). Read: paired against `lean-thr-s*` r2
   (`lean_read.py lean-distil lean-thr`, minus by hand; `boss_lead.py`),
   plus round.json `teacher` (override share, minutes). Read 0057b (train half) when it ends.
   Interim, s1 only (not a result): distil minus thr on tight2, train
   elite +0.020, held-out elite +0.016, bosses -0.007 / -0.015, hallways
   +0.012 / +0.005; teacher 40 min per round, 21.6% overrides.
D. **Goal 1 features**: Demon Form probe done (results doc): the nets
   under-play it badly (12-17% of fights vs 65%; value -0.09 to -0.15 vs
   their best option). **Rate features spec confirmed**
   (`docs/specs/rate-features.md`, ff934a5); built and merged 1516994,
   `sts` rebuilt. Step 3 queued as 0049b-d (`lean-rates-s*`, ~110 min
   each, after data5k). Read: `lean_read.py lean-rates lean-thr` and take
   lean-rates minus lean-thr by hand (the script pairs extra arms against
   lean); tight_bosses via `boss_lead.py --nets lean-thr-s1 ... lean-rates-s201`;
   then `demon_form_probe.py --nets` on the lean-rates r2 nets. Adopt per
   the spec (held-out boss >= +0.06, train >= -0.015). All three seeds
   done; interim tight2 read under Running (held-out boss +0.055);
   tight_bosses and the probe queued 0052a1/a2. **Read 12:10 (results
   doc "Rate features"): rule fails, rates stay off; but Demon Form fights
   gain +0.10 to +0.20 (nets play it like the heuristic now) while
   Guardian fights without it lose -0.06 to -0.10, both halves; power
   timing is not the cause.** Next: the fork's decision-diff finds the
   Guardian cost; fix it, rerun 3 seeds, adopt if the rule passes
   (decisions "Rate features: off by default for now"). **Fork's hunt
   (results doc "Where the Guardian cost comes from", c01d788):** no
   column bug; the rate nets hesitate before Mode Shift (with <= 15
   damage to go they block or end turn where thr and the heuristic
   attack, 81 vs 26). Fixes to test, cheapest first: `decision_diff.py`
   on Slime Boss near its split (threshold-row learning?), then a
   damage-to-threshold feature; or play the rate nets with two-turn
   search on these fights (does depth remove the hesitation?). **14:30:
   first, more seeds** (decisions "Rate features: more seeds before a
   Guardian fix"): the 3 seeds disagree (-0.00 / -0.20 / -0.12), so
   s301/s401 of both arms run (0057a6a-d) and 0057a7a reads boss lead.
   Read the 5-seed Guardian diff from `lead-lean-rates.json`,
   `lead-lean-thr.json` (check they exist) and `lead-rates-seeds2.json`;
   tight2 from round.json. Below -0.05: hunt the fix; within ~1 se of 0:
   apply the spec rule on 5 seeds. Also: lookahead test queued 0058-0060; lean-thr read: no transfer (results doc "Threshold rows").
E. **Generated power mechanics: read 16:35, no transfer** (results doc
   "Generated-power training arms"; decisions "Generated-power arms: no
   transfer"): gen128 -0.006 (se 0.010), gen16 -0.004 vs lean-thr on
   unseen generated powers; content stays out of the recipe (it costs
   ~0.04 on elites). Next goal-1 step per the spec: per-mechanic features
   plus an adaptation burst (short fine-tune on a new mechanic's games);
   spec after the 16:40 big-picture review. Detail of the old item:
   Registry-lite + generated power mechanics: built and merged
   (0e0046a). First check: the heuristic is a weak yardstick on generated
   cards. **Training-arms spec confirmed and steps 1-3 built**
   (`docs/specs/gen-training-arms.md`, 2edd871..7a70743): arms
   `lean-gen16-s*` / `lean-gen128-s*` (lean-thr + 16 / 128 generated
   train powers, share 0.5, night round 0), control = lean-thr r2; queued
   0057a1-a6 (128 arm first). 12-fight bench `data/bench/gen_powers12.json`;
   control nets' play queued 0051b. **Step 4 (when 0057a* end):** queue
   `gen_powers_read.py play --bench data/bench/gen_powers12.json --threads
   4 --nets <the six lean-gen r2 run dirs>` (~2 min per net), then
   `gen_powers_read.py arms --bench data/bench/gen_powers12.json --control
   lean-thr --arms lean-gen16 lean-gen128 --out
   results/gen_powers/arms.json`, plus `lean_read.py lean-gen16
   lean-gen128 lean-thr` and `boss_lead.py`; decide per the spec's rule,
   write results doc + decision, fold the spec (note: `play` saves under `results/gen_powers/arms/<bench name>/`; review optional items in the log line). Pricing (not from
   `hook_rates`) stays a later item; Metallicize cells are contaminated.
F. **Yardstick and seed selection**: novelty slices in the read scripts;
   paired HP lost at run-realistic HP; held-out non-inferiority in the
   ladder; ladder-test the best lean r2 / cover21 r1 / data r1 nets
   against the champion (minutes each).
G. **Throughput**: keep >= 6 h queued; a disk cache for the heuristic's
   tight results. This file slimmed 10:03 (Log, old Running and items 0-9
   moved to `docs/manager-archive.md`); Next A-E could be trimmed next.
   Memory, not cores, now stops jobs (two OOM deaths and one hang today):
   size `--mem-gb` honestly for two-turn teachers (~1.4 GB per worker).
Stop (review): label / cap / frontier / curriculum-round / loss variants
under one-turn search; recipe comparisons with expected effect < ~0.02
(shared round 0) or ~0.03 (fresh); broad heuristic-leaf depth runs after
0038/0039; acting on any reading > 0.05 before an artifact hunt.

Older ranking (2026-10-30) with items 0-9 in full (warm start, job queue,
ladder, depth history, lean loop, mechanics, bosses, lookahead, gauntlet,
relics): `docs/manager-archive.md`. Its rules still hold: report by fight
type, keep train and held-out apart, state each experiment's MDE
(~2.8 x seed sd x sqrt(2/seeds); seed sd ~2x bigger with fresh round 0s),
never call a single-seed pass a result.

Housekeeping: `HANDOFF-exact-solver-curriculum.md` is stale (2026-10-27);
`NIGHT-REPORT.md` is from 2026-10-26; branch `cloud-gpu-test`
(scratchpad worktree, pushed to origin) is left over. Check each before
removing.

### Log

One line per manager run: date, time, session, what happened.

Older lines: `docs/manager-archive.md`.

- 2026-10-31 00:07-01:45 sts-manager 94bb52f5: took the free lock. Read the coverage pilot (4/10/21 kinds: held-out -0.074/-0.039/-0.025; fresh-round-0 seed sd ~2x the old figure; 20k vs 5k round 0 ~+0.03), so generated content moves up and a data-scaling run is queued (0045-0057). Merged threshold-rows (ad17de2) and monster-lookahead (a57f338, built by a fork, review clean), rebuilt `sts`, fast suites pass. Ran the big-picture review (`docs/research/big-picture-2026-10-31.md`), re-ranked Next (A-G). Queued 0040-0060 (~14 h): slow suites, round-0 scoring, lean-thr, data scaling, lean-look.
- 2026-10-31 04:06 sts-manager (scheduled): lock held by cfd4b2bf (heartbeat 04:10, session active 04:04, its fork editing registry-lite step 5), stood down. Runner alive, 0044b running since 03:29.
- 2026-10-31 06:06 sts-manager (scheduled): lock held by cfd4b2bf (session active 06:06, rate-features step 2 committed 06:01), stood down. Runner alive, 0047/0048 running, nothing crashed.
- 2026-10-31 02:07-06:30 sts-manager cfd4b2bf: Read 0038/0039 (fallback player), 0041b (rounds stay), 0041c (Demon Form probe: nets under-play it), 0044b (net-leaf two-turn +0.055 held-out), 0042-0044 + 0044c (threshold rows: no Guardian transfer). Specs confirmed and built by forks, reviewed, merged: registry-lite (0e0046a, first check: heuristic a weak yardstick on generated cards), rate features (1516994), distillation (20e94f8). Queued 0049b-d (lean-rates), 0049e/0052b/0052c (lean-distil). Three orphaned `find.exe` processes burn 3 cores; stopping them was refused (For the owner).
- 2026-10-31 08:02-08:35 sts-manager a2a020e7: took the free lock. Found 0049e (distillation) hung after its teacher workers ran out of memory and 0049d (lean-rates s201) dead from the same pressure; stopping 0049e was refused (For the owner). Fixed the hang (75b16fe, 48108eb), requeued 0051a / 0052a, 0057b at 4 workers. Generated-power training-arms spec confirmed (2edd871) and steps 1-3 built (6df8bb7, 7a70743); arms queued 0057a1-a6, control play 0051b. Review: no must-fix; optional: `read --limit` still cuts by 4 fights on other benches, `arm_won` picks the last-sorting hash if a name has two r2 runs on one date.
- 2026-10-31 10:03-10:25 sts-manager 9958cbf1: took the free lock. 0052 (data20k-s201) died out of memory; 0049e still hung (kill refused again). Interim reads: lean-rates beats lean-thr on held-out bosses by +0.055 on tight2 (bar 0.06), data20k beats data5k by ~+0.017 train on two seeds. Queued and moved to the front 0052a1 (lean-rates tight_bosses), 0052a2 (Demon Form probe), 0052a3 (0052 rerun). Slimmed this file into `docs/manager-archive.md` (Next G).
- 2026-10-31 10:35-11:25 setup session bc0daa80 (owner present): ended 0049e (owner's go-ahead); hang and memory review (6 lenses, 30 findings, verified, 7 must-fix) and fixes in three worktrees, each reviewed clean, merged 0e0a3ff; sts rebuilt, runner restarted on the new code. Optional review items listed in decisions "Hang and memory fixes". Lock released.
- 2026-10-31 12:07-12:45 sts-manager 7328b322: runner alive, took the free lock. Read lean-rates (rule fails, rates off; Demon Form fights +0.10 to +0.20, Guardian without it -0.06 to -0.10) with a proper lean-thr control probe (0054z3) and a power-timing probe (0054z4, ruled out); a fork's decision diff (c01d788) found the rate nets hesitate before Mode Shift. Read data20k vs data5k (5 seeds: +0.015 / +0.011). Interim distil s1. Queue: data40k mem 11 -> 5 GB, distil s101/s201 moved ahead as 0057a7/a8 (6 GB), r0 scoring queued (0061-score-r0). Deleted the stale `.pyd.old`.
- 2026-10-31 14:02-14:50 sts-manager (scheduled): runner alive, find.exe orphans gone, took the free lock. Read data40k (3 seeds): +0.013 train / +0.009 held-out over 20k, slope holds; queued data80k (0057a9a-c) and added 40k r0 nets to 0061. Queued 2 more paired seeds of lean-thr / lean-rates (0057a6a-d) + boss lead (0057a7a) to test whether the Guardian cost is real before a fix. Heavy paging at 14:00 from another project's build.
- 2026-10-31 16:07-17:10 sts-manager bb961751: runner alive, took the free lock. Read the gen-power arms (no transfer: gen128 -0.006, gen16 -0.004; content stays out), ran big-picture review 2026-10-31b and re-ranked Next; ladder of 12 newer nets (all lose to the 10-29 champion, lean/data40k ~0.01 weaker than the night recipe); rates on 5 seeds (Guardian cost -0.08 / -0.05, hunt stopped, depth test 0057a6i queued); a fork's two first checks (both bars fail; top-3 overrides lower puzzle regret). Queued ids twin, hallway depth; data80k to 2 seeds; 0057b to 4 per cell.
- 2026-10-31 18:07-18:50 sts-manager c3a3a6dc: runner alive, took the free lock. 0057a6i (Guardian depth) failed: tight2 has no Guardian; added `depth_paired.py --bench` and requeued (0057a8z). Read hallway depth (+0.025 held-out), ids twin s1 (elites -0.06 / -0.09; s101/s201 queued), distil s101 (null; ladder fail -0.013). Added `--policy topk` (no Rust filter needed) and queued the top-3 test; post hoc slice shows net-leaf depth gain sits on unseen power cards (+0.076 vs +0.012), check on fresh boss fights queued.
- 2026-10-31 20:07-20:45 sts-manager 44869c1c: runner alive, took the free lock. Read ids twin 3 seeds (effects beats ids on held-out elites -0.075), distillation 3 seeds (closed; ladder s201 fails), Guardian depth (two-turn closes the rates gap +0.13 on all seeds). Queued rates-vs-thr two-turn on all bosses (0057a8z4, front, 2 GB) and the oracle arm (new `content_split` key, test passes; 0057a8z5-z8). Dropped the heuristic cache (2 min per run).
- 2026-10-31 22:07-23:02 sts-manager 5cbfc037: runner alive, took the free lock. Read topk3 (no change, fallback stays) and rates under depth (held-out +0.033 vs +0.06: rates stay off; train half for the record). Ran the prior-art scan on search in stochastic card games (8 scouts, 7 sources verified; checked two-turn search can't see draw order). Confirmed and built the ensemble evaluator spec (4fda986, fecd817; review: one must-fix, fixed, clean); ladder ens3 fails (+0.002); two-turn ens3 queued (0057a8z9). Optional review items: gen_powers_read.py / boss_lead.py don't take `+` specs; an ensemble member with `+` in its path is misread; README evaluator lines not updated.
- 2026-11-01 02:06-02:20 sts-manager fb4fed6b: runner alive. Lock of 048566e9 stale (session gone ~00:30, last edit 00:11): took it, committed its oracle tight2 side read. Checked 0057a8z9 "STALLED" flag: false alarm, workers busy. Added the ensemble `+` spec to README (review optional item). Nothing else unblocked: all reads wait on running or queued jobs (~8 h queued on two slots).
- 2026-11-01 00:02-00:30, 02:10-03:08 sts-manager 048566e9: runner alive, took the free lock (lost it to fb4fed6b while waiting on 0057a8z9, retook it 02:12). Requeued the oracle play (0057a8z8 failed: no `ls` in the runner's bash). Wrote `sample_agree.py` and read it (k4 fine; gap gate saves little; 54% of decisions tie at the top). Read ensemble two-turn (+0.008, no change; spec folded), oracle on gen_powers12 (+0.001: bench blind) and on a new 3-copy bench (`build --copies`; +0.013), data80k s1 interim and ladder (fail -0.018). Queued gen arms on the 3-copy bench (0057a8z8e).
- 2026-11-01 04:07-05:25 sts-manager 68e81bce: runner alive, took the free lock. Read: depth novelty check passes (+0.096), train-half depth +0.035, data80k = 40k (scaling stops), gen arms on 3-copy bench match the oracle, lookahead off. Ran big-picture review 2026-11-01 (stop list, Next re-ranked). Built and merged: adaptation burst (finetune generated content), ladder v2 (cached champion, fixed-n, run-HP; review must-fix fixed), hp_weight (review clean); selective depth fails its check (branch kept). Results: nets lose ~2x the heuristic's HP at run HP; burst8 beats the champion (control fails) and was promoted. Queued: run-HP of new champion, train-split bursts, hpw arms (~4 h).
- 2026-11-01 06:07-07:39 sts-manager 5f767652 (line written by 4440e145 from its message): promoted burst8hp2 s1, added `runhp --two-turn`, closed the burst work for the ladder (ratchet, 16/32 cards level), had a queue-rename incident (fixed, no data lost); queued 0059h1/h2. Left the lock set without a Log line.
- 2026-11-01 08:07-10:05 sts-manager 4440e145: runner alive; took the lock from 5f767652 (idle since 07:39, not running). Read run-HP at two turns for burst8 s1 (-0.55) and the HP-weighted champion (+0.59): depth is not the HP lever. New `tempo_probe.py`: the hallway gap is under-blocking, not tempo, so N1 is now an `unblocked_incoming` feature spec. Adaptation burst rerun (game_seed 41, new `burst_rerun.py`): contrast +0.027, between again, closed. Added `gen_powers_read.py depth` (two-turn on the generated bench; workers load the pack); its first job died on a read bug, fixed and requeued (0059l3), heuristic control 0059l4. Runner STALLED flags on run-HP jobs were false alarms.
- 2026-11-01 10:07-11:15 sts-manager 1474ae6a: runner alive, took the free lock. Found why the nets bleed HP: no start-HP column, so their HP price in hallways is 1/10-1/100 of the label's (new `hp_price_probe.py`); dropped `unblocked_incoming` (leaves are after End turn). Built the `start_hp` encoder option (spec start-hp.md, tests pass), queued 4 arms (0059l5-l8). Search HP bonus (`NetEvaluator hp_bonus`, spec `<net>.pt@hpb<c>`): +2.75 / +2.80 HP saved (same / fresh fights), ladder -0.0012: promoted as champion. Queued two-turn run-HP with the bonus (0059l9).
- 2026-11-01 12:07-12:35 sts-manager f3fd4dee: runner alive, took the free lock. Depth-on-generated-powers jobs (0059l3/l4) stuck on Slime Boss at two turns (slow, not hung); interim: depth gains +0.10 on generated and original alike (contrast -0.005). Per-encounter run-HP: the gap left after the bonus is Lagavulin and Nob. Built the Act-1 gauntlet (spec, 2 steps, review: one must-fix test, fixed; e0929df..564f1fd) and `start_hp_read.py`. Prior-art scan on outside yardsticks (8 scouts, 3 sources verified; fad5da3): owner decision on the full-game simulator added. Queued: control twins + bonus (0059m1-m4), gauntlet first check (l4a/l4b) and HP-price sweep (l4c-l4f).
- 2026-11-01 14:06 sts-manager (scheduled): lock held by bc0daa80 (survival-score step 1 committed 14:03 in its worktree), stood down. Runner alive: 0059l4b running, l4a and l3 ended ok 14:02-14:04; 0059l4 STALLED flag is the known false alarm (Slime Boss at two turns).
- 2026-11-01 12:50-16:05 bc0daa80 (owner present): enemy-HP randomization researched and rejected as a label source (`docs/research/random-enemy-hp-2026-11-01.md`). Owner's design: the net predicts HP lost from now (switch-6 histogram), search scores a win c + w x end HP / 100 (survival worth a constant c). Spec `survival-score.md` built (5d13285..3d7048e: labels heal fix, Python and Rust score rule, search terminal rule, `@sc`, lean-surv configs, smoke; review: 1 must-fix fixed, Python callable evaluator carries the rule), merged, sts swapped (wheel from the branch). Arms 0061/0062 queued with chained run-HP. `test_hp_bonus.py::test_player_spec` fails on main independently (the champion string already ends in `@hpb0.01`). jobs.py kill allowed for managers. Lock released.
- 2026-11-01 16:06-17:20 sts-manager c6495ce4: runner alive, took the free lock. Queue was idle on memory (behind a 5 GB job): moved small jobs first. Read the gauntlet first check and c sweep (c 0.01 stays; level with the heuristic, pooled +0.018 se 0.011), found the bonus feeds Gremlin Nob (`nob_probe.py`), read the start-HP arms (column passes its rule but = the bonus; stays off, s101 parked) and depth on generated powers (not content-specific). Ran big-picture review 2026-11-01b and re-ranked Next. Forks: runner peak memory (merged f753339, runner restarted), GSPRT replay (no verdict changes). Built the enemy-Strength price (spec confirmed; review: 2 must-fix fixed): fixes Nob, fails at run level (-0.020). Queued: two-turn run-HP, two-turn gauntlet, survival arms.
- 2026-11-01 18:12-19:25 sts-manager 86979d83: runner alive, took the free lock. Read two-turn run-HP with the bonus (0036): -0.39 HP vs one-turn + bonus, hallways -0.93, elites +1.46. Cause: finished combats score with the engine's floored score (heal 6 makes up to 6 HP free in a won fight) and no bonus. Spec end-hp-bonus.md confirmed and built (`@hpe<c>`, 9c790b5; review: one must-fix test added, survive refusal); one-turn `@hpe` level with `@hpb` (0037). Split the 6 GB two-turn gauntlet into two 3-thread halves (0059l7r3a/b, running); queued two-turn `@hpe` run-HP (0059l7r3a2). Deleted the old-esp .pyd.
- 2026-11-01 20:07-22:10 sts-manager 9623e125: runner alive, took the free lock. Two-turn gauntlet halves 0059l7r3a/b still running (STALLED flags are the known false alarm: workers busy). Worked Next (3), profiling a two-turn decision: py-spy on a symbol build plus a timed Rust example (`two_turn_phases.rs`) showed half the time in SipHash over 1 KB states and table growth, the rest in leaf scoring, with 10% of decisions taking 88% of the time (three_louse). Built and merged two exact speedups (specs confirmed, folded): Fx hasher for search tables (f7bbe85) and a per-call net layer cache + encoder reserve (f2b42a9); review clean; bit-identical; net-leaf two-turn ~1.9-2x faster; `sts` swapped twice. Known `test_hp_bonus::test_player_spec` failure unchanged.
- 2026-11-01 22:07-22:40 sts-manager (scheduled): runner alive, took the free lock. Read the two-turn `@hpb` gauntlet (+0.024 vs one-turn, se 0.016; under the bar; elites up, bosses level). Post hoc slice of the generated-bench depth read: novelty cost sits on turn-start powers (past the one-turn leaf), depth repairs it (+0.20 over card-played, card se 0.098); built a fresh-fight bench (`build --first --pick-seed`) and queued the pre-registered replication (0061). Queued the Silent number (0059l7r3a3-a6) and the `@hpe` two-turn gauntlet halves (a7/a8, park if r3a2 fails). Deleted the old .pyd files. A fork built the heuristic rate cache (5.1x on heuristic-leaf two-turn, bit-identical; spec-reviewer clean), merged a1c4788, `sts` swapped 22:52; queued the heuristic two-turn gauntlet anchor (0062).
- 2026-11-02 02:06 sts-manager (scheduled): lock held by c3513fb5 (commit 02:03, its fork editing `rollout_probe.py` 02:05), stood down. Runner alive (0059l7r3a9 and b25 running, nothing crashed; b1's failure already handled).
- 2026-11-02 00:07-03:20 sts-manager c3513fb5: runner alive, took the free lock. Reads: two-turn `@hpe` run-HP passes (+1.41 HP per hallway) and its gauntlet passes (0.676 vs 0.616, +0.060; the product player now); Silent number (pooled level one turn deep, +0.040 two turns; Poison decks: depth +0.32 on elites); horizon replication passes (+0.274); the 10-29 net beats the burst8hp2 champion on the gauntlet (0.640 vs 0.616), so training since 10-29 didn't reach run level; rollout ceiling probe 7 / 117. Ran big-picture review 2026-11-02 (re-ranked Next R1-R9); adopted the gauntlet protocol (sequential end-HP + clears guard, `gauntlet_protocol.py`). Fixed: heuristic two-turn gauntlet guard (the anchor had failed unnoticed), `test_hp_bonus` champion string. Built: `--one-turn-floors`, rollout probe (fork), card rewards (spec confirmed, fork, review clean). Queue reordered several times (rename-ahead); deleted `.pyd.old-hrc`.
- 2026-11-02 04:07-06:20 sts-manager 61d75983: runner alive, took the free lock. Built gauntlet early stop (--block, --against; spec gauntlet-early-stop.md, review clean; real check passes: pass at n 149, rows byte-equal, 1.5 min) and runner backfill (R8 part 1, review clean; runner restarted 04:17). Fork built the bias audit (R5): leaf under-prices enemy Strength ~4x, Poison 2-6x. Reads: heuristic two-turn anchor first half (0.612 vs product 0.648), 10-29 net two-turn passes vs product (+2.37 HP; confirmation b38a/b queued), card rewards starter skip/random/sim. Let the heartbeat go stale while waiting; 75ea2a19 took the lock at 06:07. (Line carried by 75ea2a19 from its message.)
- 2026-11-02 06:07-06:50 sts-manager 75ea2a19: runner alive; took the lock (61d75983 idle since 05:44, carried its hand-over). Read card rewards (starter sim - random +0.184, pass; spec folded), built `--sim-boss` (spec confirmed, review clean) and read it (pass at n 162, +0.155 clears: new headline setting), read the 10-29 bias audit (prices Strength/Poison worse than the champion). Ran big-picture review 2026-11-02b, re-ranked Next (Q1-Q7). Queued seed twins b37d-f; parked b4.
- 2026-11-02 08:07-08:35 sts-manager 96fa2906 (line written by 14d5db36 from its commits): read run-level seed noise (twins) and run value by floor (Q4, flat price stays), confirmed and built the rest-site chooser (90a8ad5), queued its read, the Q2 anchor and the Q1 re-rank; left the lock set without a Log line; also left five `git log` lines at the end of this file (removed).
- 2026-11-02 12:07-12:35 sts-manager 158afb00: runner alive, took the free lock. Queue had idled 1 h on memory: headline halves b39a/b resized to 2 thr / 3 GB, both running. Reads: card removal (strike +1.78 end-HP over none, chooser fails vs strike -1.41: removes reward cards; closed) and mixed depth (level, 81 vs 142 min; screening default). Spec'd and built elite-skip (6669be1, review clean, 20 tests); queued its two reads and Q6 (one turn light, two-turn s1 twins).
- 2026-11-02 10:07-10:30 sts-manager 14d5db36: runner alive; took the lock (96fa2906 stale). Reads: 10-29 net two turns confirmed on 500-749 (+3.0 end-HP, z 4.1) -> product net; rest-site fails (winner's curse), closed; re-rank: no newer net beats 10-29, tight2 mis-ranks; heuristic headline anchor 0.534 vs net one turn 0.680; thread scaling (8 thr ~ 3 thr). Card-removal spec confirmed, fork built it (review clean), merged d92fa04; queued its reads (b2z3) and the Q2 headline halves (b39a/b).
- 2026-11-02 20:07 sts-manager (scheduled): lock held by 2b40a321 (commit 19:57, two `jobs.py wait` processes since 19:57 waiting on d2), stood down. Runner alive (pid 5148): d2 (100/60 min, log live), l8b4 and l8c running, l8b pending; last ten jobs ended ok, nothing crashed.
- 2026-11-02 18:07-20:25 sts-manager 2b40a321: runner alive; took the lock from 3a78b41d (stale, 16:20) and committed its b39abb read. Later reads this run: crossed chooser arms (the chooser holds ~0.09 of the 0.156 one-turn lead), run-value chooser (fails, L2 b closed), mutated monsters stage A one turn (SharpHide on new enemies -0.05 to -0.09, stat changes cheap; two-turn subset l8b4 running), line seed (pass), headline re-rank (no net near the 10-29 net; headline = final ruler). Killed l8c (mixed depth) at 20:15 to free the heavy slot for the survival arm l8b; requeued as l8e. Lock released 20:25. Reads: Q6 two turns (search takes over most of the encoding's edge on unseen cards, +0.059 -> +0.017), mixed depth on the headline (protocol stop at n 50, level so far; fixed-n continuation 0059l8c queued; decision "Cost-saving candidates are read at fixed n"), boss replays (L2 a, spec + build + 7-min run + read in one go: the boss curve is causal, share 0.87, per boss; spec folded). Built: `--chooser` (cheap read 10, arms queued d3), the run-value chooser (L2 b, spec `run-value-chooser.md`, check queued d4), mutated monsters stage A (L4, spec `mutated-monsters-a.md`, runs queued l8b3 / l8d). Queued the standing-players re-rank (cheap read 4, d2). 0059l8a (survival s1) ended ok 18:37, l8b next.
- 2026-11-02 16:10-16:20 sts-manager 3a78b41d: took the free lock, read b39abb (effects vs ids / lean / lean-thr at run level) into the results doc, then ended without committing, a Log line or releasing the lock (committed by 2b40a321 at 18:45).
- 2026-11-02 14:07-14:35 sts-manager 837a5e68: runner alive, took the free lock. Reads: the Q2 two-turn headline (0.804 vs 0.680 one turn, +0.124; vs heuristic 0.534), Q6 one turn (effects minus ids +0.048 generated / +0.154 original elite+boss), approach-review step 0 for the fitted run value (floors 6-8 pass the 3x slope gate on the headline file, floor 5 fails), elite-skip ceiling (pass at n 50, +19 HP at the boss). Re-ranked Next from the owner-requested approach review (L1-L5). Spec line-seed confirmed and built by forks (b4dd041, 7bdc104, 429ba94; probe: first tree ~60% of a turn's two-turn cost); spec-reviewer 14:40: clean, optional: no test of --line-seed with --against, the seeds test doesn't assert a multi-search turn, an unused loop variable in line_probe.pick, README states the probe's number. Queued: ten cheap one-turn reads (b39abb), the line-seed read (b39b1), mixed depth on the headline (b39b2); renamed them ahead of the Q6 two-turn jobs and survival arms. Re-took the lock 14:33 for the elite HP-rule read (hp rule +1.5 HP, pass at n 83; ceiling +14 HP; spec folded; headline unchanged); lock released 14:40. Note: the Q6 two-turn jobs (c1, c2) took both heavy slots at 14:32 by memory backfill, so b39b1 / b39b2 wait behind them (~5 h) unless a slot frees or their mem_gb is lowered.
- 2026-11-02 21:48-21:52 lanes-runner-ee6762 (build session, owner present): lanes runner step 1 (frozen wrapper, exit files, lanes.json, backfill event) merged 12063ab; runner restarted 5148 -> 27204 with no job running (0059l8b pending, waiting for free memory), so no exit codes lost; the last restart that could lose them. Lock taken and released.
- 2026-11-02 21:57-21:59 lanes-runner-ee6762: lanes runner step 2 (lanes, shares, protected head, `first`, peak reservation, half slots, status by lane) merged f58998b; runner restarted 27204 -> 20848, no job running (0059l8b still pending on free memory). Lock taken and released.
- 2026-11-02 22:04-22:04 lanes-runner-ee6762: lanes runner step 3 (conditions, check processes, verdicts, set, unpark) merged b5dc8c5; runner restarted 20848 -> 17344; jobs running at the restart: none (their exit codes survive through the wrapper's exit files). Lock taken and released.
- 2026-11-02 22:07-22:07 lanes-runner-ee6762: lanes runner step 4 (filler lanes (share 0): only when nothing else started, within the reservation) merged a864747; runner restarted 17344 -> 3004; jobs running at the restart: none (their exit codes survive through the wrapper's exit files). Lock taken and released.
- 2026-11-02 22:07-22:30 sts-manager 19428521: runner alive (pid 3004, restarted by the lanes-runner session, which merged steps 1-4 beside this run), took the free lock. Reads: mutated monsters two-turn subset (depth removes the one-turn net's SharpHide cost: horizon, no burst; spec folded) and mixed depth on the headline at fixed n (level by the bar, -0.012 clears; screening default on the headline, headline reads keep full depth). Queued light: lean s1 one-turn headline check (0061, running), retuned pairs (0062, done and read: SharpHide 1 + HP x0.9 near the parent; `--mods` added to mutate_monsters.py, tests pass). 0059l8b's mem_gb 6 -> 3.5: it could never start at 6; it started 22:21. pytest is not in the venv; the system interpreter over the venv's packages runs the tests (Machine limits). Also read 0061 (lean s1 one turn on the headline: -0.052 clears / -2.5 HP vs the 10-29 net, 1.5-2 se, all boss deaths; the solve step may matter under rewards) and queued the seed twins (0063) to settle it. Lock released.
- 2026-11-02 22:29-22:29 lanes-runner-ee6762: lanes runner step 5 (jobs pinned by default to snapshots under sts-builds, pins, unpin, 24 h sweep) merged 94dfc0d; runner restarted 3004 -> 29488; jobs running at the restart: 0059l8b-bash (their exit codes survive through the wrapper's exit files). Lock taken and released.
- 2026-11-02 22:37-22:37 lanes-runner-ee6762: lanes runner step 6 (final code: impact, docs) merged 776fb90; runner restarted 29488 -> 30900; jobs running at the restart: 0059l8b-bash, 0063-bash (their exit codes survive through the wrapper's exit files). Lock taken and released.
- 2026-11-02 23:16-23:26 kb-adoption-5acbb5 (owner present): kb claims store on (docs/specs/kb-adoption.md stages 1-3; 84 facts, STATUS.md at session start, configs/product.json, spec Status lines); manager runs record facts beside this file (Each manager run steps 2, 4; Next K). Probes P1-P3, S1-S2 pass (spec "Probe results"); stage 4 waits for a week of kb stats and the owner. Found: gauntlet.py --against doesn't check depth or setting.
- 2026-11-03 00:07-01:15 sts-manager caf615f4: runner alive, queue empty, took the free lock. Read 0059l8b with l8a (survival arms fail: tight2 -0.06, under the bonus by ~0.9 HP; c sweep flat; spec folded) and 0063 with 0061 (solve step at run level pooled -0.032 clears, se 0.021: between the verdicts, left to the owner). Landed engine-next (merged main in the worktree, one decisions.md conflict; cargo tests and series_check green; ff c3f81f4; sts swapped from the branch wheel; worktree unregistered, its target/ folder left busy). kb: 7 facts set, 2 retired, 4 cascade suspects re-set, uptake baseline. Spec line-step (line seed stage 2) confirmed 63652fe and built by two forks (c2a326e, 7adb302), spec-reviewer: 2 must-fix (one fixed 9780a94, one resolved by the fold), 4 optional; probe: identity exact, cost 0.70 (bar 0.65 missed, reads go ahead); specs folded b8a7632; reads queued 0064 / 0065 (lane depth); idea #80. Fast suites (228 tests) pass on the new module. An owner-approved merge landed meanwhile (gauntlet --against settings check, --vary; 6717bfd). Left: the engine-next worktree's target/ folder (1.2 GB) still refuses deletion.
- 2026-11-03 08:07 sts-manager (scheduled): lock held by 691c5c04 (heartbeat 08:06, step 2 of two-turn-round committed 08:04, step 3 in a fork), stood down. Runner alive (pid 30900): 0066 running (300 / 500 sequences at 33 of 75 min, peak 3.7 GB), last ten jobs ended ok, nothing crashed. Log line left uncommitted for the lock holder.
- 2026-11-03 07:25-08:40 sts-manager 691c5c04: runner alive, queue empty, took the free lock. Read 0064 (row-identical to stage 1, 544 floors) and 0065 (line step on the headline at fixed n 250: level, end-HP +0.04, clears -0.016, ~0.55 of the wall time): pass; `--line-seed --step-line` is the two-turn play mode (product flags, decision, facts; 27 cascade suspects re-confirmed); queued 0066 (stepped headline file to 500 sequences). kb uptake since 11-02: 23 sessions, lookups 20, re-opens 799. Spec two-turn-round (L6) confirmed and built by three forks (582dcd6, 8c51dd3, d3c6b75; spec-reviewer: no must-fix, 5 optional), folded f41b94c; jobs 0067-0071 queued in lane train (0067 running: 7.2 stepped fights per thread-minute, ~140 min). The owner-confirmed operating-model build (session local_fb127636) landed steps 1-2 on main beside this run and was told about L6; its cut-over archives this file. No big-picture review (last 14:25 11-02; the navigator's first run covers it). Full suite not run (two heavy jobs on); fast suites the build touched pass. Lock released.
