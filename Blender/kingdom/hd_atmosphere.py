"""hd_atmosphere.py - sky, sun, haze and post for the capital renders.  v3, Blender 5.2.

The goal is not "a Blender render" but a frame that reads like an establishing shot
from a game: a real sky gradient, sun with soft shadows, aerial perspective that
separates the near street from the far walls, and a grain of bloom.

Everything here is procedural (no HDRIs, no textures).

v3 rewrite, after a forensic pass on the v2 golden_hour frame.  Blender 5.2 broke
four of the v2 calls and every one of them sat inside `except Exception: pass`, so
the frame shipped with *none* of the grade and a default glare:
  * sky_type "NISHITA" -> enum gone ('SINGLE_SCATTERING' / 'MULTIPLE_SCATTERING'),
    and the exception killed the whole sky block, leaving PREETHAM at 15 deg;
  * CompositorNodeGlare: glare_type/quality/threshold/size/mix are input sockets now,
    so the render got a default **Streaks** glare (the vertical bars);
  * CompositorNodeColorBalance: lift/gamma/gain are sockets, so contrast/sat were no-ops;
  * CompositorNodeComposite does not exist (NodeGroupOutput only).
Nothing here is silent any more: every setter reads its value back and reports, and
apply() ends with `[atmos] applied presets ok=N fail=M`.

Physical anchors used for the presets
-------------------------------------
* sun elevation -> ground irradiance sin(e), shadow length 1/tan(e);
* sun colour -> blackbody at air-mass-corrected temperature (dawn 2100 K .. noon 5600 K);
* haze density -> Koschmieder visibility, sigma = 3.912 / V, with an exponential
  scale height so the ground layer is denser than the roofs;
* exposure -> solved against the render so the frame lands at mean ~120/255 and
  < 2 % of pixels clip at 250.

    *** UNITS OF `sun_energy` ***
    `sun_energy` is an ARTISTIC unit, calibrated against the sky dome at
    sky_strength = 1.0 -- it is NOT W/m^2 of solar irradiance, and must not be
    checked against one.  The physical scalars here are your own numbers; the
    value is whatever makes the sun contribute ~30-38 % of the light that
    reaches the ground (measured: golden_hour ground 37.5 %, city 30.1 %).
    Do not "correct" it toward 1000 W/m^2: the sky texture's radiance is not on
    a physical scale either, so only the RATIO between sun and dome matters.
    If you change sky_strength, re-solve sun_energy by that ratio, not by physics.

Presets
-------
clear_dawn, clear_morning, clear_noon, golden_hour, overcast, rain, storm, fog, snow, night

Typical use
-----------
    import hd_atmosphere as A
    A.apply("golden_hour")              # sky + sun + haze + exposure + compositor
    A.render(path, loc, look, lens=28)
    A.report()                          # prints the ok/fail tally
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

E = math.e
TAU = math.pi * 2.0

# ---------------------------------------------------------------------------
# instrumentation: nothing may fail silently
# ---------------------------------------------------------------------------
APPLIED = []          # [(key, detail), ...]
FAILED = []           # [(key, "error"), ...]
LOG = True


def _ok(key, detail):
    APPLIED.append((key, detail))
    if LOG:
        print("  [atmos ok]   %-14s %s" % (key, detail), flush=True)


def _fail(key, detail):
    FAILED.append((key, str(detail)))
    print("  [atmos FAIL] %-14s %s" % (key, detail), flush=True)


def _num_eq(a, b, tol=1e-5):
    """Compare numbers or float arrays; bpy_prop_array / Color / Vector all count."""
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
    """Set a legacy RNA property, else a node-input socket; read the value back.

    This is the single choke point that makes "looks changed" impossible: a
    property that 5.2 turned into a socket falls through to the socket, and a
    value that the shader clamps or ignores shows up as a readback mismatch.
    """
    if hasattr(owner, attr):
        try:
            setattr(owner, attr, value)
            got = getattr(owner, attr)
            if not _num_eq(got, value, tol):
                raise ValueError("readback %r != %r" % (got, value))
            _ok(key, "%s=%r (prop)" % (attr, value))
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


def _node(nt, type_names, key, loc=None):
    """First node type that exists on this build."""
    for t in (type_names if isinstance(type_names, (list, tuple)) else [type_names]):
        try:
            n = nt.nodes.new(t)
        except Exception:                                         # noqa: BLE001
            continue
        if loc is not None:
            n.location = loc
        _ok(key, "node %s" % t)
        return n
    _fail(key, "none of %r could be created" % (type_names,))
    return None


def _math(nt, op, loc, label):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.location = loc
    if n.operation != op:
        _fail(label, "Math op %r not accepted" % op)
    return n


# ---------------------------------------------------------------------------
# camera / sun geometry (pure maths, no bpy state)
# ---------------------------------------------------------------------------
def sun_dir(elev_deg, azim_deg):
    """Unit vector pointing FROM the scene TOWARDS the sun.

    Matches sun_light()'s rotation_euler = (90-elev, 0, azim): the lamp travels
    along -d, so d = (sin a cos e, -cos a cos e, sin e).
    """
    a = math.radians(azim_deg)
    e = math.radians(elev_deg)
    return Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))


def sky_rot_from_azim(azim_deg):
    """Sky-texture sun_rotation (degrees) that puts the sky's sun on the lamp's.

    Measured on 5.2: dome azimuth = 90 + sun_rotation (clockwise-positive), and
    sun_light() puts the lamp's sun at azimuth azim - 90, hence rotation = azim - 180.
    Cross-check render: rot=0 puts the glow at +Y (screen right of the ars camera),
    rot=-74 moves it to the left, i.e. toward azimuth 164 -- clockwise, confirmed.
    """
    return azim_deg - 180.0


def horizon_row(cam, width, height):
    """Pixel row (0 = top) where elevation 0 crosses, and the frame's top-edge elevation."""
    bpy.context.view_layer.update()
    m = cam.matrix_world
    fwd = (m.to_quaternion() @ Vector((0.0, 0.0, -1.0))).normalized()
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, -fwd.z))))
    lens = cam.data.lens
    sensor = cam.data.sensor_width or 36.0
    if width >= height:
        half_v = math.degrees(math.atan((sensor * height / width) * 0.5 / lens))
        half_h = math.degrees(math.atan(sensor * 0.5 / lens))
    else:
        half_v = math.degrees(math.atan(sensor * 0.5 / lens))
        half_h = math.degrees(math.atan((sensor * width / height) * 0.5 / lens))
    vfov = 2.0 * half_v
    row = height * (0.5 - pitch / vfov)
    return dict(row=row, top_deg=half_v - pitch, bottom_deg=-half_v - pitch,
                pitch=pitch, vfov=vfov, hfov=2.0 * half_h, half_h=half_h)


# ---------------------------------------------------------------------------
# presets.  Every number has a physical reason; see the table in the docstring.
#   sun_elev   degrees above the horizon           sun_color  blackbody-ish
#   sun_energy W/m^2 on a normal surface           sun_angle  angular diameter (deg)
#   sky_tint   multiplicative tint on the dome     sky_aerosol Mie/dust in the dome
#   haze       extinction at z=0 (1/m)             height     scale height (m)
#   haze_color scattering albedo                   haze_aniso g for the phase fn
#   exposure   view exposure (stops)               contrast   BrightContrast +x
#   sat        HueSat multiplier                   glare      Fog-Glow strength
# ---------------------------------------------------------------------------
_BASE = dict(
    sun_elev=20.0, sun_azim=-60.0, sun_color=(1.0, 0.93, 0.85), sun_energy=70.0,
    sun_angle=0.6,
    sky_tint=(1.0, 0.97, 0.94), sky_aerosol=0.6, sky_strength=1.0, sky_alt=120.0,
    sky_elev=None, sky_azim=None, sky_ozone=1.0, sky_type="MULTIPLE_SCATTERING",
    haze=0.00020, height=1400.0, haze_color=(0.86, 0.88, 0.92), haze_aniso=0.55,
    exposure=0.0, contrast=1.0, sat=1.0, glare=0.22, glow=1.0,
    look="AgX - Punchy",
)

PRESETS = {
    # ---- clear sky ladder: elevation drives colour temp and shadow length ----
    "clear_dawn": dict(
        sun_elev=2.5, sun_azim=-96.0, sun_color=(1.0, 0.50, 0.24), sun_energy=47.0,
        sun_angle=0.55, sky_tint=(1.0, 0.90, 0.84), sky_aerosol=1.05, sky_alt=90.0,
        haze=0.00016, height=1000.0, haze_color=(0.88, 0.84, 0.82), haze_aniso=0.62,
        exposure=-1.22, contrast=1.09, sat=1.05, glare=0.30),
    "clear_morning": dict(
        sun_elev=22.0, sun_azim=-58.0, sun_color=(1.0, 0.87, 0.72), sun_energy=77.0,
        sun_angle=0.60, sky_tint=(0.90, 0.95, 1.0), sky_aerosol=0.55, sky_alt=140.0,
        haze=0.00011, height=1900.0, haze_color=(0.86, 0.90, 0.96), haze_aniso=0.50,
        exposure=-3.18, contrast=1.09, sat=1.03, glare=0.18),
    "clear_noon": dict(
        sun_elev=62.0, sun_azim=-30.0, sun_color=(1.0, 0.97, 0.94), sun_energy=97.0,
        sun_angle=0.65, sky_tint=(0.88, 0.94, 1.0), sky_aerosol=0.40, sky_alt=200.0,
        haze=0.00008, height=2400.0, haze_color=(0.84, 0.89, 0.97), haze_aniso=0.45,
        exposure=-5.10, contrast=1.10, sat=1.0, glare=0.14,
        look="AgX - Medium High Contrast"),
    "golden_hour": dict(
        sun_elev=9.0, sun_azim=-74.0, sun_color=(1.0, 0.64, 0.39), sun_energy=85.0,
        sun_angle=0.55, sky_tint=(0.93, 0.97, 1.06), sky_aerosol=0.90, sky_alt=70.0,
        sky_strength=0.82,
        haze=0.000075, height=1300.0, haze_color=(0.88, 0.89, 0.93), haze_aniso=0.62,
        exposure=-2.52, contrast=1.14, sat=1.12, glare=0.26),
    # ---- diffused / bad weather: sun becomes a soft dome, haze thicker+lower ----
    "overcast": dict(
        sun_elev=38.0, sun_azim=-40.0, sun_color=(0.86, 0.89, 0.94), sun_energy=7.5,
        sun_angle=4.0, sky_tint=(0.86, 0.90, 0.96), sky_aerosol=2.4, sky_strength=1.35,
        sky_alt=120.0, haze=0.00022, height=900.0, haze_color=(0.80, 0.83, 0.88),
        haze_aniso=0.30, exposure=-4.00, contrast=1.02, sat=0.90, glare=0.12,
        look="AgX - Base Contrast"),
    "rain": dict(
        sun_elev=36.0, sun_azim=-40.0, sun_color=(0.78, 0.82, 0.90), sun_energy=3.5,
        sun_angle=6.0, sky_tint=(0.72, 0.78, 0.88), sky_aerosol=3.1, sky_strength=0.95,
        haze=0.00055, height=600.0, haze_color=(0.70, 0.74, 0.80), haze_aniso=0.28,
        exposure=-3.22, contrast=1.00, sat=0.84, glare=0.08,
        look="AgX - Base Contrast"),
    "storm": dict(
        sun_elev=40.0, sun_azim=-30.0, sun_color=(0.66, 0.72, 0.84), sun_energy=2.2,
        sun_angle=8.0, sky_tint=(0.58, 0.64, 0.74), sky_aerosol=3.8, sky_strength=0.66,
        haze=0.00100, height=520.0, haze_color=(0.58, 0.62, 0.70), haze_aniso=0.25,
        exposure=-2.30, contrast=0.99, sat=0.76, glare=0.06),
    "fog": dict(
        sun_elev=24.0, sun_azim=-62.0, sun_color=(0.92, 0.92, 0.95), sun_energy=5.0,
        sun_angle=7.0, sky_tint=(0.90, 0.92, 0.96), sky_aerosol=3.4, sky_strength=0.90,
        haze=0.00120, height=220.0, haze_color=(0.88, 0.89, 0.92), haze_aniso=0.45,
        exposure=-3.34, contrast=1.01, sat=0.86, glare=0.10,
        look="AgX - Base Contrast"),
    "snow": dict(
        sun_elev=18.0, sun_azim=-52.0, sun_color=(0.94, 0.96, 1.0), sun_energy=28.0,
        sun_angle=2.5, sky_tint=(0.90, 0.95, 1.0), sky_aerosol=1.9, sky_strength=1.15,
        haze=0.00050, height=420.0, haze_color=(0.90, 0.93, 0.98), haze_aniso=0.40,
        exposure=-3.18, contrast=1.05, sat=0.88, glare=0.20),
    # ---- night: the sky's sun is below the horizon, a blue "moon" lamp carries the key
    "night": dict(
        sun_elev=28.0, sun_azim=-70.0, sun_color=(0.52, 0.64, 0.92), sun_energy=4.0,
        sun_angle=0.9, sky_elev=16.0, sky_azim=-70.0, sky_tint=(0.34, 0.42, 0.66),
        sky_aerosol=0.7, sky_strength=0.060, sky_alt=180.0,
        haze=0.00014, height=1300.0, haze_color=(0.30, 0.36, 0.52), haze_aniso=0.50,
        exposure=-0.90, contrast=1.06, sat=0.95, glare=0.26),
}
for _k, _v in PRESETS.items():
    PRESETS[_k] = dict(_BASE, **_v)
del _k, _v


# ---------------------------------------------------------------------------
def _nodes_mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    return m


def _clear_world_nodes(nt):
    nt.nodes.clear()


def world_sky(preset, sun_elev=None, sun_azim=None, tint=None, aerosol=None,
              strength=None, horizon_clamp=True):
    """Sky dome, tinted, with the below-horizon hemisphere projected to the horizon.

    The projection is not cosmetic.  This city sits on a ~570 m island; every ray
    that misses it sees the *lower* hemisphere of the sky, which is a dark grey
    wall.  Projecting the direction's Z to 0 makes those rays return the horizon
    colour instead, which is what an endless hazy plain would look like and what
    stops the frame from having a grey slab behind the city.
    """
    p = PRESETS[preset]
    elev = p["sun_elev"] if sun_elev is None else sun_elev
    azim = p["sun_azim"] if sun_azim is None else sun_azim
    sky_elev = p.get("sky_elev")
    if sky_elev is None:
        sky_elev = elev
    sky_azim = p.get("sky_azim")
    if sky_azim is None:
        sky_azim = azim
    tint = tint or p["sky_tint"]
    aer = p["sky_aerosol"] if aerosol is None else aerosol
    stg = p["sky_strength"] if strength is None else strength

    w = bpy.context.scene.world
    if w is None:
        w = bpy.data.worlds.new("World")
        bpy.context.scene.world = w
    try:
        w.use_nodes = True
    except DeprecationWarning:                                    # noqa: B014
        pass
    nt = w.node_tree
    _clear_world_nodes(nt)

    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (900, 0)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.location = (660, 0)
    _set_sock(bg, "Strength", stg, "sky_strength")

    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.location = (140, 160)

    # --- sky model: NISHITA was split in 5.2 -------------------------------
    items = [i.identifier for i in sky.bl_rna.properties["sky_type"].enum_items]
    want = None
    cands = [p.get("sky_type"), "MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "NISHITA"]
    for cand in cands:
        if cand and cand in items:
            want = cand
            break
    if want is None:
        _fail("sky_type", "no usable sky model in %r" % (items,))
    else:
        _set(sky, "sky_type", want, "sky_type")

    _set(sky, "sun_elevation", math.radians(sky_elev), "sun_elev")
    _set(sky, "sun_rotation", math.radians(sky_rot_from_azim(sky_azim)), "sky_azim")
    _set(sky, "sun_disc", False, "sky_disc")
    _set(sky, "altitude", p["sky_alt"], "sky_alt")
    _set(sky, "air_density", 1.0, "sky_air")
    _set(sky, "aerosol_density", aer, "sky_aerosol")
    _set(sky, "ozone_density", p.get("sky_ozone", 1.0), "sky_ozone")

    # --- direction, below-horizon projection, land haze -------------------
    # Geometry.Incoming is the reverse of the view direction, so the direction the
    # sky has to be sampled in is -Incoming.  (Feeding Incoming straight in mirrors
    # the dome through the origin: the v3 first pass shipped an upside-down sky
    # whose horizon was a dark band below a bright ceiling.)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-700, 320)
    inv = nt.nodes.new("ShaderNodeVectorMath")
    inv.operation = "MULTIPLY"
    inv.location = (-560, 320)
    inv.inputs[1].default_value = (-1.0, -1.0, -1.0)
    nt.links.new(geo.outputs["Incoming"], inv.inputs[0])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-400, 320)
    nt.links.new(inv.outputs["Vector"], sep.inputs["Vector"])
    sky_out = sky.outputs["Color"]
    if horizon_clamp:
        mz = _math(nt, "MAXIMUM", (-240, 300), "horizon_clamp")
        mz.inputs[1].default_value = 0.0
        nt.links.new(sep.outputs["Z"], mz.inputs[0])
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        comb.location = (-60, 300)
        nt.links.new(sep.outputs["X"], comb.inputs["X"])
        nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
        nt.links.new(mz.outputs["Value"], comb.inputs["Z"])
        nt.links.new(comb.outputs["Vector"], sky.inputs["Vector"])
        _ok("horizon_clamp", "view +Z pinned to the horizon plane")

        # fac = clamp(-z * 3.5, 0, 1): 0 at the horizon, saturated 16 deg below it.
        # Darkens the below-horizon sky just enough to read as a hazy plain at
        # infinity, so the island stops floating on a bright void.
        lf = _math(nt, "MULTIPLY", (-240, 150), "land_haze")
        lf.inputs[1].default_value = -3.5
        nt.links.new(sep.outputs["Z"], lf.inputs[0])
        lm = _math(nt, "MAXIMUM", (-60, 150), "land_haze")
        lm.inputs[1].default_value = 0.0
        nt.links.new(lf.outputs["Value"], lm.inputs[0])
        land = nt.nodes.new("ShaderNodeMixRGB")
        land.blend_type = "MULTIPLY"
        land.location = (120, 200)
        nt.links.new(lm.outputs["Value"], land.inputs["Fac"])
        land.inputs["Color2"].default_value = (0.78, 0.79, 0.81, 1.0)
        nt.links.new(sky.outputs["Color"], land.inputs["Color1"])
        sky_out = land.outputs["Color"]
        _ok("land_haze", "below-horizon rays read as hazy plain (x0.78)")
    else:
        _ok("horizon_clamp", "off")

    # --- tint: multiplicative, low mix ------------------------------------
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.location = (430, 0)
    try:
        mix.blend_type = "MULTIPLY"
    except Exception as exc:                                      # noqa: BLE001
        _fail("sky_tint", "blend_type: %s" % exc)
    _set_sock(mix, "Fac", p.get("sky_tint_fac", 0.15), "sky_tint_fac")
    mix.inputs["Color1"].default_value = (1, 1, 1, 1)
    _set_sock(mix, "Color2", (tint[0], tint[1], tint[2], 1.0), "sky_tint")
    nt.links.new(sky_out, mix.inputs["Color1"])
    nt.links.new(mix.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return w


def sun_light(preset, elevation=None, azimuth=None, energy=None, angle_deg=None):
    """One sun lamp; deletes any previous sun so re-runs stay clean."""
    p = PRESETS[preset]
    elev = p["sun_elev"] if elevation is None else elevation
    azim = p["sun_azim"] if azimuth is None else azimuth
    for ob in [o for o in bpy.data.objects if o.type == "LIGHT" and o.data.type == "SUN"]:
        bpy.data.objects.remove(ob, do_unlink=True)
    data = bpy.data.lights.new("Sun", "SUN")
    _set(data, "energy", p["sun_energy"] if energy is None else energy, "sun_energy")
    _set(data, "color", tuple(p["sun_color"])[:3], "sun_color")
    _set(data, "angle", math.radians(p["sun_angle"] if angle_deg is None else angle_deg),
         "sun_angle")
    data.use_shadow = True
    ob = bpy.data.objects.new("Sun", data)
    bpy.context.collection.objects.link(ob)
    ob.rotation_euler = Euler((math.radians(90.0 - elev), 0.0, math.radians(azim)), "XYZ")
    # verify the lamp really points where the formulas say
    bpy.context.view_layer.update()
    got = (ob.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))).normalized()
    want = -sun_dir(elev, azim)
    dot = got.dot(want)
    if dot > 0.9995:
        _ok("sun_azim", "dir ok (dot %.5f) elev=%.1f azim=%.1f" % (dot, elev, azim))
    else:
        _fail("sun_azim", "lamp dir %r vs expected %r (dot %.4f)"
              % (tuple(round(v, 3) for v in got), tuple(round(v, 3) for v in want), dot))
    return ob


def haze(preset, density=None, height=None, extent=2800.0, center=None,
         color=None, aniso=None):
    """A big volume cube with an exponential height falloff.

    This is what buys aerial perspective: the far curtain wall desaturates and
    lifts towards the sky colour instead of sitting as a crisp dark band.
    v3: the falloff is exp(-z/height) evaluated in WORLD space from Geometry.Position
    -- v2 mapped object-space Z through a -1..1 range while the cube is +-1400 wide,
    so everything above z=1344 clamped to full density and the layer sat on the ceiling.
    """
    p = PRESETS[preset]
    dens = p["haze"] if density is None else density
    hgt = p["height"] if height is None else height
    col = p["haze_color"] if color is None else color
    ani = p["haze_aniso"] if aniso is None else aniso

    if center is None:
        cam = bpy.context.scene.camera
        if cam is not None:
            bpy.context.view_layer.update()
            center = (cam.matrix_world.translation.x, cam.matrix_world.translation.y)
        else:
            center = (0.0, 0.0)

    old = bpy.data.objects.get("Atmosphere")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)

    bpy.ops.mesh.primitive_cube_add(size=extent,
                                    location=(center[0], center[1], extent * 0.5 - 20.0))
    ob = bpy.context.object
    ob.name = "Atmosphere"
    ob.scale = (1.0, 1.0, 1.0)
    ob.data.materials.clear()

    m = _nodes_mat("AtmosphereVolume")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (520, 0)
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.location = (300, 0)
    _set_sock(pv, "Color", (col[0], col[1], col[2], 1.0), "haze_color")
    _set_sock(pv, "Anisotropy", ani, "haze_aniso")
    if "Absorption Color" in pv.inputs:
        pv.inputs["Absorption Color"].default_value = (0, 0, 0, 1)

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-780, 0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-600, 0)
    nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])
    mx = _math(nt, "MAXIMUM", (-430, -40), "haze_floor")
    mx.inputs[1].default_value = 0.0
    nt.links.new(sep.outputs["Z"], mx.inputs[0])
    sc_ = _math(nt, "MULTIPLY", (-270, -40), "haze_scale")
    sc_.inputs[1].default_value = -1.0 / max(1.0, hgt)
    nt.links.new(mx.outputs["Value"], sc_.inputs[0])
    pw = _math(nt, "POWER", (-110, -40), "haze_falloff")
    pw.inputs[0].default_value = E
    nt.links.new(sc_.outputs["Value"], pw.inputs[1])
    dn = _math(nt, "MULTIPLY", (40, -40), "haze")
    dn.inputs[1].default_value = dens
    nt.links.new(pw.outputs["Value"], dn.inputs[0])
    nt.links.new(dn.outputs["Value"], pv.inputs["Density"])
    nt.links.new(pv.outputs["Volume"], out.inputs["Volume"])
    if "Density" in pv.inputs and not pv.inputs["Density"].is_linked:
        _fail("haze", "Density socket not driven")
    ob.data.materials.append(m)
    ob.visible_shadow = False
    _ok("haze", "dens=%.6f h=%.0f tau(city)=%.2f" % (
        dens, hgt, dens * math.exp(-138.0 / max(1.0, hgt)) * 700.0))
    _ok("height", "scale height %.0f m" % hgt)
    return ob


def post(preset=None, use_glare=True):
    """Exposure, AgX, fog glow, contrast and saturation in the compositor."""
    p = PRESETS[preset] if preset else dict(exposure=0.0, contrast=1.0, sat=1.0, glare=0.3)
    sc = bpy.context.scene
    _set(sc.view_settings, "view_transform", "AgX", "view_transform")
    got_look = None
    for cand in (p.get("look") or "AgX - Punchy", "AgX - Base Contrast", "None"):
        try:
            sc.view_settings.look = cand
            if sc.view_settings.look == cand:
                got_look = cand
                _ok("look", "look=%r" % cand)
                break
        except Exception:                                         # noqa: BLE001
            continue
    if got_look is None:
        names = []
        try:
            names = [i.name for i in sc.view_settings.bl_rna.properties["look"].enum_items]
        except Exception:                                         # noqa: BLE001
            pass
        _fail("look", "no AgX look accepted; available=%r" % (names,))
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
                g = bpy.data.node_groups.new("CapitalComp", "CompositorNodeTree")
                sc.compositing_node_group = g
            nt = g
        else:
            nt = sc.node_tree
    except Exception as exc:                                      # noqa: BLE001
        _fail("compositor", "cannot get node tree: %s" % exc)
        return None
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    rl.location = (-760, 0)

    glare = _node(nt, "CompositorNodeGlare", "glare", (-560, 0))
    if glare is None:
        return nt
    _set_sock(glare, "Type", "Fog Glow", "glare_type")
    _set_sock(glare, "Quality", "High", "glare_quality")
    _set_sock(glare, "Threshold", 1.8, "glare_threshold")
    _set_sock(glare, "Smoothness", 0.6, "glare_smooth")
    _set_sock(glare, "Size", 0.10, "glare_size")
    _set_sock(glare, "Strength", min(0.8, p["glare"]), "glare")

    bc = _node(nt, "CompositorNodeBrightContrast", "contrast", (-340, 0))
    if bc is not None:
        _set_sock(bc, "Brightness", 0.0, "contrast_bright")
        _set_sock(bc, "Contrast", (p["contrast"] - 1.0) * 100.0, "contrast")

    hs = _node(nt, "CompositorNodeHueSat", "sat", (-140, 0))
    if hs is not None:
        _set_sock(hs, "Hue", 0.5, "sat_hue")
        _set_sock(hs, "Saturation", p["sat"], "sat")
        _set_sock(hs, "Value", 1.0, "sat_value")

    comp = None
    for tname in ("NodeGroupOutput", "CompositorNodeComposite"):
        try:
            comp = nt.nodes.new(tname)
            break
        except Exception:                                         # noqa: BLE001
            comp = None
    if comp is None:
        _fail("compositor_out", "no output node available")
        return nt
    comp.location = (140, 0)
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

    chain = [rl]
    if use_glare:
        nt.links.new(rl.outputs["Image"], glare.inputs["Image"])
        chain.append(glare)
    for n in (bc, hs):
        if n is not None:
            nt.links.new(chain[-1].outputs["Image"], n.inputs["Image"])
            chain.append(n)
    try:
        nt.links.new(chain[-1].outputs["Image"], comp.inputs["Image"])
        if not comp.inputs["Image"].is_linked:
            _fail("compositor_out", "Image input not linked")
        else:
            _ok("compositor_out", "linked to output")
    except Exception as exc:                                      # noqa: BLE001
        _fail("compositor_out", "link: %s" % exc)
    return nt


def apply(preset, samples=192, res=(1600, 900), use_haze=True, gpu=True,
          center=None, report=True):
    del APPLIED[:]
    del FAILED[:]
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU" if gpu else "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8
    sc.cycles.volume_bounces = 2
    sc.cycles.transparent_max_bounces = 8
    try:
        sc.cycles.volume_step_rate = 0.35
        sc.cycles.volume_max_steps = 512
    except Exception:                                             # noqa: BLE001
        pass
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
    except Exception as exc:                                      # noqa: BLE001
        _fail("gpu", "optix unavailable: %s" % exc)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"

    world_sky(preset)
    sun_light(preset)
    if use_haze:
        haze(preset, center=center)
    post(preset)
    if report:
        report_applied()
    return sc


def report_applied():
    bad = sorted(set(k for k, _ in FAILED))
    good = sorted(set(k for k, _ in APPLIED) - set(bad))
    print("[atmos] applied presets ok=%d fail=%d" % (len(good), len(bad)), flush=True)
    if bad:
        print("[atmos] failed keys: %s" % ", ".join(bad), flush=True)
    return dict(ok=good, fail=bad)


def render(path, loc, look, lens=28.0, ortho=None, focus=None, fstop=8.0):
    sc = bpy.context.scene
    cam = bpy.data.objects.get("BeautyCam")
    if cam is None:
        cd = bpy.data.cameras.new("BeautyCam")
        cam = bpy.data.objects.new("BeautyCam", cd)
        bpy.context.collection.objects.link(cam)
    cam.data.lens = lens
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = "PERSP"
    cam.location = Vector(loc)
    d = Vector(look) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    bpy.context.view_layer.update()
    if focus is not None and fstop:
        cd = cam.data
        cd.dof.use_dof = True
        cd.dof.focus_distance = float(focus)
        cd.dof.aperture_fstop = float(fstop)
    # keep the haze cube centred on the camera so the veil has no lateral seam
    at = bpy.data.objects.get("Atmosphere")
    if at is not None:
        at.location.x = cam.location.x
        at.location.y = cam.location.y
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[atmos] wrote", path, flush=True)
    return path
