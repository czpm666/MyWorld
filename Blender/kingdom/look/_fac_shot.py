"""look/_fac_shot.py - run facade_lab.py under the shared one-Blender lock.

    python look/_fac_shot.py old all --fast
    python look/_fac_shot.py new hero,eye

Never starts two Blenders: goes through _lock.run_blender(), which also
tee's stdout to Logs\\fac_<tag>.log and kills a stuck child.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from _lock import run_blender                            # noqa: E402

LAB = os.path.join(_HERE, "facade_lab.py")
KING = os.path.dirname(_HERE)


def main():
    a = sys.argv[1:]
    src = a[0] if a else "new"
    rest = a[1:] if len(a) > 1 else ["all"]
    lab = LAB
    if src == "dbg":
        lab = os.path.join(_HERE, "_fac_dbg.py")
    args = ["-b", "--factory-startup", "--python", lab, "--", src] + rest
    tag = "fac_%s" % "_".join([src] + [r for r in rest if r.startswith("--") is False][:1])
    tag = tag.replace(",", "")
    rc, log = run_blender(args, tag, timeout=2400, cwd=KING)
    print("[fac_shot] rc=%d log=%s" % (rc, log))
    return rc


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
