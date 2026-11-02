"""_lr.py -- run a Blender script under the shared one-at-a-time lock.

    python look/_lr.py <script.py> [-- extra blender args...]

The only sanctioned way for the TERRAIN agent to start Blender.  Prints the
tail of the log and the exit code.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from _lock import run_blender, BLENDER                          # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("usage: _lr.py <script> [-- args]")
        return 2
    script = sys.argv[1]
    extra = []
    if "--" in sys.argv:
        extra = sys.argv[sys.argv.index("--") + 1:]
    tag = os.path.splitext(os.path.basename(script))[0]
    args = ["-b", "--factory-startup", "--python", script]
    if extra:
        args += ["--"] + extra
    rc, log = run_blender(args, tag, timeout=2400, cwd=KROOT)
    print("[run] exit=%d log=%s" % (rc, log), flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
