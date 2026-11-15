"""Value nets over `sts.Features` batches: dataset storage, normalisation,
the nested Deep Sets model, a search evaluator wrapper, and save/load.

A batch dict (from `sts.Features.encode`) has `player` [B,P], `monsters`
[B,5,M], card rows over the whole batch (`cards` [N,C], `card_count`,
`card_pile`, `card_state`) and hook rows (`rows` [R,D], `row_card`,
`row_entity`, `row_state`). The net never sees card or power ids unless the
features were built with `card_repr="ids"`.
"""

import os
import shutil

# Before torch loads: every Rust search thread that calls a net otherwise
# keeps its own OpenMP pool alive, ~300 OS threads per sts.run, until thread
# creation fails. Training still sets its own thread count.
os.environ.setdefault("OMP_NUM_THREADS", "1")
# Likewise MKL's fast memory manager keeps a buffer pool per calling thread
# and leaks it when the thread exits: ~5.6 GB per tight-fight run, until the
# sweep died with MemoryError. Without it MKL allocates per call.
os.environ.setdefault("MKL_DISABLE_FAST_MM", "1")

import sys

import numpy as np
import torch
from torch import nn

import sts

# Rust search threads that call a net take turns on Python's lock, so: torch
# runs each tiny call on one thread (its default pool ignores
# OMP_NUM_THREADS on Windows; training sets its own count), the lock changes
# hands every 0.5 ms instead of 5, and net searches use NET_THREADS runner
# threads (profiled: all threads were slower than 1, about 4 was fastest).
torch.set_num_threads(1)
sys.setswitchinterval(0.0005)
NET_THREADS = min(4, os.cpu_count() or 1)


def job_threads(kw):
    """`sts.run` / `sts.play_on` keyword arguments `kw`, with `threads` set to
    a job's thread cap ($STS_JOB_THREADS, which jobs.py sets to the job's
    --threads) when `kw` names no thread count: Rust searches otherwise use
    every core, crowding the other jobs."""
    n = os.environ.get("STS_JOB_THREADS", "")
    if kw.get("threads") is None and n.isdigit() and int(n) > 0:
        return {**kw, "threads": int(n)}
    return kw


NUM_PILES = len(sts.PILES)
ALIVE = 0  # index of the "alive" flag in a monster vector

# Weight decay drives some weights into denormal floats, which the CPU handles
# far slower; flushing them to zero made CPU training 3.3x faster, same MSE.
torch.set_flush_denormal(True)

# Switch 6 (no-death HP-loss target, Amendment 1): the net predicts a
# histogram over the HP lost from a state to the end of combat. Bins by
# lower edge: 1 HP wide from 0 to 30, 5 wide to 60, 10 wide to 150, one bin
# for >= 150, then a turn-limit bin (the no-death combat hit the turn
# limit). BIN_REP is the HP lost each bin stands for (lower edge of a 1-HP
# bin, midpoint of a wide one, 150 for the last two, which never win).
BIN_LOW = np.array(list(range(30)) + list(range(30, 60, 5)) + list(range(60, 150, 10)) + [150], np.float32)
BIN_REP = np.concatenate([BIN_LOW[:30], (BIN_LOW[30:-1] + BIN_LOW[31:]) / 2, [150.0, 150.0]]).astype(np.float32)
N_BINS = len(BIN_REP)
TURN_LIMIT_BIN = N_BINS - 1
# Bins that can win: all but >= 150 and the turn limit.
WINNABLE = np.arange(N_BINS) < N_BINS - 2


def bin_index(lost):
    """The bin of an HP lost (clamped at 0; >= 150 is the last HP bin)."""
    return int(np.searchsorted(BIN_LOW, max(float(lost), 0.0), side="right")) - 1


# Per-state scalars `sts.Features.encode(heuristic=True)` adds, which switch
# 6 needs (the external formula's inputs).
HP_SCALARS = ("hp", "start_hp", "max_hp", "win_heal")


class Dataset:
    """States stored flat: per-state arrays, card rows grouped by state
    (`card_start`, `card_len`) and hook rows grouped by state (`row_start`,
    `row_len`), plus one target per state (a score, or with switch 6 a
    histogram over HP lost, [N, N_BINS]). A hook row belongs to a card
    (`row_card`: index among its state's cards, else -1) or to an entity
    (`row_ent`: 0 = player, 1 + slot = monster, else -1)."""

    FIELDS = ("player", "monsters", "cards", "card_count", "card_pile", "card_start", "card_len",
              "rows", "row_card", "row_ent", "row_start", "row_len", "target", "group")
    # Per-state extras, None when absent: the example's real outcome label
    # (its game's score, or HP lost with switch 6: what the target would be
    # without search values), and for ranking (switch 3) each example's
    # decision, its option there (-1 for the decision state), the outcome's
    # probability, the option's probability-weighted score of finished
    # outcomes, and the option's search value.
    # Switch 6 adds the HP scalars of each state (HP_SCALARS). `weight` is
    # each example's value-loss weight (None: every weight 1; 0 keeps an
    # example in the ranking term only).
    # The label inputs (curriculum, cache v6): `search`, the example's
    # recorded search number (a decision's best option value, an
    # afterstate's option value; NaN when the game has none), `kind` (0 a
    # decision state, else its option's KINDS code), `played` (1 when the
    # example is the decision or the played option's afterstate) and
    # `distance` (the game's last decision turn minus the state's turn; an
    # afterstate takes its decision's).
    # `bounded` (solver bounds): 0 when the example's option value
    # (`rank_value`) is exact; 1 when it is an upper bound and the example's
    # target is that bound (the value loss is one-sided); 2 when it is an
    # upper bound but the target is something else (ranking only). A part
    # without it counts as all 0 beside parts with it (ZERO_FILL).
    EXTRA = ("outcome", "decision", "option", "prob", "opt_const", "rank_value") + HP_SCALARS + (
        "weight", "search", "kind", "played", "distance", "bounded")
    ZERO_FILL = ("bounded",)
    EXTRA_DTYPES = {"outcome": np.float32, "decision": np.int64, "option": np.int16, "prob": np.float32,
                    "opt_const": np.float32, "rank_value": np.float32, **{k: np.float32 for k in HP_SCALARS},
                    "weight": np.float32, "search": np.float32, "kind": np.int8, "played": np.int8,
                    "distance": np.int16, "bounded": np.int8}
    KINDS = {"deterministic": 1, "chance": 2, "divergent": 3}
    # Each example's state as codec bytes (`Combat.encode`), stored ragged
    # like the cards: flat `codec`, per state `codec_start` and `codec_len`.
    # None when absent; label loading drops them before training.
    CODEC = ("codec", "codec_start", "codec_len")

    def __init__(self, player, monsters, cards, card_count, card_pile, card_start, card_len,
                 rows, row_card, row_ent, row_start, row_len, target, group=None,
                 codec=None, codec_start=None, codec_len=None, **extra):
        self.player, self.monsters = player, monsters
        self.cards, self.card_count, self.card_pile = cards, card_count, card_pile
        self.card_start, self.card_len = card_start, card_len
        self.rows, self.row_card, self.row_ent = rows, row_card, row_ent
        self.row_start, self.row_len = row_start, row_len
        self.target = target
        self.group = group if group is not None else np.zeros(len(target), np.int64)
        for k in Dataset.EXTRA:
            v = extra.get(k)
            setattr(self, k, None if v is None else np.asarray(v, Dataset.EXTRA_DTYPES[k]))
        if isinstance(codec, list):  # a list of bytes per state
            codec, codec_start, codec_len = Dataset.pack_codec(codec)
        self.codec, self.codec_start, self.codec_len = codec, codec_start, codec_len

    @staticmethod
    def pack_codec(codes):
        """(flat uint8, starts, lengths) of a list of bytes."""
        lens = np.array([len(c) for c in codes], np.int64)
        starts = np.concatenate([[0], np.cumsum(lens)[:-1]]).astype(np.int64)
        return np.frombuffer(b"".join(codes), np.uint8).copy(), starts, lens

    def codec_bytes(self, i):
        """Example i's state as codec bytes."""
        s = int(self.codec_start[i])
        return self.codec[s:s + int(self.codec_len[i])].tobytes()

    def drop_codec(self):
        self.codec = self.codec_start = self.codec_len = None

    def __len__(self):
        return len(self.target)

    @staticmethod
    def concat(parts):
        """One dataset holding every part's states in order (self-play rounds
        train on several datasets); decision ids stay distinct per part."""
        a = {}
        for k in Dataset.FIELDS:
            a[k] = np.concatenate([getattr(d, k) for d in parts])
        cards = np.cumsum([0] + [len(d.cards) for d in parts[:-1]])
        rows = np.cumsum([0] + [len(d.rows) for d in parts[:-1]])
        a["card_start"] = np.concatenate([d.card_start + o for d, o in zip(parts, cards)])
        a["row_start"] = np.concatenate([d.row_start + o for d, o in zip(parts, rows)])
        extra = {}
        for k in Dataset.EXTRA:
            if all(getattr(d, k) is not None for d in parts) or (
                    k in Dataset.ZERO_FILL and any(getattr(d, k) is not None for d in parts)):
                vals = [_or_zeros(d, k, np.arange(len(d))) for d in parts]
                if k == "decision":
                    off = np.cumsum([0] + [int(v.max()) + 1 if len(v) else 0 for v in vals[:-1]])
                    vals = [np.where(v >= 0, v + o, v) for v, o in zip(vals, off)]
                extra[k] = np.concatenate(vals)
        if all(d.codec is not None for d in parts):
            off = np.cumsum([0] + [len(d.codec) for d in parts[:-1]])
            extra["codec"] = np.concatenate([d.codec for d in parts])
            extra["codec_start"] = np.concatenate([d.codec_start + o for d, o in zip(parts, off)])
            extra["codec_len"] = np.concatenate([d.codec_len for d in parts])
        return Dataset(**a, **extra)

    @staticmethod
    def from_batches(batches, target, group=None, extra=None):
        """`extra`: per-state EXTRA arrays; the HP scalars come from the
        batches when every batch has them."""
        parts = {k: [] for k in Dataset.FIELDS[:-2]}
        n_cards = n_rows = 0
        for b in batches:
            n = b["player"].shape[0]
            order = np.argsort(b["card_state"], kind="stable")
            clen = np.bincount(b["card_state"], minlength=n)
            cfirst = np.concatenate([[0], np.cumsum(clen)[:-1]])
            pos = np.empty(len(order), np.int64)
            pos[order] = np.arange(len(order))  # card index in b -> sorted position
            rorder = np.argsort(b["row_state"], kind="stable")
            rs, rc, re = b["row_state"][rorder], b["row_card"][rorder], b["row_entity"][rorder]
            local = np.where(rc >= 0, pos[np.maximum(rc, 0)] - cfirst[rs], -1)
            ent = np.where(re >= 0, re - rs * sts.ENTITIES, -1)
            rlen = np.bincount(rs, minlength=n)
            parts["player"].append(b["player"])
            parts["monsters"].append(b["monsters"])
            parts["cards"].append(b["cards"][order].astype(np.float16))  # small integers: exact
            parts["card_count"].append(b["card_count"][order])
            parts["card_pile"].append(b["card_pile"][order].astype(np.int8))
            parts["card_start"].append(n_cards + cfirst)
            parts["card_len"].append(clen)
            parts["rows"].append(b["rows"][rorder].astype(np.float16))
            parts["row_card"].append(local.astype(np.int16))
            parts["row_ent"].append(ent.astype(np.int8))
            parts["row_start"].append(n_rows + np.concatenate([[0], np.cumsum(rlen)[:-1]]))
            parts["row_len"].append(rlen)
            n_cards += len(order)
            n_rows += len(rorder)
        a = {k: np.concatenate(v) for k, v in parts.items()}
        for k in ("card_start", "card_len", "row_start", "row_len"):
            a[k] = a[k].astype(np.int64)
        extra = dict(extra or {})
        for k in HP_SCALARS:
            if batches and all(k in b for b in batches):
                extra.setdefault(k, np.concatenate([b[k] for b in batches]))
        return Dataset(**a, target=np.asarray(target, np.float32),
                       group=None if group is None else np.asarray(group, np.int64), **extra)

    @staticmethod
    def _gather(starts, lens):
        """Flat indices of the runs (starts, lens), and each run's offset in them."""
        offs = np.concatenate([[0], np.cumsum(lens)[:-1]])
        return np.repeat(starts - offs, lens) + np.arange(lens.sum()), offs

    def batch(self, idx):
        """The batch dict for states `idx` (plus `target`), same layout as
        `sts.Features.encode`."""
        idx = np.asarray(idx)
        clens, rlens = self.card_len[idx], self.row_len[idx]
        cards, coffs = self._gather(self.card_start[idx], clens)
        rows, _ = self._gather(self.row_start[idx], rlens)
        rstate = np.repeat(np.arange(len(idx)), rlens)
        local = self.row_card[rows].astype(np.int64)
        ent = self.row_ent[rows].astype(np.int64)
        return {
            "player": self.player[idx],
            "monsters": self.monsters[idx],
            "cards": self.cards[cards].astype(np.float32),
            "card_count": self.card_count[cards],
            "card_pile": self.card_pile[cards].astype(np.int64),
            "card_state": np.repeat(np.arange(len(idx)), clens),
            "rows": self.rows[rows].astype(np.float32),
            "row_card": np.where(local >= 0, local + coffs[rstate], -1),
            "row_entity": np.where(ent >= 0, rstate * sts.ENTITIES + ent, -1),
            "row_state": rstate,
            "target": self.target[idx],
            **{k: getattr(self, k)[idx] for k in Dataset.EXTRA if getattr(self, k) is not None},
        }

    def subset(self, idx):
        b = self.batch(idx)
        return Dataset.from_batches([b], b["target"], self.group[idx],
                                    {k: b[k] for k in Dataset.EXTRA if k in b})

    def take(self, idx):
        """The examples `idx`, in order, gathered in storage form (no float32
        batch in between, so sampling a large pool stays cheap)."""
        idx = np.asarray(idx)
        clens, rlens = self.card_len[idx], self.row_len[idx]
        cards, _ = self._gather(self.card_start[idx], clens)
        rows, _ = self._gather(self.row_start[idx], rlens)
        a = {k: getattr(self, k)[idx] for k in ("player", "monsters", "target", "group")}
        a.update({k: getattr(self, k)[cards] for k in ("cards", "card_count", "card_pile")})
        a.update({k: getattr(self, k)[rows] for k in ("rows", "row_card", "row_ent")})
        a["card_start"] = np.concatenate([[0], np.cumsum(clens)[:-1]]).astype(np.int64)
        a["row_start"] = np.concatenate([[0], np.cumsum(rlens)[:-1]]).astype(np.int64)
        extra = {k: getattr(self, k)[idx] for k in Dataset.EXTRA if getattr(self, k) is not None}
        if self.codec is not None:
            lens = self.codec_len[idx]
            flat, _ = self._gather(self.codec_start[idx], lens)
            extra.update(codec=self.codec[flat], codec_len=lens,
                         codec_start=np.concatenate([[0], np.cumsum(lens)[:-1]]).astype(np.int64))
        return Dataset(**a, card_len=clens, row_len=rlens, **extra)

    def arrays(self):
        """{name: array} of everything stored (FIELDS, present EXTRA and CODEC)."""
        extra = {k: getattr(self, k) for k in Dataset.EXTRA + Dataset.CODEC if getattr(self, k) is not None}
        return {**{k: getattr(self, k) for k in Dataset.FIELDS}, **extra}

    def save(self, path):
        np.savez(path, **self.arrays())

    @staticmethod
    def load(path):
        """From an .npz file, or memory-mapped (read-only) from a directory
        DatasetWriter wrote: arrays are read from disk as they are touched."""
        if os.path.isdir(path):
            z = {n[:-4]: _load_npy(os.path.join(path, n)) for n in os.listdir(path) if n.endswith(".npy")}
            names = z.keys()
        else:
            z = np.load(path)
            names = z.files
        d = Dataset(*(z[k] for k in Dataset.FIELDS),
                    **{k: z[k] for k in Dataset.EXTRA + Dataset.CODEC if k in names})
        d.source = path if os.path.isdir(path) else None
        return d

    def take_unmapped(self, idx):
        """`take(idx)` read through a fresh memory map of the directory this
        dataset was loaded from, dropped after, so the pages read leave the
        process's working set (a large replay pool sampled each epoch stays
        on disk). Per-example arrays this object holds in memory (a
        re-weighted target) are taken from it. Not loaded from a directory:
        `take`."""
        if getattr(self, "source", None) is None:
            return self.take(idx)
        idx = np.asarray(idx)
        out = Dataset.load(self.source).take(idx)
        for k in ("player", "monsters", "target", "group") + Dataset.EXTRA:
            v = getattr(self, k)
            if v is not None and not _mapped(v):
                setattr(out, k, v[idx])
        return out


def _mapped(a):
    """Whether array `a`, or an array it views, is a memory map."""
    while a is not None:
        if isinstance(a, np.memmap):
            return True
        a = getattr(a, "base", None)
    return False


def npz_to_dir(npz, path):
    """Copies a Dataset's .npz cache into the directory form DatasetWriter
    writes (memory-mappable), one array in memory at a time."""
    z = np.load(npz)
    w = DatasetWriter(path)
    for k in z.files:
        w._write(k, np.ascontiguousarray(z[k]))
    return w.close()


def _load_npy(path):
    try:
        return np.load(path, mmap_mode="r")
    except ValueError:  # an empty array can't be mapped
        return np.load(path)


def _or_zeros(d, k, idx):
    """Field `k` of dataset `d` at `idx`, zeros when `d` lacks it."""
    v = getattr(d, k)
    return np.zeros(len(idx), Dataset.EXTRA_DTYPES[k]) if v is None else v[idx]


class DatasetWriter:
    """Writes a Dataset into a directory, one uncompressed .npy per array,
    a part at a time (`append`), so building a large cache holds one part
    at a time. Each file starts with a fixed-size header (NPY_HEADER bytes)
    rewritten with the final shape by `close`, which then renames the
    temporary directory to `path`: a crash leaves no half cache. Returns
    False from `close` when another process finished the same `path` first
    (its copy is kept)."""

    NPY_HEADER = 256

    def __init__(self, path):
        self.path = path
        self.tmp = f"{path}.tmp{os.getpid()}"
        if os.path.exists(self.tmp):
            shutil.rmtree(self.tmp)
        os.makedirs(self.tmp)
        self.files = {}  # name -> [file, dtype, trailing shape, rows]
        self.offsets = {"card_start": 0, "row_start": 0, "codec_start": 0}

    def append(self, d):
        a = d.arrays()
        a["card_start"] = a["card_start"] + self.offsets["card_start"]
        a["row_start"] = a["row_start"] + self.offsets["row_start"]
        if d.codec is not None:
            a["codec_start"] = a["codec_start"] + self.offsets["codec_start"]
            self.offsets["codec_start"] += len(d.codec)
        self.offsets["card_start"] += len(d.cards)
        self.offsets["row_start"] += len(d.rows)
        for k, v in a.items():
            self._write(k, np.ascontiguousarray(v))

    def _write(self, name, v):
        if name not in self.files:
            f = open(os.path.join(self.tmp, name + ".npy"), "wb")
            f.write(b"\0" * self.NPY_HEADER)
            self.files[name] = [f, v.dtype, v.shape[1:], 0]
        entry = self.files[name]
        if v.dtype != entry[1] or v.shape[1:] != entry[2]:
            raise ValueError(f"{name}: {v.dtype}{v.shape[1:]} after {entry[1]}{entry[2]}")
        entry[0].write(v.tobytes())
        entry[3] += len(v)

    def _header(self, dtype, shape):
        d = repr({"descr": np.lib.format.dtype_to_descr(dtype), "fortran_order": False, "shape": shape})
        body = d.encode("latin1")
        pad = self.NPY_HEADER - 10 - len(body) - 1
        if pad < 0:
            raise ValueError("npy header too long")
        h = body + b" " * pad + b"\n"
        return b"\x93NUMPY\x01\x00" + len(h).to_bytes(2, "little") + h

    def abandon(self):
        """Deletes what was written; `path` stays as it was."""
        for f, *_ in self.files.values():
            f.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # Arrays with one row per card, hook row or codec byte; every other
    # array has one row per example.
    FLAT_ARRAYS = ("cards", "card_count", "card_pile", "rows", "row_card", "row_ent", "codec")

    def close(self):
        per_example = {k: e[3] for k, e in self.files.items() if k not in self.FLAT_ARRAYS}
        if len(set(per_example.values())) > 1:
            self.abandon()
            raise ValueError(f"per-example arrays of different lengths: {per_example}")
        for f, dtype, trailing, rows in self.files.values():
            f.seek(0)
            f.write(self._header(dtype, (rows,) + tuple(trailing)))
            f.close()
        try:
            os.replace(self.tmp, self.path)
        except OSError:
            if not os.path.isdir(self.path):
                raise
            shutil.rmtree(self.tmp, ignore_errors=True)  # another process built it first
            return False
        return True


class DatasetView:
    """The training set of several parts as one Dataset, without copying
    their examples (curriculum Amendment 1): `parts` [(Dataset, indices of
    the examples used or None for all)], usually memory-mapped caches. Per
    example it holds only small arrays in RAM (where it lives, its ragged
    starts and lengths, target, group and the EXTRA fields); `batch` gathers
    the rest from the parts. Everything it returns equals what
    `Dataset.concat` of the parts (each `take`n by its indices) would.
    `tmp_dirs` are deleted by `close`."""

    PER_STATE = ("player", "monsters")
    FLAT = {"card": ("cards", "card_count", "card_pile"), "row": ("rows", "row_card", "row_ent")}

    def __init__(self, parts, tmp_dirs=()):
        self.parts = [d for d, _ in parts]
        self.tmp_dirs = list(tmp_dirs)
        idxs = [np.arange(len(d)) if i is None else np.asarray(i, np.int64) for d, i in parts]
        self.src_part = np.concatenate([np.full(len(i), k, np.int16) for k, i in enumerate(idxs)])
        self.src_local = np.concatenate(idxs)
        for kind, (first, *_) in self.FLAT.items():
            offs = np.cumsum([0] + [len(getattr(d, first)) for d in self.parts])
            setattr(self, f"_{kind}_offs", offs)
            setattr(self, f"{kind}_start", np.concatenate(
                [getattr(d, f"{kind}_start")[i] + o for d, i, o in zip(self.parts, idxs, offs)]).astype(np.int64))
            setattr(self, f"{kind}_len", np.concatenate([getattr(d, f"{kind}_len")[i] for d, i in zip(self.parts, idxs)]))
        self.target = np.concatenate([d.target[i] for d, i in zip(self.parts, idxs)])
        self.group = np.concatenate([d.group[i] for d, i in zip(self.parts, idxs)])
        for k in Dataset.EXTRA:
            if not (all(getattr(d, k) is not None for d in self.parts) or (
                    k in Dataset.ZERO_FILL and any(getattr(d, k) is not None for d in self.parts))):
                setattr(self, k, None)
                continue
            vals = [_or_zeros(d, k, i) for d, i in zip(self.parts, idxs)]
            if k == "decision":
                off = np.cumsum([0] + [int(v.max()) + 1 if len(v) else 0 for v in vals[:-1]])
                vals = [np.where(v >= 0, v + o, v) for v, o in zip(vals, off)]
            setattr(self, k, np.concatenate(vals))
        self.codec = None

    def __len__(self):
        return len(self.target)

    def _state(self, name, idx):
        """Per-state array `name` of view examples `idx`, gathered from the parts."""
        p, loc = self.src_part[idx], self.src_local[idx]
        out = None
        for k in np.unique(p):
            m = p == k
            v = getattr(self.parts[k], name)[loc[m]]
            if out is None:
                out = np.empty((len(idx),) + v.shape[1:], v.dtype)
            out[m] = v
        if out is None:
            v = getattr(self.parts[0], name)
            out = np.empty((0,) + v.shape[1:], v.dtype)
        return out

    def _flat(self, kind, name, flat):
        """Ragged array `name` (`kind` "card" or "row") at global flat indices."""
        offs = getattr(self, f"_{kind}_offs")
        p = np.searchsorted(offs, flat, "right") - 1
        out = None
        for k in np.unique(p):
            m = p == k
            v = getattr(self.parts[k], name)[flat[m] - offs[k]]
            if out is None:
                out = np.empty((len(flat),) + v.shape[1:], v.dtype)
            out[m] = v
        if out is None:
            v = getattr(self.parts[0], name)
            out = np.empty((0,) + v.shape[1:], v.dtype)
        return out

    def batch(self, idx):
        """As Dataset.batch."""
        idx = np.asarray(idx)
        clens, rlens = self.card_len[idx], self.row_len[idx]
        cards, coffs = Dataset._gather(self.card_start[idx], clens)
        rows, _ = Dataset._gather(self.row_start[idx], rlens)
        rstate = np.repeat(np.arange(len(idx)), rlens)
        local = self._flat("row", "row_card", rows).astype(np.int64)
        ent = self._flat("row", "row_ent", rows).astype(np.int64)
        return {
            "player": self._state("player", idx),
            "monsters": self._state("monsters", idx),
            "cards": self._flat("card", "cards", cards).astype(np.float32),
            "card_count": self._flat("card", "card_count", cards),
            "card_pile": self._flat("card", "card_pile", cards).astype(np.int64),
            "card_state": np.repeat(np.arange(len(idx)), clens),
            "rows": self._flat("row", "rows", rows).astype(np.float32),
            "row_card": np.where(local >= 0, local + coffs[rstate], -1),
            "row_entity": np.where(ent >= 0, rstate * sts.ENTITIES + ent, -1),
            "row_state": rstate,
            "target": self.target[idx],
            **{k: getattr(self, k)[idx] for k in Dataset.EXTRA if getattr(self, k) is not None},
        }

    def rows_of(self, name):
        """`name` (player, monsters, cards, rows or "live", the live monster
        slots) as the concatenated Dataset would hold it, read in slices
        (`Normalizer.fit`)."""
        return _ViewRows(self, name)

    def close(self):
        """Lets go of the parts' mapped files and deletes `tmp_dirs`."""
        import gc
        self.parts = []
        gc.collect()
        for d in self.tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)


class _ViewRows:
    """Rows of one array of a DatasetView in the concatenated order,
    sliceable `[i:j]`, for Normalizer.moments."""

    CHUNK = 65536

    def __init__(self, view, name):
        self.view, self.name = view, name
        n = len(view)
        if name in DatasetView.PER_STATE:
            self.starts = None
            self.n = n
            sample = view._state(name, np.arange(min(n, 1)))
        elif name == "live":
            counts = np.zeros(n, np.int64)  # live slots per example, read in chunks
            for i in range(0, n, self.CHUNK):
                m = view._state("monsters", np.arange(i, min(n, i + self.CHUNK)))
                counts[i:i + len(m)] = (m[:, :, ALIVE] > 0).sum(1)
            self.cum = np.concatenate([[0], np.cumsum(counts)])
            self.n = int(self.cum[-1])
            sample = view._state("monsters", np.arange(min(n, 1)))[:, 0]
        else:
            kind = "card" if name == "cards" else "row"
            self.kind = kind
            lens = getattr(view, f"{kind}_len")
            self.cum = np.concatenate([[0], np.cumsum(lens)])
            self.n = int(self.cum[-1])
            sample = view._flat(kind, name, np.zeros(0, np.int64))
        self.shape = (self.n,) + sample.shape[1:]

    def __len__(self):
        return self.n

    def __getitem__(self, s):
        i, j = s.start or 0, min(s.stop, self.n)
        v = self.view
        if self.name in DatasetView.PER_STATE:
            return v._state(self.name, np.arange(i, j))
        if self.name == "live":
            e0 = np.searchsorted(self.cum, i, "right") - 1
            e1 = np.searchsorted(self.cum, j, "left")
            m = v._state("monsters", np.arange(e0, e1))
            live = m[m[:, :, ALIVE] > 0]
            return live[i - self.cum[e0]:j - self.cum[e0]]
        pos = np.arange(i, j)
        e = np.searchsorted(self.cum, pos, "right") - 1
        start = getattr(v, f"{self.kind}_start")
        return v._flat(self.kind, self.name, start[e] + (pos - self.cum[e]))


class Normalizer:
    """Per-dimension mean/std, fitted on training data. Monster stats use
    live slots only; constant dims get std 1 so unseen values stay finite."""

    KEYS = ("player", "monsters", "cards", "rows")

    def __init__(self, stats):
        self.stats = {k: (np.asarray(m, np.float32), np.asarray(s, np.float32)) for k, (m, s) in stats.items()}

    @staticmethod
    def moments(x, chunk=65536):
        """Per-column mean and std (constant columns std 1) in float64,
        accumulated over row chunks: numpy's whole-array std makes float64
        copies of x, ~6 GB on a large training set."""
        if len(x) == 0:
            return np.zeros(x.shape[1]), np.ones(x.shape[1])
        m = np.zeros(x.shape[1])
        for i in range(0, len(x), chunk):
            m += x[i:i + chunk].sum(0, dtype=np.float64)
        m /= len(x)
        v = np.zeros(x.shape[1])
        for i in range(0, len(x), chunk):
            v += ((x[i:i + chunk] - m) ** 2).sum(0)
        s = np.sqrt(v / len(x))
        s[s < 1e-6] = 1.0
        return m, s

    @staticmethod
    def fit(ds):
        if isinstance(ds, DatasetView):  # read in slices, same numbers as the concatenation's
            return Normalizer({k: Normalizer.moments(ds.rows_of("live" if k == "monsters" else k))
                               for k in Normalizer.KEYS})
        live = ds.monsters[ds.monsters[:, :, ALIVE] > 0]
        return Normalizer({"player": Normalizer.moments(ds.player), "monsters": Normalizer.moments(live),
                           "cards": Normalizer.moments(ds.cards), "rows": Normalizer.moments(ds.rows)})

    def tensors(self, b):
        t = {}
        for k in Normalizer.KEYS:
            m, s = self.stats[k]
            t[k] = torch.from_numpy(((b[k] - m) / s).astype(np.float32))
        t["alive"] = torch.from_numpy(b["monsters"][:, :, ALIVE] > 0).float()
        t["card_count"] = torch.from_numpy(np.asarray(b["card_count"], np.float32))
        for k in ("card_pile", "card_state", "row_card", "row_entity"):
            t[k] = torch.from_numpy(np.asarray(b[k], np.int64))
        for k in HP_SCALARS:
            if k in b:
                t[k] = torch.from_numpy(np.asarray(b[k], np.float32))
        return t

    def state_dict(self):
        return {k: (m.tolist(), s.tolist()) for k, (m, s) in self.stats.items()}


def mlp(sizes):
    layers = []
    for a, b in zip(sizes, sizes[1:]):
        layers += [nn.Linear(a, b), nn.ReLU()]
    return nn.Sequential(*layers)


class ValueNet(nn.Module):
    """Nested Deep Sets value net. Hook rows: a shared ψ per row, summed into
    their card or entity. Cards: a shared φ over (card vector, its pooled
    rows), times its count, summed per (state, pile). Monsters: a shared ρ
    over (monster vector, its pooled rows) per live slot, summed and
    max-pooled. Player: an MLP over (player vector, its pooled rows). A head
    MLP gives a score in [0, 2]. Ids features carry no rows, so their pooled
    parts stay zero.

    `hp_loss=True` (switch 6): the head gives log-probabilities [B, N_BINS]
    of a histogram over the HP lost from the state to the end of combat
    instead of a score (`histogram` exponentiates them); `external_score`
    turns the histogram into a score."""

    def __init__(self, dims, width=64, hidden=256, row_width=32, hp_loss=False):
        super().__init__()
        self.dims = dict(dims)
        self.width, self.row_width = width, row_width
        self.hp_loss = hp_loss
        # Pile slots: the net's own (its features' `piles`), not today's PILES.
        self.n_piles = n_piles = self.dims.get("piles", NUM_PILES)
        self.row = mlp([dims["row"], row_width, row_width])
        self.card = mlp([dims["card"] + row_width, width, width])
        self.monster = mlp([dims["monster"] + row_width, width, width])
        self.player = mlp([dims["player"] + row_width, width])
        self.head = nn.Sequential(mlp([n_piles * width + 2 * width + width, hidden, hidden // 2]),
                                  nn.Linear(hidden // 2, N_BINS if hp_loss else 1))

    def forward(self, t):
        b = t["player"].shape[0]
        w, rw = self.width, self.row_width
        psi = self.row(t["rows"])
        on_card, on_ent = t["row_card"] >= 0, t["row_entity"] >= 0
        card_rows = torch.zeros(t["cards"].shape[0], rw).index_add_(0, t["row_card"][on_card], psi[on_card])
        ent_rows = torch.zeros(b * sts.ENTITIES, rw).index_add_(0, t["row_entity"][on_ent], psi[on_ent])
        ent_rows = ent_rows.view(b, sts.ENTITIES, rw)
        phi = self.card(torch.cat([t["cards"], card_rows], 1)) * t["card_count"].unsqueeze(1)
        np_ = self.n_piles
        piles = torch.zeros(b * np_, w).index_add_(0, t["card_state"] * np_ + t["card_pile"], phi)
        mon = self.monster(torch.cat([t["monsters"], ent_rows[:, 1:1 + sts.MAX_MONSTERS]], 2)) * t["alive"].unsqueeze(2)
        me = self.player(torch.cat([t["player"], ent_rows[:, 0]], 1))
        x = torch.cat([piles.view(b, np_ * w), mon.sum(1), mon.max(1).values, me], 1)
        if self.hp_loss:
            return torch.log_softmax(self.head(x), 1)
        return 2 * torch.sigmoid(self.head(x).squeeze(1))


def histogram(model, t):
    """An HP-loss net's histograms [B, N_BINS] for tensors `t`."""
    return model(t).exp()


def win_probability(p, hp):
    """P(win) of a histogram `p` [B, N_BINS] of HP lost: the mass of the
    bins below the current HP."""
    return (p * _win(hp)).sum(1)


def _win(hp, tau=None, rep=None):
    """[B, N_BINS] win indicator per bin: a bin wins when the HP lost it
    stands for (`rep`, default BIN_REP) is below the current HP (never the
    >= 150 and turn-limit bins). `tau` > 0 smooths the step into a sigmoid
    of width tau HP, centred half an HP below the step (bins sit on whole HP)."""
    left = hp.unsqueeze(1) - _rep_tensor(rep)
    win = (left > 0).float() if tau is None else torch.sigmoid((left - 0.5) / tau)
    return win * torch.from_numpy(WINNABLE).float()


def _rep_tensor(rep):
    return torch.from_numpy(BIN_REP if rep is None else np.asarray(rep, np.float32))


# Score rules for HP-loss nets (docs/specs/survival-score.md): "engine" is
# today's 2 - (start HP - end HP) / 100 for a win; "survive" scores a win
# c + w x end HP / 100, so survival is worth c in every fight and each HP
# w / 100. A loss scores 0 under both.
SURVIVE_DEFAULTS = {"c": 1.0, "w": 2.0}


def score_rule(rule):
    """A score rule normalised: None for the engine rule (absent, None or
    kind "engine"), else {"kind": "survive", "c", "w"} with defaults
    filled in. Unknown kinds or keys raise ValueError."""
    if rule is None or rule.get("kind", "engine") == "engine":
        if rule and set(rule) - {"kind"}:
            raise ValueError(f"the engine score rule takes no parameters: {rule}")
        return None
    if rule.get("kind") != "survive":
        raise ValueError(f"unknown score rule kind {rule.get('kind')!r}")
    extra = set(rule) - {"kind", "c", "w"}
    if extra:
        raise ValueError(f"unknown score rule keys {sorted(extra)}")
    return {"kind": "survive", **{k: float(rule.get(k, v)) for k, v in SURVIVE_DEFAULTS.items()}}


def external_score(p, hp, start_hp, max_hp, heal, tau=None, rep=None, rule=None):
    """Switch 6's fixed formula: a score from a histogram `p` [B, N_BINS] of
    HP lost from now and the state's real HP. A bin wins when its HP lost
    is below the current HP; its end HP gets end-of-combat healing (capped
    at max HP) before scoring. Engine rule (`rule` None): score = sum over
    bins of p * win * (2 - HP lost after the heal / 100) = P(win) x (2 -
    expected HP lost when winning / 100). Survive rule (`score_rule`): a
    winning bin scores c + w x its end HP / 100 (start HP plays no part).
    `tau` > 0 smooths the win step (for training's ranking term); None is
    exact. `rep`: the bins' HP lost (a loaded net's saved `bin_rep`);
    default BIN_REP."""
    win = _win(hp, tau, rep)
    hp, start_hp, max_hp, heal = (x.unsqueeze(1) for x in (hp, start_hp, max_hp, heal))
    end = torch.minimum(hp - _rep_tensor(rep) + heal, max_hp)
    if rule is not None and rule.get("kind") == "survive":
        return (p * win * (rule["c"] + rule["w"] * end / 100)).sum(1)
    lost = torch.relu(start_hp - end)
    return (p * win * (2 - lost / 100)).sum(1)


def score_of(model, t, tau=None):
    """The model's score for tensors `t`: its output, or for an HP-loss net
    the external formula (under the net's `score_rule`) on its histogram."""
    y = model(t)
    if getattr(model, "hp_loss", False):
        return external_score(y.exp(), t["hp"], t["start_hp"], t["max_hp"], t["win_heal"], tau,
                              getattr(model, "bin_rep", None), getattr(model, "score_rule", None))
    return y


class Evaluator:
    """A search evaluator: batch dict → numpy scores. An HP-loss net asks
    search for the HP scalars in its batches (`wants_heuristic`, which adds
    them) and scores through `external_score`."""

    def __init__(self, model, norm):
        self.model, self.norm = model.eval(), norm
        self.wants_heuristic = getattr(model, "hp_loss", False)
        if getattr(model, "score_rule", None) is not None:  # search scores finished combats by it
            self.score_rule = dict(model.score_rule)

    def __call__(self, batch):
        with torch.no_grad():
            return score_of(self.model, self.norm.tensors(batch)).numpy()


VOCAB_KEYS = ("known_cards", "known_powers", "known_triggers", "known_conditions", "known_effects")
# A contract net's own layout (docs/decisions.md "Contract as built"); missing = the full one.
LAYOUT_KEYS = ("columns", "row_kinds", "piles")
# Encoder value flags a net was trained with (docs/specs/shown-card-numbers.md):
# they change values, not column names, so the meta records them; missing = off.
ENCODER_FLAGS = ("shown_numbers", "exhaust_hidden")


def encoder_flags(meta, **given):
    """{flag: on} for `ENCODER_FLAGS` from `meta` (missing = off). A flag in
    `given` that is not None must agree with the meta: a net reads its inputs
    as it was trained, so a player setting (`@sn1`, `@xh1`) that disagrees is
    refused, not applied."""
    out = {k: bool(meta.get(k)) for k in ENCODER_FLAGS}
    for k, v in given.items():
        if v is not None and bool(v) != out[k]:
            raise ValueError(f"{k}={bool(v)} disagrees with the net's meta ({k}={out[k]}; a net saved without "
                             f"the key has it off): encoder flags are fixed at training, so drop the player setting "
                             f"or use a net trained with it")
    return out


def rust_evaluator(model, norm, meta, hp_bonus=0.0, survive_c=None, enemy_strength_price=0.0, hp_end_bonus=0.0,
                   draw_k=0, strength_hits_price=0.0, turn_start_leaf=False, leaf_clear_block=False, projected_ticks=0, projected_debuffs=False, tie_break=False, win_cap=False,
                   shown_numbers=None, exhaust_hidden=None):
    """The net as an `sts.NetEvaluator`: the same scores as `Evaluator`, but
    computed in Rust inside search (no Python lock, every search thread).
    `meta` gives the features it was trained on (as for `features_for`).
    `hp_bonus` c adds c x clamp(score / 2, 0, 1) x (HP - start HP) to each
    score (results doc "HP bonus at the leaves"; 0: off);
    `enemy_strength_price` k subtracts k x clamp(score / 2, 0, 1) x living
    monsters' Strength (docs/specs/enemy-strength-price.md);
    `strength_hits_price` k subtracts k x clamp(score / 2, 0, 1) x living
    monsters' Strength x the hits it will still land (`@shl<k>`,
    docs/specs/strength-hits-price.md); `hp_end_bonus`
    c prices HP after the coming heal on every leaf, finished combats too
    (docs/specs/end-hp-bonus.md). `survive_c`
    replaces a survive net's c (the `@sc<c>` player setting); search scores
    finished combats with the same rule. `draw_k` k scores end-of-turn
    leaves after k sampled draws (`@dl<k>`, docs/specs/draw-leaf.md);
    `turn_start_leaf` scores them after the player's turn-start hooks that
    need no chance (`@tsl1`, docs/specs/turn-start-leaf.md); `leaf_clear_block`
    scores them with the player's block at 0 (`@lcb1`,
    docs/specs/leaf-clear-block.md); `projected_ticks` k applies once-a-turn
    Strength and Dexterity hooks k more times there (`@pl<k>`,
    docs/specs/projected-leaf.md), with `projected_debuffs` monsters'
    once-a-turn Weak, Frail and Vulnerable on the player too (`@pd1`,
    docs/specs/recurring-debuff-leaf.md); `tie_break` breaks exact value ties toward
    the sooner win, then lower enemy HP (`@tb1`,
    docs/specs/finish-faster-tiebreak.md); `win_cap` caps an unfinished
    leaf's value at the score of a win at the HP it can still reach
    (`@wc1`, backlog 82). `shown_numbers` (card damage and
    block as the game shows them, `@sn1`) and `exhaust_hidden` (the exhaust
    pile's counts as 0, `@xh1`; docs/specs/shown-card-numbers.md) come from
    the meta (`encoder_flags`); None follows it, a value that disagrees is
    refused."""
    flags = encoder_flags(meta, shown_numbers=shown_numbers, exhaust_hidden=exhaust_hidden)
    hp = getattr(model, "hp_loss", False)
    weights = {k: v.detach().numpy().astype(np.float32) for k, v in model.state_dict().items()}
    config = {"card_repr": meta["card_repr"], **{k: meta.get(k) for k in VOCAB_KEYS + LAYOUT_KEYS},
              "lookahead": bool(meta.get("lookahead")), "rates": bool(meta.get("rates")),
              "start_hp": bool(meta.get("start_hp")), "hp_loss": hp,
              "bin_rep": _bin_rep(model) if hp else None, "hp_bonus": float(hp_bonus),
              "enemy_strength_price": float(enemy_strength_price), "hp_end_bonus": float(hp_end_bonus),
              "strength_hits_price": float(strength_hits_price),
              "draw_k": int(draw_k), "turn_start_leaf": bool(turn_start_leaf),
              "leaf_clear_block": bool(leaf_clear_block), "projected_ticks": int(projected_ticks),
              "projected_debuffs": bool(projected_debuffs),
              "tie_break": bool(tie_break), "win_cap": bool(win_cap), **flags}
    rule = getattr(model, "score_rule", None)
    if survive_c is not None:
        if rule is None:
            raise ValueError("survive_c (@sc) needs a net trained with the survive score rule")
        rule = dict(rule, c=float(survive_c))
    if rule is not None:  # only a survive net's config names a rule: every other config is as before
        config["score_rule"] = dict(rule)
    return sts.NetEvaluator(weights, norm.state_dict(), config)


# The contract's schema (docs/decisions.md "Contract as built"). Renaming a column or
# changing its meaning bumps it and adds a mapping in `load`.
SCHEMA = 1


def _bin_rep(model):
    """An HP-histogram net's bins' HP lost: its saved one, else BIN_REP."""
    rep = getattr(model, "bin_rep", None)
    return [float(x) for x in (BIN_REP if rep is None else rep)]


def layout_of(meta):
    """{"columns": {path: names}, "row_kinds", "piles"}: the layout the
    encoder for `meta` writes, i.e. what a net trained on it reads."""
    f = features_for(meta)
    columns = dict(zip(Normalizer.KEYS, (f.player_names, f.monster_names, f.card_names, f.row_names)))
    return {"columns": columns, "row_kinds": list(meta.get("row_kinds") or f.row_kinds),
            "piles": list(meta.get("piles") or f.piles)}


def save(path, model, norm, meta):
    """Saves a contract net: today's fields plus `schema`, the layout it was
    trained on (`columns` per path, `row_kinds`, `piles`; the normaliser's
    arrays are aligned with `columns`) and, for an HP-histogram net, its
    `bin_rep`. Refuses a net whose widths don't match its meta's encoder."""
    layout = layout_of(meta)
    for k, d in zip(Normalizer.KEYS, ("player", "monster", "card", "row")):
        n = len(layout["columns"][k])
        if model.dims[d] != n or len(norm.stats[k][0]) != n:
            raise ValueError(f"{path}: the net's {k} width {model.dims[d]} (normaliser {len(norm.stats[k][0])})"
                             f" doesn't match its meta's encoder ({n} columns)")
    if model.n_piles != len(layout["piles"]):
        raise ValueError(f"{path}: the net has {model.n_piles} pile slots, its meta's encoder {len(layout['piles'])}")
    hp = getattr(model, "hp_loss", False)
    torch.save({"state": model.state_dict(), "dims": model.dims, "width": model.width,
                "row_width": model.row_width,
                "hp_loss": hp,
                **({"hp_head": "histogram", "bin_rep": _bin_rep(model)} if hp else {}), "norm": norm.state_dict(),
                "meta": {**meta, **layout}, "schema": SCHEMA, **layout}, path)


def contract_path(path):
    """Where a pre-contract net's converted file sits: `<name>.contract.pt`."""
    root, ext = os.path.splitext(path)
    return root + ".contract" + (ext or ".pt")


def load(path):
    """Returns (model, normalizer, meta). `meta` holds `card_repr`, the
    `known_*` vocabularies and the net's layout (`columns`, `row_kinds`,
    `piles`), which `features_for` turns back into an `sts.Features`
    writing batches in the net's own layout. A pre-contract net (no
    `schema`) loads through its converted `<name>.contract.pt` beside it,
    else it is refused."""
    d = torch.load(path, weights_only=False)
    if "schema" not in d:
        _refuse_unloadable(path, d)
        conv = contract_path(path)
        if not os.path.exists(conv):
            raise ValueError(f"{path} is a pre-contract net (no schema) with no converted "
                             f"{os.path.basename(conv)} beside it; convert it with scripts/convert_net.py")
        path, d = conv, torch.load(conv, weights_only=False)
        if "schema" not in d:
            raise ValueError(f"{path} has no schema")
    if d["schema"] > SCHEMA:
        raise ValueError(f"{path} has schema {d['schema']}; this code reads schema {SCHEMA} and below")
    return _build(path, d)


def load_pre_contract(path):
    """A pre-contract net as saved (no layout, so the full-layout encoder),
    for the converter and the pins that compare against it. Everything
    else uses `load`."""
    d = torch.load(path, weights_only=False)
    if "schema" in d:
        raise ValueError(f"{path} is a contract net (schema {d['schema']}); use stsnet.load")
    return _build(path, d)


def _refuse_unloadable(path, d):
    if d.get("correction"):
        raise ValueError(f"{path} is a heuristic-correction net (learned-play switch 2, removed by Amendment 1)")
    if d.get("hp_loss") and d.get("hp_head") != "histogram":
        raise ValueError(f"{path} is a quantile HP-loss net (switch 6 before Amendment 1's histogram head)")


def _build(path, d):
    _refuse_unloadable(path, d)
    model = ValueNet(d["dims"], width=d["width"], row_width=d["row_width"], hp_loss=d.get("hp_loss", False))
    model.load_state_dict(d["state"])
    if d.get("bin_rep") is not None:
        model.bin_rep = np.asarray(d["bin_rep"], np.float32)
    meta = dict(d["meta"])
    rule = score_rule(meta.get("score_rule"))
    if rule is not None:
        model.score_rule = rule
    if "schema" in d:
        meta.update({k: d[k] for k in LAYOUT_KEYS})
    return model.eval(), Normalizer(d["norm"]), meta


# Each normaliser path's first layer (warm start): (ValueNet attribute, dims key).
FIRST_LAYERS = {"player": ("player", "player"), "monsters": ("monster", "monster"), "cards": ("card", "card"),
                "rows": ("row", "row")}


def widen(model, norm, meta, new_meta, new_stats=None):
    """The net carried over to `new_meta`'s encoder (docs/specs/warm-start.md):
    each path's first layer takes every old column's weights by name and
    zeros for columns the net has never seen; later layers are copied. The
    normaliser keeps the saved statistics for old columns and takes
    `new_stats`' (a Normalizer in the new layout; default mean 0, std 1)
    for new ones. Returns (model, normaliser, meta) with `new_meta`'s
    vocabularies and layout. Refuses an old column missing from the new
    layout, or a pile list that isn't the old one with piles appended (spec
    7's next_draw / known_later): an appended pile's head slot copies the
    weights of the pile the old layout folded it into (`sts.PILE_PARENTS`),
    so the net sees those cards as before. The row kinds are `new_meta`'s
    when it names them (refused if they drop one of the old net's),
    otherwise the old net's: a row of a kind the net never read would pass
    through its trained row layers and change its scores, so only a caller
    that trains on new kinds names them."""
    old, new = layout_of(meta), layout_of(new_meta)
    if not new_meta.get("row_kinds"):
        new = {**new, "row_kinds": list(old["row_kinds"])}
    dropped = [k for k in old["row_kinds"] if k not in new["row_kinds"]]
    if dropped:
        raise ValueError(f"widen: the new layout drops row kinds {dropped}")
    n_old_piles = len(old["piles"])
    if list(new["piles"][:n_old_piles]) != list(old["piles"]):
        raise ValueError(f"widen: piles {old['piles']} -> {new['piles']} (only appended piles and columns may change)")
    dims = dict(model.dims)
    dims["piles"] = len(new["piles"])
    picks = {}
    for path, (attr, d) in FIRST_LAYERS.items():
        oc, nc = old["columns"][path], new["columns"][path]
        missing = [c for c in oc if c not in nc]
        if missing:
            raise ValueError(f"widen: the new layout drops {path} columns {missing[:5]}")
        picks[path] = [nc.index(c) for c in oc]
        dims[d] = len(nc)
    if new["columns"]["monsters"][ALIVE] != "alive":
        raise ValueError("widen: the new layout's first monster column isn't 'alive'")
    out = ValueNet(dims, width=model.width, row_width=model.row_width, hp_loss=getattr(model, "hp_loss", False))
    sd = {k: v.clone() for k, v in model.state_dict().items()}
    stats = {}
    for path, (attr, d) in FIRST_LAYERS.items():
        key = f"{attr}.0.weight"
        w = sd[key]
        n_old, n_new = len(old["columns"][path]), dims[d]
        wide = torch.zeros(w.shape[0], n_new + w.shape[1] - n_old, dtype=w.dtype)
        wide[:, picks[path]] = w[:, :n_old]
        wide[:, n_new:] = w[:, n_old:]  # the pooled-row block after the columns
        sd[key] = wide
        m = np.zeros(n_new, np.float32) if new_stats is None else new_stats.stats[path][0].copy()
        s = np.ones(n_new, np.float32) if new_stats is None else new_stats.stats[path][1].copy()
        m[picks[path]], s[picks[path]] = norm.stats[path]
        stats[path] = (m, s)
    # The head's input is [pile slots x width, monsters sum, max, player]:
    # an appended pile's slot (after the old ones) takes its parent's weights
    # (the head is linear in the slot sums, so the score is unchanged).
    hw = sd["head.0.0.weight"]
    if dims["piles"] > n_old_piles:
        width, cut = model.width, n_old_piles * model.width
        slot = lambda p: hw[:, p * width:(p + 1) * width]
        added = []
        for p in new["piles"][n_old_piles:]:
            parent = sts.PILE_PARENTS.get(p)
            if parent not in old["piles"]:
                raise ValueError(f"widen: appended pile {p} has no parent in {old['piles']}")
            added.append(slot(old["piles"].index(parent)))
        sd["head.0.0.weight"] = torch.cat([hw[:, :cut], *added, hw[:, cut:]], 1)
    out.load_state_dict(sd)
    if getattr(model, "bin_rep", None) is not None:
        out.bin_rep = model.bin_rep
    if getattr(model, "score_rule", None) is not None:
        out.score_rule = model.score_rule
    keep = {k: v for k, v in meta.items() if k not in VOCAB_KEYS + LAYOUT_KEYS}
    vocab = {k: new_meta.get(k) for k in VOCAB_KEYS}
    return out.eval(), Normalizer(stats), {**keep, **vocab, "card_repr": new_meta["card_repr"], **new}


def features_for(meta):
    """The `sts.Features` a saved net was trained on: its card repr and the
    vocabularies in its meta (`known_cards`, `known_powers`,
    `known_triggers`, `known_conditions`, `known_effects`; missing = all)
    and, for a contract net, its own layout (`columns`, `row_kinds`,
    `piles`), which the encoder writes batches in. The monster lookahead
    columns are on when the meta says `lookahead` or its monster columns
    name any, the rate columns when it says `rates` or its player columns
    name any, the start-HP column likewise (the encoder checks the columns
    itself). The encoder value flags come from the meta (`encoder_flags`)."""
    kw = {k: meta.get(k) for k in VOCAB_KEYS + LAYOUT_KEYS}
    return sts.Features(meta["card_repr"], lookahead=bool(meta.get("lookahead")), rates=bool(meta.get("rates")),
                        start_hp=bool(meta.get("start_hp")), **kw, **encoder_flags(meta))
