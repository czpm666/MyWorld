"""Render the HD camera set from a saved capital .blend (no rebuild).

    blender -b --factory-startup --python _tmp/render_hd.py -- [--blend <path>] [--shots a,b] [--w 1600] [--h 900] [--samples 32]

Split out from capital.py so a render failure (bad camera, OOM) never costs the
ten-minute city build: the .blend is saved first, then photographed from here.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.join(os.path.dirname(HERE), "kingdom")
for _p in (KING, os.path.dirname(KING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                                  # noqa: E402
import capital as C                                         # noqa: E402
import kcommon as KC                                        # noqa: E402


def arg(name, default=None):
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return a[a.index(name) + 1] if name in a else default


blend = arg("--blend", os.path.join(C.OUT_PNG, "capital_full.blend"))
only = [s.strip() for s in (arg("--shots", "") or "").split(",") if s.strip()]
w = int(arg("--w", 1600))
h = int(arg("--h", 900))
samples = int(arg("--samples", 32))

print("[render] blend =", blend, flush=True)
if "--hd" in sys.argv:              # pick the HD camera set, not the legacy shots
    C.HD["on"] = True
bpy.ops.wm.open_mainfile(filepath=blend)
print("[render] objects =", len(bpy.data.objects), flush=True)

KC.clear_lights_cameras()
if C.HD["on"]:
    # must match capital.main(), or a re-rendered shot comes out of a different
    # scene than the one that was saved
    KC.setup_lighting(sun_energy=5.8, elev=33.0, azim=34.0)
    _f = bpy.data.objects.get("fill")
    if _f is not None and _f.data is not None:
        _f.data.energy = 300.0
else:
    KC.setup_lighting()
KC.setup_render(w=w, h=h, samples=samples)

shots = C.HD_SHOTS if C.HD["on"] else C.SHOTS
if only:
    shots = [s for s in shots if s[0] in only]

fail = []
t0 = time.time()
for name, loc, look, lens in shots:
    t = time.time()
    try:
        KC.setup_camera(loc, look, lens)
        path = KC.render_to(os.path.join(C.OUT_PNG, name + ".png"))
        print("[render] %-16s %5.1fs -> %s" % (name, time.time() - t, path), flush=True)
    except Exception as exc:                               # keep the rest going
        fail.append((name, "%s: %s" % (type(exc).__name__, exc)))
        print("[render] FAILED %-16s %s: %s" % (name, type(exc).__name__, exc), flush=True)

print("[render] %d/%d shots in %.1fs, failed=%s"
      % (len(shots) - len(fail), len(shots), time.time() - t0, fail or "none"), flush=True)
print("RENDER_DONE", flush=True)
