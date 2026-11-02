"""hd_paving.py -- the ground, built properly.

Measured with look/matlab.py: the five ground materials (cobble, town_street,
town_ground, flag, earth) all rendered as the same featureless mid-grey beige.
The reason is in the graphs medkit builds -- each is a single Voronoi/Noise
feeding a narrow ramp whose top stop lands around 0.45 linear, and the ramp is
set so almost the whole surface sits on that stop.  So one stone face = one
flat colour, no per-stone variation, no metre-scale wear, and no brightness
separation between road, yard and field.

Half of a 2.5D frame is this surface, so it earns its own module.  Every
material is built from four layers, in the order the eye needs them:

    1. structure -- stones, slabs or earth at real dimensions in metres
    2. per-unit  -- every stone gets its own tint (Voronoi Color / Brick Color)
    3. wear      -- metre-scale patches, dust, damp, moss, polished traffic
    4. relief    -- bump from the joint mask, so a raking sun reads the joints

Coordinates are Object space at 1 m scale, so a 0.16 m sett is 0.16 m on every
object that uses the material (and per-object, so the pattern never repeats
across the town).
"""
import bpy

__all__ = ("rebuild", "MATS")

MATS = ("street", "cobble", "flag", "town_ground", "earth", "grass")


# ---------------------------------------------------------------------------
# node plumbing
# ---------------------------------------------------------------------------
def _srgb(hex_string):
    """'#aabbcc' -> linear rgba (Blender stores socket defaults as linear)."""
    h = hex_string.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


def _nt(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return nt


def _node(nt, kind, name, loc=(0, 0)):
    n = nt.nodes.new(kind)
    n.name = name
    n.label = name
    n.location = loc
    return n


def _co(nt, loc=(-1400, 0)):
    tc = _node(nt, "ShaderNodeTexCoord", "co", loc)
    return tc.outputs["Object"]


def _scale(nt, vec, sx, sy=None, sz=None, loc=(-1200, 0)):
    m = _node(nt, "ShaderNodeMapping", "map_%d" % int(abs(sx * 1000)), loc)
    m.inputs["Scale"].default_value = (sx, sx if sy is None else sy, sx if sz is None else sz)
    nt.links.new(vec, m.inputs["Vector"])
    return m.outputs["Vector"]


def _voronoi(nt, vec, scale, name, feature="F1", rand=1.0, loc=(-1000, 0)):
    v = _node(nt, "ShaderNodeTexVoronoi", name, loc)
    v.feature = feature
    v.distance = "EUCLIDEAN"
    v.inputs["Scale"].default_value = scale
    v.inputs["Randomness"].default_value = rand
    nt.links.new(vec, v.inputs["Vector"])
    return v


def _noise(nt, vec, scale, name, detail=4.0, rough=0.55, loc=(-1000, -260)):
    n = _node(nt, "ShaderNodeTexNoise", name, loc)
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    nt.links.new(vec, n.inputs["Vector"])
    return n


def _brick(nt, vec, w, h, mortar, name, c1="#b9b2a6", c2="#8d8579", loc=(-1000, 0)):
    b = _node(nt, "ShaderNodeTexBrick", name, loc)
    b.offset = 0.42
    b.offset_frequency = 1
    b.squash = 1.0
    b.squash_frequency = 1
    b.inputs["Scale"].default_value = 1.0
    b.inputs["Mortar Size"].default_value = mortar
    b.inputs["Mortar Smooth"].default_value = 0.15
    b.inputs["Bias"].default_value = 0.0
    b.inputs["Brick Width"].default_value = w
    b.inputs["Row Height"].default_value = h
    b.inputs["Color1"].default_value = _srgb(c1)
    b.inputs["Color2"].default_value = _srgb(c2)
    b.inputs["Mortar"].default_value = _srgb("#2b2721")
    nt.links.new(vec, b.inputs["Vector"])
    return b


def _ramp(nt, src, stops, name, loc=(-800, 0), interp="LINEAR"):
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


def _mixc(nt, a, b, fac=None, name="mix", blend="MIX", loc=(-500, 0)):
    """Colour MIX node -> returns the Result colour socket (never an index)."""
    m = _node(nt, "ShaderNodeMix", name, loc)
    m.data_type = "RGBA"
    m.blend_type = blend
    m.clamp_factor = True
    col = [s for s in m.inputs if s.type == "RGBA"]
    nt.links.new(a, col[0])
    nt.links.new(b, col[1])
    if fac is not None:
        f = next(s for s in m.inputs if s.name == "Factor" and s.type == "VALUE")
        if isinstance(fac, (int, float)):
            f.default_value = float(fac)
        else:
            nt.links.new(fac, f)
    return next(s for s in m.outputs if s.type == "RGBA")


def _math(nt, op, a, b=None, name="math", clamp=False, loc=(-500, -320)):
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


def _bw(nt, src, name="bw", loc=(-800, -320)):
    n = _node(nt, "ShaderNodeRGBToBW", name, loc)
    nt.links.new(src, n.inputs["Color"])
    return n.outputs[0]


def _bump(nt, height, strength, distance, loc=(-260, -380)):
    b = _node(nt, "ShaderNodeBump", "bump", loc)
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    nt.links.new(height, b.inputs["Height"])
    return b.outputs["Normal"]


def _finish(nt, color, roughness=0.88, bump=None, spec=0.30, loc=(0, 0)):
    bsdf = _node(nt, "ShaderNodeBsdfPrincipled", "bsdf", loc)
    out = _node(nt, "ShaderNodeOutputMaterial", "out", (loc[0] + 340, loc[1]))
    nt.links.new(color, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = spec
    if bump is not None:
        nt.links.new(bump, bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return bsdf


# ---------------------------------------------------------------------------
# recipes
# ---------------------------------------------------------------------------
def road(mat, base="#6b655a", mortar="#2e2a23", light="#8a8272", dark="#4c473d",
         cell=0.16, joint=0.030, wet="#3f4634"):
    """Carriageway: worn setts, dark wide joints, polished crown.

    The joint is the whole read here.  At the game camera one pixel is 2.5 cm,
    so a 3 cm joint is barely a pixel -- which is exactly why the old material
    dissolved into gravel.  The joint is therefore drawn *wide and dark* and
    given real relief, and the stone faces are lifted well above it, so the
    surface resolves as a chunky mosaic even at 30 m.

    Two Voronoi nodes share one coordinate set so the cells line up: F1 gives
    each sett a random colour, DISTANCE_TO_EDGE gives the joint band.
    """
    nt = _nt(mat)
    co = _co(nt)
    cells = _scale(nt, co, 1.0)
    edge = _voronoi(nt, cells, 1.0 / cell, "sett_edge", feature="DISTANCE_TO_EDGE",
                    rand=0.95, loc=(-1000, -60))
    rnd = _voronoi(nt, cells, 1.0 / cell, "sett_rnd", feature="F1", rand=0.95,
                   loc=(-1000, -360))
    band = max(0.02, min(0.40, (joint * 0.5) / cell))
    joint_mask = _ramp(nt, edge.outputs["Distance"],
                       [(0.0, "#ffffff"), (band, "#000000")], "joint", loc=(-800, -60))
    tint = _bw(nt, rnd.outputs["Color"], "sett_tint", loc=(-800, -360))
    stone = _ramp(nt, tint, [(0.02, dark), (0.28, base), (0.60, light), (0.92, base)],
                  "sett_col", loc=(-620, -320))
    mortar_c = _ramp(nt, tint, [(0.0, mortar), (0.55, darken(mortar, 1.5)),
                                (1.0, mortar)], "mortar_col", loc=(-620, -520))
    col = _mixc(nt, stone.outputs["Color"], mortar_c.outputs["Color"],
                joint_mask.outputs["Color"], "stone_on_mortar", loc=(-420, 0))
    # value structure at two metres and half a metre: without it a street of
    # evenly-lit setts reads as carpet rather than as a place people walk
    broad = _noise(nt, _scale(nt, co, 0.42, loc=(-1200, 120)), 1.0, "broad",
                   detail=3.0, rough=0.55, loc=(-1000, 120))
    broad_r = _ramp(nt, broad.outputs["Fac"],
                    [(0.30, "#8e887c"), (0.52, "#ffffff"), (0.74, "#c9c3b5")],
                    "broad_r", loc=(-800, 120))
    col = _mixc(nt, col, broad_r.outputs["Color"], None, "broad_mix", "MULTIPLY",
                (-300, 40))
    mid = _noise(nt, _scale(nt, co, 2.4, loc=(-1200, -140)), 1.0, "mid",
                 detail=4.0, rough=0.6, loc=(-1000, -140))
    mid_r = _ramp(nt, mid.outputs["Fac"],
                  [(0.34, "#b7b1a4"), (0.60, "#ffffff")], "mid_r", loc=(-800, -140))
    col = _mixc(nt, col, mid_r.outputs["Color"], None, "mid_mix", "MULTIPLY", (-180, 40))
    # metre-scale wear: patches polished pale and patches churned dark
    wear = _noise(nt, _scale(nt, co, 0.34, loc=(-1200, 320)), 1.0, "wear",
                  detail=3.0, rough=0.6, loc=(-1000, 320))
    wear_r = _ramp(nt, wear.outputs["Fac"],
                   [(0.26, "#b3ada0"), (0.52, "#ffffff"), (0.78, "#9e988e")],
                   "wear_r", loc=(-800, 320))
    worn = _mixc(nt, col, wear_r.outputs["Color"], None, "wear_mix", "MULTIPLY", (-240, 60))
    # damp green sits in the joints only, never on the traffic-polished face
    damp = _math(nt, "MULTIPLY", joint_mask.outputs["Color"], 0.45, "damp_amt",
                 loc=(-620, -180))
    fin = _mixc(nt, worn, _rgb(nt, wet, "wet_c", (-620, -160)), damp, "wet_mix", "MIX",
                (-60, 60))
    # relief: joint is a groove, each sett crowns a little
    h = _math(nt, "SUBTRACT", 1.0, joint_mask.outputs["Color"], "relief",
              clamp=True, loc=(-420, -680))
    bump = _bump(nt, h, 0.62, 0.022, loc=(-160, -420))
    _finish(nt, fin, roughness=0.86, bump=bump, spec=0.32)
    return mat


def _rgb(nt, hex_string, name="flat", loc=(-620, 420)):
    n = _node(nt, "ShaderNodeRGB", name, loc)
    n.outputs[0].default_value = _srgb(hex_string)
    return n.outputs[0]


def flagslab(mat, base="#7b736b", mortar="#3b3630", light="#958d82",
             w=0.60, h=0.42, joint=0.024):
    """Plaza paving: rectangular slabs, so the coursing reads as civic work."""
    nt = _nt(mat)
    co = _co(nt)
    b = _brick(nt, co, w, h, joint, "slabs", c1="#a09789", c2="#6a6359")
    # measured, not assumed: Brick 'Fac' is 1 in the MORTAR and 0 on the slab
    # (the doc string says the opposite), so the slab mask has to be inverted
    groove = b.outputs["Fac"]
    stone_m = _math(nt, "SUBTRACT", 1.0, groove, "slab_mask", clamp=True, loc=(-800, 60))
    stone = _ramp(nt, _bw(nt, b.outputs["Color"], "sl_rnd", loc=(-800, -300)),
                  [(0.02, darken(base, 0.66)), (0.35, base), (0.70, light),
                   (1.0, darken(base, 0.88))], "sl_col", loc=(-620, -300))
    col = _mixc(nt, _rgb(nt, mortar), stone.outputs["Color"], stone_m, "slab_col",
                loc=(-440, 0))
    wear = _noise(nt, _scale(nt, co, 0.24, loc=(-1200, 300)), 1.0, "wear",
                  detail=3.0, rough=0.6, loc=(-1000, 300))
    wear_r = _ramp(nt, wear.outputs["Fac"],
                   [(0.30, "#c2bcb0"), (0.58, "#ffffff"), (0.80, "#a8a298")],
                   "wear_r", loc=(-800, 300))
    out = _mixc(nt, col, wear_r.outputs["Color"], None, "wear_mix", "MULTIPLY", (-240, 60))
    # moss creeping out of the joints
    moss_p = _noise(nt, _scale(nt, co, 0.52, loc=(-1200, -560)), 1.0, "moss_p",
                    detail=5.0, rough=0.7, loc=(-1000, -560))
    moss_amt = _math(nt, "MULTIPLY",
                     _ramp(nt, moss_p.outputs["Fac"], [(0.52, "#000000"), (0.74, "#787878")],
                           "moss_amt", loc=(-800, -560)).outputs["Color"],
                     groove, "moss_f", clamp=True, loc=(-600, -600))
    out = _mixc(nt, out, _rgb(nt, "#55633c", "moss_c", (-620, -640)), moss_amt,
                "moss_mix", "MIX", (-60, 60))
    bump = _bump(nt, groove, 0.5, 0.014, loc=(-120, -440))
    _finish(nt, out, roughness=0.80, bump=bump, spec=0.34)
    return mat


def yard(mat, base="#5c5342", dark="#3e382c", light="#7a7059", moss="#4d5734"):
    """Block interior: trodden earth, gravel, straw and moss in the corners.

    This is 60 % of the town's floor area, so its value sets the whole aerial.
    The first pass sat around 0.49 sRGB and, under a 33 deg sun with AgX, every
    courtyard came back as pale sand -- the city read as houses standing on a
    beach.  Trodden earth in a walled town is dark, slightly green and never
    uniform; the road has to stay the *lighter* of the two so it reads as a
    route, which is what the moss and the rubble gates are for.
    """
    nt = _nt(mat)
    co = _co(nt)
    big = _noise(nt, _scale(nt, co, 0.085, loc=(-1200, 140)), 1.0, "patch_big",
                 detail=2.0, rough=0.5, loc=(-1000, 140))
    big_c = _ramp(nt, big.outputs["Fac"],
                  [(0.28, "#3a3529"), (0.46, base), (0.66, light), (0.86, "#8b7f62")],
                  "c_big", loc=(-800, 140))
    mid = _noise(nt, _scale(nt, co, 0.85, loc=(-1200, -120)), 1.0, "patch_mid",
                 detail=4.0, rough=0.6, loc=(-1000, -120))
    mid_l = _ramp(nt, mid.outputs["Fac"],
                  [(0.26, "#3a3529"), (0.50, "#ffffff"), (0.78, "#9c8f72")],
                  "l_mid", loc=(-800, -120))
    lay = _mixc(nt, big_c.outputs["Color"], mid_l.outputs["Color"], 0.52, "mid_mix",
                "MULTIPLY", (-620, 80))
    grain = _noise(nt, _scale(nt, co, 6.0, loc=(-1200, -380)), 1.0, "grain",
                   detail=6.0, rough=0.72, loc=(-1000, -380))
    grain_l = _ramp(nt, grain.outputs["Fac"], [(0.34, "#8b8474"), (0.64, "#ffffff")],
                    "grain_r", loc=(-800, -380))
    lay2 = _mixc(nt, lay, grain_l.outputs["Color"], None, "grain_mix", "MULTIPLY", (-440, 80))
    # gravel: sparse stones, gated by the mid-scale patch so they cluster
    gv = _voronoi(nt, _scale(nt, co, 8.0, loc=(-1200, -640)), 1.0, "gravel", rand=1.0,
                  loc=(-1000, -640))
    gv_tone = _ramp(nt, _bw(nt, gv.outputs["Color"], "gv_rnd", loc=(-800, -640)),
                    [(0.40, "#2e2a23"), (0.72, "#726b5c"), (0.95, "#a49a85")],
                    "gravel_r", loc=(-620, -640))
    gv_gate = _ramp(nt, mid.outputs["Fac"], [(0.42, "#000000"), (0.62, "#ffffff")],
                    "gravel_gate", loc=(-800, -780))
    gv_amt = _math(nt, "MULTIPLY", _ramp(nt, gv_gate.outputs["Color"],
                                         [(0.0, "#000000"), (1.0, "#8a8a8a")],
                                         "gv_amask", loc=(-620, -780)).outputs["Color"],
                   _bw(nt, gv_tone.outputs["Color"], "gv_bw", loc=(-620, -900)),
                   "gv_amt", clamp=True, loc=(-440, -700))
    lay3 = _mixc(nt, lay2, gv_tone.outputs["Color"], gv_amt, "gravel_mix", "MIX", (-260, 80))
    # rubble: trodden yards in a town like this are half buried stone, and that
    # is the only thing at 10-20 cm that survives the 2.5 cm/px sampling
    rub = _voronoi(nt, _scale(nt, co, 5.4, loc=(-1200, -1160)), 1.0, "rubble",
                   feature="F1", rand=1.0, loc=(-1000, -1160))
    rub_m = _ramp(nt, rub.outputs["Distance"], [(0.0, "#ffffff"), (0.26, "#000000")],
                  "rub_mask", loc=(-800, -1160))
    rub_c = _ramp(nt, _bw(nt, rub.outputs["Color"], "rub_rnd", loc=(-800, -1300)),
                  [(0.05, "#2f2b23"), (0.45, "#655e50"), (0.90, "#948b78")],
                  "rub_col", loc=(-620, -1200))
    rub_amt = _math(nt, "MULTIPLY", rub_m.outputs["Color"],
                    _ramp(nt, big.outputs["Fac"], [(0.30, "#3a3a3a"), (0.62, "#8c8c8c")],
                          "rub_gate", loc=(-800, -1440)).outputs["Color"],
                    "rub_amt", clamp=True, loc=(-440, -1280))
    lay4 = _mixc(nt, lay3, rub_c.outputs["Color"], rub_amt, "rubble_mix", "MIX", (-100, 80))
    # moss / damp in shade pockets
    moss_p = _noise(nt, _scale(nt, co, 0.30, loc=(-1200, -1000)), 1.0, "moss_p",
                    detail=5.0, rough=0.62, loc=(-1000, -1000))
    moss_amt = _ramp(nt, moss_p.outputs["Fac"],
                     [(0.46, "#000000"), (0.66, "#6e6e6e")], "moss_amt", loc=(-800, -1000))
    fin = _mixc(nt, lay4, _ramp(nt, moss_p.outputs["Fac"],
                                [(0.52, "#2b3320"), (0.80, moss)], "moss_col",
                                loc=(-800, -880)).outputs["Color"], moss_amt.outputs["Color"],
                "moss_mix", "MIX", (-80, 80))
    h = _math(nt, "ADD", _math(nt, "MULTIPLY", _bw(nt, grain.outputs["Fac"], "hg",
                                                   loc=(-620, -480)), 0.7, "hg1",
                               loc=(-460, -480)),
              _math(nt, "ADD", _math(nt, "MULTIPLY", gv_amt, 0.5, "hg2",
                                     loc=(-460, -600)),
                    _math(nt, "MULTIPLY", rub_amt, 1.2, "hg3", loc=(-460, -1340)),
                    "hg23", loc=(-340, -1340)),
              "h", clamp=True, loc=(-300, -480))
    bump = _bump(nt, h, 0.45, 0.020, loc=(-120, -480))
    _finish(nt, fin, roughness=0.95, bump=bump, spec=0.18)
    return mat


def fieldpath(mat, base="#8a6b46", dark="#54402a", light="#a8875d"):
    """Unmade road outside the walls: earth, wheel ruts, dry grass centre."""
    nt = _nt(mat)
    co = _co(nt)
    big = _noise(nt, _scale(nt, co, 0.115, loc=(-1200, 120)), 1.0, "p_big",
                 detail=2.0, rough=0.5, loc=(-1000, 120))
    big_c = _ramp(nt, big.outputs["Fac"], [(0.30, dark), (0.50, base), (0.74, light)],
                  "c_big", loc=(-800, 120))
    # ruts: noise stretched along the road axis so it streaks lengthwise
    rut = _noise(nt, _scale(nt, co, 4.2, 0.75, 0.75, loc=(-1200, -200)), 1.0, "rut",
                 detail=5.0, rough=0.62, loc=(-1000, -200))
    rut_l = _ramp(nt, rut.outputs["Fac"], [(0.36, "#7b6f58"), (0.62, "#ffffff")], "rut_r",
                  loc=(-800, -200))
    out = _mixc(nt, big_c.outputs["Color"], rut_l.outputs["Color"], None, "rut_mix",
                "MULTIPLY", (-500, 80))
    grit = _noise(nt, _scale(nt, co, 14.0, loc=(-1200, -420)), 1.0, "grit",
                  detail=6.0, rough=0.72, loc=(-1000, -420))
    grit_l = _ramp(nt, grit.outputs["Fac"], [(0.38, "#9a8f79"), (0.68, "#ffffff")],
                   "grit_r", loc=(-800, -420))
    out2 = _mixc(nt, out, grit_l.outputs["Color"], None, "grit_mix", "MULTIPLY", (-300, 80))
    bump = _bump(nt, _bw(nt, grit.outputs["Fac"], "hg", loc=(-500, -420)), 0.30, 0.018,
                 loc=(-120, -420))
    _finish(nt, out2, roughness=0.96, bump=bump, spec=0.16)
    return mat


def grassdry(mat, base="#6f7449", dark="#4c5132", light="#8c8752", straw="#9d8d5c"):
    """Dry summer meadow: straw patches, olive patches, no saturated green."""
    nt = _nt(mat)
    co = _co(nt)
    field = _noise(nt, _scale(nt, co, 0.07, loc=(-1200, 120)), 1.0, "field",
                   detail=3.0, rough=0.55, loc=(-1000, 120))
    field_c = _ramp(nt, field.outputs["Fac"],
                    [(0.26, dark), (0.46, base), (0.68, light), (0.86, straw)],
                    "field_c", loc=(-800, 120))
    tuft = _noise(nt, _scale(nt, co, 2.1, loc=(-1200, -220)), 1.0, "tuft",
                  detail=6.0, rough=0.74, loc=(-1000, -220))
    tuft_l = _ramp(nt, tuft.outputs["Fac"], [(0.32, "#8a8a70"), (0.62, "#efe9cf")],
                   "tuft_r", loc=(-800, -220))
    out = _mixc(nt, field_c.outputs["Color"], tuft_l.outputs["Color"], None, "tuft_mix",
                "MULTIPLY", (-500, 80))
    blade = _noise(nt, _scale(nt, co, 17.0, loc=(-1200, -440)), 1.0, "blades",
                   detail=4.0, rough=0.6, loc=(-1000, -440))
    blade_l = _ramp(nt, blade.outputs["Fac"], [(0.38, "#7f8a5f"), (0.60, "#ffffff")],
                    "blade_r", loc=(-800, -440))
    out2 = _mixc(nt, out, blade_l.outputs["Color"], None, "blade_mix", "MULTIPLY", (-300, 80))
    bump = _bump(nt, _bw(nt, blade.outputs["Fac"], "hb", loc=(-500, -440)), 0.5, 0.03,
                 loc=(-120, -440))
    _finish(nt, out2, roughness=0.94, bump=bump, spec=0.14)
    return mat


def darken(hex_string, mul):
    r, g, b, _ = _srgb(hex_string)
    return (r * mul, g * mul, b * mul, 1.0)


# ---------------------------------------------------------------------------
# public
# ---------------------------------------------------------------------------
def rebuild(MAT, verbose=True):
    """Replace the graph of every ground material in `MAT`, in place.

    Slots are looked up by capital.py's own keys and the material *names* stay
    untouched, so every object that already references them keeps working and
    the FBX export keeps its names.
    """
    plan = (
        ("street", road, dict(base="#5e584d", mortar="#26231d", light="#807869",
                              dark="#3b372f", cell=0.150, joint=0.034)),
        ("cobble", road, dict(base="#665f52", mortar="#2b2822", light="#8a8272",
                              dark="#413c33", cell=0.170, joint=0.036)),
        ("flag", road, dict(base="#6f6860", mortar="#26221c", light="#8d867b",
                            dark="#494439", cell=0.52, joint=0.048)),
        ("town_ground", yard, dict()),
        ("earth", fieldpath, dict()),
        ("grass", grassdry, dict()),
    )
    done = []
    for key, fn, kw in plan:
        mat = MAT.get(key)
        if mat is None or getattr(mat, "node_tree", None) is None:
            if verbose:
                print("[paving] no slot for %r" % (key,), flush=True)
            continue
        try:
            fn(mat, **kw)
            done.append(key)
        except Exception as exc:                                    # noqa: BLE001
            print("[paving] %-12s FAILED: %s: %s" % (key, type(exc).__name__, exc),
                  flush=True)
    if verbose:
        print("[paving] rebuilt %d ground materials: %s"
              % (len(done), ", ".join(done)), flush=True)
    return MAT
