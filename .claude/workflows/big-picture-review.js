export const meta = {
  name: 'big-picture-review',
  description: 'Big-picture review of sts-for-ai: six analysts with different lenses, a synthesis, then skeptics on the key claims',
  phases: [
    { title: 'Analyse', detail: 'six independent lenses over data, docs and prior art' },
    { title: 'Synthesise', detail: 'one strategic review ranking directions by value per CPU-hour' },
    { title: 'Verify', detail: 'skeptics try to refute the review\'s load-bearing claims' },
  ],
}

const REPO = 'the current working directory'
const COMMON = `
You are part of a big-picture review of the sts-for-ai project at ${REPO}. The review is for data analysis, big-picture thinking and abstraction, not for building the next item in the queue.

Project goals (owner): (1) an AI that plays well on randomly generated content (cards, powers, enemies), with first-class support for custom content (new character, mechanic, entity); (2) on that system, a Slay the Spire AI as dominant in its field as Stockfish is in chess. Subgoals: relics; scope beyond combat toward the full game (as a headless simulator).

Where to read: README.md, SPEC.md, docs/concept.md, docs/extending.md, docs/decisions.md (design log, newest last), docs/operating.md (the rules, if present), docs/direction.md (the owner's weights), docs/backlog.md and the lane facts ('python -I ~/.claude/skills/kb/kb.py render', 'kb get lane/<name>'), docs/digest/ (daily digests, if present), docs/research/*.md (results: bench-baseline, exact-puzzles, learned-play-and-generalisation, learned-play-results), results/ and runs/ (raw outputs: JSON, logs), scripts/ (Python: learn.py, curve.py, sweep.py, eval and bench scripts), engine/src (Rust engine), py/ (binding), git log.

Hard rules:
- READ-ONLY. Do not edit, create, commit or delete any file in the repo. Do not touch jobs/locks/.
- The CPU is usually busy with a long training run (see '.venv/Scripts/python scripts/jobs.py status'). You may run small Python or shell analyses (single thread, under ~1 minute each, e.g. parsing JSON results with .venv/Scripts/python -I or python). Do NOT run training, sweeps, benches, cargo build/test, maturin, or anything heavy.
- Use numbers from the files, with the path they came from. If you compute something, say how. Separate what the data shows from your interpretation.
- Think abstractly: name the underlying pattern, not just the symptoms. Be willing to say a whole direction is wrong.
`

const FINDINGS = {
  type: 'object',
  properties: {
    lens: { type: 'string' },
    summary: { type: 'string', description: '5-10 plain sentences: the big picture through this lens' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          evidence: { type: 'string', description: 'numbers with file paths, or how computed' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
          implication: { type: 'string' },
        },
        required: ['claim', 'evidence', 'confidence', 'implication'],
      },
    },
    directions: {
      type: 'array',
      description: 'concrete directions to try, stop, or change',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          what: { type: 'string' },
          why: { type: 'string' },
          expected_gain: { type: 'string' },
          cpu_cost: { type: 'string', description: 'rough CPU-hours on the dev machine (CPU only, no GPU)' },
          first_check: { type: 'string', description: 'the cheapest experiment or analysis that would tell us if it is worth it' },
        },
        required: ['name', 'what', 'why', 'expected_gain', 'cpu_cost', 'first_check'],
      },
    },
    open_questions: { type: 'array', items: { type: 'string' } },
  },
  required: ['lens', 'summary', 'findings', 'directions', 'open_questions'],
}

const LENSES = [
  { key: 'results', prompt: `Lens: RESULTS ARCHAEOLOGY. Build a table of every experiment the project has run (from docs/research/*.md, docs/decisions.md, results/, runs/, git log): what was tested, the effect size, the noise level it was judged against, and the verdict. Then answer: what has actually moved playing strength, and by how much? What has been flat? Is there a pattern in what works vs what doesn't (e.g. changes to labels/training vs changes to search vs changes to data)? How much CPU time went into experiments that were within noise? Do a small quantitative summary (e.g. effect sizes vs noise) where the data allows.` },
  { key: 'strength', prompt: `Lens: WHERE IS PLAYING STRENGTH LOST? Use the bench, exact-puzzle and tight-fight results to locate errors: which encounters, which HP bands, which horizons, which kinds of decisions (card order, targeting, ending turn, potions?), search depth vs evaluation error. The exact solver reports ~10% wrong picks at horizon >= 1 (docs/research/exact-puzzles.md): what does that say about where the ceiling is? Compare search+heuristic vs search+net vs exact play. If raw per-fight or per-decision data exists in results/ or runs/, analyse it directly. Conclude: what single change would most raise win rate, and how do we know?` },
  { key: 'generalisation', prompt: `Lens: GOAL 1, GENERALISATION AND CUSTOM CONTENT. How well does the current design (choose between afterstates, cards described by effect primitives, value nets) actually generalise to unseen content? What has been measured (check 6 / generalise.py, held-out halves, generated cards, Silent vs Ironclad), and what has not? Read docs/extending.md and the rules-engine umbrella: how many steps until someone can add a new character, mechanic or entity by data alone, and is the planned engine series the shortest path or is it gold-plating? What would a truly content-agnostic AI need that this design lacks (e.g. reasoning about powers it has never seen, whose main effect is granting an unknown power, which docs/concept.md admits is a weakness)? Propose the most informative experiment on random content.` },
  { key: 'prior-art', prompt: `Lens: PRIOR ART AND THE STOCKFISH ANALOGY. Research (web search allowed) what made Stockfish dominant (search + NNUE evaluation, testing framework fishtest with SPRT, massive self-play, incremental updates) and what AlphaZero/MuZero, TD-Gammon/GNU Backgammon, and card-game AIs with hidden information and chance (poker solvers, Hearthstone/Magic AIs, Slay the Spire bots such as bottled_ai, sts_lightspeed and its search agent, any StS papers, e.g. on deckbuilding/run-level decisions) did. Then map it onto this project: which of those ingredients does sts-for-ai have, which are missing, and which missing one matters most? Pay special attention to fishtest's SPRT: how Stockfish measures tiny Elo gains cheaply, and whether the project's gate/tight-fight method could become sequential testing. Cite sources with URLs. Read the repo only enough to map it.` },
  { key: 'throughput', prompt: `Lens: THROUGHPUT AND PROCESS. Machine time is the bottleneck, and much of it goes to waiting for training runs inside tests. Using git log timestamps (git log --format='%h %ad %s' --date=iso), jobs/roles.log, the job records in jobs/done/, docs/digest/, logs/ and results/ logs, and the scripts: where did wall-clock time go over the last few days? How long do the slow test suites take (test_sweep ~35 min, test_rounds ~37 min, test_curriculum ~8 min, etc.) and why: what do they train, and could they use tiny fixtures? Profile by reading code (do not run heavy profilers): what dominates a training run's time (self-play in Rust, labelling with the exact solver, torch training on CPU, evaluation fights)? What is the manager process's own overhead (lock juggling, duplicate forks, stand-downs)? Recommend the concrete changes that would most increase useful experiments per day, with estimated speedups.` },
  { key: 'measurement', prompt: `Lens: MEASUREMENT AND EVALUATION. Is the project's yardstick able to detect progress toward "Stockfish-level"? Examine the gate (learned-play Amendment 5: search with the net beats search + heuristic on tight fights on both halves), tight fights v2 (1,226 cells x 20 seeds), the seed check results (no night round holds up over training seeds; training-seed sd ~0.006-0.0075), and how win rate is defined. Do a power analysis from the numbers: what effect size can one run detect, and how many seeds/fights would a 0.005 effect need? Are tight fights (calibrated near 50%) representative of what matters for a full run (HP carried between fights)? Propose a better measurement ladder: e.g. paired comparisons on identical seeds, sequential testing (SPRT), an Elo-like ladder of agents, HP-loss per fight as a lower-variance metric than win/loss, and a full-Act win rate. Say which metric to adopt first and why.` },
]

phase('Analyse')
const analyses = await parallel(LENSES.map(l => () =>
  agent(COMMON + '\n' + l.prompt + '\nReturn your analysis in the structured form.', { label: `analyse:${l.key}`, phase: 'Analyse', schema: FINDINGS })
))
const got = analyses.filter(Boolean)
log(`${got.length}/${LENSES.length} analyses returned`)

phase('Synthesise')
const SYNTH = {
  type: 'object',
  properties: {
    diagnosis: { type: 'string', description: 'the big picture in plain prose: where the project really stands against both goals, the underlying pattern, what has been holding it back' },
    key_claims: {
      type: 'array',
      description: 'the 4-6 load-bearing claims the recommendations rest on',
      items: { type: 'object', properties: { claim: { type: 'string' }, evidence: { type: 'string' } }, required: ['claim', 'evidence'] },
    },
    stop_doing: { type: 'array', items: { type: 'string' } },
    directions: {
      type: 'array',
      description: 'ranked by expected value per CPU-hour, best first; 5-10 items',
      items: {
        type: 'object',
        properties: {
          rank: { type: 'number' }, name: { type: 'string' }, what: { type: 'string' }, why: { type: 'string' },
          cpu_cost: { type: 'string' }, first_check: { type: 'string' }, serves_goal: { type: 'string' },
        },
        required: ['rank', 'name', 'what', 'why', 'cpu_cost', 'first_check', 'serves_goal'],
      },
    },
    next_48h: { type: 'string', description: 'a concrete plan for the next 48 hours: what runs on the CPU when, and what CPU-light work goes alongside' },
    open_questions: { type: 'array', items: { type: 'string' } },
  },
  required: ['diagnosis', 'key_claims', 'stop_doing', 'directions', 'next_48h', 'open_questions'],
}
const synth = await agent(COMMON + `
You are the SYNTHESISER. Below are six independent analyses of the project through different lenses. Weigh them against each other: where they agree, where they conflict (say which you believe and why), and what none of them saw. You may read repo files to settle a conflict. Then write the strategic review: diagnosis, the load-bearing claims, what to stop doing, directions ranked by expected value per CPU-hour (CPU time is the scarce resource; agent time is plentiful), and a 48-hour plan. Be decisive; recommend, don't survey.

ANALYSES (JSON):
${JSON.stringify(got, null, 1)}
`, { label: 'synthesise', phase: 'Synthesise', schema: SYNTH, effort: 'high' })

phase('Verify')
const VERDICT = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    status: { type: 'string', enum: ['holds', 'overstated', 'wrong', 'unverifiable'] },
    reason: { type: 'string', description: 'what you checked, with file paths and numbers' },
    corrected_claim: { type: 'string' },
  },
  required: ['refuted', 'status', 'reason', 'corrected_claim'],
}
const claims = (synth && synth.key_claims) || []
const verified = await parallel(claims.map((c, i) => () =>
  parallel([0, 1].map(k => () => agent(COMMON + `
You are a SKEPTIC (#${k + 1}). Try to refute this claim from a strategic review of the project by checking it against the repo's data and docs yourself. Do not trust the stated evidence; find the primary source. ${k === 1 ? 'Focus on whether the numbers are right and correctly compared (noise, sample sizes, like-for-like).' : 'Focus on whether the claim follows from the evidence and whether other data contradicts it.'} If uncertain, say "unverifiable" rather than "holds".

CLAIM: ${c.claim}
STATED EVIDENCE: ${c.evidence}
`, { label: `verify:claim${i + 1}:${k + 1}`, phase: 'Verify', schema: VERDICT })))
    .then(vs => ({ claim: c, verdicts: vs.filter(Boolean) }))
))

return { analyses: got, synthesis: synth, verified }
