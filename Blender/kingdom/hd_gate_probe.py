"""Throw-away probe: can we cut real window holes into a tower drum?"""
import bpy
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
for p in (_HERE, os.path.dirname(_HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import hd_common as H
import medkit as K
from medkit import T_at as Ts, box, cyl, cone

OUT = r"E:\My World\Blender\renders\kingdom"


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def cutter_boxes(name, specs, mat):
    obs = []
    for i, (T, size) in enumerate(specs):
        obs.append(box("%s_%d" % (name, i), T, size, mat))
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


def cut(target, cutter):
    m = target.modifiers.new("cut", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.solver = "EXACT"
    m.object = cutter
    bpy.context.view_layer.objects.active = target
    t0 = time.time()
    bpy.ops.object.modifier_apply(modifier=m.name)
    print("  boolean %.2fs" % (time.time() - t0))
    bpy.data.objects.remove(cutter, do_unlink=True)
    return target


def main():
    clear()
    M = H.setup_world(sun_energy=4.2)
    stone = K.mat_stone()

    t0 = time.time()
    shaft = cyl("shaft", Ts(0, 0, 11.5), 8.0, 23.0, stone, seg=96)
    print("shaft tris", len(shaft.data.polygons), "verts", len(shaft.data.vertices))
    specs = []
    for k, ang in enumerate((0.0, 40.0, 80.0, 130.0, 210.0, 300.0)):
        a = math.radians(ang)
        # cutter centre on the drum surface, pushed outward so it cuts a blind
        # recess 0.9 m deep: box is 1.6 deep in local Y, centred at r+0.8-0.9
        T = Ts(math.cos(a) * (8.0 + 0.8 - 0.45), math.sin(a) * (8.0 + 0.8 - 0.45), 18.6,
               rz=a + math.pi * 0.5)
        specs.append((T, (1.35, 1.6, 3.3)))
    c = cutter_boxes("cut", specs, stone)
    cut(shaft, c)
    print("cut tris", len(shaft.data.polygons), "verts", len(shaft.data.vertices),
          "total %.2fs" % (time.time() - t0))

    # small arched window cutter: rectangle + half cylinder on top
    # (test only the boolean robustness of a cylinder-capped cutter)
    specs2 = []
    a = math.radians(180)
    T = Ts(math.cos(a) * 8.0, math.sin(a) * 8.0, 8.0, rz=a + math.pi * 0.5)
    specs2.append((T, (0.4, 1.4, 1.4)))
    c2 = cutter_boxes("cut2", specs2, stone)
    cut(shaft, c2)

    # a flat gatehouse face with a blind recess
    body = box("body", Ts(0, 0, 5), (20.0, 10.0, 10.0), stone)
    specs3 = []
    for x in (-5.0, 0.0, 5.0):
        T = Ts(x, 5.0 + 0.9 - 0.35, 6.0)
        specs3.append((T, (2.4, 1.8, 3.4)))
    c3 = cutter_boxes("cut3", specs3, stone)
    cut(body, c3)
    print("body tris", len(body.data.polygons))

    cam = H.camera("cam", (26.0, 22.0, 17.0), (0, 0, 15.0), 55)
    H.setup_engine(samples=24, res=(900, 700), gpu=True)
    H.render_to(os.path.join(OUT, "hd_gate_probe.png"), cam)
    print("probe done")


if __name__ == "__main__":
    main()
