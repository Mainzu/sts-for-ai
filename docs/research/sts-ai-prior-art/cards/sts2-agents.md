# StS2 (Slay the Spire 2) agents, bots, simulators and data tools: cards

Scope note: StS2 is the Mega Crit Early Access title (Godot/C#, 2026). Our engine models StS1 Act 1, so nothing here is a drop-in simulator for us. The useful parts are method references (headless harness, state serialization, RL setup) and one data-exposure question. Sources below were opened on 2026-11-15. Stars are as shown on the GitHub page at fetch time. Tutorial/blog sources that failed to load are listed at the end without cards.

### sts2-ai-mod (2026)
- **Link:** https://github.com/ndwang/sts2-ai-mod · **Venue:** GitHub · **Cited by:** 1 star, 1 fork · **Read:** abstract (README and repo page)
- **Problem:** Let an external program read StS2 game state and act in the live game.
- **Method:** C# in-game mod that runs an HTTP server at `http://localhost:57541`. `GET /state/wait` long-polls until a decision point; `POST /action` sends a JSON action with a `type` field and parameters. Also `GET /state`, `GET /map`, `GET /log-level`.
- **Assumes:** Live game process on Windows with StS2 installed (build needs .NET 9 and a local `sts2.dll` reference). Real-time, one game per process. No simulator, no determinism control described.
- **Claims:** No results or benchmarks reported. Long-poll timeout defaults to 30 s, capped at 120 s. Covers main menu, map, combat, events, rest sites, shop, treasure, rewards, card selection, game over.
- **Evaluation:** None reported. README points to "ClaudePlaysSTS2" as an example agent (not opened).
- **Code:** https://github.com/ndwang/sts2-ai-mod, MIT. Release link in the page points to a different owner name (`wdong`), so check it before use.
- **Fit:** partial. Clean state/action JSON over HTTP is a pattern to copy for a live-game oracle, but it drives the real game in real time, which our CPU-hours target cannot use for search.

### sts2-cli, wuhao21 (2026)
- **Link:** https://github.com/wuhao21/sts2-cli · **Venue:** GitHub · **Cited by:** 285 stars, 67 forks · **Read:** abstract (README)
- **Problem:** Run the real StS2 engine headless from a terminal for scripted or agent play.
- **Method:** Python/JS/LLM client talks JSON over stdin/stdout to a C# project (`src/Sts2Headless`), which drives the game's own `sts2.dll` after IL patching. `src/GodotStubs` replaces `GodotSharp.dll`; Harmony patches fix localization. Commands: `start_run`, `action` (`play_card`, `end_turn`, `select_map_node`, `skip_card_reward`), `quit`. Decision points: `map_select`, `combat_play`, `card_reward`, `rest_site`, `event_choice`, `shop`, `game_over`. Stalled turns return `error_code: "combat_turn_timeout"` without marking a defeat. Logs are JSONL under `logs/`, auto-deleted after 7 days.
- **Assumes:** Steam copy of StS2 on Windows, .NET 9+ SDK, Python 3.9+. Tested with "v0.111.0 (Steam public-beta, build 24724944)"; the README warns other versions "may require adapter changes." All content unlocked; Ironclad, Silent, Defect, Necrobinder, Regent listed as fully playable.
- **Claims:** README says "all damage, card effects, enemy AI, relics, and RNG are identical to the actual game." This is the authors' claim; no independent check found. No win rates or performance numbers reported.
- **Evaluation:** Compatibility check `python3 python/play_full_run.py 5 Ironclad` (5 runs, must end in victory or defeat, not crash or stall). No quantitative benchmark.
- **Code:** https://github.com/wuhao21/sts2-cli, MIT (per page).
- **Fit:** partial. The most relevant StS2 item for us: a real-engine headless harness with decision-point JSON. It is an oracle-style reference for checking our StS1 engine's design, not something we can call per search node (game-engine speed and version lock unknown). Breaks the "our own engine is the simulator" constraint if used as the simulator.

### sts2-cli, liumin1128 (fork) (2026)
- **Link:** https://github.com/liumin1128/sts2-cli · **Venue:** GitHub · **Cited by:** 0 stars, 0 forks (101 commits) · **Read:** abstract (README)
- **Problem:** Same as wuhao21 (appears to be a fork of it).
- **Method:** Same description as wuhao21's card: headless CLI, JSON stdin/stdout protocol, `start_run`/`action`/`quit`, real `sts2.dll` with IL patches.
- **Assumes:** Same as the upstream: Steam install, .NET 9+, Python 3.9+, Windows.
- **Claims:** Same "identical to the actual game" statement as upstream; no results.
- **Evaluation:** None reported.
- **Code:** https://github.com/liumin1128/sts2-cli, licence file linked but type not named on the page.
- **Fit:** partial. Duplicate of the upstream harness; listed only for completeness.

### STS2-Agent, CharTyr (2026)
- **Link:** https://github.com/CharTyr/STS2-Agent · **Venue:** GitHub (Steam Workshop mod) · **Cited by:** 360 stars, 56 forks, 833 commits · **Read:** abstract (README)
- **Problem:** An in-game AI that auto-plays StS2 (combat, card draft, shops, events, pathing) and a local co-op teammate, driven by a hosted LLM.
- **Method:** C# mod with Godot overlay, OpenAI-compatible client, decision loop and a budget guard. Embedded HTTP API at `127.0.0.1:8080`: `GET /state`, `GET /actions/available`, `GET /events/stream` (SSE), `POST /action` (`play_card`, `choose_map_node`, `proceed`), `GET /data/{collection}`, `POST /session/control`. Optional MCP at `/mcp`. The model reads a text state summary; screenshots optional.
- **Assumes:** Live game on Windows; a model endpoint (DeepSeek, OpenRouter, OpenAI, Ollama, LM Studio, custom). The auto-play features are labelled "unreleased"; released version stays 0.17.0. Default request cap 1,500.
- **Claims:** No win-rate or benchmark figures. README says "Run completion and strategy quality depend on the model and game conditions," and offline tests "do not prove full-run completion."
- **Evaluation:** Automated tests run without the game; live validation documented separately (not opened).
- **Code:** https://github.com/CharTyr/STS2-Agent, AGPL-3.0.
- **Fit:** poor for our constraints. Uses an LLM in the loop, which our rules forbid. Its `GET /data/{collection}` endpoint is the only StS2 machine-readable data access point seen in our sources; worth a check of what collections it returns. The HTTP state/action API is a pattern reference.

### STS2 CLI Mod, longkerdandy (2026)
- **Link:** https://github.com/longkerdandy/STS2-Cli-Mod · **Venue:** GitHub · **Cited by:** 2 stars, 2 forks, 219 commits · **Read:** abstract (README)
- **Problem:** Let AI agents or scripts read StS2 state and act from a shell.
- **Method:** Two .NET 9 projects sharing no code. `STS2.Cli.Mod` runs in-process in Godot 4.5.1 and marshals state access to the main thread; `STS2.Cli.Cmd` is the `sts2` CLI. They talk over a named pipe `sts2-cli-mod` with JSON. Responses: `{"ok": true, "data": {...}}` or `{"ok": false, "error": "CODE", "message": ...}`, snake_case. Exit codes 0 success, 1 connection, 2 invalid state, 3 invalid param, 4 timeout, 5 state changed. 40+ commands (e.g. `sts2 play_card STRIKE --target 0`).
- **Assumes:** Live game on Windows (primary); WSL supported; macOS/Linux "untested." .NET 9 SDK.
- **Claims:** None quantitative. State JSON covers hand, enemies, intents, powers, draw/discard/exhaust piles, map, events, shop, rewards, rest sites; 16+ screen types.
- **Evaluation:** None reported.
- **Code:** https://github.com/longkerdandy/STS2-Cli-Mod, licence section present but name not captured. Not affiliated with Mega Crit.
- **Fit:** partial. The state schema (hand, intents, powers, pile contents, `state changed` exit code for stale actions) is a useful reference for what a combat observation should contain. Live-game only, so not a simulator.

### sts2-mcp, Yidhar (2026)
- **Link:** https://cdn.jsdelivr.net/gh/Yidhar/sts2-mcp@main/README.md (README mirror; repo page not opened) · **Venue:** GitHub · **Cited by:** n/a (star count not captured) · **Read:** abstract (README)
- **Problem:** Connect the live game to LLM agents via MCP without screen scraping.
- **Method:** C#/.NET 9 bridge mod `mods/sts2-bridge` serialises Run, Combat, Rewards, Maps to JSON, executes actions by calling game methods, writes `session.json` for discovery. Node 22 MCP server exposes 12 tools (e.g. `sts2_get_state`, `sts2_list_actions`, `sts2_perform_action`, `sts2_execute_combat_sequence` that batches cards, potions and `end_turn`, `sts2_resolve_shop_visit`). Guards stale actions with `state_version`.
- **Assumes:** Windows, Node 22+, legal StS2 copy. Built for LLM round trips, so batching is the design goal.
- **Claims:** README claims "100% accuracy and sub-millisecond latency" with no measured benchmark or method. Treat as unverified.
- **Evaluation:** None reported.
- **Code:** https://github.com/Yidhar/sts2-mcp, MIT (per README; not opened directly). Not affiliated with Mega Crit.
- **Fit:** partial. `state_version` stale-action guard and batched combat sequences are good ideas for our command interface. The LLM-first design and unmeasured latency claim are poor fits.

### netcan/slay-the-spire2-agent (2026)
- **Link:** https://github.com/netcan/slay-the-spire2-agent · **Venue:** GitHub · **Cited by:** 8 stars, 1 fork, 143 commits · **Read:** abstract (README)
- **Problem:** A pluggable policy framework that lets outside Python policies (and future LLMs) play a live StS2 game.
- **Method:** Python 3.11+ bridge client, policies, orchestrator, traces; in-game C# bridge mod; local HTTP host: `GET /health`, `GET /snapshot`, `GET /actions`, `POST /apply`, `GET/POST/DELETE /agent-status`. Writes disabled by default and must be enabled to act.
- **Assumes:** Windows install of the game, Godot 4.5.1, .NET SDK 9.
- **Claims:** No benchmarks, win rates or outcomes reported.
- **Evaluation:** None reported.
- **Code:** https://github.com/netcan/slay-the-spire2-agent; licence not shown on the captured page.
- **Fit:** partial. Policy-plugin separation (state, action list, apply, trace) matches our separation of engine and policy. No search or learning method shown, so it gives no strength evidence.

### Training an RL Agent to Play Slay the Spire 2 (cmcour, 2026?)
- **Link:** https://cmcour.github.io/sts2Showcase/ · **Venue:** blog (personal project page) · **Cited by:** n/a · **Read:** full text (single page)
- **Problem:** Train learned policies for each StS2 decision surface (combat, card picks, rest sites, shops, events, relics, routing).
- **Method:** PPO for learners. Seven specialised models; the card-picker and rest-site models fused into one `RunStateModel`; later models reuse combat's vocabulary via frozen embedding warm-start. ShopModel PPO updates every couple of minutes, with a value head.
- **Assumes:** Distributed: 11 worker laptops generating games at about 9 full runs per minute; central machine with three learners on a "brain box." ShopModel uses 32 records per update (proposal to raise to 64 not implemented). Real game via the mod, not a custom simulator.
- **Claims:** "250k+ runs simulated across the Phase 3 fleet." ShopModel V-head "positive correlation with boss-win," no coefficient, no win rates, baselines or sample sizes. V-variance described as "chronic-low." Combat model "stable and in maintenance mode." No combat win rate given.
- **Evaluation:** Live game fleet; no public benchmark.
- **Code:** none found (page gives no link or licence).
- **Fit:** partial. Per-decision-surface model split and frozen-embedding transfer are relevant to our separate run-layer. But it uses a large distributed fleet and PPO on live runs, which breaks our CPU-only, single-machine budget, and the results are unquantified.

### StS2 Exporter, OceanUwU (2026)
- **Link:** https://github.com/OceanUwU/sts2-exporter · **Venue:** GitHub · **Cited by:** 8 stars, 1 fork, 11 open issues · **Read:** abstract (README)
- **Problem:** Dump StS2 item data (cards, relics, potions) and textures from the game.
- **Method:** In-game Godot mod (`STS2Export.dll`, `.pck`, Scriban templating). Writes text files for item data plus rendered images; dumps all atlases split into individual image files. Port of the StS1 `sts-exporter` ("mostly compatible," some features missing).
- **Assumes:** Built in Megadot 4.5.1-m.5 (Godot fork) and `dotnet build`; BaseLib mod must be installed alongside.
- **Claims:** None quantitative.
- **Evaluation:** None reported. Output format not JSON per the page; the page says "text files" and does not name the format, so check the output before relying on it as machine-readable.
- **Code:** https://github.com/OceanUwU/sts2-exporter, MIT (per page).
- **Fit:** partial. This is the closest thing we found to card data export for a machine-readable table. Monsters are not mentioned on the page. Output format unconfirmed; treat as a candidate to check, not a finished data source.

### Slay the Spire Wiki, Module:Cards/StS2 data (wiki)
- **Link:** https://slaythespire.wiki.gg/wiki/Module:Cards/StS2_data · **Venue:** wiki (Lua module) · **Cited by:** n/a · **Read:** abstract (captured page)
- **Problem:** Card data for wiki templates.
- **Method:** Lua module returning a table. The captured page shows only `return {` and `}`, so no entries were visible in the snapshot.
- **Assumes:** Lua, wiki template loader.
- **Claims:** none.
- **Evaluation:** none.
- **Code:** n/a (wiki content, licence per wiki; not checked).
- **Fit:** poor. The captured snapshot was empty, so no field names could be confirmed; the revision (oldid=72090) would need checking. A sibling module `Module:Keywords/StS2 data` appeared in search but was not opened.

## Not carded (failed to load)

- Tomokinotes blog, "A Slay the Spire 2 Auto-Play Bot (1): Observing and Controlling It From Python" (https://tomokinotes.pages.dev/en/blog/sts2-bot-01-python-control/) and "12 Hours Running a Slay the Spire 2 AI: the Levers That Worked, and the Ones That Didn't" (https://tomokinotes.pages.dev/en/blog/sts2-bot-02-tuning-levers/). Both returned a DNS failure (`getaddrinfo ENOTFOUND`). This is probably the most relevant write-up in the field (levers and numbers), so it should be retried by someone else.

## Not opened (seen in search results only)

- AutoClad (benmuth), gym-sts (kronion; StS1), sts2-devmode (wrxinyue), STS2FirstMod (jiegec), sts-exporter (avolny, StS1), Nexus mods 69/100/264/293/320/883, Thunderstore/Nexus pages, Reddit and Discord threads. No community card-value or combat-calculator tool for StS2 turned up in the searches.

## Summary for the caller

- **Field status:** thin but active. About 8 StS2 repos (2026) build live-game HTTP, pipe or stdio bridges. Only one (wuhao21, plus a fork) runs the real engine headless. Every one is live-game or LLM-first, with no search or learning method except the PPO fleet write-up.
- **Play-strength evidence:** none quantitative in any source opened. The only numbers are the RL write-up's "250k+ runs" and "positive correlation," with no baselines.
- **Machine-readable StS2 data:** no official export. Community exporter (OceanUwU) writes text files of cards, relics, potions; format unconfirmed. CharTyr's `GET /data/{collection}` endpoint is another route; not verified.
- **Transfer to our StS1 engine:** low. The useful pieces are protocol and state-schema patterns, not strength methods.
- **Count:** 10 sources opened (target was 8; the batch overshot by two). Full text: 1 (cmcour blog page, as a single HTML page); the other 9 were GitHub/mod README pages read through WebFetch (abstract-level, README only, no source code read).
