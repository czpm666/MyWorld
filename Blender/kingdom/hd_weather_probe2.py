# -*- coding: utf-8 -*-
"""Diagnostic 2c: isolated snow-panel measurement.

No town.  Empty scene -> house materials -> snow applied -> three panels
(flat roof, 52 deg roof, flat flagstone) filling the frame.  The mean colour of
each panel is printed, so the mask can be read directly.

    blender -b --factory-startup --python-exit-code 1 --python hd_weather_probe2.py
"""
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "look")):
    if p not in sys.path:
        sys.path.insert(0, p)

import bpy                                                    # noqa: E402
from mathutils import Vector, Matrix                          # noqa: E402


def main():
    import hd_weather as W
    import hd_common as H
    import hd_houses as HS
    import hd_surface as SFC
    import look.render as R
    import hd_light as L

    H._clear()
    sc = bpy.context.scene
    MAT = HS.make_mats()
    try:
        SFC.apply_weathering(MAT)
    except Exception as exc:                                   # noqa: BLE001
        print("[p2] weathering skipped:", exc)
    roof = MAT.get("tile") or MAT.get("slate")
    flag = MAT.get("flag") or MAT.get("cobble") or MAT.get("stone")
    print("[p2] roof=%s flag=%s" % (roof.name if roof else None,
                                    flag.name if flag else None))
    cfg = W.state("snow")
    n = W.apply_materials(MAT, cfg)
    print("[p2] apply_materials -> %d (wet %.2f snow %.2f)"
          % (n, cfg["wetness"], cfg["snow_cover"]))

    specs = (("A_flat_roof", roof, Matrix.Translation((-3.0, 0.0, 1.6))),
             ("B_pitch52", roof, Matrix.Translation((0.0, 0.0, 1.9))
              @ Matrix.Rotation(math.radians(-52.0), 4, "X")),
             ("C_flag", flag, Matrix.Translation((3.0, 0.0, 1.6))))
    for name, mat, T in specs:
        me = bpy.data.meshes.new(name + "_me")
        me.from_pydata([(-1.3, -1.3, 0), (1.3, -1.3, 0), (1.3, 1.3, 0), (-1.3, 1.3, 0)],
                       [], [(0, 1, 2, 3)])
        me.update()
        ob = bpy.data.objects.new(name, me)
        ob.data.materials.append(mat)
        sc.collection.objects.link(ob)
        ob.matrix_world = T
        print("[p2] %-12s nz=%.2f" % (
            name, (T.to_3x3() @ Vector((0, 0, 1))).normalized().z))

    R.setup_engine("eevee", 8, (320, 180))
    L.sky("overcast_soft", 28.0, 160.0)
    L.sun("overcast_soft", 28.0, 160.0)
    w = sc.world
    if w and w.node_tree:
        for nd in w.node_tree.nodes:
            if nd.bl_idname == "ShaderNodeBackground":
                nd.inputs["Strength"].default_value = 3.0
    cam = H.camera("p2cam", (0.0, -7.2, 1.75), (0.0, 0.0, 1.72), 50.0)
    out = r"E:\My World\Blender\renders\kingdom\look\WX_probe2.png"
    H.render_to(out, cam)
    img = bpy.data.images.load(out)
    px = list(img.pixels)
    wd, ht = img.size
    for label, (x0, x1) in (("A_flat_roof ", (0.10, 0.28)),
                            ("B_pitch52   ", (0.44, 0.56)),
                            ("C_flag      ", (0.72, 0.90))):
        acc = [0.0, 0.0, 0.0]
        cnt = 0
        for y in range(int(0.42 * ht), int(0.58 * ht)):
            for x in range(int(x0 * wd), int(x1 * wd)):
                i = (y * wd + x) * 4
                acc[0] += px[i]
                acc[1] += px[i + 1]
                acc[2] += px[i + 2]
                cnt += 1
        print("[p2] %s rgb=%.3f %.3f %.3f" % (label, acc[0] / cnt, acc[1] / cnt,
                                              acc[2] / cnt))


main()
