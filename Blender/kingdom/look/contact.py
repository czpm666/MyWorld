"""Contact-sheet look-dev: one rig, many cameras, cheap frames, one image.

Two modes, because there are two different questions.

  library   "which of my curated cameras actually reads?"  Renders every entry
            of a shots.json-style library at 320x180 and tiles the frames into a
            single sheet, so the whole set can be judged in one look instead of
            thirty.  This is the cheap half of the acceptance loop: iterate at
            320x180/8 spp, then spend the big samples only on the winners.

  jitter    "is there a better camera near this one?"  Takes spots.json picks
            and shakes out N random neighbours along random headings.  Kept
            from the first pass: geometric scoring of a viewpoint kept lying --
            a point can sit in a 6 m corridor and still frame nothing but roof,
            because the camera stands 20.9 m *behind* the player and the street
            bends.  Render and look; do not predict.

Usage:
    blender -b scene.blend --python look/contact.py -- --shots-file look/shots.json \
        --shots all --tag c320 --res 320x180 --samples 8 --montage 6
    blender -b scene.blend --python look/contact.py -- --n 40 --tag j1 \
        --preset morning_town --res 320x180 --samples 8

Output: <out>/<tag>_<name>.png per frame (library) or <out>/_c_<tag>_NN.png
(jitter), a manifest <out>/<tag>.json, and --montage <cols> additionally writes
<out>/sheet_<tag>.png.
"""
import json
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(KING))
sys.path.insert(0, KING)
sys.path.insert(0, HERE)

import hd_light as L                                            # noqa: E402
import hd_sky as SKY                                            # noqa: E402
import render as R                                              # noqa: E402


def arg(name, default=None):
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if name in a:
        return a[a.index(name) + 1]
    return default


def spots_json():
    with open(os.path.join(HERE, "spots.json"), "r", encoding="utf-8") as fh:
        return json.load(fh)


def candidates(n, seed=11):
    """Jitter mode: spots.json picks plus random neighbours."""
    import random
    rnd = random.Random(seed)
    picks = spots_json().get("picks") or []
    out = []
    for p in picks:
        out.append(dict(x=p["x"], y=p["y"], ux=p["ux"], uy=p["uy"], tag="spot", w=p["w"]))
    while len(out) < n:
        base = rnd.choice(picks)
        ang = rnd.uniform(0, 2 * math.pi)
        rad = rnd.uniform(4.0, 30.0)
        out.append(dict(x=base["x"] + math.cos(ang) * rad,
                        y=base["y"] + math.sin(ang) * rad,
                        ux=math.cos(ang), uy=math.sin(ang),
                        tag="jit", w=base["w"]))
    return out[:n]


def library(path, want="all"):
    """Library mode: resolve a shots.json table into an ordered name list."""
    import fnmatch
    table = R.shot_table(path)
    names = []
    for w in str(want).split(","):
        w = w.strip()
        if not w:
            continue
        if w == "all":
            names.extend(sorted(table))
        elif "*" in w or "?" in w:
            names.extend(sorted(k for k in table if fnmatch.fnmatchcase(k, w)))
        elif w in table:
            names.append(w)
        else:
            print("[contact] no shot %r" % w)
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return table, out


def montage(paths, out_path, cols, labels=None):
    """Tile PNGs into one sheet with numpy + the bpy image API (no Pillow here)."""
    import numpy as np
    cells = []
    for p in paths:
        im = bpy.data.images.load(p, check_existing=False)
        w, h = im.size
        a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        bpy.data.images.remove(im)
        cells.append(a)
    ch = max(c.shape[0] for c in cells)
    cw = max(c.shape[1] for c in cells)
    rows = int(math.ceil(len(cells) / float(cols)))
    canvas = np.zeros((rows * ch, cols * cw, 4), dtype=np.float32)
    canvas[:, :, 3] = 1.0
    for i, a in enumerate(cells):
        r, c = divmod(i, cols)
        # Blender pixel rows run bottom-up, so row 0 of the sheet is the LAST
        # band of the buffer.  Getting this wrong silently flips the sheet.
        y0 = (rows - 1 - r) * ch
        canvas[y0:y0 + a.shape[0], c * cw:c * cw + a.shape[1], :] = a
    img = bpy.data.images.new("sheet", canvas.shape[1], canvas.shape[0], alpha=True)
    img.pixels = canvas.ravel().tolist()
    img.filepath_raw = out_path
    img.file_format = "PNG"
    img.save()
    print("[contact] sheet %dx%d -> %s" % (canvas.shape[1], canvas.shape[0], out_path))
    return out_path


def main():
    tag = arg("--tag", "c1")
    preset = arg("--preset", "morning_town")
    res = arg("--res", "320x180")
    samples = int(arg("--samples", 8))
    out_dir = arg("--out-dir") or arg("--out") or \
        r"E:\My World\Blender\renders\kingdom\look"
    sky = arg("--sky", preset)
    haze_mul = float(arg("--haze-mul", "0.45"))
    ambient = arg("--ambient")
    exposure = arg("--exposure")
    sun = arg("--sun")
    lib = arg("--shots-file")
    want = arg("--shots", "all")
    # `--shots look/shots.json` is accepted as a library path, so one command
    # line can be handed to both this and look/_shotqa.py unchanged.
    if lib is None and str(want).endswith(".json"):
        lib, want = want, "all"
    n = int(arg("--n", 0))
    mont = arg("--montage")
    w, h = [int(v) for v in res.split("x")]

    sc = bpy.context.scene
    R.wipe_rig()
    R.setup_engine("eevee", samples, (w, h), vols=True)
    L.apply(preset, sc, cam=None, samples=samples, res=(w, h), contact_shadows=False)
    over = {}
    if ambient is not None:
        over["ambient"] = float(ambient)
    SKY.world(sc, sky, **over)
    if exposure is not None:
        sc.view_settings.exposure = float(exposure)
    if sun is not None:
        for ob in bpy.data.objects:
            if ob.type == "LIGHT" and ob.data.type == "SUN":
                ob.data.energy = float(sun)

    frames = []          # (name, path, note)
    if lib or n == 0:
        table, names = library(lib, want)
        if not names:
            print("[contact] nothing to render")
            return
        for i, name in enumerate(names):
            spec = dict(table[name])
            cam_ob = R.make_camera(spec)
            sc.camera = cam_ob
            path = os.path.join(out_dir, "%s_%s.png" % (tag, name))
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            frames.append((name, path, spec.get("note", "")))
            print("[contact] %02d/%d  %s" % (i + 1, len(names), name), flush=True)
    else:
        cands = candidates(n)
        cam_ob = R.make_camera(dict(loc=(0, 0, 40), look=(0, 1, 0), vfov=30.0))
        sc.camera = cam_ob
        import mathutils
        for i, c in enumerate(cands):
            loc, tgt = R.game_cam(((c["x"], c["y"], 1.0),
                                   (c["x"] + c["ux"] * 1.5,
                                    c["y"] + c["uy"] * 1.5, 1.0)))
            cam_ob.location = loc
            d = mathutils.Vector(tgt) - mathutils.Vector(loc)
            cam_ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
            path = os.path.join(out_dir, "_c_%s_%02d.png" % (tag, i))
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            frames.append(("c%02d" % i, path, "%s (%.0f,%.0f)" % (c["tag"], c["x"], c["y"])))
            print("[contact] %02d/%d  (%.0f,%.0f) %s"
                  % (i + 1, n, c["x"], c["y"], c["tag"]), flush=True)

    with open(os.path.join(out_dir, "%s.json" % tag), "w", encoding="utf-8") as fh:
        json.dump([{"name": a, "path": b, "note": c} for a, b, c in frames], fh, indent=1)
    if mont:
        montage([b for _, b, _ in frames],
                os.path.join(out_dir, "sheet_%s.png" % tag), int(mont))
    print("[contact] done %d frames" % len(frames))


if __name__ == "__main__":
    main()
