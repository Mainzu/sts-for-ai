"""Novelty slices for held-out reads (big-picture review 2026-10-31,
direction 5a): which kind of held-out content a cell's deck holds.

check 6 (c6): unseen cards built from known primitives (selfplay.HELD_OUT).
check 9 (c9): cards that grant held-out powers or use an unseen condition
(the engine's `held_out` flag). Demon Form is split out: it carries most of
the c9 deficit (learned-play-results "Demon Form probe")."""
import numpy as np

C6 = {"Twin Strike", "Iron Wave", "Thunderclap", "Pommel Strike", "Uppercut"}
C9 = {"Go for the Eyes", "FTL", "Metallicize", "Demon Form", "Rage"}


def kinds(deck):
    names = {c.rstrip("+") for c in deck}
    return names & C6, names & C9


def novelty_slices(specs):
    """Boolean masks over `specs`: only-c6, only-c9, c6+c9, demon_form,
    c9-no-DF (c9 cards present, Demon Form absent)."""
    rows = [kinds(s["deck"]) for s in specs]
    return {
        "only-c6": np.array([bool(a) and not b for a, b in rows]),
        "only-c9": np.array([bool(b) and not a for a, b in rows]),
        "c6+c9": np.array([bool(a) and bool(b) for a, b in rows]),
        "demon_form": np.array(["Demon Form" in b for _, b in rows]),
        "c9-no-DF": np.array([bool(b) and "Demon Form" not in b for _, b in rows]),
    }
