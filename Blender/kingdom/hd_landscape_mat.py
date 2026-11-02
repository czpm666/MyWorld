"""hd_landscape_mat -- the six shaders the outer landscape is made of.

Every mesh this module's siblings emit is *world space with an identity
transform*, so `Texture Coordinate -> Object` is the world position.  That is
the whole trick behind the materials here: a shader can ask "how far is this
pixel from the city?", "what direction do the furrows run?", "how big is this
feature?" without a UV map anywhere.

The rules taken from the art brief:

  * detail must exist at *three* scales, because the landscape is looked at
    from 1.7 m, from 15 m at a 52 deg pitch, and from 900 m in the aerial;
  * anything that reads as a shape must stand up off the surface, so the third
    scale is a bump, not a colour;
  * far ground is desaturated towards the haze colour, near ground is not.

The materials are always rebuilt from scratch: `bpy.data.materials.get(name)`
returning a material built by an older revision of this file is exactly how
`land_ground` ended up with the paving mortar pattern stuck in it (see the
brief).  Use `_fresh()`.

Called as `import hd_landscape_mat as M; M.build_all(LS)` where LS is the
hd_landscape module (for `_nn` / `_mix` / `_ramp` / `srgb` / `rgb`).
"""
import math

import bpy
import numpy as np

# --------------------------------------------------------------------------- #
#  palette of the landscape shaders
# --------------------------------------------------------------------------- #
HAZE = (0.556, 0.635, 0.722)          # P["haze"] #8ea2b8 -> linear
SOIL = (0.086, 0.043, 0.021)
GRASS_LO = (0.055, 0.085, 0.021)
GRASS_HI = (0.150, 0.190, 0.055)
STONE = (0.190, 0.180, 0.160)
LEAF_LO = (0.021, 0.042, 0.013)
LEAF_HI = (0.085, 0.145, 0.032)


def _fresh(name):
    """A Principled material with an empty node tree, freshly made."""
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    m.use_backface_culling = False
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (1500, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (1200, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    m.diffuse_color = (0.24, 0.28, 0.14, 1.0)
    return m, nt, bsdf


def _pos(nt):
    """World position of the shading point (identity transforms everywhere)."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1700, 0)
    return tc.outputs["Object"]


def _view_dist(nt):
    """Rough distance from the camera, in metres.

    `Texture Coordinate -> Camera` puts the point in camera space, whose Z is
    the (negated) view depth, so |Z| is what we want.  Used only to fade high
    frequency terms that would otherwise sparkle in a 8-sample render.
    """
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1700, -900)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-1500, -900)
    nt.links.new(tc.outputs["Camera"], sep.inputs[0])
    ab = nt.nodes.new("ShaderNodeMath")
    ab.operation = "ABSOLUTE"
    ab.location = (-1350, -900)
    nt.links.new(sep.outputs["Z"], ab.inputs[0])
    return ab.outputs["Value"]


def _noise(nt, vec, scale, detail=4.0, rough=0.55, loc=(-1300, 0), dist=0.0,
           out="Fac"):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.location = loc
    n.inputs["Scale"].default_value = float(scale)
    n.inputs["Detail"].default_value = float(detail)
    n.inputs["Roughness"].default_value = float(rough)
    if "Distortion" in n.inputs:
        n.inputs["Distortion"].default_value = float(dist)
    nt.links.new(vec, n.inputs["Vector"])
    return n.outputs[out]


def _ramp1(nt, fac, lo, hi, pos=(0.42, 0.58), loc=(-1100, 0)):
    """A two-stop colour ramp used as a multiplicative tint."""
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.location = loc
    r.color_ramp.elements[0].position = pos[0]
    r.color_ramp.elements[0].color = (lo[0], lo[1], lo[2], 1.0)
    r.color_ramp.elements[1].position = pos[1]
    r.color_ramp.elements[1].color = (hi[0], hi[1], hi[2], 1.0)
    nt.links.new(fac, r.inputs["Fac"])
    return r


def _mul(nt, a, b, fac=1.0, loc=(-900, 0), blend="MULTIPLY"):
    m = nt.nodes.new("ShaderNodeMixRGB")
    m.blend_type = blend
    m.location = loc
    m.inputs["Fac"].default_value = float(fac)
    nt.links.new(a, m.inputs["Color1"])
    nt.links.new(b, m.inputs["Color2"])
    return m.outputs["Color"]


def _mixc(nt, a, b, fac, loc=(-700, 0)):
    m = nt.nodes.new("ShaderNodeMixRGB")
    m.blend_type = "MIX"
    m.location = loc
    nt.links.new(fac, m.inputs["Fac"])
    nt.links.new(a, m.inputs["Color1"])
    nt.links.new(b, m.inputs["Color2"])
    return m.outputs["Color"]


def _mult(nt, a, fac, loc=(-800, -300)):
    """Multiply a colour by a scalar socket."""
    m = nt.nodes.new("ShaderNodeMixRGB")
    m.blend_type = "MULTIPLY"
    m.location = loc
    m.inputs["Color2"].default_value = (1.0, 1.0, 1.0, 1.0)
    nt.links.new(a, m.inputs["Color1"])
    nt.links.new(fac, m.inputs["Fac"])
    return m


# Radial haze profile: fraction of the sky colour mixed into a surface.
# Radius (m) -> haze.  Read off the value, not the distance: the near apron is
# almost raw, the 2.4-4.7 km massifs sit a quarter of the way into the sky,
# the 9 km wall about two thirds, and anything past 16 km is scenery.
AIR_STOPS = ((0.045, 0.00), (0.165, 0.13), (0.325, 0.38),
             (0.640, 0.70), (1.000, 0.86))
AIR_SCALE = 1.0 / 16000.0

# HAZE is the *sky* colour (#8ea2b8, 0.556 linear).  It cannot be mixed into a
# surface as-is: that is a displayed sky value, and a surface with 0.55 albedo
# under an 88 W sun renders far brighter than the sky behind it.  Mixing toward
# it is what turned every range past 4 km into white plaster.  This is the same
# hue at albedo scale -- still light (a distant mountain must read lighter than
# a near one) but no longer emissive.
HAZE_A = tuple(v * 0.28 for v in HAZE)


def _air(nt, c, pos, loc=(-300, 100), y=0.0):
    """Blend a surface colour toward the haze by distance from the city.

    Keyed to the world radius rather than the camera distance: a radius is
    stable in every shot (aerial, 45 deg, 1.7 m eye level), which is what makes
    the three ranges read as three separate distances instead of one flat
    backdrop that changes every time the camera moves.  Every outdoor material
    goes through this, so trees, walls and ground fade together -- the old
    leaf/stone/track materials had no fade at all, which is why the far
    mountainsides stayed saturated green while the ground under them went pale.
    """
    vlen = nt.nodes.new("ShaderNodeVectorMath")
    vlen.operation = "LENGTH"
    vlen.location = (loc[0] - 620, loc[1] + y + 360)
    nt.links.new(pos, vlen.inputs[0])
    norm = nt.nodes.new("ShaderNodeMath")
    norm.operation = "MULTIPLY"
    norm.location = (loc[0] - 470, loc[1] + y + 420)
    norm.inputs[1].default_value = AIR_SCALE
    nt.links.new(vlen.outputs["Value"], norm.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (loc[0] - 300, loc[1] + y + 360)
    els = ramp.color_ramp.elements
    p0, v0 = AIR_STOPS[0]
    p1, v1 = AIR_STOPS[-1]
    els[0].position, els[0].color = p0, (v0, v0, v0, 1.0)
    els[1].position, els[1].color = p1, (v1, v1, v1, 1.0)
    for p, v in AIR_STOPS[1:-1]:
        e = els.new(p)
        e.color = (v, v, v, 1.0)
    nt.links.new(norm.outputs["Value"], ramp.inputs["Fac"])
    haze = nt.nodes.new("ShaderNodeRGB")
    haze.location = (loc[0] - 380, loc[1] + y + 560)
    haze.outputs[0].default_value = (HAZE_A[0], HAZE_A[1], HAZE_A[2], 1.0)
    return _mixc(nt, c, haze.outputs[0], ramp.outputs["Color"], loc)


# --------------------------------------------------------------------------- #
#  land_ground -- the terrain, and every painted flat surface that is not a crop
# --------------------------------------------------------------------------- #
def mat_ground():
    """Grass / soil / rock / snow, at four scales, with aerial perspective.

    Scale ladder (metres -> feature): 340 field mosaic, 26 grazing patches,
    4.2 clumps, 0.55 single clods.  The last two are bump only.
    """
    m, nt, bsdf = _fresh("land_ground")
    pos = _pos(nt)
    col = nt.nodes.new("ShaderNodeAttribute")
    col.attribute_name = "Col"
    col.location = (-1700, 320)
    dist = _view_dist(nt)

    # --- 1. 340 m: the patchwork of grazing, scrub and soil ------------------
    # These are multipliers, so the range has to be wide or the ground reads as
    # one flat colour from any distance.  Straw-green -> lush is also a hue
    # shift, not just a value shift.
    f1 = _noise(nt, pos, 1.0 / 340.0, 5.0, 0.62, (-1350, 260))
    r1 = _ramp1(nt, f1, (0.68, 0.66, 0.46), (1.14, 1.16, 0.94),
                loc=(-1150, 260))
    far340 = nt.nodes.new("ShaderNodeMapRange")
    far340.location = (-1150, 420)
    far340.inputs["From Min"].default_value = 2500.0
    far340.inputs["From Max"].default_value = 11000.0
    far340.inputs["To Min"].default_value = 0.92
    far340.inputs["To Max"].default_value = 0.42
    nt.links.new(dist, far340.inputs["Value"])
    r1b = _mul(nt, r1.outputs["Color"], far340.outputs["Result"], 1.0,
               (-950, 380), "MULTIPLY")
    c = _mul(nt, col.outputs["Color"], r1b, 0.92, (-950, 300))

    # --- 1b. bare earth breaking through the turf ---------------------------
    f0 = _noise(nt, pos, 1.0 / 96.0, 4.0, 0.60, (-1350, 460))
    soil = _ramp1(nt, f0, (0.44, 0.33, 0.20), (0.90, 0.86, 0.62),
                  pos=(0.60, 0.74), loc=(-1150, 460))
    c = _mul(nt, c, soil.outputs["Color"], 0.55, (-850, 340), "OVERLAY")

    # --- 2. 26 m: hedgerow shade, stock tracks, soil creep -------------------
    # Faded out by 2.2 km.  Past that a 26 m feature is under a pixel, and
    # unfiltered sub-pixel noise is exactly what turned the far range into a
    # grainy green blob in the aerial.
    f2 = _noise(nt, pos, 1.0 / 26.0, 6.0, 0.66, (-1350, -40))
    r2 = _ramp1(nt, f2, (0.74, 0.76, 0.64), (1.16, 1.12, 1.04),
                pos=(0.40, 0.62), loc=(-1150, -40))
    far26 = nt.nodes.new("ShaderNodeMapRange")
    far26.location = (-1150, -200)
    far26.inputs["From Min"].default_value = 700.0
    far26.inputs["From Max"].default_value = 2200.0
    far26.inputs["To Min"].default_value = 1.0
    far26.inputs["To Max"].default_value = 0.0
    nt.links.new(dist, far26.inputs["Value"])
    r2b = _mul(nt, r2.outputs["Color"], far26.outputs["Result"], 1.0,
               (-950, -160), "MULTIPLY")
    c = _mul(nt, c, r2b, 0.86, (-750, 260), "OVERLAY")

    # --- 3. 4.2 m: clumps -- colour up close, faded out past 220 m -----------
    f3 = _noise(nt, pos, 1.0 / 4.2, 4.0, 0.60, (-1350, -340))
    r3 = _ramp1(nt, f3, (0.78, 0.80, 0.66), (1.18, 1.14, 1.02),
                pos=(0.40, 0.62), loc=(-1150, -340))
    near = nt.nodes.new("ShaderNodeMapRange")
    near.location = (-1150, -560)
    near.inputs["From Min"].default_value = 90.0
    near.inputs["From Max"].default_value = 260.0
    near.inputs["To Min"].default_value = 1.0
    near.inputs["To Max"].default_value = 0.0
    nt.links.new(dist, near.inputs["Value"])
    f3b = _mul(nt, r3.outputs["Color"], near.outputs["Result"], 1.0,
               (-950, -340), "MULTIPLY")
    c = _mul(nt, c, f3b, 0.90, (-600, 200), "OVERLAY")

    # --- 4. 0.55 m and 0.14 m: single clods and tussocks -- bump only --------
    f4 = _noise(nt, pos, 1.0 / 0.55, 3.0, 0.55, (-1350, -680))
    f5 = _noise(nt, pos, 1.0 / 0.15, 2.0, 0.50, (-1350, -1080))
    close = nt.nodes.new("ShaderNodeMapRange")
    close.location = (-1350, -900)
    close.inputs["From Min"].default_value = 18.0
    close.inputs["From Max"].default_value = 52.0
    close.inputs["To Min"].default_value = 1.0
    close.inputs["To Max"].default_value = 0.0
    nt.links.new(dist, close.inputs["Value"])
    tighter = nt.nodes.new("ShaderNodeMapRange")
    tighter.location = (-1350, -1200)
    tighter.inputs["From Min"].default_value = 5.0
    tighter.inputs["From Max"].default_value = 22.0
    tighter.inputs["To Min"].default_value = 1.0
    tighter.inputs["To Max"].default_value = 0.0
    nt.links.new(dist, tighter.inputs["Value"])
    f45 = nt.nodes.new("ShaderNodeMixRGB")
    f45.blend_type = "MIX"
    f45.location = (-1150, -1100)
    nt.links.new(tighter.outputs["Result"], f45.inputs["Fac"])
    nt.links.new(f4, f45.inputs["Color1"])
    nt.links.new(f5, f45.inputs["Color2"])
    bumpmix = nt.nodes.new("ShaderNodeMixRGB")
    bumpmix.blend_type = "MIX"
    bumpmix.location = (-1050, -700)
    nt.links.new(close.outputs["Result"], bumpmix.inputs["Fac"])
    nt.links.new(f3, bumpmix.inputs["Color1"])
    nt.links.new(f45.outputs["Color"], bumpmix.inputs["Color2"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.location = (-850, -700)
    bmp.inputs["Strength"].default_value = 0.92
    bmp.inputs["Distance"].default_value = 0.85
    nt.links.new(bumpmix.outputs["Color"], bmp.inputs["Height"])

    # --- slope rock showing through ----------------------------------------
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-1350, 640)
    sepn = nt.nodes.new("ShaderNodeSeparateXYZ")
    sepn.location = (-1150, 640)
    nt.links.new(geo.outputs["Normal"], sepn.inputs[0])
    flat = _ramp1(nt, sepn.outputs["Z"], (0.42, 0.36, 0.30), (1.0, 1.0, 1.0),
                  pos=(0.82, 0.985), loc=(-950, 640))
    c = _mul(nt, c, flat.outputs["Color"], 0.85, (-450, 160), "OVERLAY")

    # No global tone multiply any more.  It used to push every ground pixel
    # green (x0.60 red) to keep clipped meadow from reading as cream; with the
    # desaturated palette the alias is already gone, and the multiply was what
    # turned limestone and snow into olive -- the rock and snow the far range
    # needed to read at all.

    # --- alpine rock, bedding and snow, drawn from world position -----------
    # The vertex colours carry a rough version of this, but only at the
    # terrain grid's 20 m spacing.  Past 3.6 km the ridge rings are 100-200 m
    # apart, so a bedding band sampled that coarsely is noise, not bedding --
    # which is why the far range rendered as one smooth grey clay model with a
    # plaster hat.  Drawn here it has no mesh resolution at all: the same snow
    # line is a hard edge on a 20 m grid or a 200 m one.
    def mr(v, fmin, fmax, tmin=0.0, tmax=1.0, loc=(0, 0)):
        n = nt.nodes.new("ShaderNodeMapRange")
        n.location = loc
        n.clamp = True
        n.inputs["From Min"].default_value = fmin
        n.inputs["From Max"].default_value = fmax
        n.inputs["To Min"].default_value = tmin
        n.inputs["To Max"].default_value = tmax
        nt.links.new(v, n.inputs["Value"])
        return n.outputs["Result"]

    def mt(op, a, b, loc=(0, 0)):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        n.location = loc
        for i, v in enumerate((a, b)):
            if isinstance(v, float) or isinstance(v, int):
                n.inputs[i].default_value = float(v)
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs["Value"]

    pz = nt.nodes.new("ShaderNodeSeparateXYZ")
    pz.location = (-1600, 1080)
    nt.links.new(pos, pz.inputs[0])
    sz = pz.outputs["Z"]
    nz = sepn.outputs["Z"]

    # Rock wants steep faces at any height, and everything above the tree line.
    steep = mr(nz, 0.90, 0.52, 0.0, 1.0, (-1400, 700))
    alt = mt("MULTIPLY", mr(sz, 820.0, 1260.0, 0.0, 1.0, (-1400, 880)),
             0.62, (-1180, 880))
    rockm = mt("MAXIMUM", steep, alt, (-960, 780))

    # Bedding: 330 m period, tipped a few degrees and folded by a 620 m noise,
    # so the bands wander the way a dipping sedimentary face does instead of
    # stripeing the range like a deckchair.
    fold = _noise(nt, pos, 1.0 / 620.0, 3.0, 0.62, (-1600, 1080))
    band = mt("ADD", mt("MULTIPLY", sz, 0.019, (-1420, 1080)),
              mt("MULTIPLY", fold, 3.4, (-1420, 1180)), (-1240, 1080))
    band = mt("SINE", band, 0.0, (-1060, 1080))
    band = mr(band, -1.0, 1.0, 0.0, 1.0, (-880, 1080))
    rockcol = nt.nodes.new("ShaderNodeValToRGB")
    rockcol.location = (-700, 1080)
    els = rockcol.color_ramp.elements
    els[0].position = 0.0
    els[0].color = (0.052, 0.048, 0.042, 1.0)
    els[1].position = 1.0
    els[1].color = (0.196, 0.188, 0.172, 1.0)
    e2 = els.new(0.46)
    e2.color = (0.118, 0.110, 0.098, 1.0)
    e3 = els.new(0.72)
    e3.color = (0.156, 0.146, 0.130, 1.0)
    nt.links.new(band, rockcol.inputs["Fac"])
    c = _mixc(nt, c, rockcol.outputs["Color"], rockm, (-460, 240))

    # Snow: hard line at SNOW_Z with a noisy edge, only on ground that can hold
    # it, so the steepest faces stay bare rock the way a real couloir does.
    snz = mr(sz, 1530.0, 1640.0, 0.0, 1.0, (-1240, 1320))
    snf = mr(nz, 0.30, 0.62, 0.0, 1.0, (-1240, 1460))
    wob = _noise(nt, pos, 1.0 / 340.0, 4.0, 0.70, (-1600, 1340))
    wob = mr(wob, 0.0, 1.0, 0.45, 1.0, (-1240, 1600))
    snowm = mt("MULTIPLY", mt("MULTIPLY", snz, snf, (-1040, 1380)), wob,
               (-860, 1380))
    snowrgb = nt.nodes.new("ShaderNodeRGB")
    snowrgb.location = (-700, 1420)
    snowrgb.outputs[0].default_value = (0.352, 0.366, 0.386, 1.0)
    c = _mixc(nt, c, snowrgb.outputs[0], snowm, (-330, 340))

    # --- aerial perspective -------------------------------------------------
    c = _air(nt, c, pos, (-300, 100))

    nt.links.new(c, bsdf.inputs["Base Color"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.93
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.18
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.18
    return m


# --------------------------------------------------------------------------- #
#  land_crop -- a field: baked crop colour x a shader-drawn furrow pattern
# --------------------------------------------------------------------------- #
def mat_crop():
    """Field soil with ridges.

    Two custom attributes carry the agronomy from the mesh builder:

        Fdir  (r,g,0,0)   cos/sin of the ridge direction, remapped to 0..1
        Fur   (r,g,b,a)   r = ridges per metre, g = strength, b = crop id,
                          a = clod size in metres

    The pattern is a triangle wave across the ridges, so the highlight sits on
    the ridge crest and the shadow in the furrow -- exactly what a 52 deg
    camera sees on a ploughed selion.
    """
    m, nt, bsdf = _fresh("land_crop")
    pos = _pos(nt)
    col = nt.nodes.new("ShaderNodeAttribute")
    col.attribute_name = "Col"
    col.location = (-1700, 380)
    adir = nt.nodes.new("ShaderNodeAttribute")
    adir.attribute_name = "Fdir"
    adir.location = (-1700, 120)
    afur = nt.nodes.new("ShaderNodeAttribute")
    afur.attribute_name = "Fur"
    afur.location = (-1700, -140)
    dist = _view_dist(nt)

    # u = position . dir   (dir is stored as 0..1, decode to -1..1)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-1500, 120)
    nt.links.new(adir.outputs["Color"], sep.inputs[0])
    d2 = nt.nodes.new("ShaderNodeVectorMath")
    d2.operation = "MULTIPLY_ADD"
    d2.location = (-1350, 240)
    nt.links.new(sep.outputs["X"], d2.inputs[0])
    d2.inputs[1].default_value = (2.0, 2.0, 2.0)
    d2.inputs[2].default_value = (-1.0, -1.0, -1.0)
    dx = nt.nodes.new("ShaderNodeSeparateXYZ")
    dx.location = (-1200, 300)
    nt.links.new(d2.outputs["Vector"], dx.inputs[0])
    dy = nt.nodes.new("ShaderNodeSeparateXYZ")
    dy.location = (-1200, 420)
    nt.links.new(d2.outputs["Vector"], dy.inputs[0])

    sxp = nt.nodes.new("ShaderNodeSeparateXYZ")
    sxp.location = (-1500, -60)
    nt.links.new(pos, sxp.inputs[0])
    uu = nt.nodes.new("ShaderNodeMath")
    uu.operation = "MULTIPLY_ADD"
    uu.location = (-1050, 260)
    nt.links.new(sxp.outputs["X"], uu.inputs[0])
    nt.links.new(dx.outputs["X"], uu.inputs[1])
    vv = nt.nodes.new("ShaderNodeMath")
    vv.operation = "MULTIPLY_ADD"
    vv.location = (-1050, 160)
    nt.links.new(sxp.outputs["Y"], vv.inputs[0])
    nt.links.new(dy.outputs["X"], vv.inputs[1])
    nt.links.new(vv.outputs["Value"], uu.inputs[2])
    # u *= ridges per metre
    sfre = nt.nodes.new("ShaderNodeSeparateXYZ")
    sfre.location = (-1500, -300)
    nt.links.new(afur.outputs["Color"], sfre.inputs[0])
    umul = nt.nodes.new("ShaderNodeMath")
    umul.operation = "MULTIPLY"
    umul.location = (-880, 200)
    nt.links.new(uu.outputs["Value"], umul.inputs[0])
    nt.links.new(sfre.outputs["X"], umul.inputs[1])
    # tri wave: abs(frac(u)-0.5)*4-1  ->  -1 furrow, +1 crest
    fr = nt.nodes.new("ShaderNodeMath")
    fr.operation = "FRACT"
    fr.location = (-720, 220)
    nt.links.new(umul.outputs["Value"], fr.inputs[0])
    sub = nt.nodes.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    sub.location = (-570, 220)
    nt.links.new(fr.outputs["Value"], sub.inputs[0])
    sub.inputs[1].default_value = 0.5
    ab = nt.nodes.new("ShaderNodeMath")
    ab.operation = "ABSOLUTE"
    ab.location = (-430, 220)
    nt.links.new(sub.outputs["Value"], ab.inputs[0])
    sg = nt.nodes.new("ShaderNodeMath")
    sg.operation = "MULTIPLY_ADD"
    sg.location = (-290, 220)
    nt.links.new(ab.outputs["Value"], sg.inputs[0])
    sg.inputs[1].default_value = 4.0
    sg.inputs[2].default_value = -1.0

    # break the crest line up lengthwise so it is not a striped shirt
    fclod = _noise(nt, pos, 0.42, 3.0, 0.55, (-1150, -420))
    wob = nt.nodes.new("ShaderNodeMath")
    wob.operation = "MULTIPLY_ADD"
    wob.location = (-150, 220)
    nt.links.new(fclod, wob.inputs[0])
    wob.inputs[1].default_value = 0.55
    nt.links.new(sg.outputs["Value"], wob.inputs[2])

    # ... times strength, faded out where a pixel spans more than a ridge
    stg = nt.nodes.new("ShaderNodeSeparateXYZ")
    stg.location = (-1500, -520)
    nt.links.new(afur.outputs["Color"], stg.inputs[0])
    kfac = nt.nodes.new("ShaderNodeMath")
    kfac.operation = "MULTIPLY"
    kfac.location = (0, 300)
    nt.links.new(wob.outputs["Value"], kfac.inputs[0])
    nt.links.new(stg.outputs["Y"], kfac.inputs[1])
    far = nt.nodes.new("ShaderNodeMapRange")
    far.location = (0, 430)
    # A shader ridge gets no antialiasing, so once it is under a pixel it does
    # not average to its mean -- it turns into black scribble.  The floor was
    # 0.18 at 420 m, which is why the belt went flat from the aerial; it is not
    # safe to raise it either (raising it painted the whole belt in black
    # fans).  The ridge survives to about a kilometre, which is a 1.8 pixel
    # pitch at the 900 m aerial, and past that the *geometry* selions carry the
    # stripes -- real triangles do get filtered.
    far.inputs["From Min"].default_value = 260.0
    far.inputs["From Max"].default_value = 1150.0
    far.inputs["To Min"].default_value = 1.0
    far.inputs["To Max"].default_value = 0.14
    nt.links.new(dist, far.inputs["Value"])
    kf = nt.nodes.new("ShaderNodeMath")
    kf.operation = "MULTIPLY"
    kf.location = (170, 330)
    nt.links.new(kfac.outputs["Value"], kf.inputs[0])
    nt.links.new(far.outputs["Result"], kf.inputs[1])

    # tint: crest lighter and drier, furrow darker and damper
    tint = nt.nodes.new("ShaderNodeMapRange")
    tint.location = (170, 180)
    tint.inputs["From Min"].default_value = -1.0
    tint.inputs["From Max"].default_value = 1.0
    tint.inputs["To Min"].default_value = 0.0
    tint.inputs["To Max"].default_value = 1.0
    nt.links.new(kf.outputs["Value"], tint.inputs["Value"])
    tcol = _ramp1(nt, tint.outputs["Result"],
                  (0.74, 0.76, 0.78), (1.26, 1.21, 1.12),
                  pos=(0.0, 1.0), loc=(340, 180))
    c = _mul(nt, col.outputs["Color"], tcol.outputs["Color"], 1.0, (520, 120))

    # a second, much finer set of drill lines for the near fields only
    dr = nt.nodes.new("ShaderNodeMath")
    dr.operation = "MULTIPLY"
    dr.location = (-880, -180)
    nt.links.new(umul.outputs["Value"], dr.inputs[0])
    dr.inputs[1].default_value = 4.7
    fr2 = nt.nodes.new("ShaderNodeMath")
    fr2.operation = "FRACT"
    fr2.location = (-720, -180)
    nt.links.new(dr.outputs["Value"], fr2.inputs[0])
    s2 = nt.nodes.new("ShaderNodeMath")
    s2.operation = "SUBTRACT"
    s2.location = (-570, -180)
    nt.links.new(fr2.outputs["Value"], s2.inputs[0])
    s2.inputs[1].default_value = 0.5
    a2 = nt.nodes.new("ShaderNodeMath")
    a2.operation = "ABSOLUTE"
    a2.location = (-430, -180)
    nt.links.new(s2.outputs["Value"], a2.inputs[0])
    drill = nt.nodes.new("ShaderNodeMath")
    drill.operation = "MULTIPLY_ADD"
    drill.location = (-290, -180)
    nt.links.new(a2.outputs["Value"], drill.inputs[0])
    drill.inputs[1].default_value = -2.0
    drill.inputs[2].default_value = 1.0

    # bump: crest height = ridge + drill
    hsum = nt.nodes.new("ShaderNodeMath")
    hsum.operation = "MULTIPLY_ADD"
    hsum.location = (520, -260)
    nt.links.new(drill.outputs["Value"], hsum.inputs[0])
    hsum.inputs[1].default_value = 0.22
    nt.links.new(kf.outputs["Value"], hsum.inputs[2])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.location = (700, -260)
    bmp.inputs["Strength"].default_value = 0.55
    bmp.inputs["Distance"].default_value = 0.22
    nt.links.new(hsum.outputs["Value"], bmp.inputs["Height"])

    # aerial perspective, same ramp as the ground
    c = _air(nt, c, pos, (860, 120))

    nt.links.new(c, bsdf.inputs["Base Color"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.95
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.15
    return m


# --------------------------------------------------------------------------- #
#  land_leaf -- foliage, for trees and hedges alike
# --------------------------------------------------------------------------- #
def mat_leaf():
    """Vertex-coloured foliage.

    Foliage reads as a *mass*, not a surface: it needs a shattered normal (so
    the clumps catch light individually) and a little forward scatter so a
    backlit hedge is yellow-green rather than black.  The old trees used
    medkit's `leaf`, which is a flat dark green with nothing to break it up --
    that is why every tree in V24 is a black dot.
    """
    m, nt, bsdf = _fresh("land_leaf")
    pos = _pos(nt)
    col = nt.nodes.new("ShaderNodeAttribute")
    col.attribute_name = "Col"
    col.location = (-1700, 320)
    dist = _view_dist(nt)

    # clump scale: 0.9 m -- each leaf cluster gets its own light
    f1 = _noise(nt, pos, 0.9, 3.0, 0.60, (-1350, 200))
    r1 = _ramp1(nt, f1, (0.62, 0.68, 0.60), (1.34, 1.28, 1.16),
                pos=(0.34, 0.66), loc=(-1150, 200))
    c = _mul(nt, col.outputs["Color"], r1.outputs["Color"], 0.95, (-900, 260))

    # crown scale: 7 m -- one side of a tree in shade, one in sun
    f2 = _noise(nt, pos, 1.0 / 7.0, 2.0, 0.5, (-1350, -120))
    r2 = _ramp1(nt, f2, (0.80, 0.84, 0.86), (1.18, 1.12, 1.04),
                pos=(0.36, 0.64), loc=(-1150, -120))
    c = _mul(nt, c, r2.outputs["Color"], 0.7, (-700, 220), "OVERLAY")

    # upward facing foliage is lighter: cheap stand-in for scatter
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-1350, 640)
    sepn = nt.nodes.new("ShaderNodeSeparateXYZ")
    sepn.location = (-1150, 640)
    nt.links.new(geo.outputs["Normal"], sepn.inputs[0])
    up = _ramp1(nt, sepn.outputs["Z"], (0.58, 0.62, 0.56), (1.16, 1.18, 1.10),
                pos=(0.10, 0.92), loc=(-950, 640))
    c = _mul(nt, c, up.outputs["Color"], 1.0, (-520, 300), "MULTIPLY")

    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.location = (-850, -420)
    bmp.inputs["Strength"].default_value = 0.85
    bmp.inputs["Distance"].default_value = 0.45
    nt.links.new(f1, bmp.inputs["Height"])

    # woods and hedges two kilometres out have to fade with everything else,
    # or the far hillsides stay saturated green under a pale ground
    c = _air(nt, c, pos, (-380, 120), 0.0)
    nt.links.new(c, bsdf.inputs["Base Color"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.78
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.25
    # a trace of emission stands in for light coming through the leaves
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (0.09, 0.13, 0.04, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 0.10
    return m


# --------------------------------------------------------------------------- #
#  land_stone -- dry stone walls, field walls, exposed rock
# --------------------------------------------------------------------------- #
def mat_stone():
    m, nt, bsdf = _fresh("land_stone")
    pos = _pos(nt)
    col = nt.nodes.new("ShaderNodeAttribute")
    col.attribute_name = "Col"
    col.location = (-1700, 320)
    dist = _view_dist(nt)
    # coursing: 0.35 m noise reads as individual stones in a wall
    f1 = _noise(nt, pos, 3.4, 5.0, 0.72, (-1350, 200))
    r1 = _ramp1(nt, f1, (0.56, 0.56, 0.54), (1.30, 1.28, 1.22),
                pos=(0.36, 0.62), loc=(-1150, 200))
    c = _mul(nt, col.outputs["Color"], r1.outputs["Color"], 0.95, (-900, 260))
    f2 = _noise(nt, pos, 0.26, 3.0, 0.6, (-1350, -200))
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.location = (-850, -300)
    bmp.inputs["Strength"].default_value = 1.15
    bmp.inputs["Distance"].default_value = 0.09
    nt.links.new(f2, bmp.inputs["Height"])
    # moss on the top courses
    moss = nt.nodes.new("ShaderNodeNewGeometry")
    moss.location = (-1350, 560)
    sepm = nt.nodes.new("ShaderNodeSeparateXYZ")
    sepm.location = (-1150, 560)
    nt.links.new(moss.outputs["Normal"], sepm.inputs[0])
    mm = _ramp1(nt, sepm.outputs["Z"], (1.0, 1.0, 1.0), (0.68, 0.80, 0.50),
                pos=(0.55, 0.95), loc=(-950, 560))
    c = _mul(nt, c, mm.outputs["Color"], 0.8, (-600, 300), "MULTIPLY")
    c = _air(nt, c, pos, (-380, 120), 0.0)
    nt.links.new(c, bsdf.inputs["Base Color"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.88
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.30
    return m


# --------------------------------------------------------------------------- #
#  land_track -- dirt roads with cart ruts
# --------------------------------------------------------------------------- #
def mat_track():
    """A dirt track: two bright ruts, a swept crown, grit at 0.3 m."""
    m, nt, bsdf = _fresh("land_track")
    pos = _pos(nt)
    col = nt.nodes.new("ShaderNodeAttribute")
    col.attribute_name = "Col"
    col.location = (-1700, 320)
    dist = _view_dist(nt)
    f1 = _noise(nt, pos, 1.6, 5.0, 0.66, (-1350, 180))
    r1 = _ramp1(nt, f1, (0.74, 0.74, 0.72), (1.22, 1.19, 1.12),
                pos=(0.36, 0.64), loc=(-1150, 180))
    c = _mul(nt, col.outputs["Color"], r1.outputs["Color"], 1.0, (-900, 260))
    f2 = _noise(nt, pos, 4.0, 3.0, 0.6, (-1350, -220))
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.location = (-850, -300)
    bmp.inputs["Strength"].default_value = 0.7
    bmp.inputs["Distance"].default_value = 0.06
    nt.links.new(f2, bmp.inputs["Height"])
    c = _air(nt, c, pos, (-380, 120), 0.0)
    nt.links.new(c, bsdf.inputs["Base Color"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.95
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.12
    return m


# --------------------------------------------------------------------------- #
#  land_soil -- bare worked earth: garden beds, plot floors, compost, spoil
# --------------------------------------------------------------------------- #
def mat_soil():
    """Tilled earth that needs no custom attribute at all.

    Everything in the near band that is a box of soil -- a raised bed, the floor
    of a croft, a spoil tip -- is drawn by ``Acc`` with a per-vertex ``Col`` and
    nothing else.  ``land_crop`` wants an ``Fur`` attribute and would read
    pitch 0 there, so the plots came out as flat mauve cards; this material only
    ever asks for the vertex colour and a world-space clod noise.
    """
    m, nt, bsdf = _fresh("land_soil")
    pos = _pos(nt)
    col = nt.nodes.new("ShaderNodeAttribute")
    col.attribute_name = "Col"
    col.location = (-1700, 320)
    dist = _view_dist(nt)
    # 2.6 m clods, 0.34 m crumbs -- both pure albedo
    f1 = _noise(nt, pos, 0.38, 5.0, 0.68, (-1350, 180))
    r1 = _ramp1(nt, f1, (0.62, 0.54, 0.44), (1.30, 1.22, 1.08),
                pos=(0.30, 0.70), loc=(-1150, 180))
    # ...and the contrast is dissolved past 90 m so 8-spp stills do not sparkle
    fade = nt.nodes.new("ShaderNodeMapRange")
    fade.location = (-1160, 20)
    fade.inputs["From Min"].default_value = 24.0
    fade.inputs["From Max"].default_value = 95.0
    fade.inputs["To Min"].default_value = 1.0
    fade.inputs["To Max"].default_value = 0.22
    nt.links.new(dist, fade.inputs["Value"])
    c1 = _mul(nt, col.outputs["Color"], r1.outputs["Color"], 1.0, (-900, 260))
    c = _mixc(nt, c1, col.outputs["Color"], fade.outputs["Result"], (-660, 260))
    f2 = _noise(nt, pos, 2.9, 3.0, 0.6, (-1350, -220))
    f3 = _noise(nt, pos, 0.42, 3.0, 0.55, (-1350, -440))
    f23 = _mul(nt, f2, f3, 0.55, (-1100, -300), blend="MIX")
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.location = (-850, -300)
    bmp.inputs["Strength"].default_value = 0.85
    bmp.inputs["Distance"].default_value = 0.10
    nt.links.new(f23, bmp.inputs["Height"])
    nt.links.new(c, bsdf.inputs["Base Color"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.96
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.10
    return m


# --------------------------------------------------------------------------- #
#  land_prop -- loose things that only have a vertex colour
# --------------------------------------------------------------------------- #
def mat_prop():
    """Hayricks, cordwood, carts and spoil: colour from ``Col`` and nothing else.

    These cannot use ``land_crop`` (it reads ``Fur``) and they must not lean on
    a material borrowed from the city module either, because what that material
    does with vertex colour is not this module's business -- a lab with no city
    loaded then renders every rick as a pale grey egg.  A little world-space
    grain over 0.6 m stops the flat quads looking like paper at arm's length.
    """
    m, nt, bsdf = _fresh("land_prop")
    pos = _pos(nt)
    col = nt.nodes.new("ShaderNodeAttribute")
    col.attribute_name = "Col"
    col.location = (-1700, 320)
    dist = _view_dist(nt)
    f1 = _noise(nt, pos, 0.62, 3.0, 0.60, (-1350, 180))
    r1 = _ramp1(nt, f1, (0.78, 0.76, 0.70), (1.16, 1.12, 1.04),
                pos=(0.30, 0.72), loc=(-1150, 180))
    c1 = _mul(nt, col.outputs["Color"], r1.outputs["Color"], 1.0, (-900, 260))
    fade = nt.nodes.new("ShaderNodeMapRange")
    fade.location = (-1160, 20)
    fade.inputs["From Min"].default_value = 18.0
    fade.inputs["From Max"].default_value = 80.0
    fade.inputs["To Min"].default_value = 1.0
    fade.inputs["To Max"].default_value = 0.25
    nt.links.new(dist, fade.inputs["Value"])
    c = _mixc(nt, c1, col.outputs["Color"], fade.outputs["Result"], (-660, 260))
    nt.links.new(c, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.88
    return m


# --------------------------------------------------------------------------- #
#  land_water -- the river and the mere
# --------------------------------------------------------------------------- #
def mat_water():
    m, nt, bsdf = _fresh("land_water")
    pos = _pos(nt)
    col = nt.nodes.new("ShaderNodeAttribute")
    col.attribute_name = "Col"
    col.location = (-1700, 320)
    # ripples: 3.5 m swell, 0.7 m chop, both as a normal only
    n1 = _noise(nt, pos, 0.28, 4.0, 0.55, (-1350, -260))
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.location = (-950, -260)
    bmp.inputs["Strength"].default_value = 0.22
    bmp.inputs["Distance"].default_value = 0.12
    nt.links.new(n1, bmp.inputs["Height"])
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.14
    for k, v in (("IOR", 1.333), ("Transmission Weight", 0.15)):
        if k in bsdf.inputs:
            bsdf.inputs[k].default_value = v
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.5
    return m


# --------------------------------------------------------------------------- #
def build_all(LS=None):
    """(Re)build every landscape material and return them by short name."""
    M = {
        "ground": mat_ground(),
        "crop": mat_crop(),
        "leaf": mat_leaf(),
        "stone": mat_stone(),
        "track": mat_track(),
        "soil": mat_soil(),
        "prop": mat_prop(),
        "water": mat_water(),
    }
    return M
