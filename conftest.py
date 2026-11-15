"""Every pytest run (scripts/test_full.py, a session's own run; pytest.ini
makes this the rootdir for both py/tests and scripts/tests) gets its
own temp folder, deleted when the run ends. Many tests call
tempfile.mkdtemp() and never clean up; without this they piled up in
%TEMP% (3,715 folders, 7 GB in a week). TMP/TEMP/TMPDIR point there too, so
subprocesses and the Rust side (std::env::temp_dir) land in it as well.
A folder Windows still holds open at the end stays; the next run removes
any such leftover older than a day."""

import os
import shutil
import stat
import tempfile
import time

PREFIX = "sts-pytest-"
_root = None


def _retry_writable(func, path, exc):
    """Git's object files are read-only, which rmtree can't delete on
    Windows: clear the flag and try once more; a file still open stays."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _remove(path):
    shutil.rmtree(path, onexc=_retry_writable)


def pytest_configure(config):
    global _root
    base = tempfile.gettempdir()
    for e in os.scandir(base):
        try:
            if e.name.startswith(PREFIX) and time.time() - e.stat().st_mtime > 86400:
                _remove(e.path)
        except OSError:
            pass
    _root = tempfile.mkdtemp(prefix=PREFIX, dir=base)
    tempfile.tempdir = _root
    for k in ("TMP", "TEMP", "TMPDIR"):
        os.environ[k] = _root


def pytest_unconfigure(config):
    tempfile.tempdir = None
    if _root:
        _remove(_root)
