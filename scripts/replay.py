"""Turn-by-turn log of one combat: the board at each decision, and for the
search agent every option it considered with its score.

    python scripts/replay.py --encounter slime_boss --agent search --seed 3
    python scripts/replay.py --encounter gremlin_nob --deck Strike*5 Defend*4 Bash Inflame Carnage
"""

import argparse

import sts

STARTER = ["Strike*5", "Defend*4", "Bash"]


def expand(deck):
    """"Strike*5" -> five Strikes."""
    out = []
    for item in deck:
        name, _, n = item.partition("*")
        out += [name] * int(n or 1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--encounter", default="slime_boss", choices=sts.encounter_names())
    ap.add_argument("--agent", default="search", choices=["search", "greedy", "random"])
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--deck", nargs="+", default=STARTER, help='card names, "Name*N" for N copies')
    ap.add_argument("--sample-k", type=int, default=0)
    ap.add_argument("--turns", type=int, default=1)
    args = ap.parse_args()

    c = sts.Combat(expand(args.deck), args.encounter, seed=args.seed)
    turn = None
    step = 0
    while not c.is_over():
        if c.turn() != turn:
            turn = c.turn()
            print(f"\n=== Turn {turn} ===")
        print(c.render())
        if args.agent == "search":
            r = sts.search(c, "heuristic", sample_k=args.sample_k, turns=args.turns, seed=step)
            ranked = sorted(r["options"], key=lambda o: -o[1])
            print(f"  options ({r['leaves']} leaves, {r['nodes']} nodes):")
            for actions, value in ranked:
                mark = "->" if r["action"] in actions else "  "
                names = " = ".join(sts.action_name(a) for a in actions)
                print(f"   {mark} {value:7.4f}  {names}")
            a = r["action"]
        elif args.agent == "greedy":
            a = sts.greedy_action(c)
        else:
            a = sts.random_action(c, seed=step)
        print(f"  play: {sts.action_name(a)}")
        c.step(a)
        step += 1
    print("\n=== End ===")
    print(c.render())
    print(f"{'won' if c.won() else 'lost'} with {c.player_hp()} HP, score {c.score():.3f}")


if __name__ == "__main__":
    main()
