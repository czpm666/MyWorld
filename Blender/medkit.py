"""
medkit.py — parametric medieval kit for Blender (headless).

Design rule (from procedural-3d-modeling skill):
  the artifact is SOURCE CODE, not a mesh. Everything here regenerates.
  All primitives build directly in WORLD space via a 4x4 matrix `T`,
  so objects keep identity transforms (clean for export).

Conventions: Z up. House local frame has its FRONT on +Y.
"""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix, Euler

TAU = math.tau


# --------------------------------------------------------------------------
# scene / object core
# --------------------------------------------------------------------------
def reset_scene():
    """Empty the scene without read_factory_settings (that kills addons)."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for item in list(blk):
            if item.users == 0:
                blk.remove(item)


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def mesh_obj(name, verts, faces, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate()
    me.update()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return link(bpy.data.objects.new(name, me))


def assign(ob, *mats):
    ob.data.materials.clear()
    for m in mats:
        ob.data.materials.append(m)
    if len(mats) == 1:
        for p in ob.data.polygons:
            p.material_index = 0
    return ob


def bevel(ob, width=0.015, segments=2, angle=35.0):
    m = ob.modifiers.new("bev", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    return ob


def T_at(x=0.0, y=0.0, z=0.0, rz=0.0, ry=0.0, rx=0.0):
    return (Matrix.Translation((x, y, z))
            @ Euler((rx, ry, rz), "XYZ").to_matrix().to_4x4())


# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------
_MAT_CACHE = {}


def _bsdf(mat):
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def _put(node, names, value):
    for n in names:
        inp = node.inputs.get(n)
        if inp is not None:
            try:
                inp.default_value = value
            except Exception:
                pass
            return True
    return False


def _new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, _bsdf(m)


def _ramp(nt, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.interpolation = "LINEAR"
    els = r.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    els[0].position = stops[0][0]
    els[0].color = stops[0][1]
    for pos, col in stops[1:]:
        e = els.new(pos)
        e.color = col
    return r


def _noise(nt, scale=8.0, detail=6.0, rough=0.55):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    return n


def _bump(nt, bsdf, src, strength=0.25, distance=0.04):
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    nt.links.new(src, b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], bsdf.inputs["Normal"])
    return b


def c(hexstr, a=1.0):
    """#rrggbb (sRGB) -> linear RGBA for shader inputs."""
    h = hexstr.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in srgb]
    return (lin[0], lin[1], lin[2], a)


def mat_plaster(name="plaster", base="#e6dcc6", dirt="#cbbfa4", scale=5.0):
    if name in _MAT_CACHE:
        return _MAT_CACHE[name]
    m, b = _new_mat(name)
    _put(b, ["Roughness"], 0.88)
    _put(b, ["Metallic"], 0.0)
    nt = m.node_tree
    n = _noise(nt, scale=scale, detail=8.0, rough=0.6)
    r = _ramp(nt, [(0.35, c(base)), (0.62, c(dirt)), (0.85, c(base))])
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    _bump(nt, b, n.outputs["Fac"], strength=0.18, distance=0.02)
    _MAT_CACHE[name] = m
    return m


def mat_wood(name="timber", base="#4a3223", light="#6b4a33", rough=0.78, scale=14.0):
    if name in _MAT_CACHE:
        return _MAT_CACHE[name]
    m, b = _new_mat(name)
    _put(b, ["Roughness"], rough)
    _put(b, ["Metallic"], 0.0)
    nt = m.node_tree
    # stretched noise reads as grain
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.0, 0.12)
    n = _noise(nt, scale=scale, detail=8.0, rough=0.62)
    nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
    r = _ramp(nt, [(0.3, c(base)), (0.55, c(light)), (0.8, c(base))])
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    _bump(nt, b, n.outputs["Fac"], strength=0.3, distance=0.01)
    _MAT_CACHE[name] = m
    return m


def mat_tile(name="roof_tile", base="#9c3f2b", dark="#6f2a1c", light="#bd5539"):
    if name in _MAT_CACHE:
        return _MAT_CACHE[name]
    m, b = _new_mat(name)
    _put(b, ["Roughness"], 0.72)
    _put(b, ["Metallic"], 0.0)
    nt = m.node_tree
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.5
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = 0.012
    br.inputs["Brick Width"].default_value = 0.30
    br.inputs["Row Height"].default_value = 0.17
    col_mortar = br.inputs.get("Mortar")
    if col_mortar is not None:
        col_mortar.default_value = c(dark)
    col1 = br.inputs.get("Color1")
    col2 = br.inputs.get("Color2")
    if col1 is not None:
        col1.default_value = c(base)
    if col2 is not None:
        col2.default_value = c(light)
    # rotate rows so they run down the slope
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0.0, 0.0, 0.0)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], br.inputs["Vector"])
    n = _noise(nt, scale=6.0, detail=6.0)
    r = _ramp(nt, [(0.25, c(dark)), (0.7, c(light))])
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs["Fac"].default_value = 0.35
    nt.links.new(br.outputs["Color"], mix.inputs["Color1"])
    nt.links.new(r.outputs["Color"], mix.inputs["Color2"])
    nt.links.new(mix.outputs["Color"], b.inputs["Base Color"])
    _bump(nt, b, br.outputs["Fac"], strength=0.42, distance=0.02)
    _MAT_CACHE[name] = m
    return m


def mat_stone(name="stone", base="#7d7466", dark="#4a443a", light="#9a9284", scale=2.4):
    """Coursed ashlar masonry, not Voronoi rubble.

    A plain Brick texture was rejected here once, and the reason was real:
    Brick samples the vector's XY plane while a wall face lies in XZ, so every
    course collapsed into vertical stripes.  The fix is to swizzle the vector
    first and feed (x + y, z) instead of (x, y).  On a +-X facing wall x is
    almost constant, so the horizontal coordinate advances with y; on a +-Y
    facing wall y is almost constant, so it advances with x.  Both wall
    orientations get correct courses, and where two walls meet at a corner the
    coursing runs straight through the joint instead of restarting.

    The Voronoi version this replaces is what made the keep towers read as
    giraffe hide: distance-to-edge at scale 2.4 produced ~0.4 m irregular
    cells behind a ~5 cm near-black seam, which at tower scale is rubble
    rather than dressed stone.  `scale` keeps its old meaning (bigger scale =
    smaller stones) via 1.5/scale x 0.75/scale courses.
    """
    if name in _MAT_CACHE:
        return _MAT_CACHE[name]
    m, b = _new_mat(name)
    _put(b, ["Roughness"], 0.84)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(sep.outputs["X"], add.inputs[0])
    nt.links.new(sep.outputs["Y"], add.inputs[1])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(add.outputs[0], comb.inputs["X"])
    nt.links.new(sep.outputs["Z"], comb.inputs["Y"])

    br = nt.nodes.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 1.5 / max(scale, 0.1)
    br.inputs["Row Height"].default_value = 0.75 / max(scale, 0.1)
    br.inputs["Mortar Size"].default_value = 0.022
    br.inputs["Mortar Smooth"].default_value = 0.25
    br.inputs["Bias"].default_value = 0.0
    nt.links.new(comb.outputs["Vector"], br.inputs["Vector"])
    br.inputs["Color1"].default_value = c(base)
    br.inputs["Color2"].default_value = c(light)
    br.inputs["Mortar"].default_value = c(dark)

    # large-scale weathering so a 90 m curtain wall is not uniformly clean
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.55
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    rg = _ramp(nt, [(0.28, c("#8d887b")), (0.74, c("#ffffff"))])
    nt.links.new(nz.outputs["Fac"], rg.inputs["Fac"])
    # fine grain, breaks up the flat per-block colour
    nz2 = nt.nodes.new("ShaderNodeTexNoise")
    nz2.inputs["Scale"].default_value = 14.0
    nz2.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], nz2.inputs["Vector"])
    rg2 = _ramp(nt, [(0.30, c("#c9c4b6")), (0.70, c("#ffffff"))])
    nt.links.new(nz2.outputs["Fac"], rg2.inputs["Fac"])

    m1 = nt.nodes.new("ShaderNodeMixRGB")
    m1.blend_type = "MULTIPLY"
    m1.inputs["Fac"].default_value = 0.45
    nt.links.new(br.outputs["Color"], m1.inputs["Color1"])
    nt.links.new(rg.outputs["Color"], m1.inputs["Color2"])
    m2 = nt.nodes.new("ShaderNodeMixRGB")
    m2.blend_type = "MULTIPLY"
    m2.inputs["Fac"].default_value = 0.30
    nt.links.new(m1.outputs["Color"], m2.inputs["Color1"])
    nt.links.new(rg2.outputs["Color"], m2.inputs["Color2"])
    nt.links.new(m2.outputs["Color"], b.inputs["Base Color"])

    # Brick.Fac is 1 inside the mortar joint, so invert it: the blocks stand
    # proud and the joint reads as a recess instead of a raised grout line
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(br.outputs["Fac"], inv.inputs[1])
    _bump(nt, b, inv.outputs[0], strength=0.32, distance=0.02)
    _MAT_CACHE[name] = m
    return m


def mat_cobble(name="cobble", base="#8f8878", mortar="#4c463c", light="#b3ab98"):
    if name in _MAT_CACHE:
        return _MAT_CACHE[name]
    m, b = _new_mat(name)
    _put(b, ["Roughness"], 0.9)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    v = nt.nodes.new("ShaderNodeTexVoronoi")
    v.feature = "DISTANCE_TO_EDGE"
    v.inputs["Scale"].default_value = 7.0
    v.inputs["Randomness"].default_value = 1.0
    nt.links.new(tc.outputs["Object"], v.inputs["Vector"])
    r = _ramp(nt, [(0.0, c(mortar)), (0.05, c(base)), (0.30, c(light))])
    nt.links.new(v.outputs["Distance"], r.inputs["Fac"])
    # second voronoi: per-stone BRIGHTNESS only (Voronoi colour is a random hue
    # and reads as confetti on a large ground plane)
    v2 = nt.nodes.new("ShaderNodeTexVoronoi")
    v2.feature = "F1"
    v2.inputs["Scale"].default_value = 7.0
    nt.links.new(tc.outputs["Object"], v2.inputs["Vector"])
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(v2.outputs["Color"], bw.inputs["Color"])
    r2 = _ramp(nt, [(0.0, c("#8e8e8e")), (1.0, c("#ffffff"))])
    nt.links.new(bw.outputs["Val"], r2.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs["Fac"].default_value = 0.55
    nt.links.new(r.outputs["Color"], mix.inputs["Color1"])
    nt.links.new(r2.outputs["Color"], mix.inputs["Color2"])
    nt.links.new(mix.outputs["Color"], b.inputs["Base Color"])
    _bump(nt, b, v.outputs["Distance"], strength=0.5, distance=0.03)
    _MAT_CACHE[name] = m
    return m


def mat_flag(name="flag", base="#7a7263", dark="#3e3930", light="#9d9483", scale=2.4):
    """Dressed flagstone paving, for a formal plaza.

    Slab SIZE matters more than colour here.  The first version ran at
    scale=0.80, i.e. slabs about 1.25 m across; at player height that read as
    cracked ice rather than paving.  Scale 2.4 gives ~0.42 m slabs, and the
    seam threshold is widened in step (0.03 -> 0.055) so the mortar line stays
    a constant ~2 cm of real stone instead of vanishing as the pieces shrink.
    """
    if name in _MAT_CACHE:
        return _MAT_CACHE[name]
    m, b = _new_mat(name)
    _put(b, ["Roughness"], 0.88)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    v = nt.nodes.new("ShaderNodeTexVoronoi")
    v.feature = "DISTANCE_TO_EDGE"
    v.inputs["Scale"].default_value = scale
    v.inputs["Randomness"].default_value = 0.62
    nt.links.new(tc.outputs["Object"], v.inputs["Vector"])
    r = _ramp(nt, [(0.0, c(dark)), (0.055, c(base)), (0.20, c(light))])
    nt.links.new(v.outputs["Distance"], r.inputs["Fac"])
    # per-slab tone only (Voronoi's colour output is a random hue and reads as
    # confetti across a large plane); the range is deliberately wide so the
    # square is not one flat brightness
    v2 = nt.nodes.new("ShaderNodeTexVoronoi")
    v2.feature = "F1"
    v2.inputs["Scale"].default_value = scale
    v2.inputs["Randomness"].default_value = 0.62
    nt.links.new(tc.outputs["Object"], v2.inputs["Vector"])
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(v2.outputs["Color"], bw.inputs["Color"])
    r2 = _ramp(nt, [(0.0, c("#8a8578")), (1.0, c("#ffffff"))])
    nt.links.new(bw.outputs["Val"], r2.inputs["Fac"])
    tone = nt.nodes.new("ShaderNodeMixRGB")
    tone.blend_type = "MULTIPLY"
    tone.inputs["Fac"].default_value = 0.62
    nt.links.new(r.outputs["Color"], tone.inputs["Color1"])
    nt.links.new(r2.outputs["Color"], tone.inputs["Color2"])
    # broad grime / traffic wear, so the slabs do not all look freshly laid
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 0.35
    n.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    rd = _ramp(nt, [(0.34, c("#8d8478")), (0.66, c("#ffffff"))])
    nt.links.new(n.outputs["Fac"], rd.inputs["Fac"])
    dirt = nt.nodes.new("ShaderNodeMixRGB")
    dirt.blend_type = "MULTIPLY"
    dirt.inputs["Fac"].default_value = 0.55
    nt.links.new(tone.outputs["Color"], dirt.inputs["Color1"])
    nt.links.new(rd.outputs["Color"], dirt.inputs["Color2"])
    nt.links.new(dirt.outputs["Color"], b.inputs["Base Color"])
    _bump(nt, b, v.outputs["Distance"], strength=0.28, distance=0.02)
    _MAT_CACHE[name] = m
    return m


def mat_metal(name="iron", base="#3b3a40", rough=0.42):
    if name in _MAT_CACHE:
        return _MAT_CACHE[name]
    m, b = _new_mat(name)
    _put(b, ["Metallic"], 1.0)
    _put(b, ["Roughness"], rough)
    nt = m.node_tree
    n = _noise(nt, scale=20.0, detail=6.0)
    r = _ramp(nt, [(0.35, c(base)), (0.7, c("#5a5760"))])
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    _MAT_CACHE[name] = m
    return m


def mat_gold(name="gold", base="#c9a227"):
    m, b = _new_mat(name)
    _put(b, ["Metallic"], 1.0)
    _put(b, ["Roughness"], 0.28)
    _put(b, ["Base Color"], c(base))
    _MAT_CACHE[name] = m
    return m


def mat_cloth(name, hexcol, rough=0.85):
    key = "cloth_" + name
    if key in _MAT_CACHE:
        return _MAT_CACHE[key]
    m, b = _new_mat(key)
    _put(b, ["Roughness"], rough)
    _put(b, ["Metallic"], 0.0)
    _put(b, ["Sheen Weight"], 0.35)
    nt = m.node_tree
    n = _noise(nt, scale=26.0, detail=5.0)
    r = _ramp(nt, [(0.4, c(hexcol)), (0.75, tuple(min(1.0, v * 1.18) for v in c(hexcol)[:3]) + (1.0,))])
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    _bump(nt, b, n.outputs["Fac"], strength=0.12, distance=0.01)
    _MAT_CACHE[key] = m
    return m


def mat_glass(name="glass", base="#3d5162"):
    m, b = _new_mat(name)
    _put(b, ["Roughness"], 0.14)
    _put(b, ["Metallic"], 0.35)
    _put(b, ["Base Color"], c(base))
    _put(b, ["Emission Color"], c("#1b2833"))
    _put(b, ["Emission Strength"], 0.25)
    _MAT_CACHE[name] = m
    return m


def mat_foliage(name="leaf", base="#3e6b32", light="#5f9440", scale=7.0):
    if name in _MAT_CACHE:
        return _MAT_CACHE[name]
    m, b = _new_mat(name)
    _put(b, ["Roughness"], 0.8)
    nt = m.node_tree
    n = _noise(nt, scale=scale, detail=7.0, rough=0.7)
    r = _ramp(nt, [(0.3, c(base)), (0.62, c(light)), (0.85, c(base))])
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    _bump(nt, b, n.outputs["Fac"], strength=0.35, distance=0.02)
    _MAT_CACHE[name] = m
    return m


def mat_water(name="water", base="#33606d"):
    m, b = _new_mat(name)
    _put(b, ["Roughness"], 0.10)
    _put(b, ["Metallic"], 0.0)
    _put(b, ["Base Color"], c(base))
    _put(b, ["Emission Color"], c("#16333c"))
    _put(b, ["Emission Strength"], 0.06)
    _MAT_CACHE[name] = m
    return m


def mat_earth(name="earth", base="#8a6a45", dark="#5c432b", scale=9.0, detail=8.0,
              bump=0.30, patch=0.0):
    """Ground material.

    `detail=8` at `scale=9` gives fine pepper grain which reads as render noise on
    a big field; `patch>0` mixes in a second, much broader noise so the surface
    breaks into patches instead of speckling.
    """
    m, b = _new_mat(name)
    _put(b, ["Roughness"], 0.95)
    nt = m.node_tree
    n = _noise(nt, scale=scale, detail=detail, rough=0.70)
    r = _ramp(nt, [(0.3, c(dark)), (0.7, c(base))])
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    col = r.outputs["Color"]
    if patch > 0:
        n2 = _noise(nt, scale=scale * 0.22, detail=2.0, rough=0.35)
        r2 = _ramp(nt, [(0.36, c(dark)), (0.64, c(base))])
        nt.links.new(n2.outputs["Fac"], r2.inputs["Fac"])
        mx = nt.nodes.new("ShaderNodeMixRGB")
        mx.blend_type = "MIX"
        mx.inputs["Fac"].default_value = patch
        nt.links.new(r.outputs["Color"], mx.inputs["Color1"])
        nt.links.new(r2.outputs["Color"], mx.inputs["Color2"])
        col = mx.outputs["Color"]
    nt.links.new(col, b.inputs["Base Color"])
    _bump(nt, b, n.outputs["Fac"], strength=bump, distance=0.03)
    _MAT_CACHE[name] = m
    return m


# --------------------------------------------------------------------------
# primitives (world space via matrix T)
# --------------------------------------------------------------------------
def box(name, T, size, mat=None, bev=0.0):
    sx, sy, sz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
    loc = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
           (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    verts = [T @ Vector(v) for v in loc]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ob = mesh_obj(name, verts, faces)
    if mat:
        assign(ob, mat)
    if bev > 0:
        bevel(ob, bev)
    return ob


def cyl(name, T, radius, height, mat=None, seg=20, cap=True, r2=None):
    r2 = radius if r2 is None else r2
    hz = height * 0.5
    verts, faces = [], []
    for i in range(seg):
        a = TAU * i / seg
        verts.append(T @ Vector((math.cos(a) * radius, math.sin(a) * radius, -hz)))
    for i in range(seg):
        a = TAU * i / seg
        verts.append(T @ Vector((math.cos(a) * r2, math.sin(a) * r2, hz)))
    for i in range(seg):
        j = (i + 1) % seg
        faces.append((i, j, seg + j, seg + i))
    if cap:
        faces.append(tuple(range(seg - 1, -1, -1)))
        faces.append(tuple(range(seg, seg * 2)))
    ob = mesh_obj(name, verts, faces)
    if mat:
        assign(ob, mat)
    return ob


def cone(name, T, radius, height, mat=None, seg=16):
    hz = height * 0.5
    verts = [T @ Vector((0.0, 0.0, hz))]
    for i in range(seg):
        a = TAU * i / seg
        verts.append(T @ Vector((math.cos(a) * radius, math.sin(a) * radius, -hz)))
    faces = []
    for i in range(seg):
        faces.append((0, 1 + i, 1 + (i + 1) % seg))
    faces.append(tuple(range(seg, 0, -1)))
    ob = mesh_obj(name, verts, faces)
    if mat:
        assign(ob, mat)
    return ob


def sphere(name, T, radius, mat=None, seg=20, ring=12, squash=1.0):
    verts, faces = [], []
    for j in range(ring + 1):
        phi = math.pi * j / ring
        for i in range(seg):
            th = TAU * i / seg
            verts.append(T @ Vector((math.sin(phi) * math.cos(th) * radius,
                                     math.sin(phi) * math.sin(th) * radius,
                                     math.cos(phi) * radius * squash)))
    for j in range(ring):
        for i in range(seg):
            a = j * seg + i
            b = j * seg + (i + 1) % seg
            cc = (j + 1) * seg + (i + 1) % seg
            d = (j + 1) * seg + i
            faces.append((a, b, cc, d))
    ob = mesh_obj(name, verts, faces, smooth=True)
    if mat:
        assign(ob, mat)
    return ob


def gable_roof(name, T, width, depth, eave_z, pitch_deg, roof_mat, gable_mat,
               ov_side=0.45, ov_gable=0.5, thick=0.16, end_mat=None):
    """Ridge runs along local Y; gable triangles face +Y / -Y."""
    hw = width * 0.5 + ov_side
    hd = depth * 0.5 + ov_gable
    rh = hw * math.tan(math.radians(pitch_deg))
    top = eave_z + rh
    prof = [(-hw, eave_z), (hw, eave_z), (0.0, top)]
    verts = []
    for y in (-hd, hd):
        for (x, z) in prof:
            verts.append(T @ Vector((x, y, z)))
    inner = []
    for y in (-hd, hd):
        for (x, z) in prof:
            # the inner shell must sit *under* the outer surface, otherwise the
            # plaster underside pokes through the tiles when seen from above
            inner.append(T @ Vector((x * (1 - thick / max(hw, 1e-6)), y,
                                     z - thick)))
    base = [T @ Vector((x, y, eave_z)) for y in (-hd, hd) for x in (-hw, hw)]
    allv = verts + inner + base
    n = 3
    faces, mat_idx = [], []
    # outer slopes (tiles)
    faces.append((0, 2, 5, 3)); mat_idx.append(0)          # -X slope
    faces.append((2, 1, 4, 5)); mat_idx.append(0)          # +X slope
    # inner slopes
    faces.append((3, 5, 8, 6)); mat_idx.append(1)
    faces.append((5, 4, 7, 8)); mat_idx.append(1)
    # gable ends
    faces.append((0, 1, 2)); mat_idx.append(1)
    faces.append((4, 3, 5)); mat_idx.append(1)
    # eaves underside
    faces.append((0, 6, 9, 3)); mat_idx.append(1)
    faces.append((1, 4, 7, 10)); mat_idx.append(1)
    faces.append((9, 6, 7, 10)); mat_idx.append(1)
    ob = mesh_obj(name, allv, faces)
    if end_mat is not None:
        # gable end caps are part of the WALL, not of the roof deck: painting
        # them with gable_mat leaves a dark board where the plaster should be.
        assign(ob, roof_mat, gable_mat, end_mat)
    else:
        assign(ob, roof_mat, gable_mat)
    for p, mi in zip(ob.data.polygons, mat_idx):
        p.material_index = mi
    if end_mat is not None:
        ob.data.polygons[4].material_index = 2
        ob.data.polygons[5].material_index = 2
    return ob


def roof_details(name, T, width, depth, eave_z, pitch_deg, metal_mat, ov_side=0.45, ov_gable=0.5):
    """Ridge cap + eave boards + rake boards."""
    hw = width * 0.5 + ov_side
    hd = depth * 0.5 + ov_gable
    rh = hw * math.tan(math.radians(pitch_deg))
    top = eave_z + rh
    parts = []
    parts.append(box(name + "_ridge", T @ T_at(0, 0, top + 0.05),
                     (0.30, hd * 2 + 0.06, 0.12), metal_mat, bev=0.02))
    for sx in (-1, 1):
        parts.append(box(name + "_eave", T @ T_at(sx * hw, 0, eave_z - 0.02),
                         (0.10, hd * 2, 0.16), metal_mat, bev=0.015))
        # rake boards along the gable edge
        rl = math.hypot(hw, rh)
        for sy in (-1, 1):
            parts.append(box(name + "_rake", T @ T_at(sx * hw * 0.5, sy * hd, eave_z + rh * 0.5,
                                                     ry=math.atan2(-rh, -sx * hw)),
                             (rl, 0.09, 0.15), metal_mat, bev=0.012))
    return parts


# --------------------------------------------------------------------------
# reusable detail assemblies
# --------------------------------------------------------------------------
def window(name, T, w, h, frame_mat, glass_mat, shutter_mat=None, mullions=2):
    """Recessed window: dark reveal, glass set back ~4 cm, frame, bars, shutters."""
    parts = []
    # glass sits behind the wall plane so the frame casts a shadow into the reveal
    parts.append(box(name + "_open", T @ T_at(0, -0.045, 0), (w, 0.05, h), glass_mat))
    fw = 0.075
    for sx in (-1, 1):
        parts.append(box(name + "_rv%d" % sx,
                         T @ T_at(sx * (w * 0.5 - 0.016), -0.022, 0),
                         (0.032, 0.075, h), frame_mat))
    parts.append(box(name + "_rvt", T @ T_at(0, -0.022, h * 0.5 - 0.016),
                     (w, 0.075, 0.032), frame_mat))
    parts.append(box(name + "_rvb", T @ T_at(0, -0.022, -h * 0.5 + 0.016),
                     (w, 0.075, 0.032), frame_mat))
    for sx in (-1, 1):
        parts.append(box(name + "_fv", T @ T_at(sx * (w * 0.5 - fw * 0.5), 0.055, 0),
                         (fw, 0.11, h + fw * 2), frame_mat, bev=0.008))
    for sz in (-1, 1):
        parts.append(box(name + "_fh", T @ T_at(0, 0.055, sz * (h * 0.5 - fw * 0.5)),
                         (w + fw * 2, 0.11, fw), frame_mat, bev=0.008))
    parts.append(box(name + "_sill", T @ T_at(0, 0.12, -h * 0.5 - fw),
                     (w + 0.30, 0.24, 0.07), frame_mat, bev=0.01))
    for i in range(mullions):
        x = (i + 1) * w / (mullions + 1) - w * 0.5
        parts.append(box(name + "_m%d" % i, T @ T_at(x, 0.02, 0),
                         (0.045, 0.07, h), frame_mat))
    parts.append(box(name + "_tr", T @ T_at(0, 0.02, 0), (w, 0.07, 0.045), frame_mat))
    if shutter_mat is not None:
        for sx in (-1, 1):
            parts.append(box(name + "_sh", T @ T_at(sx * (w * 0.5 + w * 0.30), 0.10, 0),
                             (w * 0.55, 0.05, h * 1.02), shutter_mat, bev=0.01))
    return parts


def door(name, T, w, h, wood_mat, iron_mat):
    parts = []
    parts.append(box(name + "_leaf", T @ T_at(0, 0.06, h * 0.5), (w, 0.10, h), wood_mat, bev=0.012))
    # planks
    n = 4
    for i in range(n + 1):
        x = -w * 0.5 + w * i / n
        parts.append(box(name + "_pl%d" % i, T @ T_at(x, 0.115, h * 0.5),
                         (0.022, 0.02, h * 0.97), iron_mat))
    # hinges
    for i, z in enumerate((h * 0.28, h * 0.78)):
        parts.append(box(name + "_hg%d" % i, T @ T_at(w * 0.10, 0.125, z),
                         (w * 0.62, 0.025, 0.055), iron_mat, bev=0.006))
    parts.append(sphere(name + "_knob", T @ T_at(w * 0.32, 0.15, h * 0.50),
                        0.045, iron_mat, seg=12, ring=8))
    # arch frame
    for sx in (-1, 1):
        parts.append(box(name + "_post", T @ T_at(sx * (w * 0.5 + 0.06), 0.09, h * 0.5),
                         (0.12, 0.20, h), wood_mat, bev=0.01))
    parts.append(box(name + "_lint", T @ T_at(0, 0.09, h + 0.06),
                     (w + 0.24, 0.22, 0.14), wood_mat, bev=0.012))
    # stone step
    parts.append(box(name + "_step", T @ T_at(0, 0.30, 0.06), (w + 0.5, 0.7, 0.12),
                     mat_stone("stone_step"), bev=0.02))
    return parts


def lantern(name, T, iron_mat, glow_mat, scale=1.0):
    parts = []
    parts.append(box(name + "_arm", T @ T_at(0, 0, 0), (0.05, 0.42, 0.05), iron_mat))
    parts.append(box(name + "_cage", T @ T_at(0, 0.40, -0.20 * scale),
                     (0.17 * scale, 0.17 * scale, 0.24 * scale), iron_mat))
    parts.append(box(name + "_glass", T @ T_at(0, 0.40, -0.20 * scale),
                     (0.13 * scale, 0.13 * scale, 0.19 * scale), glow_mat))
    parts.append(cone(name + "_cap", T @ T_at(0, 0.40, -0.05 * scale),
                      0.13 * scale, 0.10 * scale, iron_mat, seg=4))
    return parts


def flowerbox(name, T, w, wood_mat, leaf_mat, bloom_mat, rng):
    parts = [box(name + "_b", T @ T_at(0, 0, 0), (w, 0.20, 0.16), wood_mat, bev=0.01)]
    n = max(3, int(w / 0.16))
    for i in range(n):
        x = -w * 0.5 + w * (i + 0.5) / n
        parts.append(sphere(name + "_l%d" % i,
                            T @ T_at(x, 0.02, 0.13 + rng.uniform(0, 0.04)),
                            0.075 + rng.uniform(0, 0.03), leaf_mat, seg=8, ring=6))
        if rng.random() < 0.55:
            parts.append(sphere(name + "_f%d" % i,
                                T @ T_at(x + rng.uniform(-0.03, 0.03),
                                         0.04, 0.19 + rng.uniform(0, 0.03)),
                                0.032, bloom_mat, seg=6, ring=5))
    return parts
