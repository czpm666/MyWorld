"""Quick look at the great hall: assemble what exists and shoot it."""
import math
import os
import random
import sys
import time

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import bpy
from mathutils import Vector

import hd_common as H
import medkit as K
import hd_castle_int as C

OUT = r"E:\My World\Blender\renders\kingdom\look"


def volume(dens=0.02):
    w = bpy.data.worlds.new("W")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (0.40, 0.48, 0.62, 1.0)
    bg.inputs[1].default_value = 0.11
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = dens
    vol.inputs["Anisotropy"].default_value = 0.42
    vol.inputs["Color"].default_value = (0.88, 0.90, 0.94, 1.0)
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])


def sun(energy=9.0):
    d = bpy.data.lights.new("ci_sun", "SUN")
    d.energy = energy
    d.angle = math.radians(0.7)
    d.color = (1.0, 0.94, 0.82)
    ob = bpy.data.objects.new("ci_sun", d)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_euler = (math.radians(50.2), 0.0, math.radians(-160.1))


def area(nm, loc, rot, sx, sy, power, col):
    ld = bpy.data.lights.new(nm, "AREA")
    ld.energy = power
    ld.size = sx
    ld.size_y = sy
    ld.color = col
    o = bpy.data.objects.new(nm, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    return o


def point(nm, loc, power, col, rad=0.22):
    d = bpy.data.lights.new(nm, "POINT")
    d.energy = power
    d.shadow_soft_size = rad
    d.color = col
    o = bpy.data.objects.new(nm, d)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    return o


def main():
    t0 = time.time()
    K.reset_scene()
    rng = random.Random(3)
    M = C.make_mats()
    P = []
    P += C.build_floor(M, rng)
    P += C.side_wall(1, M, rng)
    P += C.side_wall(-1, M, rng)
    P += C.end_wall(1, M, rng)
    P += C.end_wall(-1, M, rng)
    P += C.build_roof(M, rng)
    P += C.build_dais(M)
    P += C.build_throne(M, rng)
    P += C.build_guards(M)
    P += C.build_braziers(M)
    P += C.build_candles(M)
    P += C.build_banners(M, rng)
    P += C.build_side_door(M)
    P += C.build_carpet(M)
    print("PARTS", len(P), "TRIS", H.tri_count(P), flush=True)
    H.setup_engine(samples=10, res=(480, 270), gpu=True)
    sc = bpy.context.scene
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    volume()
    sun()
    # weak fills just inside the clerestory so the upper stone is not dead
    for i in range(C.NBAY):
        xm = 0.5 * (C.BAYX[i] + C.BAYX[i + 1])
        for s in (1, -1):
            area("ci_wf", (xm, s * (C.HY - 0.15), 11.5),
                 (math.radians(90) * (-s) if s > 0 else math.radians(-90), 0, 0),
                 2.4, 3.0, 90.0, (0.80, 0.88, 1.0))
    area("ci_back", (-C.HX + 0.15, 0.0, 12.6), (0, math.radians(90), 0),
         5.2, 3.0, 900.0, (1.0, 0.93, 0.80))
    for s in (-1, 1):
        point("ci_fire", (C.DAIS_X1 + C.STEP_D * C.N_STEP + 1.35, s * 4.35, 1.20),
              420.0, (1.0, 0.44, 0.13), 0.30)
        point("ci_cand", (C.DAIS_X0 + 1.15, s * 3.95, C.Z_DAIS + 1.30),
              140.0, (1.0, 0.72, 0.36), 0.12)
    shots = [
        ("ci_A_entry", (C.HX - 2.2, 0.0, C.EYE), (-C.HX + 1.0, 0.0, 3.4), 34.0),
        ("ci_B_throne", (-5.6, 1.10, 1.85), (C.THR_X, 0.0, 2.30), 30.0),
        ("ci_C_wide", (10.2, 7.2, 1.72), (-9.5, -2.6, 2.9), 20.0),
        ("ci_D_roof", (1.0, -2.0, 1.72), (2.0, 6.0, 16.0), 18.0),
    ]
    for (nm, loc, look, lens) in shots:
        cam = C._cam(nm, loc, look, lens=lens)
        H.render_to(os.path.join(OUT, nm + ".png"), cam)
    print("DONE %.1fs" % (time.time() - t0), flush=True)


main()
