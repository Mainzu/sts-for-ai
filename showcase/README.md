# Showcase site

The project's showcase page for Slay the Spire players, written by hand on
2026-11-14 and published as a private claude.ai Artifact:
(a private claude.ai artifact; this repository's copy is index.html)

| File | What |
|---|---|
| `index.html` | the page: all prose and every quoted number, each beside its setting tag |
| `history.js` | hand-written: one entry per lane (from `measurement/portfolio-<lane>` and its decisions entries), the job queue's thread-hours per day |
| `tried.js` | hand-written with helpers and checked: one entry per thing tried outside the lanes, each naming its source |
| `story.js` | the history views: the timeline of everything tried, the per-stretch lists, the lane scorecard charts |
| `rooms/` | the game's map icons (monster, elite, rest, the three Act 1 bosses), taken from `desktop-1.0.jar` `images/ui/map/` and cropped; white shapes the page tints through SVG masks. Publish them with the other files. |
| `stats-data.js`, `stats.js`, `stats/` | the Statistics tab (`#stats`): `stats/final.json` holds each statistic as mined and as its independent check left it; `python -I showcase/stats/build_data.py . showcase/stats/final.json` writes `stats-data.js` (which ones show, in which section); `stats/history.json` holds the project-history statistics (workflow sts-history-stats: eight miners, an independent recheck each, a repeat pass), each with its chart kind (bars, line, scatter, bignum, slope, tally, heat, timeline); `stats/audit.json` is the repeat audit of the real-game set. The tab is laid out by the story's eight periods plus a whole-project section. `stats/<theme>/`, `stats/verify/<id>/` and `stats/history/` are the mining and checking scripts (run with `python -I`, read-only on the records). |
| `app.js` | the result charts (plain SVG) and the hand-written notes on each real-game run (`RUN_NOTES`) |
| `data.js` | chart data, written by `extract.py`; don't edit |
| `llms.md`, `llms-full.md` | the page as plain Markdown for language models, written by `llm.py`; don't edit. `llms.md` is the page with every chart as a table and every setting tag's hover text inline (about 33k tokens); `llms-full.md` adds every real-game fight, the whole "everything tried" list and each statistic's setting and data (about 110k tokens) |
| `llm.py` | reads `index.html` and the page's data (Node evaluates `data.js`, `tried.js`, `history.js`, `stats-data.js` and the literals inside `app.js` and `story.js`) and writes the two Markdown files; `--check` exits 1 when they are stale |
| `extract.py` | reads finished result files under `results/` (gauntlet files, one boss-replay file, `results/real-game/` through the bridge's own reader `runs_of` in `scripts/real_game_report.py`) and writes `data.js` |

The prose is not generated: results from different periods used different
rulers, so each number is quoted by hand beside the setting it was measured
on, and no chart puts numbers from different settings on one axis.

## Update and republish

1. `python -I showcase/extract.py --check` prints the numbers the page
   quotes; `python -I showcase/extract.py` rewrites `data.js` (light: it only
   reads JSON).
2. Edit the prose in `index.html` (new real-game runs: add a `RUN_NOTES`
   entry in `app.js`, keyed by the record folder's stamp). Then
   `python -I showcase/llm.py` rewrites `llms.md` and `llms-full.md`.
3. Look at it locally: `python -m http.server 8770 -d showcase` serves
   this folder at http://127.0.0.1:8770.
4. Publish `showcase/index.html` with the Artifact tool, passing in `files`
   every script the page loads (`data.js`, `app.js`, `tried.js`,
   `history.js`, `stats-data.js`, `stats.js`, `story.js`, each from
   `showcase/`) and the two text editions with
   `{"from": "showcase/llms.md", "contentType": "text/markdown"}` (same for
   `llms-full.md`; the type must be exactly `text/markdown`). `rooms/` is
   already published and stays unless replaced. Set `url` to the link above
   from another conversation (so the link stays).

## Clean-up

`data.js` is the only file `extract.py` writes; rerun it to regenerate.
`llms.md` and `llms-full.md` are the only files `llm.py` writes. Nothing
else here writes to disk.
