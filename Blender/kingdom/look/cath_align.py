"""Measure the hd_cathedral shell's inner cavity against hd_cathedral_int.

Builds the exterior shell (identity transforms) and the interior module, then
ray-casts the shell's inner faces from the axis so the report can quote real
clearance numbers instead of reading constants.  Also counts escape rays from
inside the interior with the shell present (leak test).

    python look/drive.py --tag align --lab cath_align.py -- --tag align
"""
import os
import sys
import math
import random

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import hd_common as H            # noqa: E402
import hd_cathedral as CE        # noqa: E402
import hd_cathedral_int as CI    # noqa: E402


def bb(parts):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in parts:
        if ob.type != "MESH" or ob.name not in bpy.context.scene.objects:
            continue
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    return lo, hi


def cast(o, d, dist=400.0):
    deps = bpy.context.evaluated_depsgraph_get()
    hit, loc, nrm, idx, ob, mat = bpy.context.scene.ray_cast(
        deps, Vector(o), Vector(d).normalized(), distance=dist)
    return (loc, ob.name if ob else None)


def main():
    H._clear()
    rng = random.Random(7)
    shell = CE.build(CE.mats(), rng)
    bpy.context.view_layer.update()
    slo, shi = bb(shell)
    print("[align] shell bbox lo=%s hi=%s n=%d" % (
        tuple(round(v, 2) for v in slo), tuple(round(v, 2) for v in shi), len(shell)),
        flush=True)

    # --- inner cavity of the shell, measured along the axis and across ---------
    print("[align] --- shell cavity (cast outward from the axis) ---", flush=True)
    for z in (2.0, 10.0, 16.0, 22.0):
        for (tag, o, d) in (
                ("E(apse)", (0.0, -20.0, z), (0.0, -1.0, 0.0)),
                ("W(front)", (0.0, -20.0, z), (0.0, 1.0, 0.0)),
                ("S(+x)", (0.0, -20.0, z), (1.0, 0.0, 0.0)),
                ("N(-x)", (0.0, -20.0, z), (-1.0, 0.0, 0.0))):
            loc, name = cast(o, d)
            print("[align] z=%-5.1f %-9s -> %-28s y/x=%s dist=%.2f" % (
                z, tag, str(name), round(loc.y if "W" in tag or "E" in tag else loc.x, 2),
                (loc - Vector(o)).length), flush=True)
    # transept ends
    for x in (20.0, -20.0):
        loc, name = cast((0.0, -7.5, 12.0), (1.0 if x > 0 else -1.0, 0.0, 0.0))
        print("[align] transept %s -> %-26s x=%.2f" % (
            "S" if x > 0 else "N", str(name), loc.x), flush=True)
    # roofline: straight up from the nave axis and from the crossing
    for y in (-20.0, -7.5, 5.0):
        loc, name = cast((0.0, y, 20.0), (0.0, 0.0, 1.0))
        print("[align] up y=%-6.1f -> %-26s z=%.2f" % (y, str(name), loc.z), flush=True)

    # --- interior module -------------------------------------------------------
    parts = CI.build()
    bpy.context.view_layer.update()
    ilo, ihi = bb(parts)
    print("[align] int bbox lo=%s hi=%s n=%d" % (
        tuple(round(v, 2) for v in ilo), tuple(round(v, 2) for v in ihi), len(parts)),
        flush=True)
    print("[align] int size  W=%.2f L=%.2f H=%.2f" % (
        ihi.x - ilo.x, ihi.y - ilo.y, ihi.z - ilo.z), flush=True)

    # place the interior the way the caller will, then measure the margins
    CATH_C = (-224.96, 85.84)
    rot = 0.0
    dz = 1.10
    T = (H.Matrix.Translation((CATH_C[0], CATH_C[1], dz))
         @ H.Matrix.Rotation(rot, 4, "Z")) if hasattr(H, "Matrix") else None
    if T is None:
        from mathutils import Matrix
        T = (Matrix.Translation((CATH_C[0], CATH_C[1], dz))
             @ Matrix.Rotation(rot, 4, "Z"))
    for ob in parts:
        ob.matrix_world = T @ ob.matrix_world
    bpy.context.view_layer.update()
    wlo, whi = bb(parts)
    print("[align] placed bbox lo=%s hi=%s" % (
        tuple(round(v, 2) for v in wlo), tuple(round(v, 2) for v in whi)), flush=True)

    # --- leak test: rays from inside, shell + interior present -----------------
    esc = 0
    tot = 0
    sample = []
    for p in ((0.0, -30.0, 1.72), (0.0, 0.0, 1.72), (0.0, 20.0, 1.72),
              (7.5, -20.0, 1.72), (-7.5, -20.0, 1.72), (0.0, -7.5, 12.0)):
        o = Vector(p) + T.to_translation() * 0  # already in world (parts moved)
        o = Vector((p[0] + CATH_C[0], p[1] + CATH_C[1], p[2] + dz))
        for i in range(140):
            th = math.acos(1.0 - 2.0 * (i + 0.5) / 140.0)
            ph = i * 2.399963
            d = Vector((math.sin(th) * math.cos(ph),
                        math.sin(th) * math.sin(ph),
                        math.cos(th)))
            tot += 1
            loc, name = cast(o, d)
            if name is None:
                esc += 1
                if len(sample) < 8:
                    sample.append((tuple(round(v, 1) for v in p),
                                   tuple(round(v, 2) for v in d)))
    print("[align] LEAK %d / %d rays escape (%.2f%%)" % (
        esc, tot, 100.0 * esc / max(1, tot)), flush=True)
    for s in sample:
        print("[align]   escape from %s dir %s" % (s[0], s[1]), flush=True)

    print("[align] DONE", flush=True)


main()
