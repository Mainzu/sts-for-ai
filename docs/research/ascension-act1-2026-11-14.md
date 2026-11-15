# Ascension in Act 1 combat: every branch in the game's code (2026-11-14)

Research for `docs/specs/ascension.md`. Each group's reader listed every read of `AbstractDungeon.ascensionLevel` in its classes
(installed `desktop-1.0.jar`, javap; class, method and bytecode offset), with the A0 and ascended values and where it plugs into the engine;
a skeptic per group re-read the classes for misses and wrong values. Every check is a threshold (`ascensionLevel >= N`): A20 takes every branch.

## normals-a

| Class | Level | What | A0 | Ascended | Engine | Cite |
|---|---|---|---|---|---|---|
| Cultist | 7 | HP range (setHp) | 48-54 | 50-56 | data: monsters.json Cultist "hp" | Cultist.<init>(float,float,boolean) @42 getstatic, bipush 7, if_icmplt 61 |
| Cultist | 2 | field ritualAmount (Incantation's Ritual) | 3 | 4 | data: Cultist move 0 Incantation Apply Ritual amount | Cultist.<init>(float,float,boolean) @89 getstatic, iconst_2, if_icmplt 104 |
| Cultist | 17 | Incantation applies RitualPower(ritualAmount+1) instead of ritualAmount | Ritual 3 | Ritual 5 (ritualAmount 4 + 1) | data: same Incantation amount field, A17 row = 5 | Cultist.takeTurn @111 getstatic, bipush 17, if_icmplt 152 (iconst_1 iadd @137-138) |
| JawWorm | 7 | HP range | 40-44 | 42-46 | data: monsters.json Jaw Worm "hp" | JawWorm.<init>(float,float,boolean) @43 getstatic, bipush 7, if_icmplt 62 |
| JawWorm | 17 | bellowStr/bellowBlock/chompDmg/thrashDmg/thrashBlock | Str 3, Block 6, Chomp 11, Thrash 7 + 5 block | Str 5, Block 9, Chomp 12, Thrash 7 + 5 | data: Jaw Worm moves Bellow (Apply Strength, Block) and Chomp Damage | JawWorm.<init> @70 getstatic, bipush 17, if_icmplt 109 (putfields @79-103) |
| JawWorm | 2 | same fields, A2-16 tier | Str 3, Block 6, Chomp 11 | Str 4, Block 6, Chomp 12 (Thrash 7/5 unchanged) | data: Bellow Strength + Chomp Damage amounts | JawWorm.<init> @109 getstatic, iconst_2, if_icmplt 147 |
| LouseNormal (Red Louse) | 7 | HP range | 10-15 | 11-16 | data: monsters.json Red Louse "hp" | LouseNormal.<init>(float,float) @59 getstatic, bipush 7, if_icmplt 78 |
| LouseNormal (Red Louse) | 2 | biteDamage rolled from monsterHpRng | random(5,7) | random(6,8) | CODE: monsters.rs louse::setup `5 + rng.below(3)` -> needs a data range (e.g. "rolled_attack": [lo,hi]) | LouseNormal.<init> @86 getstatic, iconst_2, if_icmplt 110 |
| LouseNormal (Red Louse) | 17 | Curl Up amount (usePreBattleAction) | random(3,7) | random(9,12) | CODE: louse::setup `3 + rng.below(5)` CurlUp -> data range | LouseNormal.usePreBattleAction @0 getstatic, bipush 17, if_icmplt 44 |
| LouseNormal (Red Louse) | 7 | Curl Up amount, A7-16 tier | random(3,7) | random(4,8) | CODE: louse::setup -> data range | LouseNormal.usePreBattleAction @44 getstatic, bipush 7, if_icmplt 87 |
| LouseNormal (Red Louse) | 17 | Grow Strength amount | 3 | 4 | data: Red Louse move 1 Grow Apply Strength amount | LouseNormal.takeTurn @189 getstatic, bipush 17, if_icmplt 225 |
| LouseNormal (Red Louse) | 17 | AI: in roll<25 branch Grow blocked after ONE Grow (lastMove(4)) instead of after two (lastTwoMoves(4)); bite branch unchanged | roll<25: lastTwoMoves(GROW)? Bite : Grow | roll<25: lastMove(GROW)? Bite : Grow | data: pattern row [RollBelow 25, LastTwo 1] -> [RollBelow 25, LastMove 1] | LouseNormal.getMove @0 getstatic, bipush 17, if_icmplt 112 (lastMove @16 vs lastTwoMoves @120) |
| LouseDefensive (Green Louse) | 7 | HP range | 11-17 | 12-18 | data: monsters.json Green Louse "hp" | LouseDefensive.<init>(float,float) @59 getstatic, bipush 7, if_icmplt 78 |
| LouseDefensive (Green Louse) | 2 | biteDamage roll | random(5,7) | random(6,8) | CODE: louse::setup -> data range | LouseDefensive.<init> @86 getstatic, iconst_2, if_icmplt 110 |
| LouseDefensive (Green Louse) | 17 | Curl Up amount | random(3,7) | random(9,12) | CODE: louse::setup -> data range | LouseDefensive.usePreBattleAction @0 getstatic, bipush 17, if_icmplt 44 |
| LouseDefensive (Green Louse) | 7 | Curl Up amount, A7-16 tier | random(3,7) | random(4,8) | CODE: louse::setup -> data range | LouseDefensive.usePreBattleAction @44 getstatic, bipush 7, if_icmplt 87 |
| LouseDefensive (Green Louse) | 17 | AI: Spit Web (move 4, DEBUFF) blocked after one use (lastMove) instead of two (lastTwoMoves) in roll<25 branch; Spit Web's Weak 2 has no ascension check | lastTwoMoves(WEB)? Bite : Web | lastMove(WEB)? Bite : Web | data: pattern row [RollBelow 25, LastTwo 1] -> [RollBelow 25, LastMove 1] | LouseDefensive.getMove @0 getstatic, bipush 17, if_icmplt 112 |
| FungiBeast | 7 | HP range | 22-28 | 24-28 | data: monsters.json Fungi Beast "hp" | FungiBeast.<init>(float,float) @21 getstatic, bipush 7, if_icmplt 40 |
| FungiBeast | 2 | field strAmt (Grow); biteDamage set to 6 on both sides | strAmt 3, bite 6 | strAmt 4, bite 6 | data: Fungi Beast move 1 Grow Apply Strength amount | FungiBeast.<init> @48 getstatic, iconst_2, if_icmplt 69 |
| FungiBeast | 17 | Grow applies Strength strAmt+1 | Strength 3 | Strength 5 (4+1) | data: Grow amount, A17 row = 5 | FungiBeast.takeTurn @96 getstatic, bipush 17, if_icmplt 142 (iconst_1 iadd @122-123) |
| Looter | 17 | goldAmt (gold stolen per hit, Thievery) | 15 | 20 | not modelled: engine has no gold in CombatState; no combat effect, skip or record only | Looter.<init>(float,float) @56 getstatic, bipush 17, if_icmplt 73 |
| Looter | 7 | HP range | 44-48 | 46-50 | data: monsters.json Looter "hp" | Looter.<init> @79 getstatic, bipush 7, if_icmplt 98 |
| Looter | 2 | swipeDmg (Mug) / lungeDmg | Mug 10, Lunge 12 | Mug 11, Lunge 14 | data: Looter moves 0 Mug and 1 Lunge Damage amounts | Looter.<init> @106 getstatic, iconst_2, if_icmplt 128 |
| SlaverBlue | 7 | HP range | 46-50 | 48-52 | data: packs/act1-monsters.json Blue Slaver "hp" | SlaverBlue.<init>(float,float) @37 getstatic, bipush 7, if_icmplt 56 |
| SlaverBlue | 2 | stabDmg / rakeDmg | Stab 12, Rake 7 | Stab 13, Rake 8 | data: Blue Slaver moves Stab/Rake Damage | SlaverBlue.<init> @64 getstatic, iconst_2, if_icmplt 86 |
| SlaverBlue | 17 | Rake applies Weak weakAmt+1 (weakAmt=1 set @33) | Weak 1 | Weak 2 | data: Rake Apply Weak amount | SlaverBlue.takeTurn @127 getstatic, bipush 17, if_icmplt 178 |
| SlaverBlue | 17 | AI: in roll<40 (or Stab-blocked) branch, Rake blocked after one Rake (lastMove(4)) instead of two (lastTwoMoves(4)) | !lastTwoMoves(RAKE)? Rake : Stab | !lastMove(RAKE)? Rake : Stab | data: pattern row [LastTwo 0] -> [LastMove 1]-style rewrite: A17 rows = [RollBelow 40, LastTwo 1]->Stab kept for roll>=40 branch; [LastTwo 1 / LastMove 1] row for the fallback (engine row [{LastTwo 0}]->Rake and the RollBelow-40 rows must be re-expressed with LastMove 1 -> Stab) | SlaverBlue.getMove @37 getstatic, bipush 17, if_icmplt 104 (lastMove @47 vs lastTwoMoves @106) |
| SlaverRed | 7 | HP range | 46-50 | 48-52 | data: packs/act1-monsters.json Red Slaver "hp" | SlaverRed.<init>(float,float) @35 getstatic, bipush 7, if_icmplt 54 |
| SlaverRed | 2 | stabDmg / scrapeDmg | Stab 13, Scrape 8 | Stab 14, Scrape 9 | data: Red Slaver moves 0,3 Stab and 1,4 Scrape Damage (two copies each, engine encodes usedEntangle by move id) | SlaverRed.<init> @62 getstatic, iconst_2, if_icmplt 84 |
| SlaverRed | 17 | Scrape applies Vulnerable VULN_AMT+1 (VULN_AMT=1 set @22) | Vulnerable 1 | Vulnerable 2 | data: Scrape Apply Vulnerable amount on moves 1 and 4 | SlaverRed.takeTurn @272 getstatic, bipush 17, if_icmplt 323 |
| SlaverRed | 17 | AI fallback (after first-turn Stab, Entangle roll, post-Entangle Stab roll): Scrape blocked after one Scrape (lastMove(3)) instead of two (lastTwoMoves(3)) | !lastTwoMoves(SCRAPE)? Scrape : Stab | !lastMove(SCRAPE)? Scrape : Stab | data: pattern rows [RollBelow 75, LastTwo 1]->0 become [RollBelow 75, LastMove 1]->0; [LastMove 4, RollBelow 50, LastTwo 4]->3 becomes [LastMove 4, RollBelow 50]->3 | SlaverRed.getMove @94 getstatic, bipush 17, if_icmplt 159 (lastMove @104 vs lastTwoMoves @161) |

**Design (reader).** What the eight classes need: HP ranges (A7), move numbers (A2 and A17), pattern rows where LastTwo becomes LastMove (A17: both lice, both slavers), and the louse rolls: bite 5-7 becomes 6-8 at A2; Curl Up 3-7 becomes 4-8 at A7 and 9-12 at A17. Only the louse rolls are code today, in engine/src/monsters.rs louse::setup (`5 + rng.below(3)`, `3 + rng.below(5)`). Everything else is already data that registry.rs parse_monster_as reads from content/monsters.json and content/packs/act1-monsters.json ("hp", move "effects" amounts, "pattern" rows). None of these AIs needs new code: every change maps onto existing PatCond values (LastMove, LastTwo, RollBelow). Looter's goldAmt has no combat effect, because the engine keeps no gold.

Smallest general design:
(1) Data: a monster entry may carry "ascension": [{"min": 2, ...}, {"min": 7, ...}, {"min": 17, ...}]. Each row restates whole top-level fields ("hp", "moves", "pattern", "start_powers", and two new fields "rolled_attack": [lo,hi] and "curl_up": [lo,hi], or one general "rolled_powers": [{power, range}]). Rows apply in ascending order of min, for every min <= the combat's level. Restating whole fields lets the parser merge the JSON objects and reuse parse_monster_as unchanged, with no per-field patch syntax. Moving the louse rolls into data (A0 values [5,7] and CurlUp [3,7]) turns louse::setup into one general "roll these ranges" setup.
(2) Resolve once, at combat creation: the registry builds one MonsterDef per (kind, distinct min tier) (Act 1 normals: tiers 0, 2, 7, 17), and kind.at(level) maps a base kind to its variant kind. pattern_ai, Monster::def(), the heuristic's move caches and the hashing stay untouched, because the variant is simply another MonsterKind. The alternative, an `ascension: u8` field on CombatState with def_at(level) lookups, would need the state passed into Monster::def() and the AI, and would change cache keys.
(3) Plumbing: one `ascension: u8` argument (default 0) on CombatState::new_with_turn1. The other new* constructors pass 0. It is applied as kinds = kinds.map(|k| k.at(asc)) before the HP roll at state.rs ~1749, so HP is rolled from the variant's hp_min/hp_max and (d.setup) runs the variant's ranges. encounter.roll_monsters stays the same. Store the level on CombatState too, so that view() can report it.
(4) py/src/lib.rs: Combat(..., ascension=0) and the monsters-list constructor pass it through. view() writes "ascension", and from_view reads it (default 0) to map each monster's name to its variant kind. Without this, a view from an A17 game rebuilds A0 move numbers and patterns, because from_view keeps the view's hp, powers and rolled_damage but takes move effects and pattern from the kind's def.
Tier count stays small: a kind gets one variant per distinct min that its own rows list, not one per level 0-20.

**Notes.** The constructor parameters `boolean` on Cultist(float,float,boolean) and JawWorm(float,float,boolean) are not ascension checks. Cultist's is the talk flag, and JawWorm's sets hardMode (JawWorm.<init> @28 putfield hardMode, read in getMove @1 for the Act 3 variant). No method parameter named ascensionLevel appears in these 8 classes. Every check found is `getstatic AbstractDungeon.ascensionLevel` followed by if_icmplt, meaning level >= N takes the ascended side. Some classes cascade A17 before A2 (JawWorm, Louse Curl Up), so A17 values include the A2 changes.

Mismatches between the engine data and the bytecode (this task was read-only, so I didn't change them):
(a) Red Slaver after Entangle. SlaverRed.getMove @50-53 is `iload_1; bipush 55; if_icmplt 94`: Stab (when not after two Stabs) on roll >= 55. The pack rows use RollBelow 50 for the post-Entangle copies (moves 3 and 4), giving 50/50 instead of 45% Stab / 55% Scrape.
(b) The Red Louse and Green Louse rows give A0 HP 10-15 and 11-17, which match. Fungi Beast A0 is 22-28, also a match.
(c) In engine/src/monsters.rs, the louse doc comment ("Curl Up 3-7", "Bite 5-7") holds only at A0.

For the Blue Slaver A17 pattern, the Java fallback order is: roll >= 40 and not lastTwo(STAB) gives Stab. Otherwise, at A17, not lastMove(RAKE) gives Rake, else Stab. At A0 it is not lastTwo(RAKE). The engine's A17 rows are:
- [RollBelow 40, LastMove 1] -> Stab
- [RollBelow 40] -> Rake
- [LastTwo 0, LastMove 1] cannot both hold, so: [LastTwo 0] -> Rake
- [] -> Stab
Check this against the golden games before landing it.

Scratch disassembly is in <scratchpad>/na/*.txt. Delete it when done.

**Skeptic: confirmed.** I disassembled all 8 classes again and counted every getstatic of AbstractDungeon.ascensionLevel: Cultist 3, JawWorm 3, LouseNormal 6, LouseDefensive 5, FungiBeast 3, Looter 3, SlaverBlue 4, SlaverRed 4, 31 in all. The research has a branch for each of the 31, and every threshold, offset and A0/ascended value it gives matches the bytecode.

Values I checked against the bytecode:
- HP setHp at A7: Cultist 50-56, Jaw Worm 42-46, Red Louse 11-16, Green Louse 12-18, Fungi Beast 24-28, Looter 46-50, both slavers 48-52.
- Cultist: ritualAmount is 4 at A2 (3 at A0), and at A17 Incantation applies ritualAmount+1 (takeTurn @137-138).
- Jaw Worm tiers: A17 is Str 5 / Block 9 / Chomp 12 / Thrash 7 + 5 block. A2 is Str 4 / Block 6 / Chomp 12. A0 is Str 3 / Block 6 / Chomp 11.
- Both lice: bite is monsterHpRng random(6,8) at A2, random(5,7) at A0. Curl Up is random(9,12) at A17, random(4,8) at A7, random(3,7) at A0.
- Red Louse: Grow gives Strength 4 at A17 (takeTurn @211 iconst_4).
- Both lice getMove @0: at A17 the roll<25 branch tests lastMove(4); below A17 it tests lastTwoMoves(4) (@120).
- Fungi Beast: strAmt is 4 at A2 and 3 at A0. Bite is 6 on both sides, and A17 adds +1 to the Grow Strength.
- Looter: goldAmt is 20 at A17 and 15 at A0. Mug/Lunge are 11/14 at A2 and 10/12 at A0.
- Blue Slaver: Stab/Rake are 13/8 at A2 and 12/7 at A0. At A17 Rake applies Weak weakAmt+1 = 2. getMove @37-50 at A17 is `lastMove(4) ifne` (meaning Stab), so the Rake test is lastMove instead of lastTwoMoves.
- Red Slaver: Stab/Scrape are 14/9 at A2 and 13/8 at A0. At A17 Scrape applies Vulnerable VULN_AMT+1 = 2. In the getMove fallback @94, A17 tests lastMove(3) and A0 tests lastTwoMoves(3).

Minor wording fixes, no wrong values:
(1) Blue Slaver: the engine text on the AI branch is muddled. Only one row changes. A0 row [RollBelow 40, LastTwo 1] -> Move 0 becomes [RollBelow 40, LastMove 1] -> Move 0 at A17. The other three rows stay as they are. The final row list in the notes is correct, because when the roll is 40 or more and lastTwo(Stab) holds, the last move is Stab and not Rake, so Rake follows.
(2) Red Slaver at A17: rewriting the row [LastMove 4, RollBelow 50, LastTwo 4] -> 3 to drop LastTwo 4 leaves the next row [LastMove 4, RollBelow 50] -> 4 unreachable. The simpler A17 rewrite is to delete both rows and keep [LastMove 4] -> 3. The behaviour is the same either way.
(3) Engine mismatch (a) is confirmed. SlaverRed.getMove @50-53 is `iload_1; bipush 55; if_icmplt 94`, and the Entangle setMove at @46 is followed by a return at @49. So after Entangle the threshold is roll >= 55 for Stab, but the pack rows for moves 2, 3 and 4 use RollBelow 50. That is an A0 bug in content/packs/act1-monsters.json (Red Slaver pattern rows 2, 4, 7 and 8), separate from ascension.

Engine placement is confirmed: everything except the louse rolls is already data in content/monsters.json and content/packs/act1-monsters.json. The louse rolls are code in engine/src/monsters.rs louse::setup lines 272-274 (`5 + rng.below(3)`, `3 + rng.below(5)`). Lice moves use the "RolledAttack" effect, so the bite range needs a data field.

**Missed (skeptic).** Nothing missed. The research has every ascensionLevel read in the 8 classes (31 in all). The only boolean constructor parameters are on Cultist (the talky flag) and JawWorm (hardMode), and neither is an ascension check. No parameter in these classes is named ascensionLevel.

## normals-b

| Class | Level | What | A0 | Ascended | Engine | Cite |
|---|---|---|---|---|---|---|
| AcidSlime_S | 7 | HP roll (setHp) | 8-12 | 9-13 | data: monster row hp, content/monsters.json "Acid Slime (S)" hp [8,12] | AcidSlime_S.<init>(FFI) off 21 getstatic; 24 bipush 7; 26 if_icmplt 40 |
| AcidSlime_S | 2 | Tackle damage (damage[0]) | 3 | 4 | data: move Tackle Damage.amount in content/monsters.json | AcidSlime_S.<init>(FFI) off 48 getstatic; 51 iconst_2; 52 if_icmplt 75 (64 iconst_4 vs 84 iconst_3) |
| AcidSlime_S | 17 | getMove (only the opening move; takeTurn alternates via setMove): A17 picks Lick (byte 2) unless lastTwoMoves(1), i.e. always Lick first; A0 aiRng.randomBoolean() 50/50 Tackle/Lick | FirstTurn 50% Tackle / 50% Lick | FirstTurn always Lick | data: pattern row (FirstTurn -> Move 0 instead of Chance 0.5) in a min-level-17 pattern | AcidSlime_S.getMove off 0 getstatic; 3 bipush 17; 5 if_icmplt 52 |
| AcidSlime_M | 7 | HP roll in 2-arg ctor only (the split ctor (FFII) takes the parent's HP, no check) | 28-32 | 29-34 | data: hp; split children already get parent HP in state.rs split() (matches game) | AcidSlime_M.<init>(FF) off 9 getstatic; 12 bipush 7; 14 if_icmplt 28 |
| AcidSlime_M | 2 | Corrosive Spit / Tackle damage | Spit 7, Tackle 10 | Spit 8, Tackle 12 | data: move Damage.amount | AcidSlime_M.<init>(FFII) off 21 getstatic; 24 iconst_2; 25 if_icmplt 67 (37 bipush 8, 55 bipush 12 vs 76 bipush 7, 94 bipush 10) |
| AcidSlime_M | 17 | getMove AI branch: roll thresholds and repeat limits | <30 Spit (lastTwoMoves Spit -> 50% Tackle/Lick); <70 Tackle (lastMove Tackle -> 40% Spit / 60% Lick); else Lick (lastTwoMoves Lick -> 40% Spit / 60% Tackle) | <40 Spit (lastTwoMoves -> 50% Tackle/Lick); <80 Tackle (lastTwoMoves Tackle -> 50% Spit/Lick); else Lick (lastMove Lick -> 40% Spit / 60% Tackle) | data: pattern rows (RollBelow/LastMove/LastTwo/Chance already exist) | AcidSlime_M.getMove off 0 getstatic; 3 bipush 17; 5 if_icmplt 276 (A17 at 9 bipush 40, 99 bipush 80, 192 lastMove(4); A0 at 277 bipush 30, 367 bipush 70, 374 lastMove(2) + 383 0.4f, 460 lastTwoMoves(4) + 469 0.4f) |
| AcidSlime_L | 7 | HP roll in 2-arg ctor only | 65-69 | 68-72 | data: hp | AcidSlime_L.<init>(FF) off 9 getstatic; 12 bipush 7; 14 if_icmplt 28 |
| AcidSlime_L | 2 | Corrosive Spit / Tackle damage | Spit 11, Tackle 16 | Spit 12, Tackle 18 | data: move Damage.amount | AcidSlime_L.<init>(FFII) off 36 getstatic; 39 iconst_2; 40 if_icmplt 82 (52 bipush 12, 70 bipush 18 vs 91 bipush 11, 109 bipush 16) |
| AcidSlime_L | 17 | getMove AI branch | <30 Spit (lastTwoMoves -> 50% Tackle/Lick); <70 Tackle (lastMove -> 40% Spit/60% Lick); else Lick (lastTwoMoves -> 40% Spit/60% Tackle) | <40 Spit (lastTwoMoves -> 60% Tackle/40% Lick); <70 Tackle (lastTwoMoves -> 60% Spit/40% Lick); else Lick (lastMove -> 40% Spit/60% Tackle) | data: pattern rows | AcidSlime_L.getMove off 0 getstatic; 3 bipush 17; 5 if_icmplt 278 (A17: 9 bipush 40, 25 0.6f, 101 bipush 70, 117 0.6f, 194 lastMove(4) 203 0.4f; A0: 279 bipush 30, 369 bipush 70, 376 lastMove(2) 385 0.4f, 462 lastTwoMoves(4) 471 0.4f) |
| SpikeSlime_S | 7 | HP roll | 10-14 | 11-15 | data: hp | SpikeSlime_S.<init>(FFI) off 21 getstatic; 24 bipush 7; 26 if_icmplt 40 |
| SpikeSlime_S | 2 | Tackle damage | 5 | 6 | data: move Damage.amount | SpikeSlime_S.<init>(FFI) off 48 getstatic; 51 iconst_2; 52 if_icmplt 76 (64 bipush 6 vs 85 iconst_5) |
| SpikeSlime_M | 7 | HP roll in 2-arg ctor only | 28-32 | 29-34 | data: hp | SpikeSlime_M.<init>(FF) off 9 getstatic; 12 bipush 7; 14 if_icmplt 28 |
| SpikeSlime_M | 2 | Flame Tackle damage | 8 | 10 | data: move Damage.amount | SpikeSlime_M.<init>(FFII) off 22 getstatic; 25 iconst_2; 26 if_icmplt 50 (38 bipush 10 vs 59 bipush 8) |
| SpikeSlime_M | 17 | getMove: Lick repeat limit (roll threshold 30 unchanged; Frail stays 1, no check in takeTurn) | Lick limited by lastTwoMoves(Lick) | Lick limited by lastMove(Lick) (never twice in a row) | data: pattern row LastTwo 1 -> LastMove 1 | SpikeSlime_M.getMove off 0 getstatic; 3 bipush 17; 5 if_icmplt 108 (A17 63 lastMove(4); A0 163 lastTwoMoves(4)) |
| SpikeSlime_L | 7 | HP roll in 2-arg ctor only | 64-70 | 67-73 | data: hp | SpikeSlime_L.<init>(FF) off 9 getstatic; 12 bipush 7; 14 if_icmplt 28 |
| SpikeSlime_L | 2 | Flame Tackle damage | 16 | 18 | data: move Damage.amount | SpikeSlime_L.<init>(FFII) off 37 getstatic; 40 iconst_2; 41 if_icmplt 65 (53 bipush 18 vs 74 bipush 16) |
| SpikeSlime_L | 17 | Lick Frail amount (takeTurn) | Frail 2 | Frail 3 | data: move Lick Apply Frail amount | SpikeSlime_L.takeTurn off 50 getstatic; 53 bipush 17; 55 if_icmplt 91 (76 iconst_3 vs 109 iconst_2) |
| SpikeSlime_L | 17 | getMove: Lick repeat limit | lastTwoMoves(Lick) | lastMove(Lick) | data: pattern row | SpikeSlime_L.getMove off 0 getstatic; 3 bipush 17; 5 if_icmplt 108 (63 lastMove(4) vs 163 lastTwoMoves(4)) |
| GremlinFat | 7 | HP roll | 13-17 | 14-18 | data: hp, content/packs/act1-monsters.json "Fat Gremlin" | GremlinFat.<init> off 30 getstatic; 33 bipush 7; 35 if_icmplt 49 |
| GremlinFat | 2 | Smash damage | 4 | 5 | data: move Damage.amount | GremlinFat.<init> off 57 getstatic; 60 iconst_2; 61 if_icmplt 84 (73 iconst_5 vs 93 iconst_4) |
| GremlinFat | 17 | Smash also applies Frail 1 (after Weak 1) | Weak 1 only | Weak 1 + Frail 1 | data: an extra effect on the move (whole-move override per level, not just a number) | GremlinFat.takeTurn off 106 getstatic; 109 bipush 17; 111 if_icmplt 144 |
| GremlinThief | 7 | HP roll | 10-14 | 11-15 | data: hp "Sneaky Gremlin" | GremlinThief.<init> off 30 getstatic; 33 bipush 7; 35 if_icmplt 49 |
| GremlinThief | 2 | thiefDamage (Puncture) | 9 | 10 | data: move Damage.amount | GremlinThief.<init> off 57 getstatic; 60 iconst_2; 61 if_icmplt 73 |
| GremlinTsundere | 17 | HP and blockAmt (Protect), checked first | HP 12-15, block 7 | HP 13-17, block 11 | data: hp + BlockAlly amount "Shield Gremlin" | GremlinTsundere.<init> off 30 getstatic; 33 bipush 17; 35 if_icmplt 55 |
| GremlinTsundere | 7 | HP and blockAmt (else-branch of the A17 check) | HP 12-15, block 7 | HP 13-17, block 8 | data: hp + BlockAlly amount | GremlinTsundere.<init> off 55 getstatic; 58 bipush 7; 60 if_icmplt 80 (A0 at 81-91) |
| GremlinTsundere | 2 | bashDmg (Shield Bash) | 6 | 8 | data: move Damage.amount | GremlinTsundere.<init> off 94 getstatic; 97 iconst_2; 98 if_icmplt 110 |
| GremlinWarrior | 7 | HP roll | 20-24 | 21-25 | data: hp "Mad Gremlin" | GremlinWarrior.<init> off 32 getstatic; 35 bipush 7; 37 if_icmplt 51 |
| GremlinWarrior | 2 | Scratch damage | 4 | 5 | data: move Damage.amount | GremlinWarrior.<init> off 59 getstatic; 62 iconst_2; 63 if_icmplt 86 |
| GremlinWarrior | 17 | Angry power at battle start (usePreBattleAction) | Angry 1 | Angry 2 | data: start_powers Angry amount | GremlinWarrior.usePreBattleAction off 0 getstatic; 3 bipush 17; 5 if_icmplt 35 (22 iconst_2 vs 49 iconst_1) |
| GremlinWizard | 7 | HP roll | 21-25 | 22-26 | data: hp "Gremlin Wizard" (engine has [23,25]: mismatch, see notes) | GremlinWizard.<init> off 49 getstatic; 52 bipush 7; 54 if_icmplt 68 (A0 69 bipush 21, 71 bipush 25) |
| GremlinWizard | 2 | Ultimate Blast damage | 25 | 30 | data: move Damage.amount | GremlinWizard.<init> off 76 getstatic; 79 iconst_2; 80 if_icmplt 104 (92 bipush 30 vs 113 bipush 25) |
| GremlinWizard | 17 | After Ultimate Blast (no escape): next move | Charging (UNKNOWN), charge reset, 3 charges before next blast | Ultimate Blast again every turn | data: pattern row LastMove 3 -> Move 3 (instead of Move 0) | GremlinWizard.takeTurn off 253 getstatic; 256 bipush 17; 258 if_icmplt 291 |

**Design (reader).** All 33 reads in these 11 classes are data, none needs AI code: HP ranges (A7), move numbers (A2: damage; A17: Frail amount, Tsundere block, Angry start power), one added effect (Fat Gremlin A17 Frail 1), and pattern-row changes (A17 slime thresholds/repeat limits/chances, Wizard re-blast). Every one maps to a field the monster JSON row already has (hp, moves[i].effects, start_powers, pattern); pattern_ai (engine/src/monsters.rs) and the existing PatCond set (RollBelow, LastMove, LastTwo, FirstTurn, Chance) express all the A17 AIs. Smallest general design: (1) one `ascension: u8` on the combat: Combat.new/versus/from_view in py/src/lib.rs take `ascension=0` (from_view reads it from the view dict), passed into CombatState::new_with_turn1 (engine/src/state.rs ~line 1728, the only place monster HP is rolled: `d.hp_min + rng.below(...)`), and stored on CombatState for later spawns. (2) Monster JSON rows get an optional `"ascension": [{"min": 2, ...}, {"min": 7, ...}, {"min": 17, ...}]` list; each entry replaces whole top-level fields (`hp`, `moves`, `start_powers`, `pattern`) for levels >= min, applied in ascending min order (later wins). Whole-field replace covers the Fat Gremlin extra effect and Tsundere's 2-step block with no new syntax. (3) At load (registry.rs parse_monster_as / the official loader at registry.rs ~2800), each row with tiers yields one variant MonsterDef per distinct threshold (a new MonsterKind each, max 4 per monster); a table kind x level -> variant kind is consulted when CombatState builds monsters and in split() (state.rs 4309: split_into resolves to the variant at the combat's level). This keeps Monster.def() static and the Ai signature unchanged, and the heuristic move caches (keyed on kind) split automatically; the alternative, a PatCond::AscAtLeast read from CombatState in pattern_ai, would need the cache key changed and still leaves numbers needing variants. Split children keep the parent's current HP (game's 4-arg ctors have no A7 check), which state.rs split() already does. MonsterKind is u8: Act 1 has ~20 kinds x <=4 tiers, fits.

**Notes.** Parameters merely named like ascension: none in these classes; the slime S ctors' third int and the M/L 4-arg ctors' ints are poisonAmount/newHealth, not ascension checks. A0 mismatches found (engine vs bytecode, independent of ascension): (a) Gremlin Wizard hp in content/packs/act1-monsters.json is [23,25]; GremlinWizard.<init> off 69-73 setHp(21,25) at A0. (b) Acid Slime (M) and (L) in content/monsters.json, Tackle row `{RollBelow 70, LastMove 1} -> Chance p 0.5 yes Spit no Lick` should be p 0.4 (AcidSlime_M.getMove off 383 / AcidSlime_L.getMove off 385 ldc 0.4f, true -> Spit). Other A0 rows checked match (Spit row 50/50, Lick row 0.4 Spit/Tackle, Spike M/L, Fat/Thief/Warrior/Tsundere numbers). A17 ordering detail: Tsundere checks A17 first then A7 (two disjoint tiers), so with min-ordered override entries the A17 entry must set both hp and block. AcidSlime_S A17 matters only for its first move (takeTurn sets later moves directly). Bytecode dumps kept at <scratchpad>/nb/*.txt (scratch; delete the nb folder when done). No repo files edited, no builds.

**Skeptic: confirmed.** I dumped all 11 classes again and checked each branch. All 32 branches in the research are right: the class, method, offsets, thresholds, and A0 and ascended values. One count in the design text is wrong. It says "All 33 reads", but these classes contain exactly 32 getstatic ascensionLevel reads: AcidSlime_S 3, AcidSlime_M 3, AcidSlime_L 3, SpikeSlime_S 2, SpikeSlime_M 3, SpikeSlime_L 4, GremlinFat 3, GremlinThief 2, GremlinTsundere 3, GremlinWarrior 3, GremlinWizard 3. The branch list itself also has 32 entries.

What I re-checked:
- AcidSlime_S getMove at A17 is lastTwoMoves(1) -> Tackle, else Lick.
- AcidSlime_M at A17: <40 lastTwo(Spit) 50/50 Tackle/Lick; <80 lastTwo(Tackle) 0.5 Spit/Lick; else lastMove(Lick) 0.4 Spit/Tackle.
- AcidSlime_L at A17: <40 with 0.6f at offset 25; <70 with 0.6f at offset 117; lastMove(4) with 0.4f at offset 203.
- SpikeSlime_M Frail stays 1 (takeTurn offset 69 iconst_1, no check). SpikeSlime_L Frail is 3 at offset 76 vs 2 at offset 109.
- GremlinFat A17: FrailPower(1) is added after Weak (offsets 117-138).
- Tsundere: the A17 branch sets 13-17 HP and block 11, the A7 branch sets 13-17 and block 8, A0 is 12-15 and block 7.
- Thief damage is 10 vs 9. Warrior Angry is 2 vs 1.
- Wizard A17 (offset 253) sets Ultimate Blast again, while A0 (offset 292) sets Charging (byte 2, UNKNOWN). The A0 cycle is charge 1-2-3, then blast.

Engine claims I checked:
- Gremlin Wizard hp in content/packs/act1-monsters.json is [23,25], but the bytecode is 21-25. The research's mismatch is real.
- The Acid Slime (M) and (L) rows `{RollBelow 70, LastMove 1} -> Chance p 0.5` should be 0.4 (ldc 0.4f at offsets 383 and 385). Also real.
- state.rs: new_with_turn1 is at line 1709, the HP roll at line 1751 (the research said ~1728), and split at line 4309.

Parameter named like ascension: none in these classes. The research is right on that.

Cleanup: I deleted my own scratch dumps (the scratchpad nbv folder). The research's nb folder is still there for its owner to delete.

**Missed (skeptic).** None. There is no ascensionLevel read in these 11 classes beyond the 32 the research lists.

## elites-bosses

| Class | Level | What | A0 | Ascended | Engine | Cite |
|---|---|---|---|---|---|---|
| GremlinNob | 8 | HP range (setHp) | 82-86 | 85-90 | data: content/monsters.json Gremlin Nob "hp" [82,86]; rolled in state.rs:1751 from d.hp_min/hp_max | GremlinNob.<init>(FFZ) @69 getstatic ascensionLevel; bipush 8; if_icmplt 88 |
| GremlinNob | 3 | bashDmg (Skull Bash) and rushDmg (Bull Rush) | Skull Bash 6, Bull Rush 14 | Skull Bash 8, Bull Rush 16 | data: monsters.json Gremlin Nob moves[2] Damage amount 6, moves[1] Damage amount 14 | GremlinNob.<init>(FFZ) @96 getstatic; iconst_3; if_icmplt 118 (putfield bashDmg/rushDmg) |
| GremlinNob | 18 | Bellow: AngerPower amount (engine power name Enrage) | Anger 2 | Anger 3 | data: monsters.json Gremlin Nob moves[0] Apply Enrage amount 2. AngerPower itself has no ascension read. | GremlinNob.takeTurn @58 getstatic; bipush 18; if_icmplt 94 (A18: AngerPower iconst_3 @80; else iconst_2 @108) |
| GremlinNob | 18 | AI branch in getMove (after Bellow): A18 skips the 33% roll. If neither last move nor the move before was Skull Bash -> Skull Bash; else if last two were Bull Rush -> Skull Bash; else Bull Rush. Since one of the last two being Skull Bash rules out lastTwo(Rush), it reduces to: Skull Bash every third turn (SB, Rush, Rush, SB...). A0 branch (@200): num<33 -> Skull Bash, else lastTwoMoves(Rush) -> Skull Bash, else Bull Rush. | rows: FirstTurn->Bellow; RollBelow 33->Skull Bash; LastTwo(Rush)->Skull Bash; else Bull Rush | rows: FirstTurn->Bellow; LastMove(SkullBash)->Bull Rush; Window(BullRush,SkullBash)->Bull Rush; else Skull Bash (expressible with existing PatCond, no new code) | data: monsters.json Gremlin Nob "pattern" (pattern_ai in engine/src/monsters.rs). Needs an alternative pattern keyed by min level 18. Note: the game always draws aiRng.random(99) in rollMove before getMove, while the engine's RollBelow rolls lazily, so A18 rows that read no roll make one fewer RNG draw than the game. That only matters for golden-game RNG parity. | GremlinNob.getMove(I) @21 getstatic; bipush 18; if_icmplt 200 (A18 body @29-197: lastMove(2)@31, lastMoveBefore(2)@39, lastTwoMoves(1)@107) |
| Lagavulin | 8 | HP range | 109-111 | 112-115 | data: monsters.json Lagavulin "hp" [109,111] | Lagavulin.<init>(Z) @59 getstatic; bipush 8; if_icmplt 78 |
| Lagavulin | 3 | attackDmg (Attack move) | 18 | 20 | data: monsters.json Lagavulin moves[3] Damage amount 18 | Lagavulin.<init>(Z) @86 getstatic; iconst_3; if_icmplt 102 |
| Lagavulin | 18 | debuff field: Siphon Soul's Strength and Dexterity loss | -1 Str, -1 Dex | -2 Str, -2 Dex | data: monsters.json Lagavulin moves[4] two Apply amounts -1. Metallicize 8 (usePreBattleAction bipush 8) and start block 8 do not depend on ascension. The sleep/stun logic is code (state.rs:4820, lagavulin::asleep) and does not depend on ascension either. | Lagavulin.<init>(Z) @108 getstatic; bipush 18; if_icmplt 125 (putfield debuff -2 / iconst_m1) |
| Sentry | 8 | HP range | 38-42 | 39-45 | data: monsters.json Sentry "hp" [38,42] | Sentry.<init>(FF) @33 getstatic; bipush 8; if_icmplt 52 |
| Sentry | 3 | beamDmg (Beam) | 9 | 10 | data: monsters.json Sentry moves[1] Damage amount 9 | Sentry.<init>(FF) @60 getstatic; iconst_3; if_icmplt 76 |
| Sentry | 18 | dazedAmt (Bolt adds Dazed to discard) | 2 Dazed | 3 Dazed | data: monsters.json Sentry moves[0] AddCard Dazed n 2. Artifact 1 (usePreBattleAction iconst_1) does not depend on ascension. | Sentry.<init>(FF) @82 getstatic; bipush 18; if_icmplt 98 |
| Hexaghost | 9 | HP (fixed) | 250 | 264 | data: monsters.json Hexaghost "hp" [250,250] | Hexaghost.<init>() @101 getstatic; bipush 9; if_icmplt 119 |
| Hexaghost | 19 | Top tier (checked before A4): strAmount, searBurnCount, fireTackleDmg, infernoDmg | Inflame Str 2; Sear adds 1 Burn; Tackle 5x2; Inferno 2x6 | Inflame Str 3; Sear adds 2 Burns; Tackle 6x2; Inferno 3x6 | data: monsters.json Hexaghost, duplicated across both cycles: Inflame moves 5 and 12 (Strength 2); Sear moves 2,4,7 (Burn n 1) and 9,11,14 (Burn+ n 1); Tackle moves 3,6,10,13 (5x2); Inferno moves 8,15 (2x6). Sear damage 6 (searDmg @209), Inferno's 3 Burn+, Inflame's 12 block and Divider (hexaghost::divider_damage) do not depend on ascension. The Burn upgrade is code (state.rs after_move) and does not depend on ascension. | Hexaghost.<init>() @126 getstatic; bipush 19; if_icmplt 158 (putfield strAmount 3, searBurnCount 2, fireTackleDmg 6, infernoDmg 3) |
| Hexaghost | 4 | Middle tier (A4-A18): fireTackleDmg, infernoDmg (strAmount and searBurnCount stay at A0 values) | Tackle 5x2; Inferno 2x6 | Tackle 6x2; Inferno 3x6 (Str 2, 1 Burn unchanged) | data: same move rows as the A19 entry. Three tiers (0/4/19) here: a min-level row table resolves them as long as rows apply in ascending order, later ones overriding earlier ones. | Hexaghost.<init>() @158 getstatic; iconst_4; if_icmplt 189 (A0 branch @189-206: strAmount 2, searBurnCount 1, fireTackleDmg 5, infernoDmg 2) |
| SlimeBoss | 9 | HP (fixed) | 140 | 150 | data: monsters.json Slime Boss "hp" [140,140] | SlimeBoss.<init>() @55 getstatic; bipush 9; if_icmplt 73 |
| SlimeBoss | 4 | slamDmg (Slam); also tackleDmg, which is dead: damage[0] is never read, takeTurn only reads damage.get(1) | Slam 35 (tackle 9 unused) | Slam 38 (tackle 10 unused) | data: monsters.json Slime Boss moves[2] Damage amount 35 | SlimeBoss.<init>() @80 getstatic; iconst_4; if_icmplt 102 (putfield tackleDmg/slamDmg); takeTurn reads only damage.get(1) @187/@297 |
| SlimeBoss | 19 | Goop Spray: Slimed count added to discard | 3 Slimed | 5 Slimed | data: monsters.json Slime Boss moves[0] AddCard Slimed n 3. SplitPower has no ascension read. The split itself is data ("split" + state.rs:4312 Monster::new_bound with the boss's current HP). The children's own constructor branches (Acid/Spike Slime L) belong to the normal-monster group. | SlimeBoss.takeTurn @65 getstatic; bipush 19; if_icmplt 97 (iconst_5 @87 vs iconst_3 @111) |
| TheGuardian | 19 | Top tier: HP and dmgThreshold (Mode Shift starting amount) | HP 240, Mode Shift 30 | HP 250, Mode Shift 40 | data AND code: hp in monsters.json The Guardian [240,240]; Mode Shift 30 appears twice: start_powers ModeShift 30 (JSON), and guardian::THRESHOLD = 30 in engine/src/monsters.rs, copied into rolled_damage by guardian::setup and re-added after Twin Slam (state.rs after_move). Both must come from one level-keyed value. THRESHOLD_STEP 10 (dmgThresholdIncrease @25) and DEFENSIVE_BLOCK 20 do not depend on ascension. | TheGuardian.<init>() @105 getstatic; bipush 19; if_icmplt 129 (setHp 250, dmgThreshold 40) |
| TheGuardian | 9 | Middle tier (A9-A18): HP and dmgThreshold | HP 240, Mode Shift 30 | HP 250, Mode Shift 35 | same as the A19 entry (JSON hp + start_powers ModeShift, code guardian::THRESHOLD) | TheGuardian.<init>() @129 getstatic; bipush 9; if_icmplt 153 (A0 branch @153: setHp 240, dmgThreshold 30) |
| TheGuardian | 4 | fierceBashDamage and rollDamage | Fierce Bash 32, Roll Attack 9 | Fierce Bash 36, Roll Attack 10 | data: monsters.json The Guardian moves[1] Damage 32, moves[5] Damage 9. Whirlwind 5x4, Twin Slam 8x2, Charging Up block 9 do not depend on ascension (constructor @31-55 constants). | TheGuardian.<init>() @166 getstatic; iconst_4; if_icmplt 188 |
| TheGuardian | 19 | Close Up: SharpHidePower amount = thornsDamage+1 | Sharp Hide 3 | Sharp Hide 4 | data: monsters.json The Guardian moves[4] Apply SharpHide amount 3. SharpHidePower and ModeShiftPower have no ascension read. | TheGuardian.useCloseUp @19 getstatic; bipush 19; if_icmplt 59 (thornsDamage iconst_3 set in <init> @59; +1 via iadd @46) |
| powers (AngerPower, AngryPower, MetallicizePower, ModeShiftPower, SplitPower, SharpHidePower, ArtifactPower, StrengthPower) | 0 | No ascension read in any of these power classes (searched the .class files for the ascensionLevel constant). Every ascended power number comes from the monster that applies it (entries above). | n/a | n/a | no change in powers.json for this group | grep -a ascensionLevel over jar/com/megacrit/cardcrawl/powers/*.class: no matches |

**Design (reader).** Engine today: only Ascension 0. The source says so outright (engine/src/monsters.rs:3 doc comment), and nothing in content/, engine/src or py/src/lib.rs reads an ascension level. Monster numbers live in content/monsters.json rows (hp, start_block, start_powers, moves[].effects, pattern, split), loaded by engine/src/registry.rs (around 1772-1829 into MonsterSpec, leaked into static MonsterDef at 1113). Monster::def() returns that static def by kind alone. CombatState::new_with (state.rs:1748-1754) rolls HP from def.hp_min/hp_max, then runs def.setup. Python's Combat.__new__ (lib.rs:307-328 -> new_bound_turn1), Combat.vs (341-368 -> new_with_turn1) and from_view (849) take no level.

Every branch in this group except the Nob AI change and the Guardian threshold is a plain number already present in JSON. The Nob A18 change can be written as a different pattern with today's PatCond set: LastMove(SkullBash)->Rush, Window(Rush,SkullBash)->Rush, else SkullBash. The Guardian's Mode Shift value is the one place a number is also hard-coded in Rust: guardian::THRESHOLD = 30, copied to rolled_damage in guardian::setup and reused in after_move. It must come from the def, either by reading start_powers ModeShift or through a new per-def field.

Smallest general design:
(1) One `ascension: u8` on the combat: a CombatState field, a parameter on new_with* and new_bound*, and a kwarg `ascension=0` on Combat(), Combat.vs() and from_view (a view key). Also add it to the state's hash/codec, or keep it outside the state and bake it into the def choice (see 3).
(2) Monster rows get an optional `"ascension": [{"min": N, ...partial row...}]` list. Each entry overrides top-level fields (hp, start_powers, pattern) or single move effects (e.g. {"moves": {"2": {"effects": [...]}}}, or a path→value patch). Entries apply in ascending min order, later ones winning. That covers the three-tier cases: Hexaghost 0/4/19 and Guardian 0/9/19.
(3) The registry resolves, at load, one MonsterDef per (kind, distinct breakpoint), e.g. a table DEFS[kind] = [(min, &MonsterDef)]. Monster::new_bound takes the level and stores a small tier index (u8) so Monster::def() picks the resolved def without the state. Caches keyed on Monster (Hash) then split by tier automatically. MonsterKind constants (TheGuardian, Lagavulin, Hexaghost) stay unchanged, so the code paths in state.rs keep working.
(4) Replace guardian::THRESHOLD with the def's ModeShift start amount (or a def field), so Mode Shift has a single source.

No per-monster Rust code is needed for this group.

**Notes.** Bytecode dumps are in <scratchpad>/eb/*.txt (scratch, delete when done).

Read counts: GremlinNob 4, Lagavulin 3, Sentry 3, Hexaghost 3, SlimeBoss 3, TheGuardian 4. All are listed above; none is a parameter merely named ascensionLevel. Thresholds use `if_icmplt`, i.e. ascensionLevel >= N takes the ascended branch.

Mismatches between engine and game:
- The engine calls Nob's Bellow power "Enrage"; the game class is AngerPower. Only the name differs.
- SlimeBoss tackleDmg (9/10) is dead code in the game; the engine rightly has no Tackle move.
- Nob A18 getMove reads no roll, but the game still consumes aiRng.random(99) in rollMove before getMove. The engine's RollBelow rolls lazily, so A18 Nob in the engine draws one RNG value fewer per turn than the game. This matters only for RNG parity against real-game traces.
- Nob's canVuln flag (constructor arg, set true for normal spawns) picks between ATTACK_DEBUFF and ATTACK intent; the engine always applies Vulnerable 2, which matches the normal case.

Powers checked for ascension reads: AngerPower, AngryPower, MetallicizePower, ModeShiftPower, SplitPower, SharpHidePower, ArtifactPower, StrengthPower. None reads it.

Values that do not depend on ascension: Lagavulin Metallicize 8 and start block 8, Sentry Artifact 1, Guardian threshold step +10 / defensive block 20 / Whirlwind 5x4 / Twin Slam 8x2 / Charging Up 9, Hexaghost Sear 6 / Inferno's 3 Burn+ / Inflame block 12 / Divider formula, Nob Vulnerable 2.

Nothing was built or edited.

**Skeptic: partly.** Game side: I found nothing wrong. I re-dumped all six classes into a fresh scratch folder (<scratchpad>/v2/), and the read counts match (Nob 4, Lagavulin 3, Sentry 3, Hexaghost 3, SlimeBoss 3, Guardian 4). Every threshold, bytecode offset, A0 value and ascended value checks out:
- Nob: HP 85-90 vs 82-86; bash/rush 8/16 vs 6/14; Anger 3 vs 2 in takeTurn @58.
- Lagavulin: HP 112-115 vs 109-111; attack 20 vs 18; debuff -2 vs -1.
- Sentry: HP 39-45 vs 38-42; beam 10 vs 9; Dazed 3 vs 2.
- Hexaghost: HP 264 at A9. At A19: Str 3, 2 Burns, Tackle 6, Inferno 3. At A4: Str 2, 1 Burn, Tackle 6, Inferno 3. A0 branch @189: 2/1/5/2.
- SlimeBoss: HP 150 vs 140; slam 38 vs 35; tackle 10 vs 9, which is never read; Slimed 5 vs 3 in takeTurn @65.
- Guardian: A19 HP 250 and threshold 40; A9 HP 250 and threshold 35; A0 HP 240 and threshold 30; Fierce Bash/Roll 36/10 vs 32/9; useCloseUp @19 thornsDamage+1.

The Nob A18 getMove reading is correct. The damage list holds rush at index 0 and bash at index 1; move bytes are 1 = Bull Rush and 2 = Skull Bash. In the engine, PatCond::Window(last, before) is an exact match on the last two moves, so the proposed rows (LastMove(2)->1, Window(1,2)->1, else 2) reproduce the game. The canVuln check inside the A18 branch only picks the intent icon.

Engine side: the JSON values the research quotes match content/monsters.json, and content/packs/act1-monsters.json holds none of these six monsters. One imprecise statement: the research says guardian::THRESHOLD is "re-added after Twin Slam". Actually after_move (state.rs:4848) re-adds m.rolled_damage. THRESHOLD seeds rolled_damage once in guardian::setup (monsters.rs:410), and lost_hp adds THRESHOLD_STEP to it (state.rs:4810). The conclusion still holds: the level-keyed value only needs to seed rolled_damage in setup and the ModeShift start power.

**Missed (skeptic).** Two misses in the research:

1. A second hard-coded copy of an ascension-dependent number in Rust. engine/src/threshold.rs:20-21 has `GUARDIAN_SHIFT = &[Effect::Block(guardian::DEFENSIVE_BLOCK), Effect::Apply { power: Power::SharpHide, amount: 3, target: Target::Me }]`. That is Close Up's Sharp Hide 3, which becomes 4 at A19 (TheGuardian.useCloseUp @19). This feature description is tested against the rules by engine/tests/threshold.rs, so at A19 it would disagree with the JSON move. It should read the resolved def's moves[CLOSE_UP].effects instead of a constant. So the research's claim that every number except the Mode Shift threshold lives only in JSON is wrong for the Guardian.

2. An unreported ascension read in a class these monsters inherit: AbstractMonster.onFinalBossVictoryLogic @0 (ascensionLevel >= 20 and bossList.size()==2). It handles run progress after the final boss and has no effect on combat, so the engine needs nothing.

Nothing else was missed. None of these classes has an ascension read: the powers (AngerPower, AngryPower, MetallicizePower, ModeShiftPower, SplitPower, SharpHidePower, ArtifactPower, StrengthPower), HexaghostOrb, HexaghostBody, the Burn/Slimed/Dazed status cards, or any action class the six monsters reference. AcidSlime_L and SpikeSlime_L, which SlimeBoss spawns, do have reads; they belong to the normal-monster group, as the research says.

## shared

| Class | Level | What | A0 | Ascended | Engine | Cite |
|---|---|---|---|---|---|---|
| characters.AbstractPlayer | 11 | Potion slots: constructor sets potionSlots=3 (offset 111-112), then if ascensionLevel>=11 decrements it by 1, before potions.clear() and refilling with PotionSlot objects | 3 potion slots | 2 potion slots | COMBAT-RELEVANT (cap on potions gained mid-fight, state.rs:2819). engine/src/potions.rs:320 BASE_POTION_SLOTS=3 const; state.rs:1929 CombatState::potion_slots() = 3 + relic slots. Plug: potion_slots() subtracts 1 when self.ascension>=11 (one general rule on the combat's level, not monster data). Python: Combat/versus/from_view must reject more than potion_slots() starting potions. | AbstractPlayer.<init>(String,PlayerClass) @382 getstatic ascensionLevel; bipush 11; if_icmplt 400; @392-397 potionSlots-=1 |
| dungeons.AbstractDungeon | 14 | Run start only (floorNum<=1 and dungeon is Exordium, branch @262-275): player.decreaseMaxHealth(player.getAscensionMaxHPLoss()); getAscensionMaxHPLoss is abstract per character (Ironclad 5, others 4 in their classes) | character's base max HP (Ironclad 80) | max HP minus character loss (Ironclad 75) | RUN-START. Fight from scratch: py/src/lib.rs hp_pair(c,hp,max_hp) default max_hp = c.max_hp() - c.ascension_max_hp_loss() when ascension>=14 (Character gets one number per class). Only the default changes; given hp/max_hp (from_view, later floors) are used as is. | AbstractDungeon.dungeonTransitionSetup() @278 getstatic; bipush 14; if_icmplt 298; @292 getAscensionMaxHPLoss, @295 decreaseMaxHealth |
| dungeons.AbstractDungeon | 6 | Run start only (same floor-1 Exordium block, after A14): player.currentHealth = round(maxHealth*0.9) (uses the already-reduced max HP) | current HP = max HP | current HP = round(0.9*max HP) (Ironclad A14+: round(67.5)=68 via MathUtils.round; A6-13: 72) | RUN-START. Fight from scratch at floor 1: hp_pair default hp = round(0.9*max_hp) when ascension>=6, applied after the A14 max-HP cut. Not a monster or CombatState rule; only the default of Combat(hp=None). | AbstractDungeon.dungeonTransitionSetup() @298 getstatic; bipush 6; if_icmplt 326; @316 ldc 0.9f, fmul, MathUtils.round, putfield currentHealth |
| dungeons.AbstractDungeon | 10 | Run start only (same floor-1 block): masterDeck.addToTop(new AscendersBane()) | starter deck only | starter deck + Ascender's Bane (unplayable, ethereal curse; soulbound) | RUN-START but it shapes every fight's deck. Fight from scratch: the caller's deck list should contain it (content/game_ids.json maps AscendersBane to gen:Ascender's Bane, a pack card); smallest rule: a run/deck builder appends it when ascension>=10, Combat itself does not add it (decks given to Combat/from_view are the real piles). | AbstractDungeon.dungeonTransitionSetup() @326 getstatic; bipush 10; if_icmplt 356; @340-347 new AscendersBane, CardGroup.addToTop |
| dungeons.AbstractDungeon | 5 | Act transition heal (start of each act, also run start where it is a no-op): heal round((max-current)*0.75) instead of heal(maxHealth) | full heal at the start of each act | heal 75% of missing HP | RUN-LAYER only (between acts). A scratch fight in Act 2/3 takes the hp the caller passes; nothing in CombatState. | AbstractDungeon.dungeonTransitionSetup() @198 getstatic; iconst_5; if_icmplt 236; @222 ldc 0.75f, @230 heal(I,Z); else @236-246 heal(maxHealth) |
| dungeons.AbstractDungeon | 1 | Map room-type generation: elite count = round(n*eliteRoomChance*1.6) on A1+ | round(n*eliteRoomChance) | round(n*eliteRoomChance*1.6) (more elites) | RUN-LAYER only (map). Nothing in combat. | AbstractDungeon.generateRoomTypes(ArrayList,int) @256 getstatic; iconst_1; if_icmplt 324; @269 ldc 1.6f fmul |
| dungeons.AbstractDungeon | 15 | isNoteForYourselfAvailable: three reads. >=15 returns false; ==0 returns true; else true only if ascensionLevel < highest unlocked (Prefs ASCENSION_LEVEL) | Note For Yourself event available | A1-14: available only below highest unlocked level; A15+: never | RUN-LAYER only (event pool). Nothing in combat. | AbstractDungeon.isNoteForYourselfAvailable() @19 (bipush 15, if_icmplt 40), @40 (ifne 59), @59 (if_icmpge vs Prefs ASCENSION_LEVEL @74) |
| dungeons.AbstractDungeon | 0 | Not a threshold: passes ascensionLevel to PublisherIntegration.setRichPresenceDisplayPlaying(floor, level, name) when isAscensionMode (@1050) | display call without level | display shows level | None (Steam/Discord presence display). | AbstractDungeon.nextRoomTransition(SaveFile) @1062 getstatic ascensionLevel -> invokeinterface setRichPresenceDisplayPlaying(IILString) |
| rooms.AbstractRoom | 13 | Boss room reward gold: base = 100 + miscRng.random(-5,5); on A13+ addGoldToRewards(round(base*0.75)) (daily runs give flat 100 before the check) | 95-105 gold | round(0.75*(95-105)) = 71-79 gold | RUN-LAYER (post-combat reward; inside update() after endBattle, MonsterRoomBoss only). Nothing in CombatState; note it consumes miscRng regardless of level. | AbstractRoom.update() @633 getstatic; bipush 13; if_icmplt 656; @644 ldc 0.75f, MathUtils.round, addGoldToRewards |
| monsters.AbstractMonster | 20 | Final boss victory: on A20 with bossList.size()==2 (second Act 3 boss pending) skip the victory/act-4 handling | one Act 3 boss, then victory / Act 4 key check | two Act 3 bosses (double boss) before victory | RUN-LAYER only (Act 3, out of the Act 1 scope). AbstractMonster has no other ascension read: all monster HP/damage/AI checks live in the monster subclasses, not this base class. | AbstractMonster.onFinalBossVictoryLogic() @0 getstatic; bipush 20; if_icmplt 21; @11 bossList.size, iconst_2, if_icmpne 21; goto 199 |
| shop.ShopScreen | 16 | Shop prices: applyDiscount(1.1f,false) on A16+ (before The Courier/Membership Card discounts) | base prices | all prices x1.1 | RUN-LAYER only (shop). | ShopScreen.init(ArrayList,ArrayList) @547 getstatic; bipush 16; if_icmplt 562; @556 ldc 1.1f, applyDiscount(FZ) |
| potions.AbstractPotion | 0 | Not a threshold: getPotency() calls the abstract getPotency(int) with ascensionLevel, then doubles for Sacred Bark. The int is a parameter named for ascension; the sampled overrides ignore it: BlockPotion returns 12, FairyPotion returns 30, EntropicBrew returns player.potionSlots (3 if no player) | potency per potion | same potency (no sampled potion reads the argument) | No ascension branch. engine/src/potions.rs potency field + state.rs:1884 potion_multiplier (Sacred Bark) already match. Indirect: EntropicBrew fills potionSlots, so at A11 it fills 2 slots; that follows from the A11 potion_slots() rule with no extra code. | AbstractPotion.getPotency() @1 getstatic ascensionLevel; @4 invokevirtual getPotency(I)I; BlockPotion.getPotency(int) @0 bipush 12; FairyPotion.getPotency(int) @0 bipush 30; EntropicBrew.getPotency(int) @0-14 potionSlots/iconst_3 |
| core.CardCrawlGame | 0 | Writes only (putstatic), no reads: sets ascensionLevel=0 for daily runs at run start, and from SaveFile.ascension_level on load | - | - | Where the level enters the game: the engine equivalent is one ascension argument at combat creation (Combat(..., ascension=0), from_view view key ascension). AbstractDungeon static {} @652 also just initialises it to 0. | CardCrawlGame.update() @422 putstatic (after Settings.isDailyRun @415); CardCrawlGame.loadPlayerSave(AbstractPlayer) @451 putstatic from SaveFile.ascension_level |

**Design (reader).** One ascension level on the combat, with monster numbers as data rows keyed by a minimum level.

1. CombatState gets `ascension: u8` (default 0). It is set once in CombatState::new_with_turn1, the function every new*/new_vs/new_with path ends in (engine/src/state.rs:1607-1720). The thin wrappers pass 0, or the level goes in through the existing relics/turn1 argument bundle. Python: Combat(..., ascension=0) and Combat.versus(..., ascension=0) at py/src/lib.rs:307/341, and a top-level view key "ascension" in from_view (lib.rs:850, which calls versus at about lib.rs:944). from_view needs it even though the view already holds monster hp/powers/intents, because later moves' damage and AI branches come from the defs.

2. Player rules that act inside a fight are general code on that field, not data. In this class group only A11 does this: potion_slots() (state.rs:1929) = BASE_POTION_SLOTS - (asc>=11) + relic slots. The run-start rules (A14 max HP minus the character's loss, then A6 current = round(0.9*max), A10 Ascender's Bane in the deck) belong to whatever builds a fresh floor-1 fight. Smallest version: hp_pair (lib.rs:126) takes the level and applies A14 then A6 to the defaults only, and a deck helper appends Ascender's Bane. CombatState never applies them, because a hp or deck the caller passes is already the real one.

3. Monsters: one general overlay list per monster row in content/monsters.json and content/packs/act1-monsters.json, e.g. "asc": [{"min": 2, "moves": {"Dark Strike": {"effects": [...]}}}, {"min": 7, "hp": [50, 56]}, {"min": 17, "start_powers": [...], "pattern": [...]}]. Each entry replaces whole fields (hp, start_block, start_powers, a move's effects, pattern rows) at level >= min. Entries apply in min order, and later ones win. The parser resolves them once at load into a few prebuilt MonsterDef variants per monster, one per distinct threshold. MonsterDef (monsters.rs:158) gains `by_asc: &'static [(u8, &'static MonsterDef)]`. Monster::def()/MonsterKind::def() then take the level (kind.def_at(asc)), so Monster stays Copy and hashing and afterstates don't change.

AI branches that are plain move choices (e.g. a different opening or forbidden repeats at A17) become replacement `pattern` rows. Only the code monsters (has_code: louse, lagavulin, hexaghost, guardian; monsters.rs:416-440) need the level passed into their setup and special cases. setup_for's fn(&mut Monster,&mut Rng) gains the level, and their ascended numbers still come from the overlay rows they read (e.g. louse Bite roll range, Curl Up, Guardian mode-shift threshold), not from per-monster `if asc` code.

content/encounters.json needs nothing: encounter lists don't change with ascension in Act 1. The A1 elite count is a map-generation rule.

**Notes.** Class group: 10 classes disassembled into <scratchpad>/asc/*.txt (scratch output; delete the folder when done). Exact read counts are shown in the branches.

- In-combat ascension checks in this group: only A11 potion slots. It is set in the AbstractPlayer constructor but acts in combat as the cap on potions obtained there, and through EntropicBrew's potency.
- No ascension check in these classes touches card draw, combat-end healing, or monster HP/damage.
  - Card draw is not here.
  - Combat-end healing is relic-driven (Burning Blood etc.).
  - Monster HP/damage/AI checks are in the individual monster subclasses, which were outside this group. AbstractMonster's only read is the A20 double boss.
- Potion potency: getPotency(int) receives ascensionLevel as a parameter, but none of the 3 sampled potions reads it. That is a named parameter, not a check. I did not check every other potion subclass for use of the argument.
- Run-start block in dungeonTransitionSetup:
  - Order: A5 heal (no-op at floor 1), then, only when floorNum<=1 and in Exordium: A14 max HP cut, A6 current HP = round(0.9 * the reduced max), A10 Ascender's Bane.
  - A fight from scratch at floor 1 should copy that order for its default hp/max_hp/deck. On later floors and in from_view, take the given values.
  - Run-layer only: A1 elites, A5 act heal, A13 boss gold, A15 Note For Yourself, A16 shop, A20 double boss. CardCrawlGame only writes the field (daily run = 0, save load).
- Current engine state:
  - engine/src/monsters.rs:3 says values are Ascension 0.
  - engine/src/potions.rs:318-320 hard-codes BASE_POTION_SLOTS=3 for Ascension 0.
  - There is no ascension field anywhere in engine/src, py/src or content/*.json.
  - from_view takes hp/max_hp/monster hp as given, so ascended HP from a real game already arrives in it. Ascended move numbers and AI rows would not, since they come from the defs.
- Gap: getAscensionMaxHPLoss values are per-character subclasses (Ironclad 5, others 4 from general knowledge) and were not disassembled here.

**Skeptic: confirmed.** I re-read the class-group disassemblies in <scratchpad>/asc/ and found no wrong values, thresholds or offsets.

AbstractDungeon has 11 lines that mention ascensionLevel. One is the field declaration, one is the static-initialiser putstatic at @652, and the other 9 are the reads the research lists:
- generateRoomTypes @256: A1.
- isNoteForYourselfAvailable @19/@40/@59: A15.
- nextRoomTransition @1062: rich presence.
- dungeonTransitionSetup @198/@278/@298/@326: A5, A14, A6, A10.

Small precision points (none changes the conclusions):
1. The A1 elite count uses java.lang.Math.round (@273). The HP and gold numbers use MathUtils.round. Both round half up for these positive values, so the results are the same.
2. The A5 act heal is heal(round((max-cur)*0.75), false) and runs before the floor-1 block. At A6 and above it is then overwritten at run start by currentHealth = round(0.9*max), so the A5 heal does nothing there. The research's order is right.
3. AbstractRoom.update boss gold happens only when the room is a MonsterRoomBoss, loading_post_combat is false and CardCrawlGame.loadingSave is false (@586-602). Daily runs get a flat 100. So "consumes miscRng regardless of level" is true only for non-daily, non-loaded boss rewards.
4. In the AbstractPlayer constructor, the A11 check (@382-397) runs after initializeStarterRelics and loadPrefs, and potionSlots=3 is set at @112. Relic slot bonuses (Potion Belt) are added later when the relic is picked up, so the engine's potion_slots() = 3 - (asc>=11) + relic slots is correct.
5. EntropicBrew.getPotency(int) returns player.potionSlots, or 3 when there is no player. It ignores the argument, as the research says.

The engine citations match: potions.rs:318-320 BASE_POTION_SLOTS=3 (comment says Ascension 0), state.rs:1929-1930 potion_slots(), lib.rs:126 hp_pair, monsters.rs:3 "Ascension 0". There is no ascension field anywhere in engine/src or content/*.json.

**Missed (skeptic).** None in these classes. Every getstatic or putstatic of ascensionLevel in the 10 disassembled files is accounted for:
- AbstractPlayer: 1 read.
- AbstractRoom: 1.
- ShopScreen: 1.
- AbstractMonster: 1.
- AbstractPotion: 1 (passed as an argument, not a threshold).
- CardCrawlGame: 2 writes.
- AbstractDungeon: 9 reads plus the field declaration and the static-init write.
- BlockPotion, FairyPotion, EntropicBrew: 0.

The caveats are the ones the research already states:
- The other potion subclasses' getPotency(int) were not checked to see whether any uses the argument.
- The per-character getAscensionMaxHPLoss values (Ironclad 5, others 4) were not disassembled.
