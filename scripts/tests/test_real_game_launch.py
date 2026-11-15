"""Tests for the real-game launcher's guards (scripts/real_game_launch.py,
docs/specs/real-game-bridge.md "Launching the game"), against a fake Steam
and %LOCALAPPDATA% layout under pytest's tmp_path. The real game is never
started: a tiny Python script stands in for java.exe."""

import datetime
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import real_game_launch as rgl  # noqa: E402

PLAYER = ["runs/x/model.pt@hpe0.01", "--two-turn"]


@pytest.fixture
def layout(tmp_path):
    steam, local, repo = tmp_path / "steam", tmp_path / "local", tmp_path / "repo"
    p = rgl.paths(str(steam), str(local), str(repo))
    for sub in ("saves", "preferences"):
        os.makedirs(os.path.join(p["game"], sub))
    with open(os.path.join(p["game"], "saves", "THE_HELOT.autosave"), "w") as f:
        f.write("run")
    with open(os.path.join(p["game"], "preferences", "1_STSPlayer"), "w") as f:
        f.write("prefs")
    os.makedirs(os.path.dirname(p["mod_lists"]))
    with open(p["mod_lists"], "w") as f:
        f.write('{"defaultList": "shion"}')
    os.makedirs(os.path.dirname(p["cm_config"]))
    with open(p["cm_config"], "w", newline="\n") as f:
        f.write("#Fri Nov 13 14:30:23 UTC 2026\ncommand=\nverbose=true\n")
    return p


def fake_java(tmp_path, edit):
    """A command prefix that 'runs the game': it optionally rewrites
    mod_lists.json (as the launcher window would) and exits 0."""
    script = tmp_path / "fake_java.py"
    script.write_text("import sys\n"
                      f"edit = {edit!r}\n"
                      "if edit:\n"
                      "    open(edit[0], 'w').write(edit[1])\n")
    return [sys.executable, str(script)]


def read_props(path):
    import re
    out = {}
    for line in open(path, encoding="latin-1").read().splitlines():
        if line and not line.startswith("#"):
            k, _, v = line.partition("=")
            out[k] = re.sub(r"\\(.)", r"\1", v)
    return out


def test_refuses_while_the_game_runs(layout, tmp_path):
    procs = [("chrome.exe", "chrome"),
             ("java.exe", r'"C:\...\jre\bin\java.exe" -jar C:\...\ModTheSpire.jar --skip-launcher')]
    with pytest.raises(SystemExit, match="already running"):
        rgl.launch(PLAYER, layout, procs=procs, java=fake_java(tmp_path, None), say=lambda s: None)
    assert not os.path.exists(layout["backups"])  # refused before any step


def test_other_java_processes_do_not_count():
    assert rgl.running_game([("java.exe", "java -jar gradle.jar"), ("javaw.exe", "intellij")]) == []
    assert rgl.running_game([("javaw.exe", "javaw -jar desktop-1.0.jar")])


def test_backup_config_and_unchanged_mod_lists(layout, tmp_path):
    lines = []
    code = rgl.launch(PLAYER, layout, procs=[], java=fake_java(tmp_path, None), say=lines.append)
    assert code == 0
    folder = rgl.newest_backup(layout)
    assert open(os.path.join(folder, "saves", "THE_HELOT.autosave")).read() == "run"
    assert open(os.path.join(folder, "preferences", "1_STSPlayer")).read() == "prefs"
    assert open(os.path.join(folder, "mod_lists.json")).read() == '{"defaultList": "shion"}'
    props = read_props(layout["cm_config"])
    assert props["command"] == " ".join([layout["python"], "-u", layout["controller"], "play", *PLAYER])
    assert props["runAtGameStart"] == "true"
    assert props["maxInitializationTimeout"] == "30"
    assert props["verbose"] == "true"  # other lines kept
    text = open(layout["cm_config"]).read()
    assert text.startswith("#Fri Nov 13 14:30:23 UTC 2026\n")
    assert text.count("command=") == 1
    assert "unchanged" in lines[-1]


def test_escaped_paths_read_back():
    import re
    v = rgl.escape(r"D:\Games\x.py a=b")
    assert re.sub(r"\\(.)", r"\1", v) == r"D:\Games\x.py a=b"
    assert "\\:" in v and "\\\\" in v


def test_keeps_a_longer_timeout(layout, tmp_path):
    with open(layout["cm_config"], "w") as f:
        f.write("maxInitializationTimeout=120\n")
    rgl.write_config(layout["cm_config"], ["py", "x"])
    assert read_props(layout["cm_config"])["maxInitializationTimeout"] == "120"


def test_restores_a_changed_mod_lists(layout, tmp_path):
    lines = []
    edit = (layout["mod_lists"], '{"defaultList": "other"}')
    rgl.launch(PLAYER, layout, procs=[], java=fake_java(tmp_path, edit), say=lines.append)
    assert open(layout["mod_lists"]).read() == '{"defaultList": "shion"}'
    assert "CHANGED" in lines[-1]


def test_restore_mod_lists_without_launching(layout, tmp_path):
    rgl.backup(layout)
    with open(layout["mod_lists"], "w") as f:
        f.write("changed")
    assert "CHANGED" in rgl.check_mod_lists(layout, rgl.newest_backup(layout))
    assert open(layout["mod_lists"]).read() == '{"defaultList": "shion"}'
    assert "unchanged" in rgl.check_mod_lists(layout, rgl.newest_backup(layout))


def test_keeps_only_the_newest_20(layout):
    t = datetime.datetime(2026, 11, 13, 12, 0, 0)
    for i in range(23):
        rgl.backup(layout, t + datetime.timedelta(seconds=i))
    os.makedirs(os.path.join(layout["backups"], "not-a-backup"))
    gone = rgl.prune(layout)
    assert len(gone) == 3 and gone[0] == "20261113-120000"
    left = os.listdir(layout["backups"])
    assert len([n for n in left if rgl.STAMP.match(n)]) == 20
    assert "not-a-backup" in left  # only stamped folders are deleted


def test_refuses_a_command_path_with_a_space(tmp_path):
    p = rgl.paths(str(tmp_path / "steam"), str(tmp_path / "local"), str(tmp_path / "my repo"))
    with pytest.raises(SystemExit, match="spaces"):
        rgl.controller_command(p, PLAYER)
    with pytest.raises(SystemExit, match="spaces"):
        rgl.controller_command(rgl.paths(str(tmp_path), str(tmp_path), str(tmp_path)), ["a b"])


def test_no_wait_records_the_pid(layout, tmp_path):
    assert rgl.launch(PLAYER, layout, procs=[], java=fake_java(tmp_path, None), wait=False,
                      say=lambda s: None) is None
    assert os.path.exists(os.path.join(rgl.newest_backup(layout), "launch.json"))
