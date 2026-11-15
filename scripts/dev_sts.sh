#!/usr/bin/env bash
# Build this checkout's `sts` into target/pyroot without touching the shared
# .venv (the job runner and running jobs load the module from there).
# Use it with: PYTHONPATH="$PWD/target/pyroot" <main>/.venv/Scripts/python.exe ...
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
venv="${STS_VENV:-$(git -C "$here" worktree list --porcelain | head -1 | cut -d' ' -f2-)/.venv}"
rm -rf "$here/target/devwheels" "$here/target/pyroot"
(cd "$here/py" && "$venv/Scripts/maturin" build --release -o "$here/target/devwheels")
"$venv/Scripts/python.exe" -c "import glob,sys,zipfile; zipfile.ZipFile(glob.glob(sys.argv[1] + '/*.whl')[0]).extractall(sys.argv[2])" \
  "$here/target/devwheels" "$here/target/pyroot"
echo "sts built into $here/target/pyroot"
