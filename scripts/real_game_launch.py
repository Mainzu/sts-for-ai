"""Launches the real Slay the Spire with only BaseMod and CommunicationMod,
with the owner's files guarded (docs/specs/real-game-bridge.md, "Launching
the game"). `scripts/real_game.py launch` calls `launch`; this file runs on
its own too:

    python scripts/real_game_launch.py launch <player tokens...> [--no-wait]
    python scripts/real_game_launch.py restore-mod-lists

ModTheSpire 3.30.3 loads the mods named by `--mods` and skips its launcher
window with `--skip-launcher`; only that window (`ModSelectWindow`) saves
`mod_lists.json`, so the owner's mod lists stay as they are.

Guards, in order:
1. Refuse while the game runs (a java.exe / javaw.exe naming
   ModTheSpire.jar or desktop-1.0.jar).
2. Back up the game's saves/ and preferences/ and ModTheSpire's
   mod_lists.json into %LOCALAPPDATA%/sts-for-ai/real-game-backups/<stamp>/,
   keeping the newest 20.
3. Write CommunicationMod's own config: only `command=`, `runAtGameStart=true`
   (CommunicationMod's default is false, and then it never starts the
   controller) and `maxInitializationTimeout` (raised to 30 when lower);
   every other line stays.
4. Launch; wait for the game to exit unless --no-wait.
5. Compare mod_lists.json with the backup; put the backup back if it changed.

Backups are the owner's safety copies: the newest 20 are kept, older ones
are deleted by the next launch."""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODS = "basemod,CommunicationMod"
KEEP = 20
STAMP = re.compile(r"^\d{8}-\d{6}(-\d+)?$")
GAME_JARS = ("modthespire.jar", "desktop-1.0.jar")
TIMEOUT = 30


def steam_path():
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
        return winreg.QueryValueEx(k, "SteamPath")[0]


def paths(steam=None, local=None, repo=REPO):
    """Every path the launcher touches; `steam` and `local` (%LOCALAPPDATA%)
    point it at a fake layout in tests."""
    steam = steam or steam_path()
    local = local or os.environ["LOCALAPPDATA"]
    game = os.path.join(steam, "steamapps", "common", "SlayTheSpire")
    mts = os.path.join(local, "ModTheSpire")
    return {
        "game": game,
        "java": os.path.join(game, "jre", "bin", "java.exe"),
        "mts_jar": os.path.join(steam, "steamapps", "workshop", "content", "646570", "1605060445", "ModTheSpire.jar"),
        "mod_lists": os.path.join(mts, "mod_lists.json"),
        "cm_config": os.path.join(mts, "CommunicationMod", "config.properties"),
        "backups": os.path.join(local, "sts-for-ai", "real-game-backups"),
        # pythonw: CommunicationMod starts the controller with pipes for its
        # input and output, and python.exe would also get a console window of
        # its own each game start (the loop runs the game without a console).
        "python": os.path.join(repo, ".venv", "Scripts", "pythonw.exe"),
        "controller": os.path.join(repo, "scripts", "real_game.py"),
    }


def list_processes():
    """(name, command line) of every running java.exe / javaw.exe."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='java.exe' or Name='javaw.exe'\" | "
          "Select-Object Name,CommandLine | ConvertTo-Json -Compress")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                         check=True).stdout.strip()
    if not out:
        return []
    rows = json.loads(out)
    rows = rows if isinstance(rows, list) else [rows]
    return [(r.get("Name") or "", r.get("CommandLine") or "") for r in rows]


def running_game(procs):
    """The processes in `procs` that are the game."""
    return [(n, c) for n, c in procs
            if n.lower() in ("java.exe", "javaw.exe") and any(j in c.lower() for j in GAME_JARS)]


def controller_command(p, player):
    """CommunicationMod's `command=` tokens. It splits the value on
    whitespace with no quoting, so no token may hold a space."""
    tokens = [p["python"], "-u", p["controller"], "play", *player]
    bad = [t for t in tokens if not t or re.search(r"\s", t)]
    if bad:
        raise SystemExit(f"refused: CommunicationMod splits its command on spaces, and these parts have one: {bad}")
    return tokens


def backup(p, now=None):
    """Copies saves/, preferences/ and mod_lists.json into a new stamped
    folder; returns it."""
    now = now or datetime.datetime.now()
    os.makedirs(p["backups"], exist_ok=True)
    name = now.strftime("%Y%m%d-%H%M%S")
    dest, n = os.path.join(p["backups"], name), 1
    while os.path.exists(dest):
        dest, n = os.path.join(p["backups"], f"{name}-{n}"), n + 1
    os.makedirs(dest)
    for sub in ("saves", "preferences"):
        src = os.path.join(p["game"], sub)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dest, sub))
    if os.path.isfile(p["mod_lists"]):
        shutil.copy2(p["mod_lists"], os.path.join(dest, "mod_lists.json"))
    return dest


def _is_link(path):
    return os.path.islink(path) or (hasattr(os.path, "isjunction") and os.path.isjunction(path))


def prune(p, keep=KEEP):
    """Deletes stamped backup folders beyond the newest `keep`; returns
    their names. Only real folders named like a stamp, inside the backups
    folder."""
    root = p["backups"]
    if not os.path.isdir(root):
        return []
    names = sorted(n for n in os.listdir(root)
                   if STAMP.match(n) and os.path.isdir(os.path.join(root, n)) and not _is_link(os.path.join(root, n)))
    gone = names[:-keep] if len(names) > keep else []
    for n in gone:
        shutil.rmtree(os.path.join(root, n))
    return gone


def newest_backup(p):
    root = p["backups"]
    names = sorted(n for n in os.listdir(root) if STAMP.match(n)) if os.path.isdir(root) else []
    return os.path.join(root, names[-1]) if names else None


def escape(value):
    """A Java properties value (Properties.store's escaping), so
    backslashes and colons in Windows paths read back as written."""
    out = []
    for i, ch in enumerate(value):
        if ch == "\\":
            out.append("\\\\")
        elif ch in "=:#!":
            out.append("\\" + ch)
        elif ch == " " and i == 0:
            out.append("\\ ")
        else:
            out.append(ch)
    return "".join(out)


def _key(line):
    """The key of a properties line, or None for a comment or blank."""
    s = line.lstrip()
    if not s or s[0] in "#!":
        return None
    m = re.match(r"((?:\\.|[^=:\s\\])*)", s)
    return m.group(1).replace("\\", "") if m else None


def _value(line):
    s = line.lstrip()
    m = re.match(r"(?:\\.|[^=:\s\\])*\s*[=:]?\s*(.*)$", s)
    return m.group(1) if m else ""


def write_config(path, command):
    """Sets `command`, `runAtGameStart=true` and `maxInitializationTimeout`
    (only when below 30) in CommunicationMod's config; keeps every other
    line; writes atomically. Returns the keys it changed."""
    lines = []
    if os.path.exists(path):
        with open(path, encoding="latin-1", newline="") as f:
            lines = f.read().splitlines()
    want = {"command": escape(" ".join(command)), "runAtGameStart": "true"}
    timeout = next((_value(l) for l in lines if _key(l) == "maxInitializationTimeout"), None)
    try:
        if timeout is None or int(timeout) < TIMEOUT:
            want["maxInitializationTimeout"] = str(TIMEOUT)
    except ValueError:
        want["maxInitializationTimeout"] = str(TIMEOUT)
    done, out = set(), []
    for line in lines:
        k = _key(line)
        if k in want and k not in done:
            out.append(f"{k}={want[k]}")
            done.add(k)
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in want.items() if k not in done]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".sts-for-ai-tmp"
    with open(tmp, "w", encoding="latin-1", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    os.replace(tmp, path)
    return sorted(want)


def check_mod_lists(p, folder):
    """Puts the backup's mod_lists.json back if the live one differs;
    returns a line saying what happened."""
    saved = os.path.join(folder, "mod_lists.json") if folder else None
    if not saved or not os.path.isfile(saved):
        return "mod_lists.json: no backup copy to compare"
    with open(saved, "rb") as f:
        want = f.read()
    have = None
    if os.path.isfile(p["mod_lists"]):
        with open(p["mod_lists"], "rb") as f:
            have = f.read()
    if have == want:
        return "mod_lists.json: unchanged"
    tmp = p["mod_lists"] + ".sts-for-ai-tmp"
    with open(tmp, "wb") as f:
        f.write(want)
    os.replace(tmp, p["mod_lists"])
    return f"mod_lists.json: CHANGED during the launch; put back from {saved}"


def launch(player, p=None, procs=None, java=None, wait=True, now=None, say=print):
    """The five steps; returns the game's exit code (None with wait=False).
    `procs` (a process list) and `java` (the command prefix standing in for
    the game's java.exe) are for tests."""
    p = p or paths()
    found = running_game(list_processes() if procs is None else procs)
    if found:
        raise SystemExit(f"refused: the game is already running ({found[0][1][:120]}); close it first")
    say("1. the game isn't running")
    command = controller_command(p, player)
    folder = backup(p, now)
    gone = prune(p)
    say(f"2. backed up saves/, preferences/ and mod_lists.json to {folder}"
        + (f" (deleted {len(gone)} older)" if gone else ""))
    keys = write_config(p["cm_config"], command)
    say(f"3. set {', '.join(keys)} in {p['cm_config']}")
    cmd = (java or [p["java"]]) + ["-jar", p["mts_jar"], "--skip-launcher", "--mods", MODS]
    proc = subprocess.Popen(cmd, cwd=p["game"])
    if not wait:
        with open(os.path.join(folder, "launch.json"), "w", encoding="utf-8") as f:
            json.dump({"pid": proc.pid, "command": cmd}, f)
        say(f"4. launched (pid {proc.pid}); after the game exits, run restore-mod-lists to check mod_lists.json")
        return None
    say(f"4. launched (pid {proc.pid}); waiting for the game to exit")
    code = proc.wait()
    say(f"5. the game exited ({code}); {check_mod_lists(p, folder)}")
    return code


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("launch", usage="launch [--no-wait] [--steam S] [--local L] <player tokens...>")
    r = sub.add_parser("restore-mod-lists")
    for s in (a, r):
        s.add_argument("--steam")
        s.add_argument("--local")
    a.add_argument("--no-wait", action="store_true")
    # Everything after the options is the controller's player string
    # (`model.pt@hpe0.01 --two-turn ...`), passed through as it is.
    a.add_argument("player", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    p = paths(args.steam, args.local)
    if args.cmd == "launch":
        if not args.player:
            ap.error("launch needs the player tokens")
        launch(args.player, p, wait=not args.no_wait)
    else:
        print(check_mod_lists(p, newest_backup(p)))


if __name__ == "__main__":
    sys.exit(main())
