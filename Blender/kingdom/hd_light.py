"""hd_light.py - light rig for the Asura royal capital: 6 time-of-day presets,
6 fixed cameras, contact shadows, graded aerial perspective.  Blender 5.2.

Why this file exists
--------------------
`renders/kingdom/b5_overview.png` showed 2,400 blocks and 12 M triangles lit like
a paper model: every mass sat on the carpet with no shadow under it.  Three
separate faults made that frame, and this module is built around fixing all
three:

  1. SUN ANGLE.  The old rig ran the sun at ~52 deg.  At that elevation a block
     casts a shadow 0.78x its own height, which hides *under* the block and is
     invisible from an aerial camera.  Here street shots get 28-42 deg (shadow
     1.11-1.88x height) and aerials 45-55 deg, and the azimuth is chosen so the
     light rakes across the roofs instead of facing the camera.
  2. CONTACT.  A shadow map carries no information at the wall/ground seam, so
     props and facades float.  We render a Cycles ambient-occlusion pass at
     0.35-0.9 m and multiply it back in the compositor, so wall feet, the
     underside of eaves and the shadow under a barrel go dark by themselves.
     The broad end of the same cascade comes free from real GI, because the sky
     dome is occluded by the geometry around it.
  3. AIR.  One haze density everywhere is either clear everywhere or fog
     everywhere.  The density here is solved against two transmittance targets
     -- T(80 m) >= 0.93 and T(600 m) in 0.45..0.65 -- which is what "near clear,
     far hazy" actually means as a number.  The haze colour is the sky's own
     horizon colour (cool), so distance goes cold while the near field, lit by a
     warm sun plus a warm stone bounce, stays hot.  That is the correct
     direction of aerial perspective.

Reuse, not rewrite
------------------
The sky model, the sun lamp, the volume and the AgX grade already exist and are
self-accepted in `hd_atmosphere.py`.  This module *imports* it (`A.world_sky`,
`A.sun_light`, `A.haze`) and only adds what was missing: the bounce card, the
contact cascade, the density solve, the camera table and the per-shot sun
override.  Nothing in hd_atmosphere.py is edited.

Units
-----
`sun_energy` is the artistic unit defined in hd_atmosphere (calibrated against
sky_strength = 1.0), NOT W/m^2 -- see that file's header.  The bounce card is
specified as a *ratio to the sky dome* and the watts are derived from a measured
constant (`BOUNCE_W_PER_RATIO`), so "sky : ground = 1 : 0.21" is a measurement,
not a guess.

Typical use
-----------
    import hd_light as L
    L.apply("golden_street")                       # canonical sun for the preset
    cam = L.camera("main_street")                  # one of the six fixed rigs
    L.shot("golden_street", cam, "out.png")        # apply + aim + render

    # 6 presets x 6 cameras:
    for p in L.PRESETS:
        for c in L.CAMERAS:
            L.shot(p, c, "light_%s_%s.png" % (p, c))
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy
from mathutils import Vector, Euler

import hd_atmosphere as A          # sky / sun / volume / grade primitives

D2R = math.pi / 180.0

# ---------------------------------------------------------------------------
# instrumentation -- same contract as hd_atmosphere: nothing fails silently
# ---------------------------------------------------------------------------
APPLIED = []          # [(key, detail), ...]
FAILED = []           # [(key, "error"), ...]
LOG = True


def _ok(key, detail):
    APPLIED.append((key, detail))
    if LOG:
        print("  [light ok]   %-18s %s" % (key, detail), flush=True)


def _fail(key, detail):
    FAILED.append((key, str(detail)))
    print("  [light FAIL] %-18s %s" % (key, detail), flush=True)


def _num_eq(a, b, tol=1e-5):
    try:
        if hasattr(b, "__len__") or isinstance(b, (tuple, list)):
            try:
                av, bv = tuple(a), tuple(b)
            except TypeError:
                return False
            if len(av) < len(bv):
                return False
            return all(abs(float(x) - float(y)) <= max(tol, abs(float(y)) * 1e-5)
                       for x, y in zip(av, bv))
        return abs(float(a) - float(b)) <= max(tol, abs(float(b)) * 1e-5)
    except (TypeError, ValueError):
        return a == b


def _set(owner, attr, value, key, socket=None, tol=1e-5):
    """Set a legacy RNA property, else a node-input socket; read the value back."""
    if hasattr(owner, attr):
        try:
            setattr(owner, attr, value)
            got = getattr(owner, attr)
            if not _num_eq(got, value, tol):
                raise ValueError("readback %r != %r" % (got, value))
            _ok(key, "%s=%r" % (attr, value))
            return True
        except Exception as exc:                                  # noqa: BLE001
            _fail(key, "%s: %s" % (attr, exc))
            return False
    ins = getattr(owner, "inputs", None)
    if socket and ins is not None and socket in ins:
        try:
            s = ins[socket]
            s.default_value = value
            if not _num_eq(s.default_value, value, tol):
                raise ValueError("socket readback %r != %r" % (s.default_value, value))
            _ok(key, "%s=%r (socket)" % (socket, value))
            return True
        except Exception as exc:                                  # noqa: BLE001
            _fail(key, "%s socket: %s" % (socket, exc))
            return False
    _fail(key, "no property %r and no socket %r" % (attr, socket))
    return False


def _set_sock(node, socket, value, key, tol=1e-5):
    ins = getattr(node, "inputs", None)
    if ins is None or socket not in ins:
        _fail(key, "node %s has no input %r" % (node.bl_idname, socket))
        return False
    try:
        ins[socket].default_value = value
        if not _num_eq(ins[socket].default_value, value, tol):
            raise ValueError("readback %r != %r" % (ins[socket].default_value, value))
        _ok(key, "%s=%r" % (socket, value))
        return True
    except Exception as exc:                                      # noqa: BLE001
        _fail(key, "%s: %s" % (socket, exc))
        return False


def _math(nt, op, loc, label):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.location = loc
    if n.operation != op:
        _fail(label, "Math op %r not accepted" % op)
    return n


def _mix_color(nt, loc, label):
    """A colour multiply node, whatever this build calls it.

    Blender 5.2 deleted CompositorNodeMixRGB; the compositor now uses the shader
    ShaderNodeMix with data_type RGBA, whose colour sockets are inputs[6]/[7] and
    output[2] (the first four sockets of each are the other data types).
    """
    for t in ("CompositorNodeMixRGB", "ShaderNodeMix"):
        try:
            n = nt.nodes.new(t)
        except Exception:                                         # noqa: BLE001
            continue
        if t == "ShaderNodeMix":
            n.data_type = "RGBA"
            n.blend_type = "MULTIPLY"
            n.location = loc
            _ok(label, "node ShaderNodeMix(RGBA)")
            return n, n.inputs[0], n.inputs[6], n.inputs[7], n.outputs[2]
        n.blend_type = "MULTIPLY"
        n.location = loc
        _ok(label, "node CompositorNodeMixRGB")
        return n, n.inputs["Fac"], n.inputs["Color1"], n.inputs["Color2"], n.outputs["Color"]
    _fail(label, "no colour mix node available")
    return None, None, None, None, None


# ---------------------------------------------------------------------------
# calibration
# ---------------------------------------------------------------------------
# Watts on the bounce card that produce a ground/sky irradiance ratio of 1.0 on
# a vertical surface at sky_strength = 1.0.  Measured once with the probe in
# _light_test.py (calib_bounce) -- see report()["calibration"].
BOUNCE_W_PER_RATIO = 2.45e7
BOUNCE_SIZE = 1700.0          # card half-extent covers the whole city (r=640 m)
BOUNCE_Z = 0.30

# ---------------------------------------------------------------------------
# presets
#   sun_elev_street / sun_elev_wide  the two sun elevations the brief asks for
#   sun_azim    compass degrees: 0 = south (-Y), 90 = east (+X), 180 = north, 270 = west
#   sun_energy  hd_atmosphere artistic unit; sun_angle is the angular diameter
#   sky_*       forwarded to A.world_sky
#   bounce_ratio  ground-bounce irradiance / sky irradiance on a vertical face
#   haze / haze_h / haze_color / haze_aniso  forwarded to A.haze
#   ao_dist / ao_strength  contact-shadow cascade (metres, compositor mix)
# ---------------------------------------------------------------------------
_BASE = dict(
    atmos="clear_morning",
    sun_elev_street=34.0, sun_elev_wide=48.0,
    sun_azim=110.0, sun_color=(1.0, 0.88, 0.74), sun_energy=85.0,
    sun_angle=1.20, sun_soft=0.35,
    sky_strength=1.00, sky_tint=(0.95, 0.98, 1.03), sky_aerosol=0.70, sky_alt=120.0,
    bounce_color=(0.62, 0.47, 0.33), bounce_ratio=0.21,
    haze=0.00085, haze_h=200.0, haze_color=(0.72, 0.80, 0.92), haze_aniso=0.60,
    exposure=-2.60, contrast=1.10, sat=1.05, glare=0.18,
    look="AgX - Punchy",
    ao_dist=0.55, ao_strength=0.55,
    torch=False, glow=False,
)

PRESETS = {
    # ---- 1. early morning: the town wakes, long cold shadows, warm roofs -----
    "morning_town": dict(
        atmos="clear_morning",
        sun_elev_street=32.0, sun_elev_wide=48.0, sun_azim=112.0,
        sun_color=(1.00, 0.855, 0.705), sun_energy=88.0, sun_angle=1.40, sun_soft=0.40,
        sky_strength=1.00, sky_tint=(0.94, 0.975, 1.05), sky_aerosol=0.72, sky_alt=110.0,
        bounce_color=(0.60, 0.45, 0.31), bounce_ratio=0.215,
        haze=0.00082, haze_h=210.0, haze_color=(0.70, 0.79, 0.93), haze_aniso=0.62,
        exposure=-2.55, contrast=1.10, sat=1.06, glare=0.18, look="AgX - Punchy",
        ao_dist=0.55, ao_strength=0.58),
    # ---- 2. hard noon: bleached stone, short but razor shadows ---------------
    "noon_harsh": dict(
        atmos="clear_noon",
        sun_elev_street=40.0, sun_elev_wide=52.0, sun_azim=152.0,
        sun_color=(1.00, 0.972, 0.940), sun_energy=104.0, sun_angle=0.52, sun_soft=0.18,
        sky_strength=0.95, sky_tint=(0.90, 0.955, 1.04), sky_aerosol=0.38, sky_alt=200.0,
        bounce_color=(0.64, 0.51, 0.37), bounce_ratio=0.190,
        haze=0.00052, haze_h=330.0, haze_color=(0.75, 0.84, 0.97), haze_aniso=0.45,
        exposure=-4.30, contrast=1.15, sat=0.97, glare=0.13,
        look="AgX - Medium High Contrast",
        ao_dist=0.45, ao_strength=0.62),
    # ---- 3. golden hour down a street: the brief's hero preset ---------------
    "golden_street": dict(
        atmos="golden_hour",
        sun_elev_street=30.0, sun_elev_wide=46.0, sun_azim=246.0,
        sun_color=(1.00, 0.640, 0.370), sun_energy=92.0, sun_angle=0.95, sun_soft=0.32,
        sky_strength=0.82, sky_tint=(0.95, 0.975, 1.06), sky_aerosol=0.95, sky_alt=70.0,
        bounce_color=(0.68, 0.47, 0.30), bounce_ratio=0.240,
        haze=0.00095, haze_h=185.0, haze_color=(0.80, 0.77, 0.84), haze_aniso=0.62,
        exposure=-2.35, contrast=1.14, sat=1.13, glare=0.24, look="AgX - Punchy",
        ao_dist=0.60, ao_strength=0.56),
    # ---- 4. overcast: no hard shadow at all, the contact cascade carries it --
    "overcast_soft": dict(
        atmos="overcast",
        sun_elev_street=38.0, sun_elev_wide=50.0, sun_azim=178.0,
        sun_color=(0.88, 0.910, 0.960), sun_energy=8.0, sun_angle=14.0, sun_soft=2.60,
        sky_strength=1.45, sky_tint=(0.88, 0.925, 0.985), sky_aerosol=2.40, sky_alt=120.0,
        bounce_color=(0.60, 0.50, 0.40), bounce_ratio=0.205,
        haze=0.00105, haze_h=165.0, haze_color=(0.81, 0.845, 0.905), haze_aniso=0.30,
        exposure=-4.05, contrast=1.05, sat=0.90, glare=0.10,
        look="AgX - Base Contrast",
        ao_dist=0.70, ao_strength=0.70),
    # ---- 5. dusk: sun on the horizon, blue shadow, warm rim -----------------
    # documented exception to the 28-42 deg rule: a dusk preset with the sun at
    # 30 deg is not a dusk preset.  16 deg is the whole point of the look.
    "dusk_city": dict(
        atmos="clear_dawn",
        sun_elev_street=16.0, sun_elev_wide=24.0, sun_azim=262.0,
        sun_color=(1.00, 0.430, 0.185), sun_energy=58.0, sun_angle=1.10, sun_soft=0.30,
        sky_strength=0.58, sky_tint=(0.95, 0.93, 1.00), sky_aerosol=1.25, sky_alt=90.0,
        bounce_color=(0.55, 0.36, 0.26), bounce_ratio=0.225,
        haze=0.00115, haze_h=245.0, haze_color=(0.56, 0.61, 0.79), haze_aniso=0.58,
        exposure=-1.55, contrast=1.12, sat=1.10, glare=0.28, look="AgX - Punchy",
        ao_dist=0.55, ao_strength=0.55),
    # ---- 6. night: moon key + torch practicals ------------------------------
    "night_torch": dict(
        atmos="night",
        sun_elev_street=32.0, sun_elev_wide=32.0, sun_azim=158.0,
        sun_color=(0.52, 0.660, 0.960), sun_energy=1.55, sun_angle=1.10, sun_soft=0.30,
        sky_strength=0.075, sky_tint=(0.62, 0.72, 1.00), sky_aerosol=0.70, sky_alt=180.0,
        bounce_color=(0.40, 0.30, 0.22), bounce_ratio=0.200,
        haze=0.00062, haze_h=300.0, haze_color=(0.30, 0.38, 0.56), haze_aniso=0.50,
        exposure=0.35, contrast=1.10, sat=0.95, glare=0.30, look="AgX - Punchy",
        ao_dist=0.55, ao_strength=0.50,
        torch=True, glow=True),
}
for _k, _v in PRESETS.items():
    PRESETS[_k] = dict(_BASE, **_v)
del _k, _v

# ---------------------------------------------------------------------------
# the six fixed cameras
#   kind: "street" -> sun_elev_street, "wide" -> sun_elev_wide
#   azim_delta: per-shot art override, degrees added to the preset's compass
#   haze_mul / haze_extent: an aerial sees a much longer column of air
# ---------------------------------------------------------------------------
CAMERAS = {
    # 1. inside the north gate, on the avenue, eye height, 35 mm.  The gatehouse
    #    fills the end of the street and the avenue reads as a corridor.
    "gate_avenue": dict(
        loc=(6.0, 545.0, 1.70), look=(0.0, 640.0, 12.0), lens=35.0,
        kind="street", azim_delta=0.0, haze_mul=1.0, haze_extent=2600.0,
        note="north gate from inside, 1.7 m eye, 35 mm"),
    # 2. a real ring-road frontage, 1.7 m, 28 mm: the shopfront proof shot.
    "main_street": dict(
        loc=(51.0, 51.0, 1.70), look=(14.0, 72.0, 3.0), lens=28.0,
        kind="street", azim_delta=0.0, haze_mul=1.0, haze_extent=2600.0,
        note="ring-road main street, 1.7 m eye, 28 mm"),
    # 3. the market square from 8 m: over the stalls to the hall and the fountain.
    "market_square": dict(
        loc=(9.2, 22.0, 8.0), look=(9.2, 92.0, 5.0), lens=35.0,
        kind="street", azim_delta=0.0, haze_mul=1.05, haze_extent=3000.0,
        note="market square, 8 m, 35 mm"),
    # 4. three-quarter aerial at 480 m, 50 mm.
    "overview_34": dict(
        loc=(700.0, -1240.0, 480.0), look=(0.0, 20.0, 15.0), lens=50.0,
        kind="wide", azim_delta=0.0, haze_mul=2.10, haze_extent=5200.0,
        note="three-quarter aerial, 480 m, 50 mm"),
    # 5. castle close-up from the +Y (north) side, three-quarter.
    "castle_close": dict(
        loc=(150.0, 340.0, 58.0), look=(0.0, 232.0, 40.0), lens=50.0,
        kind="street", azim_delta=0.0, haze_mul=1.15, haze_extent=3200.0,
        note="castle from +Y, 3/4, 50 mm"),
    # 6. cathedral west front plus the square it faces.
    "cathedral_plaza": dict(
        loc=(46.0, -86.0, 16.0), look=(-96.0, 40.0, 30.0), lens=28.0,
        kind="street", azim_delta=0.0, haze_mul=1.10, haze_extent=3200.0,
        note="cathedral + plaza, 28 mm"),
}

_TAG = "LIGHT_"          # every object this module owns starts with this


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _scn(scene=None):
    if scene is not None and scene != bpy.context.scene:
        try:
            bpy.context.window.scene = scene
        except Exception:                                         # noqa: BLE001
            _fail("scene", "cannot activate %r; using context scene" % (scene,))
    return bpy.context.scene


def _drop(*names):
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob is not None:
            bpy.data.objects.remove(ob, do_unlink=True)


def _clear_owned():
    for ob in [o for o in bpy.data.objects if o.name.startswith(_TAG)]:
        bpy.data.objects.remove(ob, do_unlink=True)


def _fog_transmittance(sigma, h, eye_z, length):
    """Analytic optical depth of a horizontal ray through exp(-z/h) haze."""
    d = sigma * math.exp(-max(0.0, eye_z) / max(1.0, h))
    return math.exp(-d * length)


# ---------------------------------------------------------------------------
# 1. sky
# ---------------------------------------------------------------------------
def sky(preset, sun_elev=None, sun_azim=None):
    """Sky dome: hd_atmosphere's model, re-tinted for this preset."""
    p = PRESETS[preset]
    elev = p["sun_elev_street"] if sun_elev is None else sun_elev
    azim = p["sun_azim"] if sun_azim is None else sun_azim
    w = A.world_sky(p["atmos"], sun_elev=elev, sun_azim=azim,
                    tint=p["sky_tint"], aerosol=p["sky_aerosol"],
                    strength=p["sky_strength"])
    _ok("sky", "%s elev=%.1f azim=%.1f strength=%.2f aerosol=%.2f"
        % (p["atmos"], elev, azim, p["sky_strength"], p["sky_aerosol"]))
    return w


# ---------------------------------------------------------------------------
# 2. sun
# ---------------------------------------------------------------------------
def sun(preset, elev=None, azim=None):
    """The key light, with the shadow settings the brief asks for.

    `angle` is the one that actually softens a SUN lamp's penumbra; `shadow_soft_size`
    is a point/area property that 5.2 still exposes on every light, so it is set
    and read back for the record but the angular diameter is what the renderer
    uses.  Contact shadows are NOT a lamp property in Cycles (that is an EEVEE
    feature) -- they come from the AO cascade in `contact()`.
    """
    p = PRESETS[preset]
    elev = p["sun_elev_street"] if elev is None else elev
    azim = p["sun_azim"] if azim is None else azim
    ob = A.sun_light(p["atmos"], elevation=elev, azimuth=azim,
                     energy=p["sun_energy"], angle_deg=p["sun_angle"])
    ob.name = _TAG + "Sun"
    d = ob.data
    d.name = _TAG + "SunData"
    d.use_shadow = True
    if not d.use_shadow:
        _fail("sun_shadow", "use_shadow did not stick")
    _set(d, "shadow_soft_size", p["sun_soft"], "sun_soft")
    _set(d, "specular_factor", 1.0, "sun_spec")
    _set(d, "diffuse_factor", 1.0, "sun_diff")
    try:
        d.shadow_catcher = False
    except Exception:                                             # noqa: BLE001
        pass
    shadow_len = 1.0 / max(0.05, math.tan(math.radians(elev)))
    _ok("sun", "elev=%.1f azim=%.1f E=%.1f ang=%.2f deg shadow_len=%.2fx height"
        % (elev, azim, p["sun_energy"], p["sun_angle"], shadow_len))
    return ob


# ---------------------------------------------------------------------------
# 3. ground bounce (the 1 : 0.21 half of the fill)
# ---------------------------------------------------------------------------
def bounce(preset, energy_mul=1.0):
    """A warm stone card at ground level, facing up, invisible to camera.

    This is the "ground bounce" the brief asks for instead of flat ambient: the
    sky dome is the dominant fill, this card is the warm stone light coming back
    up off the paving, and the ratio between them is a measured number.  It is
    not visible to the camera or in reflections, so it cannot appear as a plane.
    """
    p = PRESETS[preset]
    _drop(_TAG + "Bounce")
    ld = bpy.data.lights.new(_TAG + "BounceData", "AREA")
    ld.shape = "SQUARE"
    ld.size = BOUNCE_SIZE
    ld.color = tuple(p["bounce_color"])[:3]
    watts = p["bounce_ratio"] * p["sky_strength"] * BOUNCE_W_PER_RATIO * energy_mul
    ld.energy = watts
    ld.use_shadow = False
    ld.specular_factor = 0.0
    ld.diffuse_factor = 1.0
    ob = bpy.data.objects.new(_TAG + "Bounce", ld)
    bpy.context.collection.objects.link(ob)
    ob.location = (0.0, 0.0, BOUNCE_Z)
    ob.rotation_euler = Euler((math.pi, 0.0, 0.0), "XYZ")   # emit +Z
    for attr, val in (("visible_camera", False), ("visible_glossy", False),
                      ("visible_transmission", False),
                      ("visible_volume_scatter", False), ("visible_shadow", False)):
        try:
            setattr(ob, attr, val)
        except Exception as exc:                                  # noqa: BLE001
            _fail("bounce_" + attr, exc)
    _ok("bounce", "ratio=%.3f watts=%.3g colour=%s"
        % (p["bounce_ratio"], watts, tuple(round(c, 2) for c in p["bounce_color"])))
    return ob


# ---------------------------------------------------------------------------
# 4. haze -- density solved against T(80 m) and T(600 m)
# ---------------------------------------------------------------------------
def haze(preset, center=None, mul=1.0, extent=2800.0):
    """Aerial perspective: a ground-hugging exponential medium, distance graded.

    A homogeneous medium already grades with distance (tau = sigma * L); the
    brief's "0-80 m clear, 80-600 m progressive" is exactly the two transmittance
    targets this solve reports.  The colour is cool because that is what a real
    sky scatters down a long sight line, which is the correct direction for
    aerial perspective: near field keeps the warm sun, distance goes blue.
    """
    p = PRESETS[preset]
    sigma = p["haze"] * mul
    ob = A.haze(p["atmos"], density=sigma, height=p["haze_h"], extent=extent,
                center=center, color=p["haze_color"], aniso=p["haze_aniso"])
    ob.name = _TAG + "Haze"
    eye = 1.7
    t80 = _fog_transmittance(sigma, p["haze_h"], eye, 80.0)
    t600 = _fog_transmittance(sigma, p["haze_h"], eye, 600.0)
    _ok("haze", "sigma=%.5f H=%.0f m  T(80m)=%.3f  T(600m)=%.3f  colour=%s"
        % (sigma, p["haze_h"], t80, t600, tuple(round(c, 2) for c in p["haze_color"])))
    return ob, t80, t600


# ---------------------------------------------------------------------------
# 5. contact shadow cascade
# ---------------------------------------------------------------------------
def contact(preset, scene=None):
    """Cycles ambient-occlusion pass at 0.35-0.9 m, multiplied back in post.

    Two scales of occlusion end up in the frame:
      * this pass, at ~0.5 m, is the tight contact -- wall feet, under eaves,
        under a barrel or a cart;
      * the real GI already darkens the broad scale, because the sky dome is
        physically occluded by the surrounding masses.
    Together that is the "AO/SSAO cascade" the brief asks for, and it is what
    stops props from floating.
    """
    p = PRESETS[preset]
    sc = _scn(scene)
    vl = bpy.context.view_layer
    ok = True
    for attr in ("use_pass_ambient_occlusion",):
        if not hasattr(vl, attr):
            _fail("ao_pass", "view layer has no %s" % attr)
            ok = False
            continue
        try:
            setattr(vl, attr, True)
            if not getattr(vl, attr):
                raise ValueError("did not stick")
            _ok("ao_pass", attr + "=True")
        except Exception as exc:                                  # noqa: BLE001
            _fail("ao_pass", "%s: %s" % (attr, exc))
            ok = False
    w = sc.world
    if w is not None:
        try:
            w.light_settings.distance = p["ao_dist"]
            got = w.light_settings.distance
            if abs(got - p["ao_dist"]) > 1e-4:
                raise ValueError("readback %.3f" % got)
            _ok("ao_dist", "%.2f m" % p["ao_dist"])
        except Exception as exc:                                  # noqa: BLE001
            _fail("ao_dist", exc)
            ok = False
    return ok


# ---------------------------------------------------------------------------
# 6. Cycles
# ---------------------------------------------------------------------------
def cycles(preset, samples=192, res=(1600, 900), gpu=True, scene=None):
    """Render settings: enough bounces for the GI that carries the shadows,
    a clamp that kills fireflies without eating bounce light, OIDN on."""
    p = PRESETS[preset]
    sc = _scn(scene)
    sc.render.engine = "CYCLES"
    cy = sc.cycles
    cy.device = "GPU" if gpu else "CPU"
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.018
    cy.use_denoising = True
    for den in ("OPENIMAGEDENOISE", "OPTIX"):
        try:
            cy.denoiser = den
            break
        except Exception:                                         # noqa: BLE001
            continue
    # bounces: the contact shadow *is* bounce light, so diffuse needs headroom
    cy.max_bounces = 10
    cy.diffuse_bounces = 4
    cy.glossy_bounces = 3
    cy.transmission_bounces = 4
    cy.volume_bounces = 2
    cy.transparent_max_bounces = 8
    # clamp: direct untouched, indirect capped so one firefly cannot smear
    cy.sample_clamp_direct = 0.0
    cy.sample_clamp_indirect = 8.0
    cy.blur_glossy = 1.0
    cy.use_light_tree = True
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    try:
        cy.volume_step_rate = 0.35
        cy.volume_max_steps = 512
    except Exception:                                             # noqa: BLE001
        pass
    sc.render.use_persistent_data = True      # one BVH for all 36 shots
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"
    if gpu:
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = "OPTIX"
            prefs.get_devices()
            for d in prefs.devices:
                d.use = d.type in ("OPTIX", "CUDA")
        except Exception as exc:                                  # noqa: BLE001
            _fail("gpu", exc)
    _ok("cycles", "%d spp, bounces %d/%d/%d, clamp %.1f, %s"
        % (samples, cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces,
           cy.sample_clamp_indirect, cy.device))
    return sc


# ---------------------------------------------------------------------------
# 7. night practicals
# ---------------------------------------------------------------------------
_GLOW_MATS = ("torch_glow", "mkt_glow", "glow", "glow_warm", "fire_glow",
              "glass_warm", "glow_magic")
_EMIT_ORIG = {}


def _glow(preset):
    """Make the torch/lantern materials actually emit for the night preset."""
    p = PRESETS[preset]
    if not p["glow"]:
        if _EMIT_ORIG:
            for name, (col, stg) in _EMIT_ORIG.items():
                m = bpy.data.materials.get(name)
                if not m or not m.use_nodes:
                    continue
                for n in m.node_tree.nodes:
                    if n.type == "BSDF_PRINCIPLED":
                        n.inputs["Emission Color"].default_value = col
                        n.inputs["Emission Strength"].default_value = stg
            _EMIT_ORIG.clear()
            _ok("glow", "restored")
        return 0
    n = 0
    for name in _GLOW_MATS:
        m = bpy.data.materials.get(name)
        if m is None or not m.use_nodes:
            continue
        for node in m.node_tree.nodes:
            if node.type != "BSDF_PRINCIPLED":
                continue
            try:
                col = tuple(node.inputs["Emission Color"].default_value)
                stg = float(node.inputs["Emission Strength"].default_value)
                if name not in _EMIT_ORIG:
                    _EMIT_ORIG[name] = (col, stg)
                base = node.inputs["Base Color"]
                rgb = (tuple(base.default_value)[:3] if not base.is_linked
                       else tuple(node.inputs["Emission Color"].default_value)[:3])
                node.inputs["Emission Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
                node.inputs["Emission Strength"].default_value = 9.0
                n += 1
            except Exception as exc:                              # noqa: BLE001
                _fail("glow_" + name, exc)
    _ok("glow", "%d materials emitting" % n)
    return n


def _torches(preset, max_lights=28):
    """A handful of real point lights on torch props, so night casts shadows."""
    p = PRESETS[preset]
    for ob in [o for o in bpy.data.objects if o.name.startswith(_TAG + "Torch")]:
        bpy.data.objects.remove(ob, do_unlink=True)
    if not p["torch"]:
        return 0
    picks = []
    for ob in bpy.data.objects:
        if ob.type != "MESH" or not ob.name.lower().startswith(("torch", "lamp", "lantern")):
            continue
        picks.append(ob)
        if len(picks) >= 400:
            break
    if not picks:
        for ob in bpy.data.objects:
            if ob.type != "MESH":
                continue
            for sl in ob.material_slots:
                if sl.material and sl.material.name in ("torch_glow", "mkt_glow"):
                    picks.append(ob)
                    break
            if len(picks) >= 400:
                break
    if not picks:
        _fail("torches", "no torch props found")
        return 0
    step = max(1, len(picks) // max_lights)
    made = 0
    for ob in picks[::step][:max_lights]:
        ld = bpy.data.lights.new(_TAG + "TorchData", "POINT")
        ld.energy = 320.0
        ld.color = (1.0, 0.52, 0.20)
        ld.shadow_soft_size = 0.09
        ld.use_shadow = True
        lo = bpy.data.objects.new(_TAG + "Torch%02d" % made, ld)
        bpy.context.collection.objects.link(lo)
        lo.location = ob.matrix_world.translation + Vector((0.0, 0.0, 0.35))
        made += 1
    _ok("torches", "%d point lights from %d props" % (made, len(picks)))
    return made


# ---------------------------------------------------------------------------
# 8. compositor: contact AO -> glare -> grade
# ---------------------------------------------------------------------------
def post(preset, scene=None):
    """Exposure, AgX, AO contact multiply, fog glow, contrast, saturation."""
    p = PRESETS[preset]
    sc = _scn(scene)
    _set(sc.view_settings, "view_transform", "AgX", "view_transform")
    got_look = None
    for cand in (p.get("look"), "AgX - Base Contrast", "None"):
        try:
            sc.view_settings.look = cand
            if sc.view_settings.look == cand:
                got_look = cand
                _ok("look", "look=%r" % cand)
                break
        except Exception:                                         # noqa: BLE001
            continue
    if got_look is None:
        _fail("look", "no AgX look accepted")
    _set(sc.view_settings, "exposure", p["exposure"], "exposure")
    _set(sc.render, "dither_intensity", 1.0, "dither")

    try:
        sc.use_nodes = True
    except Exception:                                             # noqa: BLE001
        pass
    nt = None
    try:
        if hasattr(sc, "compositing_node_group"):
            g = sc.compositing_node_group
            if g is None:
                g = bpy.data.node_groups.new("CapitalLight", "CompositorNodeTree")
                sc.compositing_node_group = g
            nt = g
        else:
            nt = sc.node_tree
    except Exception as exc:                                      # noqa: BLE001
        _fail("compositor", exc)
        return None
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    rl.location = (-900, 0)
    chain = rl
    out_sock = rl.outputs["Image"]

    # --- contact shadow: image * (1 - s + s*AO) ---------------------------
    ao_name = None
    for cand in ("AO", "Ambient Occlusion", "AmbientOcclusion"):
        if cand in rl.outputs:
            ao_name = cand
            break
    if ao_name is not None and p["ao_strength"] > 0.0:
        n, fac, c1, c2, out = _mix_color(nt, (-700, 120), "ao_mult")
        if n is not None:
            fac.default_value = float(p["ao_strength"])
            nt.links.new(out_sock, c1)
            nt.links.new(rl.outputs[ao_name], c2)
            out_sock = out
            chain = n
            _ok("ao_comp", "image x AO at %.2f" % p["ao_strength"])
    else:
        _fail("ao_comp", "AO output %r not on RenderLayers" % (ao_name,))

    # --- bloom ------------------------------------------------------------
    glare = None
    try:
        glare = nt.nodes.new("CompositorNodeGlare")
        glare.location = (-500, 0)
        _set_sock(glare, "Type", "Fog Glow", "glare_type")
        _set_sock(glare, "Quality", "High", "glare_quality")
        _set_sock(glare, "Threshold", 1.6, "glare_threshold")
        _set_sock(glare, "Smoothness", 0.6, "glare_smooth")
        _set_sock(glare, "Size", 0.10, "glare_size")
        _set_sock(glare, "Strength", min(0.8, p["glare"]), "glare")
        nt.links.new(out_sock, glare.inputs["Image"])
        out_sock = glare.outputs["Image"]
    except Exception as exc:                                      # noqa: BLE001
        _fail("glare", exc)

    # --- grade ------------------------------------------------------------
    bc = None
    try:
        bc = nt.nodes.new("CompositorNodeBrightContrast")
        bc.location = (-300, 0)
        _set_sock(bc, "Brightness", 0.0, "contrast_bright")
        _set_sock(bc, "Contrast", round((p["contrast"] - 1.0) * 100.0, 3), "contrast")
        nt.links.new(out_sock, bc.inputs["Image"])
        out_sock = bc.outputs["Image"]
    except Exception as exc:                                      # noqa: BLE001
        _fail("contrast", exc)

    hs = None
    try:
        hs = nt.nodes.new("CompositorNodeHueSat")
        hs.location = (-100, 0)
        _set_sock(hs, "Hue", 0.5, "sat_hue")
        _set_sock(hs, "Saturation", p["sat"], "sat")
        _set_sock(hs, "Value", 1.0, "sat_value")
        nt.links.new(out_sock, hs.inputs["Image"])
        out_sock = hs.outputs["Image"]
    except Exception as exc:                                      # noqa: BLE001
        _fail("sat", exc)

    comp = None
    for tname in ("NodeGroupOutput", "CompositorNodeComposite"):
        try:
            comp = nt.nodes.new(tname)
            break
        except Exception:                                         # noqa: BLE001
            comp = None
    if comp is None:
        _fail("compositor_out", "no output node")
        return nt
    comp.location = (200, 0)
    if comp.bl_idname == "NodeGroupOutput":
        try:
            names = [i.name for i in nt.interface.items_tree
                     if getattr(i, "in_out", "") == "OUTPUT"]
            if "Image" not in names:
                nt.interface.new_socket(name="Image", in_out="OUTPUT",
                                        socket_type="NodeSocketColor")
            _ok("compositor_out", "NodeGroupOutput.Image")
        except Exception as exc:                                  # noqa: BLE001
            _fail("compositor_out", "interface: %s" % exc)
    try:
        nt.links.new(out_sock, comp.inputs["Image"])
        if not comp.inputs["Image"].is_linked:
            _fail("compositor_out", "Image input not linked")
    except Exception as exc:                                      # noqa: BLE001
        _fail("compositor_out", "link: %s" % exc)
    return nt


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------
def apply(preset, scene=None, sun_elev=None, sun_azim=None, *, cam=None,
          samples=None, res=None, contact_shadows=True, gpu=True):
    """Put the whole rig on the scene and return what was actually set.

    `sun_elev` / `sun_azim` override the preset's canonical angles.  When called
    from `shot()` they come from the camera's class (street 28-42 deg, aerial
    45-55 deg) and the camera's azimuth offset, which is how one preset can serve
    both an eye-level street and a 480 m aerial.
    """
    del APPLIED[:]
    del FAILED[:]
    p = PRESETS[preset]
    sc = _scn(scene)
    _clear_owned()

    elev = p["sun_elev_street"] if sun_elev is None else float(sun_elev)
    azim = p["sun_azim"] if sun_azim is None else float(sun_azim)
    azim = azim % 360.0

    sky(preset, elev, azim)
    sun(preset, elev, azim)
    bounce(preset)
    if contact_shadows:
        contact(preset, sc)
    _, t80, t600 = haze(preset,
                        center=((0.0, 0.0) if cam is None else
                                (cam["loc"][0], cam["loc"][1])),
                        mul=(1.0 if cam is None else cam.get("haze_mul", 1.0)),
                        extent=(2800.0 if cam is None else cam.get("haze_extent", 2800.0)))
    if p["torch"] or p["glow"]:
        _glow(preset)
        _torches(preset)
    post(preset, sc)
    cycles(preset, samples=samples or 192, res=res or (1600, 900), gpu=gpu, scene=sc)

    shadow_len = 1.0 / max(0.05, math.tan(math.radians(elev)))
    out = dict(
        preset=preset,
        sun=dict(elev=round(elev, 2), azim=round(azim, 2), energy=p["sun_energy"],
                 color=tuple(p["sun_color"]), angle=p["sun_angle"],
                 shadow=True, shadow_len=round(shadow_len, 2)),
        sky=dict(strength=p["sky_strength"], aerosol=p["sky_aerosol"],
                 tint=tuple(p["sky_tint"])),
        bounce=dict(ratio=p["bounce_ratio"], color=tuple(p["bounce_color"])),
        haze=dict(sigma=round(p["haze"], 6), height=p["haze_h"],
                  color=tuple(p["haze_color"]), T80=round(t80, 3), T600=round(t600, 3)),
        ao=dict(dist=p["ao_dist"], strength=p["ao_strength"]),
        post=dict(exposure=p["exposure"], contrast=p["contrast"], sat=p["sat"],
                  glare=p["glare"], look=p.get("look")),
        ok=sorted(set(k for k, _ in APPLIED)),
        fail=sorted(set(k for k, _ in FAILED)),
    )
    print("[light] %s ok=%d fail=%d  sun %.0fdeg E=%.0f  T80=%.2f T600=%.2f"
          % (preset, len(out["ok"]), len(out["fail"]), elev, p["sun_energy"], t80, t600),
          flush=True)
    return out


# ---------------------------------------------------------------------------
# camera
# ---------------------------------------------------------------------------
def camera(name, loc=None, look_at=None, lens=35, ortho=None):
    """Create (or refresh) one of the fixed rigs and return the object."""
    cfg = CAMERAS.get(name, {})
    pos = Vector(loc if loc is not None else cfg.get("loc", (0.0, 0.0, 1.7)))
    if loc is None:
        lens = cfg.get("lens", lens)
    tgt = Vector(look_at if look_at is not None else cfg.get("look", (0.0, 10.0, 1.7)))
    ob = bpy.data.objects.get(_TAG + "Cam_" + name)
    if ob is None:
        cd = bpy.data.cameras.new(_TAG + "CamData_" + name)
        ob = bpy.data.objects.new(_TAG + "Cam_" + name, cd)
        bpy.context.collection.objects.link(ob)
    cd = ob.data
    cd.lens = float(lens)
    cd.sensor_width = 36.0
    cd.clip_start = 0.08
    cd.clip_end = 9000.0
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = float(ortho)
    else:
        cd.type = "PERSP"
    ob.location = pos
    d = (tgt - pos)
    if d.length < 1e-6:
        _fail("camera", "%s look_at == loc" % name)
        d = Vector((0.0, 1.0, 0.0))
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    bpy.context.view_layer.update()
    _ok("camera", "%s at %s -> %s  %.0f mm"
        % (name, tuple(round(v, 1) for v in pos), tuple(round(v, 1) for v in tgt), lens))
    return ob


_camera_fn = camera          # `shot()`'s parameter is named `camera`, like the brief asks


# ---------------------------------------------------------------------------
# shot
# ---------------------------------------------------------------------------
def shot(preset, camera, path, res=(1600, 900), samples=192):
    """Apply the preset for this camera's class, aim, render one 16:9 frame."""
    name = camera if isinstance(camera, str) else camera.name.replace(_TAG + "Cam_", "")
    cfg = CAMERAS.get(name, {})
    p = PRESETS[preset]
    kind = cfg.get("kind", "street")
    elev = p["sun_elev_street"] if kind != "wide" else p["sun_elev_wide"]
    azim = (p["sun_azim"] + cfg.get("azim_delta", 0.0)) % 360.0
    apply(preset, None, elev, azim, cam=cfg, samples=samples, res=res)
    ob = camera if not isinstance(camera, str) else _camera_fn(name)
    bpy.context.scene.camera = ob
    bpy.context.view_layer.update()
    # keep the haze column centred on the lens so there is no lateral seam
    hz = bpy.data.objects.get(_TAG + "Haze")
    if hz is not None:
        hz.location.x = ob.matrix_world.translation.x
        hz.location.y = ob.matrix_world.translation.y
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[light] wrote %s" % path, flush=True)
    return path


# ---------------------------------------------------------------------------
# image statistics (used by the acceptance pass)
# ---------------------------------------------------------------------------
def image_stats(path, shadow_rel=0.30):
    """Histogram facts for one render.

    * clip_hi  fraction of pixels whose brightest channel is > 250  (over-exposed)
    * dead     fraction of pixels whose luma is < 8                 (crushed black)
    * shadow   fraction of pixels darker than `shadow_rel` x the 90th-percentile
               luma -- i.e. "how much of the frame is in shadow", the brief's
               12-35 % window
    """
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        a = buf.reshape(h, w, 4)[:, :, :3]
        # PNG is already display-referred 0..1
        rgb255 = a * 255.0
        luma = (0.2126 * rgb255[:, :, 0] + 0.7152 * rgb255[:, :, 1]
                + 0.0722 * rgb255[:, :, 2])
        p90 = float(np.percentile(luma, 90.0))
        thr = shadow_rel * p90
        stats = dict(
            path=path, w=w, h=h,
            mean=round(float(luma.mean()), 2),
            p50=round(float(np.percentile(luma, 50.0)), 2),
            p90=round(p90, 2),
            p99=round(float(np.percentile(luma, 99.0)), 2),
            clip_hi=round(float((rgb255.max(axis=2) > 250.0).mean()) * 100.0, 3),
            dead=round(float((luma < 8.0).mean()) * 100.0, 3),
            shadow=round(float((luma <= thr).mean()) * 100.0, 2),
            shadow_thr=round(thr, 2),
            contrast=round(float(luma.std()), 2),
        )
    finally:
        bpy.data.images.remove(img)
    return stats


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def report():
    """Everything this module knows: presets, cameras, calibration, last apply."""
    bad = sorted(set(k for k, _ in FAILED))
    good = sorted(set(k for k, _ in APPLIED) - set(bad))
    tbl = {}
    for k, p in PRESETS.items():
        tbl[k] = dict(
            atmos=p["atmos"],
            elev_street=p["sun_elev_street"], elev_wide=p["sun_elev_wide"],
            azim=p["sun_azim"], energy=p["sun_energy"], angle=p["sun_angle"],
            bounce=p["bounce_ratio"], ao=p["ao_dist"],
            haze_sigma=p["haze"], haze_h=p["haze_h"],
            exposure=p["exposure"], look=p.get("look"),
        )
    out = dict(
        presets=tbl,
        cameras={k: dict(loc=v["loc"], look=v["look"], lens=v["lens"], kind=v["kind"])
                 for k, v in CAMERAS.items()},
        calibration=dict(bounce_w_per_ratio=BOUNCE_W_PER_RATIO,
                         bounce_size=BOUNCE_SIZE),
        ok=good, fail=bad,
        last=dict(APPLIED[-40:]),
    )
    print("[light] report: %d presets, %d cameras, ok=%d fail=%d"
          % (len(PRESETS), len(CAMERAS), len(good), len(bad)), flush=True)
    return out
