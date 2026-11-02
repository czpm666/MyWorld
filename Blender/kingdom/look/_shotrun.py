"""Run a Blender job under the fleet lock, from a plain-python shell.

    python look/_shotrun.py --tag qa1 --blend --script look/_shotqa.py -- \
        --shots look/_shotdiag.json --all --res 24x14 --ascii

Flags:
    --tag T        log name (Logs\\T.log)
    --blend        open capital_v24.blend  (default: no blend, startup scene)
    --script P     python script for Blender to run (-b ... --python P);
                   repeat the flag to run several scripts on one blend load
    --timeout N    seconds (default 2400)
    --dry          print the argv and exit
    everything after `--` is handed to the script.

Why not `blender -b file.blend --python ...` directly from PowerShell: an
`@name` token in a native command line is eaten by PowerShell's splat parser,
so `@blend` silently expands to nothing and Blender starts with the default
scene -- which is exactly how the first QA run "proved" that ray_cast misses
every object.  Everything here is built in Python, no @tokens.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _lock import run_blender, status          # noqa: E402

BLEND = r"E:\My World\Blender\renders\kingdom\capital_v24.blend"


def main():
    a = sys.argv[1:]
    tag, timeout, blend, blend_file = "shotrun", 2400.0, False, None
    scripts = []
    light = False
    if "--" in a:
        rest = a[a.index("--") + 1:]
        a = a[:a.index("--")]
    else:
        rest = []
    i = 0
    while i < len(a):
        k = a[i]
        if k == "--tag":
            tag = a[i + 1]
            i += 2
        elif k == "--timeout":
            timeout = float(a[i + 1])
            i += 2
        elif k == "--blend":
            blend = True
            i += 1
        elif k == "--blend-file":
            blend_file = a[i + 1]
            i += 2
        elif k == "--light":
            light = True
            i += 1
        elif k == "--script":
            scripts.append(a[i + 1])
            i += 2
        elif k == "--dry":
            i += 1
        else:
            raise SystemExit("unknown flag %r" % k)
    if blend_file:
        blend = True
        # accept "v25" as shorthand for the v25 city blend
        if not blend_file.lower().endswith(".blend"):
            blend_file = os.path.join(os.path.dirname(BLEND),
                                      "capital_%s.blend" % blend_file)
        if not os.path.isfile(blend_file):
            raise SystemExit("[run] no such blend: %s" % blend_file)
    args = []
    if blend:
        args += ["-b", os.path.abspath(blend_file) if blend_file else BLEND]
    else:
        args += ["-b"]
    if scripts:
        for s in scripts:
            args += ["--python", os.path.abspath(s)]
    if rest:
        args += ["--"] + rest
    print("[run] cmd:", args, flush=True)
    if "--dry" in sys.argv:
        return 0
    print("[run] lock: %s" % status(), flush=True)
    rc, _log = run_blender(args, tag, timeout=timeout,
                           cwd=os.path.dirname(HERE), light=light)
    return rc


if __name__ == "__main__":
    sys.exit(main())
