"""_skysweep.py -- measure how bright the sky actually comes out.

Renders one wide shot at several hd_sky gains and prints the mean display value
of the top band (pure sky) plus the mean of the city band, so the gain can be
picked from numbers instead of eyeballing.
"""
import bpy, sys, os, math, json

sys.path.insert(0, r"E:\My World\Blender")
sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender\kingdom\look")

import hd_light as L
import hd_atmosphere as A
import hd_sky as SKY


def log(*a):
    print("[sweep]", *a)
    sys.stdout.flush()


def stats(path, bands=((0.0, 0.12, "sky_top"), (0.12, 0.30, "sky_mid"), (0.55, 1.0, "lower"))):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = list(img.pixels)
    out = {}
    for lo, hi, name in bands:
        y0 = int(h * (1.0 - hi))
        y1 = max(y0 + 1, int(h * (1.0 - lo)))
        acc = [0.0, 0.0, 0.0]
        n = 0
        for y in range(y0, y1, max(1, (y1 - y0) // 40)):
            row = y * w * 4
            for x in range(0, w, max(1, w // 80)):
                i = row + x * 4
                acc[0] += px[i]
                acc[1] += px[i + 1]
                acc[2] += px[i + 2]
                n += 1
        out[name] = tuple(round(c / max(1, n), 4) for c in acc)
    bpy.data.images.remove(img)
    return out


sc = bpy.context.scene
preset = "morning_town"
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x = 640
sc.render.resolution_y = 360
sc.render.resolution_percentage = 100
sc.eevee.taa_render_samples = 8
sc.view_settings.view_transform = "AgX"

# one rig: sun + bounce + post, no haze so the sky is not veiled
rep = L.apply(preset, sc)
log("apply ok=%d fail=%d" % (len(rep.get("ok") or []), len(rep.get("fail") or [])))

cam = bpy.data.objects.get("Camera")
if cam is None:
    cd = bpy.data.cameras.new("c")
    cd.lens = 34.0
    cam = bpy.data.objects.new("c", cd)
    sc.collection.objects.link(cam)
cam.data.lens = 34.0
cam.data.clip_end = 20000.0
cam.location = (940.0, -1180.0, 610.0)
d = (-940.0, 1160.0, -630.0)
dv = math.sqrt(sum(c * c for c in d))
# point at the city
import mathutils
fwd = mathutils.Vector(d).normalized()
cam.rotation_euler = fwd.to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam

outdir = r"E:\My World\Blender\renders\kingdom\look"
rows = []
for gain in (1.0, 2.0, 3.2, 6.0, 10.0, 16.0):
    SKY.world(sc, preset, gain=gain, elevation=48.0, azimuth=112.0)
    path = os.path.join(outdir, "_sweep_%04.1f.png" % gain)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    st = stats(path)
    rows.append((gain, st))
    log("gain %5.1f  sky_top %s  sky_mid %s  lower %s"
        % (gain, st["sky_top"], st["sky_mid"], st["lower"]))
log("SUMMARY " + json.dumps([(g, s) for g, s in rows]))
