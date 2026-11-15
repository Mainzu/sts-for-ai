# The job queue

Long runs (training, tests, benchmarks) go through a queue of jobs, so
each one starts without a person or a session having to start it. This
page covers adding and watching jobs, how the runner decides what to
start, and the dashboard.

## Job queue

Long runs go through a queue so the CPU never waits for a person or a
session to start the next one (`scripts/jobs.py`, state in `jobs/`,
gitignored; spec `docs/specs/lanes-runner.md`; the job-queue spec is folded
into this section and `docs/decisions.md`):

```
.venv/Scripts/python scripts/jobs.py add --threads 8 --estimate-min 120 [--lane run] -- .venv/Scripts/python -u scripts/curve.py --threads 8
.venv/Scripts/python scripts/jobs.py status
.venv/Scripts/python scripts/jobs.py run      # the runner; one at a time (jobs/runner.pid)
.venv/Scripts/python scripts/jobs.py wait     # exits on the next end (0) or failure/stall/suspect/parked/waiting (1)
.venv/Scripts/python scripts/jobs.py kill <id> --reason "hung"   # the runner ends the job's whole tree
.venv/Scripts/python scripts/jobs.py first <id>                  # start it next: reservation now, first in its lane
.venv/Scripts/python scripts/jobs.py set <id> [--lane L] [--after a,b] [--if-passed a,b] [--on-fail park|cancel]
.venv/Scripts/python scripts/jobs.py unpark <id>
.venv/Scripts/python scripts/jobs.py estimate <id> <minutes> [--reason "pace: 119 / 200"]   # pending or running
.venv/Scripts/python scripts/jobs.py verdict <id> pass|fail [--reason "..."]
.venv/Scripts/python scripts/jobs.py pins     # snapshots, the jobs pinned to them, their wheels
.venv/Scripts/python scripts/jobs.py unpin <commit>
.venv/Scripts/python scripts/jobs.py impact sts|scripts   # exit 1 if unpinned jobs would be hit
```

A family of reads (bursts, their reads, a table with a pass rule, follow-up
reads) is queued as one chain with `scripts/family.py queue
configs/families/<name>.json [--dry-run]`; `family.py table <file>` prints
its result and verdict from the files (docs/specs/session-free-reads.md).
A pack of generated enemy mechanics (`configs/packs/<name>.json`) queues
the same way: one joint burst per arm and seed, the zero-shot bench read
if missing, the bench reads, and a table whose per-net guard decides the
pack's net, written to `results/packs/<name>.json` only when one passes
(docs/specs/pack-adapt-pipeline.md).

To watch the roles and the queue, `python scripts/dashboard.py [--port 8766]`
serves a read-only page on http://127.0.0.1:8766 (health, running sessions
and jobs, recent role runs, lanes, what the navigator waits for, a
zoomable timeline; each role session
readable as a transcript; every done job
on `/queue`, paged and filtered); Ctrl+C stops it.

**Admission.** A job starts when its heavy slot fits (2 slots; a light
job takes none, a heavy job of 2 threads or fewer half a slot), the
runner's jobs' threads plus this one fit 14, the system's idle CPU covers
its threads (runs started by hand count as busy), the running jobs'
reserved memory (`--mem-gb`, or the measured `peak_gb` when higher) plus
this job's fit total memory minus 1 GB, and free memory (the smaller of
free RAM and commit headroom) is `--mem-gb` + 1 GB. When none of the
runner's jobs runs, commit headroom (RAM plus pagefile) alone counts, so
one job always runs, paging if it must. So `--mem-gb` is a
reservation: set it to the job's peak. The runner samples each running
job's process-tree working set every poll and keeps the largest as
`peak_gb` (shown by `status`); `add` warns, and records `mem_gb_low`,
when `--mem-gb` is below the last peak of the same script and first
argument. A job that can never start (threads above 14, `--mem-gb` + 1
above total memory, a broken job file) is moved to done as refused. Jobs
get `OMP_NUM_THREADS`, `RAYON_NUM_THREADS` and `STS_JOB_THREADS` set to
`--threads`, and still pass `--threads` to scripts that take it; Rust
searches that name no thread count use `STS_JOB_THREADS` (Rust
`default_threads`, Python `stsnet.job_threads`) instead of every core.

**Lanes.** Each job has a lane (`--lane`, default `main`); shares come
from `jobs/lanes.json` (`{"lane": share}`, read each poll, over the
defaults depth 35, run 30, goal1 25, train 10, main 10, filler 0; a lane
not named has 10). A lane's use is the sum over its running jobs of the
larger of threads / 14 and reserved memory / (total - 1 GB). Each poll the
runner tries lane heads in order of lowest use / share and starts the
first that fits (one start per poll); within a lane, name order. When a
lane's head waits for memory only, a later job of that lane may start
(backfill). The top lane head that has waited 10 minutes for any reason
gets the reservation (`first` gives it at once): while a job holds it,
another starts only if it fits alongside it (slots, thread budget,
reserved memory, as if both ran), and after 30 minutes the runner logs
`waiting`, which wakes `wait`. A lane with share 0 or below is a filler
lane: its head starts only when nothing else started that poll, and `add`
refuses a filler that is neither `--resumable` nor `--estimate-min` 20 or
less.

**Conditions.** `add --after a,b` waits until those jobs have ended;
`--if-passed a,b` until they ended and passed. A waiting job doesn't
block the ones behind it. When a condition can't hold any more (an
`--if-passed` dependency failed, was cancelled or refused, or ended-unknown
without a verdict; any dependency, `--after` included, is parked or in no
folder), the job is parked (`parked`
event; `status` shows the reason) or, with `--on-fail cancel`, cancelled;
parking cascades through chains. `set` changes a pending job's lane or
conditions and keeps its id; `unpark` clears a park (the next poll decides
again, so set a verdict or change the conditions first). A job passes when
it ended `ok`, or, with `add --check "cmd"` (one string, forward slashes),
when that check exits 0: the runner runs it after an `ok` end as its own
light process (killed after 10 minutes: fail), and records the `verdict`
with the check's last output line. `verdict <id> pass|fail` sets one by
hand. Prefer two jobs joined by `--if-passed` to `bash -c "A && B"`.

**Pinned code.** `add` pins the job to a snapshot of HEAD by default: a
detached, locked worktree `../sts-builds/<commit>/`
with main's data folders junctioned in (`results`, `db`, `cache`,
`datasets`, `models`, `logs`, `jobs`, `.venv`, `scripts/analysis/out`,
`runs`, and each ignored entry of `data/`, files by hard link) and its own
`sts` module in `pyroot/` (built from that commit, a few minutes when the
module changed, hard-linked from an earlier snapshot otherwise). The job
runs there with `PYTHONPATH` = its `pyroot`, so it writes results, runs and
the run index into main, and a merge, module swap or landing on main never
touches it. `add` refuses while the pinned paths (`scripts engine py
solvedb configs data/bench Cargo.toml Cargo.lock .cargo`) have uncommitted
or untracked files: commit, or use `--unpinned` (jobs that write tracked
files such as `bench_sets.py` and `puzzles.py`, jobs that write new files
directly in `data/`, runs by hand). `--pin <commit>` pins an older commit.
Snapshots are removed only by `unpin` or by the runner when no pending or
running job used one for 24 h, never by hand or by `git worktree remove`
(through a junction that would delete main's data); `unpin` refuses if the
snapshot holds anything besides its links and caches (a job's output).
`impact sts|scripts` lists the unpinned jobs a swap or merge would hit.

**Watching.** Output goes to `logs/jobs/<id>.log`. A log silent for 30
minutes is flagged `stalled`; a log tail with `Traceback`, `MemoryError`,
`memory allocation of` or `BrokenProcessPool` is flagged `suspect`.
Neither is killed: `kill` writes `jobs/running/<id>.kill` and the runner
ends the job on its next poll (status `killed`, with the reason and the
log's last lines). Each job runs in its own Windows Job Object and holds
its slot until its whole process tree is gone, worker processes included.
Jobs start through a frozen wrapper (`jobs/runner-<pid>/exec.py`) that
writes their exit code to `jobs/running/<id>.exit`, so they outlive the
runner and a restarted runner still records how an adopted job ended (it
watches only the wrapper's pid and kills with `taskkill /T`). Only a job
with no exit file (started before the wrapper existed, or whose wrapper
was killed from outside) ends as `ended-unknown`.
