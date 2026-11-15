"""A family of reads queued from one session (docs/specs/session-free-reads.md).

A family file (`configs/families/<name>.json`) names a parent net, arms of
burst configs, the reads per net, a table rule and follow-up reads. `queue`
turns it into one chain through the job queue: each burst (an existing
finetune job for the config, else a new one), each read `--if-passed` its
burst, one table job `--after` the reads with a check that passes when the
rule passes, and the follow-ups `--if-passed` the table. A read finds its
net when it starts, from its burst job's log line `run <id>: <model_path>`.

    python scripts/family.py queue <file> [--dry-run]
    python scripts/family.py read <file> <config|best|best#k> <read>
    python scripts/family.py table <file> [--write]
    python scripts/family.py verdict <file>      # exit 0 pass, 1 fail, 2 no table written

A table of kind "gen" (lane gen-adapted-column) scores bench reads of a
generated mechanic instead: the cut in its cost against a zero-shot base
file (`gen_cut`, `table_gen`).

A pack file (`configs/packs/<name>.json`, a family file with a `pack` key;
docs/specs/pack-adapt-pipeline.md) expands into a family: `queue` writes
one joint burst config per arm and seed to `results/packs/<name>/`, queues
the zero-shot bench read when its base file is missing (`family.py base`),
the bench read of each burst net and a table of kind "pack" (`table_pack`):
per mechanic x parent the cost cut and retention, a guard per net, and the
pack's net (`results/packs/<name>.json`) when one passes it.

    python scripts/family.py base <pack file>    # the zero-shot bench read

Placeholders in a read's cmd: {net} (the burst's model.pt), {run} (its run
folder name), {config} (the config's stem), {arm}. A seed in an arm is a
config path, or {"config": ..., "job": "<burst job id>"} to bind a given
job, or {"config": ..., "net": "<model path>"} for a net that exists.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "analysis"))
import jobs  # noqa: E402

CHECKOUT = HERE.parent  # this checkout (a snapshot's for a queued job): reads run here
PY = ".venv/Scripts/python.exe"
DATA = Path(jobs.REPO)  # main's data: results/, runs/ (tests point it elsewhere)
SEQUENCES = 500
NOTE = "queued by family.py; queue it again with family.py queue, not by hand"


def load_family(path):
    with open(path, encoding="utf-8") as f:
        fam = json.load(f)
    fam["_file"] = str(path).replace("\\", "/")
    return expand_pack(fam) if "pack" in fam else fam


# ---- packs (docs/specs/pack-adapt-pipeline.md) ----

PACK = {"control": "c-hp1.25", "starts": 1000, "seeds": 4, "read_settings": "@tsl1", "seeds_burst": [1, 2],
        "guard": {"hp": 2.0, "wins": 0.05, "min_se": 2.0}, "min_starts": 200}
PACK_BURST = {"net_settings": "@hpb0.01@tsl1", "skip": 1000, "val_fights": 40, "game_seed": 71, "n_val": 300,
              "pool": 10000, "player": "net", "threads": 4, "mem_gb": 2.0, "estimate_min": 3}
PACK_READ = {"threads": 3, "mem_gb": 1.5, "estimate_min": 18}
BURST_JOB_KEYS = ("threads", "mem_gb", "estimate_min")


def pack_dir(name):
    return (DATA / "results" / "packs" / name).as_posix()


def pack_config(fam, p, arm, a, seed):
    b = {k: v for k, v in {**PACK_BURST, **p.get("burst", {})}.items() if k not in BURST_JOB_KEYS}
    content = {"encounters": list(p["encounters"]),
               "mutated": list(p["mechanics"]) + (["parent"] if a.get("parents") else []),
               **{k: b.pop(k) for k in ("net_settings", "skip", "val_fights")}}
    extra = {k: v for k, v in a.items() if k not in ("games", "parents")}  # e.g. anchor (docs/specs/burst-anchor.md)
    return {"content": content, "games": a["games"], "name": f"pack-{fam['name']}-{arm}-s{seed}", "seed": seed,
            **b, **extra}


def expand_pack(fam):
    """The family a pack file stands for: arms of joint burst configs (kept in
    `_configs` until `queue` writes them), the bench read, the base read and
    a "pack" table."""
    import mutate_monsters as mm
    p = {**PACK, **fam["pack"]}
    p["guard"] = {**PACK["guard"], **fam["pack"].get("guard", {})}
    unknown = [m for m in p["mechanics"] if m not in mm.GEN]
    if unknown:
        raise SystemExit(f"family: pack {fam['name']}: unknown mechanics {unknown}")
    d = pack_dir(fam["name"])
    fam["_configs"], fam["arms"] = {}, {}
    for arm, a in p["arms"].items():
        fam["arms"][arm] = []
        for seed in p["seeds_burst"]:
            path = f"{d}/{arm}-s{seed}.json"
            fam["_configs"][path] = pack_config(fam, p, arm, a, seed)
            fam["arms"][arm].append(path)
    bj = {**PACK_BURST, **p.get("burst", {})}
    fam["burst"] = {k: bj[k] for k in BURST_JOB_KEYS}
    r = {**PACK_READ, **p.get("read", {})}
    mods = ",".join(list(p["mechanics"]) + list(mm.LADDER))
    play = ["scripts/analysis/mutate_monsters.py", "play", "--starts", str(p["starts"]), "--groups", "elite",
            "--seeds", str(p["seeds"]), "--mods", mods, "--threads", str(r["threads"])]
    fam["reads"] = {"bench": {"cmd": play + ["--players", "one", "--net", "{net}" + p["read_settings"],
                                             "--out", f"{d}/read-{{run}}.json"], **r}}
    base = p.get("base") or f"{d}/base.json"
    fam["_base"] = {"file": base, "cmd": play + ["--players", "heuristic,one", "--net",
                                                  fam["parent"] + p["read_settings"], "--out", base], **r}
    fam["table"] = {"kind": "pack", "book": "bench", "base": base, "mechanics": list(p["mechanics"]),
                    "encounters": list(p["encounters"]), "control": p["control"], "seeds": p["seeds"],
                    "min_starts": p["min_starts"], "guard": p["guard"], "target": p.get("target")}
    return fam


def write_pack_configs(fam, q, out):
    """Write a pack's burst configs; False (nothing written) when one would
    change under an existing burst job of it."""
    todo = []
    for path, cfg in fam["_configs"].items():
        text = json.dumps(cfg, indent=1, sort_keys=True) + "\n"
        f = Path(path)
        old = f.read_text(encoding="utf-8") if f.exists() else None
        if old == text:
            continue
        if old is not None and burst_job(q, fam, {"config": path}) is not None:
            out(f"family: {path} would change under its burst job; nothing added")
            return False
        todo.append((f, text))
    for f, text in todo:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    return True


def base(fam):
    """Run a pack's zero-shot bench read (its base file)."""
    cmd = [sys.executable, "-u"] + fam["_base"]["cmd"]
    print("family: " + " ".join(cmd))
    sys.stdout.flush()
    return subprocess.run(cmd, cwd=str(CHECKOUT)).returncode


def norm(p):
    return str(p).replace("\\", "/").lstrip("./") if p else p


def seeds(fam):
    """[(arm, k, seed dict)] in the family's order."""
    out = []
    for arm, lst in fam["arms"].items():
        for k, s in enumerate(lst):
            out.append((arm, k, {"config": s} if isinstance(s, str) else dict(s)))
    return out


def stem(cfg):
    return Path(cfg).stem


def arg_after(cmd, flag):
    words = [w for a in cmd for w in a.split()]
    return words[words.index(flag) + 1] if flag in words[:-1] else None


def is_burst(job, cfg, parent):
    cmd = job.get("cmd") or []
    return (any(a.endswith("finetune.py") for a in cmd) and norm(arg_after(cmd, "--config")) == norm(cfg)
            and norm(arg_after(cmd, "--from")) == norm(parent))


def burst_job(q, fam, seed):
    """The burst job of a seed: the one it names, else the newest pending,
    running or done-ok finetune job of its config from the parent."""
    if seed.get("job"):
        state, job = q.find(seed["job"])
        if state is None:
            raise SystemExit(f"family: burst job {seed['job']} is in no folder")
        job["id"] = seed["job"]
        return job
    found = [j for s in jobs.STATES for j in q.jobs(s) if is_burst(j, seed["config"], fam["parent"])
             and (s != "done" or j.get("status") == "ok")]
    return max(found, key=lambda j: j["id"]) if found else None


def family_args(job):
    """The arguments after family.py in a job's cmd, or None."""
    cmd = job.get("cmd") or []
    i = next((i for i, a in enumerate(cmd) if a.replace("\\", "/").endswith("scripts/family.py")), None)
    return None if i is None else [a.replace("\\", "/") for a in cmd[i + 1:]]


def family_cmd(*args):
    return [PY, "-u", "scripts/family.py", *args]


class Queuer:
    def __init__(self, q, fam, dry, out, pin):
        self.q, self.fam, self.dry, self.out, self.pin = q, fam, dry, out, pin
        self.n = 0
        self.added = False  # a read was added this run: the table runs again

    def existing(self, args):
        """Jobs whose family.py args equal `args`: (state, job), newest first."""
        found = [(s, j) for s in jobs.STATES for j in self.q.jobs(s) if family_args(j) == args]
        return sorted(found, key=lambda x: x[1]["id"], reverse=True)

    def ensure(self, args, threads, mem_gb, estimate_min, after=(), if_passed=(), check=None, label="",
               on_fail="park", again=False):
        """Bind or add the job running family.py `args`; its id. `again`: a job
        that ended ok runs again (the table, once a read was added)."""
        for state, j in self.existing(args):
            if state == "running" or (state == "done" and j.get("status") == "ok" and not again):
                self.out(f"skip {j['id']} ({state}) {label}")
                return j["id"]
            if state == "pending" and not j.get("parked"):
                want_a, want_p = sorted(after), sorted(if_passed)
                if sorted(j.get("after", [])) == want_a and sorted(j.get("if_passed", [])) == want_p:
                    self.out(f"skip {j['id']} (pending) {label}")
                else:
                    if not self.dry:
                        self.q.set(j["id"], after=list(after), if_passed=list(if_passed))
                    self.out(f"re-bind {j['id']} after={list(after)} if_passed={list(if_passed)} {label}")
                return j["id"]
            if state == "pending":  # parked: bound to a failed or parked burst
                if not self.dry:
                    self.q.cancel(j["id"])
                self.out(f"cancel {j['id']} (parked: {j['parked']}), add again {label}")
            break
        self.added = True
        return self.add(family_cmd(*args), threads, mem_gb, estimate_min, after, if_passed, check, label, on_fail)

    def add(self, cmd, threads, mem_gb, estimate_min, after=(), if_passed=(), check=None, label="", on_fail="park"):
        if self.dry:
            self.n += 1
            jid = f"<new {self.n}>"
        else:
            jid = self.q.add(cmd, threads, mem_gb=mem_gb, estimate_min=estimate_min, lane=self.fam["lane"],
                             after=[a for a in after], if_passed=[p for p in if_passed], check=check, on_fail=on_fail,
                             note=f"family {self.fam['name']} ({self.fam['_file']}): {label}; {NOTE}", pin=self.pin)
        cond = (f" after={list(after)}" if after else "") + (f" if_passed={list(if_passed)}" if if_passed else "")
        self.out(f"add {jid} {label}{cond}{' check' if check else ''}")
        return jid


def queue(fam, q, dry=False, out=print, pin="HEAD"):
    if "_configs" in fam and not dry and not write_pack_configs(fam, q, out):
        return 2
    planned = {norm(c) for c in fam.get("_configs", {})} if dry else set()
    missing = [s["config"] for _, _, s in seeds(fam) if not s.get("net") and not os.path.exists(s["config"])
               and norm(s["config"]) not in planned]
    if not os.path.exists(fam["parent"]) and not (DATA / fam["parent"]).exists() and not all(s.get("net") for _, _, s in seeds(fam)):
        missing.append(fam["parent"])
    if missing:
        out(f"family: missing {', '.join(missing)}; nothing added")
        return 2
    qr = Queuer(q, fam, dry, out, pin)
    b = fam.get("burst", {})
    read_ids = []
    for arm, k, s in seeds(fam):
        burst = None
        if not s.get("net"):
            j = burst_job(q, fam, s)
            if j is not None:
                burst = j["id"]
                out(f"bind {burst} burst {arm} {stem(s['config'])}")
            else:
                cmd = [PY, "-u", "scripts/finetune.py", "--from", fam["parent"], "--config", s["config"],
                       "--threads", str(b.get("threads", 4))]
                burst = qr.add(cmd, b.get("threads", 4), b.get("mem_gb", 2.5), b.get("estimate_min"),
                               label=f"burst {arm} {stem(s['config'])}")
        for name, r in fam["reads"].items():
            read_ids.append(qr.ensure(["read", fam["_file"], s["config"], name], r["threads"], r.get("mem_gb", 1.5),
                                      r.get("estimate_min"), if_passed=[burst] if burst else [],
                                      label=f"read {name} {arm} {stem(s['config'])}", on_fail="cancel"))
    if "_base" in fam and not (DATA / fam["_base"]["file"]).exists():
        bs = fam["_base"]
        read_ids.append(qr.ensure(["base", fam["_file"]], bs["threads"], bs["mem_gb"], bs.get("estimate_min"),
                                  label="base (zero-shot bench read)", on_fail="cancel"))
    t = fam.get("table_job", {})
    table = qr.ensure(["table", fam["_file"], "--write"], t.get("threads", 1), t.get("mem_gb", 1.0),
                      t.get("estimate_min", 2), after=read_ids,
                      check=[PY, "scripts/family.py", "verdict", fam["_file"]], label="table", again=qr.added)
    width = max(len(v) for v in fam["arms"].values())
    for name, r in fam.get("then", {}).items():
        which = ["best"] if r.get("net", "best") == "best" else [f"best#{k}" for k in range(width)]
        for w in which:
            qr.ensure(["read", fam["_file"], w, name], r["threads"], r.get("mem_gb", 1.5), r.get("estimate_min"),
                      if_passed=[table], label=f"then {name} {w}")
    return 0


# ---- resolving a seed's net ----

def run_line(log):
    """(run id, model path) from a finetune log's last `run <id>: <path>` line, or None."""
    try:
        text = Path(log).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    hits = re.findall(r"^run (\S+): (.+?)\s*$", text, re.M)
    return hits[-1] if hits else None


def resolve(q, fam, seed):
    """(model path, run name) of a seed's net, or raise LookupError."""
    if seed.get("net"):
        return seed["net"], Path(seed["net"]).parent.name
    j = burst_job(q, fam, seed)
    if j is None:
        raise LookupError(f"no burst job for {seed['config']}")
    hit = run_line(j.get("log", ""))
    if hit is None:
        raise LookupError(f"burst {j['id']}: no 'run <id>: <path>' line in {j.get('log')}")
    run_id, path = hit
    main = DATA / "runs" / run_id / "model.pt"  # the snapshot's runs/ is a junction to main's
    for p in (main, Path(path)):
        if p.exists():
            return str(p).replace("\\", "/"), run_id
    raise LookupError(f"burst {j['id']}: model {path} is missing")


def fill(cmd, subs):
    return [a.format(**subs) for a in cmd]


def read_out(fam, read, subs):
    cmd = fill(fam["reads"][read]["cmd"] if read in fam["reads"] else fam["then"][read]["cmd"], subs)
    return arg_after(cmd, "--out")


def subs_for(q, fam, arm, seed):
    net, run = resolve(q, fam, seed)
    return {"net": net, "run": run, "config": stem(seed["config"]), "arm": arm}


def results_path(fam, ext):
    return DATA / "results" / "families" / f"{fam['name']}.{ext}"


def read(fam, q, which, name, out=print):
    if which.startswith("best"):
        try:
            v = json.loads(results_path(fam, "json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out("family: no table written; run family.py table --write first")
            return 3
        if not v.get("best"):
            out("family: the table names no best arm")
            return 3
        arm = v["best"]
        arm_seeds = [s for a, _, s in seeds(fam) if a == arm]
        if which == "best":
            seed = arm_seeds[v["arms"][arm]["best_seed"]]
        else:
            k = int(which.split("#")[1])
            if k >= len(arm_seeds):
                out(f"family: arm {arm} has no seed {k}; nothing to read")
                return 0
            seed = arm_seeds[k]
    else:
        hit = [(a, s) for a, _, s in seeds(fam) if norm(s["config"]) == norm(which)]
        if not hit:
            out(f"family: {which} is no seed of {fam['name']}")
            return 3
        arm, seed = hit[0]
    try:
        subs = subs_for(q, fam, arm, seed)
    except LookupError as err:
        out(f"family: {err}")
        return 3
    r = fam["reads"].get(name) or fam.get("then", {}).get(name)
    cmd = fill(r["cmd"], subs)
    if cmd[0].endswith(".py"):
        cmd = [sys.executable, "-u"] + cmd
    out("family: " + " ".join(cmd))
    sys.stdout.flush()
    return subprocess.run(cmd, cwd=str(CHECKOUT)).returncode


# ---- the table ----

def iso_ts(s):
    return datetime.fromisoformat(s).timestamp()


def thread_h(job):
    try:
        return job["threads"] * (iso_ts(job["ended"]) - iso_ts(job["started"])) / 3600
    except (KeyError, TypeError, ValueError):
        return 0.0


def job_for_out(q, out_path):
    """The newest done job whose cmd writes `out_path` (--out)."""
    found = [j for j in q.jobs("done") if norm(arg_after(j.get("cmd") or [], "--out")) == norm(out_path)]
    return max(found, key=lambda j: j["id"]) if found else None


def read_job(q, fam, cfg, name):
    """The newest done family read job of a seed's read."""
    want = ["read", fam["_file"], cfg.replace("\\", "/"), name]
    found = [j for j in q.jobs("done") if family_args(j) == want]
    return max(found, key=lambda j: j["id"]) if found else None


def load_seqs(path):
    return {r["i"]: r for r in json.loads(Path(path).read_text(encoding="utf-8"))["sequences"]}


def gen_cut(base, burst, t):
    """A burst's read of a generated mechanic (`mutate_monsters.py play`,
    player `one`) against the zero-shot base file on the starts of both on
    `t["encounters"]`, the base cut to its first `t["seeds"]` seeds (they
    pair): per start, the cut in the net's HP lost on the mechanic beyond
    the cut on its ladder control, (a - b)(mechanic) - (a - b)(control)
    (the heuristic cancels), and the parent's change b - a (retention).
    `control` "parent" uses the start's parent fight (the wide rows' cost).
    Returns (cut per start, parent change per start, base cost (mean, se))."""
    import mutate_monsters as mm
    k, m, c = t["seeds"], t["mechanic"], t["control"]
    lost = lambda res, r: mm.outcome(res[:k], r["hp"])[1]  # noqa: E731
    col = lambda r, x: r["parent"] if x == "parent" else r["mods"].get(x, {})  # noqa: E731
    a = {(r["i"], r["floor"]): r for r in base["rows"]}
    pairs = [(a[(r["i"], r["floor"])], r) for r in burst["rows"] if r["encounter"] in t["encounters"]
             and (r["i"], r["floor"]) in a and "one" in r["parent"] and all("one" in col(r, x) for x in (m, c))]
    cut = [(lost(col(ra, m)["one"], ra) - lost(col(rb, m)["one"], rb))
           - (lost(col(ra, c)["one"], ra) - lost(col(rb, c)["one"], rb)) for ra, rb in pairs]
    par = [lost(rb["parent"]["one"], rb) - lost(ra["parent"]["one"], ra) for ra, rb in pairs]
    gap = lambda r, x: lost(col(r, x)["one"], r) - lost(col(r, x)["heuristic"], r)  # noqa: E731
    cost = [gap(ra, m) - gap(ra, c) for ra, _ in pairs]
    return cut, par, mean_se(cost)


def mean_se(xs):
    n = len(xs)
    if n == 0:
        return (math.nan, math.nan)
    mu = sum(xs) / n
    return (mu, math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1) / n) if n > 1 else math.nan)


def table_gen(fam, q, write=False, out=print):
    """The table of a family of bursts on a generated mechanic (lane
    gen-adapted-column, docs/specs/gen-adapted-burst.md): per arm, the mean
    over its nets of the cut in the mechanic's cost (`gen_cut`), se over
    starts and over nets; an arm passes when it has two nets or more and
    its cut is at least `rule.share` of the zero-shot cost and `rule.min_se`
    se over nets. The parent change is reported, not gated."""
    t, rule = fam["table"], fam["table"]["rule"]
    base = json.loads((DATA / t["base"]).read_text(encoding="utf-8"))
    arms, best, base_cost = {}, None, None
    for arm in fam["arms"]:
        cuts, pars, names, ks, missing, job_ids, th = [], [], [], [], [], [], 0.0
        for a, k, s in seeds(fam):
            if a != arm:
                continue
            try:
                subs = subs_for(q, fam, arm, s)
                bj = None if s.get("net") else burst_job(q, fam, s)
            except LookupError as err:
                missing.append(f"{stem(s['config'])}: {err}")
                continue
            if bj is not None:
                job_ids.append(bj["id"])
                th += thread_h(bj)
            p = read_out(fam, t["book"], subs)
            rj = read_job(q, fam, s["config"], t["book"]) or job_for_out(q, p)
            if rj is not None:
                job_ids.append(rj["id"])
                th += thread_h(rj)
            f = DATA / p
            if not f.exists():
                missing.append(f"{p} (no read)")
                continue
            cut, par, cost = gen_cut(base, json.loads(f.read_text(encoding="utf-8")), t)
            if len(cut) < t.get("min_starts", 1):
                missing.append(f"{p} ({len(cut)} starts)")
                continue
            base_cost = cost
            cuts.append(cut)
            pars.append(par)
            names.append(subs["run"])
            ks.append(k)
        per_net = [sum(c) / len(c) for c in cuts]
        if per_net:
            gain, se_nets = mean_se(per_net)
            se_seq = math.sqrt(sum(mean_se(c)[1] ** 2 for c in cuts)) / len(cuts)
            parent = mean_se([sum(x) / len(x) for x in pars])
            passed = (len(cuts) >= 2 and not math.isnan(se_nets) and gain >= rule["share"] * base_cost[0]
                      and gain >= rule["min_se"] * se_nets)
            best_seed = ks[max(range(len(cuts)), key=lambda i: per_net[i])]
        else:
            gain = se_nets = se_seq = parent = best_seed = None
            passed = False
        arms[arm] = {"nets": names, "missing": missing, "pass": passed, "gain": gain, "se_nets": se_nets,
                     "se_seq": se_seq, "per_net": per_net, "parent": parent, "best_seed": best_seed,
                     "jobs": job_ids, "thread_h": round(th, 2)}
        if passed and (best is None or gain > arms[best]["gain"]):
            best = arm
    verdict = "pass" if best else "fail"
    bc = f"{base_cost[0]:+.2f} ({base_cost[1]:.2f})" if base_cost else "-"
    lines = [f"### Family {fam['name']}: cut in {t['mechanic']}'s cost on {', '.join(t['encounters'])} "
             f"(net HP lost per elite fight beyond {t['control']}; zero-shot cost {bc})\n",
             "| arm | nets | cut (se starts / se nets) | share of cost | per net | parent HP lost change | pass | thread-h |",
             "|---|---|---|---|---|---|---|---|"]
    for arm, v in arms.items():
        if v["gain"] is None:
            lines.append(f"| {arm} | 0 | missing | | | | no | {v['thread_h']:.1f} |")
            continue
        share = v["gain"] / base_cost[0] if base_cost[0] else math.nan
        se_n = "-" if math.isnan(v["se_nets"]) else f"{v['se_nets']:.2f}"
        lines.append(f"| {arm} | {len(v['nets'])} | {v['gain']:+.2f} ({v['se_seq']:.2f} / {se_n}) | {share:.2f} | "
                     f"{', '.join(f'{x:+.2f}' for x in v['per_net'])} | {v['parent'][0]:+.2f} | "
                     f"{'yes' if v['pass'] else 'no'} | {v['thread_h']:.1f} |")
    lines.append(f"\nrule: cut >= {rule['share']} x the zero-shot cost and >= {rule['min_se']} se over nets, two nets "
                 f"or more; verdict: **{verdict}**" + (f", best {best}" if best else ""))
    for arm, v in arms.items():
        lines.append(f"- {arm}: jobs {', '.join(v['jobs']) or 'none'}" + (f"; missing: {'; '.join(v['missing'])}"
                                                                         if v["missing"] else ""))
    text = "\n".join(lines)
    out(text)
    if write:
        p = results_path(fam, "json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"name": fam["name"], "family": fam["_file"], "at": jobs.now_iso(), "arms": arms,
                                 "base_cost": base_cost, "verdict": verdict, "best": best}, indent=1), encoding="utf-8")
        results_path(fam, "md").write_text(text + "\n", encoding="utf-8")
    return 0


def pack_cells(base, burst, t):
    """Per cell of a pack's table, (mechanic or "parent", encounter or
    "all"), per start paired with the zero-shot base on its first
    `t["seeds"]` seeds: {"hp": burst minus zero-shot HP lost, "wins": the
    same in wins, and for a mechanic "cut" (`gen_cut`'s formula) and "cost"
    (zero-shot, net minus heuristic beyond the control)}, keyed by start."""
    import mutate_monsters as mm
    k, c = t["seeds"], t["control"]
    res = lambda r, m, pl: r["parent"][pl] if m == "parent" else r["mods"][m][pl]  # noqa: E731
    oc = lambda r, m, pl: mm.outcome(res(r, m, pl)[:k], r["hp"])  # noqa: E731
    cells = {}
    a = {(r["i"], r["floor"]): r for r in base["rows"]}
    need = list(t["mechanics"]) + [c]
    for rb in burst["rows"]:
        ra = a.get((rb["i"], rb["floor"]))
        if (rb["encounter"] not in t["encounters"] or ra is None or "one" not in rb["parent"]
                or not all("one" in rb["mods"].get(m, {}) for m in need)
                or not all(pl in ra["parent"] and all(pl in ra["mods"].get(m, {}) for m in need)
                           for pl in ("one", "heuristic"))):
            continue
        key = (rb["i"], rb["floor"])
        ctl_a, ctl_b, ctl_h = oc(ra, c, "one")[1], oc(rb, c, "one")[1], oc(ra, c, "heuristic")[1]
        for m in ["parent"] + list(t["mechanics"]):
            (wa, la), (wb, lb) = oc(ra, m, "one"), oc(rb, m, "one")
            v = {"hp": lb - la, "wins": wb - wa}
            if m != "parent":
                v["cut"] = (la - lb) - (ctl_a - ctl_b)
                v["cost"] = (la - oc(ra, m, "heuristic")[1]) - (ctl_a - ctl_h)
                v["win_a"], v["win_h"] = wa, oc(ra, m, "heuristic")[0]
            for enc in (rb["encounter"], "all") if m == "parent" else (rb["encounter"],):
                cells.setdefault((m, enc), {})[key] = v
    return cells


def cell_stats(per_start):
    """{field: (mean, se)} over the starts of one cell."""
    vals = list(per_start.values())
    return {f: mean_se([v[f] for v in vals]) for f in vals[0]} if vals else {}


def guard_fails(stats, g):
    """The cells (name, why) where a net loses `g["hp"]` HP or `g["wins"]`
    wins or more at `g["min_se"]` se against the zero-shot net."""
    bad = []
    for (m, enc), st in stats.items():
        hp, w = st["hp"], st["wins"]
        if hp[0] >= g["hp"] and hp[0] >= g["min_se"] * hp[1]:
            bad.append((f"{m} x {enc}", f"HP lost {hp[0]:+.2f} ({hp[1]:.2f})"))
        if -w[0] >= g["wins"] and -w[0] >= g["min_se"] * w[1]:
            bad.append((f"{m} x {enc}", f"wins {w[0]:+.3f} ({w[1]:.3f})"))
    return bad


def ship_path(fam):
    return DATA / "results" / "packs" / f"{fam['name']}.json"


def table_pack(fam, q, write=False, out=print):
    """A pack's table (docs/specs/pack-adapt-pipeline.md): the zero-shot cost
    per mechanic x parent, per arm the burst nets' cut and retention pooled
    over nets per start, the guard per net and the ship verdict; the pack's
    net is the guard-passing net with the largest mean cut over the pack's
    cells."""
    t, g = fam["table"], fam["table"]["guard"]
    bf = DATA / t["base"]
    if not bf.exists():
        out(f"family: base file {t['base']} is missing; no table")
        return 3
    base = json.loads(bf.read_text(encoding="utf-8"))
    arms, nets_all, zero = {}, [], None
    for arm in fam["arms"]:
        nets, missing, job_ids, th = [], [], [], 0.0
        for a, k, s in seeds(fam):
            if a != arm:
                continue
            try:
                subs = subs_for(q, fam, arm, s)
                bj = None if s.get("net") else burst_job(q, fam, s)
            except LookupError as err:
                missing.append(f"{stem(s['config'])}: {err}")
                continue
            if bj is not None:
                job_ids.append(bj["id"])
                th += thread_h(bj)
            p = read_out(fam, t["book"], subs)
            rj = read_job(q, fam, s["config"], t["book"]) or job_for_out(q, p)
            if rj is not None:
                job_ids.append(rj["id"])
                th += thread_h(rj)
            f = DATA / p
            if not f.exists():
                missing.append(f"{p} (no read)")
                continue
            cells = pack_cells(base, json.loads(f.read_text(encoding="utf-8")), t)
            n = len(cells.get(("parent", "all"), {}))
            if n < t.get("min_starts", 1):
                missing.append(f"{p} ({n} starts)")
                continue
            stats = {c: cell_stats(v) for c, v in cells.items()}
            mech = [st["cut"][0] for (m, _), st in stats.items() if m != "parent"]
            net = {"arm": arm, "run": subs["run"], "path": subs["net"], "seed": k, "cells": cells, "stats": stats,
                   "fails": guard_fails(stats, g), "mean_cut": sum(mech) / len(mech) if mech else math.nan}
            nets.append(net)
            nets_all.append(net)
            zero = cells
        pooled = {}
        if nets:
            for c in nets[0]["cells"]:
                common = set.intersection(*(set(n["cells"].get(c, {})) for n in nets))
                pooled[c] = cell_stats({key: {f: sum(n["cells"][c][key][f] for n in nets) / len(nets)
                                              for f in nets[0]["cells"][c][key]} for key in common})
        tgt = None
        if t.get("target") and nets:
            tg = t["target"]
            c = (tg["mechanic"], tg["encounter"])
            per = [n["stats"][c]["cut"][0] for n in nets if c in n["stats"]]
            gain, se_n = mean_se(per)
            cost = pooled[c]["cost"][0] if c in pooled else math.nan
            tgt = {"cell": f"{c[0]} x {c[1]}", "gain": gain, "se_nets": se_n, "cost": cost, "per_net": per,
                   "pass": len(per) >= 2 and not math.isnan(se_n) and gain >= tg["share"] * cost
                   and gain >= tg["min_se"] * se_n}
        arms[arm] = {"nets": [n["run"] for n in nets], "missing": missing, "pooled": pooled, "target": tgt,
                     "jobs": job_ids, "thread_h": round(th, 2)}
    ok = [n for n in nets_all if not n["fails"]]
    ship = max(ok, key=lambda n: n["mean_cut"]) if ok else None
    verdict = "pass" if ship else "fail"
    lines = [f"### Pack {fam['name']}: joint bursts on {len(t['mechanics'])} mechanics x "
             f"{', '.join(t['encounters'])} against the zero-shot net (HP lost per elite fight, control "
             f"{t['control']}, {t['seeds']} seeds, mean (se over starts))\n"]
    if zero is not None:
        zs = {c: cell_stats(v) for c, v in zero.items()}
        lines += ["Zero-shot cost (net minus heuristic beyond the control), and wins net / heuristic:\n",
                  "| mechanic | " + " | ".join(t["encounters"]) + " |", "|---|" + "---|" * len(t["encounters"])]
        for m in t["mechanics"]:
            row = []
            for e in t["encounters"]:
                st = zs.get((m, e))
                row.append(f"{st['cost'][0]:+.2f} ({st['cost'][1]:.2f}), {st['win_a'][0]:.3f} / {st['win_h'][0]:.3f}"
                           if st else "-")
            lines.append(f"| {m} | " + " | ".join(row) + " |")
    for arm, v in arms.items():
        lines += [f"\nArm {arm} ({len(v['nets'])} nets, pooled per start; {v['thread_h']:.1f} thread-h): "
                  "delta HP lost, delta wins, cut in cost\n",
                  "| cell | " + " | ".join(t["encounters"]) + " |", "|---|" + "---|" * len(t["encounters"])]
        for m in ["parent"] + list(t["mechanics"]):
            row = []
            for e in t["encounters"]:
                st = v["pooled"].get((m, e))
                if not st:
                    row.append("-")
                    continue
                cell = f"{st['hp'][0]:+.2f} ({st['hp'][1]:.2f}), {st['wins'][0]:+.3f}"
                row.append(cell + (f", cut {st['cut'][0]:+.2f}" if "cut" in st else ""))
            lines.append(f"| {m} | " + " | ".join(row) + " |")
        st = v["pooled"].get(("parent", "all"))
        if st:
            lines.append(f"\nparent, all encounters: HP lost {st['hp'][0]:+.2f} ({st['hp'][1]:.2f}), "
                         f"wins {st['wins'][0]:+.3f} ({st['wins'][1]:.3f})")
        if v["target"]:
            tg = v["target"]
            se_n = "-" if math.isnan(tg["se_nets"]) else f"{tg['se_nets']:.2f}"
            lines.append(f"target {tg['cell']}: cut {tg['gain']:+.2f} (se over nets {se_n}) of zero-shot cost "
                         f"{tg['cost']:+.2f}, per net {', '.join(f'{x:+.2f}' for x in tg['per_net'])}: "
                         f"{'pass' if tg['pass'] else 'fail'}")
        lines.append(f"jobs {', '.join(v['jobs']) or 'none'}" + (f"; missing: {'; '.join(v['missing'])}"
                                                                if v["missing"] else ""))
    lines.append(f"\nGuard per net (fails at {g['hp']} HP or {g['wins']} wins lost at {g['min_se']} se, any "
                 "mechanic or parent x encounter, or the parent over all):\n")
    for n in nets_all:
        lines.append(f"- {n['arm']} {n['run']}: mean cut {n['mean_cut']:+.2f}; "
                     + ("passes" if not n["fails"] else "fails: " + "; ".join(f"{c} {w}" for c, w in n["fails"])))
    lines.append(f"\nverdict: **{verdict}**" + (f", the pack's net: {ship['path']} ({ship['arm']})" if ship else
                                                ", no net ships (the zero-shot net stays for the pack)"))
    if write and not ship and ship_path(fam).exists():
        lines.append(f"(an earlier {ship_path(fam).as_posix()} is left as it was)")
    text = "\n".join(lines)
    out(text)
    if write:
        p = results_path(fam, "json")
        p.parent.mkdir(parents=True, exist_ok=True)
        dump = lambda st: {f"{m} x {e}": v for (m, e), v in st.items()}  # noqa: E731
        p.write_text(json.dumps({
            "name": fam["name"], "family": fam["_file"], "at": jobs.now_iso(), "verdict": verdict,
            "best": ship["arm"] if ship else None, "ship": ship["path"] if ship else None,
            "arms": {a: {**{k: x for k, x in v.items() if k != "pooled"}, "pooled": dump(v["pooled"])}
                     for a, v in arms.items()},
            "nets": [{k: (dump(x) if k == "stats" else x) for k, x in n.items() if k != "cells"} for n in nets_all],
        }, indent=1), encoding="utf-8")
        results_path(fam, "md").write_text(text + "\n", encoding="utf-8")
        if ship:
            sp = ship_path(fam)
            sp.parent.mkdir(parents=True, exist_ok=True)
            sp.write_text(json.dumps({"pack": fam["name"], "net": ship["path"], "arm": ship["arm"],
                                      "run": ship["run"], "table": results_path(fam, "md").as_posix(),
                                      "at": jobs.now_iso()}, indent=1), encoding="utf-8")
    return 0


def table(fam, q, write=False, out=print, decks=None):
    if fam["table"].get("kind") == "gen":
        return table_gen(fam, q, write, out)
    if fam["table"].get("kind") == "pack":
        return table_pack(fam, q, write, out)
    import cards_by_half as cbh
    t = fam["table"]
    root = DATA
    dk = decks if decks is not None else cbh.decks()
    ref = {}
    for b in t["books"]:
        ref.update(load_seqs(root / t["control"][b]))
    rule = t["rule"]
    arms, best = {}, None
    for arm in fam["arms"]:
        nets, names, ks, missing, job_ids, th = [], [], [], [], [], 0.0
        for a, k, s in seeds(fam):
            if a != arm:
                continue
            try:
                subs = subs_for(q, fam, arm, s)
                bj = None if s.get("net") else burst_job(q, fam, s)
            except LookupError as err:
                missing.append(f"{stem(s['config'])}: {err}")
                continue
            if bj is not None:
                job_ids.append(bj["id"])
                th += thread_h(bj)
            recs, ok = {}, True
            for b in t["books"]:
                p = read_out(fam, b, subs)
                f = root / p
                rows = load_seqs(f) if f.exists() else {}
                rj = read_job(q, fam, s["config"], b) or job_for_out(q, p)
                if rj is not None:
                    job_ids.append(rj["id"])
                    th += thread_h(rj)
                if len(rows) < SEQUENCES:
                    missing.append(f"{p} ({len(rows)} sequences)")
                    ok = False
                recs.update(rows)
            if ok:
                nets.append(recs)
                names.append(subs["run"])
                ks.append(k)
        row = cbh.strata_row(nets, ref, dk) if nets else None
        st = rule["stratum"]
        if row:
            gain, se_nets = row[st][0], row[st][2]
            keep_ok = all(row[ks][0] >= f.get("hp", -math.inf) and row[ks][3] >= f.get("clears", -math.inf)
                          for ks, f in rule.get("keep", {}).items())
            passed = (len(nets) >= 2 and not math.isnan(se_nets) and gain > 0 and gain >= rule["min_se"] * se_nets
                      and keep_ok)
            per_net = [cbh.strata_row([n], ref, dk)[st][0] for n in nets]
            best_seed = ks[max(range(len(nets)), key=lambda i: per_net[i])]  # index in the arm's seed list
        else:
            gain, se_nets, passed, per_net, best_seed = None, None, False, [], None
        arms[arm] = {"nets": names, "row": row, "missing": missing, "pass": passed, "gain": gain,
                     "se_nets": se_nets, "per_net": per_net, "best_seed": best_seed, "jobs": job_ids,
                     "thread_h": round(th, 2)}
        if passed and (best is None or gain > arms[best]["gain"]):
            best = arm
    verdict = "pass" if best else "fail"
    lines = [f"### Family {fam['name']}: paired edge over the control by stratum (se over sequences / nets)\n",
             "| arm | nets | " + " | ".join(f"{s}: HP, clears" for s in cbh.STRATA) + " | pass | thread-h |",
             "|---|---|" + "---|" * len(cbh.STRATA) + "---|---|"]
    for arm, v in arms.items():
        r = v["row"]
        cells = [f"{r[s][0]:+.2f} ({r[s][1]:.2f} / {r[s][2]:.2f}), {r[s][3]:+.3f} ({r[s][4]:.3f} / {r[s][5]:.3f})"
                 if r else "missing" for s in cbh.STRATA]
        lines.append(f"| {arm} | {len(v['nets'])} | " + " | ".join(cells) + f" | {'yes' if v['pass'] else 'no'} | "
                     f"{v['thread_h']:.1f} |")
    lines.append(f"\nrule: {rule['stratum']} gain >= {rule['min_se']} se over nets, keep "
                 + ", ".join(f"{k} HP >= {f.get('hp')} and clears >= {f.get('clears')}" for k, f in
                             rule.get("keep", {}).items()) + f"; verdict: **{verdict}**" + (f", best {best}" if best else ""))
    for arm, v in arms.items():
        lines.append(f"- {arm}: jobs {', '.join(v['jobs']) or 'none'}" + (f"; missing: {'; '.join(v['missing'])}"
                                                                         if v["missing"] else ""))
    text = "\n".join(lines)
    out(text)
    if write:
        p = results_path(fam, "json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"name": fam["name"], "family": fam["_file"], "at": jobs.now_iso(), "arms": arms,
                                 "verdict": verdict, "best": best}, indent=1), encoding="utf-8")
        results_path(fam, "md").write_text(text + "\n", encoding="utf-8")
    return 0


def verdict(fam):
    try:
        v = json.loads(results_path(fam, "json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("family: no table written")
        return 2
    print(f"family {fam['name']}: {v['verdict']}" + (f" (best {v['best']})" if v.get("best") else ""))
    return 0 if v["verdict"] == "pass" else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="what", required=True)
    a = sub.add_parser("queue")
    a.add_argument("file")
    a.add_argument("--dry-run", action="store_true")
    a = sub.add_parser("read")
    a.add_argument("file")
    a.add_argument("which")
    a.add_argument("read")
    a = sub.add_parser("table")
    a.add_argument("file")
    a.add_argument("--write", action="store_true")
    a = sub.add_parser("verdict")
    a.add_argument("file")
    a = sub.add_parser("base")
    a.add_argument("file")
    args = ap.parse_args(argv)
    fam = load_family(args.file)
    q = jobs.Queue(jobs.ROOT, here=jobs.HERE)
    if args.what == "queue":
        return queue(fam, q, args.dry_run)
    if args.what == "read":
        return read(fam, q, args.which, args.read)
    if args.what == "table":
        return table(fam, q, args.write)
    if args.what == "base":
        return base(fam)
    return verdict(fam)


if __name__ == "__main__":
    sys.exit(main())
