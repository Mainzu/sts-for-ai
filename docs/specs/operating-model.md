# Operating model: a steward, a navigator and project lanes

Status: closed (2026-11-03, built and in use; cut over 2026-11-03, amendment 6 built 2026-11-04 e4af46ff, wakes amended 2026-11-09 f8c52c22; decisions "Operating model as built").

Asked for by the owner: the system exists for long-term management of
an automated project; the owner doesn't act as manager and only adds
ideas or shifts direction.

## Why

The owner set two standing functions, in order (2026-11-03):

1. **Keep the environment healthy**, so development and experiments go on
   without the owner. This is the primary goal.
2. **Drive the project forward:** think in big pictures, keep exploring new
   approaches and combinations, and steer when the owner isn't there.

When the two conflict, health wins.

Today one scheduled manager does everything every 2 hours. That falls short
of both functions.

- **Short work wins over long work.** The loop picks what one wake-up can
  finish (fact `cause/loop-selects-short-work`). The engine re-scope was
  recommended three times and started only when the owner started it.
- **The hand-over has outgrown its use.** `docs/manager.md` is 1,368 lines:
  - "For the owner" (about 500 lines) parks decisions that wait on the owner;
  - "Next" holds three stacked rankings.
- **Health is nobody's job.**
  - The queue sat empty overnight on 11-03.
  - Booked CPU was 49% of the machine's threads over the runner's life.
  - Lock housekeeping is a quarter of all commits.
  - Five runs stood down on a held lock.
- **Reviews re-derive.** Seven big-picture reviews in four days rebuilt the
  same findings.
- **The session budget tightens at a set date (the budget switch).** From then, session time is the
  scarce resource: cost mode (Sonnet for builds, Haiku for chores, one
  lane at a time).

How we'll know, over the first two weeks:
- **Health:** booked CPU share and zero-job minutes per day, time with an
  empty queue, days with red tests (`scripts/health.py`).
- **Progress:** checkpoints passed per week, and headline movement (facts
  `measurement/headline*`).
- **Owner load:** owner questions, with a target of zero, and digests
  delivered.
- **Cost:** role sessions per day against each role's budget.

## Outcome

Three roles and a small owner interface replace the single manager.
- **Steward:** frequent, cheap and mechanical; it keeps the environment
  healthy.
- **Navigator:** infrequent and deep; it decides which project lanes are
  open, runs the exploration, and answers the owner's open questions with
  reversible defaults.
- **Lane worker:** carries the open lanes. Each lane is a temporary project
  with a charter, checkpoints, a stop rule, a CPU-hour cap and an end date.
- **Owner interface:** the ideas list and a direction note going in; a daily
  digest and a rare escalation notice coming out. The owner is never asked
  to decide.

## Behaviour

### 1. Where things live

- **`docs/operating.md`** (new): the shared rules every role reads at
  start. It holds:
  - the owner's dated standing sections, carried verbatim and append-only
    (goals, standing grants, machine time, the training rule, big-picture
    reviews);
  - machine limits and pacing;
  - the job-queue crib (commands, conditions, pinning, `impact`, restarts
    belong to the steward);
  - the sceptical-read rules for results;
  - kb filing rules;
  - the lock, claim and wake rules of this spec.

  Cap: 250 lines, not counting the verbatim owner sections. Each role's own
  duties live in its scheduled-task prompt (at most 120 lines), not here.
- **`docs/direction.md`** (new, the owner's file): goal weights, interests,
  things to avoid. It is seeded and marked as a seed. The navigator reads it
  first, and it outranks every other ranking.
- **Charters, split by writer** (kb facts):
  - `lane/<name>`, written by the navigator only:
    - goal, measure, stop rule;
    - kind (`project` or `exploration`);
    - budget: CPU share, a CPU-hour cap and an end date.
  - `lane/<name>/step`, written by the lane worker only: current step and
    next checkpoint.
  - `lane/<name>/checkpoint`, written by the lane worker only:
    `passed <name>` or `failed <name>`. Its kb `at` dates it.

  Closing a lane retires all three, with the outcome.
- **`docs/backlog.md`** (navigator): candidate lanes. Each has a source, an
  expected value, a CPU-hour estimate and a goal.
- **`docs/filler.md`** (steward): standing small jobs. The full test run is
  job id `test-full`, in lane `filler`.
- **Health:** `jobs/health.json` (gitignored), written by
  `scripts/health.py` on every steward run. There are no health commits;
  the daily digest records the day's health.
- **`docs/digest/<date>.md`** (steward): the daily digest.
- **Per-job read rules** stay in each job's `note`, as today. The lane that
  owns the job acts on the read; the steward only files values.

### 2. Who writes where, and when

- **Lane workers** always work in their own worktree on branch
  `lane/<name>` (the /build way).
  - They merge into main with a fast-forward under the merge lock, then
    push.
  - They never edit the main checkout.
- **The steward and the navigator** edit only their own files in the main
  checkout. They edit and commit in one short step, by pathspec, then do a
  plain `git push`.
  - There is no `pull --rebase`: only this laptop pushes.
  - A refused push is reported, never forced.
  - Shared append-only files (`docs/decisions.md`, the results doc) are
    written the same way.
- **Locks.** Gitignored files under `jobs/locks/`, each holding holder,
  session id, time and heartbeat:
  - `main-merge`: held while merging into main or swapping `sts`;
  - `lane-<name>`: a claim. A worker takes it before working a lane and
    skips claimed lanes.

  Any role breaks a lock whose heartbeat is older than 45 minutes and whose
  holder isn't running.
- **Queue adds from the main checkout** (the steward's filler) use `--pin
  <HEAD sha>`. That avoids the dirty-tree refusal while a lane edits
  elsewhere.
- **The runner** is restarted by the steward only. Other
  roles report, but don't restart it.

### 3. Steward (scheduled task `sts-steward`)

- **Cadence:**
  - every 2 h until the budget switch (session default model);
  - every 4 h from then, on Haiku, with a budget of 6 sessions a day.
- **Health.** It passes the session-usage numbers in to
  `scripts/health.py`. Without them, usage
  shows as unknown, not red. Each metric has an owner and a fix.
  - **Blockers.** These gate the navigator and get the steward's immediate
    fix:
    - the runner dead and not restartable;
    - disk under 8 GB with nothing rebuildable left;
    - session usage at its limit;
    - a push or auth failure.
  - **Work items**, red but not a gate:
    - **Ready work:** total hours of ready work across open lanes under 3.
      Fix: wake the lane worker; top up filler.
    - **CPU:** booked CPU share over 24 h under 50%, or more than 60
      zero-job minutes. Fix: filler and a lane wake.
    - **Tests:** `test-full` failing or older than 48 h. Fix: queue it; a
      failure becomes the lane worker's first task.
    - **Facts:** `kb check` with more than 10 suspect or unchecked facts.
      Fix: run `kb verify`, then flag what fails. Only facts whose check
      passes are confirmed.
    - **Render:** `kb render` over 250 lines. Fix: the navigator merges
      facts on its next run.
    - **Debris:** branches and worktrees this system made (`lane/*`,
      `claude/*`) idle over 3 days. Fix: prune merged ones and list the rest
      in the digest. Branches it didn't make are listed once and then
      ignored.
    - **Snapshots:** over 20, or over 2 GB. Fix: `unpin`.
    - **Ideas:** untriaged ideas. Fix: triage them into the backlog, with an
      agent note on each issue.
    - **Stagnation:** no `measurement/headline*` change and no passed
      checkpoint for 3 days. Fix: wake the navigator. Facts the steward
      files never reset it.
- **Fixes it makes:** restart the runner (keeping exactly
  one), top up filler, re-check facts, unpin snapshots, prune merged
  worktrees (never data), file results no lane filed, triage ideas.
- **Wakes**, through `run_scheduled_task`, event-driven and debounced:
  - **The lane worker:** only when a lane can act now. That means a
    checkpoint job of its lane ended, or the lane has no running and no
    ready job. At most once per lane per such event. A checkpoint job is an
    ended job with a `check`, one that didn't end ok, or the lane's last
    (nothing of the lane running or pending unparked); a lane's other ended
    jobs are held and listed with its next such wake, at the latest when
    its queue drains (amended 2026-11-09, `docs/research/queue-throughput.md`).
  - **The navigator:** on its triggers (§4).
  - A refused wake (the task is disabled or already running) is logged once
    and not retried. It doesn't make the run unclean.
- **Escalation**, a notice and never a question. A separate push
  notification, outside the daily limit, goes out when:
  - a blocker stays red for 3 steward runs; or
  - the problem is one only the owner can fix: the machine down, the
    app not running scheduled tasks, auth expired, or disk full of data
    the grants forbid deleting.
- **Digest:** writes it at the first run after 07:00 (§6).
- **Never** plans, picks research, or touches charters.

### 4. Navigator (scheduled task `sts-navigator`)

- **Triggers** (from the steward):
  - a lane closed, hit its stop rule, cap or end date;
  - a `measurement/headline*` fact was superseded;
  - stagnation;
  - five or more newly triaged ideas;
  - an edit to `docs/direction.md`.
- **Backstop:** daily until the budget switch, which keeps the owner's every-~24 h
  review rule, then every 3 days, recorded as a decision that re-sets
  `owner/reviews`. It doesn't run while a blocker is red.
- **Portfolio:**
  - keeps 2-3 lanes open, one of them `kind: exploration`;
  - opens lanes from the backlog by expected value per CPU-hour, weighted
    by `docs/direction.md`;
  - writes `lane/<name>` and sets the shares of open lanes in
    `jobs/lanes.json`, plus `main` 10 and `filler` 0;
  - closes a lane at its stop rule or goal, or when it reaches its
    CPU-hour cap or end date. It may extend a lane once, with a decisions
    entry giving the reason; a second extension needs a new lane.
  - For each closed lane it records predicted against actual value as a
    `measurement/portfolio-*` fact, so its estimates get checked.
- **Exploration:**
  - cheap probes of new approaches and combinations, each with a kill-fast
    rule (one probe, one read, then go or stop);
  - sources: the ideas list, prior-art scans, the reviews' "approaches to
    try", combinations of open lanes' results;
  - a passing probe becomes a backlog entry with its evidence.
  - It pauses first under budget pressure.
- **Big-picture thinking without re-deriving:**
  - it starts from `kb render`, `kb find` and what changed since its last
    run (`git log`, new and retired facts);
  - it uses workflows freely;
  - it cites facts by key and writes conclusions as `cause/` or
    `decision/` facts.
  - The saved `big-picture-review` workflow runs after a headline change,
    pointed at these inputs instead of manager.md.
- **Decides on the owner's behalf:**
  - The most reversible option, recorded in `docs/decisions.md` marked
    "(on the owner's behalf)" with the alternatives, and listed in the
    digest.
  - First run:
    - bundles vs atoms for goal 1: bundles first;
    - simulator and arena: keep this engine, arena ladder 0 and 1;
    - archiving `db/`: no, it stays forbidden.
  - Never decides what the grants forbid. Those go in the digest, and in
    an escalation if they block.
- **Model and budget:** session default until the budget switch; from then Sonnet, one
  session per run, workflows sized to the session budget.

### 5. Lane worker (scheduled task `sts-lanes`)

- **Cadence:**
  - every 4 h as a backstop, plus the steward's wakes;
  - after the budget switch, 4 sessions a day, on Sonnet.
- **Picking work.** At start it reads `jobs/health.json`. If it is over 4 h
  old, the steward may be dead, so it runs `health.py` itself, reports in
  the digest folder, and escalates. Then:
  - a red `test-full` gets repaired first;
  - otherwise it takes the claim of the lane with an acted-on event or the
    least ready work, skipping claimed lanes.
  - Until the budget switch it may start one more session for a second lane, which
    takes that lane's claim.
- **Work:** today's protocol from operating.md:
  - /spec and /build with Away rules, specs confirmed under the mandate;
  - long runs queued with `--lane <name>` and conditions, keeping at least
    6 h ready when the lane has queueable work;
  - results read sceptically and filed as facts with `path#heading`
    sources;
  - `lane/<name>/step` updated.
- **Checkpoints:** it writes `lane/<name>/checkpoint`. On a stop rule or
  goal, it marks the lane done in its step fact and wakes the navigator,
  which closes it.
- **Context:** when context passes about 50%, it finishes the step, updates
  the step fact, releases the claim and ends.

### 6. Owner interface

- **In:** ideas (the owner's ideas list, kept outside this repo) and `docs/direction.md`. Anything the owner
  writes where a role can see it outranks everything else.
- **Out, the daily digest** (at most 60 lines): worst red first, then:
  - what was fixed;
  - open lanes with their checkpoints, opened or closed lanes and why;
  - exploration results;
  - decisions made on the owner's behalf;
  - headline numbers with their change;
  - what's next per lane;
  - role sessions used against budget.

  It is committed and pushed, with one push notification a day carrying
  its first line.
- **Escalations:** as in §3. No questions.

### 7. Pacing

- **Ahead of the session budget's pace:** lanes finish their step and start
  nothing big; exploration pauses first.
- **Near the limit:** only the steward runs.
- **After the budget switch:**
  - only one role session runs at a time: each role checks `list_sessions`
    for another running role session at start and defers;
  - each role keeps to its daily session budget and exits early when it's
    spent.

## Migration of manager.md

Every heading of `docs/manager.md` has a destination. The cut-over appends
it to the existing `docs/manager-archive.md` as raw history.

| manager.md section | Destination |
|---|---|
| Goals; Standing grants; Machine time is the bottleneck; Training: when it runs and when it stops; Big-picture reviews (all owner-dated) | operating.md, verbatim, append-only |
| Machine limits; Pacing | operating.md |
| Each manager run | split: shared rules (sceptical reads, job-queue crib, kb filing) into operating.md; steps into the three prompts |
| Directions | backlog |
| For the owner | open decisions to the navigator's first run (defaults); notes to archive |
| Active manager | removed (locks in `jobs/locks/`) |
| Running | job notes (read rules) and `lane/*/step`; the queue itself |
| Next | backlog and the first charters |
| Log | archive |

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Owner's grants and dated rules | Unchanged, verbatim in operating.md | migration table; review |
| kb facts citing manager.md (owner/goals, grants, budget, machine-time, reviews; how/disk-rules, keep-awake, machine, tests) | Re-set to the operating.md sections at the cut-over | verification 2: no "missing: docs/manager.md" in `kb check` |
| The job runner | Used as built; `lanes.json` edited only by the navigator; running jobs keep their lane | lanes-runner tests |
| Running and queued jobs | Keep running; read rules stay in their notes | migration step |
| `big-picture-review` workflow, `scripts/analysis/cpu_timeline.py` (reads the Log), the memory note "live operating state is docs/manager.md", kb-adoption stage 4 | Re-pointed: the workflow to operating.md, facts, digests and `git log`; cpu_timeline to the archive; the memory updated; kb-adoption stage 4 superseded | step 5 checks |
| The old manager | No overlap: `sts-manager` is disabled in the same step that archives manager.md and enables the new roles | build step 5 |

## Scope

May change:
- new: `docs/operating.md`, `docs/direction.md`, `docs/backlog.md`,
  `docs/filler.md`, `docs/digest/`, `scripts/health.py` and its tests;
- `docs/manager.md` (archived) and `docs/manager-archive.md` (appended);
- kb facts: `lane/*`, `owner/*` and `how/*` re-sets, `measurement/portfolio-*`;
- `jobs/lanes.json`; `jobs/locks/`;
- the scheduled tasks `sts-steward`, `sts-navigator`, `sts-lanes` (new) and
  `sts-manager` (disabled);
- `AGENTS.md` (its pointer), README;
- the `big-picture-review` workflow prompt, `cpu_timeline.py`'s log source;
- the memory note; `docs/specs/kb-adoption.md` (status);
- a decisions entry; this spec.

Off limits: `jobs.py`, kb's code, the engine, other scripts' behaviour.

## Decisions taken (owner's framing; the rest the manager's, reversible)

- **Three roles**, because health and direction differ in frequency, depth
  and cost (owner: health first).
- **One lane-worker task with per-lane claims**, not a task per lane:
  nothing to create or delete when lanes change.
- **Charters split by writer.** One fact with three writers lost updates.
- **Lane work in worktrees; the main checkout only for short,
  edit-and-commit writes.** A shared checkout breaks `pull --rebase` and
  pinned adds.
- **Health in a gitignored file**, not kb, so there are no health commits.
- **Blockers gate; everything else is a work item with an owner.** Gating
  on every red would block the navigator from day one: the tests and debris
  metrics are red today.
- **Event-driven wakes, daily budgets per role, and one role at a time after
  the budget switch.** Fixed 2-hour cadences for two roles would double sessions.
- **Lanes have a CPU-hour cap and an end date, extended at most once.** The
  navigator's estimates are checked against outcomes.
- **Owner questions become reversible defaults, made on the owner's
  behalf.** The owner said they don't intend to manage.
- **A single cut-over step.** Any gap would let the old and new managers
  run together.
- **Reviews: daily until the budget switch** (the owner's rule), then every 3 days and
  after headline changes.

## Verification

1. `scripts/tests/test_health.py`:
   - each metric red and green on fixtures (empty queue, dead runner pid,
     fake `kb check`, disk stub);
   - usage unknown without arguments;
   - blockers and work items separated;
   - `test-full` found by id;
   - stagnation ignores steward-filed facts;
   - exit 1 only on a blocker.
2. **Cut-over checks:**
   - operating.md within its cap (owner sections excluded);
   - each prompt at most 120 lines;
   - `kb check` lists no `missing: docs/manager.md`;
   - every manager.md heading appears in the migration table's destination.
3. **Dry runs**, one per role prompt, in a scratch clone (no push, a fake
   `run_scheduled_task`):
   - the steward finds the empty queue, tops up filler, and wakes the lane
     worker once, not twice for the same event;
   - the navigator opens a lane from the backlog with all three charter
     facts and a decisions entry;
   - two lane workers don't take the same lane;
   - with stale `health.json` the lane worker runs the dead-man check.
4. **One supervised "Run now" per new task**, to grant its tool approvals,
   before any unattended run.
5. **First real runs after the cut-over:** two clean steward runs, the
   navigator's defaults decisions and charters, a first digest under 60
   lines.
6. **After a week:** the "Why" measures, reported in a digest.

## Build steps

1. `scripts/health.py` with tests. Check: verification 1.
2. Drafts, not yet live:
   - `docs/operating.md`, `docs/direction.md` (seed), `docs/filler.md`
     with `test-full`, `docs/backlog.md`;
   - the three prompts, as scheduled tasks created disabled.

   manager.md stays live. The build session holds its "Active manager" lock
   for any manager.md edit. Check: dry runs (verification 3).
3. The first charters (`lane/cheap-depth` to finish line-step and its
   read, `lane/run-decisions`, `lane/goal1-yardstick`, each with a cap and
   end date) and `jobs/lanes.json`. `jobs.py set --lane` on pending jobs;
   running ones keep their lane.
4. One supervised "Run now" of each new task (verification 4), still
   disabled for schedules.
5. **Cut-over, one step:**
   1. take the lock;
   2. append manager.md to `docs/manager-archive.md` and remove it;
   3. re-set the 9 facts;
   4. update AGENTS.md, the workflow prompt, cpu_timeline's source, the
      memory note and kb-adoption's status;
   5. disable `sts-manager`, enable the three new tasks;
   6. commit, push.

   Check: verification 2, then 5.
6. A decisions entry. After a week, the digest reports verification 6.

## Amendment 1 (2026-11-03)

Instruction files state the rules as they stand, without history (owner,
after step 3).

- **Behaviour, section 1:** `docs/operating.md`, the three role prompts,
  `docs/filler.md` and `docs/direction.md` hold no decision history: no
  date a rule was made or who made it, no "seeded", "checked at" or
  "refused at" notes, no pointer to the decisions entry that set a rule.
  History lives in `docs/decisions.md`, git and `docs/manager-archive.md`.
  Dates that schedule behaviour (the budget switch, a lane's end
  date) are rules and stay.
- **The owner's sections** keep their rules. Their headings drop the date
  ("Goals (owner)", "Standing grants (owner)", "Machine time is the
  bottleneck (owner)", "Training: when it runs and when it stops (owner)",
  "Big-picture reviews (owner)"); dates, point-in-time facts (a past disk
  reading, where a number came from) and the old manager.md names ("For the
  owner", "Next" and the away-mode tags) go, the names replaced by today's files;
  the review cadence states its change at the budget switch.

## Amendment 2 (2026-11-03)

Each role's model is a setting of its task in the app; a session can't
switch its own model, so the prompts don't try. Models: steward Haiku from
the start; lane worker Opus, Sonnet after the budget switch (set in
the app); navigator Fable. This replaces "session default model" in sections
3-5: the app's default was Fable at high effort, too costly for a role
that runs about 12 times a day.
- **Fits with:** the 9 facts re-set at the cut-over cite these headings.
- **Verification 2** adds: the instruction files carry no past dates or
  history notes; the owner sections' changes against manager.md are listed
  in the commit.
- **Steps:** amend operating.md, filler.md,
  direction.md and the three prompts (re-installed in the tasks); step 5
  is unchanged.

## Amendment 3 (2026-11-03)

No role starts another. In an unattended scheduled run the app asks a
person to approve `run_scheduled_task` every time ("Allow once" only), so
the steward's wakes were refused on the first real run.

- **Schedules instead of wakes:** steward every 2 h at :20; lane worker
  every 2 h at :50; navigator daily. After the budget switch: the steward skips a
  run within 4 h of its last one; the lane worker keeps its budget of 4 a
  day; the navigator skips a run within 3 days of its last one unless
  `wakes.navigator` lists a trigger.
- **Events stay:** `health.py` still lists `wakes.lanes` (the lane worker
  takes those lanes first) and `wakes.navigator` (the navigator's
  triggers); `woke navigator --ran` records the navigator's run.
- **One session at a time (after the budget switch)** applies to the lane worker
  and the navigator; the steward never defers, since health comes first.
- **Verification 3** (the steward wakes once per event) no longer applies.

## Amendment 4 (2026-11-03)

The lane worker and the navigator are started by the role launcher
(`docs/specs/role-launcher.md`) as headless CLI sessions, on events and
backstops, with budgets, one-at-a-time and time limits held in code; their
prompts live in `docs/roles/`. The steward stays an app task and restarts
the launcher. This replaces amendment 3's schedules for those two roles.

## Amendment 5 (2026-11-03)

The owner doesn't type direction in bare; they question and understand
the current approach first, and their suggestions are reviewed like any
other idea (owner, approved the proposal).

- **Ideas board:** unchanged: the steward triages, the navigator reviews.
- **Discussion:** a project skill `/approach` for a session with the owner.
  It explains the current approach from the full record (no one-page
  summary): the overview first, then wherever the owner asks, down to the
  evidence, citing fact keys and doc sections. A suggestion the owner makes
  there is reviewed on the spot, with them, to an idea's standard (what it
  changes, evidence for and against, expected value per CPU-hour against
  the open lanes, a sceptic agent for anything substantial); the owner
  decides there, and the session records the outcome: `docs/direction.md`,
  a backlog entry, or a decisions entry marked "(owner)"; a rejected or
  parked suggestion gets its reasons. A committed `direction.md` change
  wakes the navigator.
- **Removed:** "anything the owner writes where a role can see it outranks
  everything" and bare edits of `direction.md`. Owner decisions and
  `direction.md` bind the roles because they come out of a review.

## Amendment 6 (2026-11-04)

Bringing in new approaches is the navigator's reason to exist beside the
steward (the Why's second function). Until now the spec gave idea work no
trigger, no required output and no measure, and paused it first under
budget pressure, so runs did bookkeeping and stopped (owner review,
2026-11-04). The navigator now thinks and steers; the lane worker
does the lanes' bookkeeping, closing included; the navigator wakes on
conditions it sets itself (owner, in an `/approach` session).

### Navigator: duties

Each run, after the health gate (the prompt orders them so each feeds the next):
1. **New ideas.** Plausible ones only: each states its mechanism (why it
   would work here), the goal it moves, and the result that would show it
   wrong; the trade-off rule (`docs/operating.md`, "A probe needs a
   trade-off") applies.
2. **Revived ideas.** Every closed lane or family carries a "reopen if"
   condition (below); each run checks those conditions against what
   changed since its last run. A rejected idea's reason stands unless new
   evidence answers it.
3. **Outside research.** Searches start from a short list of open
   questions the navigator keeps in the backlog, not from browsing:
   papers (the `prior-art` skill), engineering work (StS bots,
   sts_lightspeed, write-ups). A borrowed technique lists its
   preconditions, each checked against this project's setting before it
   becomes a candidate.
4. **First principles.** Reason from where the losses are (`cause/`
   facts), from the bottleneck (machine time) and from what limits each
   goal. Every idea names the closest known technique and what differs,
   and is checked against this project's own record (`kb find`,
   `docs/decisions.md`) so a closed idea isn't re-proposed as new.
5. **Combinations.** After a lane closes, ask what its result says beyond
   its own question, alone and with other lanes' results.
6. **Likelihood in words.** Each candidate is rated likely, even or a long
   shot, with the evidence for and against; no probabilities. CPU-hours
   stay numbers. Priority: likelihood, what it moves (weighted by
   `docs/direction.md`) and its cost. Each `measurement/portfolio-*` fact
   records the rating beside the outcome, so the ratings can be checked.
7. **Pruning.** Retire candidates that went stale, were answered
   elsewhere or fall under the direction's avoid list; merge duplicates.
   Keep a spread: not every candidate from one family, at least one long
   shot in reach of the exploration slot.
8. **Queued work a new idea would waste.** When an idea, if it works,
   would make pending jobs worthless, its cheap probe runs first
   (`jobs.py first`) and those jobs wait on it (`jobs.py set <id> --after
   <probe>`), with a decisions entry the lane worker reads. After the
   read, the owning lane releases or drops them. Running jobs are never
   touched.
9. **Ready charters.** The top one or two backlog candidates carry a
   drafted charter (goal, measure, stop rule, kind, cap, end, on-close
   condition), so a lane worker can open one without designing it.
10. **Wake conditions** for its next run (below).

Ideas issues: the navigator reviews those the steward triaged (amendment
5) as part of steps 1-2. Idea work costs session time, not CPU: within the session
budget it uses subagents and workflows freely; past it, it keeps working
from facts without them. Only the exploration lane's CPU pauses first.

### Navigator: wakes

- **Self-set.** Each run ends by writing its wake conditions to
  `jobs/navigator-wakes.json`, each with the reason the result matters.
  Kinds, all checked by `health.py`: `job:<id>` (ends), `fact:<key>`
  (changes), `checkpoint:<lane>` (any new checkpoint), `ideas:<n>` (n
  new triaged ideas), `date:<YYYY-MM-DD HH:MM>`.
- **Fixed.** The owner's wake (below); stagnation; a lane worker's
  on-close wake (below); a safety backstop of 72 hours with no navigator
  run. A commit to `docs/direction.md` no longer wakes it (replaces that
  line of amendment 5); the next run reads it.
- **No daily limit and no daily schedule.** The launcher's one-at-a-time
  and 2-hour session limit stay.

### Owner access to the navigator

- **Notify:** `scripts/roles.py wake navigator "<note>"` adds an owner
  wake with the note to `jobs/navigator-wakes.json`. The launcher starts
  (or resumes) the navigator on its next tick, the note in its prompt's
  closing "This run started on" list (the role text stays first, so its
  cache holds); if a navigator is running, the note goes to the next run.
- **Chat:** `scripts/roles.py chat navigator` opens the navigator's last
  session interactively (`claude --resume <id>`, in a terminal), so the
  owner talks to it with its context. While the chat runs, the launcher
  counts the navigator as busy and starts no headless one beside it. If a
  headless navigator is running, `chat` says so and when it will end at
  the latest, and opens nothing.
- **`/approach`** ends by offering the owner a wake with a note naming
  what was recorded; the owner chooses.
- The digest lists each wake that fired and whether its run changed a
  ranking, a lane or a decision.

### Lane worker: closing and opening

- **Close.** At `done:` or its stop rule, cap or end, the lane worker
  closes its own lane in the order the navigator's prompt has today
  (decisions entry "Lane <name> closed (<date>)", retire the lane facts,
  `measurement/portfolio-<name>` with the rating, `jobs/lanes.json`), and
  writes the "reopen if" condition from the result.
- **On-close condition,** part of the charter (`lane/<name>`, `on-close:`
  field), written by the navigator. A simple form whenever it fits:
  `wake on go`, `wake on fail`, `wake always`, `wake never`, or
  `wake if <fact key> <comparison> <value>`; plain words only when those
  are too clunky or can't say it.
- **If it says wake:** the slot stays empty; the lane worker adds the
  wake. If no other lane has queued work, it queues the first ready
  candidate's first CPU job (not opening the lane) so the machine stays
  busy.
- **Otherwise,** or with no condition: the lane worker opens the first
  candidate with a ready charter, in backlog order, with the decisions
  entry, the charter fact and the shares. With no ready charter, the slot
  waits for the navigator (a fixed wake).

### Session reuse

The launcher resumes a role's previous session (`claude -p --resume
<id>`) instead of starting a fresh one when all hold:
- its last request was under 55 minutes ago (the logs show 1-hour cache
  writes);
- its last context was under 400k tokens (logs: 53k-224k so far);
- it ended cleanly (a result, not killed or errored);
- same role, model and effort, and the role's prompt file unchanged since
  it started; for the lane worker, the same lane.

A resumed session gets a short prompt: the new trigger, and an
instruction to treat everything in its context from before the resume as
possibly stale (re-read `jobs/health.json`, `kb render` and `git log`
since its last run before acting).

### Models

Navigator: Fable at high effort, before and after the budget switch (replaces
`decision/role-models`' navigator line). Lane worker: Opus at medium
effort, Sonnet at medium after the budget switch.

### Health, launcher and prompts

- `health.py`: evaluates `jobs/navigator-wakes.json` into
  `wakes.navigator`; drops the lane-closed and direction-edit triggers;
  keeps stagnation.
- `roles.py`: the 72-hour backstop replaces the daily one; session reuse;
  `wake` and `chat`; navigator model and effort.
- `.claude/skills/approach/SKILL.md`: step 4's "a committed change wakes
  the navigator" becomes the offer of a wake.
- `docs/roles/sts-navigator.md`: duties 1-10 lead; the portfolio
  bookkeeping moves to `docs/roles/sts-lanes.md`.
- `docs/operating.md`: the roles table, cadences and the lane-close rule.

### Verification

- `test_health.py`: each wake kind fires on its event and not before; the
  fixed wakes still fire with an empty wake file.
- `test_roles.py`: resume chosen only when every reuse condition holds,
  fresh otherwise (each condition failing alone); the 72-hour backstop;
  `wake` starts a navigator on the next tick with the note in its prompt;
  no headless navigator starts while a `chat` runs, and `chat` opens
  nothing while a headless one runs.
- A lane closed by the lane worker in a test lane with each on-close
  form: wake and empty slot, open the ready candidate, wait with no ready
  charter.
- After the build: the first navigator run's backlog shows new candidates
  with origins and ratings, and its wake file has reasons; the next digest
  reports resumed against fresh sessions' cost per run from the logs.

### Scope

`scripts/health.py`, `scripts/roles.py` and their tests;
`docs/roles/sts-navigator.md`, `docs/roles/sts-lanes.md`;
`.claude/skills/approach/SKILL.md`;
`docs/operating.md`; `docs/backlog.md` (the open-questions list, ratings
in place of probabilities); this spec; a decisions entry and
`decision/role-models`.

### Steps

1. `health.py` wakes with tests.
2. `roles.py` reuse, backstop, `wake`, `chat` and models with tests.
3. Prompts and operating.md.
4. Re-word the backlog's probabilities as ratings.
5. Commit, restart the launcher, read the first navigator run.
