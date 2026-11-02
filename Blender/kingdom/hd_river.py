"""The river the capital stands on.

The generator has carried a `RIVER_Y` constant since the first version and
builds a harbour with quay walls, piers, warehouses, a crane and boats around
it -- but the river itself was a 2 m box at z = -1.1 sitting underneath a
1284 m ground plate, so it was completely buried.  Every render of the city so
far shows an inland town with no water in it at all, and the harbour reads as
warehouses standing in a field.

This module puts the water where it can be seen: south of the outer wall, on
the approach to the south gate.  It

  * moves the channel outside the enceinte (the wall is a 620-666 m polygon,
    the channel now sits at y = -762, so nothing has to be cut open),
  * splits the outer ground plate in two along the banks, so the water is not
    under a lid any more,
  * walls both banks in stone with a coping course and stairs,
  * spans the south road with a three-arch segmental bridge,
  * and rebuilds the water material: medkit's `mat_water` is a flat teal with
    roughness 0.10, which in EEVEE reflects nothing and reads as painted
    lino.  A river has to be almost a mirror at grazing angles.

Everything is built from explicit vertex lists so the module has no dependency
on capital.py's local helpers; it only needs medkit's `mesh_obj` / `assign`.
"""
import math

# channel geometry (world metres)
RIVER_Y = -762.0
RIVER_W = 92.0
WATER_Z = -0.62
BED_Z = -2.60
QUAY_Z = 0.14
BANK_N = RIVER_Y + RIVER_W * 0.5      # -716
BANK_S = RIVER_Y - RIVER_W * 0.5      # -808
HALF_X = 1100.0
GROUND_Z = -0.35

BRIDGE_WIDTH = 9.6
BRIDGE_LEN = RIVER_W + 30.0


# ---------------------------------------------------------------- utilities
def _obj(K, name, verts, faces, mat, smooth=False):
    ob = K.mesh_obj(name, verts, faces, smooth=smooth)
    if ob is not None:
        K.assign(ob, mat)
    return ob


def _box(K, name, cx, cy, cz, sx, sy, sz, mat, bev=None):
    """Axis-aligned box from explicit verts (no capital.py dependency)."""
    hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
    v = [(cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
         (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
         (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
         (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
         (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return _obj(K, name, v, f, mat)


def _ring_fan(K, name, pts, z, mat, flip=False):
    """Closed 2D polygon -> flat slab with a fan triangulation."""
    n = len(pts)
    cx = sum(p[0] for p in pts) / float(n)
    cy = sum(p[1] for p in pts) / float(n)
    v = [(p[0], p[1], z) for p in pts]
    v.append((cx, cy, z))
    c = n
    f = []
    for i in range(n):
        a, b = i, (i + 1) % n
        f.append((c, b, a) if flip else (c, a, b))
    return _obj(K, name, v, f, mat)


# ---------------------------------------------------------------- ground
def ground_half(K, name, r, z, mat, y_edge, keep=1, seg=180):
    """A disc clipped by the horizontal line y = y_edge.

    keep = +1 keeps the part above the line (y >= y_edge), -1 the part below.
    The clipped region is a circular segment, which is convex, so a fan from
    its centroid is a valid triangulation and the winding is exact.
    """
    if y_edge is None or abs(y_edge) >= r:
        pts = [(r * math.cos(2 * math.pi * k / seg),
                r * math.sin(2 * math.pi * k / seg)) for k in range(seg)]
        return _ring_fan(K, name, pts, z, mat)

    a0 = math.asin(max(-1.0, min(1.0, y_edge / r)))
    n = max(8, int(seg * (math.pi - 2 * a0) / (2 * math.pi)) + 2)
    pts = []
    for k in range(n):
        a = a0 + (math.pi - 2 * a0) * k / float(n - 1)
        pts.append((r * math.cos(a), r * math.sin(a)))
    if keep > 0:
        return _ring_fan(K, name, pts, z, mat)
    mirror = [(p[0], -p[1]) for p in pts]
    mirror.reverse()
    return _ring_fan(K, name, mirror, z, mat)


def ground(K, MAT, r=980.0, z=GROUND_Z):
    """The outer plate, split along the two banks so the water is visible."""
    out = [ground_half(K, "ground_outer_n", r, z, MAT["grass"], BANK_N, +1),
           ground_half(K, "ground_outer_s", r, z, MAT["grass"], BANK_S, -1)]
    return [o for o in out if o is not None]


# ---------------------------------------------------------------- material
def water_material(MAT, name="water"):
    """A river, not a teal plate: near-mirror, with broken-up normals."""
    m = MAT.get(name)
    if m is None:
        import bpy
        m = bpy.data.materials.new(name)
        MAT[name] = m
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (900, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (600, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    co = nt.nodes.new("ShaderNodeTexCoord")
    co.location = (-900, 0)

    def noise(scale, detail, rough, loc):
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.location = loc
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        nt.links.new(co.outputs["Object"], n.inputs["Vector"])
        return n

    def ramp(src, stops, loc):
        r = nt.nodes.new("ShaderNodeValToRGB")
        r.location = loc
        r.color_ramp.elements.remove(r.color_ramp.elements[1])
        first = r.color_ramp.elements[0]
        first.position, first.color = stops[0][0], stops[0][1]
        for pos, col in stops[1:]:
            e = r.color_ramp.elements.new(pos)
            e.color = col
        nt.links.new(src, r.inputs["Fac"])
        return r

    def rgba(hexs):
        h = hexs.lstrip("#")
        srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
        return (lin[0], lin[1], lin[2], 1.0)

    # colour: deep channel green-blue in the middle, silty green at the banks.
    # the depth cue is a broad noise so it does not read as a stripe.
    deep = noise(0.012, 2.0, 0.5, (-700, 260))
    col = ramp(deep.outputs["Fac"], [(0.32, rgba("#123540")), (0.68, rgba("#2f6a63"))],
               (-420, 260))
    # a second, finer tint keeps large areas from going flat
    tint = noise(0.085, 3.0, 0.55, (-700, 60))
    col2 = ramp(tint.outputs["Fac"], [(0.30, rgba("#0e2a33")), (0.72, rgba("#3c7a70"))],
                (-420, 60))
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MIX"
    mix.location = (-120, 160)
    mix.inputs["Factor"].default_value = 0.45
    ins = [s for s in mix.inputs if s.type == "RGBA"]
    nt.links.new(col.outputs["Color"], ins[0])
    nt.links.new(col2.outputs["Color"], ins[1])
    cout = next(s for s in mix.outputs if s.type == "RGBA")
    nt.links.new(cout, bsdf.inputs["Base Color"])

    # ripples: two scales of noise into one bump.  0.30 m chop over a 3.5 m
    # swell is what makes a still river read as water and not as glass.
    n1 = noise(0.30, 3.0, 0.6, (-700, -160))
    n2 = noise(3.5, 2.0, 0.45, (-700, -360))
    mixn = nt.nodes.new("ShaderNodeMix")
    mixn.data_type = "FLOAT"
    mixn.location = (-120, -220)
    mixn.inputs["Factor"].default_value = 0.42
    nt.links.new(n1.outputs["Fac"], mixn.inputs[2])
    nt.links.new(n2.outputs["Fac"], mixn.inputs[3])
    nout = next(s for s in mixn.outputs if s.type == "VALUE")
    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (280, -220)
    bump.inputs["Strength"].default_value = 0.085
    bump.inputs["Distance"].default_value = 0.06
    nt.links.new(nout, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    bsdf.inputs["Roughness"].default_value = 0.045
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["IOR"].default_value = 1.333
    for key in ("Specular IOR Level", "Specular"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.55
    return m


# ---------------------------------------------------------------- channel
def channel(K, MAT):
    out = []
    mat_w = water_material(MAT)
    # water surface
    out.append(_obj(K, "river_water",
                    [(-HALF_X, BANK_S - 2.0, WATER_Z), (HALF_X, BANK_S - 2.0, WATER_Z),
                     (HALF_X, BANK_N + 2.0, WATER_Z), (-HALF_X, BANK_N + 2.0, WATER_Z)],
                    [(0, 1, 2, 3)], mat_w))
    # bed, so the channel is not a hole onto the void when seen from above
    out.append(_box(K, "river_bed", 0.0, RIVER_Y, BED_Z, HALF_X * 2.0, RIVER_W + 4.0,
                    0.6, MAT["stone_warm"]))
    # quay walls: the town side is a dressed wall with a coping, the far side
    # is lower rubble so the river still reads as a natural bank from the city
    for tag, y, h, thick in (("n", BANK_N, QUAY_Z, 2.4), ("s", BANK_S, 0.05, 2.0)):
        top = h
        out.append(_box(K, "quay_%s" % tag, 0.0, y, (top + BED_Z) * 0.5,
                        HALF_X * 2.0, thick, top - BED_Z, MAT["stone_warm"]))
        # coping course proud of the wall face
        out.append(_box(K, "quay_%s_coping" % tag, 0.0, y, top + 0.09,
                        HALF_X * 2.0, thick + 0.5, 0.30, MAT["stone"]))
    # stairs down to the water on the town side, both banks of the bridge
    for i, sx in enumerate((-96.0, -52.0, 52.0, 96.0)):
        for k in range(5):
            out.append(_box(K, "quay_stair%d_%d" % (i, k), sx, BANK_N - 1.2 - k * 0.62,
                            QUAY_Z - 0.14 - k * 0.36, 5.2, 1.3, 0.36, MAT["stone"]))
    return out


# ---------------------------------------------------------------- bridge
def _arc(half, z_spring, z_crown, n):
    """Points on a circular segment, left spring -> crown -> right spring."""
    dz = z_spring - z_crown
    if abs(dz) < 1e-6 or abs(dz) > half:
        pts = []
        for k in range(n):
            t = -1.0 + 2.0 * k / (n - 1)
            pts.append((t * half, z_crown - (1.0 - t * t) * 0.0))
        return pts
    R = -(half * half + dz * dz) / (2.0 * dz)
    cz = z_crown - R
    tmax = math.asin(max(-1.0, min(1.0, half / R)))
    pts = []
    for k in range(n):
        t = -tmax + 2.0 * tmax * k / (n - 1)
        pts.append((R * math.sin(t), cz + R * math.cos(t)))
    return pts


def bridge(K, MAT, cx, cy, ang):
    """Three-arch segmental stone bridge along the road direction `ang`."""
    ca, sa = math.cos(ang), math.sin(ang)

    def W(u, v, z):
        return (cx + u * ca - v * sa, cy + u * sa + v * ca, z)

    half = BRIDGE_LEN * 0.5
    hw = BRIDGE_WIDTH * 0.5
    out = []

    def deck_z(u):
        t = u / half
        return 0.55 + 0.80 * (1.0 - t * t)

    # deck: a strip of quads following the hump
    nseg = 24
    verts, faces = [], []
    for k in range(nseg + 1):
        u = -half + 2.0 * half * k / nseg
        z = deck_z(u)
        verts.append(W(u, -hw, z))
        verts.append(W(u, hw, z))
    for k in range(nseg):
        a = k * 2
        faces.append((a, a + 2, a + 3, a + 1))
    out.append(_obj(K, "bridge_deck", verts, faces, MAT["flag"]))
    # deck underside / spandrel band, closed with a box under the hump
    for k in range(nseg):
        u0 = -half + 2.0 * half * k / nseg
        u1 = -half + 2.0 * half * (k + 1) / nseg
        # the local frame origin is (cx, cy): without it every rib lands at the
        # world origin, which is a 1.1 m stone band lying across the castle
        # plaza in every plaza camera (found by the CAMERA agent's ray_cast QA)
        _um = (u0 + u1) * 0.5
        out.append(_box(K, "bridge_rib%d" % k, cx + _um * ca, cy + _um * sa,
                        deck_z(_um) - 0.42,
                        (u1 - u0) * 1.02, BRIDGE_WIDTH, 0.36, MAT["stone"]))

    piers = (-29.0, 0.0, 29.0)
    pier_w = 7.0
    spans = [(-half, piers[0] - pier_w * 0.5), (piers[0] + pier_w * 0.5, piers[1] - pier_w * 0.5),
             (piers[1] + pier_w * 0.5, piers[2] - pier_w * 0.5), (piers[2] + pier_w * 0.5, half)]
    for i, (ua, ub) in enumerate(spans):
        um = (ua + ub) * 0.5
        h = (ub - ua) * 0.5
        zs = -1.55
        zc = deck_z(um) - 0.95
        arc = _arc(h, zs, zc, 15)
        # soffit: the curved underside of the arch, spanning the bridge width
        v, f = [], []
        for (du, z) in arc:
            v.append(W(um + du, -hw + 0.3, z))
            v.append(W(um + du, hw - 0.3, z))
        for k in range(len(arc) - 1):
            a = k * 2
            f.append((a, a + 1, a + 3, a + 2))
        out.append(_obj(K, "bridge_soffit%d" % i, v, f, MAT["stone"]))
        # the two visible faces: arch ring + spandrel up to the deck
        for side in (-1, 1):
            vv, ff = [], []
            n = len(arc)
            for (du, z) in arc:
                vv.append(W(um + du, side * hw, z))
            for (du, z) in arc:
                vv.append(W(um + du, side * hw, z + 0.85))
            for k in range(n - 1):
                a, b = k, k + 1
                ff.append((a, b, n + b, n + a))
            base = len(vv)
            for (du, z) in arc:
                vv.append(W(um + du, side * hw, z + 0.85))
            for (du, z) in arc:
                vv.append(W(um + du, side * hw, deck_z(um + du) - 0.10))
            for k in range(n - 1):
                a, b = base + k, base + k + 1
                ff.append((a, b, base + n + b, base + n + a))
            if side < 0:
                ff = [tuple(reversed(q)) for q in ff]
            out.append(_obj(K, "bridge_face%d_%s" % (i, "a" if side < 0 else "b"),
                            vv, ff, MAT["stone"]))
    for i, u in enumerate(piers):
        out.append(_box(K, "bridge_pier%d" % i, cx + u * ca, cy + u * sa,
                        (deck_z(u) - 1.9) * 0.5 + BED_Z * 0.5,
                        pier_w, BRIDGE_WIDTH + 1.0, deck_z(u) - 1.9 - BED_Z, MAT["stone"]))
        # cutwater on the upstream face
        out.append(_box(K, "bridge_cut%d" % i, cx + u * ca + 0.0, cy + u * sa,
                        (deck_z(u) - 1.9) * 0.5 + BED_Z * 0.5,
                        pier_w * 0.55, BRIDGE_WIDTH + 1.6, deck_z(u) - 1.9 - BED_Z,
                        MAT["stone"]))
    # parapets
    for side in (-1, 1):
        v, f = [], []
        for k in range(nseg + 1):
            u = -half + 2.0 * half * k / nseg
            z = deck_z(u)
            v.append(W(u, side * hw, z))
            v.append(W(u, side * hw, z + 0.95))
        for k in range(nseg):
            a = k * 2
            q = (a, a + 2, a + 3, a + 1) if side > 0 else (a + 1, a + 3, a + 2, a)
            f.append(q)
        out.append(_obj(K, "bridge_parapet%s" % ("a" if side < 0 else "b"), v, f, MAT["stone"]))
    return out


# ---------------------------------------------------------------- entry
def build(K, MAT, gaps=(), ground_r=980.0):
    """Ground halves + channel + one bridge per road that crosses the river."""
    out = list(ground(K, MAT, r=ground_r))
    out += channel(K, MAT)
    if gaps:
        for gp, ang in gaps:
            ux, uy = math.cos(ang), math.sin(ang)
            # does this radial road actually cross the channel?
            if abs(uy) < 0.35:
                continue
            t = RIVER_Y / uy if abs(uy) > 1e-6 else None
            if t is None or t <= 0:
                continue
            cx, cy = ux * t, uy * t
            if math.hypot(cx, cy) > ground_r + 40.0:
                continue
            out += bridge(K, MAT, cx, cy, ang)
    return [o for o in out if o is not None]
