# Lane blind-row-kinds: charter

The lane's charter as the navigator wrote it. `lane/blind-row-kinds` holds a summary and cites this file.

goal: goal 1's first-class custom content, every content element a custom power or monster can use reaches the net's inputs under the default row kinds (cause/roundend-blind);
measure: a test over registry::element_names() that builds a one-element power (and monster where the element is a move or pattern atom) and asserts the default encoder writes a row that changes with it, listing each blind element;
starting list (read only, to be confirmed by the test): docs/research/engine-audit.md entries 9 (BlockAlly, ApplyPack, Heal, HealOf, GainMaxHp, DrawPicked, PlayTop, Discover, ObtainRandomPotions write no column) and 14 (default-off kinds); the first code step may be entry 9's per-named-column pins, so each added column is no re-pin;
for each blind element a fix that writes the row it needs without the official rows the opt-in kinds would add, series_check PASS (the product net bit-identical), and the feature cache's rows per state on the fixed set unchanged;
stop: go if at least one blind element beyond RoundEnd is found and fixed with series_check passing;
fail (closed as filed, the test kept) if none is found;
kind: exploration;
cap: 5 cpu-h;
end: 2026-11-14 (ended early: one lane at a time, `decision/one-lane`);
on-close: no wake and no new lane: the slot stays empty while one lane runs at a time
