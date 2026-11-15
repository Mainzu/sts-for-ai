//! The solved-state database: WAL concurrency, persistence across
//! processes, rules versions, hash collisions, snapshot reads, eviction,
//! trivial rows (Amendment 1).

use std::collections::BTreeSet;
use std::path::PathBuf;
use std::process::Command;

use rusqlite::Connection;
use solvedb::db::{is_trivial, Position, SolvedDb, TIE_EPS};
use sts_engine::agent::greedy_action;
use sts_engine::codec::{decode, encode};
use sts_engine::solve::{group_options, solve, MemoryStore, Solution, SolveConfig, Solved, SolvedStore};
use sts_engine::*;

/// A fresh, empty directory for one test's database.
/// Deleted when the test ends (declared first, so it drops after the
/// databases that hold its files open).
fn temp_db(name: &str) -> TempDb {
    let dir = std::env::temp_dir().join(format!("solvedb-test-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    TempDb(dir.join("solved.sqlite"))
}

/// The database path of `temp_db`; removes its folder on drop.
struct TempDb(PathBuf);

impl std::ops::Deref for TempDb {
    type Target = PathBuf;
    fn deref(&self) -> &PathBuf {
        &self.0
    }
}

impl AsRef<std::path::Path> for TempDb {
    fn as_ref(&self) -> &std::path::Path {
        &self.0
    }
}

impl AsRef<std::ffi::OsStr> for TempDb {
    fn as_ref(&self) -> &std::ffi::OsStr {
        self.0.as_os_str()
    }
}

impl Drop for TempDb {
    fn drop(&mut self) {
        if let Some(dir) = self.0.parent() {
            let _ = std::fs::remove_dir_all(dir);
        }
    }
}

fn cfg(max_nodes: u64, distribution: bool) -> SolveConfig {
    SolveConfig { max_nodes, distribution, bounds: false }
}

/// Decision states of one greedy game, last first, with at least 2 options.
fn walk_back(enc: Encounter, seed: u64) -> Vec<CombatState> {
    let mut rng = Rng::new(seed);
    let mut s = CombatState::new(&starter_deck(), 80, 80, enc, &mut rng);
    let mut out = Vec::new();
    while s.awaiting_action() {
        out.push(s.clone());
        let a = greedy_action(&s);
        s.step(a, &mut rng).unwrap();
    }
    out.into_iter().rev().filter(|s| s.legal_actions().len() >= 2).collect()
}

/// `n` tail positions that solve within `max_nodes` and cost at least `min_cost`.
fn positions(n: usize, max_nodes: u64, min_cost: u64) -> Vec<CombatState> {
    let mut out = Vec::new();
    'games: for seed in 0..400u64 {
        let enc = Encounter::ALL[seed as usize % Encounter::ALL.len()];
        for s in walk_back(enc, seed) {
            let Some(r) = solve(&s, &cfg(max_nodes, false), None) else { continue 'games };
            if r.cost >= min_cost {
                out.push(s);
                if out.len() == n {
                    return out;
                }
            }
        }
    }
    out
}

fn same(a: &Solution, b: &Solution) {
    assert_eq!(a.options.len(), b.options.len());
    for (x, y) in a.options.iter().zip(&b.options) {
        assert_eq!(x.actions, y.actions);
        assert_eq!(x.value.to_bits(), y.value.to_bits());
        assert_eq!(x.dist, y.dist);
    }
}

fn count(path: &PathBuf, sql: &str) -> i64 {
    Connection::open(path).unwrap().query_row(sql, [], |r| r.get(0)).unwrap()
}

#[test]
fn wal_smoke() {
    let path = temp_db("wal");
    let db = SolvedDb::open(&path, 5.0).unwrap();
    let mode: String = Connection::open(&path).unwrap().query_row("PRAGMA journal_mode", [], |r| r.get(0)).unwrap();
    assert_eq!(mode, "wal");
    let states = positions(1, 20_000, 0);
    let root = &states[0];
    // One writer commits batches while four readers on their own
    // connections keep reading: each sees whole batches, never part of one.
    let stop = std::sync::atomic::AtomicBool::new(false);
    std::thread::scope(|scope| {
        let readers: Vec<_> = (0..4)
            .map(|_| {
                scope.spawn(|| {
                    let conn = Connection::open(&path).unwrap();
                    conn.busy_timeout(std::time::Duration::from_secs(60)).unwrap();
                    let mut reads = 0;
                    while !stop.load(std::sync::atomic::Ordering::Relaxed) || reads == 0 {
                        let n: i64 = conn.query_row("SELECT COUNT(*) FROM states", [], |r| r.get(0)).unwrap();
                        assert_eq!(n % 100, 0, "a reader saw part of a batch");
                        reads += 1;
                    }
                    reads
                })
            })
            .collect();
        let mut store = db.store(0).unwrap();
        let mut s = root.clone();
        for batch in 0..20 {
            for i in 0..100 {
                s.turn = (batch * 100 + i) as u16 + 1_000;
                store.insert(&s, &Solved { value: 1.0, cost: 5, turns_left: 0, dist: None, options: None });
            }
            store.end_solve();
        }
        stop.store(true, std::sync::atomic::Ordering::Relaxed);
        for r in readers {
            assert!(r.join().unwrap() > 0);
        }
    });
    assert_eq!(count(&path, "SELECT COUNT(*) FROM states"), 2_000);
}

/// The child half of `db_persists`, run in its own process.
#[test]
#[ignore]
fn db_persists_child() {
    let Ok(path) = std::env::var("SOLVEDB_CHILD") else { return };
    let root = decode(&std::fs::read(format!("{path}.root")).unwrap());
    let db = SolvedDb::open(&path, 5.0).unwrap();
    let mut store = db.store(0).unwrap();
    let r = solve(&root, &cfg(1_000_000, true), Some(&mut store)).unwrap();
    assert_eq!((r.nodes, r.hits), (0, 1), "the root is not a hit");
    let mut text = String::new();
    for o in &r.options {
        let d = o.dist.as_ref().unwrap();
        text += &format!("{:?} {:016x} {:016x} {:?}\n", o.actions, o.value.to_bits(), d.loss.to_bits(), d.wins.iter().map(|&(k, p)| (k, p.to_bits())).collect::<Vec<_>>());
    }
    std::fs::write(format!("{path}.child"), text).unwrap();
}

#[test]
fn db_persists() {
    let path = temp_db("persists");
    let root = positions(1, 50_000, 2_000).remove(0);
    let first = {
        let db = SolvedDb::open(&path, 5.0).unwrap();
        let mut store = db.store(1_000).unwrap();
        solve(&root, &cfg(1_000_000, true), Some(&mut store)).unwrap()
    };
    // A new process reopens the file and finds the root solved.
    std::fs::write(format!("{}.root", path.display()), encode(&root)).unwrap();
    let out = Command::new(std::env::current_exe().unwrap())
        .args(["db_persists_child", "--exact", "--ignored", "--nocapture", "--test-threads=1"])
        .env("SOLVEDB_CHILD", &path)
        .output()
        .unwrap();
    assert!(out.status.success(), "child failed: {}", String::from_utf8_lossy(&out.stdout));
    let child = std::fs::read_to_string(format!("{}.child", path.display())).unwrap();
    let mut text = String::new();
    for o in &first.options {
        let d = o.dist.as_ref().unwrap();
        text += &format!("{:?} {:016x} {:016x} {:?}\n", o.actions, o.value.to_bits(), d.loss.to_bits(), d.wins.iter().map(|&(k, p)| (k, p.to_bits())).collect::<Vec<_>>());
    }
    assert_eq!(child, text, "values or distributions differ after reopening");
    // Its row decodes to the same state.
    let conn = Connection::open(&path).unwrap();
    let bytes = encode(&root);
    let stored: Vec<u8> = conn
        .query_row("SELECT state FROM states WHERE key_hash = ?1", [solvedb::fnv1a(&bytes) as i64], |r| r.get(0))
        .unwrap();
    assert_eq!(decode(&stored), root);
    // And this process, reopening, hits it too.
    let db = SolvedDb::open(&path, 5.0).unwrap();
    let mut store = db.store(1_000).unwrap();
    let again = solve(&root, &cfg(1_000_000, true), Some(&mut store)).unwrap();
    assert_eq!(again.hits, 1);
    same(&first, &again);
}

#[test]
fn db_rules_version() {
    let path = temp_db("version");
    let root = positions(1, 50_000, 2_000).remove(0);
    {
        let a = SolvedDb::open_as(&path, 5.0, "aaaaaaaaaaaaaaaa").unwrap();
        let mut store = a.store(0).unwrap();
        solve(&root, &cfg(1_000_000, false), Some(&mut store)).unwrap();
    }
    let b = SolvedDb::open_as(&path, 5.0, "bbbbbbbbbbbbbbbb").unwrap();
    assert_eq!(b.snapshot_rows(), 0);
    let mut store = b.store(0).unwrap();
    let r = solve(&root, &cfg(1_000_000, false), Some(&mut store)).unwrap();
    assert_eq!(r.hits, 0, "rows of another rules version were used");
    assert_eq!(store.db_hits, 0);
    let stats = b.stats().unwrap();
    assert_eq!(stats.versions.len(), 2);
    assert!(stats.versions.iter().all(|v| v.rows > 0));
    // Back under A, its rows are hits again.
    let a = SolvedDb::open_as(&path, 5.0, "aaaaaaaaaaaaaaaa").unwrap();
    let mut store = a.store(0).unwrap();
    assert_eq!(solve(&root, &cfg(1_000_000, false), Some(&mut store)).unwrap().hits, 1);
}

#[test]
fn db_collision() {
    let path = temp_db("collision");
    let states = positions(3, 50_000, 0);
    let (a, b, c) = (&states[0], &states[1], &states[2]);
    let row = |v: f64| Solved { value: v, cost: 10, turns_left: 0, dist: None, options: None };
    // Every key hashes to 42.
    let collide: fn(&[u8]) -> u64 = |_| 42;
    {
        let db = SolvedDb::open(&path, 5.0).unwrap();
        let mut store = db.store_with_hasher(0, collide).unwrap();
        store.insert(a, &row(0.25));
        store.insert(b, &row(0.75));
        store.end_solve();
    }
    assert_eq!(count(&path, "SELECT COUNT(DISTINCT key_hash) FROM states"), 1);
    let db = SolvedDb::open(&path, 5.0).unwrap();
    let mut store = db.store_with_hasher(0, collide).unwrap();
    assert_eq!(store.lookup(a).unwrap().value, 0.25);
    assert_eq!(store.lookup(b).unwrap().value, 0.75);
    assert!(store.lookup(c).is_none(), "a key sharing the hash found another's row");
}

#[test]
fn db_snapshot() {
    let path = temp_db("snapshot");
    let root = positions(1, 50_000, 2_000).remove(0);
    let early = SolvedDb::open(&path, 5.0).unwrap();
    {
        let writer = SolvedDb::open(&path, 5.0).unwrap();
        let mut store = writer.store(0).unwrap();
        solve(&root, &cfg(1_000_000, false), Some(&mut store)).unwrap();
    }
    assert!(count(&path, "SELECT COUNT(*) FROM states") > 0);
    // Written after `early` opened: not used through it.
    let mut store = early.store(0).unwrap();
    let r = solve(&root, &cfg(1_000_000, false), Some(&mut store)).unwrap();
    assert_eq!((r.hits, store.db_hits), (0, 0));
    // A reopen sees them.
    let late = SolvedDb::open(&path, 5.0).unwrap();
    let mut store = late.store(0).unwrap();
    let again = solve(&root, &cfg(1_000_000, false), Some(&mut store)).unwrap();
    assert_eq!(again.hits, 1);
    same(&r, &again);

    // A distribution added later isn't seen through a handle opened before.
    let before = SolvedDb::open(&path, 5.0).unwrap();
    {
        let writer = SolvedDb::open(&path, 5.0).unwrap();
        let mut store = writer.store(0).unwrap();
        solve(&root, &cfg(1_000_000, true), Some(&mut store)).unwrap();
    }
    let mut store = before.store(0).unwrap();
    let d = solve(&root, &cfg(1_000_000, true), Some(&mut store)).unwrap();
    assert!(d.nodes > 0, "a distribution written after open was used");
    let mut store = SolvedDb::open(&path, 5.0).unwrap().store(0).unwrap();
    assert_eq!(solve(&root, &cfg(1_000_000, true), Some(&mut store)).unwrap().hits, 1);
}

#[test]
fn db_positions_basic() {
    let path = temp_db("positions");
    let root = positions(1, 50_000, 0).remove(0);
    let db = SolvedDb::open(&path, 5.0).unwrap();
    // min_nodes far above the root's cost: the position still gets its row.
    let mut store = db.store(u64::MAX).unwrap();
    let r = solve(&root, &cfg(1_000_000, false), Some(&mut store)).unwrap();
    let pos = Position { source: "bench", spec: "{}", prefix: "[]", step: 3, horizon: 0, gap: 0.5 };
    assert!(store.add_position(&root, &r, &pos).unwrap());
    assert!(!store.add_position(&root, &r, &pos).unwrap(), "recorded twice");
    assert_eq!(count(&path, "SELECT COUNT(*) FROM states"), 1);
    assert_eq!(count(&path, "SELECT COUNT(*) FROM positions"), 1);
    let rows = db.positions("bench").unwrap();
    assert_eq!(rows.len(), 1);
    assert_eq!((rows[0].step, rows[0].horizon, rows[0].gap), (3, 0, 0.5));
    assert_eq!(rows[0].options, r.options);
    assert_eq!(sts_engine::codec::decode(&rows[0].state), root);
    assert!(db.positions("other").unwrap().is_empty());
    let mut store = SolvedDb::open(&path, 5.0).unwrap().store(0).unwrap();
    let again = solve(&root, &cfg(1_000_000, false), Some(&mut store)).unwrap();
    assert_eq!(again.hits, 1);
    same(&r, &again);
}

#[test]
fn db_evict() {
    let path = temp_db("evict");
    // Many distinct states: a few positions, each with many turn counters.
    let base = positions(4, 50_000, 0);
    let fill = |db: &SolvedDb, n: usize, offset: u64| {
        let mut store = db.store(0).unwrap();
        for i in 0..n {
            let mut s = base[i % base.len()].clone();
            s.turn = 100 + (i / base.len()) as u16;
            let cost = offset + (i as u64 * 7919) % n as u64;
            store.insert(&s, &Solved { value: 1.0, cost, turns_left: 0, dist: None, options: None });
        }
        store.end_solve();
    };
    fill(&SolvedDb::open_as(&path, 5.0, "oldoldoldoldoldo").unwrap(), 4_000, 0);
    let db = SolvedDb::open(&path, 5.0).unwrap();
    fill(&db, 12_000, 1_000_000);
    let stats = db.stats().unwrap();
    let used = stats.bytes;
    assert!(used > 1_000_000, "only {used} bytes");

    // Under the cap: nothing goes.
    let none = db.evict(used + 1).unwrap();
    assert_eq!((none.other_versions, none.current), (0, 0));
    assert_eq!(count(&path, "SELECT COUNT(*) FROM states"), 16_000);

    // Over it: the old version first, then the cheapest.
    let cap = used / 2;
    let e = db.evict(cap).unwrap();
    assert_eq!(e.other_versions, 4_000);
    assert!(e.current > 0);
    assert_eq!(count(&path, "SELECT COUNT(*) FROM states WHERE cost < 1000000"), 0);
    let min_left = count(&path, "SELECT MIN(cost) FROM states") as u64;
    assert_eq!(min_left, 1_000_000 + e.current, "not the cheapest rows went");
    let file = std::fs::metadata(&path).unwrap().len();
    assert!(file <= cap * 9 / 10, "file {file} over 90% of cap {cap}");
    assert!(e.bytes_after <= cap * 9 / 10);
}

/// A tail position whose options are all tied (and not all lost),
/// solvable within 50k nodes.
fn tied_root() -> CombatState {
    for seed in 0..400u64 {
        let enc = Encounter::ALL[seed as usize % Encounter::ALL.len()];
        for s in walk_back(enc, seed) {
            let Some(r) = solve(&s, &cfg(50_000, false), None) else { break };
            let lo = r.options.iter().map(|o| o.value).fold(f64::INFINITY, f64::min);
            let hi = r.options.iter().map(|o| o.value).fold(f64::NEG_INFINITY, f64::max);
            if r.options.len() >= 2 && hi - lo <= TIE_EPS && hi > 0.0 {
                return s;
            }
        }
    }
    panic!("no tied position found")
}

/// Key hashes in `table`.
fn hashes(path: &PathBuf, table: &str) -> BTreeSet<i64> {
    let conn = Connection::open(path).unwrap();
    let mut q = conn.prepare(&format!("SELECT key_hash FROM {table}")).unwrap();
    let h = q.query_map([], |r| r.get(0)).unwrap().map(|h| h.unwrap()).collect();
    h
}

/// A stored entry read back: the same value, cost and turns left; options
/// with the same actions, their values exact, or within `TIE_EPS` when the
/// entry is trivial (its options all come back at its value).
fn same_entry(want: &Solved, got: &Solved) {
    assert_eq!(want.value.to_bits(), got.value.to_bits());
    assert_eq!((want.cost, want.turns_left), (got.cost, got.turns_left));
    assert_eq!(want.options.as_ref().map(Vec::len), got.options.as_ref().map(Vec::len));
    for (x, y) in want.options.iter().flatten().zip(got.options.iter().flatten()) {
        assert_eq!(x.actions, y.actions);
        if is_trivial(want) {
            assert!((x.value - y.value).abs() <= TIE_EPS);
        } else {
            assert_eq!(x.value.to_bits(), y.value.to_bits());
        }
    }
}

/// Turns a database into a version-1 one: no `trivial` table, schema 1.
fn downgrade(path: &PathBuf) {
    let conn = Connection::open(path).unwrap();
    conn.execute_batch("DROP TABLE trivial; UPDATE meta SET value = '1' WHERE key = 'schema';").unwrap();
}

#[test]
fn db_trivial_roundtrip() {
    let path = temp_db("trivial");
    let root = positions(1, 50_000, 2_000).remove(0);
    // What the solver offers, kept in memory: what a store over an empty
    // database keeps.
    let mut mem = MemoryStore::new(0);
    let first = solve(&root, &cfg(1_000_000, false), Some(&mut mem)).unwrap();
    let entries: Vec<(CombatState, Solved)> = mem.iter().map(|(s, e)| (s.clone(), e.clone())).collect();
    let key = |s: &CombatState| solvedb::fnv1a(&encode(s)) as i64;
    let trivial: BTreeSet<i64> = entries.iter().filter(|(_, e)| is_trivial(e)).map(|(s, _)| key(s)).collect();
    let full: BTreeSet<i64> = entries.iter().filter(|(_, e)| !is_trivial(e)).map(|(s, _)| key(s)).collect();
    assert!(!trivial.is_empty() && !full.is_empty(), "{} trivial, {} full", trivial.len(), full.len());
    {
        let db = SolvedDb::open(&path, 5.0).unwrap();
        let mut store = db.store(0).unwrap();
        same(&first, &solve(&root, &cfg(1_000_000, false), Some(&mut store)).unwrap());
    }
    assert_eq!(hashes(&path, "trivial"), trivial);
    assert_eq!(hashes(&path, "states"), full);
    // Every entry reads back through a fresh handle.
    let db = SolvedDb::open(&path, 5.0).unwrap();
    assert_eq!(db.snapshot_rows(), trivial.len() + full.len());
    let mut store = db.store(0).unwrap();
    for (s, e) in &entries {
        same_entry(e, &store.lookup(s).unwrap());
    }
    // A solve that can't answer from the root's row expands it and hits
    // its children's rows, trivial ones among them: the same option values.
    let conn = Connection::open(&path).unwrap();
    conn.execute("DELETE FROM states WHERE key_hash = ?1", [key(&root)]).unwrap();
    conn.execute("DELETE FROM trivial WHERE key_hash = ?1", [key(&root)]).unwrap();
    let mut store = SolvedDb::open(&path, 5.0).unwrap().store(0).unwrap();
    let again = solve(&root, &cfg(1_000_000, false), Some(&mut store)).unwrap();
    assert!(again.nodes > 0 && again.hits > 0 && store.db_hits > 0);
    same(&first, &again);
}

#[test]
fn db_trivial_check() {
    let path = temp_db("trivial-check");
    let s = positions(1, 50_000, 0).remove(0);
    let bytes = encode(&s);
    let version = SolvedDb::open(&path, 5.0).unwrap().version_id();
    let conn = Connection::open(&path).unwrap();
    let wrong = (solvedb::fnv1a32(&bytes) ^ 1) as i64;
    conn.execute(
        "INSERT INTO trivial (version, key_hash, check_hash, value, cost, turns_left) VALUES (?1, ?2, ?3, 0.5, 10, 3)",
        rusqlite::params![version, solvedb::fnv1a(&bytes) as i64, wrong],
    )
    .unwrap();
    let mut store = SolvedDb::open(&path, 5.0).unwrap().store(0).unwrap();
    assert!(store.lookup(&s).is_none(), "a row with the right key hash and a wrong check was used");
    conn.execute("UPDATE trivial SET check_hash = ?1", [solvedb::fnv1a32(&bytes) as i64]).unwrap();
    let mut store = SolvedDb::open(&path, 5.0).unwrap().store(0).unwrap();
    let got = store.lookup(&s).unwrap();
    assert_eq!((got.value, got.cost, got.turns_left), (0.5, 10, 3));
    let groups: Vec<Vec<Action>> = group_options(&s).into_iter().map(|(_, a)| a).collect();
    let opts = got.options.unwrap();
    assert_eq!(opts.iter().map(|o| o.actions.clone()).collect::<Vec<_>>(), groups);
    assert!(opts.iter().all(|o| o.value == 0.5 && o.dist.is_none()));
}

#[test]
fn db_position_full() {
    let path = temp_db("position-full");
    let root = tied_root();
    let h = solvedb::fnv1a(&encode(&root)) as i64;
    let db = SolvedDb::open(&path, 5.0).unwrap();
    let mut store = db.store(0).unwrap();
    let r = solve(&root, &cfg(1_000_000, false), Some(&mut store)).unwrap();
    assert!(hashes(&path, "trivial").contains(&h), "the tied root wasn't stored as trivial");
    let pos = Position { source: "bench", spec: "{}", prefix: "[]", step: 1, horizon: 0, gap: 0.0 };
    assert!(store.add_position(&root, &r, &pos).unwrap());
    assert!(!hashes(&path, "trivial").contains(&h), "the puzzle stayed in trivial");
    assert!(hashes(&path, "states").contains(&h));
    let db = SolvedDb::open(&path, 5.0).unwrap();
    let rows = db.positions("bench").unwrap();
    assert_eq!(rows.len(), 1);
    assert_eq!(decode(&rows[0].state), root);
    assert_eq!(rows[0].options, r.options, "the puzzle's own option values, not rebuilt ones");
    let again = solve(&root, &cfg(1_000_000, false), Some(&mut db.store(0).unwrap())).unwrap();
    assert_eq!(again.hits, 1);
    same(&r, &again);
}

#[test]
fn db_schema_upgrade() {
    let path = temp_db("upgrade");
    let root = positions(1, 50_000, 2_000).remove(0);
    let first = {
        let db = SolvedDb::open(&path, 5.0).unwrap();
        let mut store = db.store_full_rows(0).unwrap();
        solve(&root, &cfg(1_000_000, false), Some(&mut store)).unwrap()
    };
    downgrade(&path);
    let rows = count(&path, "SELECT COUNT(*) FROM states");
    let db = SolvedDb::open(&path, 5.0).unwrap();
    let conn = Connection::open(&path).unwrap();
    let schema: String = conn.query_row("SELECT value FROM meta WHERE key = 'schema'", [], |r| r.get(0)).unwrap();
    assert_eq!(schema, "2");
    assert_eq!((count(&path, "SELECT COUNT(*) FROM trivial"), count(&path, "SELECT COUNT(*) FROM states")), (0, rows));
    let again = solve(&root, &cfg(1_000_000, false), Some(&mut db.store(0).unwrap())).unwrap();
    assert_eq!(again.hits, 1);
    same(&first, &again);
}

#[test]
fn db_compact() {
    let path = temp_db("compact");
    let roots = positions(3, 50_000, 2_000);
    let tied = tied_root();
    // A version-1 database: every row in full, one puzzle on a tied root.
    let mut mem = MemoryStore::new(0);
    {
        let db = SolvedDb::open(&path, 5.0).unwrap();
        let mut store = db.store_full_rows(0).unwrap();
        for root in &roots {
            solve(root, &cfg(1_000_000, false), Some(&mut store)).unwrap();
            solve(root, &cfg(1_000_000, false), Some(&mut mem)).unwrap();
        }
        let r = solve(&tied, &cfg(1_000_000, false), Some(&mut store)).unwrap();
        solve(&tied, &cfg(1_000_000, false), Some(&mut mem)).unwrap();
        let pos = Position { source: "bench", spec: "{}", prefix: "[]", step: 1, horizon: 0, gap: 0.0 };
        assert!(store.add_position(&tied, &r, &pos).unwrap());
    }
    downgrade(&path);
    let tied_bytes = encode(&tied);
    let states: Vec<Vec<u8>> = mem.iter().map(|(s, _)| encode(s)).collect();
    let movable = mem.iter().zip(&states).filter(|((_, e), b)| is_trivial(e) && **b != tied_bytes).count();
    assert!(movable > 0);
    let rows = count(&path, "SELECT COUNT(*) FROM states");
    assert_eq!(rows as usize, states.len());
    let before = SolvedDb::open(&path, 5.0).unwrap().lookup(&states).unwrap();
    let file_before = std::fs::metadata(&path).unwrap().len();

    let c = SolvedDb::open(&path, 5.0).unwrap().compact().unwrap();
    assert_eq!(c.moved as usize, movable);
    assert_eq!(count(&path, "SELECT COUNT(*) FROM states"), rows - c.moved as i64);
    assert_eq!(count(&path, "SELECT COUNT(*) FROM trivial"), c.moved as i64);
    assert!(c.bytes_after < c.bytes_before, "{c:?}");
    assert!(std::fs::metadata(&path).unwrap().len() < file_before);
    // Lookups agree on every state, and the puzzle keeps its full row.
    let db = SolvedDb::open(&path, 5.0).unwrap();
    let after = db.lookup(&states).unwrap();
    for (b, a) in before.iter().zip(&after) {
        same_entry(b.as_ref().unwrap(), a.as_ref().unwrap());
    }
    assert_eq!(decode(&db.positions("bench").unwrap()[0].state), tied);
    let stats = db.stats().unwrap();
    let current = stats.versions.iter().find(|v| v.current).unwrap();
    assert_eq!((current.rows, current.trivial), ((rows - c.moved as i64) as u64, c.moved));
    assert!(stats.tables.iter().any(|(t, b)| t == "trivial" && *b > 0));
}

/// The children `repair_costs` reads: a decision's distinct afterstates, a
/// random event's outcomes, unfinished only.
fn kids(s: &CombatState) -> Vec<CombatState> {
    let all: Vec<CombatState> = if s.awaiting_action() {
        group_options(s).into_iter().map(|(after, _)| after).collect()
    } else {
        match s.chance_outcomes(usize::MAX) {
            Some(ChanceOutcomes::Listed(v)) => v.into_iter().map(|(_, k)| k).collect(),
            _ => panic!("a stored chance state lists its outcomes"),
        }
    };
    all.into_iter().filter(|k| !k.is_over()).collect()
}

/// Costs summed by the old rule (negative once wrapped) are rebuilt from the
/// rows' children: never above the true cost, one more than the costliest
/// child's, other rows untouched; a bad trivial row nothing reaches gets
/// `max_cost`.
#[test]
fn db_repair_costs() {
    let path = temp_db("repair");
    let db = SolvedDb::open(&path, 5.0).unwrap();
    // Walks back reusing hits, every state kept, so children have rows.
    for seed in 0..2u64 {
        let enc = Encounter::ALL[seed as usize % Encounter::ALL.len()];
        let mut store = db.store(0).unwrap();
        for s in walk_back(enc, seed).into_iter().take(8) {
            if solve(&s, &cfg(50_000, false), Some(&mut store)).is_none() {
                break;
            }
        }
    }
    let conn = Connection::open(&path).unwrap();
    let read = |sql: &str| -> Vec<(i64, i64)> {
        let mut q = conn.prepare(sql).unwrap();
        let rows = q.query_map([], |r| Ok((r.get(0)?, r.get(1)?))).unwrap();
        rows.map(Result::unwrap).collect()
    };
    let states_before = read("SELECT id, cost FROM states ORDER BY id");
    let trivial_before = read("SELECT key_hash, cost FROM trivial ORDER BY key_hash");
    let mut sorted: Vec<i64> = states_before.iter().map(|&(_, c)| c).collect();
    sorted.sort_unstable();
    let max_cost = sorted[sorted.len() / 2] as u64;
    // Break every row above the median, half of them wrapped below 0.
    let broken = |(k, c): (i64, i64)| (c as u64 > max_cost).then_some(if k % 2 == 0 { -c } else { c * 1_000_000 });
    let bad_states: Vec<_> = states_before.iter().filter_map(|&r| broken(r).map(|b| (r.0, b))).collect();
    let bad_trivial: Vec<_> = trivial_before.iter().filter_map(|&r| broken(r).map(|b| (r.0, b))).collect();
    assert!(bad_states.len() > 20 && !bad_trivial.is_empty(), "{} / {}", bad_states.len(), bad_trivial.len());
    conn.execute_batch("BEGIN").unwrap();
    for &(id, c) in &bad_states {
        conn.execute("UPDATE states SET cost = ?1 WHERE id = ?2", [c, id]).unwrap();
    }
    for &(h, c) in &bad_trivial {
        conn.execute("UPDATE trivial SET cost = ?1 WHERE key_hash = ?2", [c, h]).unwrap();
    }
    conn.execute_batch("COMMIT").unwrap();
    // A bad trivial row no stored state reaches.
    conn.execute("INSERT INTO trivial VALUES (?1, 12345, 0, 0.0, -7, 0)", [db.version_id()]).unwrap();

    let r = SolvedDb::open(&path, 5.0).unwrap().repair_costs(max_cost).unwrap();
    assert_eq!(r.states as usize, bad_states.len());
    assert_eq!((r.trivial + r.clamped) as usize, bad_trivial.len() + 1);
    assert!(r.clamped >= 1);
    assert_eq!(count(&path, "SELECT cost FROM trivial WHERE key_hash = 12345"), max_cost as i64);
    let states_after = read("SELECT id, cost FROM states ORDER BY id");
    let trivial_after = read("SELECT key_hash, cost FROM trivial WHERE key_hash != 12345 ORDER BY key_hash");
    let mut exact = 0;
    for (table, before, after) in [("states", &states_before, &states_after), ("trivial", &trivial_before, &trivial_after)] {
        assert_eq!(before.len(), after.len());
        for (b, a) in before.iter().zip(after) {
            assert_eq!(b.0, a.0);
            if b.1 as u64 <= max_cost {
                assert_eq!(b, a, "a sound {table} row changed");
            } else if !(table == "trivial" && a.1 as u64 == max_cost) {
                // Clamped trivial rows aside, never above the true cost.
                assert!(1 <= a.1 && a.1 <= b.1, "{table}: repaired {} vs true {}", a.1, b.1);
                exact += (a.1 == b.1) as usize;
            }
        }
    }
    // Each repaired state's cost is one more than its costliest child's.
    let db = SolvedDb::open(&path, 5.0).unwrap();
    let mut q = conn.prepare("SELECT state, cost FROM states WHERE id = ?1").unwrap();
    let (mut all, mut ends, mut costs) = (Vec::new(), Vec::new(), Vec::new());
    for &(id, _) in &bad_states {
        let (bytes, cost): (Vec<u8>, i64) = q.query_row([id], |r| Ok((r.get(0)?, r.get(1)?))).unwrap();
        all.extend(kids(&decode(&bytes)).iter().map(encode));
        ends.push(all.len());
        costs.push(cost as u64);
    }
    let found = db.lookup(&all).unwrap();
    let mut start = 0;
    for (end, cost) in ends.into_iter().zip(costs) {
        let best = found[start..end].iter().map(|k| k.as_ref().map_or(0, |e| e.cost)).max().unwrap_or(0);
        assert_eq!(cost, best + 1);
        start = end;
    }
    eprintln!("db_repair_costs: {} states and {} trivial rows repaired ({exact} back to their true cost), {} clamped",
              r.states, r.trivial, r.clamped);
}
