"""Glue layer between capital.py and the high-detail landmark modules.

Nothing in the hd_* modules is edited here: this file only
  * completes the material palette the hd modules expect (capital.py's MAT dict
    is missing a handful of keys such as ``slate`` or ``stone_pale``),
  * places their output with ``T(x, y, z) @ Rz(rot)`` so the modules keep their
    own local frames (origin = footprint centre, +Y = front, z = 0 = ground),
  * reports object / triangle counts,
  * adds the one connector hd_castle cannot know about: the approach ramp from
    the end of its causeway down the castle rock.

Conventions used here (identical to capital.py):
    world +X = east, +Y = north, +Z = up
    a module's local +Y is its front (gate / west front / shopfront / door)
"""

import math
import os
import sys

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
BL = os.path.dirname(HERE)
for _p in (BL, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import medkit as K                                   # noqa: E402
import hd_common as H                                # noqa: E402

# how many distinct wall/roof palettes a house can draw from.  Kept here so
# capital.py can hash a placement into the same range (see build_city_hd).
NVAR = 8

# The hd modules are being edited by several people at once, so a module can be
# saved half-written at any moment.  Import them one by one and keep going: a
# missing landmark is a report line, not a dead 10-minute city build.
FAILED = []
_MODS = {}


def _imp(name):
    try:
        _MODS[name] = __import__(name)
    except Exception as exc:                     # noqa: BLE001 - reported
        _MODS[name] = None
        msg = "%s: %s" % (type(exc).__name__, exc)
        FAILED.append((name, msg))
        print("[hd-glue] cannot import %-14s %s" % (name, msg), flush=True)
    return _MODS[name]


hd_castle = _imp("hd_castle")
hd_cathedral = _imp("hd_cathedral")
hd_gate = _imp("hd_gate")
hd_market = _imp("hd_market")
hd_houses = _imp("hd_houses")

# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------
_PRODUCE_COLS = ("#cbb350", "#7d9a3c", "#b4553c", "#d9c9a6", "#7b4a2e", "#a5527a")

# hd_market is the only module that needs the prefixed private helpers, so reuse
# its own water-jet shader instead of re-inventing it.
_jet = None


def _water_jet():
    global _jet
    if _jet is None:
        _jet = hd_market._jet_mat()
    return _jet


def hd_materials(MAT):
    """Return a copy of *MAT* with every key the hd modules look up.

    Where capital.py already owns a material for a concept (paving, plaster,
    lamps, glow) that material is reused so the HD landmarks sit in the same
    palette as the rest of the city instead of importing their own greys.

    This is the palette handed to hd_gate, the only module without a material
    factory of its own (hd_market/hd_castle/hd_houses build theirs, hd_cathedral
    has ``mats()`` and they are used through ``*_mats`` below).
    """
    m = dict(MAT)
    have = m.setdefault
    have("plaster_warm", MAT.get("plaster2") or MAT["plaster"])
    have("plaster2", MAT["plaster2"])
    have("ground", MAT["flag"])
    have("ground_worn", MAT["cobble"])
    have("lamp", MAT["glow_warm"])
    have("glow", MAT["glow"])
    # warm slate, not the module's blue-grey: the gate plates and pinnacle roofs
    # read as a blue stripe across a beige west front otherwise
    have("slate", K.mat_tile("hd_slate", "#4a463c", "#2e2b25", "#5f5a4d"))
    have("tile_blue_lt", K.mat_tile("hd_tile_blue_lt", "#5a6a78", "#414d59", "#778897"))
    have("tile_dark", K.mat_tile("hd_tile_dark", "#7a3325", "#54231a", "#94432f"))
    have("stone_dark", K.mat_stone("hd_stone_dark", "#5d564a", "#332f28", "#78705f", 2.8))
    have("stone_pale", K.mat_stone("hd_stone_pale", "#a89e8a", "#726a5b", "#c3b8a1", 2.2))
    have("iron_dark", K.mat_metal("hd_iron_dark", "#26252a", 0.55))
    have("iron_warm", K.mat_metal("hd_iron_warm", "#463c33", 0.40))
    have("lead", K.mat_metal("hd_lead", "#6a6d72", 0.52))
    have("bronze", K.mat_metal("hd_bronze", "#5c7a5e", 0.40))
    have("void", K.mat_metal("hd_void", "#14151a", 0.90))
    have("wood_light", K.mat_wood("hd_wood_light", "#7a5a3c", "#9a7450", 0.80, 14.0))
    have("wood_pale", K.mat_wood("hd_wood_pale", "#9a8461", "#b8a07a", 0.82, 14.0))
    have("canvas", K.mat_cloth("hd_canvas", "#cbbd9e", 0.90))
    have("canvas_red", K.mat_cloth("hd_canvas_red", "#8d3a30", 0.90))
    have("banner_green", K.mat_cloth("hd_banner_green", "#2f5a3a", 0.88))
    have("water_jet", _water_jet())
    if "produce" not in m or not isinstance(m.get("produce"), list):
        m["produce"] = [K.mat_cloth("hd_produce_%d" % i, c, 0.95)
                        for i, c in enumerate(_PRODUCE_COLS)]
    return m


# --------------------------------------------------------------------------
# placement
# --------------------------------------------------------------------------
def _T(x, y, z, rot, scale=1.0):
    m = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, "Z")
    if scale != 1.0:
        m = m @ Matrix.Scale(scale, 4)
    return m


def place(parts, x, y, z=0.0, rot=0.0, scale=1.0):
    """Bake T(x,y,z)@Rz(rot)@S(scale) into *parts* (unit transforms out)."""
    parts = [p for p in parts if getattr(p, "type", None) == "MESH"]
    H.apply(parts, _T(x, y, z, rot, scale))
    return parts


def stats(parts):
    """(objects, faces, triangles) for a flat list of objects."""
    objs = faces = tris = 0
    for p in parts:
        me = getattr(p, "data", None)
        if me is None or not hasattr(me, "polygons"):
            continue
        objs += 1
        faces += len(me.polygons)
        tris += H.tri_count([p])
    return objs, faces, tris


def note(name, parts):
    if not parts:                       # guard() already printed the reason
        return parts
    o, f, t = stats(parts)
    print("[hd] %-14s objects=%-5d faces=%-7d tris=%d" % (name, o, f, t), flush=True)
    return parts


# --------------------------------------------------------------------------
# per-module palettes
# --------------------------------------------------------------------------
# The hd modules do not only index MAT["key"] with literal strings: they also
# reach for keys through locals (hd_market's W["interior"], W["plaster_warm"]),
# so a kernel palette can never be complete.  Each module therefore ships its own
# material set; those are layered over the capital palette so a landmark looks
# exactly like its own preview and still falls back on capital materials for
# anything the module does not know about.
_PALS = {}


def _own_mats(mod, factory, fallback="MAT"):
    """A module's own material dict (module-level MAT or its factory)."""
    m = getattr(mod, fallback, None)
    if isinstance(m, dict) and m:
        return m
    f = getattr(mod, factory, None)
    if callable(f):
        try:
            return f()
        except Exception:
            pass
    return {}


def _pal(key, MAT, base):
    p = _PALS.get(key)
    if p is None:
        p = dict(MAT)
        if base:
            p.update(base)
        _PALS[key] = p
    return p


def castle_mats(MAT):
    return _pal("castle", MAT, _own_mats(hd_castle, "make_mats"))


def cathedral_mats(MAT):
    return _pal("cathedral", MAT, _own_mats(hd_cathedral, "mats"))


def market_mats(MAT):
    return _pal("market", MAT, _own_mats(hd_market, "make_materials"))


def house_mats(MAT, variant=0, back=False):
    """hd_houses' palette, re-coloured for a real medieval town.

    The module ships a saturated terracotta and a blue-grey slate, and takes the
    slate 35% of the time: two roofs in three come back bright red or bright
    blue and the aerial reads as toy bricks.  Terracotta dominates a real town,
    slate is the minority, and the vivid blue tiles stay with the privileged
    buildings (they carry their own palettes, so they keep them).  Walls go the
    same way: shop frontage is cream plaster over timber, the back rows behind
    it are grey-tan render, and nothing stays paper white.
    """
    key = ("houses", int(variant) % NVAR, bool(back))
    hit = _PALS.get(key)
    if hit is not None:
        return hit
    base = _pal("houses", MAT, _own_mats(hd_houses, "make_mats"))
    v = int(variant) % NVAR
    # Walls: the first pass gave five creams whose values sat inside 0.02 of
    # each other, so at any distance the town was one colour -- a chalk pit,
    # not a town.  A real town is limewash, ochre, clay pink and faded sage in
    # the same street, each a different *hue*, with a value range wide enough
    # to survive AgX and a 33 deg sun.
    terra = (("#8c5a43", "#65402f", "#a3715a"),
             ("#7c4c39", "#573527", "#94614a"),
             ("#96634a", "#6a4634", "#ad7a60"),
             ("#6f4a3a", "#503326", "#8b6450"),
             ("#a0522d", "#733a1f", "#bd6b41"),
             ("#7d7166", "#57504a", "#96897c"),
             ("#5f6470", "#434850", "#787e8a"),
             ("#875440", "#5f3a2c", "#a06b53"))[v]
    slate = (("#6a6f73", "#4c5053", "#82878b"),
             ("#5c6064", "#414548", "#74797d"),
             ("#767b7f", "#565a5e", "#8f9498"))[v % 3]
    pal = dict(base)
    pal["tile"] = K.mat_tile("hd_tile_terra%d" % v, *terra)
    pal["slate"] = K.mat_tile("hd_tile_slate%d" % v, *slate)
    if back:
        pal["plaster"] = K.mat_plaster("hd_plaster_back%d" % (v % 3),
                                       ("#b3a894", "#a89b86", "#bcb09b")[v % 3],
                                       "#8d8371")
        pal["plaster2"] = K.mat_plaster("hd_plaster_back%db" % (v % 3),
                                        ("#a79c88", "#9c9079", "#b0a48f")[v % 3],
                                        "#847a69")
    else:
        pal["plaster"] = K.mat_plaster("hd_plaster_c%d" % v,
                                       # 0.90 sRGB limewash clipped to pure white
                                       # in every sunlit frame, which is what
                                       # made the town read as folded paper; a
                                       # real limewash sits near 0.80 and keeps
                                       # its shading and its noise
                                       ("#cfc6b2",          # limewash, warm white
                                        "#c6b38c",          # cream ochre
                                        "#b89c76",          # ochre
                                        "#be9b8c",          # clay pink
                                        "#aa9f8c",          # grey-tan render
                                        "#a8a795",          # faded sage -> warm grey
                                        "#c3b497",          # sand
                                        "#b5927b")[v],      # salmon
                                       ("#a3977f", "#9a8764", "#8d7451", "#926f61",
                                        "#807764", "#757c66", "#96876d",
                                        "#876954")[v])
        pal["plaster2"] = K.mat_plaster("hd_plaster_c%db" % v,
                                        ("#d8cdb6", "#cdb88e", "#bd9e74",
                                         "#c49c8c", "#ada28c", "#a8a795",
                                         "#c9b898", "#b9927a")[v],
                                        ("#a89d86", "#9c8763", "#8e7350",
                                         "#957264", "#807763", "#747c64",
                                         "#998868", "#887058")[v])
    _PALS[key] = pal
    return pal


# --------------------------------------------------------------------------
# landmarks
# --------------------------------------------------------------------------
# A module that is mid-edit (or carries a bug) must not cost the whole city
# build: each landmark is guarded, and a failure is recorded so the run can
# still be rendered and reported instead of dying at minute eight.
_FAIL_N = {}


def guard(name, fn):
    before = set(bpy.data.objects)
    try:
        return fn()
    except Exception as exc:                    # noqa: BLE001 - reported, not hidden
        # a landmark that dies half-built leaves its first few hundred parts in
        # the scene and hands back an empty list, so nothing ever collects them.
        # Measured on the 9 500-house city: 280 orphans per block, and the cost
        # of every later bpy.data.objects.new() grows with that count.
        _drop([o for o in bpy.data.objects if o not in before])
        msg = "%s: %s" % (type(exc).__name__, exc)
        FAILED.append((name, msg))
        n = _FAIL_N.get(name, 0) + 1
        _FAIL_N[name] = n
        if n <= 2:                              # a broken house must not spam 300 lines
            print("[hd-glue] FAILED %-12s %s" % (name, msg), flush=True)
        elif n == 3:
            print("[hd-glue] FAILED %-12s (further failures of this landmark muted)"
                  % name, flush=True)
        return []


def gatehouse(MAT, rng, x, y, rot=0.0, z=0.0, name="gate_south", scale=1.0):
    """hd_gate front (+Y) = outside the city."""
    if hd_gate is None:
        return []
    return note(name, place(guard(name, lambda: hd_gate.build_gatehouse(MAT, rng)),
                            x, y, z, rot, scale))


def castle(MAT, rng, x, y, rot=0.0, z=0.0, scale=1.0):
    """hd_castle front (+Y) = main gate, city-facing."""
    if hd_castle is None:
        return []
    return note("castle", place(guard("castle", lambda: hd_castle.build(castle_mats(MAT), rng)),
                                x, y, z, rot, scale))


def cathedral(MAT, rng, x, y, rot=0.0, z=0.0):
    """hd_cathedral front (+Y) = west front (twin towers)."""
    if hd_cathedral is None:
        return []
    return note("cathedral",
                place(guard("cathedral",
                            lambda: hd_cathedral.build(cathedral_mats(MAT), rng)), x, y, z, rot))


def market_hall(MAT, rng, x, y, rot=0.0, z=0.0):
    """hd_market front is -Y."""
    if hd_market is None:
        return []
    return note("market_hall",
                place(guard("market_hall",
                            lambda: hd_market.market_hall(market_mats(MAT), rng)), x, y, z, rot))


def guild_hall(MAT, rng, x, y, rot=0.0, z=0.0):
    if hd_market is None:
        return []
    return note("guild_hall",
                place(guard("guild_hall",
                            lambda: hd_market.guild_hall(market_mats(MAT), rng)), x, y, z, rot))


def fountain(MAT, rng, x, y, rot=0.0, z=0.0):
    if hd_market is None:
        return []
    return note("fountain",
                place(guard("fountain",
                            lambda: hd_market.fountain(market_mats(MAT), rng)), x, y, z, rot))


_HOUSE_KINDS = ("timber", "stone", "shop", "timber", "inn", "craft",
                "stone", "timber", "shop", "warehouse", "manor", "timber")


class HousePlanner(object):
    """Decides kind / frontage / size for consecutive houses.

    Kept in the glue so capital.py only asks for `next()`; frontages alternate
    (eaves / gable / eaves ...) and the kind rotates through the catalogue with
    a little rng jitter, which is what makes a row read as a real street.
    """

    def __init__(self, rng, kinds=_HOUSE_KINDS):
        self.rng = rng
        self.kinds = kinds
        self.i = 0

    def next(self, w, d, floors):
        rng = self.rng
        i = self.i
        self.i += 1
        if i % 5 == 4:
            kind = rng.choice(("inn", "manor", "tower"))
        else:
            kind = self.kinds[i % len(self.kinds)]
        frontage = "gable" if i % 2 else "eaves"
        k = self.kinds.index(kind) if kind in self.kinds else 0
        if kind in ("manor", "tower", "warehouse"):
            w = max(w, 8.0)
            d = max(d, 9.0)
            floors = max(floors, 3 if kind == "tower" else 2)
        return dict(kind=kind, frontage=frontage,
                    w=float(w), d=float(d), floors=int(floors))


def house(MAT, rng, x, y, rot, w, d, floors, kind, frontage,
          variant=0, back=False):
    """hd_houses front (+Y) matches capital.py's own house convention."""
    if hd_houses is None:
        return []
    pal = house_mats(MAT, variant, back)
    return place(guard("house",
                       lambda: hd_houses.house(pal, rng, kind=kind, w=w,
                                               d=d, floors=floors, frontage=frontage)),
                 x, y, 0.0, rot)


# --------------------------------------------------------------------------
# functional buildings (hd_shops)
# --------------------------------------------------------------------------
# hd_shops was written while this glue was in use, so it is imported lazily: a
# half-saved module must not take the whole city build down with it.
def _shops():
    global _SHOPS
    if _SHOPS is None:
        import hd_shops as _m
        _SHOPS = _m
    return _SHOPS


_SHOPS = None


def shops_ok():
    try:
        return _shops()
    except Exception:                            # noqa: BLE001
        return None


def shop_footprint(kind):
    """(w, d, h) as the module itself reports it (falls back to hd_layout's copy)."""
    try:
        return _shops().footprint(kind)
    except Exception:                            # noqa: BLE001
        import hd_layout
        return hd_layout.shop_footprint(kind)


_SHOP_MATS = None


def shop_mats(MAT):
    global _SHOP_MATS
    if _SHOP_MATS is None:
        mod = shops_ok()
        _SHOP_MATS = _pal("shops", MAT, _own_mats(mod, "make_materials") if mod else {})
    return _SHOP_MATS


def shop(kind, MAT, rng, x, y, rot=0.0, z=0.0):
    """hd_shops front (+Y) matches capital.py's own house convention."""
    mod = shops_ok()
    if mod is None:
        return house(MAT, rng, x, y, rot, 7.0, 9.0, 2, "shop", "gable")
    return place(guard("shop_" + kind,
                       lambda: mod.build(kind, shop_mats(MAT), rng)), x, y, z, rot)


# --------------------------------------------------------------------------
# fast merge: 262 objects per hd house would put a 3 000-house city at 800 k
# objects, which neither the .blend nor EEVEE's per-frame conversion survives.
# place() has already baked every part into world space, so a plain bmesh append
# per part is enough -- no matrix maths, no bpy.ops, no depsgraph evaluation.
# --------------------------------------------------------------------------
def merge_objects(name, parts):
    import bmesh
    raw = list(parts)
    parts = [p for p in raw if getattr(p, "type", None) == "MESH" and p.data]
    if not parts:
        # still bury the sources: a house can come back as empties only, and
        # leaving those behind costs more than the geometry ever did
        _drop(raw)
        return None
    bm = bmesh.new()
    slots = []
    seen = {}

    def slot_of(mat):
        key = mat.name if mat is not None else ""
        i = seen.get(key)
        if i is None:
            i = len(slots)
            seen[key] = i
            slots.append(mat)
        return i

    for p in parts:
        me = p.data
        mats = me.materials
        if len(mats) == 1:
            gi = slot_of(mats[0])
            for poly in me.polygons:
                poly.material_index = gi
        elif len(mats) > 1:
            loc = [slot_of(m) for m in mats]
            for poly in me.polygons:
                poly.material_index = loc[poly.material_index]
        bm.from_mesh(me)
    new = bpy.data.meshes.new(name)
    bm.to_mesh(new)
    bm.free()
    for m in slots:
        if m is not None:
            new.materials.append(m)
    ob = bpy.data.objects.new(name, new)
    bpy.context.scene.collection.objects.link(ob)
    # the sources are baked in now; drop them so peak memory stays flat.  A single
    # batch_remove matters: removing 5 000 objects one by one is quadratic in
    # bpy.data and cost 2.4 s per house before this.
    _drop(raw)
    return ob


def _drop(parts):
    """Remove every source object of a merge, not just the meshes.

    hd_houses/hd_shops hand back a mix of meshes and empties.  Filtering to
    MESH and then deleting only that filtered list leaks ~20 empties per
    building: measured 280 live objects after a 15-building block, which then
    makes every later bpy.data.objects.new() scan a growing ID list -- block 1
    of 371 took 0.6 s and block 18 took 55 s.  Same 371 blocks, but this is the
    difference between a 20-minute build and a 6-hour one.
    """
    ids = []
    for p in parts:
        try:
            ids.append(p)
            if getattr(p, "type", None) == "MESH" and p.data is not None:
                ids.append(p.data)
        except ReferenceError:                   # already gone: nothing to do
            continue
    if not ids:
        return
    try:
        bpy.data.batch_remove(ids)
    except Exception as exc:                     # noqa: BLE001 - report loudly
        print("[hd-glue] batch_remove failed: %r" % (exc,), flush=True)
        for p in list(parts):
            try:
                if getattr(p, "type", None) is not None:
                    bpy.data.objects.remove(p, do_unlink=True)
            except ReferenceError:
                continue


# --------------------------------------------------------------------------
# castle approach: a SOLID ramp, so nothing hangs in the air over the crag
# --------------------------------------------------------------------------
def wedge_ramp(MAT, name, x, y_top, z_top, y_bot, z_bot, w=11.0, batter=1.4,
               mat=None, ribs=3):
    """Masonry ramp from (y_top, z_top) down to (y_bot, z_bot).

    Built as one wedge mesh whose flanks reach the ground (plus a bury depth),
    because the castle rock is much steeper than the walkable grade: a thin slab
    would float .  Side walls are battered and get vertical ribs so the big
    triangular flank reads as a retaining wall, not a blank triangle.
    """
    mat = mat or MAT["stone_warm"]
    hw = w * 0.5
    z_base = z_bot - 1.2
    hb = hw + batter
    verts = [
        (-hw, y_top, z_top), (hw, y_top, z_top),          # 0 1 top, high end
        (-hw, y_bot, z_bot), (hw, y_bot, z_bot),          # 2 3 top, low end
        (-hb, y_top, z_base), (hb, y_top, z_base),        # 4 5 base, high end
        (-hb, y_bot, z_base), (hb, y_bot, z_base),        # 6 7 base, low end
    ]
    faces = [(0, 1, 3, 2),          # deck
             (0, 2, 6, 4),          # left flank
             (1, 5, 7, 3),          # right flank
             (2, 3, 7, 6),          # low end
             (0, 4, 5, 1)]          # high end (buried in the causeway)
    parts = [K.mesh_obj(name, [(x + v[0], v[1], v[2]) for v in verts], faces)]
    K.assign(parts[0], mat)

    dy = y_top - y_bot
    dz = z_top - z_bot
    pitch = math.atan2(dz, dy)                       # +Y end lifted
    length = math.hypot(dy, dz)
    cy = 0.5 * (y_top + y_bot)
    # parapets ride the deck
    for s, tag in ((1.0, "l"), (-1.0, "r")):
        parts.append(K.box("%s_par%s" % (name, tag),
                           K.T_at(x + s * (hw - 0.42), cy,
                                  (z_top + z_bot) * 0.5 + 0.42, rx=pitch),
                           (0.84, length + 1.2, 1.0), mat, bev=0.02))
    # battered ribs: they stop at the deck height of their station
    for i in range(ribs):
        t = (i + 1.0) / (ribs + 1.0)
        yy = y_top - dy * t
        zz = z_top - dz * t
        for s in (1.0, -1.0):
            parts.append(K.box("%s_rib%d%s" % (name, i, "l" if s > 0 else "r"),
                               K.T_at(x + s * (hb - 0.15), yy, (zz + z_base) * 0.5),
                               (0.9, 1.5, zz - z_base), mat, bev=0.02))
    return parts


# --------------------------------------------------------------------------
# curtain wall with a real opening for the hd gatehouse
# --------------------------------------------------------------------------
def wall_arc(name, r, h, t, mat, a0, a1, z=0.0, cx=0.0, cy=0.0, seg_deg=1.1,
             merlon=True, merlon_h=1.25, merlon_step=2.6):
    """Same construction as capital.wall_ring, but only the arc a0..a1.

    Used to leave a gate-sized hole in the outer curtain: the hd gatehouse is a
    solid wall block, so the curtain has to butt into its flanks instead of
    running through the passage.
    """
    n = max(8, int(abs(a1 - a0) / math.radians(seg_deg)))
    ri, ro = r - t * 0.5, r + t * 0.5
    verts, faces = [], []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / float(n)
        ca, sa = math.cos(a), math.sin(a)
        verts += [(cx + ri * ca, cy + ri * sa, z), (cx + ro * ca, cy + ro * sa, z),
                  (cx + ri * ca, cy + ri * sa, z + h), (cx + ro * ca, cy + ro * sa, z + h)]
    for i in range(n):
        b, c = 4 * i, 4 * (i + 1)
        faces += [(b + 0, b + 1, c + 1, c + 0),
                  (b + 2, c + 2, c + 3, b + 3),
                  (b + 1, b + 3, c + 3, c + 1),
                  (b + 0, c + 0, c + 2, b + 2)]
    last = 4 * n
    faces += [(0, 2, 3, 1), (last, last + 1, last + 3, last + 2)]
    ob = K.mesh_obj(name, verts, faces)
    K.assign(ob, mat)
    parts = [ob]
    if merlon:
        steps = max(2, int(abs(a1 - a0) * r / merlon_step))
        for i in range(steps):
            if i % 2:
                continue
            a = a0 + (a1 - a0) * (i + 0.5) / steps
            parts.append(K.box("%s_m%d" % (name, i),
                               K.T_at(cx + r * math.cos(a), cy + r * math.sin(a),
                                      z + h + merlon_h * 0.5, rz=a),
                               (t * 1.05, 1.35, merlon_h), mat, bev=0.03))
    return parts


# --------------------------------------------------------------------------
# self test: build every landmark, print extents, keep nothing
# --------------------------------------------------------------------------
def wall_seg(name, p0, p1, h, t, mat, z=0.0, merlon=True, merlon_h=1.25,
             merlon_step=2.6):
    """Straight run of curtain wall between two points.

    The far enceinte is a 16..24 sided polygon, so wall_arc (which assumes a
    constant radius) cannot build it; same construction, straight.
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    if L < 2.5:
        return []
    a = math.atan2(dy, dx)
    parts = [K.box(name, K.T_at(p0[0] + dx * 0.5, p0[1] + dy * 0.5, z + h * 0.5, rz=a),
                   (L, t, h), mat, bev=0.02)]
    if merlon:
        n = max(2, int(L / merlon_step))
        for i in range(n):
            if i % 2:
                continue
            u = (i + 0.5) / n
            parts.append(K.box("%s_m%d" % (name, i),
                               K.T_at(p0[0] + dx * u, p0[1] + dy * u,
                                      z + h + merlon_h * 0.5, rz=a),
                               (1.35, t * 1.05, merlon_h), mat, bev=0.03))
    return parts


def well(name, T, MAT):
    """Village well: stone drum, water, two posts and a beam for the bucket."""
    stone = MAT.get("stone_warm") or MAT.get("stone")
    wood = MAT.get("wood_dark") or MAT.get("wood")
    parts = [K.cyl(name + "_ring", T @ (Matrix.Translation((0, 0, 0.55))),
                   1.30, 1.10, stone, seg=16),
             K.cyl(name + "_water", T @ (Matrix.Translation((0, 0, 1.03))),
                   1.02, 0.05, MAT.get("water"), seg=16)]
    for sx in (-1, 1):
        parts.append(K.box("%s_post%d" % (name, sx),
                           T @ (Matrix.Translation((sx * 1.12, 0, 1.55))),
                           (0.18, 0.18, 2.1), wood, bev=0.02))
    parts.append(K.box(name + "_beam", T @ (Matrix.Translation((0, 0, 2.56))),
                       (2.55, 0.20, 0.20), wood, bev=0.02))
    return parts


def street_props(MAT, placements, rng, cap=2600, streets=None):
    """Lamps, barrels, crates, stalls along the streets, spaced by street class.

    Density is measured along the street polyline, not counted off buildings:
    a main street gets a piece every 12-18 m, a secondary every 20-25 m, and an
    alley only barrels and crates at 40 m+ -- a lamp post in a 4 m lane is a
    barricade, not furniture.  All parts are hd_common's own.
    """
    iron = MAT.get("iron")
    glow = MAT.get("glow") or MAT.get("glow_warm")
    wood = MAT.get("wood")
    wood_dark = MAT.get("wood_dark") or wood
    cloth = MAT.get("cloth_a") or MAT.get("banner_red")
    TIER = {"main": (12.0, 18.0, ("lantern", "stall", "crate", "barrel")),
            "secondary": (20.0, 25.0, ("lantern", "barrel", "crate")),
            "alley": (40.0, 56.0, ("barrel", "crate"))}
    out = []
    if not streets:
        return out
    made = 0
    for si, s in enumerate(streets):
        if made >= cap:
            break
        try:
            ax, ay = float(s["a"][0]), float(s["a"][1])
            bx, by = float(s["b"][0]), float(s["b"][1])
            w = float(s.get("w") or 7.0)
            kind = s.get("kind") or ("main" if w > 9.0 else
                                     "secondary" if w > 5.0 else "alley")
            lo, hi, kinds = TIER.get(kind, TIER["alley"])
            L = math.hypot(bx - ax, by - ay)
            if L < 8.0:
                continue
            ux, uy = (bx - ax) / L, (by - ay) / L
            px, py = -uy, ux
            t = rng.uniform(1.0, lo)
            i = 0
            while t < L - 1.5 and made < cap:
                side = 1.0 if (i + si) % 2 == 0 else -1.0
                # hug the far side of the kerb so the carriageway stays clear
                off = w * 0.5 + 1.25 + rng.uniform(0.0, 0.7)
                x = ax + ux * t + px * off * side
                y = ay + uy * t + py * off * side
                yaw = math.atan2(ux, uy)
                key = "%d_%d" % (si, i)
                kk = kinds[i % len(kinds)]
                if kk == "lantern":
                    out += H.lantern_post("lp" + key, _T(x, y, 0.0, yaw),
                                          3.4 + rng.uniform(0.0, 0.5), iron, glow)
                elif kk == "stall":
                    out += H.market_stall("st" + key, _T(x, y, 0.0, yaw),
                                          2.6, 1.8, cloth, wood)
                elif kk == "barrel":
                    out += H.barrel("br" + key, _T(x, y, 0.0, yaw), 0.34, 0.88,
                                    wood, iron)
                    out += H.barrel("br%sb" % key, _T(x - 0.62, y + 0.24, 0.0, yaw),
                                    0.30, 0.80, wood, iron)
                else:
                    out += H.crate("cr" + key, _T(x, y, 0.0, yaw), 0.66, wood_dark)
                made += 1
                i += 1
                t += rng.uniform(lo, hi)
        except Exception:
            continue
    return out


def selftest(MAT, seed=7):
    import random
    rng = random.Random(seed)
    M = hd_materials(MAT)
    out = {}
    for label, fn in (("castle", lambda: hd_castle.build(M, rng)),
                      ("cathedral", lambda: hd_cathedral.build(M, rng)),
                      ("gatehouse", lambda: hd_gate.build_gatehouse(M, rng)),
                      ("market_hall", lambda: hd_market.market_hall(M, rng)),
                      ("guild_hall", lambda: hd_market.guild_hall(M, rng)),
                      ("fountain", lambda: hd_market.fountain(M, rng)),
                      ("house_timber", lambda: hd_houses.house(M, rng)),
                      ("house_gable", lambda: hd_houses.house(
                          M, rng, kind="shop", frontage="gable", w=8, d=9.5,
                          floors=3))):
        parts = [p for p in fn() if p is not None]
        bb = H.bbox(parts)
        o, f, t = stats(parts)
        print("[hd-probe] %-13s objects=%-5d faces=%-7d tris=%-7d "
              "x[%7.2f %7.2f] y[%7.2f %7.2f] z[%7.2f %7.2f]"
              % (label, o, f, t, bb[0][0], bb[1][0], bb[0][1], bb[1][1],
                 bb[0][2], bb[1][2]), flush=True)
        out[label] = (parts, bb)
    return out

