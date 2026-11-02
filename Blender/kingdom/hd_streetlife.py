"""hd_streetlife.py -- what people leave in the streets of the capital.

The city has 9 500 houses and nothing between them.  At the 2.5D camera (52 deg
pitch, 34 m back, 30 deg vertical FOV) the visible ground is only ~23 m deep by
~32 m wide, so the furniture has to be dense *locally*: one barrel every 30 m
across a 9 km town is the same as no barrel at all.

This module therefore builds, per street and per yard:

    * a band of props against each facade, never crossing the centre line
      (a street keeps >= 55 % of its width walkable),
    * litters of the things a real town leaves in a lane: barrels, crates, sacks,
      hay, firewood, handcarts, wagons, pallets, buckets, planks, broken wheels,
      ladders, troughs, hitching posts, benches, wells, wall lanterns, hanging
      shop signs and laundry lines across the lane,
    * yards behind the frontage rows: sheds, chicken coops, fenced vegetable
      gardens, haystacks, pig pens, laundry racks, compost, water butts, gates,
    * market squares: rows of stalls with striped awnings, produce, carts.

Everything is emitted as THREE objects (props_street / props_yard / props_market),
each with a handful of material slots.  Geometry is built straight into numpy
arrays and handed to `Mesh.foreach_set`, so a 25 000-prop city costs three
objects instead of 25 000 -- the 9 500 houses already make bpy.data expensive
enough (every `objects.new()` scans the whole ID list).

Materials are Principled + procedural nodes on TexCoord.Object, so the grain is
in metres and never repeats across props.  There are no image files.

Public API
----------
    build(MAT, rng, units, streets, blocks=None, density=1.0) -> list of objects
"""
import math
import random

import bpy

try:
    import numpy as np
except Exception:                                        # pragma: no cover
    np = None

__all__ = ("build", "MATS", "CATS", "stats", "build_prop_sheet")

TAU = math.pi * 2.0
CATS = ("street", "yard", "market")


def _log(*a):
    print("[streetlife]", *a, flush=True)


# ===========================================================================
# materials -- procedural, Object-space, no textures
# ===========================================================================
def _srgb(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


def _mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return m, nt


def _node(nt, kind, name, loc=(0, 0)):
    n = nt.nodes.new(kind)
    n.name = name
    n.label = name
    n.location = loc
    return n


def _co(nt, loc=(-1500, 0)):
    tc = _node(nt, "ShaderNodeTexCoord", "co", loc)
    return tc.outputs["Object"]


def _noise(nt, vec, scale, name, detail=4.0, rough=0.55, loc=(-1100, 0)):
    n = _node(nt, "ShaderNodeTexNoise", name, loc)
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    nt.links.new(vec, n.inputs["Vector"])
    return n


def _wave(nt, vec, scale, name, distortion=0.0, loc=(-1100, 0)):
    n = _node(nt, "ShaderNodeTexWave", name, loc)
    n.wave_type = "BANDS"
    n.bands_direction = "X"
    n.inputs["Scale"].default_value = scale
    n.inputs["Distortion"].default_value = distortion
    n.inputs["Detail"].default_value = 2.0
    nt.links.new(vec, n.inputs["Vector"])
    return n


def _voronoi(nt, vec, scale, name, feature="F1", loc=(-1100, 0)):
    v = _node(nt, "ShaderNodeTexVoronoi", name, loc)
    v.feature = feature
    v.inputs["Scale"].default_value = scale
    v.inputs["Randomness"].default_value = 1.0
    nt.links.new(vec, v.inputs["Vector"])
    return v


def _ramp(nt, src, stops, name, loc=(-900, 0), interp="LINEAR"):
    r = _node(nt, "ShaderNodeValToRGB", name, loc)
    r.color_ramp.interpolation = interp
    els = r.color_ramp.elements
    while len(els) > len(stops):
        els.remove(els[-1])
    while len(els) < len(stops):
        els.new(0.5)
    for el, (pos, col) in zip(els, stops):
        el.position = pos
        el.color = col if isinstance(col, tuple) else _srgb(col)
    nt.links.new(src, r.inputs["Fac"])
    return r


def _mixc(nt, a, b, fac, name, blend="MIX", loc=(-600, 0)):
    m = _node(nt, "ShaderNodeMix", name, loc)
    m.data_type = "RGBA"
    m.blend_type = blend
    m.clamp_factor = True
    cols = [s for s in m.inputs if s.type == "RGBA"]
    nt.links.new(a, cols[0])
    nt.links.new(b, cols[1])
    if fac is not None:
        f = next(s for s in m.inputs if s.name == "Factor" and s.type == "VALUE")
        if isinstance(fac, (int, float)):
            f.default_value = float(fac)
        else:
            nt.links.new(fac, f)
    return next(s for s in m.outputs if s.type == "RGBA")


def _math(nt, op, a, b=None, name="m", clamp=False, loc=(-600, -350)):
    m = _node(nt, "ShaderNodeMath", name, loc)
    m.operation = op
    m.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            m.inputs[i].default_value = float(v)
        else:
            nt.links.new(v, m.inputs[i])
    return m.outputs[0]


def _bw(nt, src, name="bw", loc=(-900, -350)):
    n = _node(nt, "ShaderNodeRGBToBW", name, loc)
    nt.links.new(src, n.inputs["Color"])
    return n.outputs[0]


def _bump(nt, h, strength, dist, loc=(-300, -400)):
    b = _node(nt, "ShaderNodeBump", "bump", loc)
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = dist
    nt.links.new(h, b.inputs["Height"])
    return b.outputs["Normal"]


def _finish(nt, color, rough=0.85, spec=0.3, bump=None, metal=0.0, emit=None,
            loc=(0, 0)):
    bsdf = _node(nt, "ShaderNodeBsdfPrincipled", "bsdf", loc)
    out = _node(nt, "ShaderNodeOutputMaterial", "out", (loc[0] + 340, loc[1]))
    nt.links.new(color, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metal
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = spec
    if bump is not None:
        nt.links.new(bump, bsdf.inputs["Normal"])
    if emit is not None:
        col, strength = emit
        for key in ("Emission Color",):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = col
        bsdf.inputs["Emission Strength"].default_value = strength
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return bsdf


def _grain_mat(name, base, light, dark, scale=9.0, rough=0.80, extra_dirt=None,
               spec=0.24):
    """Wood / burlap / straw: one grain noise, one metre-scale weathering noise.

    Detail below ~6 cm is invisible at 2.5 cm per pixel, so the graph spends its
    nodes on value structure at 10-60 cm instead of on micro texture.
    """
    mat, nt = _mat(name)
    co = _co(nt)
    g = _noise(nt, co, scale, "grain", 5.0, 0.62)
    gr = _ramp(nt, g.outputs["Fac"], [(0.28, dark), (0.52, base), (0.80, light)],
               "gcol")
    w = _noise(nt, co, 1.15, "wear", 3.0, 0.60, loc=(-1100, -320))
    wr = _ramp(nt, w.outputs["Fac"], [(0.30, "#8e8168"), (0.58, "#ffffff"),
                                      (0.82, "#b7a98d")], "wcol", loc=(-900, -320))
    col = _mixc(nt, gr.outputs["Color"], wr.outputs["Color"], None, "wear_mix",
                "MULTIPLY", loc=(-600, 0))
    if extra_dirt is not None:
        d = _noise(nt, co, 3.4, "dirt", 4.0, 0.7, loc=(-1100, -640))
        dr = _ramp(nt, d.outputs["Fac"], [(0.45, "#000000"), (0.72, "#6a6a6a")],
                   "dirt_amt", loc=(-900, -640))
        col = _mixc(nt, col, _node(nt, "ShaderNodeRGB", "dirt_c", (-900, -820)
                                   ).outputs[0], dr.outputs["Color"], "dirt_mix",
                    "MIX", loc=(-420, 0))
        nt.nodes["dirt_c"].outputs[0].default_value = _srgb(extra_dirt)
    h = _bw(nt, g.outputs["Fac"], "h", loc=(-600, -640))
    bump = _bump(nt, h, 0.35, 0.006, loc=(-200, -640))
    _finish(nt, col, rough=rough, spec=spec, bump=bump)
    return mat


def _cloth_mat(name, a, b=None, stripe=0.0, rough=0.92):
    mat, nt = _mat(name)
    co = _co(nt)
    if b is not None:
        w = _wave(nt, co, stripe, "stripes")
        wr = _ramp(nt, w.outputs["Fac"], [(0.30, a), (0.52, b), (0.86, a)],
                   "stripe_col", interp="CONSTANT")
        col = wr.outputs["Color"]
    else:
        n = _noise(nt, co, 6.0, "weave", 5.0, 0.6)
        r = _ramp(nt, n.outputs["Fac"], [(0.30, b or a), (0.55, a), (0.85, "#ffffff")],
                  "cloth_col")
        col = _mixc(nt, r.outputs["Color"], r.outputs["Color"], None, "noop",
                    "MULTIPLY", loc=(-600, 0))
    w = _noise(nt, co, 2.2, "folds", 3.0, 0.7, loc=(-1100, -400))
    wr2 = _ramp(nt, w.outputs["Fac"], [(0.32, "#9c9384"), (0.62, "#ffffff")],
                "fold_col", loc=(-900, -400))
    col2 = _mixc(nt, col, wr2.outputs["Color"], None, "fold_mix", "MULTIPLY",
                 loc=(-400, 60))
    bump = _bump(nt, _bw(nt, w.outputs["Fac"], "hb", loc=(-600, -620)), 0.28, 0.01)
    _finish(nt, col2, rough=rough, spec=0.12, bump=bump)
    return mat


def _metal_mat(name, base, rough=0.45, metal=0.85, rust=None):
    mat, nt = _mat(name)
    co = _co(nt)
    n = _noise(nt, co, 7.0, "n", 6.0, 0.68)
    r = _ramp(nt, n.outputs["Fac"], [(0.30, "#151518"), (0.58, base),
                                     (0.86, "#8a8a92")], "mcol")
    col = r.outputs["Color"]
    if rust:
        rust_n = _noise(nt, co, 2.4, "rust", 5.0, 0.75, loc=(-1100, -400))
        rr = _ramp(nt, rust_n.outputs["Fac"], [(0.50, "#000000"), (0.74, "#9a9a9a")],
                   "rust_amt", loc=(-900, -400))
        col = _mixc(nt, col, _node(nt, "ShaderNodeRGB", "rust_c", (-900, -600)
                                   ).outputs[0], rr.outputs["Color"], "rust_mix",
                    "MIX", loc=(-500, 0))
        nt.nodes["rust_c"].outputs[0].default_value = _srgb(rust)
    bump = _bump(nt, _bw(nt, n.outputs["Fac"], "hb", loc=(-600, -620)), 0.18, 0.004)
    _finish(nt, col, rough=rough, spec=0.5, bump=bump, metal=metal)
    return mat


def _stone_mat(name, base, light, dark, scale=3.2):
    return _grain_mat(name, base, light, dark, scale=scale, rough=0.86,
                      extra_dirt=None, spec=0.28)


def _flat_mat(name, base, rough=0.9, metal=0.0, spec=0.3, tint=None, scale=5.0):
    mat, nt = _mat(name)
    co = _co(nt)
    n = _noise(nt, co, scale, "n", 5.0, 0.62)
    r = _ramp(nt, n.outputs["Fac"], [(0.30, _srgb(darken(base, 0.72))),
                                     (0.55, base), (0.84, _srgb(darken(base, 1.14)))],
              "col")
    col = r.outputs["Color"]
    if tint:
        tn = _noise(nt, co, 0.9, "tint", 3.0, 0.6, loc=(-1100, -400))
        tr = _ramp(nt, tn.outputs["Fac"], [(0.45, "#000000"), (0.70, "#808080")],
                   "tint_amt", loc=(-900, -400))
        col = _mixc(nt, col, _node(nt, "ShaderNodeRGB", "tint_c", (-900, -600)
                                   ).outputs[0], tr.outputs["Color"], "tint_mix",
                    "MIX", loc=(-500, 0))
        nt.nodes["tint_c"].outputs[0].default_value = _srgb(tint)
    bump = _bump(nt, _bw(nt, n.outputs["Fac"], "hb", loc=(-600, -620)), 0.25, 0.006)
    _finish(nt, col, rough=rough, spec=spec, bump=bump, metal=metal)
    return mat


def darken(h, mul):
    r, g, b, _ = _srgb(h)
    return "#%02x%02x%02x" % (max(0, min(255, int(r ** (1 / 2.4) * 255 * mul))),
                              max(0, min(255, int(g ** (1 / 2.4) * 255 * mul))),
                              max(0, min(255, int(b ** (1 / 2.4) * 255 * mul))))


MATS = ("wood", "wood_dark", "wood_pale", "iron", "rust", "burlap", "straw",
        "pottery", "stone", "water", "glow", "cloth_red", "cloth_blue",
        "cloth_cream", "cloth_green", "cloth_ochre", "leaf_pile", "veg",
        "produce_o", "produce_r", "produce_y", "fish")

_PAL = {}


def palette(MAT=None):
    """Build (once) the prop palette.  Reuses capital's water/glow when given."""
    if _PAL:
        return _PAL
    P = _PAL
    P["wood"] = _grain_mat("sl_wood", "#6d4826", "#8f6238", "#3f2a16",
                           scale=11.0, rough=0.80, extra_dirt="#4a3520")
    P["wood_dark"] = _grain_mat("sl_wood_dark", "#42301e", "#5e4429", "#251a10",
                                scale=9.0, rough=0.82)
    P["wood_pale"] = _grain_mat("sl_wood_pale", "#9c7c50", "#b99767", "#6b5335",
                                scale=13.0, rough=0.78)
    P["iron"] = _metal_mat("sl_iron", "#33313a", rough=0.44, metal=0.85,
                           rust="#5a3a26")
    P["rust"] = _metal_mat("sl_rust", "#5b3a24", rough=0.72, metal=0.35)
    P["burlap"] = _grain_mat("sl_burlap", "#9d855c", "#b8a077", "#6d5837",
                             scale=26.0, rough=0.94, spec=0.10)
    P["straw"] = _grain_mat("sl_straw", "#b99b45", "#d8bc63", "#7d6628",
                            scale=22.0, rough=0.92, spec=0.10,
                            extra_dirt="#6b5a25")
    P["pottery"] = _grain_mat("sl_pottery", "#7d4a35", "#96604a", "#4f2c1e",
                              scale=17.0, rough=0.55, spec=0.42)
    P["stone"] = _stone_mat("sl_stone", "#8b8375", "#a49c8c", "#5f594d")
    # the yard floor: a block's inner ground ships as bare beige, which is what
    # makes a courtyard read as a car park.  Reuse the city's own cobble and
    # earth so a yard pad matches the street it opens onto.
    P["cobble"] = (MAT or {}).get("cobble")
    if P["cobble"] is None:
        P["cobble"] = _stone_mat("sl_cobble", "#6f6a60", "#8b8578", "#4a463e",
                                 scale=26.0)
    P["earth"] = (MAT or {}).get("earth")
    if P["earth"] is None:
        P["earth"] = _grain_mat("sl_earth", "#7d6a4c", "#94805c", "#4f4230",
                                scale=9.0)
    P["water"] = MAT.get("water") if MAT else None
    if P["water"] is None:
        P["water"] = _flat_mat("sl_water", "#2c4a4b", rough=0.12, spec=0.6,
                               scale=2.0)
    P["glow"] = MAT.get("glow_warm") if MAT else None
    if P["glow"] is None:
        m, nt = _mat("sl_glow")
        _finish(nt, _node(nt, "ShaderNodeRGB", "c", (-600, 0)).outputs[0],
                rough=0.4, emit=(_srgb("#ffcb8a"), 7.0))
        nt.nodes["c"].outputs[0].default_value = _srgb("#ffcb8a")
        P["glow"] = m
    P["cloth_red"] = _cloth_mat("sl_cloth_red", "#7d3a30", "#cdbc99", stripe=11.0)
    P["cloth_blue"] = _cloth_mat("sl_cloth_blue", "#31506e", "#c6c0ac", stripe=11.0)
    P["cloth_cream"] = _cloth_mat("sl_cloth_cream", "#c2b596", None)
    P["cloth_green"] = _cloth_mat("sl_cloth_green", "#44583a", "#b2a682", stripe=12.0)
    P["cloth_ochre"] = _cloth_mat("sl_cloth_ochre", "#96743a", None)
    # awnings: an awning is the brightest, most saturated thing in a street, so
    # it gets its own striped cloths instead of borrowing the dark garment dyes
    P["awning_red"] = _cloth_mat("sl_awning_red", "#cabb99", "#9a3f30",
                                 stripe=9.0)
    P["awning_ochre"] = _cloth_mat("sl_awning_ochre", "#cabb99", "#a8823a",
                                   stripe=9.0)
    P["awning_blue"] = _cloth_mat("sl_awning_blue", "#cabb99", "#3d5a74",
                                  stripe=9.0)
    P["leaf_pile"] = _grain_mat("sl_leafpile", "#6a5a2c", "#8a7738", "#40351a",
                                scale=9.0, rough=0.95, spec=0.06)
    P["veg"] = _grain_mat("sl_veg", "#4d6b32", "#68883f", "#31461f", scale=8.0,
                          rough=0.85, spec=0.20)
    P["produce_o"] = _flat_mat("sl_prod_o", "#a5672c", rough=0.62, spec=0.35,
                               scale=14.0)
    P["produce_r"] = _flat_mat("sl_prod_r", "#7f312a", rough=0.55, spec=0.4,
                               scale=14.0)
    P["produce_y"] = _flat_mat("sl_prod_y", "#b08f36", rough=0.6, spec=0.35,
                               scale=14.0)
    P["fish"] = _flat_mat("sl_fish", "#b8bcc0", rough=0.32, metal=0.5, spec=0.6,
                          scale=9.0)
    # foliage: the city already owns a leaf shader (capital.py:init_mats); reuse
    # it so a yard tree sits in the same greenscape as city_trees.  Fall back to
    # our own if the module is used without capital's MAT.
    P["leaf"] = (MAT or {}).get("leaf")
    if P["leaf"] is None:
        P["leaf"] = _grain_mat("sl_leaf", "#4c6c34", "#5f8541", "#2b3f1e",
                               scale=5.5, rough=0.88, spec=0.22)
    P["leaf_dark"] = (MAT or {}).get("leaf_dark")
    if P["leaf_dark"] is None:
        P["leaf_dark"] = _grain_mat("sl_leaf_dark", "#33502a", "#446536",
                                    "#1d3017", scale=6.5, rough=0.90, spec=0.18)
    P["skin"] = _flat_mat("sl_skin", "#a97f5e", rough=0.78, spec=0.25, scale=18.0)
    P["paint"] = _flat_mat("sl_paint", "#7d6a4c", rough=0.72, spec=0.30, scale=9.0)
    return P


# ===========================================================================
# geometry pool: local primitives -> numpy proto -> world-space batches
# ===========================================================================
def _rot3(rx=0.0, ry=0.0, rz=0.0):
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    return (cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx,
            sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx,
            -sy, cy * sx, cy * cx)


def _mx(R, v):
    if R is None:
        return v
    x, y, z = v
    return (R[0] * x + R[1] * y + R[2] * z,
            R[3] * x + R[4] * y + R[5] * z,
            R[6] * x + R[7] * y + R[8] * z)


_BOX_F = ((4, 5, 6, 7), (0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 6, 5),
          (2, 3, 7, 6), (3, 0, 4, 7))


class Geo(object):
    """Accumulates verts/faces per material in one local frame."""

    __slots__ = ("m",)

    def __init__(self):
        self.m = {}

    def add(self, mat, verts, faces):
        s = self.m.get(mat)
        if s is None:
            s = self.m[mat] = [[], []]
        o = len(s[0])
        s[0].extend(verts)
        if faces:
            s[1].extend([tuple(i + o for i in f) for f in faces])

    # -- primitives --------------------------------------------------------
    def box(self, mat, c, s, R=None):
        hx, hy, hz = s[0] * 0.5, s[1] * 0.5, s[2] * 0.5
        loc = ((-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
               (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz))
        cx, cy, cz = c
        verts = []
        for v in loc:
            p = _mx(R, v)
            verts.append((p[0] + cx, p[1] + cy, p[2] + cz))
        self.add(mat, verts, _BOX_F)

    def beam(self, mat, p0, p1, w, h=None):
        """A box running from p0 to p1 (planks, rungs, rails, ropes)."""
        h = w if h is None else h
        dx, dy, dz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        L = math.sqrt(dx * dx + dy * dy + dz * dz)
        if L < 1e-6:
            return
        dx, dy, dz = dx / L, dy / L, dz / L
        # any perpendicular pair
        ux, uy, uz = (0.0, 0.0, 1.0)
        if abs(dz) > 0.9:
            ux, uy, uz = (1.0, 0.0, 0.0)
        ax = uy * dz - uz * dy
        ay = uz * dx - ux * dz
        az = ux * dy - uy * dx
        n = math.sqrt(ax * ax + ay * ay + az * az)
        ax, ay, az = ax / n, ay / n, az / n
        bx = dy * az - dz * ay
        by = dz * ax - dx * az
        bz = dx * ay - dy * ax
        hw, hh = w * 0.5, h * 0.5
        verts = []
        for (px, py, pz) in (p0, p1):
            for (sa, sb) in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
                verts.append((px + ax * sa + bx * sb, py + ay * sa + by * sb,
                              pz + az * sa + bz * sb))
        self.add(mat, verts, _BOX_F)

    def cyl(self, mat, c, r, h, seg=10, r2=None, R=None, caps=True):
        r2 = r if r2 is None else r2
        z0, z1 = -h * 0.5, h * 0.5
        verts, faces = [], []
        for z, rr in ((z0, r), (z1, r2)):
            for i in range(seg):
                a = TAU * i / seg
                verts.append((rr * math.cos(a), rr * math.sin(a), z))
        for i in range(seg):
            j = (i + 1) % seg
            faces.append((i, j, seg + j, seg + i))
        if caps:
            verts.append((0.0, 0.0, z0))
            verts.append((0.0, 0.0, z1))
            cb, ct = 2 * seg, 2 * seg + 1
            for i in range(seg):
                j = (i + 1) % seg
                faces.append((ct, seg + i, seg + j))
                faces.append((cb, j, i))
        cx, cy, cz = c
        out = []
        for v in verts:
            p = _mx(R, v)
            out.append((p[0] + cx, p[1] + cy, p[2] + cz))
        self.add(mat, out, faces)

    def band(self, mat, c, r, h, seg=10, R=None):
        """Open ring (barrel hoop, cart tyre, bucket rim)."""
        verts, faces = [], []
        for z in (-h * 0.5, h * 0.5):
            for i in range(seg):
                a = TAU * i / seg
                verts.append((r * math.cos(a), r * math.sin(a), z))
        for i in range(seg):
            j = (i + 1) % seg
            faces.append((i, j, seg + j, seg + i))
        cx, cy, cz = c
        out = []
        for v in verts:
            p = _mx(R, v)
            out.append((p[0] + cx, p[1] + cy, p[2] + cz))
        self.add(mat, out, faces)

    def lathe(self, mat, c, prof, seg=10, R=None, caps=True):
        """prof = [(r, z), ...] bottom to top."""
        verts, faces = [], []
        for (r, z) in prof:
            for i in range(seg):
                a = TAU * i / seg
                verts.append((r * math.cos(a), r * math.sin(a), z))
        nb = len(prof)
        for k in range(nb - 1):
            b, t = k * seg, (k + 1) * seg
            for i in range(seg):
                j = (i + 1) % seg
                faces.append((b + i, b + j, t + j, t + i))
        if caps:
            if prof[0][0] > 1e-5:
                verts.append((0.0, 0.0, prof[0][1]))
                cb = len(verts) - 1
                for i in range(seg):
                    faces.append((cb, (i + 1) % seg, i))
            if prof[-1][0] > 1e-5:
                verts.append((0.0, 0.0, prof[-1][1]))
                ct = len(verts) - 1
                t = (nb - 1) * seg
                for i in range(seg):
                    faces.append((ct, t + i, t + (i + 1) % seg))
        cx, cy, cz = c
        out = []
        for v in verts:
            p = _mx(R, v)
            out.append((p[0] + cx, p[1] + cy, p[2] + cz))
        self.add(mat, out, faces)

    def sphere(self, mat, c, r, seg=8, ring=4, sqz=1.0, R=None):
        prof = []
        for k in range(ring + 1):
            t = math.pi * k / ring
            prof.append((r * math.sin(t), -r * math.cos(t) * sqz))
        prof[0] = (0.0, prof[0][1])
        prof[-1] = (0.0, prof[-1][1])
        self.lathe(mat, c, prof, seg=seg, R=R, caps=False)

    def quad(self, mat, p0, p1, p2, p3):
        self.add(mat, [p0, p1, p2, p3], ((0, 1, 2, 3),))

    def panel(self, mat, c, w, h, R=None, sag=0.0, seg=2):
        """A cloth/board panel hanging in local XZ, y = 0 (+sag in Y)."""
        verts, faces = [], []
        for iy in range(seg + 1):
            for ix in range(seg + 1):
                u = ix / float(seg) - 0.5
                v = iy / float(seg) - 0.5
                y = math.sin(u * math.pi) * sag
                verts.append((u * w, y, v * h))
        n = seg + 1
        for iy in range(seg):
            for ix in range(seg):
                a = iy * n + ix
                faces.append((a, a + 1, a + n + 1, a + n))
        cx, cy, cz = c
        out = []
        for v in verts:
            p = _mx(R, v)
            out.append((p[0] + cx, p[1] + cy, p[2] + cz))
        self.add(mat, out, faces)


def to_proto(g):
    """{matname: (verts ndarray, flat loops, sizes)} -- rotatable, shareable."""
    out = {}
    for matname, (v, f) in g.m.items():
        loops, sizes = [], []
        for fc in f:
            loops.extend(fc)
            sizes.append(len(fc))
        out[matname] = (np.asarray(v, dtype=np.float64),
                        np.asarray(loops, dtype=np.int32),
                        np.asarray(sizes, dtype=np.int32))
    return out


class Batch(object):
    """World-space accumulator for one output object (any number of materials)."""

    def __init__(self, name):
        self.name = name
        self.co = []                      # global vert chunks, insertion order
        self.ch = {}                      # matname -> [loops chunks, sizes chunks]
        self.slot = {}                    # matname -> material slot index
        self.mats = []
        self.nv = 0
        self.nf = 0
        self.tris = 0

    def put(self, proto, x, y, z, yaw, sc=1.0):
        ca, sa = math.cos(yaw) * sc, math.sin(yaw) * sc
        zs = z
        for matname, (v, loops, sizes) in proto.items():
            ch = self.ch.get(matname)
            if ch is None:
                ch = self.ch[matname] = [[], []]
                self.slot[matname] = len(self.mats)
                self.mats.append(matname)
            n = v.shape[0]
            co = np.empty((n, 3), dtype=np.float32)
            co[:, 0] = v[:, 0] * ca - v[:, 1] * sa + x
            co[:, 1] = v[:, 0] * sa + v[:, 1] * ca + y
            co[:, 2] = v[:, 2] * sc + zs
            self.co.append(co)
            ch[0].append(loops + self.nv)
            ch[1].append(sizes)
            self.nv += n
            self.nf += sizes.shape[0]
            self.tris += int(sizes.sum()) - 2 * sizes.shape[0]

    def emit(self, pal):
        if not self.co:
            return None
        co = np.concatenate(self.co, axis=0)
        loops = []
        sizes = []
        midx = []
        for matname in self.mats:
            ch = self.ch[matname]
            loops.append(np.concatenate(ch[0]))
            sz = np.concatenate(ch[1])
            sizes.append(sz)
            midx.append(np.full(sz.shape[0], self.slot[matname], dtype=np.int32))
        loops = np.concatenate(loops)
        sizes = np.concatenate(sizes)
        midx = np.concatenate(midx)
        starts = np.zeros(sizes.shape[0], dtype=np.int32)
        if sizes.shape[0] > 1:
            starts[1:] = np.cumsum(sizes)[:-1]
        me = bpy.data.meshes.new(self.name)
        me.vertices.add(co.shape[0])
        me.vertices.foreach_set("co", co.ravel())
        me.loops.add(loops.shape[0])
        me.loops.foreach_set("vertex_index", loops)
        me.polygons.add(sizes.shape[0])
        me.polygons.foreach_set("loop_start", starts)
        me.polygons.foreach_set("material_index", midx)
        me.polygons.foreach_set("use_smooth", np.zeros(sizes.shape[0], np.int8))
        me.update(calc_edges=True)
        for matname in self.mats:
            # Geo stores material datablocks; accept palette keys as well
            m = pal.get(matname) if isinstance(matname, str) else matname
            me.materials.append(m or pal["wood"])
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        _log("%-13s verts=%-7d faces=%-7d tris=%-7d mats=%d"
             % (self.name, co.shape[0], sizes.shape[0], self.tris, len(self.mats)))
        return ob


# ===========================================================================
# prop geometry (local frame: +X = long axis, +Y = front, z = 0 = ground)
# ===========================================================================
def p_barrel(g, P, r, h):
    # 8 segments, 4 profile points, 2 hoops: ~72 faces.  Barrels are the most
    # numerous prop in the city (4.5k of them), so every face here is paid 4.5k
    # times over; the silhouette and the top disc are what the game camera sees.
    prof = [(r * 0.90, 0.0), (r * 1.04, h * 0.32), (r * 1.04, h * 0.68),
            (r * 0.90, h)]
    g.lathe(P["wood"], (0, 0, 0), prof, seg=8)
    # lid: a lighter disc, so the top face (all the camera sees) reads as planks
    g.lathe(P["wood_pale"], (0, 0, h - 0.012), [(r * 0.86, 0.0), (r * 0.86, 0.014)],
            seg=8)
    for k in (0.20, 0.80):
        g.band(P["iron"], (0, 0, h * k), r * 1.055, 0.055, seg=8)


def p_crate(g, P, s, h):
    g.box(P["wood"], (0, 0, h * 0.5), (s, s * 0.82, h))
    for sy in (-1, 1):
        for sz in (0.18, 0.82):
            g.box(P["wood_dark"], (0, sy * s * 0.41, h * sz),
                  (s * 1.02, 0.045, 0.075))
    for sx in (-1, 1):
        for sy in (-1, 1):
            g.box(P["wood_dark"], (sx * s * 0.47, sy * s * 0.38, h * 0.5),
                  (0.05, 0.05, h * 0.98))
    g.box(P["wood_pale"], (0, 0, h - 0.012), (s * 0.96, s * 0.78, 0.03))


def p_sacks(g, P, n=2, seed=0):
    rnd = _R(seed)
    for i in range(n):
        x = (i - (n - 1) * 0.5) * 0.46 + rnd.uniform(-0.05, 0.05)
        y = rnd.uniform(-0.12, 0.12)
        r = rnd.uniform(0.20, 0.26)
        g.sphere(P["burlap"], (x, y, 0.0), r, seg=6, ring=3, sqz=1.25)
        # tied neck
        g.cyl(P["burlap"], (x, y, r * 1.02), 0.055, 0.16, seg=5, r2=0.075)


def p_hay(g, P, r=0.34, L=0.95, lying=True):
    R = _rot3(rx=math.pi * 0.5) if lying else None
    c = (0, 0, r) if lying else (0, 0, L * 0.5)
    g.cyl(P["straw"], c, r, L, seg=9, R=R)
    for s in (-1, 1):
        if lying:
            g.band(P["wood_dark"], (s * L * 0.3, 0, r), r * 1.02, 0.045, seg=9,
                   R=_rot3(rx=math.pi * 0.5))
    # loose straw on the ground
    for i in range(3):
        a = i * 2.1
        g.box(P["straw"], (math.cos(a) * (r + 0.12), math.sin(a) * (r + 0.12), 0.02),
              (0.26, 0.05, 0.02), R=_rot3(rz=a))


def p_woodpile(g, P):
    """Split logs stacked against the wall + chopping block + axe."""
    for layer in range(3):
        for i in range(4 - layer):
            x = (i - (3 - layer) * 0.5) * 0.24
            g.cyl(P["wood_dark"], (x, 0, 0.13 + layer * 0.22), 0.115, 0.72,
                  seg=6, R=_rot3(ry=math.pi * 0.5))
    g.cyl(P["wood"], (0.55, 0, 0.19), 0.24, 0.38, seg=9)          # chopping block
    g.beam(P["wood_pale"], (0.55, 0.06, 0.55), (0.42, 0.10, 0.20), 0.05)   # handle
    g.box(P["iron"], (0.44, 0.11, 0.36), (0.16, 0.05, 0.10),
          R=_rot3(rz=0.5, ry=0.6))


def p_handcart(g, P):
    """Two-wheel barrow with a load of sacks."""
    for sy in (-1, 1):
        g.cyl(P["wood_dark"], (0.10, sy * 0.56, 0.42), 0.42, 0.075, seg=12,
              R=_rot3(rx=math.pi * 0.5))
        g.band(P["iron"], (0.10, sy * 0.56, 0.42), 0.425, 0.06, seg=12,
               R=_rot3(rx=math.pi * 0.5))
        for k in range(6):
            a = TAU * k / 6.0
            g.beam(P["wood_dark"],
                   (0.10, sy * 0.56, 0.42),
                   (0.10 + math.cos(a) * 0.4, sy * 0.56, 0.42 + math.sin(a) * 0.4),
                   0.045)
    g.box(P["wood"], (0, 0, 0.72), (1.30, 0.94, 0.09))
    for s in (-1, 1):
        g.box(P["wood"], (0, s * 0.46, 0.86), (1.30, 0.055, 0.26))
    for s in (-1, 1):
        g.beam(P["wood"], (-0.72, s * 0.36, 0.80), (-1.62, s * 0.30, 0.86), 0.07)
    for i, sx in enumerate((-0.30, 0.22)):
        g.sphere(P["burlap"], (sx, 0.02, 0.72), 0.26, seg=7, ring=4, sqz=1.15)


def p_wagon(g, P):
    for sy in (-1, 1):
        for sx in (-1, 1):
            g.cyl(P["wood_dark"], (sx * 0.85, sy * 0.66, 0.60), 0.58, 0.08, seg=12,
                  R=_rot3(rx=math.pi * 0.5))
            g.band(P["iron"], (sx * 0.85, sy * 0.66, 0.60), 0.585, 0.07, seg=12,
                   R=_rot3(rx=math.pi * 0.5))
            for k in range(7):
                a = TAU * k / 7.0
                g.beam(P["wood_dark"], (sx * 0.85, sy * 0.66, 0.60),
                       (sx * 0.85 + math.cos(a) * 0.54, sy * 0.66,
                        0.60 + math.sin(a) * 0.54), 0.05)
    g.box(P["wood"], (0, 0, 0.96), (2.30, 1.26, 0.11))
    for s in (-1, 1):
        g.box(P["wood"], (0, s * 0.62, 1.20), (2.30, 0.07, 0.42))
        g.box(P["wood"], (s * 1.16, 0, 1.20), (0.07, 1.26, 0.42))
    g.box(P["wood_dark"], (0, 0, 1.10), (2.6, 0.16, 0.14))
    for s in (-1, 1):
        g.beam(P["wood_dark"], (-1.3, s * 0.30, 1.02), (-2.5, s * 0.26, 0.92), 0.09)
    g.sphere(P["burlap"], (0.35, 0.0, 1.02), 0.30, seg=7, ring=4, sqz=1.0)


def p_pallet(g, P, w=1.2, d=0.9, cloth=True):
    for i in range(4):
        g.box(P["wood_pale"], ((i - 1.5) * d * 0.28, 0, 0.10), (0.13, w, 0.05))
    g.box(P["wood_pale"], (0, 0, 0.06), (d, w, 0.06))
    # cargo under a cloth
    g.box(P["burlap"], (0, 0, 0.36), (d * 0.86, w * 0.82, 0.44))
    if cloth:
        g.panel(P["cloth_cream"], (0, 0, 0.60), d * 0.95, w * 0.9,
                R=_rot3(rx=math.pi * 0.5), sag=0.07, seg=2)


def p_planks(g, P, seed=0):
    rnd = _R(seed)
    for i in range(3):
        L = rnd.uniform(1.4, 2.2)
        g.box(P["wood_pale"], (0, i * 0.16 - 0.16, 0.06 + i * 0.05),
              (L, 0.19, 0.045), R=_rot3(rz=rnd.uniform(-0.12, 0.12)))
    g.box(P["wood"], (-0.1, 0.30, 0.55), (1.5, 0.16, 0.05),
          R=_rot3(rz=0.35, rx=-0.5))


def p_bucket(g, P):
    prof = [(0.15, 0.0), (0.185, 0.29)]
    g.lathe(P["wood_dark"], (0, 0, 0), prof, seg=9)
    g.band(P["iron"], (0, 0, 0.06), 0.163, 0.035, seg=9)
    g.band(P["iron"], (0, 0, 0.24), 0.19, 0.035, seg=9)
    g.beam(P["iron"], (-0.17, 0, 0.28), (0, 0, 0.42), 0.02)
    g.beam(P["iron"], (0, 0, 0.42), (0.17, 0, 0.28), 0.02)


def p_yoke(g, P):
    g.beam(P["wood_pale"], (-0.9, 0, 0.28), (0.9, 0, 0.28), 0.09, 0.07)
    for s in (-1, 1):
        g.beam(P["iron"], (s * 0.62, 0, 0.26), (s * 0.62, 0, 0.12), 0.025)
    p_bucket(g, P)


def p_trough(g, P, L=1.7):
    """Stone drinking trough with a water surface."""
    for s in (-1, 1):
        g.box(P["stone"], (0, s * 0.30, 0.26), (L, 0.16, 0.52))
        g.box(P["stone"], (s * L * 0.5, 0, 0.26), (0.16, 0.62, 0.52))
    g.box(P["stone"], (0, 0, 0.06), (L, 0.56, 0.12))
    g.panel(P["water"], (0, 0, 0.44), L - 0.28, 0.44, R=_rot3(rx=math.pi * 0.5))
    for s in (-1, 1):
        g.box(P["stone"], (s * (L * 0.5 + 0.16), 0, 0.10), (0.34, 0.5, 0.2))


def p_hitch(g, P):
    g.box(P["wood_dark"], (0, 0, 0.52), (0.16, 0.16, 1.04))
    g.band(P["iron"], (0, 0, 0.92), 0.11, 0.05, seg=8)
    for s in (-1, 1):
        g.beam(P["iron"], (0, 0, 0.80), (s * 0.22, 0.10, 0.66), 0.03)
    g.box(P["stone"], (0, 0, 0.05), (0.5, 0.5, 0.10))


def p_bench(g, P):
    for s in (-1, 1):
        g.box(P["wood_dark"], (s * 0.62, 0, 0.21), (0.13, 0.42, 0.42))
    for i in range(2):
        g.box(P["wood"], (0, (i - 0.5) * 0.20, 0.45), (1.5, 0.17, 0.06))
    g.box(P["wood"], (0.62, -0.16, 0.72), (1.33, 0.06, 0.20),
          R=_rot3(rx=0.15))


def p_stone_bench(g, P):
    g.box(P["stone"], (0, 0, 0.42), (1.7, 0.44, 0.14))
    for s in (-1, 1):
        g.box(P["stone"], (s * 0.62, 0, 0.19), (0.28, 0.40, 0.38))


def p_well(g, P):
    prof = [(1.05, 0.0), (1.05, 0.10), (1.15, 0.16), (1.15, 0.78),
            (1.05, 0.86), (1.05, 0.96)]
    g.lathe(P["stone"], (0, 0, 0), prof, seg=12, caps=False)
    g.lathe(P["stone"], (0, 0, 0), [(0.86, 0.0), (0.86, 0.02)], seg=12)
    g.cyl(P["water"], (0, 0, 0.55), 0.88, 0.04, seg=12)
    for s in (-1, 1):
        g.box(P["wood_dark"], (s * 1.02, 0, 1.68), (0.14, 0.14, 1.6))
    g.cyl(P["wood_dark"], (0, 0, 2.36), 0.10, 2.0, seg=8, R=_rot3(ry=math.pi * 0.5))
    g.beam(P["wood"], (0.0, 0, 2.50), (0.0, 0, 1.30), 0.03)
    for s in (-1, 1):
        g.beam(P["wood_dark"], (s * 1.02, 0, 2.50), (0.0, 0, 2.72), 0.10)
    p_bucket(g, P)
    g.m[P["wood"]][0][-3] = g.m[P["wood"]][0][-3]
    # the bucket hangs at the well mouth
    g2 = Geo()
    p_bucket(g2, P)
    for matname, (v, f) in g2.m.items():
        o = len(g.m.setdefault(matname, [[], []])[0])
        g.m[matname][0].extend([(p[0] * 0.9 + 0.0, p[1] * 0.9, p[2] + 0.82) for p in v])
        g.m[matname][1].extend([tuple(i + o for i in fc) for fc in f])


def p_lantern(g, P, h=3.2):
    g.beam(P["iron"], (0, 0, h - 0.55), (0, 0.55, h - 0.30), 0.055)
    g.beam(P["iron"], (0, 0, h - 0.90), (0, 0.40, h - 0.30), 0.04)
    g.box(P["iron"], (0, 0.52, h - 0.95), (0.06, 0.06, 0.42))
    g.box(P["iron"], (0, 0.52, h - 1.28), (0.30, 0.30, 0.06))
    g.box(P["glow"], (0, 0.52, h - 1.05), (0.24, 0.24, 0.34))
    for sx in (-1, 1):
        for sy in (-1, 1):
            g.box(P["iron"], (sx * 0.13, 0.52 + sy * 0.13, h - 1.05),
                  (0.04, 0.04, 0.38))
    g.cyl(P["iron"], (0, 0.52, h - 0.72), 0.20, 0.16, seg=4, r2=0.02)


def p_sign(g, P, kind=0):
    """Hanging shop sign: iron bracket + plank board, no glass."""
    g.beam(P["iron"], (0, 0, 3.35), (0, 0.62, 3.30), 0.06)
    g.beam(P["iron"], (0, 0.10, 2.95), (0, 0.58, 3.28), 0.035)
    for s in (-1, 1):
        g.beam(P["iron"], (s * 0.30, 0.58, 3.30), (s * 0.30, 0.58, 3.16), 0.02)
    mat = (P["wood_pale"], P["cloth_red"], P["cloth_blue"], P["cloth_ochre"])[kind % 4]
    g.box(P["wood_dark"], (0, 0.58, 2.86), (0.78, 0.06, 0.60))
    g.box(mat, (0, 0.55, 2.86), (0.70, 0.03, 0.52))
    g.box(P["wood_dark"], (0, 0.55, 2.86), (0.74, 0.02, 0.06))
    g.box(P["wood_dark"], (0, 0.55, 2.86), (0.06, 0.02, 0.56))
    # painted symbol: three raised bars
    for i in range(3):
        g.box(P["wood_pale"], (0, 0.52, 2.72 + i * 0.14), (0.42, 0.02, 0.07))


def p_laundry(g, P, span=5.0, z=3.6, seed=0):
    rnd = _R(seed)
    g.beam(P["iron"], (0, 0, z) if False else (-span * 0.5, 0, z),
           (span * 0.5, 0, z - 0.18), 0.025)
    n = rnd.randint(3, 5)
    cols = (P["cloth_cream"], P["cloth_red"], P["cloth_blue"], P["cloth_green"],
            P["cloth_ochre"])
    for i in range(n):
        u = -0.42 + 0.84 * (i + 0.5) / n + rnd.uniform(-0.03, 0.03)
        w = rnd.uniform(0.45, 0.85)
        h = rnd.uniform(0.55, 1.05)
        zz = z - 0.18 * (u + 0.5) - h * 0.5
        g.panel(cols[(i + seed) % len(cols)], (u * span, 0, zz), w, h, sag=0.05,
                seg=1)


def p_leaves(g, P, seed=0):
    rnd = _R(seed)
    for i in range(9):
        a = rnd.uniform(0, TAU)
        d = rnd.uniform(0.1, 0.85)
        g.box(P["leaf_pile"], (math.cos(a) * d, math.sin(a) * d, 0.01),
              (rnd.uniform(0.14, 0.3), rnd.uniform(0.08, 0.18), 0.015),
              R=_rot3(rz=a + rnd.uniform(-0.6, 0.6)))
    g.sphere(P["leaf_pile"], (0, 0, 0.02), 0.20, seg=6, ring=3, sqz=0.35)


def p_wheel(g, P):
    """Broken cart wheel leaning on the wall, one spoke snapped."""
    R = _rot3(rx=math.pi * 0.5, rz=0.18)
    g.band(P["wood_dark"], (0, 0.12, 0.52), 0.50, 0.09, seg=12, R=R)
    g.band(P["iron"], (0, 0.12, 0.52), 0.505, 0.05, seg=12, R=R)
    g.cyl(P["wood_dark"], (0, 0.12, 0.52), 0.10, 0.16, seg=8, R=R)
    for k in range(5):
        a = TAU * k / 6.0
        if k == 3:
            continue
        g.beam(P["wood_dark"], (0, 0.12, 0.52),
               (math.cos(a) * 0.46, 0.12, 0.52 + math.sin(a) * 0.46), 0.05)


def p_ladder(g, P, h=2.4):
    lean = 0.26
    top = (0.0, h * math.sin(lean) * -1.0, h * math.cos(lean))
    for s in (-1, 1):
        g.beam(P["wood_pale"], (s * 0.24, 0, 0), (top[0] + s * 0.24, top[1], top[2]),
               0.07, 0.05)
    n = 7
    for k in range(n):
        t = (k + 0.5) / n
        y = top[1] * t
        z = top[2] * t
        g.beam(P["wood_pale"], (-0.24, y, z), (0.24, y, z), 0.05)


def p_stall(g, P, w=2.4, d=1.6, cloth=None):
    cloth = cloth or P["cloth_red"]
    for sx in (-1, 1):
        for sy in (-1, 1):
            g.box(P["wood"], (sx * w * 0.42, sy * d * 0.42, 1.10),
                  (0.08, 0.08, 2.20))
    g.box(P["wood"], (0, 0, 0.92), (w, d, 0.09))
    for s in (-1, 1):
        g.box(P["wood_dark"], (0, s * d * 0.46, 1.06), (w, 0.06, 0.22))
    # awning: two sloping sheets, striped, with a scalloped valance
    g.panel(cloth, (0, 0, 2.34), w + 0.55, d + 0.85, R=_rot3(rx=math.pi * 0.5),
            sag=0.10, seg=3)
    for s in (-1, 1):
        g.panel(cloth if s > 0 else P["cloth_cream"],
                (0, s * (d * 0.5 + 0.36), 2.06), w + 0.5, 0.34, sag=0.02, seg=2)
    # goods
    rnd = _R(7)
    for i in range(5):
        x = -w * 0.36 + i * w * 0.18
        g.box(P["wood_pale"], (x, 0.02, 1.02), (0.28, 0.34, 0.10))
        g.sphere(rnd.choice((P["produce_o"], P["produce_r"], P["produce_y"])),
                 (x, 0.02, 1.12), 0.09, seg=6, ring=3, sqz=0.8)
    for s in (-1, 1):
        g.box(P["wood"], (s * w * 0.30, d * 0.30, 0.34), (0.42, 0.38, 0.5))


def p_rack(g, P, w=1.6):
    """Cloth-drying rack / trestle for a yard."""
    for s in (-1, 1):
        for sy in (-1, 1):
            g.beam(P["wood"], (s * w * 0.5, sy * 0.30, 0), (s * w * 0.5, 0, 1.70),
                   0.06)
    g.beam(P["wood"], (-w * 0.5, 0, 1.70), (w * 0.5, 0, 1.70), 0.05)
    g.beam(P["wood"], (-w * 0.5, 0, 1.45), (w * 0.5, 0, 1.45), 0.045)
    for i in range(3):
        g.panel((P["cloth_cream"], P["cloth_blue"], P["cloth_red"])[i],
                ((i - 1) * w * 0.30, 0, 1.22), 0.42, 0.48, sag=0.04, seg=1)


def p_shed(g, P, w=2.2, d=1.8, h=1.9):
    for sx in (-1, 1):
        for sy in (-1, 1):
            g.box(P["wood_dark"], (sx * (w * 0.5 - 0.07), sy * (d * 0.5 - 0.07),
                                   h * 0.5), (0.12, 0.12, h))
    g.box(P["wood_dark"], (0, -d * 0.5, h * 0.55), (w, 0.07, h * 0.9))
    g.box(P["wood_dark"], (0, d * 0.5, h * 0.55), (w, 0.07, h * 0.9))
    for s in (-1, 1):
        g.box(P["wood_dark"], (s * w * 0.5, 0, h * 0.55), (0.07, d, h * 0.9))
    g.box(P["wood"], (0, 0, h + 0.10), (w + 0.3, d + 0.25, 0.10),
          R=_rot3(rx=0.0))
    for s in (-1, 1):
        g.box(P["wood_pale"], (0, s * d * 0.26, h + 0.26), (w + 0.4, d * 0.62, 0.06),
              R=_rot3(rx=s * 0.42))
    g.box(P["wood"], (0, -d * 0.5 - 0.04, 0.62), (0.62, 0.05, 1.24))
    # clutter in the doorway
    g.box(P["wood"], (0.55, -d * 0.5 - 0.30, 0.22), (0.5, 0.5, 0.44))
    g.sphere(P["burlap"], (-0.55, -d * 0.5 - 0.28, 0.16), 0.2, seg=6, ring=3)


def p_yardpad(g, P, w=7.0, d=7.0, kind=0, seed=0):
    """A patch of courtyard floor: cobbles, strawed dung, bare earth.

    One big quad (2 tris) plus three streaks.  The block interiors ship as a
    single flat beige plate, and that plate is what makes a yard read as a car
    park no matter how many barrels sit on it; tiling the floor with the city's
    own cobble is the cheapest fix in the whole module.
    """
    rnd = _R(seed)
    hw, hd = w * 0.5, d * 0.5
    base = P["earth"] if kind == 2 else P["cobble"]
    g.quad(base, (-hw, -hd, 0.004), (hw, -hd, 0.004),
           (hw, hd, 0.004), (-hw, hd, 0.004))
    for i in range(3):
        x0 = rnd.uniform(-hw * 0.70, hw * 0.20)
        y0 = rnd.uniform(-hd * 0.70, hd * 0.20)
        ww = rnd.uniform(0.9, 2.6)
        hh = rnd.uniform(0.5, 1.4)
        m = P["straw"] if kind == 1 else P["earth"]
        g.quad(m, (x0, y0, 0.010), (x0 + ww, y0, 0.010),
               (x0 + ww, y0 + hh, 0.010), (x0, y0 + hh, 0.010))


def p_bed(g, P, w=1.7, d=2.4, kind=0, seed=0):
    """Cheap ground dressing: a tilled / strawed / rubbled patch.

    Quads only (~8 faces).  From the game camera (52 degrees, 34 m) the thing
    that reads is not a barrel but the *floor*: a bare beige yard stays beige no
    matter how many crates you dot on it.  These patches are the cheapest way to
    break that up, so they can be scattered by the dozen.
    """
    rnd = _R(seed)
    hw, hd = w * 0.5, d * 0.5
    zz = 0.012
    if kind == 1:
        base, stripe, tip = P["straw"], P["wood_dark"], P["straw"]
    elif kind == 2:
        base, stripe, tip = P["stone"], P["wood_dark"], P["stone"]
    else:
        base, stripe, tip = P["wood_dark"], P["veg"], P["leaf"]

    def q(mat, x0, y0, x1, y1, z):
        g.quad(mat, (x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z))

    q(base, -hw, -hd, hw, hd, zz)
    n = 3
    for i in range(n):
        y0 = -hd + (i + 0.12) * (d / n)
        y1 = -hd + (i + 0.88) * (d / n)
        q(stripe, -hw * 0.88, y0, hw * 0.88, y1, zz + 0.016)
    for i in range(3):
        cx = -hw * 0.5 + i * hw * 0.5 + rnd.uniform(-0.06, 0.06)
        cy = rnd.uniform(-hd * 0.6, hd * 0.6)
        q(tip, cx - 0.18, cy - 0.14, cx + 0.18, cy + 0.14, zz + 0.030)


def p_garden(g, P, w=3.4, d=2.6, seed=0):
    """Tilled beds with cabbages and a wattle fence on three sides."""
    rnd = _R(seed)
    for i in range(4):
        y = (i - 1.5) * d / 4.0
        g.box(P["wood_dark"], (0, y, 0.06), (w, 0.42, 0.12))
        g.box(P["veg"], (0, y, 0.13), (w * 0.96, 0.36, 0.05))
        for k in range(int(w / 0.55)):
            g.sphere(P["veg"], ((k - (w / 1.1 - 0.5)) * 0.55 + rnd.uniform(-0.05, 0.05),
                                y + rnd.uniform(-0.06, 0.06), 0.22),
                     0.15, seg=6, ring=3, sqz=0.8)
    for s in (-1, 1):
        for k in range(int(d / 0.42) + 1):
            g.box(P["wood_pale"], (s * w * 0.5, (k - d / 0.84) * 0.42, 0.42),
                  (0.06, 0.06, 0.84))
        g.beam(P["wood_pale"], (s * w * 0.5, -d * 0.5, 0.66),
               (s * w * 0.5, d * 0.5, 0.66), 0.045)
        g.beam(P["wood_pale"], (s * w * 0.5, -d * 0.5, 0.30),
               (s * w * 0.5, d * 0.5, 0.30), 0.045)


def p_haystack(g, P, r=1.05, h=1.5):
    prof = [(r * 0.92, 0.0), (r, h * 0.30), (r * 0.86, h * 0.66),
            (r * 0.45, h * 0.92), (0.05, h)]
    g.lathe(P["straw"], (0, 0, 0), prof, seg=12)
    g.band(P["wood_dark"], (0, 0, h * 0.42), r * 0.98, 0.05, seg=12)
    for i in range(4):
        a = i * 1.6
        g.box(P["straw"], (math.cos(a) * (r + 0.1), math.sin(a) * (r + 0.1), 0.02),
              (0.4, 0.08, 0.02), R=_rot3(rz=a))


def p_coop(g, P):
    for sx in (-1, 1):
        for sy in (-1, 1):
            g.box(P["wood_dark"], (sx * 0.55, sy * 0.40, 0.32), (0.08, 0.08, 0.64))
    g.box(P["wood"], (0, 0, 0.70), (1.30, 1.00, 0.10))
    g.box(P["wood_dark"], (0, 0, 0.90), (1.20, 0.90, 0.50))
    g.box(P["wood_pale"], (0, 0, 1.16), (1.30, 1.00, 0.06), R=_rot3(rx=0.10))
    for i in range(5):
        g.beam(P["wood_dark"], (-0.6 + i * 0.3, 0.46, 0.66), (-0.6 + i * 0.3, 0.46, 0.20),
               0.03)
    g.sphere(P["burlap"], (0.15, 0.0, 0.30), 0.16, seg=6, ring=3)  # nesting box


def p_compost(g, P):
    g.lathe(P["leaf_pile"], (0, 0, 0), [(0.85, 0), (0.80, 0.16), (0.55, 0.34),
                                       (0.20, 0.42)], seg=10)
    for i in range(4):
        a = i * 1.5
        g.beam(P["wood_dark"], (math.cos(a) * 0.8, math.sin(a) * 0.8, 0),
               (math.cos(a) * 0.7, math.sin(a) * 0.7, 0.7), 0.05)


def p_waterbutt(g, P):
    prof = [(0.42, 0), (0.46, 0.30), (0.44, 0.72), (0.42, 0.92)]
    g.lathe(P["wood_dark"], (0, 0, 0), prof, seg=10)
    g.band(P["iron"], (0, 0, 0.22), 0.455, 0.05, seg=10)
    g.band(P["iron"], (0, 0, 0.70), 0.44, 0.05, seg=10)
    g.cyl(P["water"], (0, 0, 0.90), 0.38, 0.03, seg=10)


def p_stonepile(g, P, seed=0):
    rnd = _R(seed)
    for i in range(5):
        a = rnd.uniform(0, TAU)
        d = rnd.uniform(0, 0.55)
        r = rnd.uniform(0.16, 0.32)
        g.sphere(P["stone"], (math.cos(a) * d, math.sin(a) * d, r * 0.42),
                 r, seg=6, ring=3, sqz=0.75)


def p_pigpen(g, P, w=2.8, d=2.2):
    for s in (-1, 1):
        for k in range(int(w / 0.5) + 1):
            g.box(P["wood_dark"], ((k - w / 1.0) * 0.5, s * d * 0.5, 0.34),
                  (0.09, 0.09, 0.68))
        g.beam(P["wood_dark"], (-w * 0.5, s * d * 0.5, 0.55), (w * 0.5, s * d * 0.5, 0.55),
               0.05)
    g.box(P["wood_dark"], (0, 0, 0.30), (w, d, 0.10))
    for i in range(3):
        g.box(P["leaf_pile"], (0, -0.2 + i * 0.28, 0.36), (w * 0.8, 0.22, 0.06))
    for sx in (-1, 1):
        g.sphere(P["burlap"], (sx * 0.7, 0.1, 0.45), 0.22, seg=6, ring=3, sqz=0.7)


def p_gate(g, P, w=1.8):
    g.box(P["wood_dark"], (-w * 0.5, 0, 0.85), (0.12, 0.12, 1.7))
    g.box(P["wood_dark"], (w * 0.5, 0, 0.85), (0.12, 0.12, 1.7))
    for i in range(4):
        g.box(P["wood"], (0, 0, 0.30 + i * 0.38), (w - 0.1, 0.06, 0.22))
    g.beam(P["wood"], (-w * 0.45, 0, 0.32), (w * 0.45, 0, 1.46), 0.07)
    g.band(P["iron"], (w * 0.32, 0.06, 1.02), 0.09, 0.04, seg=8,
           R=_rot3(rx=math.pi * 0.5))


def p_fence(g, P, L=4.0):
    n = max(2, int(L / 0.55))
    for k in range(n + 1):
        x = -L * 0.5 + k * L / n
        h = 1.05 + (0.10 if k % 3 == 0 else 0.0)
        g.box(P["wood_dark"], (x, 0, h * 0.5), (0.09, 0.09, h), R=_rot3(rz=0.0))
    for z in (0.42, 0.82):
        g.beam(P["wood_pale"], (-L * 0.5, 0, z), (L * 0.5, 0, z), 0.05)


def p_shrub(g, P, r=0.55):
    for i in range(3):
        a = i * 2.4
        g.sphere(P["veg"], (math.cos(a) * r * 0.35, math.sin(a) * r * 0.35,
                            r * 0.55), r * 0.7, seg=6, ring=3, sqz=0.85)


# ---------------------------------------------------------------------------
# vegetation
# ---------------------------------------------------------------------------
def p_tree(g, P, h=4.2, r=1.25, seed=0):
    """Yard tree: 6-gon trunk + a packed canopy mass (~120 quads).

    The canopy has to be one continuous mass: blobs spread on a ring with a
    gap under them read as a green totem on a stick from 30 m away.
    """
    rnd = _R(seed)
    g.cyl(P["wood_dark"], (0.0, 0.0, h * 0.40), 0.17, h * 0.80, seg=6, r2=0.10)
    g.sphere(P["leaf"], (0.0, 0.0, h * 0.66), r * 0.92, seg=8, ring=4, sqz=0.92)
    for i in range(5):
        a = TAU * i / 5.0 + rnd.uniform(-0.40, 0.40)
        d = r * rnd.uniform(0.26, 0.50)
        g.sphere(P["leaf_dark"] if i % 2 else P["leaf"],
                 (math.cos(a) * d, math.sin(a) * d,
                  h * (0.58 + rnd.uniform(-0.05, 0.10))),
                 r * rnd.uniform(0.46, 0.62), seg=6, ring=3, sqz=0.80)


def p_tree_bush(g, P, h=2.1, r=0.82, seed=0):
    rnd = _R(seed)
    g.cyl(P["wood_dark"], (0.0, 0.0, h * 0.28), 0.07, h * 0.56, seg=5, r2=0.05)
    for i in range(3):
        a = TAU * i / 3.0 + rnd.uniform(-0.30, 0.30)
        g.sphere(P["leaf"], (math.cos(a) * r * 0.28, math.sin(a) * r * 0.28,
                             h * (0.56 + rnd.uniform(-0.05, 0.08))),
                 r * rnd.uniform(0.60, 0.78), seg=6, ring=3, sqz=0.85)


def p_ivy(g, P, w=1.9, h=2.5, seed=0):
    """Wall patch.  Local +Y points INTO the wall, wall plane at y=WALL_Y."""
    rnd = _R(seed)
    g.beam(P["wood_dark"], (0.0, WALL_Y - 0.04, 0.0),
           (0.0, WALL_Y - 0.04, h * 0.95), 0.035)
    for i in range(7):
        x = rnd.uniform(-w * 0.46, w * 0.46)
        z = rnd.uniform(0.20, h)
        s = rnd.uniform(0.28, 0.54)
        g.panel(P["leaf_dark"] if i % 2 else P["leaf"],
                (x, WALL_Y - 0.07 - rnd.random() * 0.05, z),
                s, s * rnd.uniform(0.70, 1.15), sag=rnd.uniform(0.0, 0.06))


def p_vine(g, P, h=3.8, seed=0):
    rnd = _R(seed)
    for i in range(3):
        x = rnd.uniform(-0.42, 0.42)
        g.beam(P["wood_dark"], (x, WALL_Y - 0.05, 0.0),
               (x + rnd.uniform(-0.3, 0.3), WALL_Y - 0.05, h), 0.028)
    for i in range(6):
        g.sphere(P["leaf"], (rnd.uniform(-0.50, 0.50), WALL_Y - 0.12,
                             rnd.uniform(0.6, h)), rnd.uniform(0.16, 0.30),
                 seg=5, ring=2, sqz=1.25)


def p_shopawning(g, P, w=2.70, drop=1.45, cloth=None, seed=0):
    """Striped awning over a shop front.  Local +Y goes INTO the wall, so the
    cloth hangs out towards -Y; the origin sits WALL_Y off the facade."""
    rnd = _R(seed)
    cloth = cloth or P["awning_red"]
    zw, zo = 3.00, 2.24                     # wall edge higher than outer edge
    yw, yo = WALL_Y + 0.02, WALL_Y - drop
    n = 3
    for i in range(n):
        x0 = -w * 0.5 + w * i / n
        x1 = -w * 0.5 + w * (i + 1) / n
        xm = (x0 + x1) * 0.5
        zl = zo - 0.06 - 0.05 * (i % 2)     # sag in the middle of each strip
        g.quad(cloth, (x0, yw, zw), (x1, yw, zw), (xm, yo, zl),
               (x0, yo, zl + 0.02))
        g.quad(cloth, (x0, yo, zl + 0.02), (xm, yo, zl), (x1, yo, zl - 0.02),
               (x1, yo, zl))
    # valance: the scalloped front edge, which is what reads at 30 m
    for i in range(n * 2):
        x0 = -w * 0.5 + w * i / (n * 2)
        x1 = -w * 0.5 + w * (i + 1) / (n * 2)
        g.panel(cloth, ((x0 + x1) * 0.5, yo + 0.01, zo - 0.28), x1 - x0, 0.34,
                sag=0.03, seg=1)
    for sx in (-1, 1):
        g.beam(P["wood"], (sx * w * 0.46, yw, zw), (sx * w * 0.46, yo, zo),
               0.055)
        g.beam(P["wood"], (sx * w * 0.46, yw, zw - 0.75),
               (sx * w * 0.46, yo, zo - 0.12), 0.045)
    rnd.random()


def p_trellis(g, P, w=1.70, h=2.30, seed=0):
    """Lattice of thin slats against a wall with a climbing plant on it."""
    rnd = _R(seed)
    y = WALL_Y - 0.05
    for sx in (-1, 1):
        g.beam(P["wood_dark"], (sx * w * 0.5, y, 0.0), (sx * w * 0.5, y, h),
               0.055)
    k = 4
    for i in range(k):
        z = h * (i + 1) / (k + 1.0)
        g.beam(P["wood_dark"], (-w * 0.5, y, z), (w * 0.5, y, z), 0.040)
    for sx in (-1, 1):
        g.beam(P["wood_dark"], (sx * w * 0.5, y, 0.10),
               (-sx * w * 0.42, y, h - 0.15), 0.032)
    for i in range(5):
        g.sphere(P["leaf"], (rnd.uniform(-w * 0.44, w * 0.44),
                             y - 0.06, rnd.uniform(0.5, h)),
                 rnd.uniform(0.17, 0.30), seg=5, ring=2, sqz=1.15)


def p_sillbox(g, P, w=0.55, seed=0):
    """Window box, sits on a sill; local origin on the sill, +Y into the wall."""
    rnd = _R(seed)
    g.box(P["wood_dark"], (0.0, WALL_Y - 0.16, -0.05), (w, 0.30, 0.16))
    for i in range(3):
        x = (i - 1) * w * 0.30
        g.sphere((P["cloth_red"], P["cloth_ochre"], P["veg"])[i % 3],
                 (x, WALL_Y - 0.16, 0.06), 0.10, seg=5, ring=2, sqz=0.85)
    g.sphere(P["leaf"], (0.0, WALL_Y - 0.16, -0.01), w * 0.42, seg=5, ring=2,
             sqz=0.45)


def p_pots(g, P, n=3, seed=0):
    rnd = _R(seed)
    for i in range(n):
        x = (i - (n - 1) * 0.5) * 0.50 + rnd.uniform(-0.05, 0.05)
        s = rnd.uniform(0.82, 1.15)
        g.lathe(P["pottery"], (x, rnd.uniform(-0.06, 0.06), 0.0),
                [(0.14 * s, 0.0), (0.185 * s, 0.13 * s), (0.165 * s, 0.26 * s),
                 (0.195 * s, 0.29 * s)], seg=7)
        g.sphere(P["veg"], (x, 0.0, 0.41 * s), 0.185 * s, seg=6, ring=2, sqz=0.85)


def p_herbs(g, P, w=1.30, d=0.85, seed=0):
    rnd = _R(seed)
    g.box(P["wood_dark"], (0.0, 0.0, 0.09), (w, d, 0.18))
    g.box(P["earth"] if "earth" in P else P["burlap"], (0.0, 0.0, 0.16),
          (w - 0.10, d - 0.10, 0.06))
    for i in range(4):
        x = -w * 0.5 + w * (i + 0.5) / 4.0
        for j in range(2):
            y = -d * 0.25 + d * 0.5 * j
            g.sphere(P["veg"], (x + rnd.uniform(-0.05, 0.05), y, 0.27),
                     rnd.uniform(0.11, 0.16), seg=5, ring=2, sqz=0.95)


def p_hedge(g, P, L=1.8, h=1.10, seed=0):
    rnd = _R(seed)
    n = 4
    for i in range(n):
        x = -L * 0.5 + L * (i + 0.5) / n
        g.box(P["leaf_dark"], (x, 0.0, h * 0.5), (L / n + 0.06, 0.60, h),
              R=_rot3(rz=rnd.uniform(-0.06, 0.06)))
    for i in range(5):
        g.sphere(P["leaf"], (-L * 0.5 + L * (i + 0.5) / 5.0, 0.0, h),
                 0.30, seg=5, ring=2, sqz=0.55)


def p_weeds(g, P, r=0.55, seed=0):
    rnd = _R(seed)
    for i in range(5):
        a = rnd.uniform(0.0, TAU)
        d = rnd.uniform(0.05, r)
        s = rnd.uniform(0.55, 1.15)
        g.sphere(P["veg"], (math.cos(a) * d, math.sin(a) * d, 0.13 * s),
                 0.14 * s, seg=5, ring=2, sqz=1.45)


# ---------------------------------------------------------------------------
# plot boundaries (modular panels, placed in runs)
# ---------------------------------------------------------------------------
def p_wall_panel(g, P, L=1.8, seed=0):
    rnd = _R(seed)
    for r in range(3):
        z = 0.13 + r * 0.235
        n = 4 if r % 2 else 5
        for i in range(n):
            x = -L * 0.5 + (i + 0.5) * L / n + rnd.uniform(-0.03, 0.03)
            g.box(P["stone"], (x, 0.0, z),
                  (L / n * rnd.uniform(0.88, 1.03), 0.44 + rnd.uniform(-0.05, 0.05),
                   0.235 + rnd.uniform(-0.02, 0.03)))
    g.box(P["stone"], (0.0, 0.0, 0.79), (L, 0.47, 0.09))


def p_board_panel(g, P, L=1.8, h=1.30, seed=0):
    rnd = _R(seed)
    n = 6
    for i in range(n):
        x = -L * 0.5 + L * (i + 0.5) / n
        g.box(P["wood_pale"], (x, 0.0, h * 0.5 + rnd.uniform(-0.02, 0.02)),
              (L / n * 0.90, 0.055, h))
    for z in (0.32, 1.06):
        g.box(P["wood_dark"], (0.0, 0.055, z), (L, 0.05, 0.085))
    for sx in (-1, 1):
        g.box(P["wood_dark"], (sx * L * 0.5, 0.0, h * 0.5 + 0.05),
              (0.10, 0.11, h + 0.12))


def p_gate_leaf(g, P, L=1.7, h=1.55, seed=0):
    """A gate panel hinged at x=-L/2, swung open by `open` radians."""
    rnd = _R(seed)
    g.box(P["wood_dark"], (-L * 0.5, 0.0, h * 0.5), (0.09, 0.09, h))
    for i in range(4):
        z = 0.28 + i * 0.34
        g.box(P["wood_pale"], (-L * 0.25, 0.0, z), (L * 0.92, 0.05, 0.16))
    g.beam(P["wood_pale"], (-L * 0.92, 0.0, 0.26), (-L * 0.08, 0.0, h * 0.86), 0.07)


# ---------------------------------------------------------------------------
# street furniture
# ---------------------------------------------------------------------------
def p_mountblock(g, P):
    g.box(P["stone"], (0.0, 0.0, 0.17), (0.95, 0.72, 0.34))
    g.box(P["stone"], (0.0, 0.02, 0.45), (0.62, 0.50, 0.24))
    g.cyl(P["iron"], (0.42, -0.30, 0.72), 0.035, 0.95, seg=5)
    g.band(P["iron"], (0.42, -0.30, 0.86), 0.08, 0.028, seg=6,
           R=_rot3(rx=math.pi * 0.5))


def p_signpost(g, P, n=3):
    g.cyl(P["wood_dark"], (0.0, 0.0, 1.30), 0.075, 2.60, seg=6)
    for i in range(n):
        z = 2.48 - i * 0.33
        s = 1 if i % 2 == 0 else -1
        g.box(P["wood_pale"], (0.46 * s, 0.0, z), (0.72, 0.045, 0.19))
        g.box(P["wood_pale"], (0.80 * s, 0.0, z), (0.16, 0.045, 0.14),
              R=_rot3(rz=0.62 * s))


def p_notice(g, P, seed=0):
    rnd = _R(seed)
    for sx in (-1, 1):
        g.box(P["wood_dark"], (sx * 0.60, 0.0, 0.92), (0.10, 0.10, 1.84))
    g.box(P["wood_pale"], (0.0, 0.0, 1.40), (1.30, 0.06, 0.80))
    g.box(P["wood_pale"], (0.0, 0.0, 1.83), (1.46, 0.10, 0.09))
    for i in range(5):
        x = rnd.uniform(-0.50, 0.50)
        z = rnd.uniform(1.12, 1.68)
        g.box(P["cloth_cream"], (x, 0.05, z),
              (rnd.uniform(0.16, 0.26), 0.008, rnd.uniform(0.16, 0.26)),
              R=_rot3(ry=rnd.uniform(-0.12, 0.12)))


def p_shrine(g, P):
    g.box(P["stone"], (0.0, 0.0, 0.13), (0.92, 0.50, 0.26))
    for sx in (-1, 1):
        g.box(P["stone"], (sx * 0.36, 0.06, 0.62), (0.14, 0.36, 0.78))
    g.box(P["stone"], (0.0, WALL_Y - 0.08, 0.70), (0.80, 0.10, 0.96))
    g.quad(P["iron"], (-0.30, WALL_Y - 0.16, 0.36), (0.30, WALL_Y - 0.16, 0.36),
           (0.30, WALL_Y - 0.16, 1.04), (-0.30, WALL_Y - 0.16, 1.04))
    g.box(P["stone"], (0.0, 0.04, 1.20), (1.00, 0.58, 0.09))
    for sx in (-1, 1):
        g.box(P["stone"], (0.0, 0.04, 1.30), (1.00, 0.32, 0.06),
              R=_rot3(rx=0.34 * sx))
    for sx in (-1, 1):
        g.cyl(P["cloth_cream"], (sx * 0.16, 0.16, 0.34), 0.035, 0.16, seg=5)
        g.sphere(P["glow"], (sx * 0.16, 0.16, 0.44), 0.030, seg=4, ring=2)


def p_banner(g, P, span=6.0, z=4.60, cloth=None, seed=0):
    rnd = _R(seed)
    cloth = cloth if cloth is not None else P["cloth_red"]
    g.beam(P["wood_dark"], (-span * 0.5, 0.0, z), (span * 0.5, 0.0, z - 0.22), 0.032)
    w = min(1.35, span * 0.30)
    g.box(P["wood_dark"], (0.0, 0.0, z - 0.30), (w + 0.14, 0.05, 0.05))
    g.box(cloth, (0.0, 0.005, z - 0.30 - 0.60), (w, 0.022, 1.16))
    g.box(P["cloth_cream"], (0.0, 0.018, z - 0.72), (w * 0.44, 0.014, 0.26))


def p_stairs(g, P, h=2.40, w=1.05):
    """Steep wooden stair to an upper door; climbs toward +Y (wall at WALL_Y)."""
    n = max(4, int(round(h / 0.27)))
    run = 0.24
    for i in range(n):
        y = WALL_Y - 0.10 - (n - 0.5 - i) * run
        zt = (i + 1) * h / n
        g.box(P["wood_dark"], (0.0, y, zt * 0.5), (w, run + 0.02, zt))
    for sx in (-1, 1):
        g.beam(P["wood_dark"], (sx * (w * 0.5 + 0.04), WALL_Y - 0.12, h),
               (sx * (w * 0.5 + 0.04), WALL_Y - 0.12 - n * run, 0.10), 0.07)
        for k in (0.35, 0.72):
            g.beam(P["wood_dark"], (sx * (w * 0.5 + 0.02), WALL_Y - 0.10, h * k + 0.95),
                   (sx * (w * 0.5 + 0.02), WALL_Y - 0.10 - n * run * k, h * k + 0.95),
                   0.05)


def p_pigeons(g, P, n=4, seed=0):
    rnd = _R(seed)
    for i in range(n):
        a = rnd.uniform(0.0, TAU)
        d = rnd.uniform(0.04, 0.30)
        x, y = math.cos(a) * d, math.sin(a) * d
        s = rnd.uniform(0.85, 1.12)
        g.sphere(P["fish"], (x, y, 0.085 * s), 0.075 * s, seg=5, ring=2, sqz=1.10)
        g.sphere(P["fish"], (x + 0.06 * s, y, 0.155 * s), 0.045 * s, seg=4, ring=2)
        g.box(P["fish"], (x - 0.07 * s, y, 0.09 * s),
              (0.07 * s, 0.04 * s, 0.028 * s))


def p_dog(g, P, seed=0):
    body, dk, ns = P["burlap"], P["wood_dark"], P["skin"]
    rnd = _R(seed)
    g.box(body, (0.0, 0.0, 0.42), (0.60, 0.24, 0.26))
    for sx in (-1, 1):
        for sy in (-1, 1):
            g.box(dk, (sx * 0.20, sy * 0.08, 0.16), (0.09, 0.09, 0.32))
    g.box(body, (0.34, 0.0, 0.55), (0.21, 0.19, 0.19))
    g.box(ns, (0.45, 0.0, 0.50), (0.11, 0.10, 0.10))
    for sy in (-1, 1):
        g.box(dk, (0.34, sy * 0.07, 0.66), (0.07, 0.035, 0.08))
    g.beam(dk, (-0.30, 0.0, 0.46), (-0.46, 0.03, 0.62), 0.05)


def p_cat(g, P):
    g.box(P["wood_dark"], (0.0, 0.0, 0.14), (0.16, 0.17, 0.28))
    g.sphere(P["wood_dark"], (0.06, 0.0, 0.30), 0.078, seg=5, ring=2)
    g.beam(P["wood_dark"], (-0.06, 0.0, 0.03), (-0.27, 0.03, 0.15), 0.035)


def p_person(g, P, seed=0, cloak=False):
    """~1.75 m silhouette figure, <200 tris.

    At 30 m the figure is ~30 px tall, so what has to read is the *outline*:
    a dark skirt under a coloured coat, shoulders wider than the hips, and a
    brimmed hat on top.  A bare capsule reads as a post.
    """
    rnd = _R(seed)
    # Colour is what reads at 30 m: brown and cream on beige cobbles vanish, so
    # the coat palette is biased to the dyed cloths (blue / madder red / green).
    top = (P["cloth_blue"], P["cloth_red"], P["cloth_green"], P["cloth_blue"],
           P["cloth_red"], P["burlap"], P["cloth_green"])[seed % 7]
    legs = P["wood_dark"] if seed % 3 else P["paint"]
    for sx in (-1, 1):
        g.box(legs, (sx * 0.085, 0.0, 0.36), (0.130, 0.150, 0.72))
    # coat: wider at the hem than at the waist, so the silhouette flares
    g.lathe(top, (0.0, 0.0, 0.44),
            [(0.215, 0.0), (0.200, 0.22), (0.175, 0.46), (0.160, 0.62),
             (0.150, 0.74)],
            seg=7, caps=False)
    # shoulders + a chest slab: the shoulder line is what reads at distance
    g.box(top, (0.0, 0.0, 1.28), (0.375, 0.215, 0.30))
    for sx in (-1, 1):
        g.box(top, (sx * 0.195, 0.0, 1.16), (0.100, 0.145, 0.44),
              R=_rot3(ry=0.07 * sx))
        g.box(P["skin"], (sx * 0.205, 0.0, 0.92), (0.085, 0.115, 0.09))
    g.box(P["cloth_cream"], (0.0, 0.0, 1.44), (0.26, 0.19, 0.09))
    g.cyl(P["skin"], (0.0, 0.0, 1.49), 0.052, 0.08, seg=5)
    g.sphere(P["skin"], (0.0, 0.0, 1.615), 0.120, seg=6, ring=3, sqz=1.05)
    if cloak:
        g.panel(P["cloth_red"] if seed % 2 else P["cloth_green"],
                (0.0, -0.15, 1.10), 0.46, 0.98, sag=0.06)
    if seed % 3 != 2:
        # straw: the lightest thing on the street, so the figure gets a dot of
        # contrast against both the dark cobbles and the plaster walls
        g.cyl(P["straw"], (0.0, 0.0, 1.700), 0.265, 0.030, seg=8)
        g.cyl(P["straw"], (0.0, 0.0, 1.760), 0.120, 0.110, seg=7, r2=0.092)
    else:
        g.sphere(P["cloth_ochre"], (0.0, 0.0, 1.670), 0.135, seg=6, ring=2,
                 sqz=0.78)


def p_amphorae(g, P, n=4, seed=0):
    rnd = _R(seed)
    for i in range(n):
        x = (i - (n - 1) * 0.5) * 0.30 + rnd.uniform(-0.03, 0.03)
        y = rnd.uniform(-0.05, 0.05)
        h = rnd.uniform(0.60, 0.80)
        g.lathe(P["pottery"], (x, y, 0.0),
                [(0.09, 0.0), (0.150, h * 0.20), (0.160, h * 0.46),
                 (0.085, h * 0.78), (0.055, h)],
                seg=6)
        for sx in (-1, 1):
            g.beam(P["pottery"], (x + sx * 0.055, y, h * 0.82),
                   (x + sx * 0.145, y, h * 0.52), 0.032)


def p_barrow(g, P):
    g.box(P["wood_pale"], (0.0, 0.0, 0.54), (0.72, 0.45, 0.26), R=_rot3(rx=0.10))
    for sy in (-1, 1):
        g.beam(P["wood_dark"], (0.28, sy * 0.20, 0.62), (-0.56, sy * 0.16, 0.80),
               0.04)
        g.beam(P["wood_dark"], (0.24, sy * 0.18, 0.52), (0.24, sy * 0.18, 0.22),
               0.035)
    g.cyl(P["wood_dark"], (0.36, 0.0, 0.21), 0.19, 0.075, seg=10,
          R=_rot3(ry=math.pi * 0.5))
    g.band(P["iron"], (0.36, 0.0, 0.21), 0.195, 0.04, seg=10,
           R=_rot3(ry=math.pi * 0.5))


def p_crates3(g, P, seed=0):
    rnd = _R(seed)
    g.box(P["wood_pale"], (0.0, 0.0, 0.24), (0.60, 0.58, 0.47))
    g.box(P["wood_pale"], (0.02, 0.01, 0.63), (0.52, 0.50, 0.42),
          R=_rot3(rz=0.12))
    g.box(P["wood_pale"], (0.62, 0.04, 0.21), (0.46, 0.44, 0.42),
          R=_rot3(rz=-0.22))
    for (cx, cz, s) in ((0.30, 0.24, 0.005), (-0.30, 0.24, 0.005)):
        g.box(P["wood_dark"], (cx, 0.0, cz), (s, 0.60, 0.40))


def p_stoop(g, P):
    g.box(P["stone"], (0.0, 0.0, 0.09), (1.10, 0.44, 0.18))
    g.box(P["stone"], (0.0, 0.16, 0.24), (0.86, 0.30, 0.12))


def p_dovecote(g, P, h=2.95):
    g.box(P["wood_dark"], (0.0, 0.0, 0.36), (0.15, 0.15, 0.72))
    g.box(P["wood_pale"], (0.0, 0.0, h - 0.60), (0.78, 0.62, 1.16))
    for i in range(3):
        for j in range(2):
            g.box(P["iron"], (-0.24 + i * 0.24, 0.32, h - 0.92 + j * 0.34),
                  (0.11, 0.03, 0.11))
    for sy in (-1, 1):
        g.box(P["wood_dark"], (0.0, 0.0, h + 0.02), (0.95, 0.80, 0.07),
              R=_rot3(rx=0.30 * sy))


def p_beehives(g, P, n=3):
    g.box(P["wood_dark"], (0.0, 0.0, 0.20), (n * 0.46, 0.62, 0.40))
    for i in range(n):
        x = (i - (n - 1) * 0.5) * 0.46
        g.lathe(P["straw"], (x, 0.0, 0.40),
                [(0.195, 0.0), (0.215, 0.16), (0.185, 0.34),
                 (0.125, 0.46), (0.05, 0.52)], seg=7)


def p_grindstone(g, P):
    for sx in (-1, 1):
        g.box(P["wood_dark"], (sx * 0.28, 0.0, 0.31), (0.085, 0.30, 0.62))
    g.cyl(P["stone"], (0.0, 0.0, 0.66), 0.30, 0.17, seg=10,
          R=_rot3(ry=math.pi * 0.5))
    g.cyl(P["wood_dark"], (0.0, 0.0, 0.66), 0.035, 0.70, seg=5,
          R=_rot3(ry=math.pi * 0.5))
    g.beam(P["wood_dark"], (0.30, 0.0, 0.66), (0.36, 0.24, 0.50), 0.04)
    g.box(P["wood_dark"], (0.0, 0.0, 0.04), (0.86, 0.44, 0.08))


def p_rainbarrel(g, P, wall=3.60):
    p_barrel(g, P, 0.32, 0.90)
    g.box(P["wood_dark"], (0.0, 0.18, 0.93), (0.66, 0.50, 0.06))
    g.cyl(P["iron"], (0.0, WALL_Y - 0.14, (wall + 0.95) * 0.5), 0.05,
          wall - 0.95, seg=6)
    g.box(P["iron"], (0.0, WALL_Y - 0.14, wall), (1.30, 0.16, 0.14))
    g.beam(P["iron"], (0.0, WALL_Y - 0.14, wall - 0.04),
           (0.0, WALL_Y - 0.34, 0.98), 0.05)


def p_fountain(g, P, r=1.45):
    g.lathe(P["stone"], (0.0, 0.0, 0.0),
            [(r * 1.00, 0.0), (r * 1.02, 0.34), (r * 1.08, 0.44),
             (r * 0.96, 0.52)], seg=12, caps=False)
    g.lathe(P["stone"], (0.0, 0.0, 0.0), [(r * 0.92, 0.02), (r * 0.90, 0.42)],
            seg=12, caps=False)
    g.cyl(P["water"], (0.0, 0.0, 0.42), r * 0.92, 0.04, seg=12)
    g.lathe(P["stone"], (0.0, 0.0, 0.42),
            [(0.30, 0.0), (0.20, 0.50), (0.14, 0.80), (0.42, 0.92)],
            seg=10, caps=False)
    g.cyl(P["water"], (0.0, 0.0, 1.34), 0.40, 0.03, seg=10)
    g.cyl(P["stone"], (0.0, 0.0, 1.46), 0.07, 0.30, seg=6)


# ---------------------------------------------------------------------------
# yard furniture (added)
# ---------------------------------------------------------------------------
def p_woodpile_lean(g, P, seed=0):
    """Lean-to log stack against a wall."""
    rnd = _R(seed)
    for i in range(4):
        z = 0.16 + i * 0.28
        g.cyl(P["wood_dark"], (0.0, 0.0, z), 0.13, 1.90, seg=6,
              R=_rot3(ry=math.pi * 0.5, rz=rnd.uniform(-0.03, 0.03)))
    for sx in (-1, 1):
        g.box(P["wood_pale"], (sx * 0.86, 0.0, 0.60), (0.10, 0.62, 1.20))


def p_toolrack(g, P, seed=0):
    rnd = _R(seed)
    g.box(P["wood_dark"], (0.0, 0.0, 1.62), (1.70, 0.10, 0.10))
    for sx in (-1, 1):
        g.box(P["wood_dark"], (sx * 0.80, 0.0, 0.82), (0.10, 0.10, 1.62))
    for i in range(4):
        x = -0.60 + i * 0.40
        if i % 2:
            g.beam(P["wood_pale"], (x, 0.0, 1.56), (x, 0.0, 0.72), 0.045)
            g.box(P["iron"], (x, 0.02, 0.66), (0.16, 0.05, 0.14))
        else:
            g.beam(P["wood_pale"], (x, 0.0, 1.56), (x, 0.0, 0.86), 0.05)
            g.box(P["iron"], (x, 0.06, 0.78), (0.20, 0.12, 0.10),
                  R=_rot3(rx=0.5))


def _R(seed):
    import random
    return random.Random((seed * 2654435761) & 0x7FFFFFFF)


WALL_Y = 0.50


# ---------------------------------------------------------------------------
# proto cache
# ---------------------------------------------------------------------------
_P = {}
_PROTO = {}


def protos():
    """Every prop geometry, built once in local space."""
    if _PROTO:
        return _PROTO
    P = palette()
    G = _PROTO

    def mk(name, fn):
        g = Geo()
        fn(g, P)
        G[name] = to_proto(g)

    for r, h in ((0.25, 0.62), (0.30, 0.82), (0.36, 1.00)):
        mk("barrel_%d" % int(r * 100), lambda g, P, r=r, h=h: p_barrel(g, P, r, h))
    for s, h in ((0.46, 0.44), (0.60, 0.58), (0.76, 0.72)):
        mk("crate_%d" % int(s * 100), lambda g, P, s=s, h=h: p_crate(g, P, s, h))
    for n in (2, 3):
        mk("sacks_%d" % n, lambda g, P, n=n: p_sacks(g, P, n, seed=n))
    mk("hay", lambda g, P: p_hay(g, P))
    for k, nm in ((0, "bed_veg"), (1, "bed_straw"), (2, "bed_rubble")):
        mk(nm, lambda g, P, k=k: p_bed(g, P, kind=k, seed=k + 1))
    for k in (0, 1, 2):
        mk("yardpad_%d" % k, lambda g, P, k=k: p_yardpad(g, P, kind=k, seed=k + 3))
    mk("hay_stack", lambda g, P: p_haystack(g, P))
    mk("woodpile", lambda g, P: p_woodpile(g, P))
    mk("cart", lambda g, P: p_handcart(g, P))
    mk("wagon", lambda g, P: p_wagon(g, P))
    mk("pallet", lambda g, P: p_pallet(g, P))
    mk("pallet_bare", lambda g, P: p_pallet(g, P, cloth=False))
    for s in (0, 1, 2):
        mk("planks_%d" % s, lambda g, P, s=s: p_planks(g, P, seed=s))
    mk("bucket", lambda g, P: p_bucket(g, P))
    mk("yoke", lambda g, P: p_yoke(g, P))
    mk("trough", lambda g, P: p_trough(g, P))
    mk("hitch", lambda g, P: p_hitch(g, P))
    mk("bench", lambda g, P: p_bench(g, P))
    mk("stone_bench", lambda g, P: p_stone_bench(g, P))
    mk("well", lambda g, P: p_well(g, P))
    for s in (0, 1, 2):
        mk("sign_%d" % s, lambda g, P, s=s: p_sign(g, P, s))
    for s in (0, 1):
        mk("leaves_%d" % s, lambda g, P, s=s: p_leaves(g, P, s))
    mk("wheel", lambda g, P: p_wheel(g, P))
    mk("ladder", lambda g, P: p_ladder(g, P))
    mk("lantern", lambda g, P: p_lantern(g, P))
    for s in (0, 1):
        mk("laundry_%d" % s, lambda g, P, s=s: p_laundry(g, P, 5.0, 3.5, s))
    for s in (0, 1):
        mk("stall_%d" % s, lambda g, P, s=s: p_stall(g, P, 2.4, 1.6,
                                                    (P["awning_red"],
                                                     P["awning_ochre"])[s]))
    mk("stall_2", lambda g, P: p_stall(g, P, 2.9, 1.7, P["awning_blue"]))
    mk("rack", lambda g, P: p_rack(g, P))
    mk("shed", lambda g, P: p_shed(g, P))
    for s in (0, 1):
        mk("garden_%d" % s, lambda g, P, s=s: p_garden(g, P, 3.4, 2.6, s))
    mk("coop", lambda g, P: p_coop(g, P))
    mk("compost", lambda g, P: p_compost(g, P))
    mk("waterbutt", lambda g, P: p_waterbutt(g, P))
    mk("stonepile", lambda g, P: p_stonepile(g, P))
    mk("pigpen", lambda g, P: p_pigpen(g, P))
    mk("gate", lambda g, P: p_gate(g, P))
    mk("fence", lambda g, P: p_fence(g, P))
    mk("shrub", lambda g, P: p_shrub(g, P))

    # --- vegetation --------------------------------------------------------
    for s, (h, r) in enumerate(((4.4, 1.30), (3.4, 1.05), (5.8, 1.55))):
        mk("tree_%d" % s, lambda g, P, h=h, r=r, s=s: p_tree(g, P, h, r, s + 17))
    for s, (h, r) in enumerate(((2.1, 0.82), (2.7, 0.98))):
        mk("treebus_%d" % s,
           lambda g, P, h=h, r=r, s=s: p_tree_bush(g, P, h, r, s + 5))
    for s in (0, 1):
        mk("ivy_%d" % s, lambda g, P, s=s: p_ivy(g, P, 1.9 + 0.5 * s,
                                                  2.5 + 0.8 * s, s + 3))
    mk("vine", lambda g, P: p_vine(g, P, 3.8, 4))
    mk("shopawning_0", lambda g, P: p_shopawning(g, P, 2.70, 1.45,
                                                 P["awning_red"], 1))
    mk("shopawning_1", lambda g, P: p_shopawning(g, P, 3.10, 1.60,
                                                 P["awning_ochre"], 2))
    mk("shopawning_2", lambda g, P: p_shopawning(g, P, 2.30, 1.30,
                                                 P["cloth_cream"], 3))
    mk("trellis", lambda g, P: p_trellis(g, P, 1.70, 2.30, 5))
    mk("sillbox", lambda g, P: p_sillbox(g, P, 0.55, 1))
    for n in (2, 3):
        mk("pots_%d" % n, lambda g, P, n=n: p_pots(g, P, n, n + 8))
    mk("herbs", lambda g, P: p_herbs(g, P))
    for L, h in ((1.5, 0.95), (2.2, 1.20)):
        mk("hedge_%d" % int(L * 100),
           lambda g, P, L=L, h=h: p_hedge(g, P, L, h, int(L * 10)))
    for r in (0.55, 0.85):
        mk("weeds_%d" % int(r * 100),
           lambda g, P, r=r: p_weeds(g, P, r, int(r * 100)))
    # --- boundaries (modular panels) ---------------------------------------
    mk("wall_panel", lambda g, P: p_wall_panel(g, P, 1.8, 2))
    mk("board_panel", lambda g, P: p_board_panel(g, P, 1.8, 1.30, 5))
    mk("board_panel_lo", lambda g, P: p_board_panel(g, P, 1.8, 0.95, 6))
    mk("gate_leaf", lambda g, P: p_gate_leaf(g, P, 1.7, 1.55, 7))
    # --- street furniture --------------------------------------------------
    mk("mountblock", lambda g, P: p_mountblock(g, P))
    mk("signpost_2", lambda g, P: p_signpost(g, P, 2))
    mk("signpost_3", lambda g, P: p_signpost(g, P, 3))
    mk("notice", lambda g, P: p_notice(g, P, 11))
    mk("shrine", lambda g, P: p_shrine(g, P))
    for span in (5.0, 6.5, 8.0, 9.5):
        for s in (0, 1):
            mk("banner_%d%d" % (int(span * 10), s),
               lambda g, P, span=span, s=s: p_banner(
                   g, P, span, 4.60 + 0.35 * s,
                   (P["cloth_red"], P["cloth_blue"])[s], s * 3 + int(span)))
    mk("stairs", lambda g, P: p_stairs(g, P, 2.40, 1.05))
    for n in (3, 4):
        mk("pigeons_%d" % n, lambda g, P, n=n: p_pigeons(g, P, n, n + 2))
    mk("dog", lambda g, P: p_dog(g, P, 3))
    mk("cat", lambda g, P: p_cat(g, P))
    for s in (0, 1, 2, 3, 4, 5):
        mk("person_%d" % s, lambda g, P, s=s: p_person(g, P, s, cloak=(s % 2 == 0)))
    for n in (3, 4):
        mk("amphorae_%d" % n, lambda g, P, n=n: p_amphorae(g, P, n, n + 9))
    mk("barrow", lambda g, P: p_barrow(g, P))
    mk("crates3", lambda g, P: p_crates3(g, P, 13))
    mk("stoop", lambda g, P: p_stoop(g, P))
    mk("dovecote", lambda g, P: p_dovecote(g, P, 2.95))
    for n in (2, 3):
        mk("beehives_%d" % n, lambda g, P, n=n: p_beehives(g, P, n))
    mk("grindstone", lambda g, P: p_grindstone(g, P))
    mk("rainbarrel", lambda g, P: p_rainbarrel(g, P, 3.60))
    mk("fountain", lambda g, P: p_fountain(g, P, 1.45))
    mk("woodpile_lean", lambda g, P: p_woodpile_lean(g, P, 21))
    mk("toolrack", lambda g, P: p_toolrack(g, P, 23))
    return G


# ===========================================================================
# spatial tests
# ===========================================================================
def _quad_area(q):
    a = 0.0
    n = len(q)
    for i in range(n):
        x1, y1 = q[i]
        x2, y2 = q[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) * 0.5


def _in_poly(x, y, poly):
    c = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[j]
        if (y1 > y) != (y2 > y):
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                c = not c
        j = i
    return c


def _seg_dist(x, y, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return math.hypot(x - x1, y - y1)
    t = ((x - x1) * dx + (y - y1) * dy) / L2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(x - (x1 + dx * t), y - (y1 + dy * t))


def _poly_margin(x, y, poly):
    """Distance from a point to the polygon outline (positive inside)."""
    if not _in_poly(x, y, poly):
        return -1.0
    n = len(poly)
    return min(_seg_dist(x, y, poly[i][0], poly[i][1],
                         poly[(i + 1) % n][0], poly[(i + 1) % n][1])
               for i in range(n))


def _in_quad_pad(x, y, q, pad=0.0):
    """Inside a convex quad, at least `pad` from every edge."""
    n = len(q)
    if n < 3:
        return False
    sign = 0
    for i in range(n):
        x1, y1 = q[i]
        x2, y2 = q[(i + 1) % n]
        c = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if c > 1e-9:
            s = 1
        elif c < -1e-9:
            s = -1
        else:
            continue
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    if pad <= 0.0:
        return True
    for i in range(n):
        x1, y1 = q[i]
        x2, y2 = q[(i + 1) % n]
        if _seg_dist(x, y, x1, y1, x2, y2) < pad:
            return False
    return True


class UnitGrid(object):
    """Cheap 'is this spot inside (or too near) a building' index."""

    def __init__(self, units, cell=4.0):
        self.cell = cell
        self.g = {}
        for k, u in enumerate(units):
            q = u.get("quad") or ()
            if len(q) < 3:
                continue
            xs = [p[0] for p in q]
            ys = [p[1] for p in q]
            self._insert(k, min(xs) - 2.0, min(ys) - 2.0, max(xs) + 2.0,
                         max(ys) + 2.0)
        self.units = units

    def _insert(self, k, x0, y0, x1, y1):
        c = self.cell
        for ix in range(int(math.floor(x0 / c)), int(math.floor(x1 / c)) + 1):
            for iy in range(int(math.floor(y0 / c)), int(math.floor(y1 / c)) + 1):
                self.g.setdefault((ix, iy), []).append(k)

    def hit(self, x, y, pad=0.3):
        c = self.cell
        for k in self.g.get((int(math.floor(x / c)), int(math.floor(y / c))), ()):
            if _in_quad_pad(x, y, self.units[k]["quad"], pad):
                return True
        return False

    def near(self, x, y, rad):
        """Any building within `rad` of the point (approximate, cell based)."""
        c = self.cell
        r = int(math.ceil(rad / c))
        ix, iy = int(math.floor(x / c)), int(math.floor(y / c))
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for k in self.g.get((ix + dx, iy + dy), ()):
                    q = self.units[k]["quad"]
                    if _in_quad_pad(x, y, q, -rad * 0.0):
                        return True
                    n = len(q)
                    for i in range(n):
                        if _seg_dist(x, y, q[i][0], q[i][1],
                                     q[i + 1][0] if i + 1 < n else q[0][0],
                                     q[i + 1][1] if i + 1 < n else q[0][1]) < rad:
                            return True
        return False


class SegGrid(object):
    """Street centre lines in a bucket grid, for junction / crossing tests."""

    def __init__(self, streets, cell=10.0, chains=None):
        self.cell = cell
        self.g = {}
        self.segs = []
        for si, s in enumerate(streets):
            for chain in _chains(s):
                for i in range(len(chain) - 1):
                    x1, y1 = chain[i]
                    x2, y2 = chain[i + 1]
                    k = len(self.segs)
                    self.segs.append((x1, y1, x2, y2, float(s.get("w") or 6.0) * 0.5,
                                      si))
                    self._insert(k, min(x1, x2) - 3.0, min(y1, y2) - 3.0,
                                 max(x1, x2) + 3.0, max(y1, y2) + 3.0)

    def _insert(self, k, x0, y0, x1, y1):
        c = self.cell
        for ix in range(int(math.floor(x0 / c)), int(math.floor(x1 / c)) + 1):
            for iy in range(int(math.floor(y0 / c)), int(math.floor(y1 / c)) + 1):
                self.g.setdefault((ix, iy), []).append(k)

    def far_from_other(self, x, y, sid, clear=2.2):
        c = self.cell
        best = 1e9
        for k in self.g.get((int(math.floor(x / c)), int(math.floor(y / c))), ()):
            x1, y1, x2, y2, half, osid = self.segs[k]
            if osid == sid:
                continue
            d = _seg_dist(x, y, x1, y1, x2, y2) - half
            if d < best:
                best = d
        return best > clear


def _chains_street(street, tol=0.75):
    try:
        import hd_street as HS
        return HS._chains(street, tol)
    except Exception:                                     # pragma: no cover
        segs = []
        for seg in (street.get("segs") or ()):
            try:
                if isinstance(seg[0], (list, tuple)):
                    pts = [(float(p[0]), float(p[1])) for p in seg]
                else:
                    pts = [(float(seg[0]), float(seg[1])),
                           (float(seg[2]), float(seg[3]))]
            except (TypeError, IndexError, ValueError):
                continue
            for i in range(len(pts) - 1):
                if math.hypot(pts[i + 1][0] - pts[i][0],
                              pts[i + 1][1] - pts[i][1]) > 0.05:
                    segs.append((pts[i], pts[i + 1]))
        if not segs:
            a, b = street.get("a"), street.get("b")
            if a and b:
                segs.append(((float(a[0]), float(a[1])),
                             (float(b[0]), float(b[1]))))
        runs = []
        while segs:
            run = list(segs.pop(0))
            grew = True
            while grew:
                grew = False
                ex, ey = run[-1]
                sx, sy = run[0]
                for i, (p, q) in enumerate(segs):
                    if math.hypot(q[0] - ex, q[1] - ey) <= tol:
                        run.append(p)
                    elif math.hypot(p[0] - ex, p[1] - ey) <= tol:
                        run.append(q)
                    elif math.hypot(q[0] - sx, q[1] - sy) <= tol:
                        run.insert(0, p)
                    elif math.hypot(p[0] - sx, p[1] - sy) <= tol:
                        run.insert(0, q)
                    else:
                        continue
                    segs.pop(i)
                    grew = True
                    break
            if len(run) >= 2:
                runs.append(run)
        return runs


def _chains(street, tol=0.75):
    fn = _CHAIN_FN[0]
    if fn is None:
        fn = _CHAIN_FN[0] = _chains_street
    return fn(street, tol)


_CHAIN_FN = [None]


# ===========================================================================
# spot generation: streets
# ===========================================================================
SPACING = {"alley": 3.0, "secondary": 4.1, "main": 5.6}
Z_STREET = 0.026
Z_YARD = 0.100


def street_spots(streets, ugrid, rng):
    """Dense candidates along both kerbs, never inside the walkable middle."""
    grid = SegGrid(streets)
    ends = []
    for si, s in enumerate(streets):
        for chain in _chains(s):
            ends.append((chain[0][0], chain[0][1], si))
            ends.append((chain[-1][0], chain[-1][1], si))
    endcell = {}
    for (x, y, si) in ends:
        endcell.setdefault((int(x // 12.0), int(y // 12.0)), []).append((x, y, si))
    out = []
    for si, s in enumerate(streets):
        w = float(s.get("w") or 6.0)
        kind = s.get("kind") or "secondary"
        h = w * 0.5
        inner = max(0.275 * w, h - 1.25)
        facade = h + 0.75
        sp = SPACING.get(kind, 4.0)
        for chain in _chains(s):
            # cumulative length + direction per segment
            acc = [0.0]
            for i in range(len(chain) - 1):
                acc.append(acc[-1] + math.hypot(chain[i + 1][0] - chain[i][0],
                                                chain[i + 1][1] - chain[i][1]))
            L = acc[-1]
            if L < 1.0:
                continue
            t = rng.uniform(0.3, 1.0) * sp
            side = 1 if rng.random() < 0.5 else -1
            while t < L - 0.7:
                # locate the segment
                lo, hi = 0, len(acc) - 1
                while lo < hi - 1:
                    mid = (lo + hi) // 2
                    if acc[mid] <= t:
                        lo = mid
                    else:
                        hi = mid
                x1, y1 = chain[lo]
                x2, y2 = chain[lo + 1]
                seg = acc[lo + 1] - acc[lo]
                f = 0.0 if seg < 1e-9 else (t - acc[lo]) / seg
                ax = (x2 - x1) / seg if seg > 1e-9 else 1.0
                ay = (y2 - y1) / seg if seg > 1e-9 else 0.0
                px = x1 + (x2 - x1) * f
                py = y1 + (y2 - y1) * f
                nx, ny = -ay * side, ax * side
                tx, ty = px + nx * (h * 0.85), py + ny * (h * 0.85)
                ok = grid.far_from_other(tx, ty, si, 2.3)
                if ok:
                    ex, ey = int(tx // 12.0), int(ty // 12.0)
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            for (qx, qy, qsid) in endcell.get((ex + dx, ey + dy), ()):
                                if qsid != si and math.hypot(qx - tx, qy - ty) < 5.6:
                                    ok = False
                                    break
                            if not ok:
                                break
                        if not ok:
                            break
                if ok and ugrid is not None and ugrid.hit(px + nx * facade, py + ny * facade, 0.10):
                    ok = False
                if ok:
                    out.append(dict(cat="street", x=px, y=py, ax=ax, ay=ay,
                                    nx=nx, ny=ny, h=h, w=w, inner=inner,
                                    facade=facade, kind=kind, sid=si,
                                    z=Z_STREET,
                                    yaw_face=math.atan2(nx, -ny),
                                    yaw_along=math.atan2(ay, ax),
                                    yaw_across=math.atan2(ny, nx)))
                side = -side
                t += sp * rng.uniform(0.72, 1.32)
    return out


# ===========================================================================
# spot generation: yards (block interiors)
# ===========================================================================
YARD_ClUSTERS = {
    "residential": (("garden", 2.8), ("laundry_yard", 2.4), ("coop", 1.5),
                    ("shed", 2.2), ("butt", 1.0), ("rack", 1.7), ("compost", 1.3),
                    ("stonepile", 1.1), ("fence_gate", 3.2), ("bench_y", 1.1),
                    ("pallets", 1.5), ("planks", 1.6)),
    "craft": (("woodpile_y", 1.5), ("planks", 1.7), ("crates_y", 1.4),
              ("shed", 2.2), ("stonepile", 1.3), ("barrels_y", 1.4),
              ("rack", 1.7), ("butt", 1.0), ("cart_y", 1.8)),
    "artisan": (("woodpile_y", 1.5), ("stonepile", 1.3), ("planks", 1.6),
                ("shed", 2.2), ("barrels_y", 1.3), ("compost", 1.2)),
    "dock": (("crates_y", 1.5), ("barrels_y", 1.5), ("pallets", 1.7),
             ("cart_y", 1.8), ("rack", 1.8), ("coop", 1.5), ("butt", 1.0)),
    "outer": (("haystack_y", 1.5), ("pigpen", 2.2), ("garden", 2.8),
              ("coop", 1.5), ("woodpile_y", 1.5), ("cart_y", 1.8),
              ("laundry_yard", 2.4), ("compost", 1.3)),
    "guild": (("bench_y", 1.0), ("shrub_y", 0.9), ("butt", 0.9),
              ("stonepile", 1.0), ("rack", 1.6)),
    "temple": (("bench_y", 1.0), ("shrub_y", 1.0), ("butt", 0.9),
               ("stonepile", 1.1)),
    "palace": (("bench_y", 1.0), ("shrub_y", 1.0), ("stonepile", 1.1)),
}


def yard_spots(units, blocks, ugrid, rng, dens=1.0):
    by_block = {}
    for u in units:
        by_block.setdefault(u.get("block"), []).append(u)
    out = []
    for b in blocks:
        poly = b.get("poly") or ()
        role = b.get("role") or "residential"
        if len(poly) < 3 or role in ("square", "plaza"):
            continue
        area = float(b.get("area") or 0.0)
        us = by_block.get(b.get("id"), ())
        built = sum(_quad_area(u["quad"]) for u in us if u.get("quad"))
        free = area - built
        if free < 90.0:
            continue
        mix = YARD_ClUSTERS.get(role) or YARD_ClUSTERS["residential"]
        need = max(1, int(min(20, free / 27.0) * dens))
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        taken = {}
        got = 0
        tries = 0
        while got < need and tries < need * 14:
            tries += 1
            kind, rad = mix[rng.randrange(len(mix))]
            x = rng.uniform(x0, x1)
            y = rng.uniform(y0, y1)
            if _poly_margin(x, y, poly) < 1.35:
                continue
            # cluster footprint: centre + ring
            if ugrid.hit(x, y, 0.85):
                continue
            ok = True
            for k in range(8):
                a = TAU * k / 8.0
                qx = x + math.cos(a) * rad
                qy = y + math.sin(a) * rad
                if _poly_margin(qx, qy, poly) < 0.9 or ugrid.hit(qx, qy, 0.30):
                    ok = False
                    break
            if not ok:
                continue
            cx, cy = int(x // 1.5), int(y // 1.5)
            if any((cx + dx, cy + dy) in taken for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                continue
            taken[(cx, cy)] = 1
            got += 1
            out.append(dict(cat="yard", x=x, y=y, r=rad, role=role, z=Z_YARD,
                            block=b.get("id"),
                            yaw=rng.uniform(0, TAU)))
    return out


# ===========================================================================
# spot generation: market squares
# ===========================================================================
def _landmarks():
    try:
        import json
        import os
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layout.json")
        with open(p, "r", encoding="utf-8") as f:
            return [l for l in (json.load(f).get("landmarks") or ())
                    if l.get("plot")]
    except Exception:                                     # pragma: no cover
        return []


_LM = []


def _lm_clear(x, y, pad=2.0):
    if not _LM:
        _LM.extend(_landmarks())
    for l in _LM:
        if _in_poly(x, y, l["plot"]) or _poly_margin(x, y, l["plot"]) > -pad:
            return False
    return True


def market_spots(blocks, ugrid, rng, dens=1.0):
    """Rows of stalls on the paved squares, aisles left between them."""
    out = []
    for b in blocks:
        role = b.get("role") or ""
        poly = b.get("poly") or ()
        if role not in ("square", "plaza") or len(poly) < 3:
            continue
        # local frame from the longest edge
        best = (0.0, 1.0, 0.0)
        for i in range(len(poly)):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % len(poly)]
            L = math.hypot(x2 - x1, y2 - y1)
            if L > best[0]:
                best = (L, (x2 - x1) / L, (y2 - y1) / L)
        _, ux, uy = best
        vx, vy = -uy, ux
        cu = sum((p[0] * ux + p[1] * uy) for p in poly) / len(poly)
        cv = sum((p[0] * vx + p[1] * vy) for p in poly) / len(poly)
        us = [p[0] * ux + p[1] * uy for p in poly]
        vs = [p[0] * vx + p[1] * vy for p in poly]
        # rows across the square, stalls spaced along the row with aisles
        rows = 0
        v = min(vs) + 3.0
        while v < max(vs) - 3.0:
            u = min(us) + 3.0
            col = 0
            while u < max(us) - 3.0:
                x = cu * 0 + u * ux + v * vx
                y = u * uy + v * vy
                if (_poly_margin(x, y, poly) > 2.6 and not ugrid.hit(x, y, 1.2)
                        and _lm_clear(x, y, 3.0)):
                    if (col % 4 == 3):
                        pass                              # aisle
                    else:
                        out.append(dict(cat="market", x=x, y=y, z=Z_YARD,
                                        yaw=math.atan2(vx, vy), block=b.get("id"),
                                        sq=role, u=u, v=v, row=rows))
                u += 2.9
                col += 1
            v += 4.2
            rows += 1
    return out


# ===========================================================================
# street occupancy raster (O(1) "am I standing in the road" test)
# ===========================================================================
class StreetRaster(object):
    """2 m raster of every street corridor.  0 = open ground, 1 = in the road,
    2 = within `margin` of the road.  Querying is a single list index, which
    matters: the build issues ~100k of these."""

    def __init__(self, streets, res=2.0, margin=5.0):
        self.res = res
        segs = []
        x0 = y0 = 1e9
        x1 = y1 = -1e9
        for s in streets:
            half = float(s.get("w") or 6.0) * 0.5
            for ch in _chains(s):
                for i in range(len(ch) - 1):
                    (ax, ay), (bx, by) = ch[i], ch[i + 1]
                    segs.append((ax, ay, bx, by, half))
                    x0 = min(x0, ax, bx)
                    x1 = max(x1, ax, bx)
                    y0 = min(y0, ay, by)
                    y1 = max(y1, ay, by)
        pad = margin + 12.0
        self.x0 = x0 - pad
        self.y0 = y0 - pad
        self.w = max(1, int((x1 - x0 + 2.0 * pad) / res) + 1)
        self.h = max(1, int((y1 - y0 + 2.0 * pad) / res) + 1)
        self.a = bytearray(self.w * self.h)
        for (ax, ay, bx, by, half) in segs:
            self._stamp(ax, ay, bx, by, half + margin, 2)
            self._stamp(ax, ay, bx, by, half - 0.20, 1)

    def _stamp(self, ax, ay, bx, by, r, val):
        if r <= 0.0:
            return
        res = self.res
        ia = int((min(ax, bx) - r - self.x0) / res) - 1
        ib = int((max(ax, bx) + r - self.x0) / res) + 2
        ja = int((min(ay, by) - r - self.y0) / res) - 1
        jb = int((max(ay, by) + r - self.y0) / res) + 2
        ia, ja = max(0, ia), max(0, ja)
        ib, jb = min(self.w, ib), min(self.h, jb)
        w = self.w
        for ix in range(ia, ib):
            cx = self.x0 + (ix + 0.5) * res
            for iy in range(ja, jb):
                cy = self.y0 + (iy + 0.5) * res
                if _seg_dist(cx, cy, ax, ay, bx, by) <= r:
                    self.a[iy * w + ix] = val

    def clear(self, x, y):
        """99 = open ground, 2 = road shoulder, -1 = in the carriageway."""
        ix = int((x - self.x0) / self.res)
        iy = int((y - self.y0) / self.res)
        if ix < 0 or iy < 0 or ix >= self.w or iy >= self.h:
            return 99.0
        v = self.a[iy * self.w + ix]
        return -1.0 if v == 1 else (2.0 if v == 2 else 99.0)


# ===========================================================================
# prop catalogue: collision radius (m) and alignment rule
# ===========================================================================
# alignment: "along" = local +X along the kerb/wall, "face" = local +Y away
# from the wall, "wall" = local +Y into the wall (ivy, downpipes, stairs).
RAD = {
    "barrel_25": 0.26, "barrel_30": 0.30, "barrel_36": 0.36,
    "crate_46": 0.30, "crate_60": 0.36, "crate_76": 0.42, "crates3": 0.58,
    "sacks_2": 0.34, "sacks_3": 0.44, "hay": 0.48, "hay_stack": 0.85,
    "bed_veg": 0.60, "bed_straw": 0.60, "bed_rubble": 0.55,
    "yardpad_0": 0.30, "yardpad_1": 0.30, "yardpad_2": 0.30,
    "woodpile": 0.55, "woodpile_lean": 0.75, "cart": 0.75, "wagon": 0.95,
    "pallet": 0.45, "pallet_bare": 0.45, "planks_0": 0.55, "planks_1": 0.55,
    "planks_2": 0.55, "bucket": 0.20, "yoke": 0.45, "trough": 0.65,
    "hitch": 0.45, "bench": 0.55, "stone_bench": 0.60, "well": 0.85,
    "sign_0": 0.30, "sign_1": 0.30, "sign_2": 0.30, "leaves_0": 0.55,
    "leaves_1": 0.55, "wheel": 0.32, "ladder": 0.35, "lantern": 0.20,
    "laundry_0": 0.30, "laundry_1": 0.30, "stall_0": 0.95, "stall_1": 0.95,
    "stall_2": 1.10,
    "rack": 0.55, "shed": 1.05, "garden_0": 1.35, "garden_1": 1.35,
    "coop": 0.70, "compost": 0.60, "waterbutt": 0.35, "stonepile": 0.50,
    "pigpen": 1.10, "gate": 0.60, "fence": 0.45, "shrub": 0.42,
    "tree_0": 0.55, "tree_1": 0.45, "tree_2": 0.60, "treebus_0": 0.40,
    "treebus_1": 0.45, "ivy_0": 0.40, "ivy_1": 0.45, "vine": 0.35,
    "sillbox": 0.25, "pots_2": 0.36, "pots_3": 0.50, "herbs": 0.55,
    "hedge_150": 0.55, "hedge_220": 0.75, "weeds_55": 0.30,
    "weeds_85": 0.40, "wall_panel": 0.30, "board_panel": 0.30,
    "board_panel_lo": 0.30, "gate_leaf": 0.45, "mountblock": 0.55,
    "signpost_2": 0.30, "signpost_3": 0.30, "notice": 0.70, "shrine": 0.40,
    "stairs": 0.60, "pigeons_3": 0.30, "pigeons_4": 0.35, "dog": 0.35,
    "cat": 0.20, "amphorae_3": 0.42, "amphorae_4": 0.52, "barrow": 0.48,
    "stoop": 0.55, "dovecote": 0.45, "beehives_2": 0.55, "beehives_3": 0.75,
    "grindstone": 0.50, "rainbarrel": 0.45, "fountain": 1.60,
    "toolrack": 0.60, "banner_500": 0.30, "banner_501": 0.30,
    "banner_650": 0.30, "banner_651": 0.30, "banner_800": 0.30,
    "banner_801": 0.30, "banner_950": 0.30, "banner_951": 0.30,
    "shopawning_0": 0.55, "shopawning_1": 0.60, "shopawning_2": 0.50,
    "trellis": 0.40,
}
for _s in range(6):
    RAD["person_%d" % _s] = 0.24

WALL_ATTACHED = frozenset(("ivy_0", "ivy_1", "vine", "rainbarrel", "stairs",
                           "shrine", "sillbox", "shopawning_0",
                           "shopawning_1", "shopawning_2", "trellis"))

# kerb mixes ---------------------------------------------------------------
STREET_MIX = {
    "main": (("barrel_36", 2.0), ("barrel_30", 1.6), ("crate_60", 1.8),
             ("crate_76", 1.3), ("crates3", 1.0), ("sacks_2", 1.4),
             ("sacks_3", 0.9), ("amphorae_4", 1.0), ("stall_0", 2.8),
             ("stall_1", 2.4), ("stall_2", 2.0), ("cart", 2.2), ("wagon", 0.7),
             ("bench", 1.1), ("hitch", 1.1), ("lantern", 1.5),
             ("trough", 0.8), ("mountblock", 0.7), ("notice", 0.6),
             ("sign_0", 0.5), ("sign_1", 0.5), ("sign_2", 0.5),
             ("stoop", 0.7), ("pots_3", 1.1), ("pots_2", 0.8),
             ("barrow", 0.9), ("hay", 1.4), ("pigeons_4", 0.8),
             ("pigeons_3", 0.6), ("dog", 0.4), ("cat", 0.35),
             ("treebus_0", 1.0), ("treebus_1", 0.7), ("weeds_85", 0.2),
             ("pallet_bare", 0.3), ("wheel", 0.4), ("ladder", 0.9),
             ("leaves_0", 0.2), ("leaves_1", 0.15), ("barrel_25", 0.9),
             ("crate_46", 0.7), ("signpost_2", 0.35), ("well", 0.10),
             ("fountain", 0.04)),
    "secondary": (("barrel_30", 2.2), ("barrel_36", 1.5), ("barrel_25", 1.2),
                  ("crate_60", 1.9), ("crate_46", 1.4), ("crates3", 0.9),
                  ("sacks_2", 1.8), ("sacks_3", 1.0), ("amphorae_3", 0.8),
                  ("amphorae_4", 0.5), ("stall_0", 1.5), ("stall_1", 1.3),
                  ("stall_2", 1.2),
                  ("cart", 1.3), ("bench", 1.2), ("hitch", 1.2),
                  ("lantern", 1.6), ("trough", 1.0), ("mountblock", 0.7),
                  ("sign_0", 0.7), ("sign_1", 0.7), ("sign_2", 0.6),
                  ("stoop", 0.7), ("pots_2", 0.9), ("pots_3", 0.9),
                  ("barrow", 1.0), ("hay", 1.4), ("pigeons_3", 0.9),
                  ("pigeons_4", 0.7), ("dog", 0.5), ("cat", 0.45),
                  ("treebus_0", 1.2), ("treebus_1", 0.9), ("weeds_85", 0.25),
                  ("weeds_55", 0.15), ("pallet_bare", 0.4), ("wheel", 0.5),
                  ("leaves_0", 0.3), ("leaves_1", 0.2), ("bucket", 0.4),
                  ("ladder", 0.9), ("planks_0", 0.5), ("woodpile", 0.8),
                  ("signpost_2", 0.4), ("well", 0.06), ("toolrack", 0.3),
                  ("wagon", 0.5), ("shed", 0.25)),
    "alley": (("barrel_25", 2.2), ("barrel_30", 1.4), ("crate_46", 1.8),
              ("crate_60", 1.1), ("sacks_2", 1.6), ("pots_2", 1.2),
              ("bucket", 0.5), ("pallet_bare", 0.5), ("planks_0", 0.5),
              ("woodpile", 1.1), ("woodpile_lean", 0.9), ("leaves_0", 0.3),
              ("leaves_1", 0.25), ("weeds_55", 0.35), ("weeds_85", 0.3),
              ("cat", 0.6), ("pigeons_3", 0.7), ("treebus_0", 0.9),
              ("bench", 0.7), ("barrow", 0.6), ("wheel", 0.5), ("hitch", 0.5),
              ("lantern", 0.8), ("trough", 0.4), ("amphorae_3", 0.6),
              ("crates3", 0.5), ("stoop", 0.5), ("ladder", 0.8),
              ("toolrack", 0.3), ("compost", 0.4), ("stonepile", 0.4),
              ("waterbutt", 0.9), ("hay", 0.6), ("cart", 0.5),
              ("coop", 0.35), ("shed", 0.3)),
}

# block-interior mixes ------------------------------------------------------
YARD_MIX = {
    "residential": (("shed", 1.3), ("garden_0", 1.1), ("garden_1", 0.9),
                    ("coop", 1.0), ("pigpen", 0.4), ("hay_stack", 0.4),
                    ("woodpile", 1.1), ("woodpile_lean", 1.0), ("compost", 0.8),
                    ("waterbutt", 0.8), ("rack", 0.8), ("tree_1", 0.8),
                    ("treebus_0", 0.7), ("treebus_1", 0.5), ("hedge_150", 0.6),
                    ("well", 0.22), ("bench", 0.7), ("dovecote", 0.3),
                    ("beehives_2", 0.25), ("grindstone", 0.3), ("herbs", 0.5),
                    ("pots_3", 0.5), ("barrow", 0.5), ("pallet", 0.6),
                    ("stonepile", 0.6), ("trough", 0.25), ("cart", 0.5),
                    ("toolrack", 0.3), ("crates3", 0.4), ("sacks_3", 0.4),
                    ("tree_0", 0.5), ("fountain", 0.03)),
    "craft": (("woodpile", 1.6), ("woodpile_lean", 1.4), ("planks_1", 1.5),
              ("crates3", 1.1), ("shed", 1.2), ("stonepile", 1.0),
              ("barrel_36", 1.0), ("rack", 1.2), ("waterbutt", 0.8),
              ("cart", 1.0), ("toolrack", 1.0), ("wheel", 0.6),
              ("grindstone", 0.5), ("pallet", 0.7), ("trough", 0.4),
              ("treebus_0", 0.3)),
    "artisan": (("woodpile", 1.4), ("stonepile", 1.2), ("planks_2", 1.3),
                ("shed", 1.2), ("barrel_30", 1.1), ("compost", 0.9),
                ("grindstone", 0.6), ("toolrack", 0.8), ("crates3", 0.7),
                ("treebus_1", 0.4), ("waterbutt", 0.5)),
    "dock": (("crates3", 1.5), ("barrel_36", 1.5), ("pallet", 1.4),
             ("cart", 1.2), ("rack", 1.3), ("coop", 0.9), ("waterbutt", 0.7),
             ("sacks_3", 0.9), ("amphorae_4", 0.9), ("stonepile", 0.5),
             ("trough", 0.4), ("hitch", 0.4)),
    "outer": (("hay_stack", 1.4), ("pigpen", 1.6), ("garden_0", 1.2),
              ("coop", 1.2), ("woodpile", 1.2), ("cart", 1.0), ("compost", 1.0),
              ("tree_1", 0.8), ("tree_0", 0.6), ("hedge_220", 0.6),
              ("well", 0.25), ("trough", 0.5), ("hay", 0.7),
              ("beehives_3", 0.3), ("dovecote", 0.3), ("fountain", 0.02),
              ("shrine", 0.2)),
    "guild": (("bench", 1.2), ("shrub", 1.0), ("waterbutt", 0.9),
              ("stonepile", 0.8), ("rack", 1.0), ("tree_1", 0.9),
              ("hedge_150", 0.8), ("well", 0.2), ("pots_3", 0.7),
              ("stone_bench", 0.7), ("notice", 0.3), ("tree_0", 0.5)),
    "temple": (("bench", 1.1), ("shrub", 1.0), ("waterbutt", 0.8),
               ("stonepile", 1.0), ("tree_2", 0.9), ("hedge_220", 0.8),
               ("pots_3", 0.7), ("stone_bench", 0.8), ("well", 0.2),
               ("shrine", 0.4), ("vine", 0.2)),
    "palace": (("bench", 1.0), ("shrub", 1.0), ("tree_2", 1.0),
               ("hedge_220", 0.9), ("fountain", 0.15), ("stone_bench", 0.8),
               ("pots_3", 0.6), ("well", 0.1)),
}

# wall-hug (the 1-3 m strips behind a house) -------------------------------
WALL_MIX = (("barrel_25", 1.6), ("barrel_30", 1.2), ("crate_46", 1.4),
            ("crate_60", 0.9), ("sacks_2", 1.2), ("woodpile_lean", 1.0),
            ("waterbutt", 1.1), ("pots_2", 1.0), ("bucket", 0.8),
            ("planks_0", 0.8), ("pallet_bare", 0.9), ("weeds_55", 1.0),
            ("weeds_85", 0.8), ("shrub", 0.8), ("ladder", 0.7),
            ("compost", 0.6), ("stonepile", 0.7), ("leaves_0", 0.9),
            ("crates3", 0.5), ("amphorae_3", 0.7), ("hay", 0.6),
            ("toolrack", 0.4), ("trough", 0.3), ("bench", 0.5),
            ("grindstone", 0.3), ("dovecote", 0.2), ("beehives_2", 0.25),
            ("treebus_0", 0.5), ("hedge_150", 0.4), ("stoop", 0.7),
            ("hitch", 0.4), ("wheel", 0.4), ("barrow", 0.4),
            ("fence", 0.5), ("board_panel", 0.5), ("wall_panel", 0.5),
            ("gate", 0.3), ("cat", 0.4), ("pigeons_3", 0.35))

WALL_ATTACH_MIX = (("ivy_0", 1.6), ("ivy_1", 1.0), ("vine", 1.0),
                   ("rainbarrel", 0.8), ("stairs", 0.5), ("shrine", 0.35),
                   ("shopawning_0", 1.1), ("shopawning_1", 0.9),
                   ("shopawning_2", 0.5), ("trellis", 1.0))


def _pick(mix, rng):
    tot = 0.0
    for _, w in mix:
        tot += w
    if tot <= 0.0:
        return mix[0][0]
    t = rng.random() * tot
    for name, w in mix:
        t -= w
        if t <= 0.0:
            return name
    return mix[-1][0]


def _yaw_to(dx, dy):
    """yaw that makes a prop's local +Y point along (dx,dy)."""
    return math.atan2(-dx, dy)


def _yaw_x(dx, dy):
    """yaw that makes a prop's local +X point along (dx,dy)."""
    return math.atan2(dy, dx)


def _wall_march(ug, x, y, dx, dy, maxd, step=0.34):
    """Distance from (x,y) to a facade along (dx,dy), or None."""
    d = 0.30
    while d <= maxd:
        if ug.hit(x + dx * d, y + dy * d, 0.0):
            return d
        d += step
    return None


class Occ(object):
    """Disc occupancy grid for prop-vs-prop separation."""

    def __init__(self, cell=1.4):
        self.c = cell
        self.g = {}

    def free(self, x, y, r):
        c = self.c
        ix0 = int(math.floor((x - r) / c))
        ix1 = int(math.floor((x + r) / c))
        iy0 = int(math.floor((y - r) / c))
        iy1 = int(math.floor((y + r) / c))
        for ix in range(ix0, ix1 + 1):
            for iy in range(iy0, iy1 + 1):
                for (px, py, pr) in self.g.get((ix, iy), ()):
                    dx = px - x
                    dy = py - y
                    rr = pr + r
                    if dx * dx + dy * dy < rr * rr:
                        return False
        return True

    def take(self, x, y, r):
        c = self.c
        for ix in range(int(math.floor((x - r) / c)),
                        int(math.floor((x + r) / c)) + 1):
            for iy in range(int(math.floor((y - r) / c)),
                            int(math.floor((y + r) / c)) + 1):
                self.g.setdefault((ix, iy), []).append((x, y, r))


# ===========================================================================
# the emitter
# ===========================================================================
CELL = 56.0
_LAST = {}
_BUILT = []


def _proto_faces(proto):
    return sum(v[2].shape[0] for v in proto.values())


class _Ctx(object):
    def __init__(self, P, units, streets, blocks, seed=7, cell=CELL, region=None,
                 keep_points=False, budget=0):
        self.P = P
        self.reg = region
        self.G = protos()
        self.keep = keep_points
        self.budget = float(budget or 0.0)
        self.pts = []
        self.st_station = 0
        self.st_nowall = 0
        self.ug = UnitGrid(units)
        self.sr = StreetRaster(streets or ())
        self.occ = Occ()
        self.b = {}
        self.rng = random.Random((int(seed) * 7919) ^ 0x5F3A)
        self.n = {}
        self.nfk = {}
        self.nf = 0
        self.rej = 0
        self.cell = cell
        self.lm = _landmarks()
        self.lmb = []
        for l in self.lm:
            pl = l.get("plot") or ()
            if len(pl) < 3:
                continue
            xs = [p[0] for p in pl]
            ys = [p[1] for p in pl]
            self.lmb.append((min(xs) - 2.5, min(ys) - 2.5, max(xs) + 2.5,
                             max(ys) + 2.5, pl))

    def batch(self, x, y):
        k = (int(math.floor(x / self.cell)), int(math.floor(y / self.cell)))
        b = self.b.get(k)
        if b is None:
            b = self.b[k] = Batch("streetlife_%d_%d" % k)
        return b

    def put(self, name, x, y, z, yaw, sc=1.0, bld=True, prop=True,
            street=False, gap=0.0, reserve=True):
        proto = self.G.get(name)
        if proto is None:
            return False
        if self.reg is not None:
            rx, ry, rr = self.reg
            if (x - rx) ** 2 + (y - ry) ** 2 > rr * rr:
                return False
        r = RAD.get(name, 0.55) * sc
        if prop and not self.occ.free(x, y, r * 0.85):
            self.rej += 1
            return False
        if bld and self.ug.hit(x, y, r * 0.42 + gap):
            self.rej += 1
            return False
        if street and self.sr.clear(x, y) < -0.5:
            self.rej += 1
            return False
        if not self.lm_ok(x, y):
            self.rej += 1
            return False
        if reserve:
            self.occ.take(x, y, r * 0.85)
        if self.budget and self.nf >= self.budget:
            # hard face ceiling: later passes are supplementary, so truncating
            # them is always preferable to blowing the parent's budget.
            self.rej += 1
            return False
        self.batch(x, y).put(proto, x, y, z, yaw, sc)
        if self.keep:
            self.pts.append((x, y, name))
        self.n[name] = self.n.get(name, 0) + 1
        f = _proto_faces(proto)
        self.nf += f
        self.nfk[name] = self.nfk.get(name, 0) + f
        return True

    def lm_ok(self, x, y):
        for (x0, y0, x1, y1, pl) in self.lmb:
            if x < x0 or x > x1 or y < y0 or y > y1:
                continue
            if _in_poly(x, y, pl) or _poly_margin(x, y, pl) > -2.5:
                return False
        return True


# ---------------------------------------------------------------------------
# pass 1: street kerbs
# ---------------------------------------------------------------------------
def _streets_pass(ctx, streets, dens=1.0, spots=None):
    rng = ctx.rng
    spots = street_spots(streets, ctx.ug, rng) if spots is None else spots
    for sp in spots:
        kind = sp["kind"]
        mix = STREET_MIX.get(kind, STREET_MIX["secondary"])
        w, h = sp["w"], sp["h"]
        nx, ny, ax, ay = sp["nx"], sp["ny"], sp["ax"], sp["ay"]
        px, py = sp["x"], sp["y"]
        d = _wall_march(ctx.ug, px, py, nx, ny, h + 2.6)
        ctx.st_station += 1
        if d is None:
            ctx.st_nowall += 1
            d = h + 1.2
        u = rng.random()
        n = 1
        if u < 0.46 * dens:
            n = 2
        elif u < 0.66 * dens:
            n = 3
        off = 0.0
        sgn = 1 if rng.random() < 0.5 else -1
        tight = 1.0
        # now and then the street keeps a heap instead of a neat row: a stall's
        # stock unloaded against the wall, a pile nobody has carried in yet
        if kind != "alley" and rng.random() < 0.24 * dens:
            n = rng.randint(4, 6)
            tight = 0.34
        for i in range(n):
            name = _pick(mix, rng)
            r = RAD.get(name, 0.55)
            inset = d - r - rng.uniform(0.10, 0.45)
            if inset < h * 0.40:
                inset = min(h * 0.74, max(h * 0.46, h - 1.05))
            sc = rng.uniform(0.90, 1.12) if r < 0.55 else rng.uniform(0.94, 1.07)
            if name.startswith("person"):
                sc = rng.uniform(0.94, 1.06)
            x = px + nx * inset + ax * off
            y = py + ny * inset + ay * off
            if rng.random() < 0.5:
                yaw = _yaw_x(ax, ay) + rng.uniform(-0.16, 0.16)
            else:
                yaw = _yaw_to(-nx, -ny) + rng.uniform(-0.30, 0.30)
            ctx.put(name, x, y, sp["z"], yaw, sc)
            off += sgn * (r * 2.0 + rng.uniform(0.30, 1.10)) * tight
        # alley yards: a run of fence / wall along the kerb now and then
        if kind == "alley" and rng.random() < 0.30 * dens:
            _kerb_run(ctx, sp, d)


def _kerb_run(ctx, sp, d):
    """A fence or low wall run along an alley kerb."""
    rng = ctx.rng
    nx, ny, ax, ay = sp["nx"], sp["ny"], sp["ax"], sp["ay"]
    name = ("board_panel_lo", "wall_panel", "board_panel", "fence")[
        rng.randrange(4)]
    ln = 1.8
    n = 1 + rng.randrange(3)
    inset = min(d - 0.4, sp["h"] + 0.35)
    if inset < sp["h"] * 0.5:
        return
    yaw = _yaw_x(ax, ay)
    sgn = 1 if rng.random() < 0.5 else -1
    for i in range(n):
        x = sp["x"] + nx * inset + ax * (i * ln * sgn)
        y = sp["y"] + ny * inset + ay * (i * ln * sgn)
        ctx.put(name, x, y, sp["z"], yaw, 1.0, gap=0.0)


# ---------------------------------------------------------------------------
# pass 2: overhead - laundry lines and banners spanning the street
# ---------------------------------------------------------------------------
SPAN = ((5.0, "banner_500", "banner_501"), (6.5, "banner_650", "banner_651"),
        (8.0, "banner_800", "banner_801"), (9.5, "banner_950", "banner_951"))


def _overhead_pass(ctx, streets, dens=1.0):
    rng = ctx.rng
    ug = ctx.ug
    for si, s in enumerate(streets):
        kind = s.get("kind") or "secondary"
        if kind == "main":
            lo, hi = 7.0, 15.0
        elif kind == "secondary":
            lo, hi = 5.5, 12.0
        else:
            lo, hi = 5.0, 10.0
        for chain in _chains(s):
            acc = [0.0]
            for i in range(len(chain) - 1):
                acc.append(acc[-1] + math.hypot(chain[i + 1][0] - chain[i][0],
                                                chain[i + 1][1] - chain[i][1]))
            L = acc[-1]
            if L < 8.0:
                continue
            t = rng.uniform(lo, hi) * 0.5
            while t < L - 3.0:
                lo_i, hi_i = 0, len(acc) - 1
                while lo_i < hi_i - 1:
                    mid = (lo_i + hi_i) // 2
                    if acc[mid] <= t:
                        lo_i = mid
                    else:
                        hi_i = mid
                x1, y1 = chain[lo_i]
                x2, y2 = chain[lo_i + 1]
                seg = acc[lo_i + 1] - acc[lo_i]
                if seg < 1e-6:
                    break
                f = (t - acc[lo_i]) / seg
                ax = (x2 - x1) / seg
                ay = (y2 - y1) / seg
                px = x1 + (x2 - x1) * f
                py = y1 + (y2 - y1) * f
                nx, ny = -ay, ax
                d1 = _wall_march(ug, px, py, nx, ny, 8.5)
                d2 = _wall_march(ug, px, py, -nx, -ny, 8.5)
                if d1 and d2:
                    gap = d1 + d2
                    cx = px + nx * (d1 - d2) * 0.5
                    cy = py + ny * (d1 - d2) * 0.5
                    yaw = _yaw_x(nx, ny)
                    if 3.4 <= gap <= 15.0 and ctx.lm_ok(cx, cy):
                        if gap <= 5.4 and rng.random() < 0.42:
                            ctx.put("laundry_%d" % rng.randrange(2), cx, cy,
                                    0.0, yaw, 1.0, bld=False, prop=False)
                        else:
                            for cared, a, b in SPAN:
                                if cared >= gap - 0.3:
                                    sc = min(1.35, gap / cared)
                                    ctx.put(a if rng.random() < 0.5 else b,
                                            cx, cy, 0.0, yaw, sc,
                                            bld=False, prop=False)
                                    break
                t += rng.uniform(lo, hi)


# ---------------------------------------------------------------------------
# pass 3: people
# ---------------------------------------------------------------------------
def _people_pass(ctx, streets, dens=1.0):
    rng = ctx.rng
    for si, s in enumerate(streets):
        kind = s.get("kind") or "secondary"
        h = float(s.get("w") or 6.0) * 0.5
        if kind == "main":
            lo, hi, n = 22.0, 50.0, 2
        elif kind == "secondary":
            lo, hi, n = 19.0, 40.0, 1
        else:
            lo, hi, n = 21.0, 52.0, 1
        for chain in _chains(s):
            acc = [0.0]
            for i in range(len(chain) - 1):
                acc.append(acc[-1] + math.hypot(chain[i + 1][0] - chain[i][0],
                                                chain[i + 1][1] - chain[i][1]))
            L = acc[-1]
            if L < 6.0:
                continue
            t = rng.uniform(lo, hi)
            while t < L - 2.0:
                lo_i, hi_i = 0, len(acc) - 1
                while lo_i < hi_i - 1:
                    mid = (lo_i + hi_i) // 2
                    if acc[mid] <= t:
                        lo_i = mid
                    else:
                        hi_i = mid
                x1, y1 = chain[lo_i]
                x2, y2 = chain[lo_i + 1]
                seg = acc[lo_i + 1] - acc[lo_i]
                if seg < 1e-6:
                    break
                f = (t - acc[lo_i]) / seg
                ax = (x2 - x1) / seg
                ay = (y2 - y1) / seg
                px = x1 + (x2 - x1) * f
                py = y1 + (y2 - y1) * f
                nx, ny = -ay, ax
                side = 1 if rng.random() < 0.5 else -1
                off = h * rng.uniform(0.30, 0.72)
                k = 1 + (1 if rng.random() < 0.25 * dens else 0)
                for j in range(k):
                    x = px + nx * off * side + ax * (j * 0.55)
                    y = py + ny * off * side + ay * (j * 0.55)
                    if ctx.sr.clear(x, y) > 0.0:
                        continue
                    yaw = _yaw_x(ax, ay) + rng.uniform(-1.3, 1.3)
                    ctx.put("person_%d" % rng.randrange(6), x, y, Z_STREET,
                            yaw, rng.uniform(0.94, 1.06), prop=True, bld=True)
                if rng.random() < 0.10:
                    ctx.put("dog", px + nx * off * side, py + ny * off * side,
                            Z_STREET, _yaw_x(ax, ay) + rng.uniform(-0.6, 0.6),
                            1.0)
                t += rng.uniform(lo, hi)


# ---------------------------------------------------------------------------
# pass 4: block interiors
# ---------------------------------------------------------------------------
PAD_MIX = (("yardpad_0", 3.0), ("yardpad_1", 1.2), ("yardpad_2", 1.2))


def _pad_pass(ctx, blocks, dens=1.0):
    """Tile every block's open ground with cheap courtyard-floor quads.

    The pads are flat and carry no occupancy, so they can go under every other
    prop: they are the carpet, not the furniture.
    """
    rng = ctx.rng
    for b in blocks:
        poly = b.get("poly") or ()
        if len(poly) < 3:
            continue
        area = float(b.get("area") or 0.0)
        if area < 60.0:
            continue
        role = b.get("role") or "residential"
        if role in ("square", "plaza"):
            continue
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        step = 6.2 / max(0.35, min(2.0, dens))
        y = y0
        while y < y1:
            x = x0
            while x < x1:
                px = x + rng.uniform(-0.9, 0.9)
                py = y + rng.uniform(-0.9, 0.9)
                if (_in_poly(px, py, poly)
                        and _poly_margin(px, py, poly) > -0.4
                        and not ctx.ug.hit(px, py, 0.15)):
                    ctx.put(_pick(PAD_MIX, rng), px, py, Z_YARD,
                            rng.uniform(0.0, TAU), rng.uniform(0.92, 1.18),
                            prop=False, reserve=False, gap=0.0)
                x += step
            y += step


BED_MIX = (("bed_veg", 2.0), ("bed_straw", 1.3), ("bed_rubble", 1.0))


def _bed_pass(ctx, blocks, dens=1.0):
    """Scatter flat ground patches through every block's open ground.

    This is the pass that actually kills "empty beige": a yard floor is most of
    what the game camera sees, and these cost ~8 faces each, so they can go down
    at ten times the density of any solid prop.
    """
    rng = ctx.rng
    for b in blocks:
        poly = b.get("poly") or ()
        if len(poly) < 3:
            continue
        area = float(b.get("area") or 0.0)
        if area < 70.0:
            continue
        role = b.get("role") or "residential"
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        nb = int(min(26.0, max(3.0, area / 110.0)) * dens)
        if role in ("square", "plaza", "palace", "temple"):
            nb = int(nb * 0.35)
        for _i in range(nb):
            for _try in range(5):
                x = rng.uniform(x0, x1)
                y = rng.uniform(y0, y1)
                if not _in_poly(x, y, poly):
                    continue
                if _poly_margin(x, y, poly) < 1.05:
                    continue
                if ctx.ug.hit(x, y, 0.25):
                    continue
                name = _pick(BED_MIX, rng)
                if ctx.put(name, x, y, Z_YARD, rng.uniform(0.0, TAU),
                           rng.uniform(1.25, 2.10), street=True, gap=0.0):
                    break


def _yards_pass(ctx, units, blocks, dens=1.0):
    rng = ctx.rng
    by_block = {}
    for u in units:
        by_block.setdefault(u.get("block"), []).append(u)
    for b in blocks:
        poly = b.get("poly") or ()
        role = b.get("role") or "residential"
        if len(poly) < 3 or role in ("square", "plaza"):
            continue
        area = float(b.get("area") or 0.0)
        built = 0.0
        for u in by_block.get(b.get("id"), ()):
            q = u.get("quad")
            if q:
                built += _quad_area(q)
        free = area - built
        if free < 65.0:
            continue
        # A single crate in a 200 m2 yard is invisible from the game camera;
        # four props inside 4 m read as an inhabited corner.  So the block
        # interior is filled with *clusters*, not with a uniform sprinkle.
        mix = RECIPE_MIX.get(role) or RECIPE_MIX["residential"]
        ncl = int(min(5.0, max(1.0, free / 120.0)) * dens)
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        placed = 0
        tries = 0
        while placed < ncl and tries < ncl * 14:
            tries += 1
            recipe = _pick(mix, rng)
            items = YARD_RECIPES[recipe]
            cx = rng.uniform(x0, x1)
            cy = rng.uniform(y0, y1)
            if _poly_margin(cx, cy, poly) < 2.9:
                continue
            if ctx.ug.hit(cx, cy, 2.55):
                continue
            yaw = rng.uniform(0.0, TAU)
            sc = rng.uniform(0.94, 1.08)
            if _cluster(ctx, cx, cy, yaw, items, sc=sc) >= 2:
                placed += 1


# ---------------------------------------------------------------------------
# pass 4a: yard clusters -- a farmyard reads as life, one barrel reads as litter
# ---------------------------------------------------------------------------
# local frame: +Y is the side the group faces; metres between members.
YARD_RECIPES = {
    "farm": (("shed", 0.0, 0.0), ("woodpile", -2.35, 0.70),
             ("woodpile_lean", 2.30, -0.60), ("hay_stack", 2.15, 1.40),
             ("cart", -0.30, 2.55), ("waterbutt", -2.50, 2.10),
             ("barrel_30", 2.80, 2.65), ("trough", -1.60, -1.40)),
    "garden": (("garden_0", 0.0, 0.0), ("herbs", -1.80, 1.40),
               ("compost", 1.90, 1.30), ("waterbutt", 2.95, -0.40),
               ("pots_3", -2.60, 1.80), ("barrow", 0.55, 2.40)),
    "livestock": (("coop", 0.0, 0.0), ("pigpen", 2.80, 0.60),
                  ("hay", 1.45, 2.00), ("hay_stack", -1.90, 1.30),
                  ("trough", -2.40, -0.80), ("fence", 0.10, 2.20)),
    "workshop": (("planks_1", 0.0, 0.0), ("crates3", 2.10, 0.45),
                 ("barrel_36", -2.00, 0.65), ("rack", 2.00, 1.90),
                 ("cart", -0.55, 2.20), ("woodpile", 2.40, -1.40)),
    "wash": (("waterbutt", 0.0, 0.0), ("trough", -1.75, 0.70),
             ("bucket", -0.50, 1.30), ("bench", 1.60, 1.10),
             ("rack", 2.30, -0.70)),
    "seating": (("bench", 0.0, 0.0), ("stone_bench", 2.20, 0.55),
                ("tree_1", -2.30, 0.80), ("pots_3", 1.60, 1.80),
                ("ladder", 2.60, -1.60)),
    "yard_lot": (("woodpile_lean", 0.0, 0.0), ("crate_46", 1.60, 0.35),
                 ("crate_60", 1.40, 1.20), ("barrel_25", -1.50, 0.85),
                 ("sacks_2", -0.35, 1.80), ("pallet_bare", 1.05, 2.35)),
}

RECIPE_MIX = {
    "residential": (("garden", 1.6), ("yard_lot", 1.2), ("farm", 1.2),
                    ("wash", 1.0), ("livestock", 0.7), ("seating", 0.5)),
    "craft": (("workshop", 2.0), ("yard_lot", 1.4), ("farm", 0.5)),
    "artisan": (("workshop", 1.6), ("yard_lot", 1.2), ("garden", 0.6)),
    "dock": (("yard_lot", 2.0), ("workshop", 1.2), ("farm", 0.3)),
    "outer": (("livestock", 1.8), ("farm", 1.6), ("garden", 1.0),
              ("yard_lot", 0.8)),
    "guild": (("seating", 1.4), ("wash", 0.8), ("yard_lot", 0.6)),
    "temple": (("seating", 1.6), ("garden", 0.8)),
    "palace": (("seating", 2.0), ("garden", 1.0)),
}


def _cluster(ctx, cx, cy, yaw, items, sc=1.0, z=None):
    """Place one recipe's worth of props around (cx, cy).  Returns how many."""
    z = Z_YARD if z is None else z
    ca, sa = math.cos(yaw), math.sin(yaw)
    n = 0
    for it in items:
        name, lx, ly = it[0], it[1] * sc, it[2] * sc
        x = cx + lx * ca - ly * sa
        y = cy + lx * sa + ly * ca
        if ctx.put(name, x, y, z, yaw + (it[3] if len(it) > 3 else 0.0),
                   sc, street=True, gap=0.08):
            n += 1
    return n


# ---------------------------------------------------------------------------
# pass 4b: trees -- the cheapest way to stop a block reading as beige
# ---------------------------------------------------------------------------
TREE_MIX = (("tree_1", 1.7), ("tree_0", 1.2), ("tree_2", 0.8),
            ("treebus_0", 1.1), ("treebus_1", 0.6))


def _trees_pass(ctx, spots, blocks, dens=1.0):
    rng = ctx.rng
    ug = ctx.ug
    # a) kerbside: a plane or a lime in front of the houses, so a lane reads as
    #    a street and not as a corridor between two walls
    for sp in spots:
        if rng.random() > 0.17 * dens:
            continue
        kind = sp["kind"]
        nx, ny = sp["nx"], sp["ny"]
        d = _wall_march(ug, sp["x"], sp["y"], nx, ny, sp["h"] + 3.6)
        if d is None:
            d = sp["h"] + 1.4
        if kind == "alley":
            name = "treebus_0" if d > 2.2 else None
            inset = min(d - 0.70, sp["h"] * 0.5 + 0.45)
        else:
            name = _pick(TREE_MIX, rng)
            inset = max(0.85, min(d - 1.05, sp["h"] * 0.5 + 0.95))
        if name is None or inset < 0.40:
            continue
        ctx.put(name, sp["x"] + nx * inset, sp["y"] + ny * inset, sp["z"],
                rng.uniform(0.0, TAU), rng.uniform(0.85, 1.30))
    # b) yard and block-core trees
    for b in blocks:
        poly = b.get("poly") or ()
        if len(poly) < 3:
            continue
        area = float(b.get("area") or 0.0)
        if area < 90.0:
            continue
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        n = int(min(5.0, max(1.0, area / 300.0)) * dens)
        for i in range(n):
            for attempt in range(5):
                x = rng.uniform(x0, x1)
                y = rng.uniform(y0, y1)
                if _poly_margin(x, y, poly) < 1.15:
                    continue
                if ctx.put(_pick(TREE_MIX, rng), x, y, Z_YARD,
                           rng.uniform(0.0, TAU), rng.uniform(0.80, 1.35),
                           street=True, gap=0.40):
                    break


# ---------------------------------------------------------------------------
# pass 5: hug the back (and courtyard-facing) walls
# ---------------------------------------------------------------------------
# `ring` in hd_dense.placements() is the block tier name, not an index
_TIER = {"outer": 0, "mid": 1, "core": 2}


def _tier(u):
    r = u.get("ring")
    if isinstance(r, str):
        return _TIER.get(r.strip().lower(), 1)
    try:
        return int(r or 0)
    except (TypeError, ValueError):
        return 0


def _wallhug_pass(ctx, units, dens=1.0):
    rng = ctx.rng
    ug = ctx.ug
    for u in units:
        q = u.get("quad")
        if not q or len(q) < 4:
            continue
        yaw = float(u.get("yaw") or 0.0)
        nx, ny = -math.sin(yaw), math.cos(yaw)
        ring = _tier(u)
        # back edge = the two vertices furthest along -n
        pr = [-(p[0] * nx + p[1] * ny) for p in q]
        o = sorted(range(len(q)), key=lambda i: -pr[i])
        a, b = q[o[0]], q[o[1]]
        ex, ey = b[0] - a[0], b[1] - a[1]
        el = math.hypot(ex, ey)
        if el < 1.6:
            continue
        ex, ey = ex / el, ey / el
        # how far can we go behind the wall before the next ring starts?
        depth = _wall_march(ug, (a[0] + b[0]) * 0.5 - nx * 0.35,
                            (a[1] + b[1]) * 0.5 - ny * 0.35,
                            -nx, -ny, 3.8, 0.30)
        if depth is not None and depth < 0.55:
            continue
        t = rng.uniform(0.10, 0.30) * el
        side = 1
        while t < el - 0.35:
            if rng.random() < 0.55 * dens:
                cx = a[0] + ex * t - nx * 0.34
                cy = a[1] + ey * t - ny * 0.34
                wall = rng.random() < 0.34
                if wall:
                    name = _pick(WALL_ATTACH_MIX, rng)
                    if name == "stairs" and (depth is not None and depth < 2.3):
                        name = "ivy_0"
                    z = Z_YARD + (rng.uniform(2.55, 3.85)
                                  if name == "sillbox" else 0.0)
                    ctx.put(name, cx - nx * 0.16, cy - ny * 0.16, z,
                            _yaw_to(-nx, -ny) + math.pi, 1.0, prop=True,
                            bld=False)
                else:
                    name = _pick(WALL_MIX, rng)
                    r = RAD.get(name, 0.55)
                    px = cx - nx * (r * 0.55)
                    py = cy - ny * (r * 0.55)
                    yw = (_yaw_x(ex, ey) + rng.uniform(-0.20, 0.20)
                          if rng.random() < 0.55
                          else _yaw_to(-nx, -ny) + rng.uniform(-0.25, 0.25))
                    ctx.put(name, px, py, Z_YARD, yw,
                            rng.uniform(0.92, 1.10), bld=False)
            t += rng.uniform(2.0, 3.7)
        # ring>=1 houses face the courtyard: clutter their frontage too
        if ring >= 1 and rng.random() < 0.40 * dens:
            prf = [p[0] * nx + p[1] * ny for p in q]
            oo = sorted(range(len(q)), key=lambda i: -prf[i])
            a2, b2 = q[oo[0]], q[oo[1]]
            ex2, ey2 = b2[0] - a2[0], b2[1] - a2[1]
            el2 = math.hypot(ex2, ey2)
            if el2 > 1.6:
                t2 = rng.uniform(0.15, 0.85) * el2
                cx = a2[0] + ex2 / el2 * t2 + nx * 0.36
                cy = a2[1] + ey2 / el2 * t2 + ny * 0.36
                name = _pick((("pots_2", 1.2), ("bench", 1.0),
                              ("barrel_25", 1.0), ("crate_46", 1.0),
                              ("woodpile", 0.8), ("pots_3", 0.8),
                              ("shrub", 1.0), ("weeds_55", 1.0),
                              ("amphorae_3", 0.8), ("trough", 0.5)), rng)
                ctx.put(name, cx, cy, Z_YARD,
                        _yaw_to(nx, ny) + rng.uniform(-0.3, 0.3),
                        rng.uniform(0.92, 1.08), prop=True, bld=True)


# ---------------------------------------------------------------------------
# pass 6: plot boundaries
# ---------------------------------------------------------------------------
def _fence_pass(ctx, units, dens=1.0):
    """A boundary running back from one corner of every few houses: the fence
    that separates this plot from the neighbour's yard."""
    rng = ctx.rng
    ug = ctx.ug
    for u in units:
        if rng.random() > 0.30 * dens:
            continue
        q = u.get("quad")
        if not q or len(q) < 4:
            continue
        if _tier(u) > 1:
            continue
        yaw = float(u.get("yaw") or 0.0)
        nx, ny = -math.sin(yaw), math.cos(yaw)
        pr = [-(p[0] * nx + p[1] * ny) for p in q]
        o = sorted(range(len(q)), key=lambda i: -pr[i])
        a, b = q[o[0]], q[o[1]]
        corner = a if rng.random() < 0.5 else b
        csgn = -1.0 if corner is a else 1.0
        ex, ey = b[0] - a[0], b[1] - a[1]
        el = math.hypot(ex, ey)
        if el < 1.4:
            continue
        ex, ey = ex / el, ey / el
        # start just off the corner and run outward along -n
        name = ("fence", "board_panel", "wall_panel", "hedge_150")[
            rng.randrange(4)]
        ln = 1.8
        yw = _yaw_x(-nx, -ny)
        n = 1 + rng.randrange(3)
        for i in range(n):
            d = 0.55 + (i + 0.5) * ln
            x = corner[0] + ex * 0.30 * csgn - nx * d
            y = corner[1] + ey * 0.30 * csgn - ny * d
            if not ctx.put(name, x, y, Z_YARD, yw, 1.0, street=True,
                           gap=0.05):
                break
        if rng.random() < 0.35:
            ctx.put("gate_leaf", corner[0] + ex * 0.30 * csgn - nx * 0.55,
                    corner[1] + ey * 0.30 * csgn - ny * 0.55, Z_YARD,
                    yw + rng.uniform(0.4, 1.1), 1.0, bld=False)


# ---------------------------------------------------------------------------
# pass 7: market squares
# ---------------------------------------------------------------------------
def _market_pass(ctx, blocks, dens=1.0):
    rng = ctx.rng
    spots = market_spots(blocks, ctx.ug, rng, dens)
    for sp in spots:
        yaw = sp["yaw"] + rng.uniform(-0.10, 0.10)
        x, y = sp["x"], sp["y"]
        front = (math.cos(yaw + math.pi * 0.5), -math.sin(yaw + math.pi * 0.5))
        if not ctx.put("stall_%d" % rng.randrange(2), x, y, sp["z"], yaw,
                       1.0, prop=False):
            continue
        # companion clutter at the side of the stall
        for k in (1, -1):
            side = (math.cos(yaw), math.sin(yaw))
            nx2 = x + side[0] * k * 1.45
            ny2 = y + side[1] * k * 1.45
            name = _pick((("crate_60", 2.0), ("crates3", 1.2), ("sacks_2", 1.6),
                          ("amphorae_4", 1.0), ("barrel_36", 1.3),
                          ("pots_3", 0.6), ("hay", 0.7)),
                         rng)
            ctx.put(name, nx2, ny2, sp["z"],
                    _yaw_to(-side[0] * k, -side[1] * k), 1.0)
        if rng.random() < 0.30:
            ctx.put("person_%d" % rng.randrange(6),
                    x + front[0] * 1.2 + rng.uniform(-0.4, 0.4),
                    y + front[1] * 1.2 + rng.uniform(-0.4, 0.4), sp["z"],
                    rng.uniform(0.0, TAU), rng.uniform(0.94, 1.05))


# ===========================================================================
# build
# ===========================================================================
def _clip(region, units, streets, pad=18.0):
    """Keep only the houses/streets touching (x, y, r) plus a pad ring.

    The pad ring matters: UnitGrid and StreetRaster have to know about the
    buildings just outside the region, otherwise props on the rim are placed
    straight through the neighbours' walls.
    """
    rx, ry, rr = float(region[0]), float(region[1]), float(region[2])
    lim = (rr + pad) ** 2
    us = []
    for u in units:
        try:
            dx = float(u.get("x") or 0.0) - rx
            dy = float(u.get("y") or 0.0) - ry
        except (TypeError, ValueError):
            continue
        if dx * dx + dy * dy <= lim:
            us.append(u)
    ss = []
    for s in streets:
        keep = False
        for ch in _chains(s):
            for i in range(len(ch) - 1):
                ax, ay = ch[i]
                bx, by = ch[i + 1]
                mx, my = (ax + bx) * 0.5 - rx, (ay + by) * 0.5 - ry
                if mx * mx + my * my <= lim:
                    keep = True
                    break
                if ((ax - rx) ** 2 + (ay - ry) ** 2 <= lim
                        or (bx - rx) ** 2 + (by - ry) ** 2 <= lim):
                    keep = True
                    break
            if keep:
                break
        if keep:
            ss.append(s)
    return us, ss


def build(MAT, units, res, seed=7, density=1.0, cell=CELL, verbose=True,
          collection=None, region=None, keep_points=False, budget=3950000):
    """Emit the whole street-life layer.

    MAT    : capital's material dict (init_mats()); may be None.
    units  : hd_dense.placements(...) list of building dicts.
    res    : layout.json dict (needs "streets" and "blocks").
    seed   : everything is derived from this.
    density: global multiplier on prop counts (1.0 = as designed).
    cell   : merge cell size in metres (~56 m = one game-camera frame).
    budget : hard triangle ceiling; later passes stop once it is hit
             (default 3.95 M, under the 4 M allowance).

    Returns the list of created objects (already linked into the scene).
    One object per occupied cell; each object is one mesh with all its
    materials, so the whole layer is ~450 objects for ~40k props.
    """
    import time as _t
    t0 = _t.time()
    P = palette(MAT)
    G = protos()
    streets = list((res or {}).get("streets") or ())
    blocks = list((res or {}).get("blocks") or ())
    units = list(units or ())
    if region is not None:
        units, streets = _clip(region, units, streets)
        _log("region %s: %d units, %d streets kept"
             % (tuple(round(v, 1) for v in region), len(units), len(streets)))
    ctx = _Ctx(P, units, streets, blocks, seed, cell, region=region,
               keep_points=keep_points, budget=budget)
    rng = ctx.rng

    spots = []
    if streets:
        spots = street_spots(streets, ctx.ug, rng)
    if spots:
        _streets_pass(ctx, streets, density, spots)
        _overhead_pass(ctx, streets, density)
        _people_pass(ctx, streets, density)
        _trees_pass(ctx, spots, blocks, density)
    elif blocks:
        _trees_pass(ctx, spots, blocks, density)
    _wallhug_pass(ctx, units, density)
    _fence_pass(ctx, units, density)
    if blocks:
        _pad_pass(ctx, blocks, density)
        _bed_pass(ctx, blocks, density)
        _yards_pass(ctx, units, blocks, density)
        _market_pass(ctx, blocks, density)

    objs = []
    for k in sorted(ctx.b):
        ob = ctx.b[k].emit(P)
        if ob is not None:
            objs.append(ob)
    dt = _t.time() - t0
    nprop = sum(ctx.n.values())
    _LAST.clear()
    _LAST.update(dict(props=nprop, faces=ctx.nf, objects=len(objs),
                      seconds=dt, rejected=ctx.rej, seed=seed,
                      density=density, kinds=len(ctx.n),
                      stations=ctx.st_station, no_wall=ctx.st_nowall,
                      points=ctx.pts,
                      by_kind=dict(ctx.n), by_kind_faces=dict(ctx.nfk)))
    _BUILT.extend(objs)
    if verbose:
        _log("streetlife: %d props, %d faces, %d objects, %.1fs (rej %d)"
             % (nprop, ctx.nf, len(objs), dt, ctx.rej))
    return objs


def stats():
    """Summary of the last build()."""
    return dict(_LAST)


def clear():
    """Remove everything the last build() created (for iterative labs)."""
    for ob in list(_BUILT):
        try:
            me = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if me.users == 0:
                bpy.data.meshes.remove(me)
        except Exception:
            pass
    del _BUILT[:]
    _LAST.clear()


# ===========================================================================
# prop sheet (visual QA of every proto at once)
# ===========================================================================
def build_prop_sheet(MAT, cols=8, step=3.2, name="propsheet"):
    """Lay every prototype out on a grid so one render shows the whole
    vocabulary.  Returns the single object."""
    P = palette(MAT)
    G = protos()
    b = Batch(name)
    keys = sorted(G.keys())
    for i, k in enumerate(keys):
        cx = (i % cols) * step
        cy = (i // cols) * step
        b.put(G[k], cx, cy, 0.0, 0.0, 1.0)
    ob = b.emit(P)
    _log("prop sheet: %d protos, %d faces" % (len(keys), b.nf))
    return ob, keys

