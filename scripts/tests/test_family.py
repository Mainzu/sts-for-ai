"""Tests for scripts/family.py (docs/specs/session-free-reads.md). Plain
asserts; run with `python scripts/tests/test_family.py` or pytest."""
import json
import os
import random
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import family  # noqa: E402
import jobs  # noqa: E402

PY = sys.executable
WRITE = "import sys; open(sys.argv[1], 'w').write(sys.argv[2])"


class Env:
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="family-test-"))
        self.q = jobs.Queue(str(self.tmp / "jobs"))
        family.DATA = self.tmp
        for n in ("a1", "a2", "b1", "b2"):
            (self.tmp / f"{n}.json").write_text("{}", encoding="utf-8")
        (self.tmp / "parent.pt").write_text("", encoding="utf-8")
        self.out = []

    def fam(self, arms=None, then=True):
        t = self.tmp.as_posix()
        fam = {"name": "fam-test", "lane": "test", "parent": f"{t}/parent.pt",
               "arms": arms or {"x": [f"{t}/a1.json"], "y": [f"{t}/b1.json"]},
               "burst": {"threads": 4, "mem_gb": 2.5, "estimate_min": 30},
               "reads": {"a": {"cmd": [PY, "-c", WRITE, t + "/out-{config}-a.txt", "{net}", "--out",
                                       "fam-{config}-a.json"], "threads": 3, "estimate_min": 6},
                         "b": {"cmd": [PY, "-c", WRITE, t + "/out-{config}-b.txt", "{run}", "--out",
                                       "fam-{config}-b.json"], "threads": 3, "estimate_min": 6}},
               "table": {"kind": "strata", "books": ["a", "b"], "control": {"a": "ctl-a.json", "b": "ctl-b.json"},
                         "rule": {"stratum": "held-out DF", "min_se": 2.0,
                                  "keep": {"train": {"hp": -0.9, "clears": -0.04}}}},
               "_file": "configs/families/fam-test.json"}
        if then:
            fam["then"] = {"h": {"cmd": [PY, "-c", "pass"], "net": "best", "threads": 3, "estimate_min": 40}}
        return fam

    def queue(self, fam, dry=False):
        self.out = []
        return family.queue(fam, self.q, dry=dry, out=self.out.append, pin=None)

    def pending(self):
        return self.q.jobs("pending")

    def by_kind(self):
        out = {}
        for j in self.pending():
            args = family.family_args(j)
            kind = "burst" if args is None else args[0] if args[0] != "read" or "best" not in args[2] else "then"
            out.setdefault(kind, []).append(j)
        return out


def test_queue_adds_the_chain_once():
    e = Env()
    fam = e.fam()
    assert e.queue(fam) == 0
    k = e.by_kind()
    assert len(k["burst"]) == 2 and len(k["read"]) == 4 and len(k["table"]) == 1 and len(k["then"]) == 1, k.keys()
    bursts = {j["id"] for j in k["burst"]}
    assert all(len(j["if_passed"]) == 1 and j["if_passed"][0] in bursts for j in k["read"])
    assert all(NOTE_OK(j) for j in k["read"])
    table = k["table"][0]
    assert sorted(table["after"]) == sorted(j["id"] for j in k["read"])
    assert table["check"][-2:] == ["verdict", fam["_file"]]
    assert k["then"][0]["if_passed"] == [table["id"]]
    assert all(j["lane"] == "test" for j in e.pending())
    n = len(e.pending())
    assert e.queue(fam) == 0
    assert len(e.pending()) == n, e.out
    assert not any(line.startswith("add") for line in e.out)


def test_failed_burst_cancels_reads_and_table_goes_ahead():
    e = Env()
    fam = e.fam()
    e.queue(fam)
    k = e.by_kind()
    assert all(j.get("on_fail") == "cancel" for j in k["read"])
    burst = k["burst"][0]
    burst["status"] = "failed"
    e.q.move(burst, "pending", "done")
    r = jobs.Runner(e.q, 2, 14, idle=lambda: 0.0, free=lambda: 0.0, total=lambda: 16.0, clock=lambda: 1e9,
                    alive=lambda pid: False, start=None, kill=None, mem=lambda job: 0.0)
    r._decide(1e9)
    table = e.q.find(k["table"][0]["id"])
    assert table[0] == "pending" and "parked" not in table[1], table
    dead = [j for j in k["read"] if j["if_passed"] == [burst["id"]]]
    assert all(e.q.find(j["id"])[1]["status"] == "cancelled" for j in dead)
    # a burst queued again: queue adds its reads again and the table, ended ok before, runs again
    tj = e.q.find(k["table"][0]["id"])[1]
    tj["status"] = "ok"
    e.q.move(tj, "pending", "done")
    e.q.add(burst["cmd"], 4)
    e.queue(fam)
    assert len(e.by_kind()["table"]) == 1 and e.by_kind()["table"][0]["id"] != tj["id"]


def NOTE_OK(job):
    return "fam-test" in job["note"] and family.NOTE in job["note"]


def test_dry_run_adds_nothing():
    e = Env()
    assert e.queue(e.fam(), dry=True) == 0
    assert e.pending() == [] and sum(line.startswith("add") for line in e.out) == 8


def test_missing_config_adds_nothing():
    e = Env()
    fam = e.fam(arms={"x": [(e.tmp / "nope.json").as_posix()]})
    assert e.queue(fam) == 2 and e.pending() == []


def test_existing_burst_is_bound_and_parked_read_rebound():
    e = Env()
    fam = e.fam(then=False)
    t = e.tmp.as_posix()
    old = e.q.add([PY, "-u", "scripts/finetune.py", "--from", f"{t}/parent.pt", "--config", f"{t}/a1.json",
                   "--threads", "4"], 4)
    e.queue(fam)
    k = e.by_kind()
    assert len(k["burst"]) == 2 and any(j["id"] == old for j in k["burst"])
    reads_a1 = [j for j in k["read"] if family.family_args(j)[2].endswith("a1.json")]
    assert all(j["if_passed"] == [old] for j in reads_a1)
    # the owning lane parks the reads (their burst failed) and queues the burst again
    for j in reads_a1:
        j["parked"] = "test"
        e.q.update(j, "pending")
    e.q.cancel(old)
    new = e.q.add([PY, "-u", "scripts/finetune.py", "--from", f"{t}/parent.pt", "--config", f"{t}/a1.json",
                   "--threads", "4"], 4)
    e.queue(fam)
    live = [j for j in e.by_kind()["read"] if family.family_args(j)[2].endswith("a1.json")]
    assert len(live) == 2 and all(j["if_passed"] == [new] and "parked" not in j for j in live), live
    assert all(e.q.find(j["id"])[1]["status"] == "cancelled" for j in reads_a1)
    table = e.by_kind()["table"][0]
    assert sorted(table["after"]) == sorted(j["id"] for j in e.by_kind()["read"])
    assert len(e.by_kind()["burst"]) == 2


def fake_burst(e, cfg, run_id, line=True):
    log = e.tmp / f"{run_id}.log"
    (e.tmp / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (e.tmp / "runs" / run_id / "model.pt").write_text("", encoding="utf-8")
    log.write_text("epoch 1\n" + (f"run {run_id}: C:\\elsewhere\\runs\\{run_id}\\model.pt\n" if line else ""),
                   encoding="utf-8")
    jid = e.q.add([PY, "-u", "scripts/finetune.py", "--from", f"{e.tmp.as_posix()}/parent.pt", "--config", cfg,
                   "--threads", "4"], 4, log=str(log))
    state, job = e.q.find(jid)
    job["status"] = "ok"
    e.q.move(job, "pending", "done")
    return jid


def test_read_resolves_net_from_log():
    e = Env()
    fam = e.fam()
    cfg = (e.tmp / "a1.json").as_posix()
    fake_burst(e, cfg, "2026-11-07-a1-abc1234")
    assert family.read(fam, e.q, cfg, "a", out=e.out.append) == 0
    got = (e.tmp / "out-a1-a.txt").read_text(encoding="utf-8")
    assert got == (e.tmp / "runs" / "2026-11-07-a1-abc1234" / "model.pt").as_posix(), got
    assert family.read(fam, e.q, cfg, "b", out=e.out.append) == 0
    assert (e.tmp / "out-a1-b.txt").read_text(encoding="utf-8") == "2026-11-07-a1-abc1234"


def test_read_fails_without_log_line():
    e = Env()
    fam = e.fam()
    cfg = (e.tmp / "b1.json").as_posix()
    fake_burst(e, cfg, "2026-11-07-b1-abc1234", line=False)
    assert family.read(fam, e.q, cfg, "a", out=e.out.append) == 3
    assert not (e.tmp / "out-b1-a.txt").exists()
    assert family.read(fam, e.q, (e.tmp / "a1.json").as_posix(), "a", out=e.out.append) == 3  # no burst job


# ---- the table ----

def rec(i, half, cleared, hp):
    return {"i": i, "half": half, "cell": i % 7, "cleared": cleared, "floors": [{"hp_end": hp}]}


def write_book(path, recs):
    path.write_text(json.dumps({"sequences": recs}), encoding="utf-8")


def setup_table(e, df_gain, train_gain, seeds=3):
    """Control and nets on two books: half the sequences train, the rest held-out, a third of those
    with Demon Form; each net gains `df_gain` HP on DF decks and `train_gain` on train, with noise."""
    rng = random.Random(7)
    decks, base = {}, {}
    for i in range(1000):
        half = "train" if i % 2 == 0 else "held_out"
        decks[i] = ["Strike", "Demon Form"] if half == "held_out" and i % 3 == 0 else ["Strike"]
        base[i] = rec(i, half, True, 40 + rng.randint(-10, 10))
    write_book(e.tmp / "ctl-a.json", [base[i] for i in range(500)])
    write_book(e.tmp / "ctl-b.json", [base[i] for i in range(500, 1000)])
    arms = {"x": [], "y": []}
    for arm, scale in (("x", 1.0), ("y", 0.0)):
        for s in range(seeds):
            cfg = (e.tmp / f"{arm}{s}.json").as_posix()
            Path(cfg).write_text("{}", encoding="utf-8")
            run = f"2026-11-07-{arm}{s}-abc{s}"
            fake_burst(e, cfg, run)
            arms[arm].append(cfg)
            for book, rng_i in (("a", range(500)), ("b", range(500, 1000))):
                recs = []
                for i in rng_i:
                    g = df_gain * scale if "Demon Form" in decks[i] else train_gain * scale if i % 2 == 0 else 0
                    recs.append(rec(i, base[i]["half"], True, base[i]["floors"][0]["hp_end"] + g + rng.gauss(0, 1)))
                write_book(e.tmp / f"fam-{arm}{s}-{book}.json", recs)
    fam = e.fam(arms=arms)
    return fam, decks


def test_table_pass_and_fail():
    e = Env()
    fam, decks = setup_table(e, df_gain=5.0, train_gain=0.0)
    rj = e.q.add(family.family_cmd("read", fam["_file"], fam["arms"]["x"][0], "a"), 3)
    job = e.q.find(rj)[1]
    job.update(status="ok", started="2026-11-07T01:00:00+05:00", ended="2026-11-07T02:00:00+05:00")
    e.q.move(job, "pending", "done")
    out = []
    assert family.table(fam, e.q, write=True, out=out.append, decks=decks) == 0
    v = json.loads(family.results_path(fam, "json").read_text(encoding="utf-8"))
    assert v["verdict"] == "pass" and v["best"] == "x", out
    assert not v["arms"]["y"]["pass"] and len(v["arms"]["x"]["nets"]) == 3
    assert abs(v["arms"]["x"]["row"]["held-out DF"][0] - 5.0) < 0.3
    assert v["arms"]["x"]["best_seed"] in (0, 1, 2)
    assert v["arms"]["x"]["thread_h"] == 3.0 and v["arms"]["y"]["thread_h"] == 0.0
    assert family.verdict(fam) == 0
    assert (family.results_path(fam, "md")).exists()


def test_table_fails_when_train_drops():
    e = Env()
    fam, decks = setup_table(e, df_gain=5.0, train_gain=-3.0)
    assert family.table(fam, e.q, write=True, out=[].append, decks=decks) == 0
    v = json.loads(family.results_path(fam, "json").read_text(encoding="utf-8"))
    assert v["verdict"] == "fail" and v["best"] is None
    assert family.verdict(fam) == 1


def test_short_file_counts_as_missing():
    e = Env()
    fam, decks = setup_table(e, df_gain=5.0, train_gain=0.0)
    p = e.tmp / "fam-x0-b.json"
    write_book(p, json.loads(p.read_text(encoding="utf-8"))["sequences"][:100])
    family.table(fam, e.q, write=True, out=[].append, decks=decks)
    v = json.loads(family.results_path(fam, "json").read_text(encoding="utf-8"))
    assert len(v["arms"]["x"]["nets"]) == 2 and any("100 sequences" in m for m in v["arms"]["x"]["missing"])


def test_verdict_missing():
    e = Env()
    assert family.verdict(e.fam()) == 2


BURST8 = r"rerank-(2026-11-01-burst8-s\d+-\w+)-hpb0\.01"


def test_burst8_equals_step1b():
    """family's table on burst8's three nets, against the one-turn 10-29 net, equals
    cards_by_half's 'burst8 (transfer)' row (files on disk; skipped when missing)."""
    import cards_by_half as cbh
    g = Path(jobs.REPO) / "results" / "gauntlet"
    runs = sorted(m.group(1) for p in g.glob("rerank-*-hpb0.01.json") if (m := re.fullmatch(BURST8, p.stem)))
    if len(runs) < 3 or not all((g / f"rerank-{r}-hpb0.01-b500.json").exists() for r in runs):
        print("skip: burst8 files missing")
        return
    family.DATA = Path(jobs.REPO)
    fam = {"name": "burst8-check", "lane": "test", "parent": "x",
           "arms": {"burst8": [{"config": f"configs/{r}.json", "net": f"runs/{r}/model.pt"} for r in runs]},
           "reads": {"a": {"cmd": ["--out", "results/gauntlet/rerank-{run}-hpb0.01.json"], "threads": 1},
                     "b": {"cmd": ["--out", "results/gauntlet/rerank-{run}-hpb0.01-b500.json"], "threads": 1}},
           "table": {"kind": "strata", "books": ["a", "b"],
                     "control": {"a": "results/gauntlet/net1029-hpb0.01.json",
                                 "b": "results/gauntlet/net1029-hpb0.01-b500.json"},
                     "rule": {"stratum": "held-out DF", "min_se": 2.0, "keep": {}}},
           "_file": "x"}
    dk = cbh.decks()
    q = jobs.Queue(tempfile.mkdtemp(prefix="family-test-"))
    out = []
    family.table(fam, q, out=out.append, decks=dk)
    names = {p.stem for p in g.glob("*.json")}
    want = cbh.strata_row(cbh.complete_nets(g, names, cbh.STRATA_GROUPS[-1][1]),
                          cbh.load_union(g, cbh.ONE_TURN_NET), dk)
    fam_rows = None
    # the row the table computed
    for line in "\n".join(out).splitlines():
        if line.startswith("| burst8 |"):
            fam_rows = line
    assert fam_rows is not None and fam_rows.split("|")[2].strip() == "3", out
    for s in cbh.STRATA:
        assert f"{want[s][0]:+.2f} ({want[s][1]:.2f} / {want[s][2]:.2f})" in fam_rows, (s, want[s], fam_rows)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


# ---- the gen table (lane gen-adapted-column) ----

def gen_row(i, enc, hp, lost_mech, lost_ctl, lost_par, heur_mech=10, heur_ctl=10):
    res = lambda lost: [[True, hp - lost]] * 4  # noqa: E731
    return {"i": i, "floor": 1, "encounter": enc, "group": "elite", "hp": hp,
            "parent": {"one": res(lost_par), "heuristic": res(5)},
            "mods": {"M": {"one": res(lost_mech), "heuristic": res(heur_mech)},
                     "C": {"one": res(lost_ctl), "heuristic": res(heur_ctl)}}}


def setup_gen(e, cut_x):
    """A base file where the net loses 16 on mechanic M and 10 on control C
    (cost 6 beyond the heuristic's equal 10s); arm x's nets cut M's loss by
    `cut_x` (+-0.5 by seed), arm y's not at all; a third encounter is ignored."""
    encs = ["lagavulin", "three_sentries", "gremlin_nob"]
    base = [gen_row(i, encs[i % 3], 70, 16, 10, 8) for i in range(60)]
    (e.tmp / "base.json").write_text(json.dumps({"rows": base}), encoding="utf-8")
    arms = {"x": [], "y": []}
    for arm, cut in (("x", cut_x), ("y", 0.0)):
        for s in range(3):
            cfg = (e.tmp / f"{arm}{s}.json").as_posix()
            Path(cfg).write_text("{}", encoding="utf-8")
            fake_burst(e, cfg, f"2026-11-08-{arm}{s}-abc{s}")
            arms[arm].append(cfg)
            noise = (s - 1) * 0.5
            rows = [gen_row(r["i"], r["encounter"], 70, 16 - cut - noise, 10, 9) for r in base]
            (e.tmp / f"gen-{arm}{s}.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
    fam = e.fam(arms=arms, then=False)
    fam["reads"] = {"g": {"cmd": [PY, "-c", "pass", "--out", "gen-{config}.json"], "threads": 3}}
    fam["table"] = {"kind": "gen", "book": "g", "base": "base.json", "mechanic": "M", "control": "C", "seeds": 4,
                    "encounters": ["lagavulin", "three_sentries"], "rule": {"share": 0.5, "min_se": 2.0}}
    return fam


def test_gen_table_pass_and_fail():
    e = Env()
    fam = setup_gen(e, cut_x=4.0)
    out = []
    assert family.table(fam, e.q, write=True, out=out.append) == 0
    v = json.loads(family.results_path(fam, "json").read_text(encoding="utf-8"))
    assert v["verdict"] == "pass" and v["best"] == "x", out
    assert abs(v["base_cost"][0] - 6.0) < 1e-9
    x = v["arms"]["x"]
    assert abs(x["gain"] - 4.0) < 1e-9 and [round(g, 6) for g in x["per_net"]] == [3.5, 4.0, 4.5]
    assert abs(x["parent"][0] - 1.0) < 1e-9 and x["best_seed"] == 2
    assert not v["arms"]["y"]["pass"]
    e2 = Env()
    fam2 = setup_gen(e2, cut_x=2.0)  # a third of the cost: under half
    family.table(fam2, e2.q, write=True, out=[].append)
    assert json.loads(family.results_path(fam2, "json").read_text(encoding="utf-8"))["verdict"] == "fail"
    assert family.verdict(fam2) == 1


def test_gen_table_short_read_keeps_base_cost():
    """A read with too few starts is missing and leaves the base cost alone."""
    e = Env()
    fam = setup_gen(e, cut_x=4.0)
    (e.tmp / "gen-x2.json").write_text(json.dumps({"rows": []}), encoding="utf-8")
    fam["arms"] = {"x": fam["arms"]["x"]}
    family.table(fam, e.q, write=True, out=[].append)
    v = json.loads(family.results_path(fam, "json").read_text(encoding="utf-8"))
    assert v["verdict"] == "pass" and len(v["arms"]["x"]["nets"]) == 2, v
    assert any("0 starts" in m for m in v["arms"]["x"]["missing"])


# ---- packs (docs/specs/pack-adapt-pipeline.md) ----

MECHS = ["GE-AttackLoss-Damage", "GE-TurnEnd-Frail"]


def pack_file(e, base=None, arms=None):
    t = e.tmp.as_posix()
    pack = {"mechanics": MECHS, "encounters": ["gremlin_nob", "lagavulin"], "starts": 100, "seeds": 4,
            "arms": arms or {"g99": {"games": 99}, "g99-par": {"games": 99, "parents": True}},
            "target": {"mechanic": "GE-AttackLoss-Damage", "encounter": "gremlin_nob", "share": 0.5, "min_se": 2.0}}
    if base:
        pack["base"] = base
    path = e.tmp / "pack-test.json"
    path.write_text(json.dumps({"name": "pack-test", "lane": "test", "parent": f"{t}/parent.pt", "pack": pack}),
                    encoding="utf-8")
    return family.load_family(path)


def test_pack_queues_the_chain():
    e = Env()
    fam = pack_file(e)
    assert e.queue(fam) == 0, e.out
    k = e.by_kind()
    assert len(k["burst"]) == 4 and len(k["read"]) == 4 and len(k["base"]) == 1 and len(k["table"]) == 1, k.keys()
    cfgs = {}
    for j in k["burst"]:
        c = family.arg_after(j["cmd"], "--config")
        cfgs[Path(c).name] = json.loads(Path(c).read_text(encoding="utf-8"))
    assert sorted(cfgs) == ["g99-par-s1.json", "g99-par-s2.json", "g99-s1.json", "g99-s2.json"]
    assert cfgs["g99-s1.json"]["content"]["mutated"] == MECHS and cfgs["g99-s2.json"]["seed"] == 2
    assert cfgs["g99-par-s1.json"]["content"]["mutated"] == MECHS + ["parent"]
    assert cfgs["g99-s1.json"]["games"] == 99 and cfgs["g99-s1.json"]["content"]["net_settings"] == "@hpb0.01@tsl1"
    bursts = {j["id"] for j in k["burst"]}
    assert all(len(j["if_passed"]) == 1 and j["if_passed"][0] in bursts for j in k["read"])
    read_cmd = fam["reads"]["bench"]["cmd"]
    assert "--players" in read_cmd and family.arg_after(read_cmd, "--players") == "one"
    table = k["table"][0]
    assert sorted(table["after"]) == sorted([j["id"] for j in k["read"]] + [k["base"][0]["id"]])
    assert table["check"][-2:] == ["verdict", fam["_file"]]
    n = len(e.pending())
    assert e.queue(pack_file(e)) == 0 and len(e.pending()) == n, e.out
    e2 = Env()
    (e2.tmp / "zs.json").write_text("{}", encoding="utf-8")
    assert e2.queue(pack_file(e2, base="zs.json")) == 0
    assert "base" not in e2.by_kind()


def test_pack_dry_run_writes_nothing():
    e = Env()
    assert e.queue(pack_file(e), dry=True) == 0, e.out
    assert not e.pending() and not Path(family.pack_dir("pack-test")).exists()


def test_pack_config_change_refused():
    e = Env()
    assert e.queue(pack_file(e)) == 0
    n = len(e.pending())
    assert e.queue(pack_file(e, arms={"g99": {"games": 50}, "g99-par": {"games": 99, "parents": True}})) == 2
    assert len(e.pending()) == n and any("would change" in line for line in e.out)


def prow(i, enc, lost):
    """A bench row; `lost` maps cell -> (net HP lost, heuristic HP lost, net won)."""
    def res(x, won=True):
        return [[won, 70 - x]] * 4 if won else [[False, 0]] * 4
    r = {"i": i, "floor": 1, "encounter": enc, "group": "elite", "hp": 70, "parent": {}, "mods": {}}
    for cell, (net, heur, won) in lost.items():
        slot = r["parent"] if cell == "parent" else r["mods"].setdefault(cell, {})
        slot["one"] = res(net, won)
        slot["heuristic"] = res(heur)
    return r


def setup_pack(e, frail_lag=0.0, par_lose=False):
    """Zero-shot base: the net loses 16 on AttackLoss-Damage (heuristic 10),
    10 on TurnEnd-Frail and on the control (heuristic 10), 8 on the parent.
    Arm g99's nets cut AttackLoss-Damage by 6 (+-0.5 by seed) and lose
    `frail_lag` more on TurnEnd-Frail x Lagavulin; arm g99-par cuts 3 and
    keeps everything. Per-start noise +-1 gives each cell a se."""
    fam = pack_file(e, base="base.json")
    encs = ["gremlin_nob", "lagavulin"]
    base, reads = [], {}
    for i in range(240):
        d = 1 if i % 2 else -1
        base.append(prow(i, encs[i % 2], {"parent": (8 + d, 6, True), "GE-AttackLoss-Damage": (16 + d, 10, True),
                                          "GE-TurnEnd-Frail": (10 + d, 10, True), "c-hp1.25": (10 + d, 10, True)}))
    (e.tmp / "base.json").write_text(json.dumps({"rows": base}), encoding="utf-8")
    assert e.queue(fam) == 0
    for arm, cut in (("g99", 6.0), ("g99-par", 3.0)):
        for s in (1, 2):
            run = f"2026-11-08-{arm}-s{s}-abc"
            cfg = f"{family.pack_dir('pack-test')}/{arm}-s{s}.json"
            fake_burst(e, cfg, run)
            noise = (s - 1.5)
            rows = []
            for r in base:
                lag = r["encounter"] == "lagavulin"
                d = 1 if r["i"] % 2 else -1
                dd = d if r["i"] % 4 < 2 else -d  # noise uncorrelated with the base's
                frail = 10 + d + (frail_lag + dd if arm == "g99" and lag else 0)
                won_par = not (par_lose and arm == "g99" and lag and r["i"] % 20 < 2)
                rows.append(prow(r["i"], r["encounter"], {
                    "parent": (8 + d, 6, won_par), "GE-AttackLoss-Damage": (16 + d - cut - noise, 10, True),
                    "GE-TurnEnd-Frail": (frail, 10, True), "c-hp1.25": (10 + d, 10, True)}))
            Path(f"{family.pack_dir('pack-test')}/read-{run}.json").write_text(json.dumps({"rows": rows}),
                                                                                 encoding="utf-8")
    return fam


def test_pack_table_ships_best_guarded_net():
    e = Env()
    fam = setup_pack(e, frail_lag=1.5)
    out = []
    assert family.table(fam, e.q, write=True, out=out.append) == 0
    v = json.loads(family.results_path(fam, "json").read_text(encoding="utf-8"))
    assert v["verdict"] == "pass" and v["best"] == "g99", out
    ship = json.loads(family.ship_path(fam).read_text(encoding="utf-8"))
    assert ship["arm"] == "g99" and ship["run"].endswith("g99-s2-abc"), ship  # s1 cuts 5.5, s2 6.5
    tg = v["arms"]["g99"]["target"]
    assert abs(tg["gain"] - 6.0) < 1e-9 and abs(tg["cost"] - 6.0) < 1e-9 and tg["pass"], tg
    assert family.verdict(fam) == 0


def test_pack_guard_refuses_hp_and_wins():
    e = Env()
    fam = setup_pack(e, frail_lag=3.0)
    out = []
    family.table(fam, e.q, write=True, out=out.append)
    v = json.loads(family.results_path(fam, "json").read_text(encoding="utf-8"))
    g99 = [n for n in v["nets"] if n["arm"] == "g99"]
    assert all(any(c == "GE-TurnEnd-Frail x lagavulin" for c, _ in n["fails"]) for n in g99), g99
    assert v["best"] == "g99-par" and v["verdict"] == "pass"
    text = "\n".join(out)
    assert "GE-TurnEnd-Frail x lagavulin HP lost +3.00" in text, text
    e2 = Env()
    fam2 = setup_pack(e2, par_lose=True)  # g99 loses 1 Lagavulin parent fight in 10: wins -0.1
    family.table(fam2, e2.q, write=True, out=[].append)
    v2 = json.loads(family.results_path(fam2, "json").read_text(encoding="utf-8"))
    fails = [c for n in v2["nets"] if n["arm"] == "g99" for c, w in n["fails"] if w.startswith("wins")]
    assert "parent x lagavulin" in fails and v2["best"] == "g99-par", v2["nets"]


def test_pack_table_fail_keeps_earlier_ship():
    e = Env()
    fam = setup_pack(e, frail_lag=3.0)
    family.ship_path(fam).parent.mkdir(parents=True, exist_ok=True)
    family.ship_path(fam).write_text('{"net": "old"}', encoding="utf-8")
    fam["arms"] = {"g99": fam["arms"]["g99"]}
    out = []
    family.table(fam, e.q, write=True, out=out.append)
    assert json.loads(family.results_path(fam, "json").read_text(encoding="utf-8"))["verdict"] == "fail"
    assert json.loads(family.ship_path(fam).read_text(encoding="utf-8")) == {"net": "old"}
    assert "left as it was" in "\n".join(out) and family.verdict(fam) == 1


def test_pack_arm_keys_reach_config():
    """docs/specs/burst-anchor.md: arm keys other than games and parents go
    into the arm's burst configs."""
    e = Env()
    fam = pack_file(e, arms={"a003": {"games": 99, "anchor": 0.003}, "g99": {"games": 99}})
    cfgs = {Path(p).name: c for p, c in fam["_configs"].items()}
    assert cfgs["a003-s1.json"]["anchor"] == 0.003 and cfgs["a003-s2.json"]["anchor"] == 0.003
    assert "anchor" not in cfgs["g99-s1.json"] and "parents" not in cfgs["g99-s1.json"]
