"""What does hd_light put in the scene?  List every object after apply()."""
import os
import sys

import bpy


def main():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import hd_light as L
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    rep = L.apply("morning_town", sc, cam=None, samples=16, res=(320, 180))
    print("[probe] ok=%d fail=%d" % (len(rep.get("ok") or []), len(rep.get("fail") or [])),
          flush=True)
    for ob in sc.objects:
        d = ob.dimensions
        print("[obj] %-22s %-8s loc=(%.1f,%.1f,%.1f) dim=(%.1f,%.1f,%.1f)"
              % (ob.name, ob.type, *ob.location, *d), flush=True)
    for lt in bpy.data.lights:
        print("[light] %-16s %-8s energy=%.1f" % (lt.name, lt.type, lt.energy), flush=True)


main()
