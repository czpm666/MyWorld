"""Generic Launcher: run Blender under the fleet lock, tee to Logs\\<tag>.log.

    python look/export_run.py <tag> [timeout_s] [LIGHT] -- <blender args...>

Add the word LIGHT as a free-form argument (anywhere in the head) to take one
of three shared slots instead of the exclusive lock.  Light slots let small lab
runs proceed while a city build is going; use LIGHT for anything that opens a
scene under ~200 MB (a lab .blend, a single module preview, a 480x270 sheet)
and leave it off for capital_v25.blend.

    python look/export_run.py props_lab 600 LIGHT -- -b lab.blend --python ...
    python look/export_run.py build_v25 5400 -- -b --python capital.py -- ...
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lock import run_blender  # noqa: E402


def main(argv):
    if "--" not in argv:
        print(__doc__)
        return 2
    i = argv.index("--")
    head, rest = argv[1:i], argv[i + 1:]
    if not head:
        print(__doc__)
        return 2
    words = [h.upper() for h in head]
    light = "LIGHT" in words
    head = [h for h in head if h.upper() != "LIGHT"]
    tag = head[0]
    timeout = float(head[1]) if len(head) > 1 else 2400.0
    # A tag that starts with "build_" is a grand build: 20-40 minutes, one
    # progress line every few seconds, unrecoverable if killed.  Pin it so no
    # waiter can `_lock.py kill` it by mistake -- that is how build_v25 died at
    # block 91 with no error line at all.
    pinned = tag.startswith("build_") and not light
    rc, log = run_blender(rest, tag=tag, timeout=timeout, pinned=pinned,
                          light=light, cwd=r"E:\My World\Blender\kingdom")
    print("[run] %s exit=%s pinned=%s light=%s log=%s"
          % (tag, rc, pinned, light, log))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
