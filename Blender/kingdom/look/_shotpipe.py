"""One blend load, the whole camera pipeline.

    blender -b capital_v25.blend --python look/_shotpipe.py -- \
        --qa-out look/_qa_v25.json --tag v25

The lock is the scarce resource (other agents hold it for 20+ minutes at a
time), so everything that needs the blend loaded happens here in one process:
read the real block footprints, re-pick the street cameras, rebuild the
library, measure every camera with ray_cast, fold the measurements back into
the notes, then tile a 320x180 contact sheet.

Each stage is an ordinary module with its own `main()` and its own argv
parsing, so this driver just rewrites `sys.argv` before each call instead of
duplicating any logic.  `_shotgrid` is the one module that calls `main()` at
import time, hence the set-argv-before-import dance.

Nothing here writes outside look/: the blend itself is never saved.
"""
import importlib
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def flag(name, default=None):
    a = [v for v in sys.argv[1:] if v != "--"]
    if name in a and a.index(name) + 1 < len(a):
        return a[a.index(name) + 1]
    return default


QA_OUT = flag("--qa-out", os.path.join(HERE, "_qa_v25.json"))
QA_MD = flag("--md", os.path.splitext(QA_OUT)[0] + ".md")
TAG = flag("--tag", "v25")
GRID = flag("--grid", "24x14")
SHEET_RES = flag("--sheet-res", "320x180")
SHEET_SAMPLES = flag("--sheet-samples", "8")
MONTAGE = flag("--montage", "6")
SHEET_DIR = flag("--sheet-dir", os.path.join(
    os.path.dirname(os.path.dirname(HERE)), "renders", "kingdom", "look",
    "sheet_%s" % TAG))
BLOCKS = os.path.join(HERE, "_shotblocks.json")
SPOTS = os.path.join(HERE, "spots.json")
SHOTS = os.path.join(HERE, "shots.json")
# which stages to run: "all" or a comma list of grid,spots,gen,qa,fold,sheet
STAGES = [s.strip() for s in str(flag("--stages", "all")).split(",") if s.strip()]


def want(stage):
    return "all" in STAGES or stage in STAGES


def call(modname, args, unguarded=False):
    """Import `modname` with a fresh sys.argv and run its main()."""
    sys.argv = ["shotpipe", "--"] + list(args)
    mod = importlib.import_module(modname)
    if not unguarded:
        mod.main()
    return mod


def stage(name, fn):
    t0 = time.time()
    print("\n[pipe] === %s ===" % name, flush=True)
    try:
        fn()
    except SystemExit as e:
        print("[pipe] %s exited: %s" % (name, e), flush=True)
        raise
    except Exception:
        print("[pipe] %s FAILED:\n%s" % (name, traceback.format_exc()),
              flush=True)
        raise
    print("[pipe] === %s done in %.1f s ===" % (name, time.time() - t0),
          flush=True)


def do_grid():
    # _shotgrid runs main() at import time, so argv must be right first
    call("_shotgrid", [], unguarded=True)


def do_spots():
    call("spots", ["--blocks", BLOCKS, "--out", SPOTS])


def do_gen():
    call("_shotgen", [])


def do_qa():
    call("_shotqa", ["--shots", SHOTS, "--all", "--grid", GRID,
                     "--out", QA_OUT, "--md", QA_MD])


def do_fold():
    call("_shotgen", ["--from-qa", QA_OUT])


def do_sheet():
    os.makedirs(SHEET_DIR, exist_ok=True)
    call("contact", ["--shots-file", SHOTS, "--shots", "all",
                     "--tag", "c_%s" % TAG, "--res", SHEET_RES,
                     "--samples", SHEET_SAMPLES, "--out-dir", SHEET_DIR,
                     "--montage", MONTAGE])


def main():
    import bpy
    print("[pipe] blend: %s" % bpy.data.filepath, flush=True)
    print("[pipe] objects: %d  stages: %s" % (len(bpy.data.objects),
                                              ",".join(STAGES)), flush=True)
    t0 = time.time()
    if want("grid"):
        stage("grid", do_grid)
    if want("spots"):
        stage("spots", do_spots)
    if want("gen"):
        stage("gen", do_gen)
    if want("qa"):
        stage("qa", do_qa)
    if want("fold"):
        stage("fold", do_fold)
    if want("sheet"):
        stage("sheet", do_sheet)
    print("\n[pipe] all stages done in %.1f s" % (time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
