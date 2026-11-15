# Lanes runner: shares, conditions, filler jobs and pinned code for the job queue

Status: closed (2026-11-02, built and in use; steps 1-6 in use: decisions "Lanes runner as built").

The owner asked for lanes for work on different time scales, one runner
that keeps the CPU busy without waste, jobs that a change can't break,
and coordination before a breaking change lands.

## Why (both goals: machine time is the bottleneck)

The runner (`scripts/jobs.py`) starts jobs in file-name order, with backfill
when the head job waits for memory. Measured over its life (10-30 12:25 to
11-02 21:14, 80.8 h):

- **Booked threads were 49% of 16** (630 thread-hours), 35% on 11-02. CPU was
  rarely the limit: the runner saw 8-10 idle cores before a typical start.
  Memory and the 2 heavy slots were. Two 2-thread two-turn jobs held both
  heavy slots for 139 min with 4 threads busy (11-02 14:46-17:05). There were
  307 zero-job minutes, mostly waiting for a manager.
- **Order is set by renaming files.** 216 of 277 job ids carry hand-inserted
  suffixes. The survival arm `0059l8b` has waited 29 h. Backfill passed it
  four times in 40 minutes, and a kill meant to free room for it was refilled
  by backfill in the same poll, 38 minutes into its wait.
- **Conditions between jobs live in notes.** "Park a7/a8 if a2 fails" was
  never applied: a7 started the second a2 ended, an hour before any manager
  read a2. 14 jobs are `bash -c "A && B"` chains standing in for "run B only
  if A passed".
- **Code changes under queued jobs.** `sts` was swapped about 15 times in 3
  days, and a rebuild once left it missing for a minute: two jobs died on
  import. 27 commits touched scripts, engine or py between `0059l8a` being
  queued and started. The engine-next landing has waited 5.6 h for jobs,
  because main's new scripts with the old module could crash a job.
- **A runner restart loses running jobs' exit codes** (`ended-unknown`), so
  no condition on such a job can be decided.
- **Declared memory is often too low.** 18 of 62 jobs with a measured
  `peak_gb` went over their `mem_gb` (up to +1.2 GB), and admission reserves
  `mem_gb`, not the peak.

How we'll know: booked thread share and zero-job minutes per day before and
after (from `jobs/done` and `runner.log`); no manual rename to reorder; no
job broken by a swap or landing; a landing that doesn't wait for running jobs.

## Outcome

`jobs.py` gains:
- exit codes that survive a restart, through a frozen wrapper;
- lanes with shares;
- protection for a waiting head job;
- memory reserved by measured peaks;
- conditions decided by a check process;
- `set` and `first` for pending jobs;
- a filler lane;
- jobs pinned to a snapshot of the code and module they were queued with;
- an `impact` command for unpinned jobs.

Not in this spec: filler preemption, and the `needs`/`about` fields for the
claims store. Both are deferred; see Decisions. Lane charters and the
manager's cadence are the owner's arrangement (see "For the owner").

## Behaviour

### 1. A frozen wrapper and exit codes that survive a restart
- At `run` start the runner writes `jobs/runner-<pid>/exec.py`, a
  standalone script from a string constant. It has no imports from
  `scripts/`, and its argv is fixed across versions: `exec.py <exit file> --
  <cmd...>`. It runs the command (same cwd, env and log handles) and writes
  the exit code to the exit file, via temp file and rename. Then it exits
  with that code. An edit or merge of `jobs.py` while the runner runs can't
  break a starting job.
- `spawn` deletes any stale `running/<id>.exit`, then starts `[python,
  exec.py, running/<id>.exit, "--", *cmd]`. The Job Object, kill and
  tree-memory code are unchanged: the wrapper is part of the tree.
- `_end` and adoption read the exit file. An adopted job ends `ok` or
  `failed` with its code. A dead tree with no exit file ends
  `ended-unknown`, as today. `_finish` deletes the exit file.
- Backfill and every lane choice are logged as their own events through
  `q.event` (today the "ahead of" text is added after the line is written).

### 2. Lanes, shares and a protected head
- Job field `lane` (default `main`); `add --lane`. Shares come from
  `jobs/lanes.json`, read each poll inside try/except (OSError, ValueError,
  TypeError). On a bad file the runner keeps the last good shares and logs
  `lanes-bad` once. Missing lane: share 10. Share 0 or below: filler
  behaviour (§4).
- **Use.** A lane's use is the dominant share of its running jobs: for each
  job, the larger of threads / thread budget and reserved memory / (total
  memory − 1 GB), summed over the lane. Lane heads are tried in order of
  lowest use / share (ties by name). The first that `_admit` accepts starts,
  one start per poll. Within a lane, order is name order.
- **Protected head.** When the top-ranked lane head is refused, for any
  reason except "never", it gets a reservation once it has waited
  `RESERVE_MIN` (default 10 min, one wait clock across reasons). While it
  holds the reservation, another job may start only if it fits alongside the
  head: after that start, the head would still pass the thread budget, the
  slots and reserved memory (`reserved + its own + head ≤ total − 1 GB`).
  Idle CPU and free memory aren't counted, since they change. Backfill
  inside the head's lane follows the same rule. After 30 min of waiting the
  runner logs a `waiting` event, which wakes `wait`.
- `jobs.py first <id>` gives a pending job the reservation at once and puts
  it first in its lane. This replaces renaming.
- **Memory.** A running job reserves `max(mem_gb, peak_gb)`. `add` warns,
  and records `mem_gb_low`, when `mem_gb` is below the last `peak_gb` of a
  done job with the same script and the same first argument.
- **Slots.** `heavy_slots` stays 2, but a heavy job with 2 threads or fewer
  counts as half a slot. So two 2-thread jobs no longer fill the machine,
  while memory gates as before.
- `status` prints each job's lane, reservation and parked reason, and each
  lane's use and share.

### 3. Conditions, verdicts and changing pending jobs
- Fields: `after: [ids]` (wait until each has ended), `if_passed: [ids]`
  (wait until each ended and passed), and `on_fail: park|cancel` (default
  park). Set them with `add --after/--if-passed/--on-fail`, or later with
  `jobs.py set <id> [--lane] [--after] [--if-passed] [--on-fail]`, which
  rewrites a pending job and keeps its id and pin. Unknown ids are refused.
- **Verdict.**
  - `add --check -- <cmd>` stores a check command.
  - When the job ends `ok`, the runner starts the check as its own light
    process. Its record is `running/<id>.check.json` with pid, start time,
    and an exit file through the same frozen wrapper. It never runs inside
    `step()`.
  - Each poll the runner reaps finished checks and writes `verdict: pass`
    (exit 0) or `fail` with the last output line into the done job. A check
    still running after 10 min is killed and recorded as `fail
    (timeout)`.
  - At `run` start, the runner restarts any check that has a record but no
    live pid, and any done job with a `check` and no `verdict`.
  - With no check, `ok` means pass and anything else means fail.
  - `jobs.py verdict <id> pass|fail [--reason]` sets a verdict by hand.
- **Deciding a condition** happens each poll, as a pure function of the
  queue files:
  - a dependency that is pending or running, or done with a check still
    running: the dependent waits, without blocking jobs behind it;
  - a dependency done and passed: the condition is satisfied;
  - a dependency done and failed, cancelled, refused, `ended-unknown`
    without a verdict, parked, or missing from every folder: the dependent
    is parked (`parked: "<reason>"`, a `parked` event that wakes `wait`).
  - Parking cascades through chains in the same poll.
  - `jobs.py unpark <id>` clears it.
- `bash -c "A && B"` chains stay allowed. New chains should be two jobs
  joined by `--if-passed`.

### 4. Filler lane (no preemption)
- Lane `filler` (share 0): a filler head is tried only when no other lane's
  head started this poll. A filler must be resumable or short: `add` refuses
  `--lane filler` unless `--resumable` is given or `--estimate-min` is 20 or
  less. The reservation rule in §2 applies to fillers too. A filler never
  starts if it would take room a protected head needs, so a waiting head
  waits at most for running fillers to end.
- Candidates, all peaking under 2 GB: one-turn gauntlet sequences on the
  control files, seed twins, bias-audit slices, boss replays, the slow test
  suites.

### 5. Pinned code (snapshots)
- **Where.** A snapshot of commit `<c>` is a detached worktree at
  `../sts-builds/<c12>/` (outside the repo,
  so searches in main don't walk it), made with `git worktree add --detach
  --lock`.
- **Layout, worked out against the real `.gitignore`:**
  - **`runs/`** holds tracked files (`index.csv`, `sweep-*.md`). In the
    snapshot: `git update-index --skip-worktree` on those paths, check
    that the checked-out `runs/` holds only those tracked files, remove it,
    then `mklink /J runs <main>/runs`. `registry.py` finds `runs/` from
    `__file__`, so pinned runs then create their run folders and index line
    in main.
  - **Directory junctions** to main for the whole-ignored folders:
    `results`, `db`, `cache`, `datasets`, `models`, `logs`, `jobs`,
    `.venv`, `scripts/analysis/out`.
  - **`data/`:** `data/bench` stays the snapshot's own, since it is tracked
    and part of the pin. Each ignored child folder of `data/` gets a
    junction. Each ignored file directly in `data/` gets a hard link (same
    volume, no admin rights, no copy). Files and folders that appear in
    main's `data/` later are linked in the next time a job is added to that
    snapshot, and `pins` reports them.
  - **The refusal rule:** a snapshot is refused if main has an ignored
    folder that is neither junctioned nor linked by these rules.
- **Module.** The snapshot's `pyroot/sts/` is built from that commit with
  `CARGO_TARGET_DIR` set to one folder shared by snapshot builds only (not
  main's `target/`). The artifact is taken from that build's own wheel. When
  an earlier snapshot has the same tree hashes for `engine/`, `py/`,
  `solvedb/`, `Cargo.toml`, `Cargo.lock` and `.cargo/`, its `pyroot` is
  hard-linked in instead, so each snapshot stays self-contained. Main's
  build-then-swap installs the wheel from the snapshot of its commit when
  one exists, so main and pinned jobs load identical bytes and share caches
  keyed by the `.pyd` hash (`ladder.py:197-206`).
- **Jobs.**
  - `add` pins to HEAD by default: `cwd` is the snapshot, and env
    `PYTHONPATH` is its `pyroot`. `--pin <commit>` pins an older commit
    (for a re-added job).
  - It refuses when `git status --porcelain --untracked-files=all --
    scripts engine py solvedb configs data/bench Cargo.toml Cargo.lock
    .cargo` prints anything. Untracked files count, because a new config
    must be committed first. The refusal names the paths and the two ways
    out: commit, or `--unpinned`.
  - `--unpinned` keeps today's behaviour. Use it for jobs that write
    tracked files (`data/bench` producers such as `bench_sets.py` and
    `puzzles.py`), jobs that write new files directly in `data/`, and runs
    by hand.
  - A missing snapshot is built at add: about a minute when the module
    changed, seconds otherwise.
- **Removal.**
  - `jobs.py pins` lists snapshots and the pending or running jobs using
    each.
  - `jobs.py unpin <commit>` removes a snapshot no job uses, in this order:
    1. run `git status --porcelain --ignored --untracked-files=all` in it,
       and refuse, naming the paths, on anything outside an allow-list: the
       junctions and links, the `runs` skip-worktree entries, `pyroot/`,
       `__pycache__/` and `.pytest_cache/`. Modified tracked files and
       unknown untracked files are refused too, because they are a job's
       output;
    2. check that every junction is a reparse point and remove it with
       `cmd /c rmdir`; remove the hard links with `del`;
    3. `git worktree unlock`, then `git worktree remove --force`.
  - The runner runs `unpin` on snapshots that no pending or running job has
    used for 24 h, and logs refusals. Nothing else may delete a snapshot:
    git removal through a junction would delete main's data, and `db/` is
    not rebuildable.
- **Effect.** A module swap, merge or landing on main never touches a
  pinned job. The AGENTS.md build-then-swap is then needed only for unpinned
  jobs and runs by hand.

### 6. Impact (unpinned jobs only)
- `jobs.py impact sts|scripts` lists pending and running jobs that are
  unpinned, which are the ones a swap or merge would hit, and exits 1 if
  there are any.
- A swap, merge or landing runs it first and records the result in its
  commit.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Existing job files (pending, running, parked) | Read as lane `main`, unpinned, no conditions; jobs running at the switch-over end as today | `test_old_job_files` |
| Admission rules (slots, thread budget, idle CPU, memory, refusal) | Same per job, except half slots for ≤2-thread heavy jobs and reserving the peak; only the choice among fitting jobs changes | existing tests + `test_half_slot`, `test_peak_reserved` |
| `wait` events | Old events keep their exit codes; `parked`, `waiting` added | `test_wait_*` |
| Manager steps using `add/status/kill/wait` | Same commands work; the new flags are optional | existing tests, docs |
| Main's data folders | Never deleted through a snapshot; pinned runs write into main | `test_unpin_keeps_data`, `test_pinned_writes_main` |
| The ladder cache | Shared between pinned and main runs of the same commit | `test_same_pyd_bytes` |

## Scope

May change: `scripts/jobs.py`, `scripts/tests/test_jobs.py`, README "Job
queue", AGENTS.md "Project gotchas" (which jobs build-then-swap still
concerns, and installing the snapshot's wheel), `docs/manager.md` "Each
manager run" (queue commands), this spec, a decisions entry. Off limits:
every other script's behaviour, `.gitignore`, the engine.

## Decisions taken (manager; reversible)

- **Shares by dominant resource** (threads or memory, whichever is larger).
  Memory was the binding limit. Alternative: threads only.
- **Default shares:** depth 35, run 30, goal1 25, train 10, main 10, filler
  0, from the last 48 h of work and the training rule. Editing
  `jobs/lanes.json` changes them.
- **A reservation for the top waiting head after 10 min, for any wait
  reason, plus `first`.** Alternative: memory-only protection after 120 min.
  The review showed it doesn't prevent the l8b case, and heads waiting for
  threads or slots got none.
- **Reserve the measured peak; half a slot for ≤2-thread jobs; keep 2
  slots.** Alternative: 3 slots on declared memory. Under-declared jobs
  would bring back the out-of-memory kills (0049d, 0052).
- **Verdict by a check process, exit code as the fallback, by hand with
  `verdict`.** Alternatives: exit code only (most passes here are rules read
  afterwards); a verdict field in each output file (no common format).
- **Full snapshot pinning, on by default.** Alternative: module-only
  pinning, which fails at a landing (new scripts with an old module crash).
- **Deferred:** filler preemption (fillers are short or resumable, and the
  reservation bounds a head's wait; the review found preemption prone to
  thrash), and `needs`/`about` (they pay off once the claims store exists).

## For the owner (not built here)

- The lane set and charters (goal, measure, stop rule, checkpoints, share)
  and the light manager (runner alive, results filed, refill from lane
  buffers, reviews after a headline change): a proposal follows once this
  runner exists.

## Verification (tests first, `scripts/tests/test_jobs.py`, `Env` fakes)

1. `test_exit_survives_restart`: a job runs through the wrapper; a new
   Runner adopts it; it ends `ok` (0) or `failed` (3), not `ended-unknown`.
   A stale exit file is deleted at spawn.
2. `test_wrapper_frozen`: editing `jobs.py` to a syntax error after `run`
   starts doesn't stop a job from starting.
3. `test_lanes_json_bad`: a corrupt `lanes.json` keeps the last shares, logs
   `lanes-bad` once, and the runner keeps stepping.
4. `test_lane_choice`: shares 3:1 with equal jobs: starts follow lowest use
   / share; a memory-heavy job counts by memory.
5. `test_head_reserved_threads` and `test_head_reserved_memory`, the l8b
   case: a head refused for threads (or memory) for over 10 min; a smaller
   job in another lane that would take the room it needs doesn't start; one
   that fits alongside does; after a running job is killed, the next poll
   starts the head or nothing. `first` reserves at once.
6. `test_peak_reserved`: three running heavy jobs whose `peak_gb` exceeds
   their `mem_gb` block a fourth that the declared values would admit.
   `test_half_slot`: two 2-thread heavy jobs leave a slot for a third.
7. `test_conditions`: `if_passed` waits, starts on pass, parks on fail;
   `after` starts on any end; parking cascades A → B → C; a missing or
   parked dependency parks; a parked job doesn't block others; `unpark`;
   `set` adds a condition to a pending job and keeps its id.
8. `test_check_process`: a check exiting 0 / 1 gives pass / fail without
   blocking a poll; a runner restart during a check restarts it; a 10-min
   timeout gives `fail (timeout)`; `verdict` by hand.
9. `test_filler`: a filler starts only when nothing else started; never into
   a protected head's room; `add` refuses a long, non-resumable filler.
10. `test_pin` (scratch repo with a copy of the real `.gitignore`): `add`
    pins HEAD; refuses with an untracked file in `configs/` and names it;
    `--unpinned` doesn't; the junctions, the `runs` junction with
    skip-worktree, the `data/` hard links and child junctions exist; the
    pyroot is reused by hard link when the trees match.
11. `test_pinned_writes_main`: a pinned `registry` run creates its run
    folder and `index.csv` line in main.
12. `test_unpin_keeps_data`: main's data survives `unpin`; `__pycache__/`
    in the snapshot is allowed; a modified `data/bench` file or an unknown
    untracked file is refused, with the paths named.
13. `test_same_pyd_bytes`: main's swap from the snapshot's wheel gives the
    same `.pyd` hash as the snapshot.
14. `test_impact`: lists unpinned jobs and exits 1; 0 with only pinned jobs.
15. `test_old_job_files`: today's pending and running file shapes run.

End to end: a pinned one-turn gauntlet of 5 sequences, with main's `sts`
swapped mid-run, finishes with rows identical to an unpinned run before the
swap. A two-job `--if-passed` chain whose check fails parks the second.
`jobs.py status` shows lanes and reservations.

## Build steps

1. Frozen wrapper, exit files, `lanes.json` loading, choice logging. Check:
   tests 1-3, 15 and the existing suite. Restart the runner on the new code.
   This restart is the last one that loses exit codes.
2. Lanes, use and shares, the protected head, `first`, peak reservation,
   half slots, status. Check: tests 4-6.
3. Conditions, check processes, verdicts, parking, `set`, `unpark`. Check:
   tests 7-8.
4. Filler lane. Check: test 9.
5. Snapshots, default pinning, `pins`, `unpin` and the 24 h sweep, wheel
   install from the snapshot. Check: tests 10-13 and the end-to-end swap
   run.
6. `impact`; docs (README, AGENTS.md gotcha, manager.md queue commands,
   decisions). Check: test 14.

Restart the runner after each step that changes `run`.
