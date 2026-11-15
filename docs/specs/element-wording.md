# Wording for every content element

Status: closed (2026-11-08, built and in use; 4ed9b90; Amendment 1 c0b8fb4; deviation: decisions "Element wording").

## Outcome

Every element the content format can name (an effect such as `BlockAlly`,
a move-pick condition such as `Allies`, an encounter slot form such as
`draw`, a trigger, a target, ...) has a short game-worded description,
kept in one data file beside the content. Adding an element to the engine
without its wording fails `cargo test`, the check a lane already runs when
it changes the engine. The explorer builds every card, monster, move,
power and encounter text from these descriptions, so new content made from
existing elements needs no writing at all.

**Why.** On 2026-11-08 the act1-content lane added three elements
(`Allies`, the `draw` slot, `BlockAlly`). The explorer had no words for
them: the content view crashed for every user and Protect showed as
"BlockAlly: 7". Nothing failed in the lane, because the explorer's words
live in Python and only the 48-hour full test run would have noticed.

**How it moves the goals.** Goal 1 (custom content as data): a designer
reading a pack, or the owner reading the explorer, sees every rule in the
game's words, including rules added after the explorer was written. We'll
know by the checks: the wording test fails on an unworded element, every
description of every source matches a pin taken before the change, and no
description contains a raw engine name.

**Non-goals:**
- A description per card, monster or encounter (owner: per element, not
  per instance). Entries keep being worded from their elements.
- Changing any text the explorer shows today (the pin checks it), except
  AddCard's: "a copy of Shiv" becomes "1 Shiv", and a card adding itself
  says "this card". The pin is rewritten for exactly those lines, listed
  in the commit.
- The engine's own `render()` text, and the net's input names.
- Keyword hover (kept as an idea, Amendment 3).

## Behavior

### The wording file

`content/wording.json`: one object per element family, each mapping the
element's JSON name to its description, in the game's terse words (no
explanations in parentheses, keywords stay keywords; Amendment 3's rules).

```json
{"version": 1,
 "effect": {"Block": "gain {0} Block",
            "BlockAlly": "give {0} Block to a random other enemy", ...},
 "pattern_condition": {"FirstTurn": "on its first turn",
                       "Allies": "while another enemy is alive",
                       "LastMove": "after {0}", ...},
 "encounter_slot": {"draw": "{draw} drawn from {from}", ...},
 "target": {...}, "quantity": {...}, "pick": {...}, "pile": {...},
 "trigger": {...}, "condition": {...}, "modifies": {...},
 "static_condition": {...}, "pattern_pick": {...},
 "code_monster": {"lagavulin": "Asleep for 3 turns; ...", ...}}
```

- A description is a template: `{0}` is a tuple element's value, `{name}`
  a field's; a field that is itself an element (an amount, a monster) is
  filled with that element's own wording.
- **Who uses it.** An effect reads differently on a card, a monster and a
  power. The templates say how through slots the explorer fills for the
  user:

  | slot | card | monster | power |
  |---|---|---|---|
  | `{target}` | the target's wording for cards ("the enemy", "you") | for monsters ("you", "itself") | for powers ("its owner's opponent", "its owner") |
  | `{to}` | " to {target}", left out for Opponent | " to {target}", left out when it lands on you | " to {target}" |
  | `{subject}` / `{s}` | "" / "" | "" / "" | "its owner " / "s" |
  | `{per}` | "" | "" | " per stack" |

  The `target` family therefore holds one wording per user:
  `"Opponent": {"card": "the enemy", "monster": "you", "power": "its owner's opponent"}`.
  Examples: `"Block": "{subject}gain{s} {0} Block{per}"`,
  `"Damage": "deal {amount} damage{per}{to}{hits}"`.
- **How a field reads.** A few fields have one fixed rule, the same in
  every element that has them:
  - `{hits}`: " N times" when N is above 1, nothing at 1.
  - `{cards}`: a count and a card name, procedurally and without plurals
    (owner): "1 Shiv" for one, "N copies of Shiv" for more ("3 copies of
    Burn+"). A card that adds itself says "a copy of this card" (Anger,
    the game's words), "N copies of this card" for more.
    Example: `"AddCard": "add {cards} to your {pile}"`.
- **Values that change the words** stay in explorer code, each with a
  plain entry in the file (the form most uses take), so no element is
  worded in code only: a negative Apply ("lose 2 Strength"), an amount read
  from the game state ("equal to your Block"), Perfected Strike's "plus 2
  per card tagged Strike", ScaledBlock's "for each card in your hand", a
  card's PlainDamage to itself ("take 3 damage"), and Split's named halves.
  The build lists the final set in the decisions entry.
- `code_monster` holds the behaviour that lives in engine code
  (`CODE_MONSTERS` today: lice, Lagavulin, Hexaghost, the Guardian), and
  the hand-written power text (`CODE_POWERS`: Mode Shift, Split Hits)
  moves to a `code_power` family. `code_monster` is keyed by the monsters'
  `code` field; powers carry no such mark, so `code_power` holds today's
  two entries and isn't checked for completeness.
- The file is text, not rules: `rules_version()` and the golden games
  don't change, and a wording edit needs no rebuild of `sts` for the
  explorer (it reads the file directly).

### The engine's list of elements

- For each family, one function in `engine/src/registry.rs`, next to the
  JSON writer, returns an element's JSON name through a `match` with no
  wildcard arm. A new enum variant then doesn't compile until it is
  named, and naming it is the moment the lane meets the wording file.
- `registry::element_names()` lists every family's names; the binding
  exposes it as `sts.element_names()`.

### The checks

- **Rust, `engine/tests/wording.rs`:** `content/wording.json`
  (`include_str!`) has exactly the families and names of
  `element_names()`: a missing entry fails with "add wording for
  effect BlockAlly to content/wording.json", an entry with no element
  fails as stale. Every `code` value a monster in any content file uses
  has a `code_monster` entry.
- **Python, `test_explore_wording`:** every description of every content
  source (official, packs, mutated cards, generated enemies) equals the
  pin `scripts/tests/data/explore/wording_pin.json`, written from today's
  explorer before anything moves; and none contains an element's raw JSON
  name where words belong (the explorer's raw-name fallbacks record what
  they were given, and the test asserts the record is empty).
- AGENTS.md "Project gotchas" gains one line: a new content element needs
  its wording in `content/wording.json`; `cargo test` says which.

## Build steps

1. **Pin today's text.** Write `wording_pin.json` from today's
   `describe_index()` for every source, and `test_explore_wording`
   (passes today, apart from the fallback record, which step 3 adds).
2. **Element names in the engine.** The per-family exhaustive name
   functions and `element_names()`, `sts.element_names()`; Rust tests
   pass; golden games and `rules_version()` unchanged. Needs an `sts`
   rebuild and swap under the `main-merge` lock (AGENTS.md), with
   `jobs.py impact sts` recorded.
3. **The wording file.** Move the explorer's word tables and every
   effect, condition and slot case into `content/wording.json`, with the
   user slots; the explorer fills the slots and reads the file; only the
   value-dependent cases keep code, each with a plain entry.
   Check: the pin test passes byte for byte; the fallback record is empty.
4. **The Rust check** `engine/tests/wording.rs`. Check: it passes; with
   one entry deleted it fails naming that element.
5. **The AGENTS.md line**, and a decisions.md entry.

## Risks

- The act1-content lane is adding elements now. Step 2 lands on main
  quickly; the lane rebases and, from then on, its new elements need
  wording to pass `cargo test` (the point of this spec). Tell the lane
  through its next step note.
- Templates can't express every phrasing; those stay in code (with a plain
  entry), so the pin, not the template format, is what guarantees the
  text. A lane that changes such an element's fields must also check its
  code; the pin and the raw-name check catch a miss in the next explorer
  test run, not in `cargo test`.

## Amendment 1 (2026-11-08) · built c0b8fb4

The owner's correction: consistency over parity with the game. `{cards}`
always reads as copies: "1 copy of Shiv", "N copies of Shiv"; a card
adding itself "1 copy of this card", "N copies of this card". The pin
changes for the AddCard lines only. Check: `test_explore_wording`.
