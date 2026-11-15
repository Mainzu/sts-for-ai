# Cards: afterstate value functions and backgammon engines

Angle: afterstate value functions, TD-Gammon and successors, expectimax or search with learned evaluators, rollouts, search depth.
Papers opened: 11 (3 full text, 8 abstract only). Abstract-only cards say so on the Read line.

---

### Temporal Difference Learning and TD-Gammon (1995)
- **Link:** https://bkgm.com/articles/tesauro/tdl.html (reproduction of the CACM article; DOI https://doi.org/10.1145/203330.203343 not opened; the ece.uvic.ca PDF returned 404) · **Venue:** Communications of the ACM · **Cited by:** 1602 (OpenAlex W2131600418) · **Read:** full text (bkgm.com copy)
- **Problem:** Learn a backgammon evaluator by self-play, with no expert data, and play by evaluating candidate moves with it.
- **Method:** Net outputs win/gammon estimates for each side; weights updated by TD(lambda) at each time step, with the final outcome replacing the next prediction at game end. Move choice: score every legal move with the net and take the maximum. Version 2.0 added "a heuristic 2-ply search in real time." The article does not discuss afterstate vs state values (per the fetched text).
- **Assumes:** Discrete turns; dice are chance that appears only implicitly (variety in self-play, no explicit expectation step in training); raw board encoding first, then Neurogammon-style hand features added; the best raw-encoding net had 40 hidden units and trained for 200,000 games.
- **Claims:** Raw-encoding net (40 hidden units, 200,000 games) "approximately equal to Neurogammon." v1.0 lost 13 points in 51 games against Robertie, Magriel and Davis ("a very respectable net loss of 13 points"). v2.0 lost 7 points in 38 exhibition games. v2.1 trailed a 40-game session with Robertie and lost the last game by 1 point. Robertie estimated v1.0 loses 0.2 to 0.25 points per game against world-class humans. Explanation given: absolute errors are often a tenth of a point or more, but errors among similar candidate moves are correlated through the net's generalisation, so they "largely cancel in comparisons"; dice broaden self-play states; the outcome function is smoother than in deterministic games.
- **Evaluation:** Exhibition and test matches against human experts; no reproducible benchmark in the article.
- **Code:** none checked.
- **Fit:** partial. The relative-ranking argument (errors cancel between similar candidates) bears directly on a net used only to compare candidate plays. It breaks the setup: TD bootstrapping from self-play, not regression on outcomes of a heuristic's games, and no hidden information.

---

### On-line Policy Improvement using Monte-Carlo Search (1996; arXiv 2501.05407)
- **Link:** https://arxiv.org/abs/2501.05407 · full text https://arxiv.org/html/2501.05407v1 · **Venue:** NeurIPS 1996 (NIPS 9), posted to arXiv 2025 · **Cited by:** not checked · **Read:** full text (arXiv HTML)
- **Problem:** Improve any simulable base policy at decision time by estimating each candidate move's long-run value under that policy.
- **Method:** For each candidate a in state x, run many trials that play a and then follow the base policy P, average the outcomes, and pick the best estimate. Statistical pruning drops candidates outside a confidence bound or equivalent to the current best. Truncated variant: stop after a few steps and score the cut position with the net. Dice are sampled at random; the paper gives no more detail.
- **Assumes:** Stochastic, simulable environment; parallel compute (32 SP1 nodes for the CPU times in the tables, parallel efficiency "on the order of 90%"); base policies were random, linear nets (Lin-1/2/3), and TD nets with 10 and 80 hidden units.
- **Claims:** Table 2 (average equity loss per move, 800 positions, full rollouts): Random 0.330 base to 0.131 MC (ratio 2.5); Lin-1 0.040 to 0.0124 (3.2); Lin-2 0.0665 to 0.0175 (3.8); Lin-3 0.0291 to 0.00749 (3.9). TD-Gammon 2.1 1-ply scores 0.0120 and 2-ply 0.00843 on the same set. Table 3 (truncated rollouts): 10-hidden base 0.0152 to 0.00318 with 11-step thorough rollouts (ratio 4.8, 25 sec/move); 80-hidden base 0.0120 to 0.00181 with 7-step thorough rollouts (ratio 6.6, 65 sec/move). Table 1: Lin-3 base -0.32 ppg vs TD-Gammon 2.1 1-ply, MC +0.04 at 10 sec/move. The abstract says "by as much as a factor of 5 or more"; the text says "a factor of 4 or more."
- **Evaluation:** About 800 positions, each rolled out extensively by TD-Gammon 2.1 1-ply (Tables 2-3); several thousand games against TD-Gammon 2.1 1-ply (Table 1; 30K trials for base players, 5K for MC players).
- **Code:** none checked.
- **Fit:** partial. Chance is handled by sampling dice in the rollouts, and truncated rollouts with a learned evaluator at the cut show large error reductions. Breaks the budget: 25 to 65 sec per move on 32 SP nodes, and it relies on a simulator of the full game.

---

### PureTD: Reinforcement Learning for Backgammon Money Games with No Evaluation-time Search (2026; arXiv 2608.15146)
- **Link:** https://arxiv.org/abs/2608.15146 · full text https://arxiv.org/html/2608.15146 · **Venue:** arXiv cs.LG (v1 15 Aug 2026, v2 15 Oct 2026) · **Cited by:** 0 (OpenAlex W7203702150) · **Read:** full text (HTML, read in two chunks covering the 153,898-character page; the Sec. 3.2 pseudo-state definition was not in the text returned)
- **Problem:** Learn backgammon money play from scratch by self-play TD, with no search at evaluation time.
- **Method:** ReLU MLP on 196 base inputs (Tesauro-style per-point thermometer, perspective-encoded) plus 4 cube inputs; hidden [512, 512, 256, 256]. Learns values of pre-roll "pseudo-states," described as "closely related to afterstates, not afterstates themselves." Targets: sampled-Bellman (one dice roll, greedy continuation) and exact-Bellman (expectation over all 21 rolls). Batch rounds of 1,000 self-play games, then one epoch of Adam minibatch SGD. Move choice is "0-ply": score each legal successor in one batched net call and take the best.
- **Assumes:** Discrete turns; dice are explicit chance; money games only (match play listed as future work); cubeful model 563k parameters; CPU throughput measured on a Ryzen 7 9700X and 5950X, but training ran on "a Zen 5 workstation with a consumer GPU"; the cubeful fork used about 198M self-play episodes (27M sampled-Bellman, 171M exact-Bellman); base about 49M.
- **Claims:** Cubeless money, head-to-head mEq/game vs PureTD 0-ply over 10^7 games, 95% percentile bootstrap CI: gnubg 0-ply -45.8 [-46.7, -45.0]; gnubg 1-ply -12.1 [-12.9, -11.2]; Open Sage 0-ply -36.8 [-37.7, -35.9]; Open Sage 1-ply -5.9 [-6.8, -5.1]. Sign convention is my reading: negative values favour PureTD. Cubeful, XG++ Performance Rating (lower is better): PureTD 0-ply 0.80 [0.76, 0.84]; gnubg 1-ply 1.25 [1.20, 1.32]; Open Sage 1-ply 1.24 [1.18, 1.29]. Cubeful head-to-head vs gnubg 1-ply: -27.2 [-29.0, -25.3]. Throughput (Zen 5, checker decisions/s): PureTD 0-ply 5,600 (cubeful) vs gnubg 1-ply 1,480.
- **Evaluation:** Head-to-head backgammon matches (10^7 games per matchup in most tables; 2x10^6 for Open Sage cubeful); offline PR from 1,000 self-play games per row; opponents gnubg at 0/1/2-ply and Open Sage at 0/1-ply.
- **Code:** none checked.
- **Fit:** good for the core question (a value net with no search vs a search-based engine as the baseline). The net scores successor positions in one batched call with no search. Breaks two constraints: training used a GPU and 49M to 198M self-play episodes, far beyond hours of CPU training.

---

### Bootstrapping from Game Tree Search (2009)
- **Link:** https://proceedings.nips.cc/paper_files/paper/2009/file/389bc7bb1e1c2a5e7e147703232a88f6-Paper.pdf (PDF bytes not decodable; abstract from the PDF metadata and https://mlanthology.org/neurips/2009/veness2009neurips-bootstrapping) · **Venue:** NIPS 2009 (NeurIPS 22), pp. 1937-1945 · **Cited by:** not checked · **Read:** abstract
- **Problem:** Learn a heuristic evaluator from search results rather than from game outcomes.
- **Method:** Update heuristic parameters towards values computed by alpha-beta search. Differs from TD-Leaf by updating all nodes of the search tree, and by using the outcome of a deep search rather than a subsequent search as the training signal. Linear heuristic, small random initial weights, self-play only.
- **Assumes:** Deterministic two-player perfect-information game (chess, program Meep); alpha-beta search; linear evaluator.
- **Claims:** Abstract: "When tested online against human opponents, Meep played at a master level, the best performance of any chess program with a heuristic learned entirely from self-play." No numbers on the abstract.
- **Evaluation:** Chess self-play and online human play. Not extractable from the abstract.
- **Code:** none checked.
- **Fit:** partial. Training every node of a search tree toward search values is a direct analogue for a net that scores afterstates, but chess has no chance nodes and the full text was not readable.

---

### TDLeaf(lambda): Combining Temporal Difference Learning with Game-Tree Search (1998; arXiv cs/9901001)
- **Link:** https://arxiv.org/abs/cs/9901001 (PDF bytes not decodable) · **Venue:** Australian Journal of Intelligent Information Processing Systems 5(1), 1998, pp. 39-43; ACNN'98 pp. 168-172 (per arXiv page) · **Cited by:** not checked · **Read:** abstract
- **Problem:** Use TD(lambda) when the evaluator is applied only after a minimax search.
- **Method:** Described on the abstract page only as "a variation on the TD(lambda) algorithm that enables it to be used in conjunction with minimax search." Leaf selection, TD error and lambda were not extracted.
- **Assumes:** Chess and backgammon; minimax search.
- **Claims:** KnightCap "improved from a 1650 rating to a 2100 rating in just 308 games" on the Free Internet Chess Server. The page gives no backgammon results.
- **Evaluation:** Online chess on FICS; backgammon experiments (not extracted).
- **Code:** none checked.
- **Fit:** partial. Establishes the classic route from search to evaluator update. The exact update rule is unverified here.

---

### Why did TD-Gammon Work? (1996)
- **Link:** https://papers.neurips.cc/paper_files/paper/1996/hash/459a4ddcb586f24efd9395aa7662bc7c-Abstract.html (PDF at https://papers.nips.cc/paper_files/paper/1996/file/459a4ddcb586f24efd9395aa7662bc7c-Paper.pdf, bytes not decodable) · **Venue:** NIPS 9 (1996), pp. 10-16 · **Cited by:** 26 (OpenAlex W2112836703) · **Read:** abstract
- **Problem:** Explain why TD-Gammon worked when TD learning did not transfer to other games.
- **Method:** A 4,000-parameter feed-forward net trained by simple hill-climbing in a relative fitness setting, without backpropagation, RL or TD.
- **Assumes:** Backgammon; co-evolutionary self-play.
- **Claims:** Abstract quotes: "Although TD-Gammon is one of the major successes in machine learning, it has not led to similar impressive breakthroughs" and "the surprising success of Tesauro's program had more to do with the co-evolutionary structure of the learning task." No numbers on the abstract.
- **Evaluation:** Not extracted.
- **Code:** none checked.
- **Fit:** partial. Argues the result depends on the task's dynamics, which is a caution about attributing generalisation to the learner. It does not address supervised regression.

---

### Monte-Carlo Tree Search in Backgammon (2007)
- **Link:** https://orbi.uliege.be/handle/2268/28469 (PDF https://orbi.uliege.be/bitstream/2268/28469/1/vanlishout_backgammon.pdf returned binary, not decoded) · **Venue:** Computer Games Workshop, Amsterdam, 2007, pp. 175-184 · **Cited by:** 25 (OpenAlex W2293209287) · **Read:** abstract
- **Problem:** Apply MCTS to backgammon, a two-player game with chance, which the abstract says had not been tested before.
- **Method:** Per the abstract, "playing online simulated games to learn how to play correctly in the current position." Tree and chance-node handling not extracted.
- **Assumes:** Two-player game with dice; online simulation from the current position.
- **Claims:** None extracted; the abstract says the strongest backgammon programs use RL "with millions of offline games."
- **Evaluation:** Not extracted.
- **Code:** none checked.
- **Fit:** partial. The chance-node tree question is the relevant part; no numbers available.

---

### Learning and Improving Backgammon Strategy (1994 Learning Day; arXiv 2504.02221, posted 2025)
- **Link:** https://arxiv.org/abs/2504.02221 · **Venue:** Proceedings of the CBCL Learning Day (1994); arXiv 3 Apr 2025 · **Cited by:** not checked · **Read:** abstract
- **Problem:** Learn a backgammon value function by combining off-line and on-line methods.
- **Method:** Off-line parallel NN training with TD(lambda), plus Monte-Carlo "Rollouts" as a "massively parallel on-line policy improvement technique" at decision points of a game-tree search.
- **Assumes:** Parallel supercomputer (per the 1994 setting).
- **Claims:** Qualitative only: "roughly as good as, or possibly better than, the current champion human and computer backgammon players" after "a short period of learning." No numbers on the abstract page.
- **Evaluation:** Not on the abstract page.
- **Code:** none checked.
- **Fit:** partial. Same family as the Tesauro-Galperin card; the abstract adds no numbers.

---

### Multi-Stage Temporal Difference Learning for 2048-like Games (2016; arXiv 1606.07374)
- **Link:** https://arxiv.org/abs/1606.07374 (PDF returned binary; HTML 404) · **Venue:** arXiv 1606.07374 (comments: accepted by TCIAIG) · **Cited by:** 30 (OpenAlex W2964169838, the 2016 record; DOI 10.1109/tciaig.2016.2593710) · **Read:** abstract
- **Problem:** TD-trained n-tuple programs for 2048 rarely reach large tiles.
- **Method:** Multi-stage TD (MS-TD), a hierarchical RL method, building on Szubert and Jaskowski's n-tuple TD work; the abstract reports expectimax search over the learned values.
- **Assumes:** 2048 (single-player, random tile spawns after each move, so the afterstate split is natural); discrete turns; n-tuple value tables.
- **Claims:** Abstract quotes: "the program with MS-TD learning reached 32768-tiles with a rate of 18.31%" under "2048, 3-ply expectimax search", where the TD-only program reached no 32768-tiles. "After further tuning, our 2048 program reached 32768-tiles with a rate of 31.75% in 10,000 games." Threes: MS-TD reached 6144-tiles at 7.83% vs 0.45% for TD-only.
- **Evaluation:** 2048 and Threes, with the number of games as given in the abstract (10,000 for the tuned result).
- **Code:** none checked.
- **Fit:** good for the afterstate-plus-chance question: a learned afterstate evaluator used at the leaves of a depth-3 expectimax, with a reported effect of depth. Breaks: 2048 is a single-player game with no hidden information, and its table-based n-tuple net does not generalise across states the way a Deep Sets net does.

---

### On Reinforcement Learning for the Game of 2048 (2022; arXiv 2212.11087, PhD dissertation)
- **Link:** https://arxiv.org/abs/2212.11087 · **Venue:** PhD dissertation, National Yang Ming Chiao Tung University; arXiv Dec 2022 (v2 Jan 2023), CC BY 4.0 · **Cited by:** not checked · **Read:** abstract
- **Problem:** Learn 2048 play by TD with better exploration.
- **Method:** "Optimistic temporal difference learning" (optimistic initialization to encourage exploration); the abstract also names n-tuple ensembles, MCTS and deep RL as investigated.
- **Assumes:** 2048, single-player stochastic puzzle.
- **Claims:** "an average score of 625377 points and a rate of 72% for reaching 32768-tiles." Conditions (games, protocol) not on the abstract page.
- **Evaluation:** Not on the abstract page.
- **Code:** none checked.
- **Fit:** partial. A TD exploration result for afterstate learning; no search or generalisation claims could be checked.

---

### Scalable decision-making for games of imperfect information (Nature, 2026)
- **Link:** https://doi.org/10.1038/s41586-026-11036-y (resolves to nature.com, which redirects to a login page; not followed) · metadata and abstract via https://api.openalex.org/works/W7214912595 (abstract rebuilt by the fetch tool, which gave a summary, not verbatim) · **Venue:** Nature, 2026 · **Cited by:** 0 · **Read:** abstract (OpenAlex record only)
- **Problem:** Decision-making when part of the state is hidden, where standard RL and search break down.
- **Method:** Per the abstract summary: a policy-value network trained by self-play, a belief network that infers hidden information, and test-time search that samples possible hidden states and runs depth-limited rollouts. Named system: Ataraxos (Stratego).
- **Assumes:** Hidden information; games Stratego, Barrage, Hanabi, dou dizhu.
- **Claims:** Beat a four-time Stratego champion, per secondary press coverage (not opened): 15 wins, 1 loss, 4 draws in 20 games. The OpenAlex-derived abstract did not give numbers.
- **Evaluation:** Stratego and other games; the exact benchmark not extracted.
- **Code:** none checked.
- **Fit:** partial. Relevant to "learned value plus search under hidden information," which is the StS setting. Only the abstract summary was read; the paper itself was not reachable.
