"""Why does one hd house cost 0.1 s alone but 3 s inside the capital build?

Run:  blender -b --factory-startup --python _tmp\bench_scale.py
"""
import os
import sys
import time

BL = r"E:\My World\Blender"
KING = os.path.join(BL, "kingdom")
for p in (KING, BL):
    if p not in sys.path:
        sys.path.insert(0, p)

import bpy

import hd_common as H
import hd_houses

MAT = hd_houses.make_mats()
N = 40
rng = __import__("random").Random(7)

print("[scale] objects=%d meshes=%d mats=%d" %
      (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.materials)))
t_prev = time.time()
for i in range(N):
    t0 = time.time()
    parts = hd_houses.house(MAT, rng, kind="timber", w=7.0, d=8.5, floors=2)
    H.apply(parts, H.Matrix.Translation((i * 12.0, 0, 0)))
    t1 = time.time()
    if i < 12 or i % 5 == 0:
        print("[scale] %2d build %.3f s objects=%d meshes=%d mats=%d parts=%d" %
              (i, t1 - t0, len(bpy.data.objects), len(bpy.data.meshes),
               len(bpy.data.materials), len(parts)), flush=True)
print("[scale] total %.1f s for %d houses" % (time.time() - t_prev, N))
