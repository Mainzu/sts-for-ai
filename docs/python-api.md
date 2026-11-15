# Python API

The engine is a Python module, `sts`, built from the Rust code (see Build
in the README). This page lists its main calls in one block.

## Python API (short)

```python
import sts
c = sts.Combat(["Strike"] * 5 + ["Defend"] * 4 + ["Bash"], "jaw_worm", seed=1)
c.legal_actions(); c.options(16); c.step(a); c.render()
f = sts.Features("effects")            # or "ids"; known_cards=, known_powers=, known_triggers=,
                                       # known_conditions=, known_effects= (f.vocab: the lists in use)
batch = f.encode([c])                  # player, monsters, cards, card_count, card_pile, card_state
                                       # + rows, row_card, row_entity, row_state (hook rows)
sts.search_action(c, "heuristic")      # or a callable: batch dict -> scores, or an sts.NetEvaluator
sts.search(c, "heuristic", turns=2, sample_k=4, max_nodes=50_000)  # {action, options, nodes, leaves, cuts}
                                       # cuts: states left unexpanded at max_nodes; sibling options
                                       # share sampled outcomes (common random numbers)
sts.run("search", sts.make_specs("boss", 100), threads=16)
sts.run("search", specs, record=True, values=True)  # + "values": per decision [(actions, value)]
sts.run("search", specs, forced=[[a1, a2], ...])     # each game plays its forced actions first
s = sts.Combat(sts.starter_deck("silent"), "cultist", character="silent")
sts.run("search", sts.make_specs("boss", 100, character="silent"), character="silent")
sts.solve(c, max_nodes=1_000_000, distribution=False, store=None)  # exact option values, or None
db = sts.SolvedDb("db/solved.sqlite"); store = sts.SolveStore(min_nodes=1000, db=db)
sts.Combat.decode(c.encode())          # the state as bytes and back
h = sts.load_content("pack.json")      # generated powers/cards (docs/specs/registry-lite.md); content hash
m = sts.Combat.versus(deck, ["gen:brute", "Cultist"], seed=1)  # monsters by name (official or a pack's)
g = sts.Combat(deck + ["gen:gc017"], "cultist")  # decks and run specs name them gen:<id>; at most
                                       # registry::MAX_CARD_SLOTS generated cards and
                                       # 24 (POWER_SLOTS) generated powers per combat; no encode(); ids-mode
                                       # features see them as unknown. sts.loaded_content(): hashes loaded
```
