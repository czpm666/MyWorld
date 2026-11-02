# -*- coding: utf-8 -*-
"""Diagnostic 3: after the real lab sequence (clear then snow), what do the
roof materials actually look like?  No render.

    blender -b --factory-startup --python-exit-code 1 --python hd_weather_probe3.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "look")):
    if p not in sys.path:
        sys.path.insert(0, p)

import bpy                                                    # noqa: E402


def main():
    import weather_lab as WL
    import hd_weather as W
    parts, MAT, trees, nh = WL._town()

    def report(tag="clear"):
        for name in sorted(MAT):
            m = MAT[name]
            if m is None:
                continue
            if not (name.startswith("v0_tile") or name.startswith("v0_slate")
                    or name in ("v0_stone", "v0_plaster", "flag", "v0_wood")):
                continue
            nt = getattr(m, "node_tree", None)
            if nt is None:
                print("[p3] %-14s %-26s NO NODES" % (name, m.name))
                continue
            sm = nt.nodes.get("WX.Snow.Mask")
            core = "mask=%s" % ("MISSING" if sm is None else
                                ("IN1=%.2f" % sm.inputs[1].default_value
                                 if not sm.inputs[1].is_linked else "IN1=LINKED"))
            nd = nt.nodes.get("WX.Snow.Up")
            if nd is not None:
                core += " up[%.2f..%.2f]" % (nd.inputs["From Min"].default_value,
                                             nd.inputs["From Max"].default_value)
            bsdf = W._principled(nt)
            src = "?"
            if bsdf is not None:
                s = bsdf.inputs["Base Color"]
                src = s.links[0].from_node.name if s.is_linked else "UNLINKED"
            print("[p3] %-6s %-14s %-26s %-40s base<-%s"
                  % (tag, name, m.name, core, src))

    W.apply_materials(MAT, W.state("clear"))
    report("clear")
    print("")
    W.apply_materials(MAT, W.state("snow"))
    report("snow")

    # and what the objects use
    used = set()
    for ob in bpy.context.scene.objects:
        for sl in ob.material_slots:
            if sl.material is not None:
                used.add(sl.material.name)
    vals = set(m.name for m in MAT.values() if m is not None)
    print("\n[p3] scene materials=%d, MAT values=%d, used-not-in-MAT=%s"
          % (len(used), len(vals), sorted(used - vals)))


main()
