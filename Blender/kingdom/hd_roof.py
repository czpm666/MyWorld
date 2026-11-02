"""Roof coverings.

The gameplay camera looks down at 52 degrees from 34 m, so in a 2.5D frame the
roofs of the two or three houses in front of the player cover more pixels than
everything else put together.  They used to be the flattest thing in the
picture: the house module cloned the palette into `hu_roof_hd_tile_terraN`
materials whose node tree was two noise textures, two ramps and a bump, and
`medkit.mat_tile` builds its Brick in object X/Y -- which on a sloped roof is
the wrong pair of axes, because a roof varies in X and Z.

This module rebuilds a roof material properly.  Each cover is a node group
taking a flat coordinate pair (u across the slope, w down the slope), so the
same pattern can be instantiated twice -- once from object X/Z and once from
object Y/Z -- and the two are mixed by how far the surface normal leans on
each axis.  Gables only come in those two orientations, so for this city the
switch is exact.

  * clay: a row of convex pantiles.  A sine across the tile pitch gives the
    barrel, a second sine down the slope gives the lap of one course over the
    next, an aligned Voronoi cell gives each tile its own firing colour, and
    moss settles in the shadowed laps.
  * slate: a staggered grid of flat slates with a lap shadow and the slight
    sheen wet slate gives back to the sky.
  * lead: rolled seams only.

`rebuild()` walks `bpy.data.materials` and fixes anything whose name looks like
a roof, so it does not matter which module created it.
"""
import bpy
import sys

# ------------------------------------------------------------------ palettes
# (base, dark, light) -- fired clay, from a pale sandy tile to a sooty brown
CLAY = [
    ("#9a6146", "#6a3f2c", "#b87a58"),
    ("#8c5a43", "#5f3a2a", "#a86c4e"),
    ("#a2684a", "#6f4230", "#c07f5d"),
    ("#7c4c39", "#543026", "#96634a"),
    ("#a0522d", "#6b361d", "#bd6a41"),
    ("#875440", "#5a3527", "#a26a52"),
    ("#b07050", "#7a4a33", "#c98a68"),
    ("#6f4a3a", "#4a3026", "#8a604c"),
]
# slate: cool grey with a faint blue cast. These have to sit high on the value
# scale: a "realistic" #5f6470 slate under a blue sky with AgX and a -2.2 EV
# exposure renders at about (40,55,85) and reads as navy tar paper, not stone.
SLATE = [
    ("#8a909c", "#5e646e", "#a8aeba"),
    ("#92969b", "#646870", "#b0b4b9"),
    ("#828994", "#585f6a", "#a0a7b2"),
    ("#9a8e82", "#6a6159", "#b8aca0"),
    ("#7e8794", "#545c69", "#9ca5b2"),
    ("#8c9290", "#606663", "#aab0ae"),
    ("#868b99", "#5c616e", "#a4a9b7"),
    ("#948f87", "#666159", "#b2ada5"),
]
# glazed blue, for the castle and the guild hall only
GLAZED = [
    ("#3f5b78", "#26384c", "#5c7d9c"),
    ("#48627d", "#2b3d50", "#67839f"),
]
LEAD = [("#6a6d72", "#42454a", "#8b8f95")]


# ------------------------------------------------------------------- helpers
def _srgb(hexs):
    h = hexs.lstrip("#")
    s = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in s]
    return (lin[0], lin[1], lin[2], 1.0)


def _hexmix(a, b, t):
    """Mix two #rrggbb strings in sRGB space (approximate, good enough here)."""
    aa = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    bb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    out = []
    for i in range(3):
        v = int(round(aa[i] + (bb[i] - aa[i]) * t))
        out.append(max(0, min(255, v)))
    return "#%02x%02x%02x" % tuple(out)


def _stop(val):
    """Ramp stop: hex string = sRGB colour, float = LINEAR grey."""
    if isinstance(val, str):
        return _srgb(val)
    if isinstance(val, (tuple, list)):
        return tuple(val) if len(val) == 4 else (val[0], val[1], val[2], 1.0)
    v = float(val)
    return (v, v, v, 1.0)


def _node(nt, kind, loc, name=None, **props):
    n = nt.nodes.new(kind)
    n.location = loc
    if name:
        n.name = name
        n.label = name
    for k, v in props.items():
        setattr(n, k, v)
    return n


def _feed(nt, sock, val):
    if val is None:
        return
    if hasattr(val, "bl_idname"):
        nt.links.new(val, sock)
    elif isinstance(val, (tuple, list)):
        sock.default_value = val
    else:
        sock.default_value = float(val)


def _math(nt, op, a, b, loc, name=None, clamp=False):
    n = _node(nt, "ShaderNodeMath", loc, name, operation=op, use_clamp=clamp)
    _feed(nt, n.inputs[0], a)
    _feed(nt, n.inputs[1], b)
    return n.outputs[0]


def _ramp(nt, src, stops, loc, name=None):
    """Colour ramp.  A stop may be a hex string (a colour) or a plain number
    (a LINEAR grey), and the difference matters: #6a6a6a is 0.42 in sRGB but
    only 0.148 in linear, so writing shading multipliers as hex silently
    crushes them by a factor of three and turns a slate roof into tar paper.
    """
    r = _node(nt, "ShaderNodeValToRGB", loc, name)
    els = r.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    els[0].position, els[0].color = stops[0][0], _stop(stops[0][1])
    for pos, col in stops[1:]:
        e = els.new(pos)
        e.color = _stop(col)
    _feed(nt, r.inputs["Fac"], src)
    return r


def _mixc(nt, a, b, fac, loc, name=None, blend="MIX"):
    m = _node(nt, "ShaderNodeMix", loc, name, data_type="RGBA", blend_type=blend)
    ins = [s for s in m.inputs if s.type == "RGBA"]
    _feed(nt, ins[0], a)
    _feed(nt, ins[1], b)
    _feed(nt, m.inputs["Factor"], fac)
    return next(s for s in m.outputs if s.type == "RGBA")


def _mixf(nt, a, b, fac, loc, name=None):
    m = _node(nt, "ShaderNodeMix", loc, name, data_type="FLOAT")
    ins = [s for s in m.inputs if s.type == "VALUE"]
    _feed(nt, ins[0], a)
    _feed(nt, ins[1], b)
    _feed(nt, m.inputs["Factor"], fac)
    return next(s for s in m.outputs if s.type == "VALUE")


def _sepxyz(nt, vec, loc):
    n = _node(nt, "ShaderNodeSeparateXYZ", loc)
    _feed(nt, n.inputs[0], vec)
    return n


def _combine(nt, x, y, z, loc):
    n = _node(nt, "ShaderNodeCombineXYZ", loc)
    _feed(nt, n.inputs[0], x)
    _feed(nt, n.inputs[1], y)
    _feed(nt, n.inputs[2], z)
    return n.outputs[0]


def _wave(nt, vec, scale, loc, name=None, direction="X"):
    w = _node(nt, "ShaderNodeTexWave", loc, name,
              wave_type="BANDS", bands_direction=direction, wave_profile="SIN")
    w.inputs["Scale"].default_value = scale
    w.inputs["Distortion"].default_value = 0.0
    w.inputs["Detail"].default_value = 0.0
    _feed(nt, w.inputs["Vector"], vec)
    return w


def _voronoi(nt, vec, scale, loc, name=None, rand=1.0):
    v = _node(nt, "ShaderNodeTexVoronoi", loc, name,
              voronoi_dimensions="3D", feature="F1")
    v.inputs["Scale"].default_value = scale
    v.inputs["Randomness"].default_value = rand
    _feed(nt, v.inputs["Vector"], vec)
    return v


def _noise(nt, vec, scale, loc, detail=5.0, rough=0.55, name=None):
    n = _node(nt, "ShaderNodeTexNoise", loc, name)
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    _feed(nt, n.inputs["Vector"], vec)
    return n


def _bump(nt, height, strength, distance, loc, normal=None):
    b = _node(nt, "ShaderNodeBump", loc)
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    _feed(nt, b.inputs["Height"], height)
    if normal is not None:
        _feed(nt, b.inputs["Normal"], normal)
    return b


# ------------------------------------------------------------ cover groups
def _group(name, u_in, w_in):
    """Make a shader node group with float inputs U and W, and C/H outputs."""
    ng = bpy.data.node_groups.new(name, "ShaderNodeTree")
    gi = ng.nodes.new("NodeGroupInput")
    gi.location = (-1500, 0)
    go = ng.nodes.new("NodeGroupOutput")
    go.location = (900, 0)
    ng.interface.new_socket("U", in_out="INPUT", socket_type="NodeSocketFloat")
    ng.interface.new_socket("W", in_out="INPUT", socket_type="NodeSocketFloat")
    ng.interface.new_socket("Color", in_out="OUTPUT", socket_type="NodeSocketColor")
    ng.interface.new_socket("Height", in_out="OUTPUT", socket_type="NodeSocketFloat")
    return ng, gi.outputs["U"], gi.outputs["W"], go


def _finish_group(ng, go, color, height):
    ng.links.new(color, go.inputs["Color"])
    ng.links.new(height, go.inputs["Height"])


def _clay_group(base, dark, light, tile=0.30, course=0.36, moss_amt=0.16,
                rough=0.74):
    """A clay pantile roof.

    Readability at 2.5D distance comes from three things, in this order: the
    course line every 0.36 m (about ten pixels, and the only line the eye can
    resolve), a slow mottling at the three-metre scale, and the per-tile firing
    colour.  The barrel shading and the per-tile detail are there for the eye
    that looks closely, not for the one that is playing.  Everything is kept in
    the 0.6-1.0 brightness band: multiplying three layers at 0.35 each is how
    the first version turned a terracotta roof into a navy one.
    """
    ng, u, w, go = _group("RoofClay", 0, 0)
    uw = _combine(ng, u, w, 0.0, (-1200, 0))

    # across the slope: one convex barrel per tile pitch.  A Wave band has a
    # period of 1/scale, so the scale is 1/pitch, not 1/(2*pitch).
    ridge = _wave(ng, u, 1.0 / tile, (-1000, 260), "ridge", "X")
    rfac = _ramp(ng, ridge.outputs["Fac"],
                 [(0.0, 0.52), (0.42, 0.70), (0.84, 1.0), (1.0, 0.90)],
                 (-800, 260), "ridge_shade")
    # down the slope: each course laps the one below, and that lap line is the
    # one structure that reads at gameplay distance
    lap = _wave(ng, w, 1.0 / course, (-1000, 60), "lap", "X")
    lfac = _ramp(ng, lap.outputs["Fac"],
                 [(0.0, 0.58), (0.06, 0.74), (0.18, 0.93), (0.50, 1.0),
                  (1.0, 0.98)], (-800, 60), "lap_shade")
    # per-tile firing colour, one cell per tile, kept close to the base tone
    vor = _voronoi(ng, uw, 1.0 / tile, (-1000, -160), "tile_id")
    tint = _ramp(ng, vor.outputs["Color"],
                 [(0.0, _hexmix(base, dark, 0.42)),
                  (0.38, base),
                  (0.70, _hexmix(base, light, 0.34)),
                  (1.0, _hexmix(base, dark, 0.18))],
                 (-800, -160), "tile_tint")
    # slow mottling: weathering at the metre scale, which is what keeps a roof
    # from reading as wallpaper
    mot = _noise(ng, uw, 0.30, (-1000, -420), detail=3.0, rough=0.5, name="mottle")
    motc = _ramp(ng, mot.outputs["Fac"],
                 [(0.30, _hexmix(base, dark, 0.16)), (0.72, "#ffffff")],
                 (-800, -420), "mottle_c")

    c1 = _mixc(ng, tint.outputs["Color"], rfac.outputs["Color"], 1.0,
               (-560, 220), "tint_ridge", blend="MULTIPLY")
    c2 = _mixc(ng, c1, lfac.outputs["Color"], 1.0, (-360, 220), "tint_lap",
               blend="MULTIPLY")
    c3 = _mixc(ng, c2, motc.outputs["Color"], 1.0, (-160, 220), "tint_mottle",
               blend="MULTIPLY")

    # moss settles in the laps, broken up so it does not read as paint
    mn = _noise(ng, uw, 3.4, (-520, -560), detail=6.0, rough=0.62, name="moss_n")
    mm = _ramp(ng, mn.outputs["Fac"], [(0.56, "#000000"), (0.74, "#ffffff")],
               (-300, -560), "moss_m")
    moss_c = _ramp(ng, mn.outputs["Fac"], [(0.45, "#5d6346"), (0.85, "#7d8259")],
                   (-300, -700), "moss_c")
    amt = _math(ng, "MULTIPLY", mm.outputs["Color"], moss_amt, (-80, -600),
                "moss_amt")
    amt = _math(ng, "MULTIPLY", amt, lfac.outputs["Color"], (60, -600), "moss_lap")
    col = _mixc(ng, c3, moss_c.outputs["Color"], amt, (140, 60), "moss")

    h = _math(ng, "ADD",
              _math(ng, "MULTIPLY", ridge.outputs["Fac"], 0.55, (140, -180)),
              _math(ng, "MULTIPLY", lfac.outputs["Color"], 0.45, (140, -300)),
              (300, -220), "h")
    _finish_group(ng, go, col, h)
    return ng, rough


def _slate_group(base, dark, light, tile=0.26, course=0.20, moss_amt=0.22,
                 rough=0.52):
    ng, u, w, go = _group("RoofSlate", 0, 0)
    uw = _combine(ng, u, w, 0.0, (-1200, 0))

    # one brick cell per slate: normalise by the slate size so the cells come
    # out as slate-shaped rectangles in world space.  A Voronoi was the wrong
    # primitive here -- its cells are irregular polygons, so the roof read as
    # crumpled paper.  Brick gives real rectangles with a running bond.
    cells = _combine(ng, _math(ng, "DIVIDE", u, tile, (-900, -60)),
                     _math(ng, "DIVIDE", w, course, (-900, -200)), 0.0,
                     (-760, -120))
    br = _node(ng, "ShaderNodeTexBrick", (-1000, 60), "slates",
               offset=0.5, offset_frequency=2, squash=1.0, squash_frequency=2)
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = 0.045
    br.inputs["Mortar Smooth"].default_value = 0.12
    br.inputs["Bias"].default_value = 0.5
    br.inputs["Brick Width"].default_value = 1.0
    br.inputs["Row Height"].default_value = 1.0
    br.inputs["Color1"].default_value = _srgb(_hexmix(base, dark, 0.22))
    br.inputs["Color2"].default_value = _srgb(_hexmix(base, light, 0.26))
    br.inputs["Mortar"].default_value = _srgb(_hexmix(base, dark, 0.55))
    _feed(ng, br.inputs["Vector"], cells)
    # Brick's Fac is 1 inside the mortar and 0 on the face (the tooltip says the
    # opposite), so the recess mask is Fac itself.
    joint = br.outputs["Fac"]
    joint_c = _ramp(ng, joint, [(0.0, 1.0), (1.0, 0.66)], (-760, 20), "joint_c")

    lap = _wave(ng, w, 1.0 / course, (-1000, -260), "lap", "X")
    lfac = _ramp(ng, lap.outputs["Fac"],
                 [(0.0, 0.56), (0.10, 0.80), (0.34, 0.97),
                  (1.0, 1.0)], (-800, -260), "lap_shade")
    # Brick's own Color output is a per-cell mix of Color1/Color2, which is
    # exactly the per-slate firing variation we want
    tint = br.outputs["Color"]
    mot = _noise(ng, uw, 0.42, (-1000, -520), detail=3.0, rough=0.5, name="mottle")
    motc = _ramp(ng, mot.outputs["Fac"],
                 [(0.28, _hexmix(base, dark, 0.20)), (0.74, "#ffffff")],
                 (-800, -520), "mottle_c")
    col = _mixc(ng, tint, lfac.outputs["Color"], 1.0,
                (-560, 160), "slate_col", blend="MULTIPLY")
    col = _mixc(ng, col, motc.outputs["Color"], 1.0, (-380, 160), "slate_mottle",
                blend="MULTIPLY")
    col = _mixc(ng, col, joint_c.outputs["Color"], 1.0, (-200, 160), "joints",
                blend="MULTIPLY")

    mn = _noise(ng, uw, 2.6, (-520, -420), detail=5.0, name="moss_n")
    mm = _ramp(ng, mn.outputs["Fac"], [(0.58, "#000000"), (0.76, "#ffffff")],
               (-300, -420), "moss_m")
    moss_c = _ramp(ng, mn.outputs["Fac"], [(0.5, "#585e44"), (0.9, "#787c5a")],
                   (-300, -560), "moss_c")
    amt = _math(ng, "MULTIPLY", mm.outputs["Color"], moss_amt, (-80, -460),
                "moss_amt")
    col = _mixc(ng, col, moss_c.outputs["Color"], amt, (140, 60), "moss")

    h = _math(ng, "ADD",
              _math(ng, "SUBTRACT", 1.0, joint, (140, -200)),
              _math(ng, "MULTIPLY", lfac.outputs["Color"], 0.35, (140, -320)),
              (300, -240), "h")
    _finish_group(ng, go, col, h)
    return ng, rough


def _lead_group(base, dark, light, seam=1.4, rough=0.34):
    ng, u, w, go = _group("RoofLead", 0, 0)
    s = _wave(ng, u, 1.0 / (seam * 2.0), (-1000, 120), "seam", "X")
    sfac = _ramp(ng, s.outputs["Fac"], [(0.0, "#4e4e4e"), (0.55, "#ffffff"),
                                        (1.0, "#9a9a9a")], (-800, 120), "seam_shade")
    flat = _ramp(ng, 0.5, [(0.0, base)], (-800, -60), "flat")
    col = _mixc(ng, flat.outputs["Color"], sfac.outputs["Color"], 1.0,
                (-520, 60), "lead", blend="MULTIPLY")
    n = _noise(ng, _combine(ng, u, w, 0.0, (-1200, -240)), 0.9, (-1000, -240),
               detail=3.0, name="patina")
    pat = _ramp(ng, n.outputs["Fac"], [(0.42, dark), (0.62, light)], (-800, -240),
                "patina_c")
    col = _mixc(ng, col, pat.outputs["Color"], 0.25, (-300, 60), "patina",
                blend="MULTIPLY")
    _finish_group(ng, go, col, s.outputs["Fac"])
    return ng, rough


_GROUPS = {}


def _cover_group(kind, pal):
    key = (kind, pal[0], pal[1], pal[2])
    if key in _GROUPS and _GROUPS[key][0].name in bpy.data.node_groups:
        return _GROUPS[key]
    if kind == "lead":
        out = _lead_group(*pal)
    elif kind == "slate":
        out = _slate_group(*pal)
    else:
        out = _clay_group(*pal)
    _GROUPS[key] = out
    return out


# --------------------------------------------------------------- material
def rebuild_material(mat, kind, pal):
    """Rebuild one roof material in place; the name and slots are untouched.

    The cover has to be laid out *in the plane of the roof*, not in object X/Y.
    A roof's fall line is the horizontal part of its normal, so the ridge
    direction is that turned 90 degrees, and the distance down the slope is
    just z divided by the sine of the pitch (which is the length of the normal's
    horizontal part).  Building the pattern from those two coordinates gives one
    projection that is correct for a roof at any angle in plan -- using object
    X/Z instead put the courses at 45 degrees to the ridge on half the houses,
    which read as woven cloth rather than tiles.
    """
    ng, rough = _cover_group(kind, pal)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)

    co = _node(nt, "ShaderNodeTexCoord", (-1400, 0))
    sep = _sepxyz(nt, co.outputs["Object"], (-1200, 0))
    geo = _node(nt, "ShaderNodeNewGeometry", (-1400, -420))
    nsep = _sepxyz(nt, geo.outputs["Normal"], (-1200, -420))

    # horizontal part of the normal: its direction is the fall line, its length
    # is sin(pitch)
    nx = _math(nt, "MULTIPLY", nsep.outputs["X"], nsep.outputs["X"], (-1000, -360))
    ny = _math(nt, "MULTIPLY", nsep.outputs["Y"], nsep.outputs["Y"], (-1000, -480))
    nh = _math(nt, "SQRT", _math(nt, "ADD", nx, ny, (-860, -420)), None,
               (-720, -420))
    # a flat roof has no fall line; keep the divisor away from zero
    nhs = _math(nt, "MAXIMUM", nh, 0.06, (-580, -420))
    hx = _math(nt, "DIVIDE", nsep.outputs["X"], nhs, (-440, -360))
    hy = _math(nt, "DIVIDE", nsep.outputs["Y"], nhs, (-440, -480))

    # u = position along the ridge = dot(xy, perpendicular of the fall line)
    ua = _math(nt, "MULTIPLY", sep.outputs["X"], hy, (-280, 120))
    ub = _math(nt, "MULTIPLY", sep.outputs["Y"], hx, (-280, -20))
    u = _math(nt, "SUBTRACT", ub, ua, (-140, 60))

    # w = distance down the slope; on a vertical wall sin(pitch) is 1, so this
    # degrades to plain z
    nws = _math(nt, "MAXIMUM", nh, 0.30, (-580, -560))
    w = _math(nt, "DIVIDE", sep.outputs["Z"], nws, (-280, -180))

    g = _node(nt, "ShaderNodeGroup", (-20, 120), "cover")
    g.node_tree = ng
    _feed(nt, g.inputs["U"], u)
    _feed(nt, g.inputs["W"], w)

    col = g.outputs["Color"]
    hgt = g.outputs["Height"]
    # the roofs are flat planes, so the relief has to come from the bump: at
    # 0.55/0.035 the barrels and the lap lines were there in the node tree but
    # invisible in the render, and a clay roof read as planked wood
    nrm = _bump(nt, hgt, 1.0 if kind == "clay" else 0.80,
                0.055 if kind == "clay" else 0.030, (320, -60))

    out = _node(nt, "ShaderNodeOutputMaterial", (900, 0))
    b = _node(nt, "ShaderNodeBsdfPrincipled", (640, 0))
    nt.links.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = 0.0
    for key in ("Specular IOR Level", "Specular"):
        if key in b.inputs:
            b.inputs[key].default_value = 0.5 if kind == "slate" else 0.32
    nt.links.new(nrm.outputs["Normal"], b.inputs["Normal"])
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    return mat


def _palette_for(name):
    """Which cover, and which colour, a material name asks for."""
    low = name.lower()
    digits = ""
    for ch in reversed(low):
        if ch.isdigit():
            digits = ch + digits
        else:
            break
    idx = int(digits) if digits else 0
    if "lead" in low:
        return "lead", LEAD[0]
    if "blue" in low or "glazed" in low:
        return "clay", GLAZED[idx % len(GLAZED)]
    if "slate" in low:
        return "slate", SLATE[idx % len(SLATE)]
    if "soot" in low:
        return "clay", CLAY[7]
    if "terra" in low or "tile" in low or "roof" in low:
        return "clay", CLAY[idx % len(CLAY)]
    return None, None


def rebuild(verbose=True, only=None):
    """Fix every roof material in the file, whoever created it."""
    done, failed = [], []
    for mat in list(bpy.data.materials):
        if only and mat.name not in only:
            continue
        low = mat.name.lower()
        if not any(k in low for k in ("roof", "tile", "slate", "lead")):
            continue
        kind, pal = _palette_for(mat.name)
        if kind is None:
            continue
        try:
            rebuild_material(mat, kind, pal)
            done.append("%s:%s" % (mat.name, kind))
        except Exception as exc:                                   # noqa: BLE001
            failed.append("%s(%s: %s)" % (mat.name, type(exc).__name__, exc))
    if verbose:
        print("[roof] rebuilt %d covers, %d failed" % (len(done), len(failed)),
              flush=True)
        if done:
            print("[roof]   " + ", ".join(sorted(done)), flush=True)
        for f in failed:
            print("[roof]   FAILED " + f, flush=True)
    return done, failed


def preview():
    """CLI: build a few test roofs and render them at the gameplay camera."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    specs = [("hu_roof_hd_tile_terra1", "clay", CLAY[1]),
             ("hu_roof_hd_tile_terra4", "clay", CLAY[4]),
             ("hu_roof_hd_tile_slate5", "slate", SLATE[5]),
             ("roof_lead", "lead", LEAD[0])]
    mats = []
    for name, kind, pal in specs:
        mat = bpy.data.materials.new(name)
        rebuild_material(mat, kind, pal)
        mats.append(mat)

    # four little gable roofs in a row, 9 m wide, 45 degrees
    import math
    for i, mat in enumerate(mats):
        cx = (i - 1.5) * 9.5
        w, d, h = 8.0, 8.0, 5.4
        verts, faces = [], []
        # two sloped planes meeting at a ridge along Y
        eave_z = 2.4
        for sgn in (-1, 1):
            verts += [(cx + sgn * w * 0.5, -d * 0.5, eave_z),
                      (cx + sgn * w * 0.5, d * 0.5, eave_z),
                      (cx, d * 0.5, h),
                      (cx, -d * 0.5, h)]
            n = len(verts)
            if sgn < 0:
                faces.append((n - 1, n - 2, n - 3, n - 4))
            else:
                faces.append((n - 4, n - 3, n - 2, n - 1))
        # gable ends
        verts += [(cx - w * 0.5, -d * 0.5, 0.0), (cx + w * 0.5, -d * 0.5, 0.0),
                  (cx, -d * 0.5, h)]
        n = len(verts)
        faces.append((n - 3, n - 2, n - 1))
        verts += [(cx - w * 0.5, d * 0.5, 0.0), (cx + w * 0.5, d * 0.5, 0.0),
                  (cx, d * 0.5, h)]
        n = len(verts)
        faces.append((n - 2, n - 3, n - 1))
        me = bpy.data.meshes.new("roof%d" % i)
        me.from_pydata(verts, [], faces)
        me.validate()
        me.update()
        me.materials.append(mat)
        ob = bpy.data.objects.new("roof%d" % i, me)
        bpy.context.collection.objects.link(ob)

    import hd_light as L
    import hd_sky as SKY
    L.sky("morning_town", 33.0, 112.0)
    SKY.world(bpy.context.scene, "morning_town", elevation=33.0, azimuth=112.0,
              ambient=0.38)
    L.sun("morning_town", 33.0, 112.0)
    L.bounce("morning_town")
    try:
        L.post("morning_town")
    except Exception as exc:                                       # noqa: BLE001
        print("[roof] post skipped: %s" % exc, flush=True)
    bpy.context.scene.view_settings.exposure = -2.20
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 40
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 37.8
    cam_data.sensor_width = 36.0
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.collection.objects.link(cam)
    pitch = math.radians(52.0)
    dist = 34.0
    tgt = (0.0, 0.0, 4.0)
    cam.location = (tgt[0], tgt[1] - dist * math.cos(pitch), tgt[2] + dist * math.sin(pitch))
    cam.rotation_euler = (math.radians(90.0 - 52.0), 0.0, 0.0)
    sc.camera = cam
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(os.path.dirname(here), "renders", "kingdom", "look",
                       "_roof_preview.png")
    sc.render.filepath = out
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("[roof] wrote %s" % out, flush=True)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "preview" in argv:
        preview()
