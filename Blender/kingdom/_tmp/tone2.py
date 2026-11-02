"""Fast tone experiment: darken the pavement materials at render time.

    blender -b --factory-startup --python _tmp/tone2.py -- --f cob=0.72,st=0.8,gnd=0.9 --shots b5_overview

Rebuilding the city costs 20 minutes, so the colour of the ground is tuned on the
saved blend first; whatever wins here gets baked into init_mats().
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.dirname(HERE)
for _p in (KING, os.path.dirname(KING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                                   # noqa: E402
import capital as C                                          # noqa: E402
import kcommon as KC                                         # noqa: E402


def arg(name, default=None):
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return a[a.index(name) + 1] if name in a else default


C.HD["on"] = True
f = {}
for part in (arg("--f", "") or "").split(","):
    if "=" in part:
        k, v = part.split("=")
        f[k] = float(v)

bpy.ops.wm.open_mainfile(filepath=os.path.join(C.OUT_PNG, "capital_full.blend"))

stems = {
    "cob": ("cobble", "cy_cobbles", "cobble_dark", "town_cobble"),
    "st": ("town_street", "street"),
    "gnd": ("town_ground", "earth"),
}
hit = []
for mat in bpy.data.materials:
    for key, names in stems.items():
        if key in f and any(n in mat.name.lower() for n in names):
            if not mat.use_nodes:
                continue
            for node in mat.node_tree.nodes:
                if node.type != "BSDF_PRINCIPLED":
                    continue
                for inp in ("Base Color", "Base color"):
                    if inp in node.inputs:
                        c = node.inputs[inp].default_value
                        node.inputs[inp].default_value = (c[0] * f[key], c[1] * f[key],
                                                          c[2] * f[key], 1.0)
                        hit.append(mat.name)
                        break
print("[tone]", sorted(set(hit)), flush=True)

KC.clear_lights_cameras()
KC.setup_lighting(sun_energy=5.8, elev=33.0, azim=34.0)
_fl = bpy.data.objects.get("fill")
if _fl is not None and _fl.data is not None:
    _fl.data.energy = 300.0
KC.setup_render(w=1600, h=900, samples=24)

only = [s.strip() for s in (arg("--shots", "b5_overview") or "").split(",") if s.strip()]
for name, loc, look, lens in C.HD_SHOTS:
    if name in only:
        KC.setup_camera(loc, look, lens)
        print("[tone]", KC.render_to(os.path.join(C.OUT_PNG, name + "_tone.png")), flush=True)
print("TONE_DONE", flush=True)
