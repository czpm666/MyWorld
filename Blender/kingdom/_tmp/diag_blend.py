"""Close-up diagnostics from a saved capital .blend.

    blender -b --factory-startup --python _tmp/diag_blend.py -- --blend <path> [--samples 12]

Renders `_tmp/diag_<name>.png` at 1280x720 for whatever needs a second look:
the castle plateau edge (overhang?), the market hall roof (is that hoist beam
attached?), the gate flank (is the curtain buried in it?), the ramp foot.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.join(os.path.dirname(HERE), "kingdom")
for _p in (KING, os.path.dirname(KING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                                  # noqa: E402
import kcommon as KC                                        # noqa: E402

OUT = os.path.join(HERE, "diag")
if not os.path.isdir(OUT):
    os.makedirs(OUT)


def arg(name, default=None):
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return a[a.index(name) + 1] if name in a else default


SHOTS = (
    # name, loc, look, lens
    ("ramp", (0.0, -6.0, 9.0), (0.0, 150.0, 26.0), 35.0),
    ("plateau", (150.0, 60.0, 46.0), (0.0, 196.0, 26.0), 35.0),
    ("plateau_edge", (40.0, 120.0, 30.0), (18.0, 160.0, 20.0), 45.0),
    ("market_roof", (8.0, 4.0, 24.0), (0.0, 34.0, 14.0), 50.0),
    ("gate_flank", (16.0, -262.0, 6.0), (14.0, -300.0, 11.0), 45.0),
    ("castle_gate", (0.0, 118.0, 6.0), (0.0, 150.0, 22.0), 40.0),
)

only = [s.strip() for s in (arg("--shots", "") or "").split(",") if s.strip()]
if only:
    SHOTS = [s for s in SHOTS if s[0] in only]

blend = arg("--blend", r"E:\My World\Blender\renders\kingdom\capital_full.blend")
samples = int(arg("--samples", 12))

bpy.ops.wm.open_mainfile(filepath=blend)
KC.clear_lights_cameras()
KC.setup_lighting()
KC.setup_render(w=1280, h=720, samples=samples)

for name, loc, look, lens in SHOTS:
    KC.setup_camera(loc, look, lens)
    print("[diag] %s -> %s" % (name, KC.render_to(os.path.join(OUT, "diag_%s.png" % name))),
          flush=True)
print("DIAG_DONE", flush=True)
