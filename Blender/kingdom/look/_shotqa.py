"""Content-composition QA for a camera against a built .blend.

Why this exists
---------------
Two of the five "hero" shots in v24 were unusable and nobody could see it from
the numbers: `V24_plaza.png` was shot from *inside* the market hall, and every
`street*` frame was a single wall because spots.py only tested ground clearance,
never the volume above it.  Both faults are invisible in a contact sheet until
you look at the picture, and by then a 1280x720 render has been spent.

This module answers the question *before* the render: **what is in this frame,
in what proportion?**  It fires an N x M ray grid through the camera and sorts
every hit by material family and surface orientation:

    sky      no hit
    ground   paving / earth / grass, or a horizontal surface below head height
    roof     roof materials, or any horizontal wall top above 3 m
    facade   a vertical wall
    other    props, cloth, iron, trees, water, rock faces

It also runs the three geometric tests that the old spot picker was missing:

    stand    (eye shots) the camera is 1.72 m over a flat floor, not floating
             or sunk, and 1.2 m of clear air surrounds it at eye height
    los      (eye shots) how far you can see along the view axis at eye height
    inside   nothing overhead / not boxed in -- the `plaza` camera failed here

Usage (must run inside Blender, the .blend is the geometry)

    blender -b capital_v24.blend --python look/_shotqa.py -- \
        --shots look/shots.json --all --res 24x14 --ascii --seg look/_qa_seg

    # one shot, ad hoc camera, no shots.json needed
    blender -b capital_v24.blend --python look/_shotqa.py -- \
        --pos 13.6,32.6,12 --look 13.6,136,6 --lens 35 --name probe

Outputs `look/_qa.json` (per-shot stats + verdict) and, with `--seg`, one
false-colour segmentation PNG per shot so a human can see *where* the classes
land.  Exit code is 0 whatever the verdict; the JSON is the contract.

The classification table is data, not code: `--raw` prints the material-name
histogram per shot so a new asset family can be added to FAMILY in one line.
"""
import json
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.dirname(HERE)
ROOT = os.path.dirname(KING)
for _p in (ROOT, KING, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DEFAULT_SHOTS = os.path.join(HERE, "shots.json")
DEFAULT_OUT = os.path.join(HERE, "_qa.json")

# --------------------------------------------------------------------------- #
#  material name -> family.  Substring match, first rule wins, so the list is
#  ordered from most specific to most general.  The vocabulary below is the one
#  that is actually in capital_v24.blend (225 materials, dumped with `--raw`):
#
#    hu_roof_hd_tile_slate0_086 / _terra1_112   roofs, 8 variants x 3 tones
#    hd_plaster_c0..c7 / hd_plaster_back*       house walls
#    hd_stone_pale / hd_stone_dark / hd_slate   house stone + slate
#    mkt_*                                      market hall family
#    cob_a/b/c, cobble, flag, land_ground       paving
#    cloth_*, glass*, glow*, iron, bronze       props and windows
#
#  Anything unmatched lands in "other" and `--raw` prints it, so extending this
#  table is a one-line edit and never a code change.
# --------------------------------------------------------------------------- #
FAMILY = [
    # roofing (before "tile"/"stone" so hu_roof_hd_tile_* is not read as paving)
    ("roof", "roof"), ("slate", "roof"), ("tile", "roof"), ("shingle", "roof"),
    ("thatch", "roof"), ("terracotta", "roof"),
    # walls
    ("plaster", "wall"), ("stucco", "wall"), ("timber", "wall"),
    ("stone", "wall"), ("brick", "wall"), ("marble", "wall"), ("ashlar", "wall"),
    # paving and open ground
    ("cob", "ground"), ("flag", "ground"), ("street", "ground"),
    ("paving", "ground"), ("ground", "ground"), ("earth", "ground"),
    ("dirt", "ground"), ("gravel", "ground"), ("mud", "ground"),
    ("sand", "ground"), ("grass", "ground"), ("field", "ground"),
    ("crop", "ground"),
    # landform
    ("hill", "terrain"), ("cliff", "terrain"), ("mountain", "terrain"),
    ("rock", "terrain"), ("snow", "terrain"),
    # vegetation
    ("leaf", "tree"), ("foliage", "tree"), ("tree", "tree"), ("bush", "tree"),
    ("hedge", "tree"), ("vine", "tree"), ("pine", "tree"), ("moss", "tree"),
    ("lichen", "tree"),
    # water
    ("water", "water"),
    # fills: these are the black interior cards that made V24_plaza unreadable
    ("void", "void"), ("shadow", "void"), ("interior", "void"),
    # props
    ("cloth", "prop"), ("banner", "prop"), ("fabric", "prop"),
    ("canvas", "prop"), ("awn", "prop"), ("glass", "prop"), ("glow", "prop"),
    ("lamp", "prop"), ("torch", "prop"), ("fire", "prop"), ("iron", "prop"),
    ("metal", "prop"), ("steel", "prop"), ("bronze", "prop"), ("lead", "prop"),
    ("brass", "prop"), ("gold", "prop"), ("rope", "prop"), ("crate", "prop"),
    ("barrel", "prop"), ("cart", "prop"), ("stall", "prop"), ("sign", "prop"),
    ("wheel", "prop"), ("pot", "prop"), ("wood", "prop"),
]

# classes used in the 5-bucket summary the brief asks for
BUCKETS = ("sky", "ground", "roof", "facade", "other")

# a flat hit counts as "street" only inside this radius; see summarise()
NEAR_GROUND = 400.0

COLOURS = {
    "sky": (96, 148, 214),
    "ground": (150, 138, 108),
    "roof": (188, 74, 52),
    "facade": (226, 208, 176),
    "tree": (54, 104, 48),
    "water": (44, 96, 132),
    "prop": (232, 196, 72),
    "rock": (128, 120, 110),
    "void": (20, 20, 24),
    "other": (200, 60, 200),
}
GLYPH = {
    "sky": ".", "ground": "-", "roof": "^", "facade": "|", "tree": "T",
    "water": "~", "prop": "*", "rock": "#", "void": "X", "other": "?",
}


def family_of(mat):
    """Material name -> family, by first matching substring."""
    m = (mat or "").lower()
    if not m:
        return "other"
    for k, fam in FAMILY:
        if k in m:
            return fam
    return "other"


def classify(mat, nz, z):
    """(material, surface normal z, hit height) -> one of the detail classes.

    Orientation decides first, because a wall material and a roof material are
    the same mesh family in this city: `hd_plaster_*` on a horizontal top at
    8 m is a flat roof or a parapet, not a wall.  Material then decides for
    faces that are neither flat-up nor vertical (a 50 deg tile face has
    nz ~ 0.64 and must read as roof, not facade).
    """
    fam = family_of(mat)
    if fam in ("tree", "water", "prop", "void"):
        return fam
    if fam == "terrain":
        return "ground" if nz > 0.55 else "rock"
    if nz > 0.80:
        return "roof" if z > 3.0 else "ground"   # slab, step, market floor
    if nz < -0.55:
        return "prop"                            # soffit, underside of a jetty
    if fam == "roof":
        return "roof"
    if fam == "ground":
        return "ground"
    return "facade"


def bucket_of(cls):
    if cls in ("sky", "ground", "roof", "facade"):
        return cls
    return "other"


# --------------------------------------------------------------------------- #
#  camera basis
# --------------------------------------------------------------------------- #
def basis(pos, look):
    """Camera forward/right/up for a look-at, plus the two half-angle tangents.

    The tangents must match `render.make_camera` exactly or the statistics
    describe a frame that was never rendered: with a `fov` the camera uses
    sensor_fit VERTICAL / sensor_height 24, so tan(v/2) = tan(fov/2); without
    one it uses sensor_fit HORIZONTAL / sensor_width 36, so tan(h/2) = 18/lens.
    """
    f = np.array(look, dtype=np.float64) - np.array(pos, dtype=np.float64)
    n = np.linalg.norm(f)
    f = f / n if n > 1e-9 else np.array([0.0, 1.0, 0.0])
    r = np.cross(f, np.array([0.0, 0.0, 1.0]))
    rn = np.linalg.norm(r)
    r = r / rn if rn > 1e-9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(r, f)
    return f, r, u


def tangents(spec, aspect):
    if spec.get("fov"):
        th = math.tan(math.radians(float(spec["fov"]) * 0.5))
        return th * aspect, th
    lens = float(spec.get("lens") or 35.0)
    tw = 18.0 / lens
    return tw, tw / aspect


# --------------------------------------------------------------------------- #
#  the ray grid
# --------------------------------------------------------------------------- #
def _mat_of(ob, idx):
    if ob is None or ob.type != "MESH":
        return ""
    mats = ob.data.materials
    if not mats:
        return ""
    try:
        slot = ob.data.polygons[idx].material_index
    except (IndexError, TypeError):
        slot = 0
    if 0 <= slot < len(mats) and mats[slot] is not None:
        return mats[slot].name
    return ""


def sample(scene, dg, pos, spec, nx=24, ny=14, aspect=16.0 / 9.0):
    """Cast the grid.  Returns a list of dicts, row 0 = top of the frame."""
    f, r, u = basis(pos, spec["look"])
    tw, th = tangents(spec, aspect)
    eye = np.array(pos, dtype=np.float64)
    rows = []
    for j in range(ny):
        gy = 1.0 - 2.0 * (j + 0.5) / ny
        row = []
        for i in range(nx):
            gx = -1.0 + 2.0 * (i + 0.5) / nx
            v = f + r * (gx * tw) + u * (gy * th)
            v = v / np.linalg.norm(v)
            hit, loc, nrm, idx, ob, _m = scene.ray_cast(dg, eye, v)
            if not hit:
                row.append(dict(cls="sky", mat="", obj="", d=0.0, z=0.0,
                                nz=0.0, x=0.0, y=0.0))
                continue
            mat = _mat_of(ob, idx)
            d = float(np.linalg.norm(np.array(loc) - eye))
            row.append(dict(cls=classify(mat, float(nrm.z), float(loc.z)),
                            mat=mat, obj=(ob.name if ob else ""), d=d,
                            z=float(loc.z), nz=float(nrm.z),
                            x=float(loc.x), y=float(loc.y)))
        rows.append(row)
    return rows


def summarise(rows):
    n = sum(len(r) for r in rows)
    det = {}
    buck = dict((b, 0) for b in BUCKETS)
    mats = {}
    objs = {}
    near = 0
    near_ground = 0
    ds = []
    nearest = None
    for row in rows:
        for h in row:
            c = h["cls"]
            det[c] = det.get(c, 0) + 1
            buck[bucket_of(c)] += 1
            # `land_terrain` is one mesh that is both the city's paving base and
            # the plain out to the horizon, so a flat hit is only "street" if it
            # is close: otherwise a camera on a hill scores 40% ground by looking
            # at a field 2 km away.  Keep both numbers.
            if c == "ground" and h["d"] <= NEAR_GROUND:
                near_ground += 1
            if h["mat"]:
                mats[h["mat"]] = mats.get(h["mat"], 0) + 1
            if h["obj"]:
                objs[h["obj"]] = objs.get(h["obj"], 0) + 1
            if c != "sky":
                ds.append(h["d"])
                if h["d"] < 3.0:
                    near += 1
                if nearest is None or h["d"] < nearest["d"]:
                    nearest = dict(obj=h["obj"], mat=h["mat"],
                                   d=round(h["d"], 2), z=round(h["z"], 2),
                                   cls=c)
    hit = len(ds)
    top = sorted(objs.items(), key=lambda kv: -kv[1])[:4]
    out = {
        "rays": n,
        "detail": dict((k, round(v / float(n), 4)) for k, v in
                       sorted(det.items(), key=lambda kv: -kv[1])),
        "buckets": dict((k, round(v / float(n), 4)) for k, v in buck.items()),
        "ground_near": round(near_ground / float(n), 4),
        "materials": dict(sorted(mats.items(), key=lambda kv: -kv[1])[:12]),
        "objects": len(objs),
        "top_objects": [[k, round(v / float(max(1, hit)), 3)] for k, v in top],
        "top1_share": round(top[0][1] / float(max(1, hit)), 3) if top else 0.0,
        "nearest": nearest,
        "near3": round(near / float(max(1, n)), 4),
        "hit_d_med": round(float(np.median(ds)), 2) if ds else 0.0,
        "hit_d_min": round(float(min(ds)), 2) if ds else 0.0,
        "hit_z_med": round(float(np.median([h["z"] for row in rows
                                            for h in row if h["cls"] != "sky"])), 2)
        if any(h["cls"] != "sky" for row in rows for h in row) else 0.0,
    }
    return out


# --------------------------------------------------------------------------- #
#  geometry tests: am I inside something?  can I stand here?  can I see?
# --------------------------------------------------------------------------- #
_AXES = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def probe_solid(scene, dg, pos, reach=60.0):
    """Is the camera boxed in?  Six axis rays; `up` is the decisive one.

    A street camera sees sky straight up.  A camera inside the market hall sees
    the underside of the roof, and that single number is what `plaza` needed.
    """
    eye = np.array(pos, dtype=np.float64)
    hits = []
    for a in _AXES:
        v = np.array(a, dtype=np.float64)
        hit, loc, nrm, idx, ob, _m = scene.ray_cast(dg, eye, v, distance=reach)
        hits.append((float(np.linalg.norm(np.array(loc) - eye)) if hit else -1.0,
                     _mat_of(ob, idx) if hit else "", (ob.name if hit and ob else "")))
    up = hits[4]
    down = hits[5]
    # Five of six axis rays hit in any dense alley, so a raw count is not a
    # verdict.  What actually means "inside a solid" is a roof overhead: an
    # eye-level street camera sees sky straight up, a camera buried in the
    # market hall sees the underside of a roof 4.7 m above it.
    boxed = up[0] >= 0.0 and up[0] < 30.0
    wedged = sum(1 for h in hits[:4] if 0.0 <= h[0] < 1.6) == 4
    return {
        "up_hit": up[0] >= 0.0,
        "ceiling": round(up[0], 2) if up[0] >= 0.0 else None,
        "ceiling_mat": up[1],
        "ground": round(down[0], 2) if down[0] >= 0.0 else None,
        "ground_mat": down[1],
        "boxed": boxed,
        "wedged": wedged,
        "enclosed": sum(1 for h in hits if 0.0 <= h[0] < reach) >= 5,
        "axis": dict(zip(("+x", "-x", "+y", "-y", "+z", "-z"),
                         [round(h[0], 2) for h in hits])),
    }


def probe_stand(scene, dg, pos, eye_h=1.72, want=1.2):
    """Eye-height standability: flat floor underfoot, clear air around the head.

    The old spots.py checked clearance in plan only.  A 1.72 m eye needs the
    volume from 0.2 m to 1.9 m to be empty for `want` metres in every direction,
    which is what stops the camera being buried in a jetty, an awning or a
    signboard.
    """
    eye = np.array(pos, dtype=np.float64)
    down_hit, loc, _n, _i, ob, _m = scene.ray_cast(dg, eye, np.array((0, 0, -1.0)),
                                                  distance=6.0)
    stand_h = float(pos[2] - loc.z) if down_hit else None
    # floor flatness: 4 down rays 1.2 m out
    zs = []
    for a in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        o = eye + np.array((a[0] * 1.2, a[1] * 1.2, 0.0))
        h2, l2, _n2, _i2, _o2, _m2 = scene.ray_cast(dg, o, np.array((0, 0, -1.0)),
                                                   distance=6.0)
        if h2:
            zs.append(float(l2.z))
    spread = (max(zs) - min(zs)) if len(zs) >= 3 else None
    # horizontal air at eye height and at 0.4 m (a step/knee) and 1.7 m (a jetty)
    blocked = {}
    for hgt in (0.35, 1.0, 1.72, 2.05):
        o = eye + np.array((0.0, 0.0, hgt - eye_h))
        worst = want
        for k in range(12):
            a = k * math.pi / 6.0
            v = np.array((math.cos(a), math.sin(a), 0.0))
            hit, l3, _n3, _i3, ob3, _m3 = scene.ray_cast(dg, o, v, distance=want)
            if hit:
                worst = min(worst, float(np.linalg.norm(np.array(l3) - o)))
        blocked["%.2f" % hgt] = round(worst, 3)
    clear = min(blocked.values())
    return {
        "stand_h": round(stand_h, 2) if stand_h is not None else None,
        "floor_spread": round(spread, 2) if spread is not None else None,
        "eye_clear": clear,
        "clear_by_height": blocked,
        # 0.75 m is a shoulder-width alley, which is a real street in this town
        # (diag_eye_pick4 read 0.90 m and was a good frame); 1.2 m is comfortable.
        "tight": clear < 1.2,
        "ok": bool(stand_h is not None and 1.10 <= stand_h <= 2.30
                   and (spread is None or spread < 1.2) and clear >= 0.75),
    }


def probe_los(scene, dg, pos, look, eye_h=1.72, near=12.0, far=60.0):
    """How far the view axis stays open at eye height, and what stops it."""
    f, _r, _u = basis(pos, look)
    f = f.copy()
    f[2] = 0.0
    n = np.linalg.norm(f)
    if n < 1e-6:
        return {"los": 0.0, "los_12": False, "stop_mat": "", "stop_z": 0.0}
    f /= n
    eye = np.array(pos, dtype=np.float64)
    eye[2] = pos[2]
    step = 0.5
    t = 0.0
    while t < far:
        t += step
        o = eye + f * t
        hit, loc, _n2, idx, ob, _m = scene.ray_cast(dg, o, f, distance=step + 0.02)
        if hit and np.linalg.norm(np.array(loc) - o) < step * 0.9:
            return {"los": round(t, 1), "los_12": t >= near,
                    "stop_mat": _mat_of(ob, idx), "stop_z": round(float(loc.z), 2),
                    "stop_d": round(t, 1)}
    return {"los": far, "los_12": True, "stop_mat": "", "stop_z": 0.0,
            "stop_d": far}


# --------------------------------------------------------------------------- #
#  verdict
# --------------------------------------------------------------------------- #
#  What a usable frame looks like, per kind.  `ground` is the street; the whole
#  point of the game_* set is that the street survives the 52 deg roof field.
RULES = {
    "game":     dict(min_ground=0.10, max_sky=0.40, min_facade=0.10, max_roof=0.85,
                     near_ground=True),
    "eye":      dict(min_ground=0.06, max_sky=0.45, min_facade=0.12, max_roof=0.80,
                     near_ground=True),
    "aerial":   dict(min_ground=0.05, max_sky=0.55, min_facade=0.03, max_roof=0.95),
    "overview": dict(min_ground=0.03, max_sky=0.60, min_facade=0.02, max_roof=0.95),
    "landmark": dict(min_ground=0.05, max_sky=0.55, min_facade=0.10, max_roof=0.95,
                     near_ground=True),
}


def verdict(spec, stats, solid, stand, los):
    kind = str(spec.get("kind") or "landmark")
    rule = RULES.get(kind, RULES["landmark"])
    b = stats["buckets"]
    bad, warn = [], []
    if solid.get("boxed"):
        bad.append("ceiling %.1f m above the camera (%s) -- the camera is inside "
                   "a solid" % (solid["ceiling"], solid["ceiling_mat"] or "?"))
    if solid.get("wedged"):
        warn.append("all four horizontals hit within 1.6 m -- wedged in a slot")
    if stats["near3"] > 0.55:
        bad.append("%.0f%% of the frame is closer than 3 m -- nose against a surface"
                   % (100 * stats["near3"]))
    if b["sky"] > rule["max_sky"]:
        bad.append("sky %.0f%% (max %.0f%%)" % (100 * b["sky"], 100 * rule["max_sky"]))
    g = stats["ground_near"] if rule.get("near_ground") else b["ground"]
    min_g = rule["min_ground"]
    if kind == "landmark" and b["roof"] >= 0.12 and (g + b["roof"]) >= 0.20:
        # A landmark read over its own roofscape is a real frame, not a wall:
        # the cathedral and the guild are 40 m tall in 18 m fabric, so the
        # foreground has to be roofs unless you stand in their own forecourt.
        min_g = 0.0
    if g < min_g:
        bad.append("ground/street %.0f%% (min %.0f%%)"
                   % (100 * g, 100 * min_g))
    if b["facade"] < rule["min_facade"]:
        bad.append("facade %.0f%% (min %.0f%%)"
                   % (100 * b["facade"], 100 * rule["min_facade"]))
    if b["roof"] > rule["max_roof"]:
        bad.append("roof %.0f%% (max %.0f%%)" % (100 * b["roof"], 100 * rule["max_roof"]))
    if b["roof"] > 0.90:
        bad.append("roof field %.0f%% -- this is a roof close-up, not a street"
                   % (100 * b["roof"]))
    if b["facade"] > 0.80:
        bad.append("facade %.0f%% -- the frame is one wall" % (100 * b["facade"]))
    if stats["detail"].get("void", 0.0) > 0.18:
        bad.append("%.0f%% of the frame is void/shadow fill -- the camera is "
                   "looking at the back of a shell"
                   % (100 * stats["detail"]["void"]))
    if kind == "eye":
        if stand is None or not stand["ok"]:
            bad.append("cannot stand: %s" % _stand_why(stand))
        elif stand.get("tight"):
            warn.append("only %.2f m of clear air around the eye" % stand["eye_clear"])
        if los is None or not los["los_12"]:
            bad.append("view axis blocked after %.1f m" % (los["los"] if los else 0.0))
    if kind == "game" and b["ground"] < 0.16:
        warn.append("street is only %.0f%% of the frame" % (100 * b["ground"]))
    if kind in ("aerial", "overview") and b["sky"] > 0.45:
        warn.append("sky %.0f%% -- the city is small in frame" % (100 * b["sky"]))
    if stats["top1_share"] > 0.70 and stats["top_objects"]:
        warn.append("one object (%s) is %.0f%% of everything hit"
                    % (stats["top_objects"][0][0],
                       100 * stats["top1_share"]))
    return ("FAIL" if bad else ("WARN" if warn else "PASS")), bad, warn


def _stand_why(stand):
    if not stand:
        return "no data"
    if stand["stand_h"] is None:
        return "no floor under the camera"
    if not 1.10 <= stand["stand_h"] <= 2.30:
        return "eye is %.2f m over the floor" % stand["stand_h"]
    if stand["floor_spread"] is not None and stand["floor_spread"] >= 1.2:
        return "floor is not flat (%.2f m spread)" % stand["floor_spread"]
    return "only %.2f m of clear air around the eye" % stand["eye_clear"]


# --------------------------------------------------------------------------- #
#  ascii + png rendering of the grid
# --------------------------------------------------------------------------- #
def ascii_map(rows):
    return ["".join(GLYPH.get(h["cls"], "?") for h in row) for row in rows]


def seg_png(rows, path, scale=20):
    """Nearest-neighbour false-colour map, one PNG per shot."""
    ny, nx = len(rows), len(rows[0])
    w, h = nx * scale, ny * scale
    buf = np.zeros((h, w, 4), dtype=np.float32)
    buf[:, :, 3] = 1.0
    for j, row in enumerate(rows):
        for i, cell in enumerate(row):
            c = COLOURS.get(cell["cls"], COLOURS["other"])
            buf[j * scale:(j + 1) * scale, i * scale:(i + 1) * scale, :3] = \
                np.array(c, dtype=np.float32) / 255.0
    # thin grid so the 24x14 sampling is visible
    for j in range(1, ny):
        buf[j * scale - 1:j * scale + 1, :, :3] *= 0.35
    for i in range(1, nx):
        buf[:, i * scale - 1:i * scale + 1, :3] *= 0.35
    img = bpy.data.images.new("qa_seg", width=w, height=h, alpha=True)
    img.pixels = buf[::-1].ravel().tolist()      # bpy images are bottom-up
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return path


# --------------------------------------------------------------------------- #
#  shot loading
# --------------------------------------------------------------------------- #
def load_shots(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    shots = data.get("shots") if isinstance(data, dict) else data
    out = []
    for s in shots or ():
        if "pos" in s and "look" in s:
            out.append(s)
        elif "loc" in s and "look" in s:            # render.py's old table shape
            out.append(dict(s, pos=s["loc"]))
    return out


def markdown(recs):
    """The acceptance table, generated from the measurements, never hand-typed."""
    out = ["| camera | kind | verdict | sky | ground | roof | facade | other "
           "| d_med | nearest hit | why |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in recs:
        b = r["buckets"]
        near = r.get("nearest") or {}
        why = "; ".join(r["bad"] + r["warn"]) or "ok"
        out.append("| `%s` | %s | **%s** | %.0f%% | %.0f%% | %.0f%% | %.0f%% "
                   "| %.0f%% | %.0f m | %s (%s, z %.1f) | %s |"
                   % (r["name"], r.get("kind"), r["verdict"],
                      100 * b["sky"], 100 * r.get("ground_near", b["ground"]),
                      100 * b["roof"], 100 * b["facade"], 100 * b["other"],
                      r["hit_d_med"], near.get("obj") or "-",
                      near.get("mat") or "-", near.get("z") or 0.0, why))
    n = len(recs)
    ok = sum(1 for r in recs if r["verdict"] == "PASS")
    warn = sum(1 for r in recs if r["verdict"] == "WARN")
    out.append("")
    out.append("%d cameras: %d PASS, %d WARN, %d FAIL.  "
               "ground is the 400 m-near figure where the rules use it."
               % (n, ok, warn, n - ok - warn))
    return "\n".join(out) + "\n"


def argv():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def opts():
    out, i = {}, 0
    a = argv()
    while i < len(a):
        k = a[i]
        if k.startswith("--"):
            key = k[2:]
            if i + 1 < len(a) and not a[i + 1].startswith("--"):
                out[key] = a[i + 1]
                i += 2
            else:
                out[key] = True
                i += 1
        else:
            i += 1
    return out


def vec(s):
    return tuple(float(x) for x in str(s).split(","))


# --------------------------------------------------------------------------- #
def main():
    o = opts()
    # `--grid` is the same knob under a name that cannot collide with a render
    # `--res`, so this tool can share a command line with look/contact.py.
    res = [int(x) for x in str(o.get("grid") or o.get("res") or "24x14").split("x")]
    nx, ny = res[0], res[1]
    aspect = 16.0 / 9.0
    if o.get("aspect"):
        aspect = float(o["aspect"])
    scene = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    print("[qa] scene %r  objects %d  depsgraph ready"
          % (scene.name, len(bpy.data.objects)), flush=True)

    shots = []
    if o.get("pos") and o.get("look"):
        spec = dict(name=o.get("name", "adhoc"), kind=o.get("kind", "landmark"),
                    pos=vec(o["pos"]), look=vec(o["look"]),
                    note=o.get("note", ""))
        if o.get("fov"):
            spec["fov"] = float(o["fov"])
        if o.get("lens"):
            spec["lens"] = float(o["lens"])
        shots = [spec]
    else:
        path = o.get("shots", DEFAULT_SHOTS)
        if not os.path.exists(path):
            print("[qa] no shots file at %s" % path)
            return
        shots = load_shots(path)
        if o.get("names"):
            want = [n.strip() for n in str(o["names"]).split(",")]
            shots = [s for s in shots if s.get("name") in want]
        elif not o.get("all"):
            shots = shots[:1]
    print("[qa] %d shot(s), grid %dx%d" % (len(shots), nx, ny), flush=True)

    segdir = o.get("seg")
    if segdir and segdir is not True:
        os.makedirs(segdir, exist_ok=True)
    ascii_on = bool(o.get("ascii"))
    raw = bool(o.get("raw"))

    out = []
    for s in shots:
        name = s.get("name", "?")
        pos = tuple(float(v) for v in s["pos"])
        spec = dict(s, pos=pos)
        rows = sample(scene, dg, pos, spec, nx, ny, aspect)
        st = summarise(rows)
        solid = probe_solid(scene, dg, pos)
        stand = los = None
        if s.get("kind") == "eye" or o.get("stand"):
            stand = probe_stand(scene, dg, pos,
                                eye_h=float(o.get("eye", 1.72)))
            los = probe_los(scene, dg, pos, spec["look"],
                            eye_h=float(o.get("eye", 1.72)))
        v, bad, warn = verdict(spec, st, solid, stand, los)
        rec = dict(name=name, kind=s.get("kind"), pos=[round(p, 2) for p in pos],
                   look=[round(float(p), 2) for p in s["look"]],
                   lens=s.get("lens"), fov=s.get("fov"),
                   verdict=v, bad=bad, warn=warn,
                   buckets=st["buckets"], detail=st["detail"],
                   ground_near=st["ground_near"],
                   near3=st["near3"], hit_d_med=st["hit_d_med"],
                   hit_d_min=st["hit_d_min"], hit_z_med=st["hit_z_med"],
                   objects=st["objects"], top_objects=st["top_objects"],
                   top1_share=st["top1_share"], nearest=st["nearest"],
                   solid=solid, stand=stand, los=los)
        if raw:
            rec["materials"] = st["materials"]
        out.append(rec)
        if ascii_on:
            print("\n== %-14s %-8s %s" % (name, s.get("kind"), v), flush=True)
            for line in ascii_map(rows):
                print("   " + line, flush=True)
        print("[qa] %-14s %-4s  sky %4.0f%%  grd %4.0f%%(near %3.0f%%)  roof "
              "%4.0f%%  fac %4.0f%%  oth %4.0f%%  d_med %5.1f  near3 %3.0f%%%s"
              % (name, v, 100 * st["buckets"]["sky"], 100 * st["buckets"]["ground"],
                 100 * st["ground_near"],
                 100 * st["buckets"]["roof"], 100 * st["buckets"]["facade"],
                 100 * st["buckets"]["other"], st["hit_d_med"],
                 100 * st["near3"],
                 ("  ceiling %.1f" % solid["ceiling"]) if solid["ceiling"] else ""),
              flush=True)
        for b in bad:
            print("       FAIL: " + b, flush=True)
        for b in warn:
            print("       warn: " + b, flush=True)
        if st["nearest"]:
            print("       nearest: %.2f m  %s  [%s]  at z %.2f"
                  % (st["nearest"]["d"], st["nearest"]["obj"] or "?",
                     st["nearest"]["mat"] or "?", st["nearest"]["z"]), flush=True)
        if st["top_objects"]:
            print("       fills: " + ", ".join("%s %.0f%%" % (o, 100 * s_)
                                               for o, s_ in st["top_objects"]),
                  flush=True)
        if raw:
            print("       mats: " + ", ".join("%s=%d" % kv for kv in
                                             list(st["materials"].items())[:10]),
                  flush=True)
        if segdir and segdir is not True:
            seg_png(rows, os.path.join(segdir, "QA_%s.png" % name))

    dst = o.get("out", DEFAULT_OUT)
    try:
        with open(dst, "w", encoding="utf-8") as fh:
            json.dump(dict(grid="%dx%d" % (nx, ny), shots=out), fh, indent=1)
        print("[qa] wrote %s" % dst, flush=True)
    except OSError as exc:
        print("[qa] could not write %s: %s" % (dst, exc), flush=True)
    md = o.get("md")
    if md and md is not True:
        try:
            with open(md, "w", encoding="utf-8") as fh:
                fh.write(markdown(out))
            print("[qa] wrote %s" % md, flush=True)
        except OSError as exc:
            print("[qa] could not write %s: %s" % (md, exc), flush=True)
    n_ok = sum(1 for r in out if r["verdict"] == "PASS")
    n_warn = sum(1 for r in out if r["verdict"] == "WARN")
    print("[qa] %d PASS / %d WARN / %d FAIL"
          % (n_ok, n_warn, len(out) - n_ok - n_warn), flush=True)


if __name__ == "__main__":
    main()
