# Session-free reads: a family driver and the ledger

Status: closed (2026-11-07, built and in use; scripts/family.py and scripts/analysis/ledger.py; lane closed 2026-11-08, decisions 'Lane session-free-reads closed (2026-11-08)').

Lane `session-free-reads` (charter: `kb get lane/session-free-reads`).

## Outcome

One session queues a whole family of reads (bursts, their reads, the
table, and the follow-up reads the table's verdict picks), and the family's
result and verdict come out of one command, with no session needed between
its jobs; beside it, a ledger table prints every recipe's paired effect
against the 10-29 net from the files on disk.

**How it moves the goals and how we'll know.** Goal 2 and goal 1 both wait
on machine time, and the lanes get only a few sessions a
day: a family that needs a session per read (pattern-rows-burst: 12 jobs,
several sessions) leaves the CPU idle between sessions. The measure is the
first family's count: sessions that touched it from queueing to its table
(goal: one, plus the sceptical read), and its jobs, against
pattern-rows-burst. The ledger is right when it reproduces data5k -3.30,
data20k -1.45 and data40k -0.16 HP against the 10-29 net (checked on the
files already: mean over every (net, book) file of the paired end-HP edge
on the same book).

Non-goals: no change to `jobs.py`, `gauntlet.py`, `finetune.py` or the
runner; no new statistics (the strata come from `cards_by_half.py`); no
reading of results a check cannot give (the sceptical look stays with the
owning lane).

## Behaviour

### Family file

`configs/families/<name>.json`:

```json
{"name": "ycards-step2", "lane": "yardstick-cards",
 "parent": "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt",
 "arms": {"heur-g400": ["configs/ycards-heur-g400-s1.json", "..."], "...": []},
 "burst": {"threads": 4, "mem_gb": 2.5, "estimate_min": 30},
 "reads": {"a": {"cmd": ["scripts/gauntlet.py", "play", "{net}@hpb0.01", "--sequences", "500",
                          "--threads", "3", "--out", "results/gauntlet/fam-{config}-hpb0.01.json"],
                 "threads": 3, "mem_gb": 1.5, "estimate_min": 6}, "...": {}},
 "table": {"kind": "strata", "books": ["a", "b"], "control": {"a": "results/gauntlet/net1029-hpb0.01.json",
           "b": "results/gauntlet/net1029-hpb0.01-b500.json"},
           "rule": {"stratum": "held-out DF", "min_se": 2.0,
                    "keep": {"train": {"hp": -0.9, "clears": -0.04}}}},
 "then": {"headline": {"cmd": ["..."], "arm": "best", "net": "best", "threads": 3, "mem_gb": 1.5, "estimate_min": 40}}}
```

`{net}` is a burst's `model.pt` path, `{config}` the config's stem,
`{arm}` the arm name. A seed may carry an existing burst job instead of a
config path to queue: `{"config": "...", "job": "0305-finetune"}`.

### `scripts/family.py queue <file> [--dry-run]`

- For each config: the burst job is the newest job in the queue (pending,
  running, or done with status ok) whose cmd runs `finetune.py` with
  `--config <that config>` and `--from <parent>`; with none, it adds one
  (`finetune.py --from <parent> --config <cfg> --threads N`).
- For each config and read: a read job whose cmd is `family.py read <file>
  <config> <read>`, `--if-passed <burst>`, pinned to HEAD, lane = the
  family's lane, note naming the family and "queued by family.py; queue it
  again with family.py queue, not by hand". Skipped when a job with that
  cmd is pending (not parked), running, or done ok; a parked one is
  cancelled and added again bound to the current burst (so re-running
  `queue` after the owning lane re-queues its bursts re-binds the reads).
- One table job `family.py table <file> --write` `--after` every read,
  with `--check "family.py verdict <file>"` (exit 0 when the rule passes).
- For each `then` read: a job `family.py read <file> best <read>`
  (`"net": "best"`), or one per seed of the best arm, `best#<k>`
  (`"net": "all"`, k = 0..seeds-1 in the arm's order), `--if-passed <table
  job>`.
- Prints each job it added, skipped or re-bound; `--dry-run` adds nothing.
- Fails (exit 2, nothing added) when a config file or the parent is missing.

### `scripts/family.py read <file> <config|best> <read>`

Finds the burst's run folder from the burst job's log (finetune prints
`run <id>: <model_path>`), substitutes the placeholders and runs the read's
cmd with this interpreter, cwd = the checkout, passing its exit code on.
`best`: the arm the table's verdict file names, and its net with the
largest stratum gain. A missing log line or model is exit 3 with a message.

### `scripts/family.py table <file> [--write]` and `verdict <file>`

For each arm: its nets' read files on the table's books (a file under 500
sequences counts as missing), `cards_by_half.strata_row` against the
control per book, pooled over the arm's nets and books as `--step1b` does:
per stratum the HP edge with se over sequences and se over nets, clears
likewise, n. Verdict per arm: pass when the rule's stratum gain is at least
`min_se` times its se over nets and each `keep` stratum's HP and clears edge
is at or above its floor; `best` is the passing arm with the largest gain
(none: the family fails). Prints a markdown table, the verdict, and per
arm the job ids and thread-hours (threads x run time from the job
records). `--write` also writes `results/families/<name>.json` (arms, rows,
verdict, best) and `.md`. `verdict` reads that json: exit 0 on pass, 1 on
fail, 2 when missing.

### `scripts/analysis/ledger.py`

Per recipe group (regex groups as in `cards_by_half.GROUPS`, plus burst8,
the 1029 seed twins and any `rerank-*` net) and per net: paired end-HP and
clears edge against the 10-29 net's file on the same book (one turn deep:
`net1029-hpb0.01.json` for sequences 0-499, `net1029-hpb0.01-b500.json`
for 500-999), its se over sequences, books found, then per group the mean
over (net, book) files, the between-seed sd, the seeds, and the
thread-hours of the jobs whose `--out` wrote those files. A second column
pair gives the two-turn read where a file exists against the two-turn
control, and "none" where not. `--md` prints the table for the results
doc.

## Fits with

- `jobs.py` queue: family.py only calls `jobs.Queue.add`, `find`, `jobs`
  and `cancel`; the pinning and dirty-tree rules hold (test: a scratch
  queue, as `test_jobs.py` builds one, gets the expected jobs and
  conditions).
- `cards_by_half.py --step1b`: unchanged; family's table on burst8's three
  nets gives the same strata numbers as its "burst8 (transfer)" row
  (test on the files on disk, skipped when they're missing).
- Lane yardstick-cards owns its bursts and their reading: the family
  binds to its existing burst jobs and queues their reads in its lane, and
  every job's note names the family, so its worker sees them in `jobs.py
  status` and doesn't queue them twice (decisions entry).

When in doubt: prefer a job that fails loudly over one that guesses a net.

## Scope

New `scripts/family.py`, `scripts/analysis/ledger.py`,
`scripts/tests/test_family.py`, `scripts/tests/test_ledger.py`,
`configs/families/`, the results doc section, README's "Job queue" (a
line), decisions. Off limits: `jobs.py`, `gauntlet.py`, `finetune.py`,
the engine, the runner, `cards_by_half.py`'s output.

## Decisions taken

- The read resolves its net at run time from the burst job's log, not by a
  run-folder name fixed in advance (registry folders carry a random hash).
- Reads use `--if-passed` on their burst with `--on-fail cancel` (a failed
  or cancelled burst cancels its reads: the runner parks an `--after` job
  whose dependency is parked, so parked reads would stall the table); the
  table uses `--after` (a missing read shows as missing). `queue` run again
  adds a cancelled read again, re-binds a pending job whose conditions
  changed (`jobs.Queue.set`), and runs the table again once it added a read.

## Outside assumptions

None beyond the repo: finetune's last line `run <id>: <model_path>`
(test: a fake log).

## Verification

- `test_family.py`: `queue` on a scratch queue with a fake family (two
  arms, two configs, two reads, one `then`) adds 2 bursts, 4 reads with
  `if_passed`, a table with `after` and a check, a `then` job with
  `if_passed` on the table; a second `queue` adds nothing; a parked read
  is re-bound; an existing burst job is bound, not duplicated. `read`
  resolves `{net}` from a fake log and fails with exit 3 without it.
  `table` on fake files gives a known pass and a known fail.
- `test_ledger.py`: on the files on disk, data5k -3.30, data20k -1.45,
  data40k -0.16 (to 0.01); skipped when they're missing.
- End to end: `family.py queue configs/families/ycards-step2.json` from one
  session; the next session that reads it finds its table written.

## Build steps

1. `family.py read` and `queue` with `test_family.py`'s queue and read
   tests. Check: those tests pass.
2. `family.py table` and `verdict` (strata kind), with its tests, and the
   burst8 equality test. Check: tests pass; `family.py table` on a family
   of the three burst8 nets prints the transfer row's numbers.
3. `ledger.py` with `test_ledger.py`. Check: the three numbers; the table
   committed to `docs/research/learned-play-results.md`.
4. `configs/families/ycards-step2.json` (steps 2 and 2b, binding to
   yardstick-cards' burst jobs), queued with `queue` (long run: the bursts
   and reads, about 15 thread-hours, in yardstick-cards' lane). Check: the
   dry run lists the expected jobs; then queued.
