"""The full Python test run, as one queue job (job id `<NNNN>-test-full`). Runs pytest
with the system interpreter on the venv's packages (pytest isn't in
.venv), keeping the job's PYTHONPATH (a pinned job's `sts`) first.

Each scripts/tests/test_*.py file runs in its own pytest process, one
after another, so memory one file leaves behind never adds to the next
(one process over the whole folder peaked at 9.8 GB). Each file's line
gives its exit code, wall time and peak working set (its process tree,
sampled every 2 s); a table sorted by peak and the failing files close
the log. Exit code: the worst file's (pytest's 5, no tests collected,
counts as 0). Files in NOT_DEFAULT are left out (decisions, "test_sweep out
of the default test set"); run them with `--per-test` or pytest by hand.

    python -u scripts/test_full.py [extra pytest args, passed to each file]
    python -u scripts/test_full.py --per-test <test file>... [-- extra pytest args]
    python -u scripts/test_full.py --cap-gb G --per-test <test file>...

`--per-test` runs only the named files, each test in its own process (its
pytest node id in place of the file), to find which tests hold a file's peak.
`--cap-gb G` kills a process whose tree passes G GB (sampled every 0.5 s)
and reports it as `over cap` (exit 99), so a job reserving under what is
free can still name the tests that need more.
"""

import glob
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jobs import tree_mem_gb  # noqa: E402

PYTHON = os.environ.get("STS_TEST_PYTHON", sys.executable)
SAMPLE_S = 2.0
OVER_CAP = 99  # exit code reported for a process killed at --cap-gb
NOT_DEFAULT = ("scripts/tests/test_sweep.py",)  # 46 of 0206's 145 minutes


def run_file(path, argv, here, env, cap=None):
    """Run pytest on one file; (exit code, seconds, peak GB). With `cap`
    (GB), a tree passing it is killed and reported as OVER_CAP."""
    t0 = time.monotonic()
    p = subprocess.Popen([PYTHON, "-m", "pytest", "-q", "-p", "no:cacheprovider", path, *argv], cwd=here, env=env)
    peak = 0.0
    while True:
        try:
            code = p.wait(timeout=SAMPLE_S if cap is None else 0.5)
            break
        except subprocess.TimeoutExpired:
            peak = max(peak, tree_mem_gb({"pid": p.pid}))
            if cap is not None and peak > cap:
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
                p.wait()
                print(f"test-full: {path} over cap {cap:.2f} GB, killed", flush=True)
                return OVER_CAP, time.monotonic() - t0, peak
    return (0 if code == 5 else code), time.monotonic() - t0, peak


def node_ids(path, here, env):
    """The pytest node ids of one test file, in collection order."""
    out = subprocess.run([PYTHON, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", path],
                         cwd=here, env=env, capture_output=True, text=True).stdout
    return [line.strip() for line in out.splitlines() if "::" in line]


def main(argv):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    site = os.path.join(sys.prefix, "Lib", "site-packages")  # run it with .venv's python
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (env.get("PYTHONPATH"), site) if p)
    cap = None
    if argv[:1] == ["--cap-gb"]:
        cap, argv = float(argv[1]), argv[2:]
    if argv[:1] == ["--per-test"]:
        cut = argv.index("--") if "--" in argv else len(argv)
        files = [n for f in argv[1:cut] for n in node_ids(f, here, env)]
        argv = argv[cut + 1:]
    else:
        files = sorted(os.path.relpath(f, here).replace("\\", "/")
                       for f in glob.glob(os.path.join(here, "scripts", "tests", "test_*.py")))
        files = [f for f in files if f not in NOT_DEFAULT]
        print(f"test-full: left out (not default): {', '.join(NOT_DEFAULT)}", flush=True)
    rows = []
    for f in files:
        code, secs, peak = run_file(f, argv, here, env, cap)
        rows.append((f, code, secs, peak))
        print(f"test-full: {f} exit {code} {secs / 60:.1f} min peak {peak:.2f} GB", flush=True)
    print("\ntest-full: files by peak working set")
    for f, code, secs, peak in sorted(rows, key=lambda r: -r[3]):
        print(f"  {peak:5.2f} GB  {secs / 60:6.1f} min  exit {code}  {f}")
    failed = [f for f, code, _, _ in rows if code]
    total = sum(r[2] for r in rows) / 60
    print(f"test-full: {len(rows)} files, {total:.1f} min, max peak {max((r[3] for r in rows), default=0):.2f} GB, "
          f"failed: {', '.join(failed) or 'none'}", flush=True)
    return max((code for _, code, _, _ in rows), default=0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
