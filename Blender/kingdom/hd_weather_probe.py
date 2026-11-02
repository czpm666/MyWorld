# -*- coding: utf-8 -*-
"""Diagnostic: why do roofs not take snow?  Prints, per material that the lab
uses, whether hd_weather considers it eligible and what the mean |normal.z| of
the faces that carry it is.  No render -- runs in about a second of Blender.

    blender -b --factory-startup --python-exit-code 1 \
        --python hd_weather_probe.py
"""
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if os.path.join(HERE, "look") not in sys.path:
    sys.path.insert(0, os.path.join(HERE, "look"))

import bpy                                                    # noqa: E402


def main():
    import weather_lab as WL
    import hd_weather as W
    WL._town()
    MAT = WL._PALETTE if hasattr(WL, "_PALETTE") else None
    sc = bpy.context.scene
    # gather per-material face-normal statistics over the whole town
    stats = {}
    for ob in sc.objects:
        if ob.type != "MESH":
            continue
        mw = ob.matrix_world
        for slot in ob.material_slots:
            m = slot.material
            if m is None:
                continue
            d = stats.setdefault(m.name, [0, 0.0, 0, 0.0])   # n, sum|z|, n_up, nz>0
            me = ob.data
            for p in me.polygons:
                n = (mw.to_3x3() @ p.normal).normalized()
                d[0] += 1
                d[1] += abs(n.z)
                if n.z > 0.25:
                    d[2] += 1
                if n.z > 0.0:
                    d[3] += 1
    print("\n[probe] materials in scene: %d" % len(stats))
    rows = sorted(stats.items(), key=lambda kv: -kv[1][0])
    # what does hd_weather think of each?
    cfg = W.state("snow")
    for name, (n, sz, nup, npos) in rows[:40]:
        m = bpy.data.materials.get(name)
        kind = W._kind_of(name, m)
        el = W._eligible(name, m) if m is not None else False
        print("[probe] %-22s faces=%-6d mean|nz|=%.2f  up%%=%3d%%  z>0%%=%3d%%  "
              "kind=%-10s eligible=%s" %
              (name, n, sz / max(1, n), 100 * nup // max(1, n),
               100 * npos // max(1, n), str(kind), el))
    # what happens when we call snow_material on a roof material directly
    roof = None
    for name in stats:
        if W._kind_of(name, bpy.data.materials.get(name)) in ("tile", "slate"):
            roof = bpy.data.materials.get(name)
            break
    print("\n[probe] roof material =", roof.name if roof else None)
    if roof is not None:
        ok = W.snow_material(roof, 1.0)
        print("[probe] snow_material ->", ok)
        nt = roof.node_tree
        for nd in nt.nodes:
            if nd.name.startswith("WX.Snow"):
                vals = []
                for s in nd.inputs:
                    try:
                        vals.append("%s=%s" % (s.name, round(s.default_value, 3)
                                               if isinstance(s.default_value, float)
                                               else s.default_value))
                    except Exception:
                        vals.append(s.name)
                print("[probe]   %-16s %-22s %s" % (nd.name, nd.bl_idname,
                                                   " ".join(vals)))
        bsdf = W._principled(nt)
        for key in ("Base Color", "Roughness", "Specular IOR Level", "Normal"):
            s = bsdf.inputs.get(key)
            if s is None:
                continue
            src = s.links[0].from_node.bl_idname if s.is_linked else "UNLINKED"
            print("[probe]   bsdf.%-18s <- %s" % (key, src))


main()
