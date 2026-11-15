# Gauntlet early stop: play in blocks, stop when the protocol decides

Status: closed (2026-11-02, built and in use; decisions "Gauntlet early stop built"; 2b4188e1; gauntlet.py --block and --against in use).

## Why (goal 2)

Goal 2's candidates are read on the Act-1 gauntlet with the gauntlet
protocol (decisions "Gauntlet protocol"): a sequential test on paired
end-HP that, replayed over the existing files, stops real effects at
50-160 sequences instead of 500. But `gauntlet.py play` writes nothing
until every sequence has finished, so every read still pays for 250-500
sequences (two-turn reads: 2-4 h each on 3 threads), and a crash loses
the whole run (0059l7r3b1). Machine time is the bottleneck: letting a
read stop when the protocol decides cuts goal-2 reads ~2-3x, so about
twice as many candidates get read per day. We'll know: a play with
`--against` stops at the protocol's n with the same verdict the replay
script gives on the finished file, and the file on disk grows block by
block.

## Outcome

`gauntlet.py play ... [--block N] [--against <control.json>]`:
- sequences are played in blocks of N (default 50) in index order, and
  the output file is rewritten after each block with every row so far
  (resume already skips rows on disk);
- with `--against`, after each block the protocol runs on the sequences
  played so far that the control file also holds (same cell), in index
  order; on pass, fail or fail-guard the play stops and prints the
  verdict and n.

Non-goals: no change to what a sequence plays (results per sequence are
identical to an unblocked run), no runner changes, no new rule.

## Behavior

- Rule: `scripts/analysis/gauntlet_protocol.py`'s `sprt` and `end_hp`
  (H1 +1.5 HP, alpha = beta = 0.05, first look at 50, clears guard
  z <= -2), imported, not copied. `--d1` and `--min-n` pass through.
- The verdict is written into the file as a top-level `protocol` key
  (`against`, `verdict`, `n`, `d1`, `min_n`); `settings` stay as they are
  so resume and older files keep matching. Without a verdict yet
  (`open`), the key records that too.
- `--against` with a control whose `seed` or `shape` differs: refuse
  before playing.
- A resumed play with `--against` checks first, before playing more, so
  a finished decision isn't extended.

## Verification

Tests in `scripts/tests/test_gauntlet.py` with the fake player:
- blocked play gives the same rows as one block (with rewards random
  too), and the file is written once per block;
- `--against` stops at the block where the replay's `sprt` would stop,
  given a control that loses / wins every fight;
- a mismatched control is refused.
Then one real check: replay `gauntlet_protocol.py` on a finished pair and
compare with the `protocol` key of a short `--against` play over the same
sequences (heuristic one turn, cheap).

## Build plan

One step, in session (small). Model: current.
