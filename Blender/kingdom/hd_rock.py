"""hd_rock.py - the crag the castle stands on, and the escarpment round the city.

Two jobs:

    build(K, MAT, cx, cy, r, top_z, seed, style)   the castle rock
    cliff_ring(K, MAT, r=R_OUTER, ...)             the rock rim outside the town

Everything is a *height/radius function of world position*: the bedding dip, the
joint blocks and the road notch are analytic, so the meshes stay in register
with each other and with the shader (which reads Object coordinates and applies
the same dip).  That is the whole point of this module: the previous rock was a
stack of cylinders with noise sprinkled on it, and no amount of noise makes a
cylinder read as rock -- beds and joints do.

Geology the geometry encodes (all of it is what the eye checks first):

  * beds 0.6-2.5 m thick, each with its own hardness.  A hard bed stands proud
    and the soft one under it is eaten back, so every bedding plane throws a
    horizontal ledge with a shadow under it.  The planes dip with the slope.
  * vertical joints cut each bed into 2-6 m blocks, and the joint phase is
    re-drawn *per bed*, so columns start and stop at bedding planes instead of
    running through the mass like a tile wall.
  * talus at 33 deg below the cliff, boulders power-law sized 0.3-3 m.
  * a rock-cut corniche road: the face is pushed in by the road width for the
    whole height above the deck, so the road has a rock wall above it (not a
    cave mouth -- an overhanging cut is the classic way this goes wrong) and a
    drop below it.

Units are metres.  Triangle budget: 400 k for the crag, 300 k for the ring.
"""

import math
import os
import random
import sys

import bpy

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

TAU = math.tau

# --------------------------------------------------------------------------- #
#  numbers that the geometry AND the shader must agree on
# --------------------------------------------------------------------------- #
# Bedding dip: the bedding planes are u = const with u = z + DIP_X*x + DIP_Y*y.
# 0.021/0.013 is a 1.4 deg dip -- across the 160 m crag that is +-1.9 m of
# bedding-plane offset, which reads as real dip and still keeps the beds inside
# the 18 m of rock.
DIP = (0.021, 0.013)

# the crag's radial profile, as fractions of the requested radius
RIM_F = 0.770          # plateau rim radius / r   (63.1 m at r = 82)
CLIFF_F = 0.440        # bottom of the bare cliff, as a fraction of top_z
BATTER = 2.60          # how much the face leans back over the cliff band
TAL_K = 1.54           # 1 / tan(33 deg): run per metre of drop on the talus
APRON_Z = 0.55         # the debris fan leaves the 33 deg chute at this height
APRON_K = 12.0

# Spurs and gullies.  A crag seen from 200 m is *not* a cone with a noisy
# surface: what carries the eye is a rib-and-gully system, 8-120 m across, that
# runs unbroken through the bedding.  So the modulation is angular (it lives on
# every row, beds included) and its amplitude fades to nothing at the rim so the
# plateau edge stays where the castle needs it.
SPUR = ((3.0, 1.55, 0.42),      # (harmonic, amplitude m, phase)
        (7.0, 0.98, 2.10),
        (13.0, 0.62, 4.05),
        (23.0, 0.34, 1.73),
        (41.0, 0.17, 5.20))

# road
ROAD_W = 4.7           # deck width, wall to parapet
ROAD_D = 5.0           # how far the face is pushed in above the deck
HAIRPIN_D = 10.4       # switchback platforms need a wider bite

# palette per style.  Values are sRGB hex so they can be picked by eye.
# Under morning_town the sun is 5 W/m2 and the exposure is -2.2, so anything
# over about 0.55 sRGB blows out to paper.  These sit well under the castle's
# limestone (#c4b393) on purpose: the rock has to be the dark thing the pale
# keep stands on.
_PALETTE = {
    "limestone": dict(
        base="#6d6757", dark="#3b382c", light="#8c8473", warm="#7b6e59",
        dust="#827a66", moss="#3f4a26", moss2="#5f6b34", lichen="#82875c",
        wet="#2b2c26", road="#6d6453"),
    "sandstone": dict(
        base="#8a7052", dark="#4e3a28", light="#a98c68", warm="#9a7852",
        dust="#9d8b70", moss="#49542b", moss2="#6c753e", lichen="#8a8760",
        wet="#423a30", road="#7f6e58"),
    "granite": dict(
        base="#76766f", dark="#403f3b", light="#98978f", warm="#7a7267",
        dust="#8b8780", moss="#414f2c", moss2="#5f6c3d", lichen="#878f68",
        wet="#333531", road="#726c64"),
}


def clamp(v, a, b):
    return a if v < a else (b if v > b else v)


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(a, b, x):
    if b == a:
        return 0.0 if x < a else 1.0
    t = clamp((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# --------------------------------------------------------------------------- #
#  value noise on a lattice, seeded, seamless in world space
# --------------------------------------------------------------------------- #
class VNoise(object):
    """Bilinear-smooth value noise over a 256x256 torus of random values.

    Evaluated in world XY, so theta = 0 and theta = 2pi are the same point and
    the ring never shows a seam (a per-theta noise would).
    """

    __slots__ = ("g", "mask")

    def __init__(self, seed):
        rng = random.Random(seed)
        self.g = [rng.random() * 2.0 - 1.0 for _ in range(65536)]
        self.mask = 255

    def at(self, x, y, s):
        """One octave, lattice spacing s metres, output -1..1."""
        u = x / s
        v = y / s
        i = int(math.floor(u))
        j = int(math.floor(v))
        fu = u - i
        fv = v - j
        fu = fu * fu * (3.0 - 2.0 * fu)
        fv = fv * fv * (3.0 - 2.0 * fv)
        g = self.g
        m = self.mask
        i &= m
        j &= m
        i1 = (i + 1) & m
        j1 = (j + 1) & m
        a = g[(i << 8) | j]
        b = g[(i1 << 8) | j]
        c = g[(i << 8) | j1]
        d = g[(i1 << 8) | j1]
        return lerp(lerp(a, b, fu), lerp(c, d, fu), fv)

    def fbm(self, x, y, s, oct=3, gain=0.5):
        v = 0.0
        amp = 1.0
        norm = 0.0
        for _ in range(oct):
            v += amp * self.at(x, y, s)
            norm += amp
            amp *= gain
            s *= 0.47
        return v / norm


def _n(x, y, s, seed=0):
    """Convenience: deterministic single-octave noise without an instance."""
    return _NZ(seed).at(x, y, s)


_NZC = {}


def _NZ(seed):
    n = _NZC.get(seed)
    if n is None:
        n = VNoise(9176 + seed * 131)
        _NZC[seed] = n
    return n


# --------------------------------------------------------------------------- #
#  mesh buffer with material slots
# --------------------------------------------------------------------------- #
class MB(object):
    """Accumulate verts/faces/material indices, emit one object."""

    __slots__ = ("v", "f", "mi", "mats", "smooth")

    def __init__(self, smooth=False):
        self.v = []
        self.f = []
        self.mi = []
        self.mats = []
        self.smooth = smooth

    def slot(self, mat):
        try:
            return self.mats.index(mat)
        except ValueError:
            self.mats.append(mat)
            return len(self.mats) - 1

    def add(self, verts, faces, mat=0):
        o = len(self.v)
        self.v.extend(verts)
        for fc in faces:
            self.f.append(tuple(o + i for i in fc))
            self.mi.append(mat)
        return o

    def quad(self, a, b, c, d, mat=0):
        o = len(self.v)
        self.v.extend((a, b, c, d))
        self.f.append((o, o + 1, o + 2, o + 3))
        self.mi.append(mat)
        return o

    def tris(self, verts, faces, mat=0):
        return self.add(verts, faces, mat)

    def push(self, K, name, smooth=None):
        if not self.f:
            return None
        ob = K.mesh_obj(name, self.v, self.f, smooth=self.smooth if smooth is None else smooth)
        K.assign(ob, *self.mats)
        if len(self.mats) > 1:
            for p, mi in zip(ob.data.polygons, self.mi):
                p.material_index = mi
        for p in ob.data.polygons:
            p.use_smooth = self.smooth if smooth is None else smooth
        return ob


_ICO_V = None
_ICO_F = None


def _ico_tables():
    global _ICO_V, _ICO_F
    if _ICO_V is not None:
        return _ICO_V, _ICO_F
    t = (1.0 + 5.0 ** 0.5) * 0.5
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
         (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    n = math.sqrt(1.0 + t * t)
    v = [(a / n, b / n, c / n) for (a, b, c) in v]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
         (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
         (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    _ICO_V, _ICO_F = v, f
    return v, f


def ico_emit(mb, center, radius, rng, mat=0, sub=0, squash=(1.0, 1.0, 1.0),
             jitter=0.26, rot=None):
    """Add a deformed icosphere; returns the first vertex index.

    sub=0 is 20 faces, sub=1 is 80 -- a boulder at 30 m is 20 faces, one at 8 m
    is 80, and that is the whole LOD story here.
    """
    vs, fs = _ico_tables()
    if sub:
        vs2 = list(vs)
        mid = {}
        fs2 = []

        def _m(a, b):
            k = (a, b) if a < b else (b, a)
            i = mid.get(k)
            if i is None:
                pa, pb = vs2[a], vs2[b]
                x, y, z = (pa[0] + pb[0], pa[1] + pb[1], pa[2] + pb[2])
                d = math.sqrt(x * x + y * y + z * z) or 1.0
                vs2.append((x / d, y / d, z / d))
                i = len(vs2) - 1
                mid[k] = i
            return i

        for (a, b, c) in fs:
            ab, bc, ca = _m(a, b), _m(b, c), _m(c, a)
            fs2 += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        vs = vs2
        fs = fs2
    out = []
    cx, cy, cz = center
    sx, sy, sz = squash
    for (x, y, z) in vs:
        r = radius * (1.0 + jitter * rng.uniform(-1.0, 1.0))
        px, py, pz = x * r * sx, y * r * sy, z * r * sz
        if rot is not None:
            ca, sa = math.cos(rot), math.sin(rot)
            px, py = px * ca - py * sa, px * sa + py * ca
        # squash the bottom so a boulder reads as sitting in the ground
        out.append((cx + px, cy + py, cz + pz))
    return mb.add(out, fs, mat)


def _tube_mb(mb, pts, radii, sides, mat, cap=True):
    """A swept tube through pts: vines, hanging plants, a dead branch."""
    n = len(pts)
    base = len(mb.v)
    for i, (p, r) in enumerate(zip(pts, radii)):
        if i == 0:
            d = (pts[1][0] - p[0], pts[1][1] - p[1], pts[1][2] - p[2])
        elif i == n - 1:
            d = (p[0] - pts[-2][0], p[1] - pts[-2][1], p[2] - pts[-2][2])
        else:
            d = (pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1],
                 pts[i + 1][2] - pts[i - 1][2])
        ln = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1.0
        dx, dy, dz = d[0] / ln, d[1] / ln, d[2] / ln
        ux, uy, uz = 0.0, 0.0, 1.0
        if abs(dz) > 0.95:
            ux, uy, uz = 1.0, 0.0, 0.0
        ax = dy * uz - dz * uy
        ay = dz * ux - dx * uz
        az = dx * uy - dy * ux
        al = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
        ax, ay, az = ax / al, ay / al, az / al
        bx = ay * dz - az * dy
        by = az * dx - ax * dz
        bz = ax * dy - ay * dx
        for s in range(sides):
            ang = TAU * s / sides
            ca, sa = math.cos(ang), math.sin(ang)
            mb.v.append((p[0] + r * (ca * ax + sa * bx),
                         p[1] + r * (ca * ay + sa * by),
                         p[2] + r * (ca * az + sa * bz)))
    for i in range(n - 1):
        for s in range(sides):
            s2 = (s + 1) % sides
            mb.f.append((base + i * sides + s, base + i * sides + s2,
                         base + (i + 1) * sides + s2, base + (i + 1) * sides + s))
            mb.mi.append(mat)
    if cap:
        mb.f.append(tuple(base + s for s in range(sides - 1, -1, -1)))
        mb.mi.append(mat)


# --------------------------------------------------------------------------- #
#  node helpers
# --------------------------------------------------------------------------- #
class NT(object):
    """Tiny wrapper so a 150-node graph stays readable."""

    def __init__(self, m):
        self.nt = m.node_tree
        self.nodes = self.nt.nodes
        self.links = self.nt.links
        self._x = 0

    def new(self, kind, **kw):
        n = self.nodes.new(kind)
        for k, v in kw.items():
            setattr(n, k, v)
        self._x -= 180
        n.location = (self._x, 0)
        return n

    def link(self, out, inp):
        self.links.new(out, inp)

    def inp(self, node, name, value):
        s = node.inputs.get(name)
        if s is not None:
            try:
                s.default_value = value
            except (TypeError, ValueError):
                pass
        return node

    # --- maths -----------------------------------------------------------
    def math(self, op, a, b=None, c=None, clamp_=False):
        n = self.new("ShaderNodeMath", operation=op, use_clamp=clamp_)
        for i, x in enumerate((a, b, c)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = float(x)
            else:
                self.link(x, n.inputs[i])
        return n.outputs[0]

    def mul(self, a, b, clamp_=False):
        return self.math("MULTIPLY", a, b, clamp_=clamp_)

    def add(self, a, b):
        return self.math("ADD", a, b)

    def sub(self, a, b):
        return self.math("SUBTRACT", a, b)

    def mr(self, src, flo, fhi, tlo, thi, clamp_=True):
        n = self.new("ShaderNodeMapRange")
        try:
            n.clamp = clamp_
        except AttributeError:
            pass
        if isinstance(src, (int, float)):
            n.inputs["Value"].default_value = float(src)
        else:
            self.link(src, n.inputs["Value"])
        n.inputs["From Min"].default_value = float(flo)
        n.inputs["From Max"].default_value = float(fhi)
        n.inputs["To Min"].default_value = float(tlo)
        n.inputs["To Max"].default_value = float(thi)
        return n.outputs[0]

    def mixc(self, a, b, fac, blend="MIX"):
        n = self.new("ShaderNodeMixRGB", blend_type=blend)
        for sock, val in ((n.inputs["Color1"], a), (n.inputs["Color2"], b),
                          (n.inputs["Fac"], fac)):
            if isinstance(val, str):
                sock.default_value = _rgba(val)
            elif isinstance(val, (int, float)):
                sock.default_value = float(val)
            elif isinstance(val, tuple):
                sock.default_value = val
            else:
                self.link(val, sock)
        return n.outputs[0]

    def noise(self, vec, scale, detail=4.0, rough=0.55, dist=0.0):
        n = self.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = float(scale)
        n.inputs["Detail"].default_value = float(detail)
        n.inputs["Roughness"].default_value = float(rough)
        if "Distortion" in n.inputs:
            n.inputs["Distortion"].default_value = float(dist)
        self.link(vec, n.inputs["Vector"])
        return n.outputs["Fac"]

    def voronoi(self, vec, scale, feature="DISTANCE_TO_EDGE", randomness=1.0):
        n = self.new("ShaderNodeTexVoronoi", feature=feature)
        n.inputs["Scale"].default_value = float(scale)
        if "Randomness" in n.inputs:
            n.inputs["Randomness"].default_value = float(randomness)
        self.link(vec, n.inputs["Vector"])
        return n.outputs["Distance"]

    def white(self, w):
        n = self.new("ShaderNodeTexWhiteNoise", noise_dimensions="1D")
        if isinstance(w, (int, float)):
            n.inputs["W"].default_value = float(w)
        else:
            self.link(w, n.inputs["W"])
        return n.outputs["Value"]

    def ramp(self, fac, stops, interp="LINEAR"):
        n = self.new("ShaderNodeValToRGB")
        n.color_ramp.interpolation = interp
        cb = n.color_ramp.elements
        while len(cb) > 1:
            cb.remove(cb[-1])
        cb[0].position = stops[0][0]
        cb[0].color = _rgba(stops[0][1])
        for (p, col) in stops[1:]:
            e = cb.new(p)
            e.color = _rgba(col)
        if isinstance(fac, (int, float)):
            n.inputs["Fac"].default_value = float(fac)
        else:
            self.link(fac, n.inputs["Fac"])
        return n.outputs["Color"]

    def vmath(self, op, a, b=None):
        n = self.new("ShaderNodeVectorMath", operation=op)
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (tuple, list)):
                n.inputs[i].default_value = x
            else:
                self.link(x, n.inputs[i])
        return n.outputs["Vector"]


def _srgb_to_lin(u):
    u = u / 255.0
    return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4


def _rgba(hexstr, a=1.0):
    h = hexstr.lstrip("#")
    return (_srgb_to_lin(int(h[0:2], 16)), _srgb_to_lin(int(h[2:4], 16)),
            _srgb_to_lin(int(h[4:6], 16)), a)


def _bsdf_of(m):
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def _setin(node, names, value):
    for k in names:
        s = node.inputs.get(k)
        if s is not None:
            try:
                s.default_value = value
                return True
            except (TypeError, ValueError):
                pass
    return False


# --------------------------------------------------------------------------- #
#  the rock material
# --------------------------------------------------------------------------- #
def rock_material(MAT, name="rock_strata", style="limestone", dip=None,
                  lichen=1.0, wet=1.0):
    """Strata-driven rock, keyed off the *geometric normal*.

    A rock face and a rock bed-top are two different surfaces and must not be
    the same shader with noise on it:

      face  -> horizontal beds (colour steps at the bedding planes, soft beds
               recessive), vertical joints, water streaks running DOWN
      top   -> bed tops: dust, sun-bleached, cracked, lichen, no bedding at all

    `flat = |N.z|` blends the two recipes.  That is the "geometry normal drives
    the bedding direction" requirement: the bedding coordinate is a dip plane in
    Z, so it is only ever visible where the surface is not itself a bedding
    plane, and the bed tops get their own treatment instead of smeared streaks.

    Everything reads Object coordinates.  The caller must keep the objects at
    the world origin (which hd_rock's own objects are), so Object == world and
    the shader's dip matches DIP in this file exactly.
    """
    old = bpy.data.materials.get(name)
    if old is not None:
        return old
    dip = DIP if dip is None else dip
    pal = _PALETTE.get(style) or _PALETTE["limestone"]

    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in ("OUTPUT_MATERIAL",):
            nt.nodes.remove(n)
    out = None
    for n in nt.nodes:
        if n.type == "OUTPUT_MATERIAL":
            out = n
    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.location = (200, 0)
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    _setin(b, ["Roughness"], 0.86)
    _setin(b, ["Specular IOR Level", "Specular"], 0.28)
    _setin(b, ["Metallic"], 0.0)
    N = NT(m)

    tc = N.new("ShaderNodeTexCoord")
    obj = tc.outputs["Object"]
    sep = N.new("ShaderNodeSeparateXYZ")
    N.link(obj, sep.inputs["Vector"])
    px, py, pz = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]

    # ---- bedding coordinate: u = z + dip_x*x + dip_y*y -------------------
    u = N.add(N.add(pz, N.mul(px, dip[0])), N.mul(py, dip[1]))
    # warp the thickness slowly so beds are not a metronome
    warp = N.mr(N.noise(obj, 0.055, 2.0, 0.5), 0.30, 0.70, -1.25, 1.25)
    uw = N.add(u, warp)
    T = 1.42                                   # mean bed thickness
    band = N.mul(uw, 1.0 / T)
    fr = N.math("FRACT", band)
    fl = N.math("FLOOR", band)

    # seam: 1 exactly on a bedding plane, 0 inside a bed
    tri = N.math("MINIMUM", fr, N.sub(1.0, fr))
    seam = N.mr(tri, 0.0, 0.075, 1.0, 0.0)

    # per-bed tone and per-bed hardness (two independent white-noise hashes)
    # NOTE: a ColorRamp clamps its Fac to 0..1, so this hash has to be mapped
    # to the full 0..1 range -- mapping it into 0.62..1.30 put every bed on the
    # light stop and the face came out as one flat tone with no bedding at all
    ltone = N.white(N.mul(fl, 0.731))
    hard = N.white(N.add(N.mul(fl, 0.317), 3.17))
    # a soft bed is recessive: darker, greener, and it eats the bed below it
    soft = N.mr(hard, 0.42, 0.68, 1.0, 0.0)

    # ---- vertical joints -------------------------------------------------
    # the joint lattice is quantised in u, so a joint stops at a bedding plane
    jvec = N.new("ShaderNodeCombineXYZ")
    N.link(px, jvec.inputs["X"])
    N.link(py, jvec.inputs["Y"])
    N.link(N.mul(uw, 0.72), jvec.inputs["Z"])
    jdist = N.voronoi(jvec.outputs["Vector"], 0.30)
    jseam = N.mr(jdist, 0.0, 0.055, 1.0, 0.0)
    jmask = N.mr(N.noise(obj, 0.085, 2.0, 0.5), 0.34, 0.66, 0.25, 1.0)
    jseam = N.mul(jseam, jmask)

    # ---- water streaks: noise stretched along the bedding normal ---------
    svec = N.new("ShaderNodeCombineXYZ")
    N.link(N.mul(px, 1.7), svec.inputs["X"])
    N.link(N.mul(py, 1.7), svec.inputs["Y"])
    N.link(N.mul(uw, 0.085), svec.inputs["Z"])
    drip = N.mr(N.noise(svec.outputs["Vector"], 2.6, 3.0, 0.52), 0.46, 0.78, 0.0, 1.0)

    # ---- geometric normal: 0 = wall, 1 = bed top -------------------------
    geo = N.new("ShaderNodeNewGeometry")
    nsep = N.new("ShaderNodeSeparateXYZ")
    N.link(geo.outputs["Normal"], nsep.inputs["Vector"])
    nz = N.math("ABSOLUTE", nsep.outputs["Z"])
    # NOTE: threshold is deliberately tight.  At 0.55..0.92 a 33 degree talus
    # scored 0.78 and therefore took 78% of the *bed-top* recipe -- dust colour,
    # no bedding -- which is exactly why the whole crag rendered as a smooth
    # beige dune.  Only surfaces within ~10 degrees of level are bed tops.
    flat = N.mr(nz, 0.88, 0.985, 0.0, 1.0)

    # ---- wall recipe -----------------------------------------------------
    # A bed has to differ from its neighbour in *albedo*, not only in relief:
    # on the shaded side of the crag there is no sun to cast the ledger shadows
    # that would otherwise do the work, so the tone is what reads at 100 m.
    c_base = N.ramp(ltone, [(0.0, pal["dark"]), (0.34, pal["base"]),
                            (0.72, pal["light"]), (1.0, pal["dust"])])
    c_wall = N.mixc(c_base, pal["warm"], N.mul(soft, 0.55))
    c_wall = N.mixc(c_wall, pal["dark"], N.mul(seam, 0.55))
    c_wall = N.mixc(c_wall, pal["dark"], N.mul(jseam, 0.42))
    c_wall = N.mixc(c_wall, pal["wet"], N.mul(drip, N.mul(wet, 0.45)))
    # damp + algae in the crevices low down, where the talus keeps it wet
    damp = N.mr(N.mul(pz, -1.0), -7.0, -0.5, 0.0, 1.0)
    c_wall = N.mixc(c_wall, pal["moss"], N.mul(damp, N.add(0.10, N.mul(seam, 0.35))))

    # ---- bed-top recipe --------------------------------------------------
    # Not "pale plate with a crack grid" -- that reads as a concrete slab, which
    # is the very defect this file exists to remove.  A bed top is: blotchy bare
    # rock, sun-bleached in patches, with grit, joints opening into it, and the
    # odds and ends of turf caught in the hollows.
    tvec = N.new("ShaderNodeCombineXYZ")
    N.link(N.mul(px, 1.0), tvec.inputs["X"])
    N.link(N.mul(py, 1.0), tvec.inputs["Y"])
    N.link(N.mul(uw, 0.22), tvec.inputs["Z"])
    crack = N.mr(N.voronoi(tvec.outputs["Vector"], 0.42), 0.0, 0.06, 1.0, 0.0)
    grain = N.noise(obj, 0.42, 5.0, 0.62)
    # large blotches so a 40 m shelf is not one tone
    blotch = N.mr(N.noise(obj, 0.055, 3.0, 0.55), 0.32, 0.72, 0.0, 1.0)
    c_top = N.ramp(grain, [(0.30, pal["dark"]), (0.62, pal["base"]),
                           (0.95, pal["dust"])])
    c_top = N.mixc(c_top, pal["warm"], N.mul(blotch, 0.34))
    c_top = N.mixc(c_top, pal["dark"], N.mul(crack, 0.26))
    c_top = N.mixc(c_top, pal["dust"], N.mul(N.mr(grain, 0.55, 0.92, 0.0, 1.0), 0.22))
    # grit caught on the shelf
    grit = N.mr(N.voronoi(obj, 11.0), 0.0, 0.35, 0.0, 1.0)
    c_top = N.mixc(c_top, pal["light"], N.mul(grit, 0.10))
    # lichen: big patches, only on bed tops and only where the noise agrees
    lm = N.mr(N.noise(obj, 0.30, 3.0, 0.55), 0.44, 0.70, 0.0, 1.0)
    lm2 = N.mr(N.noise(obj, 1.7, 2.0, 0.55), 0.35, 0.72, 0.0, 1.0)
    lich = N.mul(N.mul(lm, lm2), N.mul(flat, lichen))
    c_top = N.mixc(c_top, pal["lichen"], N.mul(lich, 0.55))
    c_top = N.mixc(c_top, pal["moss2"], N.mul(N.mul(lich, lich), 0.45))

    col = N.mixc(c_wall, c_top, flat)

    # ---- bump: joints and bedding recessed, bed tops rawer ---------------
    fine = N.noise(obj, 2.6, 6.0, 0.6)
    h = N.add(N.mul(seam, 0.55), N.mul(jseam, 0.45))
    h = N.add(h, N.mul(fine, N.add(0.26, N.mul(flat, 0.5))))
    h = N.sub(h, N.mul(crack, 0.30))
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.62
    bump.inputs["Distance"].default_value = 0.06
    N.link(h, bump.inputs["Height"])
    N.link(bump.outputs["Normal"], b.inputs["Normal"])

    rough = N.add(0.80, N.mul(seam, 0.10))
    rough = N.add(rough, N.mul(lich, 0.06))
    rough = N.sub(rough, N.mul(drip, 0.18))
    N.link(rough, b.inputs["Roughness"])
    N.link(col, b.inputs["Base Color"])
    return m


def scree_material(MAT, name="rock_scree", style="limestone", dip=None):
    """Talus: no bedding at all -- it is rubble, so it is all grain.

    Made from the same palette so the chute reads as the cliff coming apart
    rather than as a different rock.
    """
    old = bpy.data.materials.get(name)
    if old is not None:
        return old
    pal = _PALETTE.get(style) or _PALETTE["limestone"]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = nt.nodes[0] if nt.nodes[0].type == "OUTPUT_MATERIAL" else None
    if out is None:
        for n in nt.nodes:
            if n.type == "OUTPUT_MATERIAL":
                out = n
    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    _setin(b, ["Roughness"], 0.92)
    _setin(b, ["Specular IOR Level", "Specular"], 0.2)
    N = NT(m)
    tc = N.new("ShaderNodeTexCoord")
    obj = tc.outputs["Object"]
    sep = N.new("ShaderNodeSeparateXYZ")
    N.link(obj, sep.inputs["Vector"])
    # A talus is read as *stones*, and stones are read by tone, not by texture.
    # So the main term is a voronoi cell colour: one random tone per block, at a
    # scale of about a metre.  Two scales below it only break up the big cells.
    vc = N.new("ShaderNodeTexVoronoi")
    vc.voronoi_dimensions = "3D"
    vc.feature = "F1"
    vc.inputs["Scale"].default_value = 0.42
    N.link(obj, vc.inputs["Vector"])
    sc = N.new("ShaderNodeSeparateColor")
    N.link(vc.outputs["Color"], sc.inputs["Color"])
    tone = sc.outputs[0]
    # CONSTANT interpolation on purpose: a continuous ramp turns the cells into
    # camouflage blotches, five flat tones with dark seams between them turn the
    # very same cells into stones.
    col = N.ramp(tone, [(0.0, pal["dark"]), (0.34, pal["base"]),
                        (0.62, pal["warm"]), (0.82, pal["light"]),
                        (1.0, pal["dust"])], interp="CONSTANT")
    # the gaps between blocks: dark seams at the cell borders, same scale
    v1 = N.voronoi(obj, 0.42)
    gap = N.mr(v1, 0.0, 0.10, 1.0, 0.0)
    col = N.mixc(col, pal["wet"], N.mul(gap, 0.82))
    # a second, finer cell layer so the metre blocks are themselves broken up
    vc2 = N.new("ShaderNodeTexVoronoi")
    vc2.voronoi_dimensions = "3D"
    vc2.feature = "F1"
    vc2.inputs["Scale"].default_value = 1.45
    N.link(obj, vc2.inputs["Vector"])
    sc2 = N.new("ShaderNodeSeparateColor")
    N.link(vc2.outputs["Color"], sc2.inputs["Color"])
    fine = N.mr(sc2.outputs[0], 0.0, 1.0, -0.5, 0.5)
    col = N.mixc(col, pal["dust"], N.mul(N.add(fine, 0.55), 0.14))
    v2 = N.voronoi(obj, 1.45)
    gap2 = N.mr(v2, 0.0, 0.06, 1.0, 0.0)
    col = N.mixc(col, pal["dark"], N.mul(gap2, 0.34))
    # grass and moss creeping into the chute
    gm = N.mr(N.noise(obj, 0.55, 3.0, 0.55), 0.50, 0.74, 0.0, 1.0)
    col = N.mixc(col, pal["moss"], N.mul(gm, 0.34))
    h = N.add(N.mul(gap, -0.6), N.mul(gap2, -0.25))
    h = N.add(h, N.mul(tone, 0.5))
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.85
    bump.inputs["Distance"].default_value = 0.07
    N.link(N.add(h, N.mul(N.noise(obj, 5.0, 4.0, 0.6), 0.35)), bump.inputs["Height"])
    N.link(bump.outputs["Normal"], b.inputs["Normal"])
    N.link(col, b.inputs["Base Color"])
    return m


def turf_material(MAT, name="rock_turf", style="limestone"):
    """The plateau top: thin dry turf over rock, rock showing through."""
    old = bpy.data.materials.get(name)
    if old is not None:
        return old
    pal = _PALETTE.get(style) or _PALETTE["limestone"]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = None
    for n in nt.nodes:
        if n.type == "OUTPUT_MATERIAL":
            out = n
    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    _setin(b, ["Roughness"], 0.94)
    _setin(b, ["Specular IOR Level", "Specular"], 0.22)
    N = NT(m)
    tc = N.new("ShaderNodeTexCoord")
    obj = tc.outputs["Object"]
    # patch mask: where the turf is thin, rock shows
    patch = N.mr(N.noise(obj, 0.13, 4.0, 0.6), 0.40, 0.62, 0.0, 1.0)
    grain = N.noise(obj, 1.1, 4.0, 0.6)
    grass = N.ramp(grain, [(0.25, "#3d4a26"), (0.55, "#586030"), (0.85, "#6b6836")])
    rock = N.ramp(N.noise(obj, 0.9, 3.0, 0.6),
                  [(0.25, pal["dark"]), (0.6, pal["base"]), (0.9, pal["dust"])])
    col = N.mixc(rock, grass, patch)
    lich = N.mul(N.mr(N.noise(obj, 0.5, 3.0, 0.55), 0.5, 0.72, 0.0, 1.0), 0.5)
    col = N.mixc(col, pal["lichen"], lich)
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    bump.inputs["Distance"].default_value = 0.05
    N.link(N.add(N.mul(patch, 0.3), N.mul(N.noise(obj, 2.4, 4.0, 0.6), 0.5)),
           bump.inputs["Height"])
    N.link(bump.outputs["Normal"], b.inputs["Normal"])
    N.link(col, b.inputs["Base Color"])
    return m


def road_material(MAT, name="rock_road", style="limestone"):
    """Packed earth / gravel over rock, with wheel ruts and a worn crown."""
    old = bpy.data.materials.get(name)
    if old is not None:
        return old
    pal = _PALETTE.get(style) or _PALETTE["limestone"]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = None
    for n in nt.nodes:
        if n.type == "OUTPUT_MATERIAL":
            out = n
    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    _setin(b, ["Roughness"], 0.93)
    _setin(b, ["Specular IOR Level", "Specular"], 0.24)
    N = NT(m)
    tc = N.new("ShaderNodeTexCoord")
    obj = tc.outputs["Object"]
    grit = N.mr(N.noise(obj, 3.4, 5.0, 0.65), 0.28, 0.72, 0.0, 1.0)
    col = N.ramp(grit, [(0.0, "#6d6455"), (0.5, pal["road"]), (1.0, "#b3a68c")])
    # wheel ruts: stripes along the road direction are not available here, so
    # two dark bands are drawn by the caller's geometry instead; the shader adds
    # the worn crown and the mud in the low spots
    mud = N.mr(N.noise(obj, 0.72, 3.0, 0.6), 0.5, 0.72, 0.0, 1.0)
    col = N.mixc(col, "#5b5346", N.mul(mud, 0.45))
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.45
    bump.inputs["Distance"].default_value = 0.04
    N.link(N.add(N.mul(grit, 0.7), N.mul(N.noise(obj, 7.0, 3.0, 0.6), 0.3)),
           bump.inputs["Height"])
    N.link(bump.outputs["Normal"], b.inputs["Normal"])
    N.link(col, b.inputs["Base Color"])
    return m

# --------------------------------------------------------------------------- #
#  the crag
# --------------------------------------------------------------------------- #
class Crag(object):
    """One crag: the mass, its bedding, its road, its rubble, its plants.

    The mass is a *radius function of (theta, z)*.  Nothing here is a box and
    nothing is a cylinder: r(th, z) is single-valued, so the whole face is one
    stack of row strips, and that is why the bedding can be a hard geometric
    ledge instead of a texture.  Every row's radius is
        r_base(th, z)  + bed offset  + joint offset  + noise  - road cut
    and each of those four terms is what one thing looks like.
    """

    TAL_ROWS = 7

    def __init__(self, K, MAT, cx=0.0, cy=303.4, r=82.0, top_z=18.0,
                 seed=11, style="limestone", road=True, drop=17.6,
                 road_deg=None, gate_deg=-90.0, plants=True, nth=1080,
                 base_z=0.0):
        self.K = K
        self.MAT = MAT
        self.cx = float(cx)
        self.cy = float(cy)
        self.R = float(r)
        self.top = float(top_z)
        self.base_z = float(base_z)
        self.seed = int(seed)
        self.style = style
        self.rng = random.Random(seed * 7919 + 13)
        self.nz = _NZ(seed)
        self.nth = max(180, int(nth))

        self.rim0 = self.R * RIM_F
        self.zc = self.top * CLIFF_F
        self.want_road = bool(road)
        self.plants = bool(plants)
        self.road_deg = (float(road_deg[0]), float(road_deg[1])) if road_deg \
            else None
        if road_deg is None:
            road_deg = (gate_deg - 5.0, gate_deg - 5.0 + 320.0)
        self.gate_deg = float(gate_deg)
        self.u0, self.u1 = float(road_deg[0]), float(road_deg[1])
        self.drop = float(drop)

        pal = _PALETTE.get(style) or _PALETTE["limestone"]
        self.pal = pal
        self.m_rock = rock_material(MAT, "rock_strata_%s" % style, style)
        self.m_scree = scree_material(MAT, "rock_scree_%s" % style, style)
        self.m_turf = turf_material(MAT, "rock_turf_%s" % style, style)
        self.m_road = road_material(MAT, "rock_road_%s" % style, style)
        self.m_leaf = (MAT or {}).get("leaf") or self.m_turf
        self.m_leaf2 = (MAT or {}).get("leaf_dark") or self.m_leaf
        self.m_bark = ((MAT or {}).get("wood_dark") or (MAT or {}).get("wood")
                       or self.m_road)
        self.m_wall = ((MAT or {}).get("stone_warm") or (MAT or {}).get("stone")
                       or self.m_road)

        self._layers()
        self.objs = []
        self.stats = {}

    # -- bedding table -----------------------------------------------------
    def _layers(self):
        rng = random.Random(self.seed * 31 + 5)
        top = self.top - 0.55
        bot = self.base_z + 0.62
        span = top - bot
        n = 9
        th = [rng.uniform(0.62, 2.45) for _ in range(n)]
        for i in (2, 5):
            th[i] = rng.uniform(0.62, 0.95)      # thin beds make a cliff read
        s = span / sum(th)
        # scale to fill the face, then push the residual back inside 0.62-2.45:
        # the brief asks for 0.6-2.5 m beds and a 17 m face, and both must hold
        th = [clamp(t * s, 0.62, 2.45) for t in th]
        for _ in range(8):
            d = span - sum(th)
            if abs(d) < 1e-7:
                break
            room = [(2.45 - t) if d > 0.0 else (t - 0.62) for t in th]
            rs = sum(room)
            if rs <= 1e-9:
                break
            th = [t + d * (r / rs) for t, r in zip(th, room)]
        self.zbed = []
        z = bot
        for i in range(n):
            self.zbed.append(z)
            z += th[i]
        self.zbed.append(top)
        self.thick = th
        self.off = []
        self.width = []
        self.nb = []
        self.phase = []
        self.dark = []
        for i in range(n):
            hard = rng.random()
            # A hard bed stands proud of its neighbour; a soft bed is cut back to
            # a niche.  The step between the two is what makes a shadow line on
            # the face.  At 960x540 with the crag filling the frame the scale is
            # ~7 px/m, so a 0.4 m step is 3 px and reads as nothing: these beds
            # are cut back up to 1.5 m, which is the depth of the real undercut
            # on a limestone bench and gives a 10 px shadow band.
            o = -1.55 + 2.45 * hard
            if th[i] < 1.05 and hard < 0.45:
                o -= 0.45                          # a soft niche
            self.off.append(o)
            w = rng.uniform(2.0, 5.6)
            self.width.append(w)
            # how many joint blocks fit round the face at this bed: the block
            # width is real metres, so a bed at r = 63 m gets 70-200 of them
            self.nb.append(max(3, int(round(TAU * self.rim0 / w))))
            self.phase.append(rng.uniform(0.0, 0.37))
            self.dark.append(hard)
        self.off_rim = -0.12
        self.nbed = n

    def _bh(self, k, b):
        x = math.sin(b * 12.9898 + k * 78.233 + self.seed * 0.717) * 43758.5453
        return (x - math.floor(x)) * 0.62 - 0.32

    # -- analytic surface --------------------------------------------------
    def rim_r(self, th):
        """Plateau edge.  Lobes only *outwards*: the castle towers reach
        r = 57.05 and the plateau must never narrow past them, so the outline
        gets promontories instead of re-entrants.  A circle reads as a spoil
        heap; a lobed outline reads as a crag."""
        n = self.nz
        w = 1.0
        w += 0.026 * (0.5 + 0.5 * math.sin(3.0 * th + 1.1))
        w += 0.018 * (0.5 + 0.5 * math.sin(5.0 * th + 2.7))
        w += 0.011 * (0.5 + 0.5 * math.sin(7.0 * th - 0.4))
        w += 0.020 * (0.5 + 0.5 * n.at(180.0 * math.cos(th), 180.0 * math.sin(th), 41.0))
        return self.rim0 * w

    def spur(self, th, z):
        """Vertical rib-and-gully system, faded out towards the rim."""
        a = 0.0
        for k, amp, ph in SPUR:
            a += amp * math.sin(k * th + ph)
        # gullies are deepest on the cliff band, and the ribs lean back with the
        # face instead of standing straight up like a gear
        t = clamp((self.top - z) / max(self.top - self.base_z, 1.0), 0.0, 1.0)
        return a * (0.16 + 0.84 * smoothstep(0.0, 0.34, t))

    def z_talus_top(self, th):
        return (self.zc + 1.30 * math.sin(2.0 * th + 0.6)
                + 0.55 * math.sin(5.0 * th + 2.2))

    def deck_u(self, th):
        u = math.degrees(th)
        if u < self.u0:
            u += 360.0
        return u

    def road_act(self, u):
        if not self.want_road:
            return 0.0
        return (smoothstep(self.u0, self.u0 + 9.0, u)
                * smoothstep(self.u1, self.u1 - 7.0, u))

    def deck_z(self, th):
        """Height of the road deck at this bearing.

        The spiral only covers 320 degrees, and outside it the linear grade keeps
        extrapolating: at theta = 350 degrees it returned -6.6 m, four metres
        below the ground, and the deck row landed under the talus.  Because the
        row *order* is fixed, one row out of order turns the whole column into
        two enormous quads -- 35 m tall, in the road material -- and that was the
        smooth pale sheet that hid the east face in every render until now.
        """
        if not self.want_road:
            return self.z_talus_top(th) + 0.30
        u = self.deck_u(th)
        zd = self.top + 0.40 - self.drop * (u - self.u0) / (self.u1 - self.u0)
        return clamp(zd, self.z_talus_top(th) + 0.30, self.top + 0.44)

    def inset(self, th, z):
        """How far the face is cut back to make room for the road.

        The cut is a *bench*: it must stop a couple of metres above the deck and
        let the natural face resume, otherwise every column along the road's 320
        degrees has its whole wall pushed back by 4.7 m, and the result is a
        10 m tall helical sheet wrapped round the crag.  That sheet was the
        "smooth pale plane" that covered half of every east-side render.
        """
        if not self.want_road:
            return 0.0
        zd = self.deck_z(th)
        if z <= zd:
            return 0.0
        a = self.road_act(self.deck_u(th))
        if a <= 0.0:
            return 0.0
        up = z - zd
        head = smoothstep(0.0, 0.10, up) * (1.0 - smoothstep(2.10, 5.00, up))
        return ROAD_W * a * head

    def r_base(self, th, z):
        rim = self.rim_r(th)
        zt = self.z_talus_top(th)
        if z >= zt:
            span = max(self.top - zt, 0.6)
            u = clamp((self.top - z) / span, 0.0, 1.35)
            r = rim + BATTER * (u ** 1.15)
        else:
            r = rim + BATTER + (zt - z) * TAL_K
        r += max(APRON_Z - max(z - self.base_z, 0.0), 0.0) * APRON_K
        return r

    def joint(self, th, k, z):
        nb = self.nb[k]
        p = th / TAU * nb + self.phase[k]
        b = math.floor(p)
        f = p - b
        o = lerp(self._bh(k, b), self._bh(k, b + 1), smoothstep(0.95, 1.0, f))
        g = min(f, 1.0 - f) / 0.030
        o -= 0.34 * math.exp(-g * g)               # the dark seam
        return o

    def detail(self, x, y, z):
        """Radial relief, in metres.

        The 40 m and 17 m terms shape the body; the 9.5/3.6 m terms are the ones
        that a camera 100 m out can actually resolve, and the 7.5/4.2 m pair is
        what was missing: with only 9.5 m and longer the face between the ledges
        stayed dead flat, because a 1 m bump at 7 px/m is two pixels.
        """
        n = self.nz
        return (0.72 * n.at(x, y, 41.0) + 0.34 * n.at(x + 13.0, y, 17.0)
                + 0.62 * n.at(x, y, 9.5) + 0.30 * n.at(x, y, 3.6)
                + 1.10 * n.at(x, y, 7.5) + 0.58 * n.at(x + 5.0, y, 4.2)
                + 0.09 * n.at(x, y, 1.55))

    def z_bound(self, k, th):
        """Absolute z of bedding boundary k, k = 0 at the top."""
        zb = self.zbed[self.nbed - k]
        x = self.rim0 * math.cos(th)
        y = self.rim0 * math.sin(th)
        z = zb + DIP[0] * x + DIP[1] * y
        z += 0.16 * math.sin(2.0 * th + 1.3) + 0.07 * math.sin(6.0 * th + 0.4 * k)
        return z

    def zmid(self, k, th):
        z0 = self.z_bound(k, th)
        z1 = self.z_bound(k + 1, th) if k + 1 <= self.nbed else self.zbed[0] + 0.4
        return 0.5 * (z0 + z1)

    def r_tal(self, th, z):
        """The debris slope.  It is NOT the beds continuing downhill: below the
        cliff the rock is buried under its own rubble, so the surface gets its
        own profile and its own lumps, and the bedding stops dead at the foot.

        Profile: hugging the cliff at ~55 deg and spreading to ~22 deg in the
        fan, so the chord is 33 deg -- a straight 33 deg cone looks like a sand
        dune from every angle, a fan does not."""
        zt = self.z_talus_top(th)
        base = self.rim_r(th) + BATTER
        h = max(zt - self.base_z, 0.8)
        t = clamp((zt - z) / h, 0.0, 1.25)
        run = h * TAL_K * t - 0.30 * h * math.sin(math.pi * min(t, 1.0))
        r = base + run
        x = base * math.cos(th) + 17.0
        y = base * math.sin(th) - 9.0
        r += 0.62 * self.nz.at(x, y, 2.6) + 0.34 * self.nz.at(x, y, 5.4)
        # tongues: rubble runs down in lobes, so the cone is not a smooth skirt
        # but a set of ridges and gullies.  sin(11*th) is a 43 m wave at this
        # radius, far too long to read as a lump, so the body wave stays weak and
        # the 3-7 m terrain noise does the work.
        r += (0.55 * math.sin(th * 11.0 + 1.3)
              + 0.22 * math.sin(th * 29.0 - 0.6)) * (t ** 0.55)
        r += (1.15 * self.nz.at(x + 41.0, y, 6.5)
              + 0.60 * self.nz.at(x, y + 27.0, 2.9)) * (0.35 + 0.65 * t)
        r += max(APRON_Z - max(z - self.base_z, 0.0), 0.0) * APRON_K
        return r

    def r_surf(self, th, z):
        """Radius of the natural surface at any height: beds above the cliff
        foot, debris slope below it."""
        if z < self.z_talus_top(th):
            return self.r_tal(th, z)
        return self.r_base(th, z)

    def r_at(self, th, z, off, layer, kind="bed"):
        if kind == "tal":
            r = self.r_tal(th, z) + off + self.spur(th, z)
            r += self.detail(self.rim0 * math.cos(th), self.rim0 * math.sin(th), z)
            return max(r - self.inset(th, z), 56.0)
        rb = self.r_base(th, z)
        x = rb * math.cos(th)
        y = rb * math.sin(th)
        r = rb + off + self.spur(th, z)
        if layer is not None:
            r += self.joint(th, layer, z)
        r += self.detail(x, y, z)
        r -= self.inset(th, z)
        return max(r, 56.0)

    def z_rim(self, th):
        """The plateau edge: a 1-2 m natural ridge, faded out over the gate.

        A flat rim lets the plateau read as a table; a raised, wobbling one is
        what makes the keep look like it grew out of a crag.  The saddle at the
        gate is kept low so the ramp still lands on the flagstones.
        """
        g = abs(((math.degrees(th) + 180.0) % 360.0) - 270.0)
        saddle = smoothstep(7.0, 28.0, g)
        c, s = math.cos(th), math.sin(th)
        amp = 0.45 + 1.10 * abs(self.nz.at(90.0 * c, 90.0 * s, 26.0))
        # a few standing knobs on the ridge, so the skyline is not one smooth arc
        knob = 0.95 * max(0.0, self.nz.at(150.0 * c + 31.0, 150.0 * s, 63.0) - 0.34)
        return self.top + 0.60 + (amp + knob) * saddle

    def z_yard(self, th):
        """The plateau floor under the castle: uneven, and *above* its plinth.

        hd_castle() is placed at top_z + 0.45 and its own build() shifts the
        whole thing so that zlo == 0, i.e. the bottom of the plinth is a flat
        plane at exactly top_z + 0.45.  A yard that averages top_z is therefore
        a quarter of a metre *below* the castle, and the walls stand on a gap.
        So the yard sits 0.17 m above that plane (0.02 m at the very lowest
        noise sample, 0.32 m at the highest): the plinth is buried, and the
        courtyard floor, which is 0.94 m higher again, still hides the rock.
        """
        base = self.top + 0.45
        c, s = math.cos(th), math.sin(th)
        n1 = self.nz.at(64.0 * c, 64.0 * s, 23.0)
        n2 = self.nz.at(64.0 * c + 7.0, 64.0 * s, 6.4)
        return max(base + 0.02, base + 0.17 + 0.13 * n1 + 0.05 * n2)

    def z_cap(self, th, ring):
        if ring == 0:
            return self.z_rim(th)
        if ring == 1:
            return self.z_rim(th) - 0.30          # outer face of the crest
        return self.z_yard(th) + 0.05 * ring

    # -- rows --------------------------------------------------------------
    def rows_at(self, th):
        """Fixed-length row list, top to bottom: (kind, z, off, layer).

        Rows that the road has eaten are *collapsed* onto the row that is still
        visible, so they produce zero-area quads and vanish: beds truncate
        against the cut, which is what beds do.
        """
        nl = self.nbed
        zd = self.deck_z(th)
        act = self.road_act(self.deck_u(th))
        has = act > 0.004
        hi = zd + 0.34 if has else -1e9
        # with no road here the second group still has to collapse somewhere sane:
        # the old sentinel was +1e9, so every column outside the spiral carried
        # vertices a billion metres up and the quads built from them swept the
        # whole screen.
        lo = zd - 0.30 if has else self.z_talus_top(th) + 0.24
        # the topmost bed boundary that has already dropped below the road:
        # everything above it survives, everything below is eaten by the cut
        kA = nl
        for k in range(nl):
            if self.z_bound(k, th) < hi:
                kA = k
                break
        # the lowest bed boundary that is still below the road
        kB = nl
        for k in range(nl):
            if self.z_bound(k, th) < lo:
                kB = k
                break
        # the cliff foot: beds stop here and the debris slope takes over
        zt = self.z_talus_top(th)
        kC = nl
        for k in range(nl):
            if self.z_bound(k, th) < zt + 0.28:
                kC = k
                break
        out = [("rim", self.z_rim(th), self.off_rim, None)]
        for k in range(nl):
            zb = self.z_bound(k, th)
            if k < kA:
                zz = zb + 2e-5 * (nl - k)
                o0 = self.off[k - 1] if k else self.off_rim
                l0 = k - 1 if k else None
                out.append(("bed", zz, o0, l0))
                out.append(("bed", zz, self.off[k], k))
                out.append(("mid", max(self.zmid(k, th), zz), self.off[k] + 0.10 * self.dark[k], k))
            else:
                zz = hi + 2e-5 * (nl - k)
                o = self.off[kA] if kA < nl else self.off_rim
                out.append(("bed", zz, o, kA if kA < nl else None))
                out.append(("bed", zz, o, kA if kA < nl else None))
                out.append(("mid", zz, o, kA if kA < nl else None))
        # where the road is not carved, these two rows sit on top of each other
        # and the quad between them degenerates and disappears
        out.append(("deck_in", zd + (0.10 if has else 0.0), 0.0, None))
        out.append(("deck_out", zd, 0.0, None))
        for k in range(nl):
            zb = self.z_bound(k, th)
            if k >= kB and k < kC:
                zz = zb - 2e-5 * k
                o0 = self.off[k - 1] if k else self.off_rim
                l0 = k - 1 if k else None
                out.append(("bed", zz, o0, l0))
                out.append(("bed", zz, self.off[k], k))
                out.append(("mid", min(self.zmid(k, th), zz), self.off[k], k))
            else:
                zz = (lo if k < kB else zt + 0.20) - 2e-5 * (k + 1)
                o = self.off[kB] if kB < nl else self.off_rim
                out.append(("bed", zz, o, kB if kB < nl else None))
                out.append(("bed", zz, o, kB if kB < nl else None))
                out.append(("mid", zz, o, kB if kB < nl else None))
        # debris slope: its own rows, its own law, no bedding in it at all
        ztop = zt
        zbot = self.base_z + 0.55
        for i in range(self.TAL_ROWS):
            out.append(("tal", ztop + (zbot - ztop) * i / (self.TAL_ROWS - 1.0),
                        -0.10, None))
        for tz in (self.base_z + 0.34, self.base_z + 0.16,
                   self.base_z + 0.02, self.base_z - 1.8):
            out.append(("tal", tz, -0.10, None))
        return out

    def build_face(self):
        nth = self.nth
        mb = MB()
        mr = mb.slot(self.m_rock)
        ms = mb.slot(self.m_scree)
        md = mb.slot(self.m_road)
        ths = [TAU * i / nth for i in range(nth)]
        P = []
        MI = []
        nrow = None
        for i, th in enumerate(ths):
            rows = self.rows_at(th)
            if nrow is None:
                nrow = len(rows)
            col = []
            matc = []
            for (kind, z, off, lay) in rows:
                r = self.r_at(th, z, off, lay, kind)
                col.append((self.cx + r * math.cos(th),
                            self.cy + r * math.sin(th), z))
                if kind == "deck_in" or kind == "deck_out":
                    matc.append(md)
                elif kind == "tal":
                    matc.append(ms)
                else:
                    matc.append(mr)
            P.append(col)
            MI.append(matc)
        for r in range(nrow - 1):
            for i in range(nth):
                j = (i + 1) % nth
                a = P[i][r]
                b = P[j][r]
                c = P[j][r + 1]
                d = P[i][r + 1]
                if (abs(a[2] - b[2]) + abs(d[2] - c[2]) < 4e-4
                        and abs(a[0] - d[0]) + abs(a[1] - d[1]) < 4e-4):
                    continue
                if (abs(a[0] - b[0]) + abs(a[1] - b[1]) < 1e-5
                        and abs(b[0] - c[0]) + abs(b[1] - c[1]) < 1e-5):
                    continue
                # last line of defence: a row out of order produces a quad that
                # spans tens of metres of z across one 0.33 degree column step,
                # and a single such quad is enough to paint over half the frame.
                # Legitimate columns never differ by more than ~0.2 m in z.
                if (abs(a[2] - b[2]) > 3.0 or abs(d[2] - c[2]) > 3.0):
                    continue
                o = len(mb.v)
                mb.v.extend([a, d, c, b])
                mb.f.append((o, o + 1, o + 2, o + 3))
                mb.mi.append(MI[i][r])
        ob = mb.push(self.K, "rock_face")
        self.stats["face_rows"] = nrow
        return ob

    def build_cap(self):
        nth = self.nth
        mb = MB()
        mt = mb.slot(self.m_turf)
        mr = mb.slot(self.m_rock)
        rings = (0.0, 0.962, 0.885, 0.76, 0.58, 0.36, 0.16)
        ths = [TAU * i / nth for i in range(nth)]
        cols = []
        for ri, f in enumerate(rings):
            col = []
            for th in ths:
                if f == 0.0:
                    rr = self.rim_r(th)
                    z = self.z_rim(th)
                else:
                    rr = self.rim_r(th) * f
                    z = self.z_cap(th, ri)
                col.append((self.cx + rr * math.cos(th), self.cy + rr * math.sin(th), z))
            cols.append(col)
        cols.append([(self.cx, self.cy, self.top + 0.12)] * nth)
        band = (mt, mr, mt, mt, mt, mt, mt, mt)
        for ri in range(len(cols) - 1):
            mat = band[ri] if ri < len(band) else mt
            for i in range(nth):
                j = (i + 1) % nth
                a = cols[ri][i]
                b = cols[ri][j]
                c = cols[ri + 1][j]
                d = cols[ri + 1][i]
                o = len(mb.v)
                mb.v.extend([a, b, c, d])
                if ri == len(cols) - 2:
                    mb.f.append((o, o + 1, o + 2))
                else:
                    mb.f.append((o, o + 1, o + 2, o + 3))
                mb.mi.append(mat)
        ob = mb.push(self.K, "rock_cap")
        return ob

    # -- rubble ------------------------------------------------------------
    def build_rubble(self):
        """Talus blocks.  A 33 deg slope with 800 blocks on it still reads as a
        dune if the blocks are one size, so: power-law sizes (0.25-3.0 m, most of
        them small), coarse blocks under the cliff where the fall lands, and the
        whole lot half-buried so they look like they arrived, not like they were
        placed."""
        mb_a = MB()
        # rubble, not strata: the scree shader gives every block its own tone,
        # which is how a fan of stones reads at all
        mr = mb_a.slot(self.m_scree)
        rng = random.Random(self.seed * 97 + 3)
        ztl = self.z_talus_top(0.0)
        n = int(self.nth * 2.6)
        made = 0
        for i in range(n):
            th = rng.uniform(0.0, TAU)
            zt = self.z_talus_top(th)
            # coarse under the cliff, finer down the fan
            q = rng.random() ** 0.78
            z = self.base_z + 0.35 + (zt - 0.55 - self.base_z) * q
            u = rng.random()
            # power law, and the big ones outrun the small ones all the way to
            # the foot of the fan -- that is what a talus does
            size = 0.72 * (u ** -0.60) * (1.0 + 0.55 * (1.0 - q))
            if size > 3.6:
                size = 3.6 - rng.random() * 0.5
            if i < 46:                              # the big blocks at the foot
                z = zt - 0.4 - rng.random() * 2.6
                size = rng.uniform(2.2, 4.2)
            act = self.road_act(self.deck_u(th))
            if act > 0.10 and abs(z - self.deck_z(th)) < 2.8:
                continue
            # half sunk into the chute, not buried in it: a block whose centre
            # sits 0.3 m inside the surface is a pebble, and 2000 pebbles still
            # read as a dune.  Sample the *built* surface radius -- r_tal alone
            # omits spur() and detail(), which together push the real face out
            # by up to 3 m, and every block placed against r_tal disappeared
            # inside the rock.
            rs = self.r_at(th, z, 0.0, None, kind="tal")
            r = rs + rng.uniform(-0.10, 0.55) - 0.10 * size
            sub = 1 if size > 1.3 else 0
            sq = (rng.uniform(0.82, 1.20), rng.uniform(0.68, 1.02),
                  rng.uniform(0.55, 0.86))
            ico_emit(mb_a, (self.cx + r * math.cos(th), self.cy + r * math.sin(th),
                            z + size * 0.22), size * 0.55, rng, mr, sub, sq,
                     jitter=0.34, rot=rng.uniform(0.0, TAU))
            made += 1
        ob = mb_a.push(self.K, "rock_talus")
        self.stats["boulders"] = made
        return ob

    def build_cap_dressing(self):
        """Stones on the plateau, and a broken line of blocks along the crest.

        The plateau is most of what a camera 52 m up actually sees, so it cannot
        be a plate: slabs and outcrops are what make its surface, and crest
        blocks are what stops the skyline from being a drawn circle.
        """
        mb = MB()
        mr = mb.slot(self.m_scree)
        rng = random.Random(self.seed * 131 + 17)
        made = 0
        # 1) slabs and low outcrops on the walkable ring inside the crest
        for i in range(int(self.nth * 0.45)):
            th = rng.uniform(0.0, TAU)
            rad = self.rim_r(th) - rng.uniform(0.7, 7.6)
            size = 0.35 * (rng.random() ** -0.55)
            if size > 2.0:
                size = rng.uniform(1.1, 2.0)
            z = self.z_yard(th) + rng.uniform(-0.12, 0.10)
            ico_emit(mb, (self.cx + rad * math.cos(th),
                          self.cy + rad * math.sin(th), z + size * 0.09),
                     size * 0.56, rng, mr, 1 if size > 1.25 else 0,
                     (rng.uniform(1.05, 1.65), rng.uniform(0.95, 1.5),
                      rng.uniform(0.30, 0.55)),
                     jitter=0.30, rot=rng.uniform(0.0, TAU))
            made += 1
        # 2) the crest itself: blocks half sunk in the rim so the skyline steps
        for i in range(int(self.nth * 0.62)):
            th = rng.uniform(0.0, TAU)
            rad = self.rim_r(th) - rng.uniform(-0.4, 1.6)
            size = min(1.6, 0.42 * (rng.random() ** -0.40))
            z = self.z_rim(th) - rng.uniform(0.15, 0.75)
            ico_emit(mb, (self.cx + rad * math.cos(th),
                          self.cy + rad * math.sin(th), z + size * 0.30),
                     size * 0.55, rng, mr, 1 if size > 1.15 else 0,
                     (rng.uniform(0.85, 1.35), rng.uniform(0.8, 1.25),
                      rng.uniform(0.5, 0.9)),
                     jitter=0.32, rot=rng.uniform(0.0, TAU))
            made += 1
        ob = mb.push(self.K, "rock_cap_stones")
        self.stats["cap_stones"] = made
        return ob

    def build_wall_stones(self):
        """Blocks that have popped out of the face and stuck in the bedding."""
        mb = MB()
        mr = mb.slot(self.m_rock)
        rng = random.Random(self.seed * 61 + 7)
        n = int(self.nth * 0.55)
        for i in range(n):
            th = rng.uniform(0.0, TAU)
            z = rng.uniform(self.base_z + 1.6, self.z_talus_top(th) + 6.0)
            act = self.road_act(self.deck_u(th))
            if act > 0.12 and abs(z - self.deck_z(th)) < 2.2:
                continue
            size = min(1.3, 0.22 * (rng.random() ** -0.42))
            r = (self.r_at(th, z, 0.0, None, kind="bed")
                 + rng.uniform(-0.05, 0.40) - 0.30 * size)
            ico_emit(mb, (self.cx + r * math.cos(th), self.cy + r * math.sin(th), z),
                     size * 0.52, rng, mr, 0, (rng.uniform(0.7, 1.2),
                     rng.uniform(0.6, 1.0), rng.uniform(0.55, 1.0)),
                     rot=rng.uniform(0.0, TAU))
        return mb.push(self.K, "rock_face_stones")

    # -- plants ------------------------------------------------------------
    def _lump(self, mb, x, y, z, r, rng, mat, squash=(1, 1, 0.8), sub=0):
        ico_emit(mb, (x, y, z), r, rng, mat, sub, squash, jitter=0.30)

    def _bush(self, mb, x, y, z, size, rng, ma, mb_, flat=0.75):
        for i in range(rng.randint(4, 7)):
            a = rng.uniform(0.0, TAU)
            d = rng.uniform(0.1, 0.75) * size
            self._lump(mb, x + d * math.cos(a), y + d * math.sin(a),
                       z + rng.uniform(0.12, 0.70) * size * flat,
                       size * rng.uniform(0.32, 0.55), rng,
                       ma if rng.random() < 0.65 else mb_, (1, 1, flat))

    def _tuft(self, mb, x, y, z, size, rng, mat, nblade=5):
        for i in range(nblade):
            a = rng.uniform(0.0, TAU)
            h = size * rng.uniform(0.6, 1.25)
            w = size * rng.uniform(0.10, 0.22)
            lean = rng.uniform(0.25, 0.75) * h
            ca, sa = math.cos(a), math.sin(a)
            ox, oy = w * ca, w * sa
            px = x + rng.uniform(-0.5, 0.5) * size
            py = y + rng.uniform(-0.5, 0.5) * size
            a2 = a + rng.uniform(-0.7, 0.7)
            tip = (px + lean * math.cos(a2), py + lean * math.sin(a2), z + h)
            mid = (px + 0.40 * (tip[0] - px), py + 0.40 * (tip[1] - py), z + 0.52 * h)
            o = len(mb.v)
            mb.v.extend([(px - ox, py - oy, z), (px + ox, py + oy, z),
                         (mid[0] + ox * 0.55, mid[1] + oy * 0.55, mid[2]),
                         (mid[0] - ox * 0.55, mid[1] - oy * 0.55, mid[2]), tip])
            mb.f.append((o, o + 1, o + 2, o + 3))
            mb.mi.append(mat)
            mb.f.append((o + 3, o + 2, o + 4))
            mb.mi.append(mat)

    def _tube(self, mb, pts, radii, sides, mat, cap=True):
        n = len(pts)
        base = len(mb.v)
        for i, (p, r) in enumerate(zip(pts, radii)):
            if i == 0:
                d = (pts[1][0] - p[0], pts[1][1] - p[1], pts[1][2] - p[2])
            elif i == n - 1:
                d = (p[0] - pts[-2][0], p[1] - pts[-2][1], p[2] - pts[-2][2])
            else:
                d = (pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1],
                     pts[i + 1][2] - pts[i - 1][2])
            ln = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1.0
            dx, dy, dz = d[0] / ln, d[1] / ln, d[2] / ln
            ux, uy, uz = 0.0, 0.0, 1.0
            if abs(dz) > 0.95:
                ux, uy, uz = 1.0, 0.0, 0.0
            ax = dy * uz - dz * uy
            ay = dz * ux - dx * uz
            az = dx * uy - dy * ux
            al = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
            ax, ay, az = ax / al, ay / al, az / al
            bx = ay * dz - az * dy
            by = az * dx - ax * dz
            bz = ax * dy - ay * dx
            for s in range(sides):
                ang = TAU * s / sides
                ca, sa = math.cos(ang), math.sin(ang)
                mb.v.append((p[0] + r * (ca * ax + sa * bx),
                             p[1] + r * (ca * ay + sa * by),
                             p[2] + r * (ca * az + sa * bz)))
        for i in range(n - 1):
            for s in range(sides):
                s2 = (s + 1) % sides
                mb.f.append((base + i * sides + s, base + i * sides + s2,
                             base + (i + 1) * sides + s2, base + (i + 1) * sides + s))
                mb.mi.append(mat)
        if cap:
            mb.f.append(tuple(base + s for s in range(sides - 1, -1, -1)))
            mb.mi.append(mat)

    def _tree(self, mb, x, y, z, size, rng, ma, mb_, mbark):
        lg = math.sqrt(max(size, 0.5)) * 1.15
        a = rng.uniform(0.0, TAU)
        pts = [(x, y, z)]
        rad = [0.19 * lg]
        h = 0.0
        for i in range(4):
            h += size * rng.uniform(0.15, 0.28)
            a += rng.uniform(-0.6, 0.6)
            pts.append((x + math.cos(a) * h * rng.uniform(0.06, 0.30),
                        y + math.sin(a) * h * rng.uniform(0.06, 0.30), z + h))
            rad.append(0.19 * lg * (1.0 - 0.19 * (i + 1)))
        self._tube(mb, pts, rad, 7, mbark, cap=True)
        tops = []
        for i in range(5):
            pi = rng.randint(1, 3)
            p = pts[pi]
            a2 = rng.uniform(0.0, TAU)
            L = size * rng.uniform(0.22, 0.45)
            q = (p[0] + math.cos(a2) * L * 0.8, p[1] + math.sin(a2) * L * 0.8,
                 p[2] + L * rng.uniform(0.45, 1.0))
            self._tube(mb, [p, q], [rad[pi] * 0.62, rad[pi] * 0.28], 5, mbark)
            tops.append((q, L))
        for (q, L) in tops:
            for j in range(rng.randint(1, 3)):
                self._lump(mb, q[0] + rng.uniform(-0.35, 0.35) * L,
                           q[1] + rng.uniform(-0.35, 0.35) * L,
                           q[2] + rng.uniform(-0.10, 0.42) * L,
                           L * rng.uniform(0.55, 1.0), rng,
                           ma if rng.random() < 0.6 else mb_, (1, 1, 0.72), 1)

    def build_plants(self):
        rng = random.Random(self.seed * 13 + 71)
        mb = MB(True)
        ma = mb.slot(self.m_leaf)
        mb_ = mb.slot(self.m_leaf2)
        mst = mb.slot(self.m_bark)
        # shrubs wedged in the joints / on the wide ledges
        for i in range(150):
            th = rng.uniform(0.0, TAU)
            k = rng.randint(0, self.nbed - 1)
            zb = self.z_bound(k, th)
            if zb < self.base_z + 1.4 or zb > self.top - 0.45:
                continue
            act = self.road_act(self.deck_u(th))
            if act > 0.15 and abs(zb - self.deck_z(th)) < 1.8:
                continue
            r = self.r_base(th, zb) + self.off[k] + 0.16
            self._bush(mb, self.cx + r * math.cos(th), self.cy + r * math.sin(th),
                       zb + 0.02, rng.uniform(0.5, 1.3), rng, ma, mb_)
        # grass: on bed tops, and loose on the debris fan
        for i in range(330):
            th = rng.uniform(0.0, TAU)
            if i % 5 == 0:
                r = self.r_surf(th, self.base_z + 0.1) + rng.uniform(-2.6, 3.2)
                self._tuft(mb, self.cx + r * math.cos(th), self.cy + r * math.sin(th),
                           self.base_z + 0.01, rng.uniform(0.25, 0.55), rng, ma)
                continue
            k = rng.randint(0, self.nbed - 1)
            zb = self.z_bound(k, th)
            if zb < self.base_z + 0.9:
                continue
            r = self.r_base(th, zb) + self.off[k] + 0.06
            self._tuft(mb, self.cx + r * math.cos(th), self.cy + r * math.sin(th),
                       zb + 0.01, rng.uniform(0.20, 0.45), rng, ma, 4)
        # vines off the rim
        for i in range(36):
            th = rng.uniform(0.0, TAU)
            if self.nz.at(80.0 * math.cos(th), 80.0 * math.sin(th), 15.0) < -0.04:
                continue
            z0 = self.z_rim(th) - 0.18
            r0 = self.rim_r(th) - 0.06
            L = rng.uniform(3.5, 10.5)
            n = 6
            pts = []
            rads = []
            for j in range(n):
                t = j / float(n - 1)
                rr = r0 - 1.7 * t * t
                pts.append((self.cx + rr * math.cos(th + 0.03 * t),
                            self.cy + rr * math.sin(th + 0.03 * t),
                            z0 - L * t + 0.10 * math.sin(t * 6.0 + i)))
                rads.append(0.30 * (1.0 - 0.75 * t))
            self._tube(mb, pts, rads, 4, ma if i % 2 else mb_, cap=False)
        # crooked trees at the foot
        for i in range(rng.randint(6, 8)):
            th = rng.uniform(0.0, TAU)
            if self.road_act(self.deck_u(th)) > 0.25 and self.deck_z(th) < 3.5:
                continue
            r = self.r_surf(th, self.base_z + 2.4) + rng.uniform(0.5, 4.5)
            self._tree(mb, self.cx + r * math.cos(th), self.cy + r * math.sin(th),
                       self.base_z, rng.uniform(2.6, 4.4), rng, ma, mb_, mst)
        return mb.push(self.K, "rock_plants")

    # -- the road ----------------------------------------------------------
    def build_road(self):
        if not self.want_road:
            return []
        mb = MB()
        mw = mb.slot(self.m_wall)
        n = 320
        cols = []
        for i in range(n + 1):
            u = self.u0 + (self.u1 - self.u0) * i / float(n)
            th = math.radians(u)
            act = self.road_act(u)
            zd = self.deck_z(th)
            if act < 0.05:
                cols.append(None)
                continue
            r0 = self.r_surf(th, zd)
            hgt = 0.82 * smoothstep(0.05, 0.30, act)
            rin = r0 - 0.60
            rout = r0 - 0.08
            cols.append([(self.cx + rin * math.cos(th), self.cy + rin * math.sin(th), zd - 0.40),
                         (self.cx + rin * math.cos(th), self.cy + rin * math.sin(th), zd + hgt),
                         (self.cx + rout * math.cos(th), self.cy + rout * math.sin(th), zd + hgt),
                         (self.cx + rout * math.cos(th), self.cy + rout * math.sin(th), zd - 0.55)])
        for i in range(n):
            a = cols[i]
            b = cols[i + 1]
            if a is None or b is None:
                continue
            for s in range(4):
                s2 = (s + 1) % 4
                o = len(mb.v)
                mb.v.extend([a[s], a[s2], b[s2], b[s]])
                mb.f.append((o, o + 1, o + 2, o + 3))
                mb.mi.append(mw)
        ob = mb.push(self.K, "rock_parapet")
        out = [ob] if ob else []
        st = self._gate_stair()
        out.extend(x for x in st if x)
        return out

    def _box(self, mb, x0, x1, y0, y1, z0, z1, mat):
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7)]
        o = len(mb.v)
        mb.v.extend(v)
        for fc in f:
            mb.f.append(tuple(o + i for i in fc))
            mb.mi.append(mat)

    def _gate_stair(self):
        """Grand stair from the causeway head down onto the plateau.

        capital_hd_glue's wedge_ramp reaches (cx, cy - 47.6*CS) with its deck
        2.55 m above the castle floor, and the castle sits at top_z + 0.45, so
        its head is at z ~ 21.0.  The stair meets it there; without it the ramp
        ends in mid-air, which is what it does today.
        """
        mb = MB()
        mw = mb.slot(self.m_wall)
        gx = self.cx
        y_head = self.cy - 47.6 * 1.15
        z_head = self.top + 3.00
        z_bot = self.z_yard(math.radians(self.gate_deg)) + 0.02
        steps = 8
        hw = 3.6
        dz = (z_head - z_bot) / steps
        dy = 4.4 / steps
        y = y_head
        for i in range(steps + 1):
            zt = z_head - dz * i
            y0 = y - (1.6 if i == 0 else dy)
            self._box(mb, gx - hw, gx + hw, y0, y, self.top - 0.40, zt, mw)
            y = y0
        for sx in (-1.0, 1.0):
            xa = gx + sx * hw
            xb = gx + sx * (hw + 0.55)
            lo, hi = min(xa, xb), max(xa, xb)
            self._box(mb, lo, hi, y, y_head, self.top - 0.40, z_head + 0.55, mw)
        ob = mb.push(self.K, "rock_gate_stair")
        return [ob] if ob else []

    def build(self):
        import time
        t0 = time.time()
        out = []
        f = self.build_face()
        if f:
            out.append(f)
        c = self.build_cap()
        if c:
            out.append(c)
        self.stats["face"] = time.time() - t0
        t1 = time.time()
        for fn in (self.build_rubble, self.build_wall_stones,
                   self.build_cap_dressing):
            ob = fn()
            if ob:
                out.append(ob)
        self.stats["rubble"] = time.time() - t1
        t2 = time.time()
        if self.plants:
            p = self.build_plants()
            if p:
                out.append(p)
        self.stats["plants"] = time.time() - t2
        t3 = time.time()
        out.extend(self.build_road())
        self.stats["road"] = time.time() - t3
        self.stats["total"] = time.time() - t0
        out = [o for o in out if o]
        self.objs = out
        return out

    def report(self):
        nv = nf = ntr = 0
        for o in self.objs:
            me = o.data
            me.calc_loop_triangles()
            nv += len(me.vertices)
            nf += len(me.polygons)
            ntr += len(me.loop_triangles)
        return dict(objects=len(self.objs), verts=nv, faces=nf, tris=ntr,
                    secs=round(self.stats.get("total", 0.0), 2),
                    per={k: round(v, 2) for k, v in self.stats.items()})


# --------------------------------------------------------------------------- #
#  public API
# --------------------------------------------------------------------------- #
def build(K, MAT, cx=0.0, cy=303.4, r=82.0, top_z=18.0, seed=11,
          style="limestone", **kw):
    """The castle crag.  Returns the list of linked objects.

    Replaces, in capital.py:build_castle_hd(), the whole rock block:
    rock_mass(...) + the 18 rock_boul + 26 rock_rim boxes + the rock_top disc.
    The plateau's top is left at top_z + ~0.2 (the castle's own plinth is
    0.94 m deep, so it sits *in* the rock) and nothing rises above
    top_z + 1.4, except the natural rim ridge, which is outside the castle's
    footprint.
    """
    cr = Crag(K, MAT, cx=cx, cy=cy, r=r, top_z=top_z, seed=seed, style=style, **kw)
    out = cr.build()
    build.LAST = cr
    return out


build.LAST = None


def _gaps_from_gates(gates, hw=17.0):
    """capital.outer_gaps() gives [(point, outward_angle_rad), ...].

    The scarp must open where the roads leave or the town is walled in twice:
    once by its wall and once by my rock.  A 17 deg half-width is a 560 m
    opening at r = 947, which is what the four avenues need.
    """
    out = []
    for g in gates or ():
        try:
            ang = float(g[1])
        except (TypeError, IndexError, ValueError):
            continue
        out.append((math.degrees(ang) % 360.0, float(hw)))
    return out


def cliff_ring(K, MAT, r=947.2, seed=23, style="limestone", height=(6.0, 15.0),
               gaps=None, gates=None, nth=1400, cx=0.0, cy=0.0, verbose=False,
               plants=True, tilt=0.0):
    """The city's rim: a rock scarp where the town's ground disc now just ends.

    Today the town is a 947 m disc at z = 0 with a plate of grass outside it, so
    the join is a perfect circular grass-to-grass seam -- the edge of a green
    plate, which is exactly what it looks like from the air.

    This lays a broken rock band on the seam, and it is a *bank*, not a trench:
    the outside ground is owned by hd_landscape/hd_river and cannot be dug down
    without touching files that are not mine, so everything here stands ABOVE
    z = 0 and the plate only ever clips the last few centimetres of the fan.

        inside          the town's flat ground
        r-17 ... r-0.2  a rocky bank that dies into the ground at -0.95 m, so
                        the join is a scatter of outcrops, not a line
        r-0.2 ... r+2   the crest: 6-15 m, so it reads as a rim behind the
                        outer wall (the wall polygon is at 0.985 R = 933 m and
                        lands on the flat part of the bank, 0.6 m up)
        r+2 ... r+~10   the cliff, in bedding steps, with ledges
        out to r+~26    a scree fan at 8-14 deg, with the boulders that came off
                        the top, half-buried

    33 deg talus is *not* what a free-standing scarp does: a 33 deg cone needs a
    pit to pour into, so the fan here is the wash-out angle, and the 33 deg
    talus belongs to the crag, where there is 18 m of rock and room to spread.

    gaps:  [(deg, halfwidth_deg), ...] explicit openings for the roads.
    gates: capital.outer_gaps() -- [(point, angle_rad), ...] -- converted here,
           so the main script does not have to do the trigonometry.
    """
    import time
    t0 = time.time()
    rng = random.Random(seed * 101 + 7)
    nth = max(180, int(nth))
    hmin, hmax = float(height[0]), float(height[1])
    rz = _NZ(seed + 4)
    mrock = rock_material(MAT, "rock_strata_cliff", style,
                          dip=(DIP[0] * 0.35, DIP[1] * 0.35))
    mscree = scree_material(MAT, "rock_scree_cliff", style)
    mturf = turf_material(MAT, "rock_turf_cliff", style)
    if gaps is None:
        gaps = _gaps_from_gates(gates) if gates else \
            [(0.0, 15.0), (90.0, 15.0), (180.0, 15.0), (270.0, 26.0)]
    mb = MB()
    mr = mb.slot(mrock)
    msc = mb.slot(mscree)
    mt = mb.slot(mturf)
    mleaf = mb.slot((MAT or {}).get("leaf") or mturf)
    ths = [TAU * i / nth for i in range(nth)]

    def h_at(th):
        d = math.degrees(th) % 360.0
        n = rz.at(90.0 * math.cos(th), 90.0 * math.sin(th), 31.0)
        h = hmin + (hmax - hmin) * (0.5 + 0.5 * n)
        for (gd, hw) in gaps:
            dd = abs(((d - gd + 180.0) % 360.0) - 180.0)
            if dd < hw + 18.0:
                h = lerp(1.30, h, smoothstep(hw, hw + 18.0, dd))
        return h

    # ---- the cross-section ------------------------------------------------
    NF = 5                                  # fan rows
    NGH = 7                                 # bedding steps down the cliff
    NB = 6                                  # rows before the cliff
    ROWS = NB + NGH + NF
    ZF = 0.55                               # height of the cliff foot
    # The apron has to *dive under the grass*, not spread out to a shelf: the
    # landscape height field is flat 0 inside 700 m and dips to -3.1 m in the
    # south-west sector, so a toe at -3.4 m is buried everywhere and the only
    # visible part is the 6 m of rubble skirt at the foot of the cliff.
    FAN = ((1.8, 0.55), (2.4, 0.10), (2.8, -0.35), (3.4, -1.20), (4.2, -3.40))
    KIND = [0, 0, 0, 1, 1, 1] + [1] * NGH + [2] * NF

    cols = []
    for th in ths:
        h = h_at(th)
        wob = 2.4 * rz.at(260.0 * math.cos(th), 260.0 * math.sin(th), 173.0)
        jn = rz.at(200.0 * math.cos(th), 200.0 * math.sin(th), 7.0)
        c = []
        c.append((r - 17.0 + wob, -0.95))
        c.append((r - 9.0 + wob, -0.05))
        c.append((r - 5.0 + wob, 0.34 * h))
        c.append((r - 2.6 + wob, 0.82 * h))
        c.append((r - 0.2 + wob, 1.00 * h))
        c.append((r + 2.0 + wob, 0.975 * h))
        for k in range(NGH):
            t = (k + 1) / float(NGH)
            z = max(h - (h - ZF) * t, 0.12)
            d = 0.90 * (h - ZF) * math.log(1.70 / max(1.70 - 1.02 * t, 0.22))
            off = 0.26 * math.sin(k * 2.17) + 0.20 * jn + 0.06 * math.sin(th * 9.0 + k)
            off -= 0.34 if k in (2, 5) else 0.0
            c.append((c[-1][0] + 0.55 + d * 0.42, z + off * 0.30))
        for (dr, z) in FAN:
            c.append((c[-1][0] + dr, z + 0.05 * jn))
        cols.append(c)

    for ri in range(ROWS - 1):
        mat = (mt if KIND[ri] == 0 else (msc if KIND[ri] == 2 else mr))
        for i in range(nth):
            j = (i + 1) % nth
            a, b = cols[i][ri], cols[j][ri]
            c, d = cols[j][ri + 1], cols[i][ri + 1]
            o = len(mb.v)
            mb.v.extend([
                (cx + a[0] * math.cos(ths[i]), cy + a[0] * math.sin(ths[i]), a[1]),
                (cx + b[0] * math.cos(ths[j]), cy + b[0] * math.sin(ths[j]), b[1]),
                (cx + c[0] * math.cos(ths[j]), cy + c[0] * math.sin(ths[j]), c[1]),
                (cx + d[0] * math.cos(ths[i]), cy + d[0] * math.sin(ths[i]), d[1])])
            mb.f.append((o, o + 3, o + 2, o + 1))
            mb.mi.append(mat)

    # ---- what came off the cliff -----------------------------------------
    # placed against the *built* rows, so a block sits on the stone it fell
    # from instead of on a formula's idea of where the stone is
    nboul = int(nth * 0.85)
    for _ in range(nboul):
        i = rng.randrange(nth)
        th = ths[i]
        col = cols[i]
        if rng.random() < 0.58:                    # rubble skirt at the foot
            lo = col[NB + NGH - 1]
            t = rng.random() ** 0.70
            rr = lo[0] + t * 5.6
            zz = lo[1] - t * 0.85 + rng.uniform(-0.10, 0.10)
        else:                                      # stuck on a bedding ledge
            k = rng.randrange(NGH)
            a = col[NB + k]
            rr = a[0] + rng.uniform(-0.15, 0.45)
            zz = a[1] + rng.uniform(0.10, 0.45)
        rad = 0.20 * (9.0 ** rng.random())         # 0.20 .. 1.8 m, power law
        ico_emit(mb, (cx + rr * math.cos(th), cy + rr * math.sin(th),
                      zz + rad * 0.28), rad, rng, mat=msc,
                 sub=1 if rad > 0.55 else 0, squash=(1.0, 1.0, 0.72),
                 jitter=0.34)

    # ---- scrub on the crest, and the plants hanging over the lip ---------
    if plants:
        for _ in range(int(nth * 0.11)):
            i = rng.randrange(nth)
            th, h = ths[i], h_at(ths[i])
            rr = r + rng.uniform(-3.2, 2.2)
            zz = h * rng.uniform(0.94, 1.00)
            sz = rng.uniform(0.7, 2.3)
            ico_emit(mb, (cx + rr * math.cos(th), cy + rr * math.sin(th), zz + sz * 0.3),
                     sz, rng, mat=mleaf, sub=1 if sz > 1.4 else 0,
                     squash=(1.15, 1.15, 0.62), jitter=0.30)
        for _ in range(int(nth * 0.05)):
            i = rng.randrange(nth)
            th, h = ths[i], h_at(ths[i])
            rr = r + rng.uniform(1.2, 2.6)
            x0, y0 = cx + rr * math.cos(th), cy + rr * math.sin(th)
            L = rng.uniform(1.4, 4.4)
            n = 4
            pts, rads = [], []
            for s in range(n + 1):
                t = s / float(n)
                pts.append((x0 + (0.28 * math.cos(th)) * t * L,
                            y0 + (0.28 * math.sin(th)) * t * L,
                            h * 0.97 - L * t + 0.08 * math.sin(t * 5.0 + i)))
                rads.append(0.16 * (1.0 - 0.72 * t))
            _tube_mb(mb, pts, rads, 3, mleaf)

    ob = mb.push(K, "cliff_ring")
    dt = time.time() - t0
    if ob is not None:
        ob.data.calc_loop_triangles()
        cliff_ring.STATS = dict(objs=1, verts=len(ob.data.vertices),
                               faces=len(ob.data.polygons),
                               tris=len(ob.data.loop_triangles),
                               secs=round(dt, 2), nth=nth)
    if verbose:
        print("[rock] cliff_ring %.2fs %r" % (dt, cliff_ring.STATS))
    cliff_ring.LAST = ob
    return [ob] if ob else []


cliff_ring.LAST = None
cliff_ring.STATS = None
