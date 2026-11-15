"""memprobe deletes its root's registry at the end, so it refuses the main
checkout however the path is spelled (case, `..`, slashes)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import memprobe  # noqa: E402
import registry  # noqa: E402


def test_refuses_main_checkout():
    for root in (registry.ROOT, registry.ROOT.lower(), registry.ROOT.upper(),
                 os.path.join(registry.ROOT, "scripts", ".."), registry.ROOT.replace("\\", "/")):
        try:
            memprobe.main(["--root", root])
            raise AssertionError(f"ran on the main checkout as {root}")
        except SystemExit as e:
            assert e.code == 2, (root, e.code)  # argparse's error, before anything is written


if __name__ == "__main__":
    test_refuses_main_checkout()
    print("ok")
