# Lane machine-throughput: charter

The lane's charter as the navigator wrote it. `lane/machine-throughput` holds a summary and cites this file.

goal: machine time for both goals: more decided reads per day from the same machine;
measure: (a) a 40k learn's feature cache sparse, batches bit-identical to the dense cache (a test), the confirming learn's wall time and peak commit against 0926 (60 min, 6.8 GB);
(b) the control-arm cache in mutate_monsters.py keyed by the .pyd hash and the arm's spec, a cached arm byte-identical to a re-run (a test);
(c) the stall check reading .partial progress (a test on 0929's log and file);
(d) queue_replay.py with a slot-count option, 3 slots over jobs/done since 11-04, adopted only if it recovers 2 h or more;
(e) test-full with files in parallel inside 4 threads, and one full run passing or naming its failures (that run waits for decision/filler-hold to lift;
no test-full under any lane meanwhile);
stop: go when (a) cuts the learn's wall time by a fifth or its peak by a third with identical batches, and (b) and (c) land with their tests;
fail if (a) is slower or not identical and (b) does not land (then the parts that landed stay, and the lane closes);
kind: project;
cap: 15 cpu-h;
end: 2026-11-14 (ended early: one lane at a time, `decision/one-lane`);
on-close: no wake and no new lane: the slot stays empty while one lane runs at a time
