"""Re-frame an already-built village .blend and re-render (no geometry rebuild).

usage: blender -b --factory-startup --python recam.py -- --variant farm_c \
        --cams x,y,z:tx,ty,tz:lens;... [--final x,y,z:tx,ty,tz:lens]
Renders each candidate at 640x360 as renders/kingdom/probe_<v>_<i>.png, and if
--final is given, renders 1280x720 to renders/kingdom/<v>.png and re-saves the .blend.
"""
import bpy
import os
import sys
import math
from mathutils import Vector

BL = r"E:\My World\Blender"
KD = os.path.join(BL, "kingdom")
RD = os.path.join(BL, "renders", "kingdom")

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opt = {}
i = 0
while i < len(argv):
    if argv[i].startswith("--"):
        opt[argv[i][2:]] = argv[i + 1] if i + 1 < len(argv) else ""
        i += 2
    else:
        i += 1

variant = opt.get("variant", "farm_c")


def parse(s):
    c, t, lens = s.split(":")
    return ([float(v) for v in c.split(",")],
            [float(v) for v in t.split(",")], float(lens))


def set_cam(loc, target, lens):
    for o in [o for o in bpy.data.objects if o.type == "CAMERA"]:
        bpy.data.objects.remove(o, do_unlink=True)
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    ob = bpy.data.objects.new("cam", cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector(loc)
    d = (Vector(target) - Vector(loc)).normalized()
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    return ob


bpy.ops.wm.open_mainfile(filepath=os.path.join(KD, variant + ".blend"))
sc = bpy.context.scene
sc.render.resolution_x = 640
sc.render.resolution_y = 360
sc.eevee.taa_render_samples = 24
if "cams" in opt:
    for k, spec in enumerate([s for s in opt["cams"].split(";") if s]):
        loc, tgt, lens = parse(spec)
        set_cam(loc, tgt, lens)
        sc.render.filepath = os.path.join(RD, "probe_%s_%d.png" % (variant, k))
        bpy.ops.render.render(write_still=True)
        print("PROBE %s_%d %s" % (variant, k, spec))
if "final" in opt:
    loc, tgt, lens = parse(opt["final"])
    set_cam(loc, tgt, lens)
    sc.render.resolution_x = 1280
    sc.render.resolution_y = 720
    sc.eevee.taa_render_samples = 96
    sc.render.filepath = os.path.join(RD, variant + ".png")
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(KD, variant + ".blend"))
    print("FINAL %s %s" % (variant, opt["final"]))
