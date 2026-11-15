# Lane wide-recipe-confirm: charter

The lane's charter as the navigator wrote it. `lane/wide-recipe-confirm` holds a summary and cites this file.

goal: goal 1, whether the wide generated recipe's zero-shot cut on unseen enemy pairings and on the owner's yardstick holds across training seeds, as the base net for later goal-1 steps, on an encoding that shows the net every power it trains on;
measure: order: seeds 101 and 201 of the wide recipe first, trained now on the current encoding and read as below; the lane closes at the seeds-go checkpoint, and step 0 below moves to `lane/final-round` as its optional input 3(a) (`decision/one-lane`), so its text stays only as the record;
step 0 (code) a `RoundEnd` hook that isn't a pure `ReduceSelf` countdown written as a `triggered` row and counted by `is_hook_power` (a test: a GE-RoundEnd power writes one triggered row;
`series_check` PASS, the product net bit-identical), then seed 1 of the wide recipe relearned on it (configs as widepack40k-s1, 40k games) and read @tsl1 one turn deep on the wide grid's rows (675 official elite starts x 2 seeds) against `gen-wide-wp1-tsl1.json`: the RoundEnd rows apart, the rest pooled;
if engine audit entry 6 (`Effect::scaled` scales every effect, so 2-stack GE-*-Dazed atoms add two Dazed) lands before that relearn, the five GE-*-Dazed rows are reported apart as well, out of both pools (their content changed with the net);
then per seed (1 if step 0 passed, else seed 1's old-encoding files;
101, 201) the wide grid's new rows, the 24 old rows (x 4 seeds), the yardstick rows as 0931 (`docs/research/genpack-yardstick.md`, same mods, 675 x 2), cells and pack headline against the seed-1 controls;
pooled over the three seeds of the wide recipe's held-out rows against pack-net-scratch s1 (and its s101/s201 files where they exist), the yardstick also against the 18-mechanic three-seed pool (descriptive);
stop: step 0 passes if the RoundEnd rows' pooled cost beyond parent falls by 1 HP or more at 2 se and the other rows are not worse by 0.3 HP at 2 se (the final training run and later base nets then use the fixed encoding);
else the fix stays in code as a correction;
seeds 101 and 201 don't wait on it either way;
go if the three-seed pooled new held-out cut is 0.7+ at 2 se, the old held-out not worse than the 18-mechanic three-seed pool at 2 se, the yardstick's pooled cost over sharp2, thorns2, ritual2, weakhit1 at most half pns1's (+4.03) at 2 se, and cells and pack headline within -1.5 HP;
fail if the pooled cut is under 0.5, a seed's cut under 0.3, or the yardstick's pooled cost over half pns1's (the seed-1 result was luck);
kind: project;
cap: 76 cpu-h;
end: 2026-11-20;
on-close: no wake and no new lane: `lane/final-round` takes the recipe from this close (seeds-go)
