"""_surf_probe_lights.py -- what does the world actually light this castle with?

hd_surface's directional-ageing layer needs the real direction of the key light,
not my reading of an euler triple.  This prints every light's world-space travel
direction, its "toward the light" vector, energy and angle, plus the world
background colour.  Headless, no render.

USAGE
    blender.exe --background --factory-startup --python _surf_probe_lights.py
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy
from mathutils import Vector

import hd_common as H


def main():
    H._clear()
    H.setup_world()
    import hd_castle as C
    C.fill_light()
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    if sc.world and sc.world.node_tree:
        for n in sc.world.node_tree.nodes:
            if n.type == "BACKGROUND":
                print("[light] world bg  colour %s  strength %.2f"
                      % (tuple(round(v, 3) for v in n.inputs["Color"].default_value[:3]),
                         n.inputs["Strength"].default_value))
    for ob in bpy.data.objects:
        if ob.type != "LIGHT":
            continue
        m = ob.matrix_world
        travel = (m.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
        toward = -travel
        ld = ob.data
        print("[light] %-10s %-8s energy %6.2f  angle %.1fdeg  size %.3f"
              % (ob.name, ld.type, ld.energy,
                 0.0 if ld.type != "SUN" else ld.angle * 57.2958,
                 getattr(ld, "size", 0.0)))
        print("          travel (%+.3f,%+.3f,%+.3f)   toward (%+.3f,%+.3f,%+.3f)"
              % (travel.x, travel.y, travel.z, toward.x, toward.y, toward.z))
        print("          world loc (%.1f %.1f %.1f)  euler %.1f %.1f %.1f"
              % (*m.translation, *(v * 57.2958 for v in ob.rotation_euler)))


if __name__ == "__main__":
    main()
