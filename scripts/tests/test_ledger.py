"""Tests for scripts/analysis/ledger.py (docs/specs/session-free-reads.md):
on the files on disk, the effects recipes reproduce the edges of review
2026-11-06 direction 3; skipped when the files are missing."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import jobs  # noqa: E402
import ledger  # noqa: E402


def test_effects_recipes_reproduce():
    root = Path(jobs.REPO)
    if not (root / "results" / "gauntlet" / "net1029-hpb0.01-b500.json").exists():
        print("skip: gauntlet files missing")
        return
    rows = {label: r for label, r, _ in ledger.ledger(root)}
    for label, want, files in (("effects 5k", -3.30, 10), ("effects 20k", -1.45, 10), ("effects 40k", -0.16, 6)):
        r = rows[label]
        assert r is not None and abs(r["hp"] - want) < 0.01 and r["files"] == files, (label, r)


if __name__ == "__main__":
    test_effects_recipes_reproduce()
    print("ok")
