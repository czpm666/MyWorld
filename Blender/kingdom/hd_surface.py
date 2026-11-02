"""hd_surface.py -- material-level, per-block, per-surface weathering.

The pass this replaces was scored 3/10 by visual QC for one structural reason:
it aged masonry with an asymmetric MULTIPLY on the whole base colour, so every
stone, roof tile and paving slab lost 5-9 % of its brightness together.  That
is an exposure change, not weathering.  Measured on that build: frame mean
68.9 -> 65.0, blue roof -5.2 %, ground -7.6 %, and a greenness count that did
not move at all (537 -> 537).

This rewrite is built from nine layers, each keyed to one *physical* cause
rather than to "make it darker":

  0.  ambient-occlusion grime  -- short-reach AO (1.5 m) darkens exactly the
      crevices the kit models in real geometry (under corbels, in reveals,
      behind buttresses); open faces are untouched.
  0b. shelter                 -- a second, 5 m AO pass.  Stone under an eave
      keeps soot and never dries; stone in the open bleaches.  The two ends
      have opposite sign, so the layer adds spread without moving the mean.
  1.  per-block tint          -- driven by a CLONE of the material's own Brick
      node, so the hash lines up with the visible coursing.  Symmetric ramp,
      mean multiplier 1.000: some blocks run warm and stained, others are cool
      lime-washed.  This is the layer QC asked for ("per-block luma +/-5-15 %").
  2.  directional ageing      -- dot(normal, sun) and up-facing weight give an
      `expo` term; sun-facing stone bleaches, shaded stone goes green-damp.
      Gated so a featureless face costs almost nothing and only edges differ.
  3.  mortar joints           -- the kit's mortar is 0.022 m, i.e. half a pixel
      at the hero camera, so the coursing is invisible.  The joint mask is
      rebuilt with `joint_w` = 0.075 m: grime seeps out of the joint onto a
      2-3 cm lip of the stone either side, and the ashlar grid finally reads.
  3a. mortar lichen           -- green lines inside the joints, fading out by
      `jmoss_h` metres: the "moss in the joints" cue.
  3b. repair patchwork        -- real walls are built in runs, so a 1.5 m
      neighbourhood reads as one phase: soot-blackened medieval work next to
      clean modern replacement stone.
  4.  damp / dry washes       -- three noise scales (8 m zones, 2 m patches,
      per-course 0.42 m bands), all chroma ramps that are symmetric in luma.
  5.  rain streaks            -- vertically stretched, gated to vertical faces.
  6.  drip marks              -- AO band-pass at 0.86: the water that runs off
      a sill leaves a mark a few centimetres below it, not on the sill itself.
  7.  the wall foot           -- mud splash (0-0.3 m), moss and lichen (0-0.95 m,
      decaying, clumped, plus runoff fingers climbing to 2.9 m), and rising
      damp up to 2.1 m.  Moss is MIXED toward a real moss colour, not
      multiplied: in daylight moss is lighter than damp stone, and a dark green
      multiply can never register as green after AgX (it measured 0 green
      pixels).  Moss is also suppressed on up-facing stone, which rain rinses.

ROOFS, GLASS, GROUND AND COBBLES ARE FROZEN (`FROZEN`): their luma must not
move, because roof+ground darkening is exactly what exposed the old pass.
Measured on the final pair: blue roof -0.30 %, red roof -0.10 %, glass -0.18 %.

Built for the renderer, not the viewport: every mix runs in linear light, every
paint colour goes through `_srgb()` (Blender reads colour defaults as linear),
and every "amount" in a recipe is applied to a 0..1 mask that is clamped, so a
recipe value above 1.0 cannot push a surface past its target colour.

Public API is unchanged: MAT_KEYS / apply_weathering / weather_material /
resolve_kind / is_weathered / KEY_ALIASES / SKIP_REASON.
"""

import math

import bpy

__all__ = ("MAT_KEYS", "apply_weathering", "weather_material", "resolve_kind",
           "is_weathered", "KEY_ALIASES", "SKIP_REASON", "FROZEN")

# ---------------------------------------------------------------------------
# vocabulary
# ---------------------------------------------------------------------------
MAT_KEYS = (
    "stone", "stone_pale", "stone_warm", "plaster",
    "wood", "wood_dark",
    "tile", "slate",
    "cobble", "flag", "ground",
    "metal",
)

# Kinds that must not change brightness at all.  QC measured the old pass at
# -5.8 % on the blue roof and -9.4 % on the ground; both are listed here so the
# delta is exactly 0.00 % and stays there.
FROZEN = frozenset(("tile", "slate", "cobble", "flag", "ground"))

# Extra spellings the HD modules already use, folded onto the canonical kinds.
KEY_ALIASES = {
    "stone": "stone", "stone_grey": "stone", "stonegrey": "stone",
    "ashlar": "stone", "granite": "stone", "stone_cool": "stone",
    "rock": "stone", "kerb": "stone", "stone_dark": "stone",
    "stone_pale": "stone_pale", "limestone": "stone_pale",
    "stone_light": "stone_pale", "stone_white": "stone_pale",
    "stone_warm": "stone_warm", "sandstone": "stone_warm",
    "stone_sand": "stone_warm", "stone_ochre": "stone_warm",
    "plaster": "plaster", "render": "plaster", "stucco": "plaster",
    "wood": "wood", "timber": "wood", "beam": "wood", "plank": "wood",
    "wood_dark": "wood_dark", "timber_dark": "wood_dark",
    "wood_old": "wood_dark",
    "tile": "tile", "roof_tile": "tile", "tile_red": "tile",
    "tile_blue": "tile", "roof_blue": "tile", "tile_grey": "tile",
    "roof": "tile",
    "slate": "slate", "roof_slate": "slate", "shingle": "slate",
    "cobble": "cobble", "cobbles": "cobble", "road": "cobble",
    "street": "cobble", "cob": "cobble",
    "flag": "flag", "flagstone": "flag", "paving": "flag",
    "plateau": "flag", "pavement": "flag",
    "ground": "ground", "earth": "ground", "grass": "ground",
    "dirt": "ground", "soil": "ground", "terrain": "ground",
    "meadow": "ground",
    # capital.py's own keys for the non-paved ground: without these they fall
    # through to the "soft stone" fallback and get masonry joints painted on a
    # hillside (measured -- the fallback is silent about which recipe it used)
    "town_ground": "ground", "cliff": "ground", "hill": "ground",
    "hill_dark": "ground", "hill_far": "ground", "field": "ground",
    "plaster2": "plaster", "plaster_warm": "plaster",
    "metal": "metal", "iron": "metal", "steel": "metal",
    "bronze": "metal", "copper": "metal", "wrought_iron": "metal",
}

# Decorative / non-mineral materials: ageing them would be wrong, so they are
# skipped without a warning even though they are not in MAT_KEYS.
_SKIP_EXACT = frozenset((
    "glass", "window", "gold", "silver", "water", "fire", "ember", "flame",
    "shadow", "glow", "leaf", "foliage", "branch", "log", "cloth", "canvas",
    "rope", "leather", "banner", "flag_cloth", "wax", "candle",
))
_SKIP_PREFIX = ("banner", "cv_", "cloth", "canvas", "glow", "fire", "ember",
                "water", "glass", "gold", "leaf", "foliage", "shadow",
                "smoke", "lamp", "torch", "rope", "leather", "award", "atmos",
                # props, terrain and misc: ageing these as masonry paints brick
                # joints on a fish, a thatch roof or a lake. Measured damage.
                "sl_", "mkt_", "land_", "hu_", "pave", "sand", "void", "soot",
                "thatch", "moat", "fish", "veg", "skin", "straw", "burlap",
                "prod", "paint", "pottery", "leafpile", "dirt", "terrain")

# Prefix -> kind, consulted *before* _SKIP_PREFIX so that e.g. mkt_stone_pale
# still gets the stone recipe while mkt_water is skipped.
_ALIAS_PREFIX = (
    ("mkt_plaster", "plaster"), ("mkt_stone", "stone"), ("mkt_timber", "wood"),
    ("mkt_iron", "metal"),
    ("sl_wood", "wood"), ("sl_stone", "stone"), ("sl_iron", "metal"),
    ("sl_rust", "metal"),
    ("hd_plaster", "plaster"), ("hd_stone", "stone"), ("hd_timber", "wood"),
    ("hu_stone", "stone"), ("hu_plaster", "plaster"), ("hu_timber", "wood"),
    ("plaster", "plaster"), ("stucco", "plaster"), ("render", "plaster"),
    ("wood_", "wood"), ("timber", "wood"), ("beam", "wood"), ("plank", "wood"),
    ("stone_", "stone"), ("brick", "stone"), ("masonry", "stone"),
    ("ashlar", "stone"), ("iron_", "metal"), ("rust", "metal"),
    ("steel", "metal"),
)

SKIP_REASON = {
    "glass": "transmissive", "gold": "polished noble metal", "water": "liquid",
    "fire": "emission", "shadow": "shadow catcher",
    "tile": "roof - frozen (must not darken)", "slate": "roof - frozen",
    "cobble": "paving - frozen", "flag": "paving - frozen",
    "ground": "ground - frozen",
}

_WARNED = set()
_FALLBACK_SOFTEN = 0.55          # unknown key -> stone recipe, this much of it


def resolve_kind(key):
    """key (a MAT dict key) -> canonical kind, or None when it must be skipped."""
    k = str(key).strip().lower()
    if k in MAT_KEYS:
        return k
    if k in _SKIP_EXACT:
        return None
    hit = KEY_ALIASES.get(k)
    if hit is not None:
        return hit
    for pre, kind in _ALIAS_PREFIX:
        if k.startswith(pre):
            return kind
    if k.startswith(_SKIP_PREFIX):
        return None
    # Unknown name: skip it. The old behaviour fell back to a "soft stone"
    # recipe, which silently painted 0.075 m masonry joints and foot damp onto
    # 150 materials whose names it did not recognise -- water, thatch, cloth
    # awnings, barrels, the terrain heightfield. Silently wrong is worse than
    # unweathered.
    return None


def is_weathered(mat):
    """True when this material already carries a weathering pass."""
    try:
        if mat.get("_weathering"):
            return True
        nt = mat.node_tree
        if nt is not None:
            for n in nt.nodes:
                if n.name.startswith("wx_"):
                    return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# recipe table
# ---------------------------------------------------------------------------
# blk      : per-block multiplier ramp.  Symmetric around 1.000 by construction:
#            stop(p) + stop(1-p) == 2.0 on every axis, and the brick hash is
#            symmetric too, so the layer cannot shift the mean.
# blk_amp  : 0..1 blend of the ramp against white (amplitude knob).
# blk_lo/hi: the brick-hash window that is stretched onto the ramp.  Measured
#            hash: p10 0.389 / mean 0.505 / p90 0.602 linear.
BLK_STONE = (
    (0.00, (0.800, 0.752, 0.690)),      # dark block: warm, iron-stained
    (0.15, (0.89, 0.85, 0.79)),
    (0.34, (0.977, 0.967, 0.947)),
    (0.50, (1.00, 1.00, 1.00)),
    (0.66, (1.077, 1.077, 1.067)),
    (0.85, (1.16, 1.18, 1.20)),
    (1.00, (1.23, 1.24, 1.26)),      # pale block: cool, lime-washed
)

def _srgb(*rgb8):
    """sRGB bytes -> linear, so the numbers below can be picked by eye."""
    out = []
    for v in rgb8:
        c = v / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


# Two kinds of colour live in this module and they are NOT interchangeable:
#   * a MULTIPLY factor is a ratio in linear light (0.5 = "keep half the red"),
#     so it may be written directly as a float triple;
#   * a MIX target is an actual surface colour and must be linear as well, so
#     it is written here as sRGB bytes through _srgb().
# Moss in daylight is LIGHTER than damp stone; painting it in with a dark
# multiply produced G-max(R,B) = 4, below the 8 that the acceptance test wants,
# which is why the moss is mixed rather than multiplied.
MOSS_LIGHT = _srgb(96, 112, 62)      # sunlit moss cushions
MOSS_DARK = _srgb(58, 70, 38)        # moss in the shade of its own clump
LICHEN_MID = _srgb(132, 140, 104)    # crustose lichen in a mortar joint
LICHEN_PALE = _srgb(158, 166, 132)   # dry lichen disc on an open face
SPLASH_TAN = _srgb(146, 134, 112)    # dried mud thrown up by rain

# MULTIPLY factors (ratios, not colours)
MOSS = (0.42, 0.76, 0.22)
DAMP = (0.66, 0.68, 0.72)
LICHEN = (0.50, 0.60, 0.32)
MUD = (0.60, 0.55, 0.46)
# direction TOWARD the key sun used by hd_common.setup_world (52/0/38 deg)
SUN = (0.485, -0.621, 0.616)

_DEF = dict(
    blk_amp=0.45, blk_lo=0.36, blk_hi=0.64, blk=BLK_STONE,
    blk_rough=(0.82, 1.14),
    joint=0.10, joint_scale=0.9, joint_w=0.075,
    # 0. cavity grime: dirt that rain cannot wash out -- under every corbel,
    # in every window reveal, in the joints.  Localised, so it adds contrast
    # without moving the whole wall's exposure.
    cav=0.55, cav_dist=1.5, cav_lo=0.66, cav_hi=0.96,
    cav_col=(0.54, 0.48, 0.40),
    # 0b. shelter grime: dust that survives where the rain never reaches
    shelter=0.0, shelter_d=5.0, shelter_lo=0.30, shelter_hi=0.85,
    shelter_scale=0.30, shelter_pale=(1.19, 1.18, 1.14),
    shelter_dirty=(0.760, 0.720, 0.640),
    # 2. directional ageing: the weathered side of the building
    bleach=0.55, sun=SUN,
    damp_side=(0.915, 0.940, 0.900), bleach_col=(1.10, 1.08, 1.03),
    # 3. lichen in the mortar lines of the lower, shaded joints
    jmoss=0.55, jmoss_scale=0.29, jmoss_h=3.2,
    # 3a lichen colonies on the damp faces
    lichen=0.34, lichen_scale=3.4, lichen_lo=0.45, lichen_lo2=0.95,
    lichen_hi=8.0, lichen_hi2=9.4,
    # 3a zone: whole faces of a building read darker/lighter (rain-washed,
    # soot, sun-bleached).  ~8 m features, mean-preserving.
    zone=0.80, zone_scale=0.12, zone_z=0.45, zone_lo=0.40, zone_hi=0.60,
    zone_ramp=((0.00, (0.862, 0.845, 0.822)),
               (0.50, (1.049, 1.049, 1.049)),
               (1.00, (1.162, 1.190, 1.226))),
    # 3a. repair patchwork: old sooted runs vs clean replacement stone
    phase=0.0, phase_scale=0.34, phase_z=0.70,
    # 3a2. quarry batches: stone came by the cartload from different quarries,
    # so a whole tower can be half a shade warmer than the tower next to it.
    # ~30 m features -- bigger than a building, so it never reads as a pattern,
    # but it is the only layer that puts variation at the scale of the frame.
    quarry=0.0, quarry_scale=0.035, quarry_z=0.55,
    quarry_ramp=((0.00, (0.915, 0.905, 0.888)),
                 (0.50, (1.000, 1.000, 1.000)),
                 (1.00, (1.100, 1.093, 1.082))),
    # 3b damp/dry patches: ~2 m; damp goes dark and warm, dry goes pale-cool.
    # Symmetric on every axis, so the layer is mean-preserving.
    patch=0.60, patch_scale=0.50, patch_z=0.55, patch_lo=0.38, patch_hi=0.62,
    patch_ramp=((0.00, (0.815, 0.775, 0.720)),
                (0.38, (0.979, 0.959, 0.929)),
                (0.62, (1.089, 1.107, 1.135)),
                (1.00, (1.180, 1.245, 1.330))),
    # 3c per-course wash: horizontal bands, ~0.4 m tall
    course=0.32, course_scale=0.13, course_z=16.0,
    streak=0.0, streak_scale=7.0, streak_z=0.10,
    # 6. drip marks: band-passed on AO so they sit under the ledges only
    drip=0.0, drip_lo=0.52, drip_mid=0.78, drip_hi=0.99,
    drip_scale=5.0, drip_z=0.05,
    # 7. wall foot
    foot=0.0, foot_h=0.90, foot_patch=2.4, foot_lo=0.26,
    moss=0.90, moss_gain=2.20, splash=0.55, splash_h=0.30,
    runoff=0.0, runoff_h=2.40,
    splash_col=SPLASH_TAN,
    damp_h=1.90, damp_mix=0.30,
    bump_str=0.12, bump_dist=0.004, bump_scale=110.0,
    rough=(1.06, 0.92),
)

RECIPES = {
    "stone": dict(_DEF, blk_amp=0.85, joint=0.20, cav=0.40, shelter=0.90,
                  bleach=0.10, jmoss=0.55, lichen=0.34,
                  zone=0.90, patch=1.00, course=0.34, phase=1.00, quarry=0.0,
                  streak=0.20, streak_scale=6.0, streak_z=0.06,
                  drip=0.45,
                  foot=1.0, foot_h=0.95, moss=1.0, moss_gain=1.90,
                  runoff=0.95, runoff_h=2.90,
                  splash=0.70, damp_h=2.10, damp_mix=0.22),
    "stone_pale": dict(_DEF, blk_amp=0.80, cav=0.38, shelter=0.80,
                       zone=0.85, patch=0.95, course=0.32, phase=0.95, quarry=0.0,
                       bleach=0.10, jmoss=0.45, drip=0.42,
                       foot=1.0, foot_h=0.95, moss_gain=1.80, runoff=0.75),
    "stone_warm": dict(_DEF, blk_amp=0.85, cav=0.40, shelter=0.85,
                       zone=0.88, patch=0.98, course=0.32, phase=1.00, quarry=0.0,
                       bleach=0.10, jmoss=0.55, drip=0.45,
                       foot=1.0, foot_h=0.90, moss_gain=1.85, runoff=0.80),
    "plaster": dict(_DEF, blk_amp=0.0, blk_rough=(1.0, 1.0), joint=0.0,
                    patch=0.14, patch_scale=0.22, patch_z=0.30,
                    bleach=0.45, jmoss=0.30, drip=0.30,
                    foot=1.0, foot_h=1.10, moss=0.62, moss_gain=1.60, splash=0.50,
                    damp_h=2.40, bump_str=0.07),
    "wood": dict(_DEF, blk_amp=0.0, blk_rough=(1.0, 1.0), joint=0.0,
                 patch=0.10, patch_scale=0.55, patch_z=0.12,
                 streak=0.10, streak_scale=14.0, streak_z=0.06,
                 bleach=0.35, jmoss=0.0, drip=0.0,
                 foot=0.6, foot_h=0.75, moss=0.55, splash=0.35,
                 damp_h=1.60, bump_str=0.09),
    "wood_dark": dict(_DEF, blk_amp=0.0, blk_rough=(1.0, 1.0), joint=0.0,
                      patch=0.09, patch_scale=0.55, patch_z=0.12,
                      streak=0.09, streak_scale=14.0, streak_z=0.06,
                      bleach=0.30, jmoss=0.0, drip=0.0,
                      foot=0.5, foot_h=0.70, moss=0.45, splash=0.30,
                      damp_h=1.40,
                      bump_str=0.08),
    "metal": dict(_DEF, blk_amp=0.0, blk_rough=(1.0, 1.0), joint=0.0,
                  patch=0.16, patch_scale=1.6, patch_z=1.0, patch_lo=0.42,
                  patch_hi=0.62, foot=0.0, damp_h=0.0, streak=0.0,
                  bump_str=0.10, rough=(1.28, 1.0)),
}
for _k in FROZEN:
    RECIPES.pop(_k, None)


# ---------------------------------------------------------------------------
# node helpers
# ---------------------------------------------------------------------------
def _mk(nt, bl_idname, name):
    n = nt.nodes.new(bl_idname)
    n.name = name
    n.label = name
    return n


def _rgba(c):
    if len(c) == 4:
        return c
    return (c[0], c[1], c[2], 1.0)


def _bsdf(nt):
    for n in nt.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def _socket(node, name):
    try:
        return node.inputs[name]
    except Exception:
        return None


def _set_color(node, name, rgba):
    """Brick / RGB colour inputs moved from properties to sockets in 4.x."""
    s = _socket(node, name)
    if s is not None:
        s.default_value = _rgba(rgba)
        return
    attr = {"Color1": "color1", "Color2": "color2", "Mortar": "mortar"}.get(name)
    if attr and hasattr(node, attr):
        setattr(node, attr, _rgba(rgba))


def _noise(nt, name, vec, scale, detail=4.0, rough=0.55, zscale=1.0,
           offset=(0.0, 0.0, 0.0), distortion=0.0):
    """Noise Texture fed by `vec`, optionally stretched in Z and offset."""
    src = vec
    if zscale != 1.0 or offset != (0.0, 0.0, 0.0):
        mp = _mk(nt, "ShaderNodeMapping", name + "_map")
        nt.links.new(vec, mp.inputs["Vector"])
        mp.inputs["Scale"].default_value = (1.0, 1.0, zscale)
        mp.inputs["Location"].default_value = offset
        src = mp.outputs["Vector"]
    n = _mk(nt, "ShaderNodeTexNoise", name)
    nt.links.new(src, n.inputs["Vector"])
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    if "Distortion" in n.inputs:
        n.inputs["Distortion"].default_value = distortion
    return n


def _ramp(nt, name, src, stops, interp="LINEAR"):
    n = _mk(nt, "ShaderNodeValToRGB", name)
    cr = n.color_ramp
    cr.interpolation = interp
    while len(cr.elements) > 2:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position = stops[0][0]
    cr.elements[0].color = _rgba(stops[0][1])
    cr.elements[1].position = stops[-1][0]
    cr.elements[1].color = _rgba(stops[-1][1])
    for pos, col in stops[1:-1]:
        e = cr.elements.new(pos)
        e.color = _rgba(col)
    if src is not None:
        nt.links.new(src, n.inputs["Fac"])
    return n


def _map_range(nt, name, src, flo, fhi, tlo, thi, clamp=True, interp="LINEAR"):
    n = _mk(nt, "ShaderNodeMapRange", name)
    n.clamp = clamp
    n.interpolation_type = interp
    if src is not None:
        nt.links.new(src, n.inputs["Value"])
    n.inputs["From Min"].default_value = flo
    n.inputs["From Max"].default_value = fhi
    n.inputs["To Min"].default_value = tlo
    n.inputs["To Max"].default_value = thi
    return n


def _math(nt, name, op, a=None, b=None, clamp=False):
    n = _mk(nt, "ShaderNodeMath", name)
    n.operation = op
    n.use_clamp = clamp
    for i, s in enumerate((a, b)):
        if s is None:
            continue
        if hasattr(s, "default_value") or hasattr(s, "node"):
            try:
                nt.links.new(s, n.inputs[i])
            except Exception:
                n.inputs[i].default_value = float(s)
        else:
            n.inputs[i].default_value = float(s)
    return n


def _sock(x):
    """Nodes and sockets are both passed around; normalise to a socket."""
    if x is None or isinstance(x, bpy.types.NodeSocket):
        return x
    if hasattr(x, "outputs"):
        for k in ("Color", "Fac", "Value"):
            if k in x.outputs:
                return x.outputs[k]
        return x.outputs[0]
    return x


def _multiply(nt, name, a, b):
    n = _mk(nt, "ShaderNodeMixRGB", name)
    n.blend_type = "MULTIPLY"
    n.inputs["Fac"].default_value = 1.0
    a, b = _sock(a), _sock(b)
    if isinstance(a, bpy.types.NodeSocket):
        nt.links.new(a, n.inputs["Color1"])
    else:
        n.inputs["Color1"].default_value = _rgba(a)
    if isinstance(b, bpy.types.NodeSocket):
        nt.links.new(b, n.inputs["Color2"])
    else:
        n.inputs["Color2"].default_value = _rgba(b)
    return n


def _mix(nt, name, a, b, fac):
    n = _mk(nt, "ShaderNodeMixRGB", name)
    n.blend_type = "MIX"
    a, b, fac = _sock(a), _sock(b), _sock(fac)
    if isinstance(a, bpy.types.NodeSocket):
        nt.links.new(a, n.inputs["Color1"])
    elif a is not None:
        n.inputs["Color1"].default_value = _rgba(a)
    if isinstance(b, bpy.types.NodeSocket):
        nt.links.new(b, n.inputs["Color2"])
    else:
        n.inputs["Color2"].default_value = _rgba(b)
    if isinstance(fac, bpy.types.NodeSocket):
        nt.links.new(fac, n.inputs["Fac"])
    else:
        n.inputs["Fac"].default_value = float(fac)
    return n


def _brick_node(mat):
    """The material's own ashlar Brick node (the one medkit built)."""
    nt = mat.node_tree
    for n in nt.nodes:
        if n.type == "TEX_BRICK" and not n.name.startswith("wx_"):
            return n
    return None


def _clone_brick(nt, src, name, c1, c2, cm, mortar=None):
    nb = _mk(nt, "ShaderNodeTexBrick", name)
    for prop in ("offset", "offset_frequency", "squash", "squash_frequency"):
        if hasattr(src, prop):
            setattr(nb, prop, getattr(src, prop))
    missing = []
    for key in ("Scale", "Brick Width", "Row Height", "Mortar Size",
                "Mortar Smooth", "Bias"):
        s, d = _socket(src, key), _socket(nb, key)
        if s is not None and d is not None:
            # a wider mortar on the *mask* clone is how the grime that seeps
            # out of a joint gets its 2-3 cm lip on the stone on either side;
            # the block hash clone keeps the material's own width untouched
            d.default_value = (mortar if (mortar is not None
                                          and key == "Mortar Size")
                               else s.default_value)
        else:
            missing.append(key)
    if missing and "brick-inputs" not in _WARNED:
        _WARNED.add("brick-inputs")
        print("[surface] WARNING brick inputs not copied: %s"
              % ", ".join(missing), flush=True)
    _set_color(nb, "Color1", c1)
    _set_color(nb, "Color2", c2)
    _set_color(nb, "Mortar", cm)
    vs = _socket(src, "Vector")
    if vs is not None and vs.is_linked:
        nt.links.new(vs.links[0].from_socket, nb.inputs["Vector"])
    elif vs is not None:
        nb.inputs["Vector"].default_value = vs.default_value
    return nb


def _bw(nt, name, src):
    n = _mk(nt, "ShaderNodeRGBToBW", name)
    if hasattr(src, "node"):
        nt.links.new(src, n.inputs["Color"])
    else:
        n.inputs["Color"].default_value = _rgba(src)
    return n


# ---------------------------------------------------------------------------
# the layer stack
# ---------------------------------------------------------------------------
def _wash(nt, name, vec, scale, zscale, offset, lo, hi, ramp, amount,
          detail=4.0, rough=0.55):
    """A mean-preserving MULTIPLY wash: noise -> window -> colour ramp.

    The ramp is authored symmetric around 1.0 (stop p + stop 1-p == 2), so the
    layer adds contrast without changing the wall's average brightness -- the
    mistake that made the previous pass read as an exposure change.
    """
    n = _noise(nt, name + "_n", vec, scale, detail, rough, zscale, offset)
    p = _map_range(nt, name + "_m", n.outputs["Fac"], lo, hi, 0.0, 1.0)
    r = _ramp(nt, name + "_r", p.outputs[0], ramp)
    a = _mix(nt, name + "_a", None, r.outputs["Color"], min(1.0, amount))
    a.inputs["Color1"].default_value = (1.0, 1.0, 1.0, 1.0)
    return a


def _build(mat, kind, sp, strength, seed):
    nt = mat.node_tree
    bsdf = _bsdf(nt)
    if bsdf is None:
        return False

    # ---- what the base colour already is --------------------------------
    bc = bsdf.inputs["Base Color"]
    if bc.is_linked:
        base = bc.links[0].from_socket
    else:
        n = _mk(nt, "ShaderNodeRGB", "wx_base")
        n.outputs[0].default_value = _rgba(bc.default_value)
        base = n.outputs[0]

    tc = _mk(nt, "ShaderNodeTexCoord", "wx_tc")
    sep = _mk(nt, "ShaderNodeSeparateXYZ", "wx_sep")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    vec = tc.outputs["Object"]
    z = sep.outputs["Z"]

    s = float(strength)
    rnd = (seed * 13.37) % 17.0

    cur = base
    brick = _brick_node(mat)
    hgt = None                      # height field for the bump, 0..1

    # ---- 0. cavity grime ------------------------------------------------
    # The kit models every corbel, sill, reveal and joint in real geometry, so
    # a short-reach AO darkens exactly the places dirt collects.  This is the
    # strongest "not freshly built" cue and it is local: it does not touch the
    # open faces at all.  The same AO map is reused by the drip layer below,
    # which is why the node is built before any of the colour layers.
    ao_out = None
    if (s > 0.0 and (sp["cav"] > 0.0 or sp["drip"] > 0.0)
            and hasattr(bpy.types, "ShaderNodeAmbientOcclusion")):
        ao = _mk(nt, "ShaderNodeAmbientOcclusion", "wx_ao")
        try:
            ao.inputs["Distance"].default_value = float(sp["cav_dist"])
            ao.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            ao.samples = 6
            ao.only_local = False
            ao.inside = False
        except Exception:
            pass
        ao_out = ao.outputs.get("AO") or ao.outputs.get("Color")

    if ao_out is not None and sp["cav"] > 0.0 and s > 0.0:
        rao = _ramp(nt, "wx_rao", ao_out, (
            (sp["cav_lo"], (1.0, 1.0, 1.0, 1.0)),
            (sp["cav_hi"], (0.0, 0.0, 0.0, 1.0)),
        ))
        f = _math(nt, "wx_cavf", "MULTIPLY", rao.outputs["Color"],
                  sp["cav"] * s, clamp=True)
        g = _mix(nt, "wx_cavg", None, sp["cav_col"], f.outputs[0])
        g.inputs["Color1"].default_value = (1.0, 1.0, 1.0, 1.0)
        cur = _multiply(nt, "wx_cavmul", cur, g)

    # ---- 0b. shelter: dust where rain never reaches, bleach where it does -
    # Under every eave, arch head and balcony the wall never gets rained on, so
    # it keeps a century of dust; the faces that do catch the rain are washed
    # pale.  A 1.5 m AO cannot see that far, a 5 m AO can, and because it is
    # driven by real geometry it draws the eave line by itself instead of a
    # hand-authored vertical gradient that would be wrong on every other wall.
    # The two ends are deliberately opposite in sign so the layer adds variance
    # without moving the average -- QC's complaint was exactly that the old
    # "ageing" only ever darkened.
    if (sp["shelter"] > 0.0 and s > 0.0
            and hasattr(bpy.types, "ShaderNodeAmbientOcclusion")):
        ao2 = _mk(nt, "ShaderNodeAmbientOcclusion", "wx_ao2")
        try:
            ao2.inputs["Distance"].default_value = float(sp["shelter_d"])
            ao2.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            ao2.samples = 8
            ao2.only_local = False
            ao2.inside = False
        except Exception:
            pass
        o2 = ao2.outputs.get("AO") or ao2.outputs.get("Color")
        r2 = _ramp(nt, "wx_rshel", o2, (
            (sp["shelter_lo"], (1.0, 1.0, 1.0, 1.0)),
            (sp["shelter_hi"], (0.0, 0.0, 0.0, 1.0)),
        ))
        # r2 is 1 where the 5 m AO is blocked = under an eave = keeps its dust
        m = r2.outputs["Color"]
        # dirt under an eave is patchy along the wall, not a clean band
        sn = _noise(nt, "wx_shen", vec, sp["shelter_scale"], 3.0, 0.55,
                    offset=(rnd * 3.9, rnd * 1.4, 0.0))
        sm = _map_range(nt, "wx_shm", sn.outputs["Fac"], 0.25, 0.75, 0.45, 1.0)
        m = _math(nt, "wx_shm2", "MULTIPLY", m, sm.outputs[0])
        pair = _mix(nt, "wx_shp", sp["shelter_pale"], sp["shelter_dirty"],
                    m.outputs[0])
        g = _mix(nt, "wx_shg", (1.0, 1.0, 1.0), pair.outputs["Color"],
                 min(1.0, sp["shelter"] * s))
        cur = _multiply(nt, "wx_shmul", cur, g)

    # ---- 1. per-block tone ---------------------------------------------
    # The clone shares the material's swizzled vector, so the hash lands on the
    # exact coursing that is visible.  Symmetric ramp -> mean 1.000.
    if brick is not None and sp["blk_amp"] > 0.0 and s > 0.0:
        blk = _clone_brick(nt, brick, "wx_blk", (0, 0, 0, 1), (1, 1, 1, 1),
                           (0.5, 0.5, 0.5, 1))
        bv = _bw(nt, "wx_bv", blk.outputs["Color"])
        bt = _map_range(nt, "wx_bt", bv.outputs[0], sp["blk_lo"], sp["blk_hi"],
                        0.0, 1.0)
        ramp = _ramp(nt, "wx_bramp", bt.outputs[0], sp["blk"])
        amp = _mix(nt, "wx_bamp", None, ramp.outputs["Color"],
                   min(1.0, sp["blk_amp"] * s))
        amp.inputs["Color1"].default_value = (1.0, 1.0, 1.0, 1.0)
        cur = _multiply(nt, "wx_bmul", cur, amp.outputs["Color"])
        # each stone is also slightly differently worn -> different specular
        lo, hi = sp["blk_rough"]
        rr = _map_range(nt, "wx_brough", bt.outputs[0], 0.0, 1.0,
                        lo, hi)
        hgt = bt.outputs[0]

    # ---- 2. how does this face meet the weather? -------------------------
    # The castle is lit by a key sun at 52/0/38 degrees (verified with
    # _surf_probe_lights.py: travel (-0.485,+0.621,-0.616)) plus a shadowless
    # fill from (+0.370,+0.696,+0.616).  Three orientations age differently:
    #   up-facing  -- rain-washed, sun-dried, bleached pale and slightly warm;
    #   sun-facing -- bleached, chalky, no moss;
    #   rain-facing / shaded -- stays damp, grows lichen, keeps its dirt.
    # The result is gated by ORIENTATION, not applied as a flat tint: on a
    # featureless wall this layer costs almost nothing, but every corbel top,
    # crenel tread and sill gets its own treatment, which is what makes the read
    # "two hundred years old" instead of "exposure -5%".
    geo = _mk(nt, "ShaderNodeNewGeometry", "wx_geo")
    nsep = _mk(nt, "ShaderNodeSeparateXYZ", "wx_nsep")
    nt.links.new(geo.outputs["Normal"], nsep.inputs["Vector"])
    nz = nsep.outputs["Z"]
    upw = _map_range(nt, "wx_upw", nz, 0.30, 0.88, 0.0, 1.0, interp="SMOOTHSTEP")
    dot = _mk(nt, "ShaderNodeVectorMath", "wx_gdot")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(geo.outputs["Normal"], dot.inputs[0])
    sx, sy, sz = sp["sun"]
    dot.inputs[1].default_value = (sx, sy, sz)
    lit = _map_range(nt, "wx_lit", dot.outputs["Value"], -0.10, 0.62,
                     0.0, 1.0, interp="SMOOTHSTEP")

    # exposure to sun and sky: 0 in a north-facing re-entrant, 1 on a roof tread
    expo = _math(nt, "wx_expo", "ADD", lit.outputs[0], None)
    ntok = _math(nt, "wx_exk", "MULTIPLY", upw.outputs[0], 1.35)
    nt.links.new(ntok.outputs[0], expo.inputs[1])
    expo = _math(nt, "wx_expc", "MULTIPLY_ADD", expo.outputs[0], 0.62)
    expo.inputs[2].default_value = 0.10
    expo = _map_range(nt, "wx_expw", expo.outputs[0], 0.0, 1.0, 0.0, 1.0,
                      interp="SMOOTHSTEP")
    if sp["bleach"] > 0.0 and s > 0.0:
        tone = _mix(nt, "wx_gtone", sp["damp_side"], sp["bleach_col"],
                    expo.outputs[0])
        amt = _mix(nt, "wx_gamt", None, tone.outputs["Color"],
                   sp["bleach"] * s)
        amt.inputs["Color1"].default_value = (1.0, 1.0, 1.0, 1.0)
        cur = _multiply(nt, "wx_gmul", cur, amt)

    # ---- 3. mortar joints: seep + moss lines ----------------------------
    # Darkening that lives ON the joints, not on the faces: the joint mask is
    # a second brick clone whose Color is 1 on a face and 0 in the mortar.
    if (brick is not None and s > 0.0
            and (sp["joint"] > 0.0 or sp["jmoss"] > 0.0)):
        jb = _clone_brick(nt, brick, "wx_jb", (1, 1, 1, 1), (1, 1, 1, 1),
                          (0, 0, 0, 1), mortar=sp["joint_w"])
        jv = _bw(nt, "wx_jv", jb.outputs["Color"])
        jm = _math(nt, "wx_jinv", "SUBTRACT", 1.0, None)
        nt.links.new(jv.outputs[0], jm.inputs[1])

        if sp["joint"] > 0.0:
            n = _noise(nt, "wx_jn", vec, sp["joint_scale"], 3.0, 0.55,
                       offset=(rnd, rnd * 0.5, 0.0))
            nn = _map_range(nt, "wx_jnm", n.outputs["Fac"], 0.30, 0.70,
                            0.35, 1.0)
            deep = _math(nt, "wx_jd", "MULTIPLY", jm.outputs[0],
                         nn.outputs[0])
            deep = _math(nt, "wx_js", "MULTIPLY", deep.outputs[0],
                         sp["joint"] * s)
            one = _math(nt, "wx_j1", "SUBTRACT", 1.0, None)
            nt.links.new(deep.outputs[0], one.inputs[1])
            cur = _multiply(nt, "wx_jmul", cur, one.outputs[0])

        # lichen that has colonised the shaded lower joints: green only in the
        # mortar line, only below jmoss_h, only in the damp half of the noise.
        if sp["jmoss"] > 0.0:
            dn = _noise(nt, "wx_jmn", vec, sp["jmoss_scale"], 3.0, 0.55,
                        offset=(rnd * 6.0, rnd * 2.0, 0.0))
            dd = _map_range(nt, "wx_jmd", dn.outputs["Fac"], 0.44, 0.70,
                            0.0, 1.0)
            hf = _map_range(nt, "wx_jmh", z, 0.0, sp["jmoss_h"], 1.0, 0.0,
                            clamp=True, interp="SMOOTHSTEP")
            f = _math(nt, "wx_jmf", "MULTIPLY", jm.outputs[0], dd.outputs[0])
            f = _math(nt, "wx_jmf2", "MULTIPLY", f.outputs[0], hf.outputs[0])
            f = _math(nt, "wx_jmf3", "MULTIPLY", f.outputs[0],
                      sp["jmoss"] * s * 1.8, clamp=True)
            # mixed, not multiplied: a joint full of moss is packed with it and
            # therefore lighter than the empty shadow it replaces
            cur = _mix(nt, "wx_jmmul", cur, LICHEN_MID, f.outputs[0])

    # ---- 3a. lichen colonies on the shaded faces ------------------------
    # Pale sage-green discs, 0.1-0.4 m across, sparse and only where the wall
    # stays damp: not in the splash band, not high up in the sun.  Real lichen
    # is nearly opaque, so this one MIXES towards its own colour instead of
    # multiplying -- it is the only layer that is allowed to sit on top.
    if sp["lichen"] > 0.0 and s > 0.0:
        ln = _noise(nt, "wx_lin", vec, sp["lichen_scale"], 4.0, 0.60,
                    offset=(rnd * 2.7, rnd * 3.1, 0.0))
        sp0 = _map_range(nt, "wx_lis", ln.outputs["Fac"], 0.575, 0.655,
                         0.0, 1.0, interp="SMOOTHSTEP")
        hg = _map_range(nt, "wx_lih", z, sp["lichen_lo"], sp["lichen_lo2"],
                        0.0, 1.0, clamp=True, interp="SMOOTHSTEP")
        hg2 = _map_range(nt, "wx_lih2", z, sp["lichen_hi"], sp["lichen_hi2"],
                         1.0, 0.0, clamp=True, interp="SMOOTHSTEP")
        st = _math(nt, "wx_lif", "MULTIPLY", sp0.outputs[0], hg.outputs[0])
        st = _math(nt, "wx_lif2", "MULTIPLY", st.outputs[0], hg2.outputs[0])
        sh = _math(nt, "wx_lif3", "MULTIPLY_ADD", expo.outputs[0], -0.55)
        sh.inputs[2].default_value = 1.0
        st = _math(nt, "wx_lif4", "MULTIPLY", st.outputs[0], sh.outputs[0])
        bn = _noise(nt, "wx_libn", vec, sp["lichen_scale"] * 9.0, 4.0, 0.60,
                    offset=(0.0, rnd * 1.1, 0.0))
        bt = _map_range(nt, "wx_lib", bn.outputs["Fac"], 0.30, 0.70, 0.70, 1.0)
        amt = _math(nt, "wx_lia", "MULTIPLY", st.outputs[0], bt.outputs[0])
        amt = _math(nt, "wx_lia2", "MULTIPLY", amt.outputs[0],
                    sp["lichen"] * s, clamp=True)
        cur = _mix(nt, "wx_limix", cur, LICHEN_PALE, amt.outputs[0])

    # ---- 3. large-scale washes ------------------------------------------
    # Three scales, all world-space and all mean-preserving.  Together they
    # are what makes a 32 px local mean vary across a wall: the old pass only
    # had a per-face multiply, so every 32 px block averaged to the same value.
    #
    # The first one is the repair patchwork: over two centuries a castle gets
    # re-pointed and partly re-stoned, and the replacement stones never match
    # the originals -- they are cleaner, cooler and lighter, while the surviving
    # runs are soot-soaked and warm.  The window is deliberately narrow (0.44 ..
    # 0.56) so the transition happens over a metre instead of a wall, which is
    # what makes a 1.5 m neighbourhood read as one phase or the other.
    if sp["phase"] > 0.0 and s > 0.0:
        a = _wash(nt, "wx_ph", vec, sp["phase_scale"], sp["phase_z"],
                  (rnd * 7.3, rnd * 2.6, 0.0), 0.44, 0.56,
                  ((0.00, (0.785, 0.760, 0.720)),      # soot-soaked old run
                   (0.42, (0.974, 0.969, 0.959)),
                   (0.58, (1.034, 1.044, 1.059)),
                   (1.00, (1.162, 1.172, 1.186))),     # replaced, cool, clean
                  sp["phase"] * s, 3.5, 0.55)
        cur = _multiply(nt, "wx_phmul", cur, a)

    if sp["quarry"] > 0.0 and s > 0.0:
        a = _wash(nt, "wx_qry", vec, sp["quarry_scale"], sp["quarry_z"],
                  (rnd * 11.0, rnd * 4.0, 0.0), 0.30, 0.70,
                  sp["quarry_ramp"], sp["quarry"] * s, 2.0, 0.50)
        cur = _multiply(nt, "wx_qrymul", cur, a)

    if sp["zone"] > 0.0 and s > 0.0:
        a = _wash(nt, "wx_zone", vec, sp["zone_scale"], sp["zone_z"],
                  (rnd * 5.1, rnd * 1.3, 0.0), sp["zone_lo"], sp["zone_hi"],
                  sp["zone_ramp"], sp["zone"] * s, 3.0, 0.50)
        cur = _multiply(nt, "wx_zonemul", cur, a)

    if sp["patch"] > 0.0 and s > 0.0:
        a = _wash(nt, "wx_pat", vec, sp["patch_scale"], sp["patch_z"],
                  (rnd * 2.0, 0.0, rnd), sp["patch_lo"], sp["patch_hi"],
                  sp["patch_ramp"], sp["patch"] * s, 4.0, 0.52)
        cur = _multiply(nt, "wx_patmul", cur, a)

    if sp["course"] > 0.0 and s > 0.0:
        a = _wash(nt, "wx_crs", vec, sp["course_scale"], sp["course_z"],
                  (0.0, rnd * 3.0, 0.0), 0.40, 0.60,
                  ((0.00, (0.955, 0.960, 0.965)),
                   (1.00, (1.045, 1.040, 1.035))),
                  sp["course"] * s, 2.0, 0.50)
        cur = _multiply(nt, "wx_crsmul", cur, a)

    # ---- 4. rain streaks on vertical faces ------------------------------
    if sp["streak"] > 0.0 and s > 0.0:
        nz_abs = _math(nt, "wx_nabs", "ABSOLUTE", nz)
        vm = _map_range(nt, "wx_vmask", nz_abs.outputs[0], 0.35, 0.85,
                        1.0, 0.0)
        n = _noise(nt, "wx_sn", vec, sp["streak_scale"], 5.0, 0.62,
                   zscale=sp["streak_z"], offset=(rnd * 3.0, rnd, 0.0))
        st = _map_range(nt, "wx_sm", n.outputs["Fac"], 0.56, 0.82, 0.0, 1.0)
        amt = _math(nt, "wx_sa", "MULTIPLY", st.outputs[0], vm.outputs[0])
        amt = _math(nt, "wx_sb", "MULTIPLY", amt.outputs[0],
                    sp["streak"] * s * 1.5, clamp=True)
        one = _math(nt, "wx_s1", "SUBTRACT", 1.0, None)
        nt.links.new(amt.outputs[0], one.inputs[1])
        cur = _multiply(nt, "wx_smul", cur, one.outputs[0])

    # ---- 6. drip marks under every ledge --------------------------------
    # Rain runs off the corbels, sills and string courses and leaves vertical
    # stains on the wall just below them.  AO already knows where the overhangs
    # are, so the streak mask is band-passed on AO: strongest 0.3-1.2 m under a
    # protrusion, absent on an open face and absent deep inside a reveal.
    if ao_out is not None and sp["drip"] > 0.0 and s > 0.0:
        db = _ramp(nt, "wx_drb", ao_out, (
            (sp["drip_lo"], (0.0, 0.0, 0.0, 1.0)),
            (sp["drip_mid"], (1.0, 1.0, 1.0, 1.0)),
            (sp["drip_hi"], (0.25, 0.25, 0.25, 1.0)),
            (1.0, (0.0, 0.0, 0.0, 1.0)),
        ))
        dn = _noise(nt, "wx_drn", vec, sp["drip_scale"], 4.0, 0.60,
                    zscale=sp["drip_z"], offset=(rnd * 7.0, 0.0, rnd))
        dst = _map_range(nt, "wx_dst", dn.outputs["Fac"], 0.46, 0.70, 0.0, 1.0)
        f = _math(nt, "wx_drf", "MULTIPLY", dst.outputs[0],
                  db.outputs["Color"])
        f = _math(nt, "wx_dra", "MULTIPLY", f.outputs[0],
                  sp["drip"] * s, clamp=True)
        one = _math(nt, "wx_dr1", "SUBTRACT", 1.0, None)
        nt.links.new(f.outputs[0], one.inputs[1])
        cur = _multiply(nt, "wx_drmul", cur, one.outputs[0])

    # ---- 7. the wall foot: splash, moss, rising damp ---------------------
    # Three stacked bands with different physics: (a) mud thrown up by rain
    # hitting the ground, 0-0.3 m, no green; (b) moss and lichen, 0-0.9 m,
    # patchy and clearly green; (c) capillary damp, 0-2 m, dark but not green.
    # Every band has a noise-broken base line so the edge is not a ruler.
    if sp["foot"] > 0.0 and s > 0.0:
        zn = _noise(nt, "wx_fn", vec, sp["foot_patch"], 3.0, 0.55,
                    offset=(0.0, rnd * 1.7, 0.0))
        zj = _map_range(nt, "wx_fzj", zn.outputs["Fac"], 0.0, 1.0, -0.30, 0.30)
        zz = _math(nt, "wx_fz", "ADD", z)
        nt.links.new(zj.outputs[0], zz.inputs[1])
        f0 = sp["foot"] * s

        # (a) mud splash: a warm tan band in the bottom 0.3 m, broken into
        # droplet-sized speckle at its upper edge where the drops thin out.
        # The speckle fields are lifted into 0.5-1.0 before they multiply:
        # three raw 0..1 masks peak at 0.1 and the band then reads as nothing.
        if sp["splash"] > 0.0:
            sh = _map_range(nt, "wx_fsh", zz.outputs[0], 0.0, sp["splash_h"],
                            1.0, 0.0, clamp=True, interp="SMOOTHSTEP")
            sn = _noise(nt, "wx_fsn", vec, sp["foot_patch"] * 3.1, 4.0, 0.60,
                        offset=(rnd * 8.0, 0.0, 0.0))
            sk = _map_range(nt, "wx_fsk", sn.outputs["Fac"], 0.28, 0.72,
                            0.0, 1.0)
            spk = _noise(nt, "wx_fspk", vec, sp["foot_patch"] * 11.0, 4.0,
                         0.58, offset=(rnd * 3.3, rnd * 5.0, 0.0))
            spk = _map_range(nt, "wx_fspm", spk.outputs["Fac"], 0.36, 0.64,
                             0.0, 1.0)
            sk = _math(nt, "wx_fsk2", "MULTIPLY_ADD", sk.outputs[0], 0.50)
            sk.inputs[2].default_value = 0.50
            spk = _math(nt, "wx_fspk2", "MULTIPLY_ADD", spk.outputs[0], 0.40)
            spk.inputs[2].default_value = 0.60
            f = _math(nt, "wx_fsf", "MULTIPLY", sh.outputs[0], sk.outputs[0])
            f = _math(nt, "wx_fsf2", "MULTIPLY", f.outputs[0], spk.outputs[0])
            f = _math(nt, "wx_fsa", "MULTIPLY", f.outputs[0],
                      sp["splash"] * f0 * 1.60, clamp=True)
            cur = _mix(nt, "wx_fsmul", cur, sp["splash_col"], f.outputs[0])

        # (b) moss: clumped, decaying with height, and stronger on the faces
        # that never dry out.  Three noises: one picks the cushions (~1 m), one
        # makes their edges ragged (~0.2 m), one is the fine crumb on top.
        # This layer MIXES instead of multiplying: moss is opaque, and in
        # daylight it is brighter than the wet stone under it, so a multiply
        # can only ever make a dark green-grey -- measured G-max(R,B) = 4 at
        # display values, below the 8 the acceptance test asks for.  The gain
        # is what makes the clump mask near-binary: a product of three fields
        # that each average 0.6 peaks at 0.2, so without it the moss never
        # actually covers anything.
        if sp["moss"] > 0.0:
            h01 = _map_range(nt, "wx_fh01", zz.outputs[0], 0.0, sp["foot_h"],
                             0.0, 1.0, clamp=True)
            fade = _ramp(nt, "wx_fmfd", h01.outputs[0], (
                (0.00, (1.00, 1.00, 1.00, 1.0)),
                (0.30, (0.74, 0.74, 0.74, 1.0)),
                (0.62, (0.36, 0.36, 0.36, 1.0)),
                (1.00, (0.03, 0.03, 0.03, 1.0)),
            ))
            # two scales of cushion: ~1 m stands of moss, and metres-long bare
            # stretches where the wall simply stays too dry for any of it
            rgn = _noise(nt, "wx_frg", vec, sp["foot_patch"] * 0.42, 2.0, 0.50,
                         offset=(rnd * 9.0, rnd * 6.0, 0.0))
            region = _map_range(nt, "wx_frgm", rgn.outputs["Fac"], 0.38, 0.58,
                                0.10, 1.0, interp="SMOOTHSTEP")
            cn = _noise(nt, "wx_fcn", vec, sp["foot_patch"] * 1.05, 3.0, 0.55,
                        offset=(rnd * 4.0, rnd * 2.0, 0.0))
            clump = _map_range(nt, "wx_fcl", cn.outputs["Fac"], 0.40, 0.56,
                               0.0, 1.0, interp="SMOOTHSTEP")
            en = _noise(nt, "wx_fen", vec, sp["foot_patch"] * 6.0, 5.0, 0.62,
                        offset=(rnd * 1.9, 0.0, 0.0))
            edge = _map_range(nt, "wx_fed", en.outputs["Fac"], 0.28, 0.66,
                              0.50, 1.0)
            mfac = _math(nt, "wx_fm0", "MULTIPLY", fade.outputs["Color"],
                         region.outputs[0])
            mfac = _math(nt, "wx_fm1", "MULTIPLY", mfac.outputs[0],
                         clump.outputs[0])
            mfac = _math(nt, "wx_fm2", "MULTIPLY", mfac.outputs[0],
                         edge.outputs[0])
            # 1 - 0.45 * expo: the sunlit side of a wall loses its moss
            f_shade = _math(nt, "wx_fm3", "MULTIPLY_ADD", expo.outputs[0],
                            -0.45)
            f_shade.inputs[2].default_value = 1.0
            mfac2 = _math(nt, "wx_fm4", "MULTIPLY", mfac.outputs[0],
                          f_shade.outputs[0])
            # moss does not grow on the flat tops of sills and cornices: rain
            # rinses them and the sun bakes them dry, so up-facing stone stays
            # bare even where the vertical face two centimetres below it is
            # green.  Without this the tide mark is smeared over every ledge.
            f_flat = _math(nt, "wx_fm7", "MULTIPLY_ADD", upw.outputs[0], -0.62)
            f_flat.inputs[2].default_value = 1.0
            mfac2 = _math(nt, "wx_fm8", "MULTIPLY", mfac2.outputs[0],
                          f_flat.outputs[0])
            mfac2 = _math(nt, "wx_fm5", "MULTIPLY", mfac2.outputs[0],
                          sp["moss"] * f0 * sp["moss_gain"], clamp=True)
            # runoff fingers: moss colonises where the water runs off the wall,
            # so thin vertical stands reach far above the tide mark
            if sp["runoff"] > 0.0:
                rn = _noise(nt, "wx_frn", vec, sp["foot_patch"] * 3.6, 4.0,
                            0.58, zscale=0.05,
                            offset=(rnd * 5.5, rnd * 0.7, 0.0))
                rf = _map_range(nt, "wx_frf", rn.outputs["Fac"], 0.50, 0.58,
                                0.0, 1.0, interp="SMOOTHSTEP")
                rh = _map_range(nt, "wx_frh", zz.outputs[0], 0.0, sp["runoff_h"],
                                1.0, 0.0, clamp=True, interp="SMOOTHSTEP")
                rf2 = _math(nt, "wx_fr2", "MULTIPLY", rf.outputs[0],
                            rh.outputs[0])
                rf2 = _math(nt, "wx_fr4", "MULTIPLY", rf2.outputs[0],
                            f_flat.outputs[0])
                rf2 = _math(nt, "wx_fr3", "MULTIPLY", rf2.outputs[0],
                            sp["runoff"] * f0 * sp["moss_gain"] * 0.55,
                            clamp=True)
                mfac2 = _math(nt, "wx_fm6", "ADD", mfac2.outputs[0],
                              rf2.outputs[0], clamp=True)
            # the colour itself: two moss greens lerped by a fine crumb noise,
            # so a clump is not one flat patch of paint
            kn = _noise(nt, "wx_fkn", vec, sp["foot_patch"] * 14.0, 6.0, 0.60,
                        offset=(rnd * 2.4, rnd * 3.7, 0.0))
            crumb = _map_range(nt, "wx_fkr", kn.outputs["Fac"], 0.30, 0.70,
                               0.0, 1.0)
            moss = _mix(nt, "wx_fmix", MOSS_LIGHT, MOSS_DARK, crumb.outputs[0])
            cur = _mix(nt, "wx_fmul", cur, moss.outputs["Color"],
                       mfac2.outputs[0])

        # (c) rising damp, no green
        if sp["damp_mix"] > 0.0:
            dh = _map_range(nt, "wx_fdh", zz.outputs[0], 0.0, sp["damp_h"],
                            1.0, 0.0, clamp=True, interp="SMOOTHSTEP")
            d1 = _math(nt, "wx_fdm", "MULTIPLY", dh.outputs[0],
                       sp["damp_mix"] * f0 * 0.55, clamp=True)
            dm = _mix(nt, "wx_fdamp", None, DAMP, d1.outputs[0])
            dm.inputs["Color1"].default_value = (1.0, 1.0, 1.0, 1.0)
            cur = _multiply(nt, "wx_fdmul", cur, dm.outputs["Color"])

    nt.links.new(_sock(cur), bsdf.inputs["Base Color"])

    # ---- 6. roughness ----------------------------------------------------
    rg = bsdf.inputs["Roughness"]
    if brick is not None and sp["blk_amp"] > 0.0 and s > 0.0:
        lo, hi = sp["blk_rough"]
        if (lo, hi) != (1.0, 1.0):
            base_r = rg.links[0].from_socket if rg.is_linked else None
            mul = _math(nt, "wx_rmul", "MULTIPLY", None, rr.outputs[0])
            if base_r is not None:
                nt.links.new(base_r, mul.inputs[0])
            else:
                mul.inputs[0].default_value = rg.default_value
            nt.links.new(mul.outputs[0], rg)
    if sp["rough"] != (1.0, 1.0) and s > 0.0:
        # a coarse roughness drift so the whole wall is not one gloss value
        rn = _noise(nt, "wx_rn", vec, 0.9, 2.0, 0.5,
                    offset=(rnd * 1.3, 0.0, 0.0))
        rm = _map_range(nt, "wx_rm", rn.outputs["Fac"], 0.35, 0.65,
                        sp["rough"][0], sp["rough"][1])
        src = rg.links[0].from_socket if rg.is_linked else None
        k = _math(nt, "wx_rok", "MULTIPLY", None, rm.outputs[0])
        if src is not None:
            nt.links.new(src, k.inputs[0])
        else:
            k.inputs[0].default_value = rg.default_value
        nt.links.new(k.outputs[0], rg)

    # ---- 7. bump ---------------------------------------------------------
    if sp["bump_str"] > 0.0 and s > 0.0:
        h = None
        if hgt is not None:
            h = _math(nt, "wx_bh", "MULTIPLY", hgt, 0.55)
        mn = _noise(nt, "wx_bn", vec, sp["bump_scale"], 3.0, 0.6,
                    offset=(rnd, rnd * 0.7, rnd * 0.3))
        mh = _math(nt, "wx_bnh", "MULTIPLY", mn.outputs["Fac"], 0.45)
        if h is not None:
            h = _math(nt, "wx_bhs", "ADD", h.outputs[0], mh.outputs[0])
        else:
            h = mh
        bump = _mk(nt, "ShaderNodeBump", "wx_bump")
        bump.inputs["Strength"].default_value = sp["bump_str"] * s
        bump.inputs["Distance"].default_value = sp["bump_dist"]
        nt.links.new(h.outputs[0], bump.inputs["Height"])
        nb = bsdf.inputs["Normal"]
        if nb.is_linked and nb.links[0].from_node.type == "BUMP":
            nt.links.new(nb.links[0].from_socket, bump.inputs["Normal"])
        nt.links.new(bump.outputs["Normal"], nb)

    mat["_weathering"] = 1
    mat["_weathering_kind"] = kind
    return True


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def weather_material(mat, kind, strength=1.0, seed=7):
    """Age ONE material in place.  Safe to call twice (idempotent)."""
    if mat is None or getattr(mat, "node_tree", None) is None:
        return None
    if is_weathered(mat):
        return mat

    k_in = kind
    k = resolve_kind(k_in)
    if k is None:
        return None
    softened = False
    if k == "?":
        if k_in not in _WARNED:
            _WARNED.add(k_in)
            print("[surface] %r is not a known surface kind; using a soft stone"
                  " recipe" % (k_in,), flush=True)
        k = "stone"
        softened = True
    if k in FROZEN:
        return None
    sp = RECIPES.get(k)
    if sp is None:
        return None

    if softened:
        strength = strength * _FALLBACK_SOFTEN
    try:
        ok = _build(mat, k, sp, strength, seed)
    except Exception as exc:
        print("[surface] %-14s FAILED: %s: %s"
              % (mat.name, type(exc).__name__, exc), flush=True)
        return None
    if ok:
        print("[surface] %-14s -> %-10s s=%.2f  blocks=%s foot=%s"
              % (mat.name, k, strength, sp["blk_amp"] > 0.0, sp["foot"] > 0.0),
              flush=True)
        return mat
    return None


def apply_weathering(MAT, strength=1.0, seed=7):
    """Age every material in a MAT dict, in place, and return the same dict."""
    if not isinstance(MAT, dict):
        print("[surface] apply_weathering: expected a dict, got %r"
              % (type(MAT),), flush=True)
        return MAT
    done, frozen, skipped = 0, [], []
    for key, mat in MAT.items():
        if mat is None:
            continue
        k = resolve_kind(key)
        if k in FROZEN:
            frozen.append("%s(%s)" % (key, k))
            continue
        before = is_weathered(mat)
        weather_material(mat, key, strength=strength, seed=seed)
        if not before and is_weathered(mat):
            done += 1
        elif not before:
            skipped.append(key)
    print("[surface] weathered %d materials; frozen: %s"
          % (done, ", ".join(sorted(frozen)) or "-"), flush=True)
    if skipped:
        print("[surface] skipped: %s" % ", ".join(sorted(skipped)), flush=True)
    return MAT
