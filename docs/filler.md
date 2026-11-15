# Filler: the steward's standing small jobs

**ON HOLD until the owner lifts it (`decision/filler-hold`):** queue no
filler job, `test-full` included, whatever `jobs/health.json` shows.

Lane `filler` (share 0): a filler job starts only when no other lane's job
started that poll, and it must be `--resumable` or estimated at 20 minutes
or less. The steward tops filler up when `jobs/health.json` shows `cpu` or
`ready` red, or `tests` red. Rules:
- At most one pending or running job per entry: each entry's note starts
  with `filler: <entry>`, so `grep -l '"note": "filler: <entry>'
  jobs/pending/*.json jobs/running/*.json` finds it.
- Add from the main checkout, pinned: `--pin $(git rev-parse HEAD)`.
- Filler never writes a file a lane is writing.
- Keep at least one resumable standing job below, so the CPU has work when
  no lane queues any.
- Set `--mem-gb` from the entry's last `peak_gb` (`jobs.py status`, or its
  record in `jobs/done/`) and `--estimate-min` from its last wall time.
- The standing CPU job must fit when nothing of ours runs: the runner
  needs `--mem-gb` + 1 GB free, so keep it small (fewer threads, not a
  lower reservation than its peak).

## Standing jobs

### test-full

The full Python test run; `scripts/health.py` finds it by its id
(`<NNNN>-test-full`, from the script name). Queue it when `tests` is red
(failing, older than 48 h, or never run) and none is pending or running:

```
.venv/Scripts/python.exe scripts/jobs.py add --lane filler --resumable --threads 4 --mem-gb 4 --estimate-min 130 --pin $(git rev-parse HEAD) --note "filler: test-full. The full Python suite (docs/filler.md). Pass: exit 0. A failure is the lane worker's first task: it names the failing tests and fixes or files them." -- .venv/Scripts/python.exe -u scripts/test_full.py
```

It runs each test file in its own pytest process and logs each file's peak
working set; set `--mem-gb` from the last run's largest file peak plus a margin.

## One-off chores

None open.
