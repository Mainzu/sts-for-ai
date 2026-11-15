//! The SQLite database of solved states.
//!
//! - `versions`: one row per rules fingerprint.
//! - `states`: one row per solved state (decodable state bytes, exact value,
//!   cost, turns left, its distribution and, on decision states, each root
//!   option's actions and exact value), unique on (version, state bytes).
//! - `trivial`: solved states whose choices don't matter (`is_trivial`),
//!   as key hash, a second check hash, value, cost and turns left only:
//!   the solver has the state in hand when it meets one again (Amendment 1).
//! - `positions`: played positions (puzzles) with their source.
//! - `meta`: the schema version.
//!
//! A handle sees the database as it was when it was opened: lookups use only
//! rows (and distributions) that existed then, so a run's output never
//! depends on what other games or processes write during it.

use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use rusqlite::{params, Connection, OptionalExtension, TransactionBehavior};
use sts_engine::codec::{decode, encode, CODEC_VERSION};
use sts_engine::solve::{group_options, MemoryStore, Solution, Solved, SolvedOption, SolvedStore};
use sts_engine::{ChanceOutcomes, CombatState};

use crate::rows::{dist_blob, dist_from_blob, options_blob, options_from_blob};
use crate::{fingerprint, fnv1a, fnv1a32};

pub use rusqlite::Error;
pub type Result<T> = rusqlite::Result<T>;

/// 2 adds `trivial` (Amendment 1); a version-1 database gains the empty
/// table when opened.
pub const SCHEMA_VERSION: i64 = 2;
/// Option values within this of each other are tied (as `TIE_EPS` in
/// scripts/learn.py).
pub const TIE_EPS: f64 = 1e-9;
pub const DEFAULT_PATH: &str = "db/solved.sqlite";
pub const DEFAULT_MAX_GB: f64 = 5.0;

const SCHEMA: &str = "
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY,
    fingerprint TEXT NOT NULL UNIQUE,
    codec INTEGER NOT NULL,
    first_seen INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS states (
    id INTEGER PRIMARY KEY,
    version INTEGER NOT NULL REFERENCES versions(id),
    key_hash INTEGER NOT NULL,
    state BLOB NOT NULL,
    value REAL NOT NULL,
    cost INTEGER NOT NULL,
    turns_left INTEGER NOT NULL,
    dist BLOB,
    options BLOB,
    solved_at INTEGER NOT NULL,
    UNIQUE (version, state)
);
CREATE INDEX IF NOT EXISTS states_hash ON states (version, key_hash);
CREATE INDEX IF NOT EXISTS states_cost ON states (version, cost);
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY,
    state INTEGER NOT NULL REFERENCES states(id),
    source TEXT NOT NULL,
    spec TEXT NOT NULL,
    prefix TEXT NOT NULL,
    step INTEGER NOT NULL,
    horizon INTEGER NOT NULL,
    gap REAL NOT NULL
);
-- One row per decision of a game per source; also the index on source.
CREATE UNIQUE INDEX IF NOT EXISTS positions_source ON positions (source, spec, step);
CREATE TABLE IF NOT EXISTS trivial (
    version INTEGER NOT NULL REFERENCES versions(id),
    key_hash INTEGER NOT NULL,
    check_hash INTEGER NOT NULL,
    value REAL NOT NULL,
    cost INTEGER NOT NULL,
    turns_left INTEGER NOT NULL,
    PRIMARY KEY (version, key_hash)
) WITHOUT ROWID;
";

/// Whether a solved state is stored as value only (Amendment 1): every line
/// loses, or at a decision every option's value is within `TIE_EPS` of the
/// others (the choice doesn't matter now).
pub fn is_trivial(s: &Solved) -> bool {
    if s.value == 0.0 {
        return true;
    }
    match s.options.as_deref() {
        Some(opts) if !opts.is_empty() && opts.iter().all(|o| !o.bounded) => {
            let lo = opts.iter().map(|o| o.value).fold(f64::INFINITY, f64::min);
            let hi = opts.iter().map(|o| o.value).fold(f64::NEG_INFINITY, f64::max);
            hi - lo <= TIE_EPS
        }
        _ => false,
    }
}

fn now() -> i64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map_or(0, |d| d.as_secs() as i64)
}

/// A connection in WAL mode (readers don't wait for a writer), waiting up
/// to ten minutes for another writer's lock: with a low `min_nodes` one
/// solve's batch can be a million rows, which takes over a minute to write.
fn connect(path: &Path) -> Result<Connection> {
    let conn = Connection::open(path)?;
    conn.busy_timeout(Duration::from_secs(600))?;
    let mode: String = conn.query_row("PRAGMA journal_mode = WAL", [], |r| r.get(0))?;
    assert_eq!(mode.to_lowercase(), "wal", "SQLite refused WAL mode");
    conn.execute_batch("PRAGMA synchronous = NORMAL;")?;
    Ok(conn)
}

/// What a handle saw when it opened.
struct Snapshot {
    /// Highest row id then: rows written later are not used.
    max_id: i64,
    /// The current version's key hashes, sorted (8 bytes per row).
    hashes: Vec<u64>,
    /// The same for its `trivial` rows.
    trivial: Vec<u64>,
    /// Rows that had distributions then, sorted.
    dist_ids: Vec<i64>,
}

impl Snapshot {
    fn has(&self, h: u64) -> bool {
        self.hashes.binary_search(&h).is_ok()
    }

    fn has_trivial(&self, h: u64) -> bool {
        self.trivial.binary_search(&h).is_ok()
    }
}

/// The database, opened under one rules fingerprint. Cheap to share across
/// threads; each thread gets its own connection through `store`.
pub struct SolvedDb {
    path: PathBuf,
    /// Size cap, in GB (10^9 bytes), enforced by `enforce_cap`.
    pub max_gb: f64,
    fingerprint: String,
    version: i64,
    snap: Arc<Snapshot>,
}

impl SolvedDb {
    /// Opens (or creates) the database under this build's rules fingerprint.
    pub fn open(path: impl AsRef<Path>, max_gb: f64) -> Result<SolvedDb> {
        SolvedDb::open_as(path, max_gb, fingerprint())
    }

    /// Opens under a given fingerprint (tests: another rules version).
    pub fn open_as(path: impl AsRef<Path>, max_gb: f64, fingerprint: &str) -> Result<SolvedDb> {
        let path = path.as_ref().to_path_buf();
        if let Some(dir) = path.parent().filter(|d| !d.as_os_str().is_empty()) {
            std::fs::create_dir_all(dir).map_err(|_| Error::InvalidPath(dir.to_path_buf()))?;
        }
        let mut conn = connect(&path)?;
        let tx = conn.transaction_with_behavior(TransactionBehavior::Immediate)?;
        tx.execute_batch(SCHEMA)?;
        tx.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('schema', ?1)", [SCHEMA_VERSION.to_string()])?;
        let schema: String = tx.query_row("SELECT value FROM meta WHERE key = 'schema'", [], |r| r.get(0))?;
        match schema.as_str() {
            // Version 1 lacked `trivial`, which SCHEMA just added.
            "1" => {
                tx.execute("UPDATE meta SET value = ?1 WHERE key = 'schema'", [SCHEMA_VERSION.to_string()])?;
            }
            "2" => {}
            _ => panic!("{}: unknown schema version {schema}", path.display()),
        }
        tx.execute(
            "INSERT OR IGNORE INTO versions (fingerprint, codec, first_seen) VALUES (?1, ?2, ?3)",
            params![fingerprint, CODEC_VERSION, now()],
        )?;
        let version: i64 = tx.query_row("SELECT id FROM versions WHERE fingerprint = ?1", [fingerprint], |r| r.get(0))?;
        let max_id: i64 = tx.query_row("SELECT COALESCE(MAX(id), 0) FROM states", [], |r| r.get(0))?;
        let mut hashes = Vec::new();
        let mut dist_ids = Vec::new();
        {
            let mut q = tx.prepare("SELECT id, key_hash, dist IS NOT NULL FROM states WHERE version = ?1")?;
            let mut rows = q.query([version])?;
            while let Some(r) = rows.next()? {
                let (id, h, d): (i64, i64, bool) = (r.get(0)?, r.get(1)?, r.get(2)?);
                hashes.push(h as u64);
                if d {
                    dist_ids.push(id);
                }
            }
        }
        let mut trivial = {
            let mut q = tx.prepare("SELECT key_hash FROM trivial WHERE version = ?1")?;
            let h = q.query_map([version], |r| r.get::<_, i64>(0).map(|h| h as u64))?.collect::<Result<Vec<u64>>>()?;
            h
        };
        tx.commit()?;
        hashes.sort_unstable();
        hashes.dedup();
        trivial.sort_unstable();
        dist_ids.sort_unstable();
        let snap = Arc::new(Snapshot { max_id, hashes, trivial, dist_ids });
        Ok(SolvedDb { path, max_gb, fingerprint: fingerprint.to_string(), version, snap })
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn fingerprint(&self) -> &str {
        &self.fingerprint
    }

    pub fn version_id(&self) -> i64 {
        self.version
    }

    /// Rows of the current version when this handle opened (both tables).
    pub fn snapshot_rows(&self) -> usize {
        self.snap.hashes.len() + self.snap.trivial.len()
    }

    /// One game's store: memory (keeping states that cost at least
    /// `min_nodes`) in front of this database, on its own connection.
    pub fn store(&self, min_nodes: u64) -> Result<DbStore> {
        self.store_with_hasher(min_nodes, fnv1a)
    }

    /// `store` with another key hash (tests: forced collisions).
    #[doc(hidden)]
    pub fn store_with_hasher(&self, min_nodes: u64, hasher: fn(&[u8]) -> u64) -> Result<DbStore> {
        Ok(DbStore {
            mem: MemoryStore::new(min_nodes),
            conn: connect(&self.path)?,
            version: self.version,
            snap: Arc::clone(&self.snap),
            hasher,
            split_trivial: true,
            pending: Vec::new(),
            db_hits: 0,
        })
    }

    /// `store` writing every row in full, as schema 1 did (tests: building
    /// a version-1 database).
    #[doc(hidden)]
    pub fn store_full_rows(&self, min_nodes: u64) -> Result<DbStore> {
        Ok(DbStore { split_trivial: false, ..self.store(min_nodes)? })
    }

    /// Size, rows per rules version and the current version's cost spread.
    pub fn stats(&self) -> Result<Stats> {
        let conn = connect(&self.path)?;
        let mut versions = Vec::new();
        {
            let mut q = conn.prepare(
                "SELECT v.id, v.fingerprint, (SELECT COUNT(*) FROM states s WHERE s.version = v.id),
                        (SELECT COUNT(*) FROM trivial t WHERE t.version = v.id)
                 FROM versions v ORDER BY v.id",
            )?;
            let mut rows = q.query([])?;
            while let Some(r) = rows.next()? {
                let id: i64 = r.get(0)?;
                versions.push(VersionRows {
                    id,
                    fingerprint: r.get(1)?,
                    rows: r.get::<_, i64>(2)? as u64,
                    trivial: r.get::<_, i64>(3)? as u64,
                    current: id == self.version,
                });
            }
        }
        // Bytes per table, its indexes included (reads every page).
        let mut tables = Vec::new();
        {
            let mut q = conn.prepare(
                "SELECT m.tbl_name, SUM(d.pgsize) FROM dbstat d JOIN sqlite_master m ON m.name = d.name
                 GROUP BY m.tbl_name ORDER BY m.tbl_name",
            )?;
            let mut rows = q.query([])?;
            while let Some(r) = rows.next()? {
                tables.push((r.get::<_, String>(0)?, r.get::<_, i64>(1)? as u64));
            }
        }
        let positions: i64 = conn.query_row("SELECT COUNT(*) FROM positions", [], |r| r.get(0))?;
        let rows = versions.iter().find(|v| v.current).map_or(0, |v| v.rows);
        let mut cost_quantiles = Vec::new();
        if rows > 0 {
            for q in [0.0, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0] {
                let at = ((rows - 1) as f64 * q).round() as i64;
                let c: i64 = conn.query_row(
                    "SELECT cost FROM states WHERE version = ?1 ORDER BY cost LIMIT 1 OFFSET ?2",
                    params![self.version, at],
                    |r| r.get(0),
                )?;
                cost_quantiles.push((q, c as u64));
            }
        }
        Ok(Stats {
            bytes: used_bytes(&conn)?,
            file_bytes: file_bytes(&self.path),
            versions,
            tables,
            positions: positions as u64,
            cost_quantiles,
        })
    }

    /// Every `positions` row of `source` in the current version, oldest
    /// first, with its state's bytes and options.
    pub fn positions(&self, source: &str) -> Result<Vec<PositionRow>> {
        let conn = connect(&self.path)?;
        let mut q = conn.prepare(
            "SELECT s.state, p.spec, p.prefix, p.step, p.horizon, p.gap, s.options FROM positions p
             JOIN states s ON s.id = p.state WHERE p.source = ?1 AND s.version = ?2 ORDER BY p.id",
        )?;
        let mut rows = q.query(params![source, self.version])?;
        let mut out = Vec::new();
        while let Some(r) = rows.next()? {
            let state: Vec<u8> = r.get(0)?;
            out.push(PositionRow {
                options: r.get::<_, Option<Vec<u8>>>(6)?.map(|b| options_from_blob(&state, &b)).unwrap_or_default(),
                state,
                spec: r.get(1)?,
                prefix: r.get(2)?,
                step: r.get::<_, i64>(3)? as u32,
                horizon: r.get::<_, i64>(4)? as u32,
                gap: r.get(5)?,
            });
        }
        Ok(out)
    }

    /// Read-only lookups (curriculum labels): each state's row (codec
    /// bytes) of the current version as this handle saw it at open, or None.
    pub fn lookup(&self, states: &[Vec<u8>]) -> Result<Vec<Option<Solved>>> {
        let conn = connect(&self.path)?;
        states.iter().map(|b| read_row(&conn, self.version, &self.snap, fnv1a, b)).collect()
    }

    /// Ids of the current version's decision rows (those with options) as
    /// this handle saw them at open, ordered by key hash (then id): an order
    /// set by the rows' content, not by when they were written.
    pub fn decision_ids(&self) -> Result<Vec<i64>> {
        let conn = connect(&self.path)?;
        let mut q = conn.prepare("SELECT id FROM states WHERE version = ?1 AND id <= ?2 AND options IS NOT NULL ORDER BY key_hash, id")?;
        let ids = q.query_map(params![self.version, self.snap.max_id], |r| r.get(0))?.collect();
        ids
    }

    /// The rows `ids` (from `decision_ids`) as (codec bytes, row), in the
    /// order given, without distributions.
    pub fn fetch(&self, ids: &[i64]) -> Result<Vec<(Vec<u8>, Solved)>> {
        let conn = connect(&self.path)?;
        let mut q = conn.prepare_cached("SELECT state, value, cost, turns_left, options FROM states WHERE id = ?1 AND version = ?2")?;
        ids.iter()
            .map(|id| {
                q.query_row(params![id, self.version], |r| {
                    let state: Vec<u8> = r.get(0)?;
                    Ok((
                        state.clone(),
                        Solved {
                            value: r.get(1)?,
                            cost: r.get::<_, i64>(2)? as u64,
                            turns_left: r.get::<_, i64>(3)? as u16,
                            dist: None,
                            options: r.get::<_, Option<Vec<u8>>>(4)?.map(|b| {
                                let mut o = options_from_blob(&state, &b);
                                o.iter_mut().for_each(|o| o.dist = None);
                                o
                            }),
                        },
                    ))
                })
            })
            .collect()
    }

    /// Enforces `max_gb` (`evict`); run at the end of a run.
    pub fn enforce_cap(&self) -> Result<Evicted> {
        self.evict((self.max_gb * 1e9) as u64)
    }

    /// Over `max_bytes`, deletes rows until the database is under 90% of it:
    /// other rules versions' rows first, then the cheapest to re-solve
    /// (lowest cost), with the positions that point at them. Then compacts
    /// the file. Under the cap, deletes nothing.
    pub fn evict(&self, max_bytes: u64) -> Result<Evicted> {
        let conn = connect(&self.path)?;
        conn.query_row("PRAGMA wal_checkpoint(TRUNCATE)", [], |_| Ok(()))?;
        let before = used_bytes(&conn)?;
        let mut out = Evicted { bytes_before: before, bytes_after: before, other_versions: 0, current: 0 };
        if before <= max_bytes {
            return Ok(out);
        }
        let target = (max_bytes as f64 * 0.9) as u64;
        // Other versions' trivial rows are never used: all go first. The
        // current version's stay (about 30 bytes each); its full rows go.
        out.other_versions += conn.execute("DELETE FROM trivial WHERE version != ?1", [self.version])? as u64;
        let orders = [
            ("version != ?1", "ORDER BY version, cost, id"),
            ("version = ?1", "ORDER BY cost, id"),
        ];
        for (k, (cond, order)) in orders.into_iter().enumerate() {
            loop {
                let used = used_bytes(&conn)?;
                let rows: i64 = conn.query_row("SELECT COUNT(*) FROM states", [], |r| r.get(0))?;
                if used <= target || rows == 0 {
                    break;
                }
                // About enough rows to get under the target, at the
                // database's mean bytes per row.
                let batch = (((used - target) as f64 / (used as f64 / rows as f64)).ceil() as i64).max(1);
                let sel = format!("SELECT id FROM states WHERE {cond} {order} LIMIT {batch}");
                conn.execute_batch("BEGIN IMMEDIATE")?;
                let pos = format!("DELETE FROM positions WHERE state IN ({sel})");
                conn.execute(&pos, [self.version])?;
                let n = conn.execute(&format!("DELETE FROM states WHERE id IN ({sel})"), [self.version])?;
                conn.execute_batch("COMMIT")?;
                if n == 0 {
                    break;
                }
                if k == 0 {
                    out.other_versions += n as u64;
                } else {
                    out.current += n as u64;
                }
            }
        }
        conn.execute_batch("VACUUM")?;
        conn.query_row("PRAGMA wal_checkpoint(TRUNCATE)", [], |_| Ok(()))?;
        out.bytes_after = used_bytes(&conn)?;
        Ok(out)
    }

    /// Moves the trivial rows (`is_trivial`) of `states` that no position
    /// points at into `trivial`, then compacts the file (Amendment 1). Run
    /// once by hand, with no other process using the database: the moved
    /// rows' bytes, options and distributions are gone (they can be solved
    /// again).
    pub fn compact(&self) -> Result<Compacted> {
        let mut conn = connect(&self.path)?;
        conn.query_row("PRAGMA wal_checkpoint(TRUNCATE)", [], |_| Ok(()))?;
        let bytes_before = used_bytes(&conn)?;
        let kept: HashSet<i64> = {
            let mut q = conn.prepare("SELECT state FROM positions")?;
            let ids = q.query_map([], |r| r.get(0))?.collect::<Result<_>>()?;
            ids
        };
        let mut moved = 0;
        let mut last = 0i64;
        loop {
            let tx = conn.transaction_with_behavior(TransactionBehavior::Immediate)?;
            let batch: Vec<(i64, i64, i64, Vec<u8>, Solved)> = {
                let mut q = tx.prepare_cached(
                    "SELECT id, version, key_hash, state, value, cost, turns_left, options FROM states
                     WHERE id > ?1 ORDER BY id LIMIT 10000",
                )?;
                let rows = q.query_map([last], |r| {
                    let state: Vec<u8> = r.get(3)?;
                    let solved = Solved {
                        value: r.get(4)?,
                        cost: r.get::<_, i64>(5)? as u64,
                        turns_left: r.get::<_, i64>(6)? as u16,
                        dist: None,
                        options: r.get::<_, Option<Vec<u8>>>(7)?.map(|b| options_from_blob(&state, &b)),
                    };
                    Ok((r.get(0)?, r.get(1)?, r.get(2)?, state, solved))
                })?;
                rows.collect::<Result<_>>()?
            };
            let Some(&(end, ..)) = batch.last() else { break };
            {
                let mut ins = tx.prepare_cached(
                    "INSERT OR IGNORE INTO trivial (version, key_hash, check_hash, value, cost, turns_left)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
                )?;
                let mut del = tx.prepare_cached("DELETE FROM states WHERE id = ?1")?;
                for (id, version, key_hash, state, s) in &batch {
                    if kept.contains(id) || !is_trivial(s) {
                        continue;
                    }
                    ins.execute(params![version, key_hash, fnv1a32(state) as i64, s.value, s.cost as i64, s.turns_left as i64])?;
                    del.execute([id])?;
                    moved += 1;
                }
            }
            tx.commit()?;
            last = end;
        }
        conn.execute_batch("VACUUM")?;
        conn.query_row("PRAGMA wal_checkpoint(TRUNCATE)", [], |_| Ok(()))?;
        Ok(Compacted { bytes_before, bytes_after: used_bytes(&conn)?, moved })
    }

    /// Repairs the current version's costs written under the old rule,
    /// which summed hits' overlapping costs (docs/decisions.md, "Solved-state
    /// cost"): a row costing over `max_cost` (one solve's node budget, so
    /// only hits could have added the excess) or wrapped below 0 gets one
    /// more than its costliest child's cost, children repaired first. A
    /// child with no row cost under `min_nodes` and counts 0. The row's own
    /// expansions are lost, so the result is the new rule's lower bound
    /// without them (at most `max_cost` too low). A bad `trivial` row is
    /// repaired when a repaired state reaches it (it has no state bytes to
    /// start from); the rest are set to `max_cost`. Run once by hand, with
    /// no other process using the database.
    pub fn repair_costs(&self, max_cost: u64) -> Result<Repaired> {
        let mut conn = connect(&self.path)?;
        let bad = |c: i64| c < 0 || c as u64 > max_cost;
        let roots: Vec<(i64, Vec<u8>)> = {
            let mut q = conn.prepare("SELECT id, state FROM states WHERE version = ?1 AND (cost < 0 OR cost > ?2)")?;
            let rows = q.query_map(params![self.version, max_cost as i64], |r| Ok((r.get(0)?, r.get(1)?)))?;
            rows.collect::<Result<_>>()?
        };
        let bad_trivial: HashSet<i64> = {
            let mut q = conn.prepare("SELECT key_hash FROM trivial WHERE version = ?1 AND (cost < 0 OR cost > ?2)")?;
            let rows = q.query_map(params![self.version, max_cost as i64], |r| r.get(0))?;
            rows.collect::<Result<_>>()?
        };
        // Each state's (repaired) cost by key hash, and the rows to rewrite.
        let mut memo: HashMap<u64, u64> = HashMap::new();
        let mut fixed_states: Vec<(i64, u64)> = Vec::new();
        let mut fixed_trivial: Vec<(i64, u64)> = Vec::new();
        for (id, bytes) in roots {
            if memo.contains_key(&fnv1a(&bytes)) {
                continue; // repaired as another row's child
            }
            // Children first, on an explicit stack: chains run a game long.
            let mut stack = vec![RepairFrame::open(Row::State(id), bytes)];
            while let Some(top) = stack.last_mut() {
                if let Some(kid) = top.kids.pop() {
                    let h = fnv1a(&kid);
                    let c = match memo.get(&h) {
                        Some(&c) => c,
                        None => match row_cost(&conn, self.version, &self.snap, &kid)? {
                            Some((row, c)) if bad(c) => {
                                if !stack.iter().any(|f| f.hash == h) {
                                    stack.push(RepairFrame::open(row, kid));
                                }
                                continue;
                            }
                            found => {
                                let c = found.map_or(0, |(_, c)| c as u64);
                                memo.insert(h, c);
                                c
                            }
                        },
                    };
                    let top = stack.last_mut().unwrap();
                    top.best = top.best.max(c);
                } else {
                    let f = stack.pop().unwrap();
                    let c = f.best.saturating_add(1);
                    memo.insert(f.hash, c);
                    match f.row {
                        Row::State(id) => fixed_states.push((id, c)),
                        Row::Trivial(h) => fixed_trivial.push((h, c)),
                    }
                    if let Some(parent) = stack.last_mut() {
                        parent.best = parent.best.max(c);
                    }
                }
            }
        }
        let reached: HashSet<i64> = fixed_trivial.iter().map(|&(h, _)| h).collect();
        let clamped: Vec<i64> = bad_trivial.into_iter().filter(|h| !reached.contains(h)).collect();
        let tx = conn.transaction_with_behavior(TransactionBehavior::Immediate)?;
        {
            let mut st = tx.prepare("UPDATE states SET cost = ?1 WHERE id = ?2")?;
            for &(id, c) in &fixed_states {
                st.execute(params![c.min(i64::MAX as u64) as i64, id])?;
            }
            let mut tr = tx.prepare("UPDATE trivial SET cost = ?1 WHERE version = ?2 AND key_hash = ?3")?;
            for &(h, c) in &fixed_trivial {
                tr.execute(params![c.min(i64::MAX as u64) as i64, self.version, h])?;
            }
            for &h in &clamped {
                tr.execute(params![max_cost as i64, self.version, h])?;
            }
        }
        tx.commit()?;
        Ok(Repaired { states: fixed_states.len() as u64, trivial: fixed_trivial.len() as u64, clamped: clamped.len() as u64 })
    }
}

/// Which row a repaired cost goes to: a `states` id or a `trivial` key hash.
#[derive(Clone, Copy)]
enum Row {
    State(i64),
    Trivial(i64),
}

/// A state being repaired: its children (codec bytes) not yet looked at,
/// and the costliest so far.
struct RepairFrame {
    row: Row,
    hash: u64,
    kids: Vec<Vec<u8>>,
    best: u64,
}

impl RepairFrame {
    /// The solver's children: a decision's distinct afterstates, a random
    /// event's outcomes; finished ones cost nothing and aren't listed.
    fn open(row: Row, bytes: Vec<u8>) -> RepairFrame {
        let s = decode(&bytes);
        let kids: Vec<CombatState> = if s.awaiting_action() {
            group_options(&s).into_iter().map(|(after, _)| after).collect()
        } else {
            match s.chance_outcomes(usize::MAX) {
                Some(ChanceOutcomes::Listed(v)) => v.into_iter().map(|(_, k)| k).collect(),
                _ => Vec::new(),
            }
        };
        let kids = kids.iter().filter(|k| !k.is_over()).map(encode).collect();
        RepairFrame { row, hash: fnv1a(&bytes), kids, best: 0 }
    }
}

/// The row holding `bytes` (current version, as the handle saw it) and its
/// stored cost, found as `read_row` finds it.
fn row_cost(conn: &Connection, version: i64, snap: &Snapshot, bytes: &[u8]) -> Result<Option<(Row, i64)>> {
    let h = fnv1a(bytes);
    if snap.has(h) {
        let mut q = conn.prepare_cached("SELECT id, state, cost FROM states WHERE version = ?1 AND key_hash = ?2 AND id <= ?3")?;
        let mut rows = q.query(params![version, h as i64, snap.max_id])?;
        while let Some(r) = rows.next()? {
            if r.get::<_, Vec<u8>>(1)? == bytes {
                return Ok(Some((Row::State(r.get(0)?), r.get(2)?)));
            }
        }
    }
    if !snap.has_trivial(h) {
        return Ok(None);
    }
    let row: Option<(i64, i64)> = conn
        .prepare_cached("SELECT check_hash, cost FROM trivial WHERE version = ?1 AND key_hash = ?2")?
        .query_row(params![version, h as i64], |r| Ok((r.get(0)?, r.get(1)?)))
        .optional()?;
    Ok(row.filter(|r| r.0 as u32 == fnv1a32(bytes)).map(|(_, c)| (Row::Trivial(h as i64), c)))
}

/// The row for `bytes` in `version` as a handle with `snap` saw it at open.
fn read_row(conn: &Connection, version: i64, snap: &Snapshot, hasher: fn(&[u8]) -> u64, bytes: &[u8]) -> Result<Option<Solved>> {
    let h = hasher(bytes);
    if snap.has(h) {
        if let Some(solved) = read_full(conn, version, snap, h, bytes)? {
            return Ok(Some(solved));
        }
    }
    if !snap.has_trivial(h) {
        return Ok(None);
    }
    let row: Option<(i64, f64, i64, i64)> = conn
        .prepare_cached("SELECT check_hash, value, cost, turns_left FROM trivial WHERE version = ?1 AND key_hash = ?2")?
        .query_row(params![version, h as i64], |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?)))
        .optional()?;
    // Confirmed on 96 bits (key and check hashes) instead of the bytes: a
    // wrong value is practically, not provably, impossible.
    let Some((_, value, cost, turns_left)) = row.filter(|r| r.0 as u32 == fnv1a32(bytes)) else { return Ok(None) };
    // Its options are rebuilt from the state as the solver groups them,
    // each at its value.
    let s = decode(bytes);
    let options = s
        .awaiting_action()
        .then(|| group_options(&s).into_iter().map(|(_, actions)| SolvedOption { actions, value, dist: None, bounded: false }).collect());
    Ok(Some(Solved { value, cost: cost as u64, turns_left: turns_left as u16, dist: None, options }))
}

/// The full `states` row for `bytes` (key hash `h`), as the handle saw it.
fn read_full(conn: &Connection, version: i64, snap: &Snapshot, h: u64, bytes: &[u8]) -> Result<Option<Solved>> {
    let mut q = conn.prepare_cached(
        "SELECT id, state, value, cost, turns_left, dist, options FROM states
         WHERE version = ?1 AND key_hash = ?2 AND id <= ?3",
    )?;
    let mut rows = q.query(params![version, h as i64, snap.max_id])?;
    while let Some(r) = rows.next()? {
        let state: Vec<u8> = r.get(1)?;
        // A hash collision is a miss, never a wrong value.
        if state != bytes {
            continue;
        }
        let id: i64 = r.get(0)?;
        let mut solved = Solved {
            value: r.get(2)?,
            cost: r.get::<_, i64>(3)? as u64,
            turns_left: r.get::<_, i64>(4)? as u16,
            dist: r.get::<_, Option<Vec<u8>>>(5)?.map(|b| dist_from_blob(&b)),
            options: r.get::<_, Option<Vec<u8>>>(6)?.map(|b| options_from_blob(&state, &b)),
        };
        // Distributions added after open aren't seen either.
        if snap.dist_ids.binary_search(&id).is_err() {
            solved.dist = None;
            for o in solved.options.iter_mut().flatten() {
                o.dist = None;
            }
        }
        return Ok(Some(solved));
    }
    Ok(None)
}

/// Bytes in use: pages minus free pages.
fn used_bytes(conn: &Connection) -> Result<u64> {
    let pages: i64 = conn.query_row("PRAGMA page_count", [], |r| r.get(0))?;
    let free: i64 = conn.query_row("PRAGMA freelist_count", [], |r| r.get(0))?;
    let size: i64 = conn.query_row("PRAGMA page_size", [], |r| r.get(0))?;
    Ok(((pages - free) * size) as u64)
}

fn file_bytes(path: &Path) -> u64 {
    std::fs::metadata(path).map_or(0, |m| m.len())
}

#[derive(Clone, Debug)]
pub struct VersionRows {
    pub id: i64,
    pub fingerprint: String,
    /// Its `states` rows.
    pub rows: u64,
    /// Its `trivial` rows.
    pub trivial: u64,
    /// This handle's rules version.
    pub current: bool,
}

#[derive(Clone, Debug)]
pub struct Stats {
    /// Bytes in use (pages minus free pages).
    pub bytes: u64,
    /// The main file's size on disk.
    pub file_bytes: u64,
    pub versions: Vec<VersionRows>,
    /// (table, bytes with its indexes).
    pub tables: Vec<(String, u64)>,
    pub positions: u64,
    /// (quantile, cost) for the current version's rows.
    pub cost_quantiles: Vec<(f64, u64)>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Evicted {
    pub bytes_before: u64,
    pub bytes_after: u64,
    pub other_versions: u64,
    pub current: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Compacted {
    pub bytes_before: u64,
    pub bytes_after: u64,
    /// Rows moved from `states` to `trivial`.
    pub moved: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Repaired {
    /// `states` rows given their children's cost.
    pub states: u64,
    /// `trivial` rows given their children's cost.
    pub trivial: u64,
    /// `trivial` rows no repaired state reached, set to `max_cost`.
    pub clamped: u64,
}

/// A played position (puzzle) to record.
#[derive(Clone, Debug)]
pub struct Position<'a> {
    /// `bench` or a registry run id.
    pub source: &'a str,
    /// The game's spec, as text.
    pub spec: &'a str,
    /// The action prefix leading to it, as text.
    pub prefix: &'a str,
    /// Its index in the game's action list.
    pub step: u32,
    /// The played game's final turn minus the decision's turn.
    pub horizon: u32,
    /// Best minus second-best option value.
    pub gap: f64,
}

/// A recorded position as read back from the database.
#[derive(Clone, Debug)]
pub struct PositionRow {
    /// The state's codec bytes.
    pub state: Vec<u8>,
    pub spec: String,
    pub prefix: String,
    pub step: u32,
    pub horizon: u32,
    pub gap: f64,
    pub options: Vec<SolvedOption>,
}

/// One game's store over the database: a `MemoryStore` in front, the rows
/// the handle saw at open behind. Offered states that cost at least
/// `min_nodes` are written when each solve ends, in one transaction.
pub struct DbStore {
    mem: MemoryStore,
    conn: Connection,
    version: i64,
    snap: Arc<Snapshot>,
    hasher: fn(&[u8]) -> u64,
    /// Trivial states go to `trivial` (false: every row in full, as schema 1).
    split_trivial: bool,
    pending: Vec<(Vec<u8>, Solved)>,
    /// Lookups answered by the database (not memory).
    pub db_hits: u64,
}

impl DbStore {
    pub fn min_nodes(&self) -> u64 {
        self.mem.min_nodes
    }

    /// The row for `bytes` as the handle saw it at open.
    fn row(&self, bytes: &[u8]) -> Result<Option<Solved>> {
        read_row(&self.conn, self.version, &self.snap, self.hasher, bytes)
    }

    /// Writes the pending states in one transaction: trivial ones to
    /// `trivial`, the rest in full (`write_full`).
    pub fn flush(&mut self) -> Result<()> {
        if self.pending.is_empty() {
            return Ok(());
        }
        let tx = self.conn.transaction_with_behavior(TransactionBehavior::Immediate)?;
        {
            let mut ins = tx.prepare_cached(
                "INSERT OR IGNORE INTO trivial (version, key_hash, check_hash, value, cost, turns_left)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            )?;
            let t = now();
            for (bytes, s) in &self.pending {
                let h = (self.hasher)(bytes);
                if self.split_trivial && is_trivial(s) {
                    ins.execute(params![self.version, h as i64, fnv1a32(bytes) as i64, s.value, s.cost as i64, s.turns_left as i64])?;
                } else {
                    write_full(&tx, self.version, h, bytes, s, t)?;
                }
            }
        }
        tx.commit()?;
        self.pending.clear();
        Ok(())
    }

    /// Records a solved decision as a played position: its full state row
    /// (with its options, whatever its cost, trivial or not) and a
    /// `positions` row. Returns whether the position is new for its source.
    pub fn add_position(&mut self, root: &CombatState, sol: &Solution, pos: &Position) -> Result<bool> {
        self.flush()?;
        let bytes = encode(root);
        let solved = Solved {
            value: sol.options.iter().map(|o| o.value).fold(f64::NEG_INFINITY, f64::max),
            cost: sol.cost,
            turns_left: sol.turns_left,
            dist: sol.dist.clone(),
            options: Some(sol.options.clone()),
        };
        // Every puzzle can be rebuilt: a trivial one moves out of `trivial`.
        let h = (self.hasher)(&bytes);
        let tx = self.conn.transaction_with_behavior(TransactionBehavior::Immediate)?;
        write_full(&tx, self.version, h, &bytes, &solved, now())?;
        tx.execute(
            "DELETE FROM trivial WHERE version = ?1 AND key_hash = ?2 AND check_hash = ?3",
            params![self.version, h as i64, fnv1a32(&bytes) as i64],
        )?;
        tx.commit()?;
        let state: i64 = self.conn.query_row(
            "SELECT id FROM states WHERE version = ?1 AND state = ?2",
            params![self.version, bytes],
            |r| r.get(0),
        )?;
        let n = self.conn.execute(
            "INSERT OR IGNORE INTO positions (state, source, spec, prefix, step, horizon, gap)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![state, pos.source, pos.spec, pos.prefix, pos.step, pos.horizon, pos.gap],
        )?;
        Ok(n == 1)
    }

    /// The row id of `root`'s state, if the database has it now.
    pub fn state_id(&self, root: &CombatState) -> Result<Option<i64>> {
        self.conn
            .query_row("SELECT id FROM states WHERE version = ?1 AND state = ?2", params![self.version, encode(root)], |r| {
                r.get(0)
            })
            .optional()
    }
}

/// Writes `s` as a full `states` row. A state already there keeps its row;
/// a distribution is added to a row without one.
fn write_full(conn: &Connection, version: i64, h: u64, bytes: &[u8], s: &Solved, t: i64) -> Result<()> {
    let dist = s.dist.as_ref().map(dist_blob);
    let opts = s.options.as_deref().map(|o| options_blob(bytes, o));
    let n = conn
        .prepare_cached(
            "INSERT OR IGNORE INTO states (version, key_hash, state, value, cost, turns_left, dist, options, solved_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
        )?
        .execute(params![version, h as i64, bytes, s.value, s.cost as i64, s.turns_left as i64, dist, opts, t])?;
    if n == 0 && dist.is_some() {
        conn.prepare_cached("UPDATE states SET dist = ?1, options = ?2 WHERE version = ?3 AND state = ?4 AND dist IS NULL")?
            .execute(params![dist, opts, version, bytes])?;
    }
    Ok(())
}

impl SolvedStore for DbStore {
    fn lookup(&mut self, s: &CombatState) -> Option<Solved> {
        if let Some(e) = self.mem.lookup(s) {
            return Some(e);
        }
        let solved = self.row(&encode(s)).expect("solved-state database read")?;
        self.db_hits += 1;
        self.mem.insert(s, &solved);
        Some(solved)
    }

    fn keeps(&self, solved: &Solved) -> bool {
        solved.cost >= self.mem.min_nodes
    }

    fn insert(&mut self, s: &CombatState, solved: &Solved) {
        if !self.keeps(solved) {
            return;
        }
        self.mem.insert(s, solved);
        self.pending.push((encode(s), solved.clone()));
    }

    fn end_solve(&mut self) {
        self.flush().expect("solved-state database write");
    }
}
