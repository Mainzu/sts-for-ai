"""Learned-play registry: every dataset, run and model is kept, so old
experiments never need redoing.

- datasets/<id>/: game records, not features. `games.jsonl.gz` has one game
  per line (setup, every action, per-decision search option values,
  outcome); `manifest.json` records the engine commit, the rules version
  (hash of the golden trajectories), the generating config, the parent model
  and the games' hash. The id is the manifest's hash. Scripts never
  overwrite or delete a dataset.
- cache/<id>-<format>-<version>[-<labels>]/: features and labels of a dataset's
  sampled states, rebuilt
  on demand by replaying its games; oldest files are evicted past a size cap.
  Replay refuses a dataset recorded under other rules.
- runs/<date>-<config>-<hash>/: one immutable folder per training run
  (config, git commit, dataset ids, model, training curves, bench results);
  `runs/index.csv` gets one line per run.
"""

import csv
import ctypes
import datetime
import gzip
import hashlib
import itertools
import json
import os
import re
import shutil
import subprocess
import time

import numpy as np

import selfplay as sp
import action_text
import sts
import stsnet
from stsnet import HP_SCALARS, Dataset, DatasetWriter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GOLDEN = os.path.join(ROOT, "engine", "tests", "data", "golden.txt")
# golden.txt hashes re-recorded under the same rules (only the recording
# changed) -> the rules version they stand for. A new rule never goes here.
SAME_RULES = {
    # 2026-11-10: an ended fight is recorded by what outlasts it.
    "e9c10f64df68a215": "7042d1d6a6149ba0",
}
CACHE_CAP = 10 * 1024 ** 3
# Games replayed and encoded at a time: a chunk's replayed games are held
# while it encodes, ~1.3 MB per net-round game (curriculum step 7: 3,000
# held ~4 GB at real round sizes); the cache is the same for any chunk size.
CHUNK = 500
# Games per `sts.run` call in self-play (`play`): a progress line per chunk.
PLAY_CHUNK = 200
# Bumped when what a cache file holds changes (v2: heuristic estimates and
# ranking fields; v3: the HP scalars of switch 6; v4: each example's real
# outcome label, no heuristic estimates; v5: switch 6's histogram labels;
# v6: each example's label inputs and codec bytes, for curriculum labels
# applied at load; v7: a directory of .npy files, memory-mapped when loaded,
# written chunk by chunk), so older cache files are rebuilt.
CACHE_VERSION = "v7"
INDEX_FIELDS = ["run", "date", "commit", "config", "switches", "feature_format", "bench_version",
                "val_mse", "tight_held_out_regret", "tight_held_out_ranking", "tight_held_out_win",
                "tight_train_regret", "tight_train_ranking", "tight_train_win"]


class RulesVersionError(Exception):
    pass


class ContentError(Exception):
    """A dataset of generated content whose pack isn't loaded in this process."""


def datasets_dir(root=ROOT):
    return os.path.join(root, "datasets")


def cache_dir(root=ROOT):
    """root/cache, or $STS_CACHE_DIR (Colab: local disk, registry on Drive)."""
    return os.environ.get("STS_CACHE_DIR") or os.path.join(root, "cache")


def packs_dir(root=ROOT):
    """root/datasets/packs: content packs by hash (docs/specs/runtime-registry.md stage 2)."""
    return os.path.join(datasets_dir(root), "packs")


def pack_hash(text_bytes):
    """The engine's content hash of a pack's text: FNV-1a 64, 16 hex digits."""
    h = 0xcbf29ce484222325
    for x in text_bytes:
        h = ((h ^ x) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def store_pack(h, root=ROOT):
    """Writes the pack of hash `h` (its exact loaded text, from
    selfplay.load_content) to the store once; a hash this process didn't
    load through selfplay is skipped."""
    text = sp.PACK_TEXTS.get(h)
    p = os.path.join(packs_dir(root), h + ".json")
    if text is None or os.path.exists(p):
        return
    os.makedirs(packs_dir(root), exist_ok=True)
    tmp = f"{p}.{os.getpid()}.tmp"
    with open(tmp, "wb") as f:
        f.write(text.encode())
    os.replace(tmp, p)


def ensure_content(hashes, root=ROOT):
    """Loads each pack of `hashes` this process hasn't loaded from the store,
    after checking its bytes hash to its name; ContentError if one is missing
    or doesn't match (never loaded then)."""
    for h in hashes:
        if h in sts.loaded_content():
            continue
        p = os.path.join(packs_dir(root), h + ".json")
        if not os.path.exists(p):
            raise ContentError(
                f"pack {h} isn't loaded (loaded: {sts.loaded_content() or 'none'}) and isn't stored at {p}; "
                "load it first (selfplay.load_content of the config's `content`).")
        with open(p, "rb") as f:
            b = f.read()
        if pack_hash(b) != h:
            raise ContentError(f"stored pack {p} doesn't hash to its name (got {pack_hash(b)}); not loaded")
        sts.load_content(b.decode())
        sp.PACK_TEXTS[h] = b.decode()


def runs_dir(root=ROOT):
    return os.path.join(root, "runs")


def _hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def rules_version():
    """Hash of the golden trajectories, through SAME_RULES: changes only
    when game rules do."""
    with open(GOLDEN, "rb") as f:
        h = hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()[:16]
    return SAME_RULES.get(h, h)


def git_commit():
    """HEAD, with "+dirty" when the engine or bindings have local changes."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "engine", "py/src"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    return head + ("+dirty" if dirty else "")


# --- datasets -------------------------------------------------------------

# Action text lives in action_text (one module for every record).
encode_action = action_text.encode_action
decode_action = action_text.decode_action


def play(specs, config, evaluator=None, features=None, forced=None, log=None, label="self-play", keep_states=False):
    """Plays `specs` (encounter, deck, seed[, hp]) with search, recording every
    decision and its search's option values; `config["search"]` holds `sts.run`'s search settings and
    optional `hp` / `character` / `no_death` (switch 6's simulation) / `explore` (softmax
    temperature of self-play rounds). `forced`: per spec, opening actions
    played first (branch games). Played PLAY_CHUNK games at a time for the
    progress line (`log`); each game's result doesn't depend on the chunk.
    Results drop their recorded `states` (records don't use them, and they
    are most of a game's memory) unless `keep_states`."""
    out = []
    for _, res in play_chunks(specs, config, evaluator, features, forced, log, label, keep_states):
        out += res
    return out


def play_chunks(specs, config, evaluator=None, features=None, forced=None, log=None, label="self-play",
                keep_states=False):
    """`play` one PLAY_CHUNK at a time: yields (index of the chunk's first
    spec, its results)."""
    from progress import Progress
    kw = dict(config.get("search", {}))
    if callable(evaluator):  # a Python net takes turns on Python's lock; a NetEvaluator uses every core
        kw["threads"] = stsnet.NET_THREADS
    kw = stsnet.job_threads(kw)
    p = Progress(label, len(specs), log)
    if config.get("ascension"):  # every fight at the config's level (docs/specs/ascension.md)
        specs = [keyed_spec(s, config["ascension"]) for s in specs]
    for i in range(0, len(specs), PLAY_CHUNK):
        part = {} if forced is None else {"forced": forced[i:i + PLAY_CHUNK]}
        res = sts.run("search", specs[i:i + PLAY_CHUNK], evaluator=evaluator, features=features, record=True,
                      values=True, hp=config.get("hp"), character=config.get("character", "ironclad"),
                      no_death=bool(config.get("no_death")), explore=float(config.get("explore", 0.0)),
                      **kw, **part)
        if not keep_states:
            for r in res:
                r.pop("states", None)
        p.update(len(specs[i:i + PLAY_CHUNK]))
        yield i, res
    p.close()


def keyed_spec(spec, ascension):
    """The tuple spec (encounter, deck, seed[, hp]) as the keyed form `sts.run`
    takes, at `ascension`."""
    enc, deck, seed = spec[:3]
    return {"encounter": enc, "deck": deck, "seed": seed, "ascension": ascension,
            **({"hp": spec[3]} if len(spec) > 3 else {})}


def records(specs, groups, results, config=None):
    """Game records (JSON-able dicts) for played specs. `values` holds, per
    decision, `[[actions], value]` per root option of the agent's search
    (null when the results have none). `hp` is the spec's own starting HP
    (a 4-field spec), else the config's."""
    config = config or {}
    out = []
    for spec, g, r in zip(specs, groups, results):
        enc, deck, seed = spec[:3]
        hp = int(spec[3]) if len(spec) > 3 else config.get("hp")
        out.append({"character": config.get("character", "ironclad"), "encounter": enc,
                    "deck": [str(c) for c in deck], "hp": hp, "seed": int(seed), "group": int(g),
                    **({"ascension": config["ascension"]} if config.get("ascension") else {}),
                    **({"no_death": True} if config.get("no_death") else {}),
                    "actions": [_text(a) for a in r["actions"]], "values": _values(r),
                    **({"luck": [float(x) for x in r["luck"]]} if r.get("luck") is not None else {}),
                    "outcome": {k: r[k] for k in ("won", "hp_start", "hp_end", "turns", "score")}})
    return out


def _text(a):
    """An action's text; one already encoded (a Python-side player's record,
    docs/specs/two-turn-round.md) passes through."""
    return a if isinstance(a, str) else encode_action(a)


def _values(r):
    if "values" not in r:
        return None
    return [[[[_text(a) for a in acts], float(v)] for acts, v in d] for d in r["values"]]


def manifest_id(manifest):
    return _hash(manifest)[:12]


def write_dataset(games, config, parent_model=None, root=ROOT, rules=None, n_games=None):
    """Stores games; returns the dataset id. An existing dataset with the same
    id is left untouched. `games` is a list, encoded line by line twice
    (hash, then file), not held as one string the size of the file; or, with
    `n_games`, an iterable read once (a self-play stream, `selfplay` with
    keep_results=False): written as it comes into a temporary folder,
    hashed on the way, the same bytes."""
    def lines(gs):
        return (json.dumps(g, sort_keys=True).encode() + b"\n" for g in gs)

    def write(tmp, gs, sha=None):
        os.makedirs(tmp, exist_ok=True)
        with open(os.path.join(tmp, "games.jsonl.gz"), "wb") as raw, \
                gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as f:
            for line in lines(gs):
                if sha is not None:
                    sha.update(line)
                f.write(line)

    sha, streamed = hashlib.sha256(), n_games is not None
    if not streamed:
        n_games = len(games)
        for line in lines(games):
            sha.update(line)
    else:
        tmp = os.path.join(datasets_dir(root), f"stream.tmp{os.getpid()}-{next(_STREAM_TMP)}")
        write(tmp, games, sha)
    manifest = {"engine_commit": git_commit(), "rules_version": rules or rules_version(),
                "config": config, "parent_model": parent_model, "n_games": n_games,
                "games_sha256": sha.hexdigest()}
    if config.get("ascension"):  # kept apart like the rules version; absent at A0
        manifest["ascension"] = config["ascension"]
    if isinstance(config.get("content"), dict):  # generated content (registry-lite): replay needs this pack loaded
        manifest["content_hash"] = config["content"]["hash"]
        store_pack(manifest["content_hash"], root)
    if config.get("packs"):  # pack learn: replay needs these packs loaded
        manifest["content_hashes"] = list(config["packs"])
        for h in manifest["content_hashes"]:
            store_pack(h, root)
    ds = manifest_id(manifest)
    path = os.path.join(datasets_dir(root), ds)
    if os.path.exists(os.path.join(path, "manifest.json")):
        if streamed:
            shutil.rmtree(tmp, ignore_errors=True)
        return ds
    if not streamed:
        tmp = f"{path}.tmp{os.getpid()}"  # clean_stale's pattern: a killed write is removed later
        write(tmp, games)
    with open(os.path.join(tmp, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    # Windows refuses to rename a folder while another process (antivirus,
    # indexer) has a file in it open; that passes within seconds.
    for attempt in range(10):
        try:
            os.replace(tmp, path)
            break
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.2 * 2 ** min(attempt, 5))
    return ds


_STREAM_TMP = itertools.count()


# Offset of the branch-picking RNG's seed from the config's sample_seed.
BRANCH_SEED = 7_000_001


def selfplay(specs, groups, config, parent_model=None, evaluator=None, features=None, root=ROOT, log=None,
             keep_states=False, keep_results=True):
    """Plays and stores one dataset; returns (id, the main games' recorded
    results). With `config["branches"]` (switch 7), each main game may get
    one branch game (`sp.pick_branches` at the config's `branch_gap`, or
    its `explore` temperature in configs from before Amendment 4): the same spec, forced through the main game's actions up
    to the branch point and then the branch option, played on by the same
    search. Branch records follow every main record and carry `branch_at`
    (the forced decision) and `branch_of` (the main game's index). The
    results keep their recorded `states` only with `keep_states`. With
    `keep_results=False` and no branches the games stream to disk a chunk
    at a time (the same dataset) and the results returned are None."""
    if not keep_results and not config.get("branches"):  # one chunk of games in memory at a time
        def games():
            for i, res in play_chunks(specs, config, evaluator, features, log=log):
                yield from records(specs[i:i + len(res)], groups[i:i + len(res)], res, config)
        return write_dataset(games(), config, parent_model, root, n_games=len(specs)), None
    results = play(specs, config, evaluator, features, log=log, keep_states=keep_states)
    games = records(specs, groups, results, config)
    if config.get("branches"):
        rng = np.random.default_rng(config.get("sample_seed", 0) + BRANCH_SEED)
        picks = sp.pick_branches(results, float(config.get("branch_gap", config.get("explore", 0.0))), rng)
        if picks:
            bspecs = [specs[g] for g, _, _ in picks]
            forced = [list(results[g]["actions"][:i]) + [a] for g, i, a in picks]
            played = play(bspecs, config, evaluator, features, forced, log=log, label="branch games")
            branch = records(bspecs, [groups[g] for g, _, _ in picks], played, config)
            for b, (g, i, _) in zip(branch, picks):
                b.update(branch_at=i, branch_of=g)
            games += branch
    return write_dataset(games, config, parent_model, root), results


def find(config, parent_model=None, root=ROOT):
    """The id of a stored dataset generated by `config` (and parent model)
    under the current rules, else None: data from a teacher that doesn't
    depend on a net is generated once and reused."""
    d = datasets_dir(root)
    if not os.path.isdir(d):
        return None
    rules = rules_version()
    for ds in sorted(os.listdir(d)):
        p = os.path.join(d, ds, "manifest.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                m = json.load(f)
            if m["config"] == config and m["parent_model"] == parent_model and m["rules_version"] == rules:
                return ds
    return None


def check_levels(datasets, config, root=ROOT):
    """The ascension level a run trains at: its datasets' (manifest key
    `ascension`, absent at 0), which must all be the config's own level.
    A mix of levels is refused unless the config says `"mixed_ascension":
    true`; then the config's level is the run's."""
    want = config.get("ascension", 0)
    levels = set()
    for d in datasets:
        try:
            levels.add(load_manifest(d, root).get("ascension", 0))
        except FileNotFoundError:
            pass
    if levels - {want} and not config.get("mixed_ascension"):
        raise ValueError(f"datasets at ascension {sorted(levels)} don't match the config's ascension {want}: "
                         "a pool never mixes levels unless the config sets mixed_ascension")
    return want


def load_manifest(ds, root=ROOT):
    with open(os.path.join(datasets_dir(root), ds, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def load_games(ds, root=ROOT):
    return list(iter_games(ds, root))


def iter_games(ds, root=ROOT):
    """The dataset's game records one at a time (a cache build holds one chunk)."""
    with gzip.open(os.path.join(datasets_dir(root), ds, "games.jsonl.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def replay(game):
    """{"states", "actions", "score"} like a recorded `sts.run` result, plus
    "values" when the game has them and "no_death" for a no-death game.
    Raises ValueError when the replayed game ends other than its recorded
    outcome (won, score, turns, HP): the engine plays it differently now.
    A game stopped at the turn limit ends still running, recorded lost."""
    c = action_text.combat_of(game)
    states, actions = [], []
    for s in game["actions"]:
        a = action_text.decode_in(c, s)
        states.append(c.clone())
        actions.append(a)
        c.step(a)
    o = game["outcome"]
    got = {"won": c.won(), "score": c.score(), "turns": c.turn(), "hp_end": c.player_hp()}
    diff = {k: (o[k], v) for k, v in got.items() if o[k] != v}
    if diff:
        raise ValueError(f"replay of {game['encounter']} seed {game['seed']} ends other than recorded"
                         f" (recorded, replayed): {diff}")
    out = {"states": states, "actions": actions, **{k: game["outcome"][k] for k in ("score", "won", "hp_start", "hp_end")}}
    if game.get("no_death"):  # switch 6's labels: no-death games have no end-of-combat heal
        out["no_death"] = True
    if "branch_at" in game:
        out["branch_at"] = game["branch_at"]
    if "luck" in game:  # per decision, docs/specs/luck-corrected-labels.md
        out["luck"] = game["luck"]
    if game.get("values") is not None:
        gen = any(c.startswith(action_text.GEN) for c in game["deck"])
        out["values"] = [_decode_values(d, st if gen else None) for d, st in zip(game["values"], states)]
    return out


def _decode_values(options, state=None):
    """One decision's recorded option values with their actions decoded;
    with `state` (a game holding generated cards, whose actions name slots
    only that combat binds), every action is taken from the state's own
    search options by its text."""
    if state is None:
        return [([decode_action(a) for a in acts], v) for acts, v in options]
    table = {encode_action(a): a for acts, _, _ in state.options(sp.LIMIT) for a in acts}
    return [([table[a] if a in table else decode_action(a) for a in acts], v) for acts, v in options]


# --- feature caches ---------------------------------------------------------

_LAYOUT_TAGS = {}


def layout_tag(mode):
    """8 hex digits of `sp.features(mode)`'s full layout, so a feature change
    that keeps the rules (no new dataset) still rebuilds the cache."""
    if mode not in _LAYOUT_TAGS:
        f = sp.features(mode)
        _LAYOUT_TAGS[mode] = _hash([f.player_names, f.monster_names, f.card_names, f.row_names, f.row_kinds, f.piles])[:8]
    return _LAYOUT_TAGS[mode]


def cache_path(ds, mode, root=ROOT, labels=None):
    tag = "" if labels is None else "-" + _hash(labels)[:8]
    return os.path.join(cache_dir(root), f"{ds}-{mode}_{sp.FORMAT}-{CACHE_VERSION}-{layout_tag(mode)}{tag}")


def examples(ds, mode, root=ROOT, cap_bytes=CACHE_CAP, labels=None, log=None):
    """The dataset's sampled states encoded with `sp.features(mode)`
    (selfplay.sample_states with `labels`, rng seeded by the config's `sample_seed`),
    from the cache or by replaying its games."""
    path = cache_path(ds, mode, root, labels)
    if os.path.isdir(path):
        os.utime(path)
        return Dataset.load(path)
    m = load_manifest(ds, root)
    if m["rules_version"] != rules_version():
        raise RulesVersionError(
            f"dataset {ds} was recorded under rules version {m['rules_version']} (engine {m['engine_commit']}), "
            f"but the engine now has rules version {rules_version()}; its games can't be replayed. "
            "Regenerate the data with the current engine.")
    if m.get("content_hash") or m.get("content_hashes"):
        try:
            ensure_content(([m["content_hash"]] if m.get("content_hash") else []) + m.get("content_hashes", []), root)
        except ContentError as e:
            raise ContentError(f"dataset {ds} holds generated content: {e}") from None
    games = iter_games(ds, root)
    rng = np.random.default_rng(m["config"].get("sample_seed", 0))
    enc = sp.features(mode)
    os.makedirs(cache_dir(root), exist_ok=True)
    out = DatasetWriter(path)
    last = None  # the last decision id written: sample_states continues from it
    from progress import Progress
    p = Progress(f"cache {ds}", m.get("n_games", 0), log)
    while chunk := list(itertools.islice(games, CHUNK)):
        extra = {} if last is None else {"decision": [last]}
        states, tg, gr = sp.sample_states([replay(g) for g in chunk], [g["group"] for g in chunk], rng, labels, extra)
        if last is not None:
            extra["decision"] = extra["decision"][1:]
        if extra.get("decision"):
            last = extra["decision"][-1]
        # each chunk written in storage form at once: the cache build holds one chunk
        part = Dataset.from_batches([enc.encode(states, heuristic=True)], tg)
        hp = {k: getattr(part, k) for k in HP_SCALARS if getattr(part, k) is not None and k not in extra}
        out.append(Dataset(**{k: getattr(part, k) for k in Dataset.FIELDS[:-1]}, group=np.asarray(gr, np.int64),
                           **hp, **extra))
        del states, part
        p.update(len(chunk))
    p.close()
    out.close()
    evict(cache_dir(root), cap_bytes, keep=path)
    return Dataset.load(path)


def pid_alive(pid):
    """Whether process `pid` runs (Windows: a process we may not open is
    taken as running)."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = ctypes.c_void_p
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ctypes.get_last_error() == 5  # access denied: it exists
    code = ctypes.c_ulong()
    ok = k32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
    k32.CloseHandle(ctypes.c_void_p(h))
    return not ok or code.value == 259  # STILL_ACTIVE


def clean_stale(folder):
    """Deletes temporary caches (`<cache>.tmp<pid>`, `exact.tmp<pid>-<n>`,
    a dataset's `stream.tmp<pid>-<n>`)
    whose process no longer runs: a crashed round's leftovers."""
    if not os.path.isdir(folder):
        return
    for n in os.listdir(folder):
        m = re.search(r"\.tmp(\d+)(?:-\d+)?$", n)
        if m and not pid_alive(int(m[1])):
            shutil.rmtree(os.path.join(folder, n), ignore_errors=True)


def _size(p):
    if os.path.isdir(p):
        return sum(os.path.getsize(os.path.join(p, n)) for n in os.listdir(p))
    return os.path.getsize(p)


def evict(folder, cap_bytes=CACHE_CAP, keep=None):
    """Deletes the least recently used caches (v7 directories, older .npz
    files) until the folder fits `cap_bytes`; `keep` is never deleted, nor
    a cache another process has open (Windows locks mapped files)."""
    caches = [os.path.join(folder, n) for n in os.listdir(folder)
              if n.endswith(".npz") or (".tmp" not in n and n != "explore" and os.path.isdir(os.path.join(folder, n)))]
    caches.sort(key=os.path.getmtime)
    total = sum(_size(p) for p in caches)
    for p in caches:
        if total <= cap_bytes:
            break
        if keep and os.path.abspath(p) == os.path.abspath(keep):
            continue
        size = _size(p)
        try:
            if os.path.isdir(p):
                # Renamed first: that fails while any file inside is mapped,
                # so a cache in use is never left half deleted. A delete that
                # stops part way leaves a `.tmp<pid>` name, which no lookup
                # takes for a cache and `clean_stale` removes.
                gone = f"{p}.tmp{os.getpid()}-0"
                os.rename(p, gone)
                shutil.rmtree(gone, ignore_errors=True)
            else:
                os.remove(p)
                try:
                    os.remove(p + ".games.npy")  # curve's sidecar
                except OSError:
                    pass
        except OSError:
            continue
        total -= size


# --- runs -------------------------------------------------------------------

class Run:
    """One immutable training run folder."""

    def __init__(self, path):
        self.path = path
        self.id = os.path.basename(path)

    @staticmethod
    def create(name, config, datasets, root=ROOT, parent=None):
        """`parent` (optional): the net a fine-tune started from, recorded in
        run.json (finetune.py: its path and sha256)."""
        level = check_levels(datasets, config, root)
        now = datetime.datetime.now().astimezone()  # with its UTC offset: Colab runs in UTC
        commit = git_commit()
        while True:
            h = _hash([config, commit, datasets, now.isoformat(), os.urandom(4).hex()])[:7]
            path = os.path.join(runs_dir(root), f"{now:%Y-%m-%d}-{name}-{h}")
            try:
                os.makedirs(path)
                break
            except FileExistsError:
                continue
        run = Run(path)
        run._write("config.json", config)
        run._write("run.json", {"commit": commit, "datasets": list(datasets), "created": now.isoformat(timespec="seconds"),
                                "rules_version": rules_version(), **({"parent": parent} if parent else {}),
                                **({"ascension": level} if level else {})})
        return run

    def _write(self, name, obj):
        with open(os.path.join(self.path, name), "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, indent=1, sort_keys=True)
            f.write("\n")

    def _read(self, name):
        p = os.path.join(self.path, name)
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    @property
    def model_path(self):
        return os.path.join(self.path, "model.pt")

    @property
    def bench_path(self):
        return os.path.join(self.path, "bench.json")

    def save_model(self, model, norm, meta):
        import stsnet
        stsnet.save(self.model_path, model, norm, meta)

    def save_curves(self, curves):
        """{"train": [loss per epoch], "val": [...]} (per round when looped)."""
        self._write("curves.json", curves)

    def save_bench(self, result):
        self._write("bench.json", result)

    def finish(self, val_mse=None, feature_format=None):
        """Appends this run's line to runs/index.csv."""
        config, info, bench = self._read("config.json"), self._read("run.json"), self._read("bench.json")
        row = {"run": self.id, "date": info["created"][:10], "commit": info["commit"][:12],
               "config": config.get("name", ""), "switches": json.dumps(config.get("switches", {}), sort_keys=True),
               "feature_format": feature_format or config.get("mode", ""),
               "bench_version": "" if bench is None else bench.get("version", ""),
               "val_mse": "" if val_mse is None else f"{val_mse:.5f}"}
        for half in ("held_out", "train"):
            m = (bench or {}).get("sets", {}).get("tight", {}).get("halves", {}).get(half, {}).get("metrics", {})
            for key, col in (("regret.contested", "regret"), ("ranking.contested", "ranking"), ("win", "win")):
                row[f"tight_{half}_{col}"] = f"{m[key][0]:.4f}" if m.get(key) else ""
        index = os.path.join(os.path.dirname(self.path), "index.csv")
        new = not os.path.exists(index)
        with open(index, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, INDEX_FIELDS, lineterminator="\n")
            if new:
                w.writeheader()
            w.writerow(row)
