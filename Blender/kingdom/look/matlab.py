"""Material lab: judge one ground material at a time, at the game camera's scale.

The 2.5D camera sits 34 m from the player looking down 52 deg with a 30 deg
vertical fov, so it sees ~32 m across 1280 px: one pixel is 2.5 cm of ground.
A 16 cm sett is six pixels -- legible, but only if the joint is drawn wide and
the stone faces are separated in value.  This tool renders one 24 x 24 m panel
per material from exactly that camera, so paving can be judged instead of
guessed.

    blender -b --factory-startup --python look/matlab.py -- --paving \
        --out DIR [--mats cobble,street] [--size 24] [--samples 48]
"""
import os
import sys
import math
import time

import bpy
import bmesh
from mathutils import Vector

# the real in-game camera (TopDownCameraRig defaults, 16:9)
PITCH = 52.0
DIST = 34.0
VFOV = 30.0
LENS = 18.0 / math.tan(math.radians(VFOV) * 0.5)     # 36 mm sensor -> 37.8 mm


def opts():
    a = sys.argv
    a = a[a.index("--") + 1:] if "--" in a else []
    o, i = {}, 0
    while i < len(a):
        if a[i].startswith("--"):
            k = a[i][2:]
            if i + 1 < len(a) and not a[i + 1].startswith("--"):
                o[k] = a[i + 1]
                i += 2
            else:
                o[k] = True
                i += 1
        else:
            i += 1
    return o


def plane(name, cx, cy, size, mat):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    h = size * 0.5
    vs = [bm.verts.new((cx - h, cy - h, 0.0)), bm.verts.new((cx + h, cy - h, 0.0)),
          bm.verts.new((cx + h, cy + h, 0.0)), bm.verts.new((cx - h, cy + h, 0.0))]
    bm.faces.new(vs)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def main():
    o = opts()
    for ob in list(bpy.data.objects):          # --factory-startup leaves a cube
        bpy.data.objects.remove(ob, do_unlink=True)
    out = o.get("out", r"E:\My World\Blender\renders\kingdom\look")
    os.makedirs(out, exist_ok=True)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import capital as C
    C.init_mats()
    MAT = C.MAT
    if o.get("paving"):
        import hd_paving as PV
        PV.rebuild(MAT)

    want = [s for s in (o.get("mats") or "").split(",") if s]
    names = want or ["cobble", "street", "town_ground", "flag", "earth", "grass",
                     "stone_warm", "hill"]
    names = [n for n in names if n in MAT]
    size = float(o.get("size", 24.0))
    step = size + 4.0

    # one panel, moved between shots -- the camera never has to hunt for it
    panel = plane("lab", 0.0, 0.0, size, MAT[names[0]])

    import hd_light as L
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.use_raytracing = True
    sc.eevee.taa_render_samples = int(o.get("samples", 48))
    sc.view_settings.view_transform = "AgX"
    rep = L.apply("morning_town", sc, cam=None, samples=int(o.get("samples", 48)),
                  res=(1280, 720))
    print("[matlab] light ok=%d fail=%d" % (len(rep.get("ok") or []),
                                            len(rep.get("fail") or [])), flush=True)

    cam_d = bpy.data.cameras.new("labcam")
    cam = bpy.data.objects.new("labcam", cam_d)
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    cam_d.lens = LENS
    cam_d.sensor_width = 36.0
    cam_d.clip_end = 3000.0
    rad = math.radians(PITCH)
    cam.location = (0.0, -DIST * math.cos(rad), DIST * math.sin(rad))
    d = Vector(cam.location) - Vector((0.0, 0.0, 0.0))
    cam.rotation_euler = d.to_track_quat("Z", "Y").to_euler()

    sc.render.resolution_x = 1280
    sc.render.resolution_y = 720
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"

    for n in names:
        panel.data.materials[0] = MAT[n]
        sc.render.filepath = os.path.join(out, "lab_%s%s.png" % (n, o.get("suffix", "")))
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print("[matlab] %-12s %5.1f s -> %s" % (n, time.time() - t0, sc.render.filepath),
              flush=True)


main()
