"""hd_weather.py -- one weather state machine, eight skies, Blender <-> Unity.

Why this module exists
----------------------
The capital has a light rig (`hd_light`), a sky (`hd_sky`) and a growing set of
materials, but no *weather*: every shot is a clear morning no matter what the
story wants.  This module adds the missing layer -- a single flat parameter
dict per weather state that drives sky + sun + fog + grade + material response
+ weather geometry, and that can be serialised straight into Unity.

The contract is deliberately boring:

    PRESETS          eight named states, each a dict of renderable numbers
    state(name)      preset + overrides, with the derived values solved
    build(scene...)  the geometry only (rain streaks, flakes, fog banks, ...)
    apply_atmos()    sky + sun + flash + fog volume + grade
    apply_materials() wetness / snow cover on ground, roof and stone
    clear()          remove everything `build` made

Design rules that shaped the code
---------------------------------
* **No Blender particle systems.**  Every particle is a real mesh, built from
  one instantiable base mesh (`asset_mesh("rain_streak")` etc.), because the
  whole point is that the same asset can be instanced by Unity.  The merged
  field objects are just those instances baked into one mesh so the object
  count stays tiny.
* **The ugly numbers are solved, not guessed.**  `fog_density` is optical
  density per metre, and `transmittance()` reports T at 20/50/200/1000/3000 m
  so "20 m visible, 50 m gone" is a measurement, not a vibe.
* **Materials are wrapped, never rebuilt.**  `wet_material()` splices a small
  named node chain in front of the Principled BSDF (base colour, roughness,
  specular, bump strength) and mutates factors on later calls.  It is
  idempotent and it leaves the material's own shader intact, which matters
  because `hd_surface` owns that shader.
* **Only surfaces that can actually get wet / snowed on are touched**: ground,
  roof, stone, bark and foliage.  Glass, cloth, iron and water are skipped.

Usage
-----
    import hd_weather as W

    cfg = W.state("storm")                    # or W.state("rain", wetness=1.0)
    W.build(scene, "storm", MAT, center=(0, 0))   # rain + splash + bolt + ...
    W.apply_atmos(scene, cfg, center=(0, 0))      # sky/sun/fog/grade
    W.apply_materials(MAT, cfg)                   # wet + snow on MAT

    blender -b --factory-startup --python look/weather_lab.py -- all

Units
-----
    sun_energy      W/m^2 in this rig's artistic scale (rig runs 85-105 clear)
    sun_color       linear-ish RGB 0..1 (matches hd_atmosphere.sun_light)
    sun_elev/azim   degrees; elevation above horizon, azimuth 0 = +Y (north)
    fog_density     extinction coefficient sigma, 1/m, at z = 0
    fog_height      exponential scale height, m
    wind            (vx, vy) m/s; rain tilt is solved from it
    exposure        absolute AgX film exposure (scene.view_settings.exposure)
    saturation      1.0 = neutral; absolute, replaces the rig's grade
    wetness         0..1.5  (1.0 = rain-soaked, 1.5 = standing water)
    snow_cover      0..1    (1.0 = full cover; up-facing surfaces first)
    particle_rate   instances of the weather's primary particle
    flash           0..1    peak-lightning exposure frame multiplier
"""
from __future__ import annotations

import json
import math
import os
import random
import sys

try:                                    # the parameter half must run without Blender
    import bpy
    from mathutils import Euler, Matrix, Vector
    IN_BLENDER = True
except ImportError:                     # pragma: no cover - pure-python tooling
    bpy = None
    Euler = Matrix = Vector = None
    IN_BLENDER = False

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

VERSION = "1.1.0"
TAG = "WX_"
ORDER = ("clear", "hazy", "overcast", "rain", "storm", "fog", "snow", "sunshower")

# Every object this module makes starts with TAG, so `clear()` is one prefix
# test and nothing else in the scene can be hurt by it.
_OBJECTS = []          # objects built by the last build() (survives reloads)
_ASSETS = {}           # canonical instancing meshes, built on demand


# =========================================================================== #
#  1.  the parameter space
# =========================================================================== #
# Every key a weather state carries.  A preset only overrides what it needs;
# `state()` fills the rest so downstream code never has to test for a key.
BASE = dict(
    # ---- sun -------------------------------------------------------------
    sun_energy=90.0,
    sun_color=(1.0, 0.86, 0.71),
    sun_elev=34.0,
    sun_azim=112.0,
    sun_angle=1.2,              # angular diameter, deg (bigger = softer shadow)
    # ---- sky (hd_sky preset + its own override dict) ----------------------
    sky_preset="morning_town",
    grade_preset="morning_town",   # hd_light preset used for the compositor ch
    sky=dict(),
    # ---- aerial medium ----------------------------------------------------
    fog_density=0.00010,        # sigma at z=0, 1/m
    fog_height=900.0,           # exponential scale height, m
    fog_color=(0.60, 0.73, 0.92),
    fog_aniso=0.55,
    fog_noise=0.0,              # 0 = uniform sheet, 1 = strong banks
    fog_bank=110.0,             # bank size, m (noise wavelength)
    fog_layer2=0.0,             # 2nd layer density as a fraction of the 1st
    fog_layer2_h=120.0,         # ... and its own scale height
    # ---- grade ------------------------------------------------------------
    exposure=-2.55,
    saturation=1.06,
    # ---- material response ------------------------------------------------
    wetness=0.0,                # 0..1.5
    snow_cover=0.0,             # 0..1
    # ---- geometry / particles --------------------------------------------
    wind=(0.6, 0.3),            # m/s, (x, y); azim 0 = +Y
    gust=0.0,                   # 0..1 extra sway amplitude on top of wind
    particle_kind="dust",       # none|dust|rain|snow|fog
    particle_rate=260,          # instances of the primary particle
    rain_fall=9.5,              # rain terminal speed, m/s -> tilt angle
    rain_length=0.62,           # streak length, m
    rain_radius=30.0,           # dense band radius, m
    rain_spread=110.0,          # sparse outer band radius, m
    rain_top=26.0,              # top of the rain volume above the ground, m
    rain_veil=0.0,              # far rain curtain, 0..1 opacity
    rain_near=8.0,              # nearest streak distance from the eye, m
    rain_alpha=0.13,            # streak alpha before distance fade
    rain_emit=0.85,             # streak emission: rain must read against a grey sky
    puddle=0.0,                 # near-field standing water, 0..1
    ripple=0.0,                 # splash ring density, 0..1
    flake_size=0.085,           # snow flake diameter, m
    flake_range=36.0,           # how far from the eye the flake cone reaches, m
    flake_top=20.0,             # top of the flake volume above the ground, m
    flake_alpha=0.78,           # flake opacity before distance fade
    flake_emit=0.9,             # emission: a flake has to out-glow the snow it falls on
    fog_banks=0.0,              # drifting fog blobs, 0..1
    bolt=0.0,                   # lightning channel, 0..1
    rainbow=0.0,                # 0..1
    flash=0.0,                  # peak-lightning exposure frame, 0..1
    # ---- bookkeeping ------------------------------------------------------
    visibility_km=20.0,         # design target; reported, also drives fog_density
    cloud_cover=0.7,
    desat_far=0.0,              # 0..1 how much the far field loses saturation
    bounce_mul=1.0,             # scale on hd_light's ground-bounce fill
    sky_fill=0.0,               # dome fill card above the town, x BOUNCE_W_PER_RATIO
)


# The eight states.  Numbers are calibrated against `look/weather_lab.py`, where
# every one of them was rendered at 640x360 and judged next to its neighbours.
PRESETS = {

    # 1. clear -- 20 km visibility, warm low sun, nothing in the air ----------
    "clear": dict(
        sun_energy=84.0, sun_color=(1.00, 0.862, 0.706), sun_elev=34.0, sun_azim=112.0,
        sun_angle=1.10,
        sky_preset="morning_town",
        sky=dict(zenith="#1b5b9c", horizon="#a9cee2", haze="#c3d2d6",
                 clouds=0.74, cloud_scale=0.44, cloud_soft=0.26, cloud_alt=900.0,
                 haze_mix=0.34, haze_band=0.055, glow=0.58,
                 gain=14.0, ambient=0.38, strength=1.00, sat=1.30),
        fog_density=0.00015, fog_height=900.0, fog_color=(0.58, 0.72, 0.92),
        fog_aniso=0.62, fog_noise=0.0,
        exposure=-2.22, saturation=1.08, bounce_mul=1.00, sky_fill=0.85,
        wetness=0.0, snow_cover=0.0,
        wind=(0.6, 0.3), particle_kind="dust", particle_rate=240,
        visibility_km=20.0, cloud_cover=0.62, desat_far=0.0,
    ),

    # 2. hazy -- attenuation starts at 1-3 km, distance goes warm and flat -----
    "hazy": dict(
        sun_energy=82.0, sun_color=(1.00, 0.878, 0.760), sun_elev=30.0, sun_azim=100.0,
        sun_angle=1.8,
        sky_preset="morning_town",
        sky=dict(zenith="#3d6f9c", horizon="#d8d2c0", haze="#cfc9b6",
                 clouds=0.40, cloud_scale=0.42, cloud_soft=0.42,
                 haze_mix=0.88, haze_band=0.19, glow=0.70,
                 gain=12.0, ambient=0.42, strength=0.98, sat=1.15),
        fog_density=0.00055, fog_height=170.0, fog_color=(0.80, 0.78, 0.71),
        fog_aniso=0.45, fog_noise=0.55, fog_bank=170.0,
        fog_layer2=0.22, fog_layer2_h=520.0,
        exposure=-2.32, saturation=0.94, bounce_mul=0.95, sky_fill=0.60,
        wetness=0.0, snow_cover=0.0,
        wind=(1.1, 0.4), particle_kind="dust", particle_rate=520,
        fog_banks=0.55, visibility_km=2.0, cloud_cover=0.40, desat_far=0.85,
    ),

    # 3. overcast -- no direct light at all, uniform grey-white dome ----------
    "overcast": dict(
        sun_energy=4.0, sun_color=(0.86, 0.905, 0.955), sun_elev=40.0, sun_azim=178.0,
        sun_angle=16.0,
        sky_preset="overcast_soft",
        sky=dict(zenith="#8b9aa6", horizon="#c3ccd2", haze="#c1c9cd",
                 clouds=1.0, cloud_scale=0.20, cloud_soft=0.56, cloud_alt=0.0,
                 haze_mix=0.58, haze_band=0.10, glow=0.22, sun_disc=0.0,
                 gain=9.5, ambient=0.70, strength=1.25, sat=1.10),
        fog_density=0.00090, fog_height=190.0, fog_color=(0.79, 0.82, 0.86),
        fog_aniso=0.30, fog_noise=0.25, fog_bank=200.0,
        exposure=-2.05, saturation=0.90, bounce_mul=0.85, sky_fill=0.50,
        wetness=0.16, snow_cover=0.0,
        wind=(1.2, 0.5), particle_kind="none", particle_rate=0,
        visibility_km=6.0, cloud_cover=1.0, desat_far=0.35,
    ),

    # 4. rain -- a bright, wet afternoon: luminous grey sky, sun that only
    #    glows, mirror-wet paving.  Rain out of a *lit* sky, never a midnight.
    "rain": dict(
        sun_energy=4.0, sun_color=(0.87, 0.905, 0.965), sun_elev=38.0, sun_azim=30.0,
        sun_angle=16.0,
        sky_preset="overcast_soft",
        sky=dict(zenith="#6d7a8a", horizon="#8f9aa6", haze="#8b96a0",
                 clouds=1.0, cloud_scale=0.22, cloud_soft=0.60, cloud_alt=0.0,
                 cloud_lit="#c2cbd3", cloud_shade="#727e8a",
                 haze_mix=0.52, haze_band=0.10, glow=0.12, sun_disc=0.0,
                 gain=11.5, ambient=0.86, strength=1.06, sat=1.12),
        fog_density=0.00075, fog_height=220.0, fog_color=(0.72, 0.76, 0.81),
        fog_aniso=0.38, fog_noise=0.30, fog_bank=150.0,
        exposure=-2.05, saturation=0.96, bounce_mul=0.95, sky_fill=0.50,
        wetness=1.00, snow_cover=0.0,
        wind=(2.4, 0.9), gust=0.15, particle_kind="rain", particle_rate=2400,
        rain_alpha=0.22, rain_emit=0.40, rain_near=9.0,
        rain_radius=44.0, rain_spread=160.0, rain_veil=0.42, rain_length=0.55,
        rain_top=24.0, puddle=0.80, ripple=1.20,
        visibility_km=1.2, cloud_cover=1.0, desat_far=0.45,
    ),

    # 5. storm -- dark violet sky, 30 deg rain, lightning, trees bent ---------
    "storm": dict(
        sun_energy=7.0, sun_color=(0.66, 0.68, 0.86), sun_elev=22.0, sun_azim=25.0,
        sun_angle=13.0,
        sky_preset="storm",
        sky=dict(zenith="#3f3a55", horizon="#5f5a7c", haze="#544f70",
                 clouds=1.0, cloud_scale=0.18, cloud_soft=0.64, cloud_alt=0.0,
                 cloud_lit="#6b5f80", cloud_shade="#191624",
                 haze_mix=0.70, haze_band=0.14, glow=0.30, sun_disc=0.0,
                 gain=6.4, ambient=0.62, strength=1.00, sat=1.50),
        fog_density=0.00125, fog_height=95.0, fog_color=(0.545, 0.535, 0.655),
        fog_aniso=0.45, fog_noise=0.55, fog_bank=120.0,
        exposure=-1.86, saturation=0.92, bounce_mul=0.75, sky_fill=0.12,
        wetness=0.95, snow_cover=0.0,
        wind=(5.2, 0.6), gust=1.0, particle_kind="rain", particle_rate=3000,
        rain_alpha=0.16, rain_emit=0.26,
        rain_radius=50.0, rain_spread=190.0, rain_veil=0.85, rain_length=0.90,
        puddle=0.85, ripple=1.35, bolt=1.0, flash=0.55,
        visibility_km=0.55, cloud_cover=1.0, desat_far=0.35,
    ),

    # 6. fog -- 20 m readable, 50 m gone, two stacked layers ------------------
    "fog": dict(
        sun_energy=9.0, sun_color=(0.79, 0.835, 0.905), sun_elev=30.0, sun_azim=140.0,
        sun_angle=18.0,
        sky_preset="overcast_soft",
        sky=dict(zenith="#aab3bb", horizon="#dfe1e0", haze="#dcdedc",
                 clouds=1.0, cloud_scale=0.20, cloud_soft=0.60, cloud_alt=0.0,
                 cloud_lit="#eef0f0", cloud_shade="#b2b8bd",
                 haze_mix=0.95, haze_band=0.35, glow=0.16, sun_disc=0.0,
                 gain=6.0, ambient=0.80, strength=0.92, sat=0.90),
        fog_density=0.05050, fog_height=12.0, fog_color=(0.855, 0.875, 0.895),
        fog_aniso=0.30, fog_noise=0.85, fog_bank=70.0,
        fog_layer2=0.11, fog_layer2_h=62.0,
        exposure=-2.25, saturation=0.80, bounce_mul=0.80, sky_fill=0.55,
        wetness=0.45, snow_cover=0.0,
        wind=(0.7, 0.2), particle_kind="fog", particle_rate=70,
        fog_banks=1.0, visibility_km=0.05, cloud_cover=1.0, desat_far=1.0,
    ),

    # 7. snow -- continuous flakes, cover driven by an up-facing weight -------
    "snow": dict(
        sun_energy=18.0, sun_color=(0.855, 0.905, 1.0), sun_elev=28.0, sun_azim=160.0,
        sun_angle=14.0,
        sky_preset="overcast_soft",
        sky=dict(zenith="#8ea3b6", horizon="#d6e0e6", haze="#d2dce2",
                 clouds=1.0, cloud_scale=0.19, cloud_soft=0.58, cloud_alt=0.0,
                 cloud_lit="#f4f8fa", cloud_shade="#a3b2be",
                 haze_mix=0.80, haze_band=0.22, glow=0.20, sun_disc=0.0,
                 gain=9.0, ambient=0.74, strength=1.10, sat=1.02),
        fog_density=0.00160, fog_height=140.0, fog_color=(0.845, 0.885, 0.925),
        fog_aniso=0.35, fog_noise=0.45, fog_bank=130.0,
        exposure=-2.20, saturation=0.94, bounce_mul=0.85, sky_fill=0.60,
        wetness=0.22, snow_cover=1.0,
        wind=(1.6, 0.6), gust=0.2, particle_kind="snow", particle_rate=15000,
        flake_size=0.175, flake_range=42.0,
        visibility_km=0.9, cloud_cover=1.0, desat_far=0.7,
    ),

    # 8. sunshower -- rain + low amber sun + a rainbow -----------------------
    "sunshower": dict(
        sun_energy=70.0, sun_color=(1.00, 0.700, 0.420), sun_elev=19.0, sun_azim=25.0,
        sun_angle=1.3,
        sky_preset="golden_street",
        sky=dict(zenith="#2f5f8c", horizon="#f0b578", haze="#e2b78e",
                 clouds=0.88, cloud_scale=0.24, cloud_soft=0.50, cloud_alt=0.0,
                 cloud_lit="#ffe0bc", cloud_shade="#8d7d80",
                 haze_mix=0.70, haze_band=0.14, glow=0.92,
                 gain=12.0, ambient=0.40, strength=0.95, sat=1.22),
        fog_density=0.00060, fog_height=135.0, fog_color=(0.86, 0.80, 0.72),
        fog_aniso=0.62, fog_noise=0.40, fog_bank=150.0,
        exposure=-2.24, saturation=1.12, bounce_mul=1.10, sky_fill=0.55,
        wetness=0.78, snow_cover=0.0,
        wind=(2.0, -0.9), gust=0.1, particle_kind="rain", particle_rate=1800,
        rain_alpha=0.24, rain_emit=0.50, rain_near=15.0,
        rain_radius=45.0, rain_spread=160.0, rain_veil=0.35,
        puddle=0.45, ripple=0.9, rainbow=1.0,
        visibility_km=2.5, cloud_cover=0.88, desat_far=0.25,
    ),
}


# =========================================================================== #
#  2.  state(), derived values, measurement
# =========================================================================== #
# Which hd_light preset supplies the compositor grade (glare, contrast) for a
# weather.  Exposure and saturation are then overwritten by the weather itself,
# so this only picks the *shape* of the grade, never its level.
_GRADE = {
    "clear": "morning_town", "hazy": "morning_town",
    "overcast": "overcast_soft", "rain": "overcast_soft",
    "storm": "dusk_city", "fog": "overcast_soft", "snow": "overcast_soft",
    "sunshower": "golden_street",
}


def state(name, **over):
    """Return the full parameter dict for `name`, plus `over` overrides.

    Derived keys are prefixed with an underscore so they never leak into the
    Unity schema: `_wind_speed`, `_wind_azim`, `_rain_tilt`.
    `sky` is forced to the sun's elevation/azimuth so the disc and the shadow
    can never disagree.
    """
    if name not in PRESETS:
        raise KeyError("unknown weather %r; have %s" % (name, ", ".join(ORDER)))
    cfg = dict(BASE)
    cfg.update(PRESETS[name])
    cfg.update(over)
    cfg["name"] = name
    cfg["grade_preset"] = _GRADE.get(name, "morning_town")

    sky = dict(cfg.get("sky") or {})
    sky["elevation"] = float(cfg["sun_elev"])
    sky["azimuth"] = float(cfg["sun_azim"])
    if "clouds" not in sky:
        sky["clouds"] = float(cfg.get("cloud_cover", 0.7))
    cfg["sky"] = sky

    cfg["wind"] = tuple(float(v) for v in cfg["wind"])
    cfg["sun_color"] = tuple(float(v) for v in cfg["sun_color"])
    cfg["fog_color"] = tuple(float(v) for v in cfg["fog_color"])

    sp = math.hypot(cfg["wind"][0], cfg["wind"][1])
    cfg["_wind_speed"] = sp
    cfg["_wind_azim"] = math.degrees(math.atan2(cfg["wind"][0], cfg["wind"][1])) % 360.0
    cfg["_rain_tilt"] = math.degrees(math.atan2(sp, max(0.5, cfg["rain_fall"])))
    cfg["_vis_m"] = visibility(cfg)
    # `visibility_km` is *derived*, never declared: a preset cannot claim 20 km
    # while its own sigma says 5 km.
    cfg["visibility_km"] = round(cfg["_vis_m"] / 1000.0, 3)
    return cfg


def transmittance(cfg, dist, eye=1.7):
    """T of a horizontal sight line at eye height through both fog layers."""
    eye = max(0.0, float(eye))
    d = _sigma(cfg, eye)
    return math.exp(-d * float(dist))


def _sigma(cfg, eye=1.7):
    """Extinction at eye height from both exponential layers, 1/m."""
    eye = max(0.0, float(eye))
    sig = float(cfg["fog_density"])
    d = sig * math.exp(-eye / max(1.0, cfg["fog_height"]))
    d += (sig * float(cfg.get("fog_layer2", 0.0))
          * math.exp(-eye / max(1.0, cfg.get("fog_layer2_h", 120.0))))
    return d


def visibility(cfg, eye=1.7, at=0.05):
    """Meteorological optical range: distance (m) where T falls to `at`.

    5% contrast is the standard visibility convention (WMO), which is why
    "20 km visibility" and "a 2% threshold" are not the same number.
    """
    d = _sigma(cfg, eye)
    if d <= 1e-9:
        return 1.0e9
    return math.log(1.0 / at) / d


def report(cfg):
    """The numbers a reviewer (or the Unity side) wants, as a plain dict."""
    out = dict(
        weather=cfg["name"],
        sun=dict(elev=cfg["sun_elev"], azim=cfg["sun_azim"], energy=cfg["sun_energy"],
                 color=tuple(round(c, 3) for c in cfg["sun_color"]),
                 angle=cfg["sun_angle"],
                 shadow_len=round(1.0 / max(0.05, math.tan(math.radians(cfg["sun_elev"]))), 2)),
        fog=dict(sigma=cfg["fog_density"], height=cfg["fog_height"],
                 color=tuple(round(c, 3) for c in cfg["fog_color"]),
                 layer2=cfg["fog_layer2"], layer2_h=cfg["fog_layer2_h"],
                 vis_m=round(cfg["_vis_m"], 1)),
        grade=dict(exposure=cfg["exposure"], saturation=cfg["saturation"]),
        response=dict(wetness=cfg["wetness"], snow_cover=cfg["snow_cover"]),
        wind=dict(v=tuple(round(v, 2) for v in cfg["wind"]), speed=round(cfg["_wind_speed"], 2),
                  azim=round(cfg["_wind_azim"], 1), rain_tilt=round(cfg["_rain_tilt"], 1)),
        particles=dict(kind=cfg["particle_kind"], rate=cfg["particle_rate"],
                       rain_len=cfg["rain_length"], flake=cfg["flake_size"]),
        extras=dict(puddle=cfg["puddle"], ripple=cfg["ripple"], bolt=cfg["bolt"],
                    rainbow=cfg["rainbow"], flash=cfg["flash"], veil=cfg["rain_veil"]),
    )
    out["T"] = {("%dm" % d): round(transmittance(cfg, d), 3)
                for d in (20, 50, 200, 1000, 3000, 20000)}
    return out


def table():
    """A fixed-width text table of all eight states (for the report / QC)."""
    keys = ("sun_energy", "sun_elev", "fog_density", "fog_height", "exposure",
            "saturation", "wetness", "snow_cover", "particle_kind", "particle_rate")
    w = 13
    lines = ["%-11s" % "weather" + "".join("%*s" % (w, k[:11]) for k in keys)]
    for n in ORDER:
        c = state(n)
        row = "%-11s" % n
        for k in keys:
            v = c[k]
            s = v if isinstance(v, str) else ("%.5g" % v if isinstance(v, float) else str(v))
            row += "%*s" % (w, s)
        lines.append(row)
    return "\n".join(lines)


def to_unity(cfg):
    """Strip the render-only keys; what is left is the cross-engine contract."""
    out = {}
    for k, v in cfg.items():
        if k.startswith("_") or k in ("sky", "name"):
            continue
        if isinstance(v, (tuple, list)):
            v = [round(float(x), 4) for x in v]
        elif isinstance(v, float):
            v = round(v, 4)
        out[k] = v
    out["weather"] = cfg["name"]
    out["wind_azim"] = round(cfg["_wind_azim"], 1)
    out["rain_tilt"] = round(cfg["_rain_tilt"], 1)
    out["sky_over"] = dict(cfg.get("sky") or {})
    return out


def dump_json(path=None):
    """Write all eight states as JSON for the Unity side.  Returns the path."""
    path = path or os.path.join(r"E:\My World\Blender\renders\kingdom\look",
                                "weather_presets.json")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        pass
    data = {n: to_unity(state(n)) for n in ORDER}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
    return path


# =========================================================================== #
#  3.  tiny node helpers
# =========================================================================== #
_E = 2.718281828459045


def _n(nt, kind, name, loc=(0, 0), **kw):
    node = nt.nodes.new(kind)
    node.name = name
    node.label = name
    node.location = loc
    for k, v in kw.items():
        try:
            setattr(node, k, v)
        except Exception:                                          # noqa: BLE001
            pass
    return node


def _lnk(nt, src, dst):
    try:
        nt.links.new(src, dst)
        return True
    except Exception:                                              # noqa: BLE001
        return False


def _math(nt, op, a=None, b=None, name="m", loc=(0, 0), clamp=False):
    nd = _n(nt, "ShaderNodeMath", name, loc, operation=op, use_clamp=clamp)
    for sock, val in zip(nd.inputs, (a, b)):
        if val is None:
            continue
        if isinstance(val, (int, float)):
            sock.default_value = float(val)
        else:
            _lnk(nt, val, sock)
    return nd.outputs[0]


def _maprange(nt, src, lo, hi, to_lo=0.0, to_hi=1.0, name="mr", loc=(0, 0)):
    nd = _n(nt, "ShaderNodeMapRange", name, loc, interpolation_type="LINEAR", clamp=True)
    _lnk(nt, src, nd.inputs["Value"])
    nd.inputs["From Min"].default_value = float(lo)
    nd.inputs["From Max"].default_value = float(hi)
    nd.inputs["To Min"].default_value = float(to_lo)
    nd.inputs["To Max"].default_value = float(to_hi)
    return nd.outputs["Result"]


def _mix(nt, a, b, fac, name="mix", loc=(0, 0), blend="MIX"):
    """Mix two colours; `a`/`b` are values or sockets, `fac` a value or socket."""
    nd = _n(nt, "ShaderNodeMixRGB", name, loc, blend_type=blend)
    for sock, val in zip((nd.inputs["Fac"], nd.inputs["Color1"], nd.inputs["Color2"]),
                         (fac, a, b)):
        if isinstance(val, (int, float)):
            sock.default_value = float(val)
        elif isinstance(val, (tuple, list)):
            sock.default_value = tuple(val)[:4] if len(val) == 4 else tuple(val) + (1.0,)
        else:
            _lnk(nt, val, sock)
    return nd.outputs["Color"]


def _principled(nt):
    for n in nt.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def _soft_material(name, rgb, alpha=1.0, emission=0.0, vcol=True, additive=False,
                   rough=0.30, spec=0.45):
    """A translucent emissive material for particles, banks and the rainbow.

    Particle geometry is 2-6 tris and the only thing that makes it read is the
    alpha profile, so the vertex colour's alpha channel is the whole shader:
    `Col.alpha * alpha`.  `Col.rgb` tints, which is what lets the rainbow use one
    material for all seven bands.
    """
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = _n(nt, "ShaderNodeOutputMaterial", "out", (620, 0))
    b = _n(nt, "ShaderNodeBsdfPrincipled", "bsdf", (380, 0))
    _lnk(nt, b.outputs["BSDF"], out.inputs["Surface"])
    # a soft, non-metallic surface: these are water droplets / snow / vapour
    for key, val in (("Base Color", tuple(rgb) + (1.0,) if len(rgb) == 3 else rgb),
                     ("Roughness", float(rough)), ("Metallic", 0.0),
                     ("Specular IOR Level", float(spec)), ("IOR", 1.33)):
        sock = b.inputs.get(key)
        if sock is not None:
            try:
                sock.default_value = val
            except Exception:                                      # noqa: BLE001
                pass
    if "Emission Color" in b.inputs:
        b.inputs["Emission Color"].default_value = (tuple(rgb) + (1.0,))[:4]
        b.inputs["Emission Strength"].default_value = float(emission)
    elif "Emission" in b.inputs:
        b.inputs["Emission"].default_value = (tuple(rgb) + (1.0,))[:4]

    alpha_src = None
    if vcol:
        at = _n(nt, "ShaderNodeVertexColor", "vcol", (-200, 0))
        at.layer_name = "Col"
        _lnk(nt, at.outputs["Color"], b.inputs["Base Color"])
        if "Emission Color" in b.inputs:
            _lnk(nt, at.outputs["Color"], b.inputs["Emission Color"])
        alpha_src = at.outputs["Alpha"]
    if alpha_src is None:
        b.inputs["Alpha"].default_value = float(alpha)
    else:
        m_ = _math(nt, "MULTIPLY", alpha_src, float(alpha), "alpha", (140, -140))
        _lnk(nt, m_, b.inputs["Alpha"])

    for attr, val in (("surface_render_method", "BLENDED"),
                      ("blend_method", "BLEND"),
                      ("use_backface_culling", False),
                      ("use_transparent_shadow", True),
                      ("shadow_method", "NONE")):
        try:
            setattr(m, attr, val)
        except Exception:                                          # noqa: BLE001
            pass
    try:
        m.diffuse_color = (tuple(rgb) + (1.0,))[:4]
    except Exception:                                              # noqa: BLE001
        pass
    m["wx"] = "soft"
    return m


def _solid_material(name, rgb, rough=0.10, metallic=0.0, emit=0.0, spec=0.5):
    """Opaque material for the puddles and the lightning core."""
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = _n(nt, "ShaderNodeOutputMaterial", "out", (620, 0))
    b = _n(nt, "ShaderNodeBsdfPrincipled", "bsdf", (380, 0))
    _lnk(nt, b.outputs["BSDF"], out.inputs["Surface"])
    b.inputs["Base Color"].default_value = (tuple(rgb) + (1.0,))[:4]
    b.inputs["Roughness"].default_value = float(rough)
    b.inputs["Metallic"].default_value = float(metallic)
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = float(spec)
    if emit and "Emission Color" in b.inputs:
        b.inputs["Emission Color"].default_value = (tuple(rgb) + (1.0,))[:4]
        b.inputs["Emission Strength"].default_value = float(emit)
    m["wx"] = "solid"
    return m


# =========================================================================== #
#  4.  base meshes (the things Unity instances)
# =========================================================================== #
def _mesh(name, verts, faces, colors=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate(verbose=False)
    if colors:
        attr = me.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="POINT")
        flat = []
        for c in colors:
            flat.extend((c[0], c[1], c[2], c[3]))
        attr.data.foreach_set("color", flat)
    me.update()
    me["wx"] = 1
    return me


def asset_mesh(kind):
    """The canonical, instantiable mesh for a weather particle.

    * ``rain_streak``  0.02 x 0.62 m ribbon, 6 verts / 4 tris, alpha taper
    * ``snowflake``    hexagon, 0.085 m, 7 verts / 6 tris, soft centre
    * ``splash_ring``  flat 0.22 m ring, 8 seg / 16 tris
    * ``puddle``       0.9 m irregular disc, 12 tris
    * ``puff``         12 verts icosphere, 20 tris (fog bank / haze blob)

    These are the *assets*: one quad, one hexagon.  The field objects built by
    `build()` are thousands of these baked into a single mesh, which is what
    keeps the object count under 40.  Unity can instance the same meshes
    directly (same scale, same orientation convention: +Z up, ribbon along -Z).
    """
    if kind in _ASSETS and _ASSETS[kind].users >= 0:
        try:
            return _ASSETS[kind]
        except ReferenceError:
            pass
    w, ln = 0.02, 0.62
    if kind == "rain_streak":
        ts = (0.0, 0.25, 1.0)
        al = (0.05, 1.0, 0.10)
        verts, cols = [], []
        for t, a in zip(ts, al):
            z = ln * (t - 1.0)
            verts += [(-w * 0.5, 0.0, z), (w * 0.5, 0.0, z)]
            cols += [(1.0, 1.0, 1.0, a), (1.0, 1.0, 1.0, a)]
        faces = [(0, 1, 3, 2), (2, 3, 5, 4)]
        me = _mesh(TAG + "asset_rain_streak", verts, faces, cols)
    elif kind == "snowflake":
        r = 0.0425
        verts = [(0.0, 0.0, 0.0)]
        cols = [(1.0, 1.0, 1.0, 1.0)]
        for i in range(6):
            a = math.tau * i / 6.0
            verts.append((math.cos(a) * r, 0.0, math.sin(a) * r))
            cols.append((1.0, 1.0, 1.0, 0.08))
        faces = [(0, 1 + i, 1 + (i + 1) % 6) for i in range(6)]
        me = _mesh(TAG + "asset_snowflake", verts, faces, cols)
    elif kind == "splash_ring":
        seg, ri, ro = 8, 0.055, 0.22
        verts, cols = [], []
        for i in range(seg):
            a = math.tau * i / seg
            verts += [(math.cos(a) * ri, math.sin(a) * ri, 0.0),
                      (math.cos(a) * ro, math.sin(a) * ro, 0.0)]
            cols += [(1.0, 1.0, 1.0, 0.55), (1.0, 1.0, 1.0, 0.0)]
        faces = []
        for i in range(seg):
            a0, a1 = 2 * i, 2 * ((i + 1) % seg)
            faces.append((a0, a0 + 1, a1 + 1, a1))
        me = _mesh(TAG + "asset_splash_ring", verts, faces, cols)
    elif kind == "puddle":
        # a fan, not a polygon: the rim carries alpha 0 so a puddle fades into
        # the paving instead of reading as a paper cut-out with a hard edge
        verts, cols = [(0.0, 0.0, 0.0)], [(0.40, 0.45, 0.53, 1.0)]
        r = 0.45
        for i in range(12):
            a = math.tau * i / 12.0
            k = 0.72 + 0.42 * ((i * 37) % 11) / 11.0
            verts.append((math.cos(a) * r * k, math.sin(a) * r * k, 0.0))
            cols.append((0.40, 0.45, 0.53, 0.10))
        faces = [(0, 1 + i, 1 + (i + 1) % 12) for i in range(12)]
        me = _mesh(TAG + "asset_puddle", verts, faces, cols)
    elif kind == "puff":
        g = (1.0 + math.sqrt(5.0)) / 2.0
        base = [(-1, g, 0), (1, g, 0), (-1, -g, 0), (1, -g, 0),
                (0, -1, g), (0, 1, g), (0, -1, -g), (0, 1, -g),
                (g, 0, -1), (g, 0, 1), (-g, 0, -1), (-g, 0, 1)]
        r = 0.5 / math.sqrt(1.0 + g * g)
        verts = [(v[0] * r, v[1] * r, v[2] * r) for v in base]
        faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
                 (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
                 (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
                 (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
        cols = [(1.0, 1.0, 1.0, 1.0)] * 12
        me = _mesh(TAG + "asset_puff", verts, faces, cols)
    else:
        raise KeyError("no such asset %r" % (kind,))
    _ASSETS[kind] = me
    return me


# =========================================================================== #
#  5.  geometry
# =========================================================================== #
def _billboard_side(p, eye, axis):
    """Width direction of a quad at p that faces `eye`, with `axis` as its down."""
    h = Vector((eye[0] - p[0], eye[1] - p[1], 0.0))
    if h.length < 1e-4:
        h = Vector((0.0, 1.0, 0.0))
    s = Vector(axis).cross(h)
    if s.length < 1e-5:
        s = Vector((1.0, 0.0, 0.0))
    return s.normalized()


class _Flat(object):
    """Accumulates verts/faces/vertex-colours, then bakes one mesh + object."""

    def __init__(self):
        self.v, self.f, self.c = [], [], []

    def ribbon(self, p0, p1, side, width, alphas, rgb=(1, 1, 1), seg=2):
        base = len(self.v)
        for i in range(seg + 1):
            t = i / float(seg)
            c = (p0[0] + (p1[0] - p0[0]) * t,
                 p0[1] + (p1[1] - p0[1]) * t,
                 p0[2] + (p1[2] - p0[2]) * t)
            off = side * (width * 0.5)
            self.v.append((c[0] - off[0], c[1] - off[1], c[2] - off[2]))
            self.v.append((c[0] + off[0], c[1] + off[1], c[2] + off[2]))
            a = alphas[min(i, len(alphas) - 1)]
            self.c.append((rgb[0], rgb[1], rgb[2], a))
            self.c.append((rgb[0], rgb[1], rgb[2], a))
        for i in range(seg):
            a0 = base + 2 * i
            self.f.append((a0, a0 + 1, a0 + 3, a0 + 2))

    def mesh(self, template, mat, T, scale, rot_z=0.0, tilt=None, name="field"):
        """Bake copies of `template` at the given transforms.

        Unused by the eight presets (each field builder inlines its own
        orientation maths) but kept as the generic instancing path: it is the
        exact transform the Unity side uses, so it doubles as a reference.
        """
        tv = [v.co.copy() for v in template.vertices]
        tf = [tuple(p.vertices) for p in template.polygons]
        tc = [(0.0, 0.0, 0.0, 0.0)] * len(tv)
        if template.color_attributes:
            ca = template.color_attributes[0]
            tc = [tuple(d.color) for d in ca.data]
        base = len(self.v)
        for i, p in enumerate(T):
            m = Matrix.Translation(p) @ (rot_z if rot_z else Matrix.Identity(4)) \
                @ Matrix.Scale(scale[i], 4)
            for k, v in enumerate(tv):
                w = m @ v
                self.v.append((w.x, w.y, w.z))
                self.c.append(tc[k])
        for i in range(len(T)):
            off = base + i * len(tv)
            for f in tf:
                self.f.append(tuple(off + k for k in f))
        return self


def _rand_point(rng, cx, cy, r0, r1, z0, z1, bias=1.5):
    u = rng.random()
    r = r0 + (r1 - r0) * (u ** bias)
    a = rng.uniform(0.0, math.tau)
    return (cx + math.cos(a) * r, cy + math.sin(a) * r, rng.uniform(z0, z1), r)


def _cone_sampler(eye, look, d0, d1, half_deg, bias=1.8):
    """Sample inside the view cone instead of a sphere round the town.

    Rain that is uniformly scattered through a 120 m sphere puts ~90% of its
    triangles where they subtend less than a pixel.  Sampling a truncated cone
    along eye->look and biasing the distance toward the camera spends the same
    budget where the frame actually is, which is what makes a streak field read
    at 640x360 instead of looking like noise.
    """
    e = Vector(eye)
    ax = Vector(look) - e
    ax.z *= 0.75                                   # flatter than the sight line
    if ax.length < 1e-6:
        ax = Vector((0.0, 1.0, -0.15))
    ax.normalize()
    up = Vector((0.0, 0.0, 1.0))
    if abs(ax.z) > 0.95:
        up = Vector((0.0, 1.0, 0.0))
    right = ax.cross(up).normalized()
    upv = right.cross(ax).normalized()
    ct = math.cos(math.radians(half_deg))

    def sample(rng):
        d = d0 + (d1 - d0) * (rng.random() ** bias)
        # uniform on the spherical cap, then thrown at a random azimuth
        cz = ct + (1.0 - ct) * rng.random()
        sz = math.sqrt(max(0.0, 1.0 - cz * cz))
        ph = rng.uniform(0.0, math.tau)
        dirv = ax * cz + (right * math.cos(ph) + upv * math.sin(ph)) * sz
        return e + dirv * d, d

    return sample


def _rain_field(n, cfg, center, rng, eye, ground_z, ring=(0.0, 30.0), top=22.0,
                length=None, alpha_mul=1.0, seg=2, cone=None):
    """N wind-tilted ribbons; each is an instance of asset_mesh('rain_streak')."""
    ln = cfg["rain_length"] if length is None else length
    tilt = math.radians(cfg["_rain_tilt"])
    az = math.radians(cfg["_wind_azim"])
    down = Vector((math.sin(tilt) * math.sin(az), math.sin(tilt) * math.cos(az),
                   -math.cos(tilt))).normalized()
    ev = Vector(eye)
    # one streak is ~1.5 px wide whatever its distance: below that a 0.02 m
    # ribbon simply is not there on a 640 px frame.
    pxw = 0.0016
    fl = _Flat()
    for _ in range(int(n)):
        if cone is not None:
            p0, dist = None, 0.0
            for _try in range(4):
                p0, dist = cone(rng)
                if ground_z + 0.3 <= p0.z <= ground_z + top:
                    break
                # rejected: try again, and on the last try pin it to a legal
                # height at the same distance instead of piling streaks on the
                # ground plane
                if _try == 3:
                    p0.z = ground_z + rng.uniform(0.5, top)
        else:
            x, y, z, _r = _rand_point(rng, center[0], center[1], ring[0], ring[1],
                                      ground_z, ground_z + top)
            p0, dist = Vector((x, y, z)), (Vector((x, y, z)) - ev).length
        # A streak has to subtend the same *angle* at every distance or the
        # field reads as one curtain: 0.85 m at 2 m is a 180 px bar, 0.85 m at
        # 60 m is 2 px.  0.030*dist is ~1.7 degrees, which is a raindrop trail,
        # and the 1.1 m cap stops the near bank from drawing a stripe across the
        # whole frame -- the exact failure of the 1.25 m / 0.055*dist version.
        L = (ln if cone is None else min(1.10, max(ln, 0.030 * dist)))
        L *= rng.uniform(0.72, 1.38)
        p1 = p0 - down * L
        side = _billboard_side(p0, eye, down)
        a = alpha_mul * rng.uniform(0.45, 1.0)
        fl.ribbon(p0, p1, side, max(0.013, dist * pxw),
                  (0.04 * a, 1.0 * a, 0.12 * a), seg=seg)
    return fl


def _snow_field(n, cfg, center, rng, eye, ground_z, ring=(0.0, 30.0), top=20.0,
                size=None, alpha_mul=1.0, cone=None):
    size = cfg["flake_size"] if size is None else size
    tem = asset_mesh("snowflake")
    tv = [v.co.copy() for v in tem.vertices]
    tf = [tuple(p.vertices) for p in tem.polygons]
    ca = [tuple(d.color) for d in tem.color_attributes[0].data]
    fl = _Flat()
    for _ in range(int(n)):
        if cone is not None:
            p = None
            for _try in range(4):
                p, dist = cone(rng)
                if ground_z + 0.2 <= p.z <= ground_z + top:
                    break
                if _try == 3:
                    p.z = ground_z + rng.uniform(0.3, top)
        else:
            x, y, z, _r = _rand_point(rng, center[0], center[1], ring[0], ring[1],
                                      ground_z, ground_z + top)
            p = Vector((x, y, z))
            dist = (p - Vector(eye)).length
        # face the eye, keep the flake's own plane vertical-ish
        d = (Vector(eye) - p)
        if d.length < 1e-3:
            d = Vector((0, 1, 0))
        yaw = math.atan2(d.y, d.x) - math.pi * 0.5
        s = size * rng.uniform(0.6, 1.5) * (1.0 if cone is None
                                            else min(2.2, 0.7 + dist * 0.035))
        r = Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(
            rng.uniform(-0.5, 0.5), 4, "Y")
        base = len(fl.v)
        m = Matrix.Translation(p) @ r @ Matrix.Scale(s, 4)
        for k, v in enumerate(tv):
            w = m @ v
            fl.v.append((w.x, w.y, w.z))
            c = ca[k]
            fl.c.append((c[0], c[1], c[2], c[3] * alpha_mul))
        for f in tf:
            fl.f.append(tuple(base + k for k in f))
    return fl


def _splash_field(n, cfg, center, rng, ground_z, ring_r=(1.0, 22.0), eye=None):
    """Ring glints where drops hit standing water.

    A ripple at gameplay distance is 3-8 px.  The previous 0.35-0.80 scale made
    40 px white ellipses that read as wireframe rings laid on the paving --
    larger than the cobbles they sat on.  Size now follows the distance to the
    eye (constant angular size) and the ring rides 4-12 mm above the ground so
    it catches the sky without z-fighting the stones.
    """
    tem = asset_mesh("splash_ring")
    tv = [v.co.copy() for v in tem.vertices]
    tf = [tuple(p.vertices) for p in tem.polygons]
    ca = [tuple(d.color) for d in tem.color_attributes[0].data]
    ev = (float(eye[0]), float(eye[1])) if eye else None
    fl = _Flat()
    for _ in range(int(n)):
        x, y, _z, _r = _rand_point(rng, center[0], center[1], ring_r[0], ring_r[1],
                                  ground_z, ground_z)
        d = math.hypot(x - ev[0], y - ev[1]) if ev else 12.0
        s = max(0.085, min(0.46, 0.0125 * d)) * rng.uniform(0.70, 1.40)
        base = len(fl.v)
        m = Matrix.Translation(Vector((x, y, ground_z + 0.004 + rng.uniform(0, 0.008)))) \
            @ Matrix.Scale(s, 4)
        for k, v in enumerate(tv):
            w = m @ v
            fl.v.append((w.x, w.y, w.z))
            fl.c.append(ca[k])
        for f in tf:
            fl.f.append(tuple(base + k for k in f))
    return fl


def _puddle_field(n, cfg, center, rng, ground_z, ring_r=(1.5, 24.0)):
    tem = asset_mesh("puddle")
    tv = [v.co.copy() for v in tem.vertices]
    tf = [tuple(p.vertices) for p in tem.polygons]
    fl = _Flat()
    for _ in range(int(n)):
        x, y, _z, _r = _rand_point(rng, center[0], center[1], ring_r[0], ring_r[1],
                                  ground_z, ground_z)
        s = rng.uniform(0.45, 0.95)
        rot = Matrix.Rotation(rng.uniform(0, math.tau), 4, "Z")
        base = len(fl.v)
        m = Matrix.Translation(Vector((x, y, ground_z + 0.02))) @ rot \
            @ Matrix.Scale(s, 4)
        for k, v in enumerate(tv):
            w = m @ v
            fl.v.append((w.x, w.y, w.z))
            fl.c.append((1.0, 1.0, 1.0, 1.0))
        for f in tf:
            fl.f.append(tuple(base + k for k in f))
    return fl


def _puff_field(n, cfg, center, rng, ground_z, ring_r=(60.0, 240.0), zr=(2.0, 26.0),
                scale=(9.0, 26.0)):
    tem = asset_mesh("puff")
    tv = [v.co.copy() for v in tem.vertices]
    tf = [tuple(p.vertices) for p in tem.polygons]
    fl = _Flat()
    for _ in range(int(n)):
        x, y, _z, _r = _rand_point(rng, center[0], center[1], ring_r[0], ring_r[1],
                                  ground_z, ground_z)
        z = ground_z + rng.uniform(*zr)
        s = rng.uniform(*scale)
        base = len(fl.v)
        m = Matrix.Translation(Vector((x, y, z))) @ Matrix.Scale(s, 4) \
            @ Matrix.Diagonal(Vector((1.0, 1.0, 0.55, 1.0)))
        for k, v in enumerate(tv):
            w = m @ v
            fl.v.append((w.x, w.y, w.z))
            fl.c.append((1.0, 1.0, 1.0, 1.0))
        for f in tf:
            fl.f.append(tuple(base + k for k in f))
    return fl


def _bolt_geometry(center, rng, base_z, top_z, dist, az_deg, width=2.6, seg=14):
    """A jagged channel from cloud base to ground, plus two forks."""
    az = math.radians(az_deg)
    ox, oy = math.sin(az) * dist, math.cos(az) * dist
    pts = []
    wob = 0.0
    for i in range(seg + 1):
        t = i / float(seg)
        z = base_z + (top_z - base_z) * t
        wob = wob * 0.55 + rng.uniform(-1.0, 1.0) * 9.0
        pts.append(Vector((center[0] + ox + wob, center[1] + oy + wob * 0.4, z)))
    verts, faces, cols = [], [], []
    for i in range(seg):
        p0, p1 = pts[i], pts[i + 1]
        d = (p1 - p0)
        side = Vector((1.0, 0.0, 0.0)).cross(d)
        if side.length < 1e-4:
            side = Vector((0.0, 1.0, 0.0))
        side = side.normalized() * (width * (0.35 + 0.65 * math.sin(math.pi * (1 - i / float(seg)))))
        b = len(verts)
        verts += [(p0 - side), (p0 + side), (p1 + side), (p1 - side)]
        cols += [(0.86, 0.92, 1.0, 1.0)] * 4
        faces.append((b, b + 1, b + 2, b + 3))
    # two forks off the main channel
    for k in (0.30, 0.55):
        i = int(k * seg)
        p0 = pts[i]
        d = Vector((rng.uniform(0.4, 1.0) * (1 if rng.random() < 0.5 else -1),
                    rng.uniform(-0.5, 0.5), -0.35)).normalized()
        q = p0
        for _ in range(4):
            q2 = q + d * rng.uniform(6.0, 14.0)
            d = (d + Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3),
                             -0.15))).normalized()
            side = Vector((1.0, 0.0, 0.0)).cross(q2 - q)
            if side.length < 1e-4:
                side = Vector((0, 1, 0))
            side = side.normalized() * width * 0.16
            b = len(verts)
            verts += [(q - side), (q + side), (q2 + side), (q2 - side)]
            cols += [(0.8, 0.88, 1.0, 0.85)] * 4
            faces.append((b, b + 1, b + 2, b + 3))
            q = q2
    return _mesh(TAG + "bolt", verts, faces, cols)


def _rainbow_mesh(center, cfg, dist=430.0, inner=39.8, outer=42.6, seg=72):
    """A real 42-degree bow: a ring on the antisolar axis, culled at the horizon."""
    el = math.radians(cfg["sun_elev"])
    az = math.radians(cfg["sun_azim"])
    anti = Vector((-math.sin(az) * math.cos(el), math.cos(az) * math.cos(el),
                   -math.sin(el))).normalized()
    c = Vector((center[0], center[1], 0.0)) + anti * dist
    up = Vector((0.0, 0.0, 1.0))
    u = (up - anti * anti.dot(up))
    u = u.normalized() if u.length > 1e-5 else Vector((0.0, 0.0, 1.0))
    v = anti.cross(u).normalized()

    def ring(theta):
        return (c + (u * math.cos(theta) + v * math.sin(theta)) * (dist * math.tan(
            math.radians(inner))))

    # visible arc: everything above z = 0
    zc = c.z
    r = dist * math.tan(math.radians(inner))
    if r <= abs(zc):
        return None
    half = math.acos(max(-1.0, min(1.0, -zc / r)))
    t0, t1 = -half, half
    rows = (0.0, 0.45, 0.78, 1.0)
    # red outside -> violet inside (row 0 = inner)
    band = ((0.42, 0.12, 0.62), (0.16, 0.28, 0.82), (0.20, 0.66, 0.70),
            (0.72, 0.86, 0.25), (0.98, 0.62, 0.10), (0.98, 0.34, 0.10))
    verts, faces, cols = [], [], []
    for i in range(seg + 1):
        th = t0 + (t1 - t0) * i / seg
        fade = math.sin(math.pi * i / seg) ** 0.5
        for j, rr in enumerate(rows):
            rad = dist * math.tan(math.radians(inner + (outer - inner) * rr))
            p = c + (u * math.cos(th) + v * math.sin(th)) * rad
            verts.append((p.x, p.y, p.z))
            k = min(len(band) - 1, int(rr * (len(band) - 1)))
            col = band[k]
            a = math.sin(math.pi * rr) * fade * (0.62 if 0 < j < len(rows) - 1 else 0.35)
            cols.append((col[0], col[1], col[2], a))
    nr = len(rows)
    for i in range(seg):
        for j in range(nr - 1):
            a0 = i * nr + j
            faces.append((a0, a0 + 1, a0 + 1 + nr, a0 + nr))
    return _mesh(TAG + "rainbow", verts, faces, cols)


def _link(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def _new_obj(name, mesh, mat=None, coll=None):
    ob = bpy.data.objects.new(name, mesh)
    if mat is not None and mesh.materials and len(mesh.materials) == 0:
        mesh.materials.append(mat)
    _link(ob, coll)
    ob.name = name
    return ob


def _bake(fl, name, mat, center, smooth=False):
    me = _mesh(name + "_me", fl.v, fl.f, fl.c)
    if mat is not None:
        me.materials.append(mat)
    ob = _new_obj(name, me)
    ob.location = (0.0, 0.0, 0.0)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


# =========================================================================== #
#  6.  build()
# =========================================================================== #
def _scene_eye_look(dist=34.0):
    """(camera location, a point `dist` metres along its view axis).

    The caller of `build()` normally does not know the camera; the render rig
    sets `scene.camera` long before.  Reading it here means the near rain/snow
    banks always land in front of the lens -- including a 52 deg gameplay
    camera, whose view axis points at the pavement, not at the horizon.
    """
    cam = None
    try:
        cam = bpy.context.scene.camera
    except Exception:                                           # noqa: BLE001
        cam = None
    if cam is None or IN_BLENDER is False:
        return None, None
    try:
        eye = tuple(float(v) for v in cam.location)
        fwd = cam.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
        look = tuple(float(eye[i] + fwd[i] * dist) for i in range(3))
        return eye, look
    except Exception:                                           # noqa: BLE001
        return None, None


def build(scene, name, MAT=None, center=(0, 0), radius=1200, seed=9,
          eye=None, ground_z=0.0, look=None):
    """Instantiate the geometry for one weather state.

    Parameters
    ----------
    scene   : the bpy scene (only used for the collection)
    name    : one of ORDER, or a dict already produced by `state()`
    MAT     : optional material dict; if given, `apply_materials` is called too
    center  : (x, y) the weather field is centred on -- pass the camera pivot,
              not the world origin, or the rain will be somewhere else
    radius  : world radius of the town, m; only used to size the far banks
    seed    : rng seed, so a shot is reproducible
    eye     : camera position, for billboarding; default (cx, cy, 8)
    ground_z: z of the ground under `center` (puddles / splashes / bolts)
    look    : point the camera is aimed at.  The near rain/snow banks are
              sampled in a cone along eye->look, so a top-down (52 deg pitch)
              gameplay camera gets its streaks in frame instead of over the
              horizon; defaults to the old straight-ahead aim.

    Returns ``{"objects": [...], "cfg": {...}, "tris": n, "assets": {...}}``.
    """
    cfg = dict(name) if isinstance(name, dict) else state(name)
    clear()
    rng = random.Random(seed)
    cx, cy = float(center[0]), float(center[1])
    if eye is None or look is None:
        c_eye, c_look = _scene_eye_look()
        if eye is None:
            eye = c_eye if c_eye is not None else (cx, cy, 8.0)
        if look is None:
            look = c_look
    # remembered so a later apply_atmos()/apply_fog() can size its box for this
    # build without the caller having to repeat the numbers
    cfg["radius"] = float(radius)
    cfg["center"] = (cx, cy)
    cfg["_ground_z"] = float(ground_z)
    cfg["eye"] = tuple(float(v) for v in eye)
    cfg["look"] = tuple(float(v) for v in look) if look is not None else None
    objs = []
    tris = [0]
    t_center = (cx, cy)

    def add(ob):
        objs.append(ob)
        tris[0] += _tri_count(ob)
        return ob

    kind = cfg["particle_kind"]

    # ---- rain ------------------------------------------------------------
    if kind == "rain" and cfg["particle_rate"] > 0:
        n = int(cfg["particle_rate"])
        near = int(n * 0.72)
        mat = _soft_material(TAG + "Rain", (0.80, 0.86, 0.95),
                             alpha=float(cfg.get("rain_alpha", 0.30)),
                             emission=float(cfg.get("rain_emit", 0.85)))
        lk = look if look is not None else (cx, cy, ground_z + 14.0)
        cone = _cone_sampler(eye, lk, float(cfg.get("rain_near", 8.0)),
                             cfg["rain_spread"] * 0.62, 30.0, bias=1.7)
        fl = _rain_field(near, cfg, t_center, rng, eye, ground_z,
                         top=cfg["rain_top"], cone=cone)
        add(_bake(fl, TAG + "RainNear", mat, t_center))
        if cfg["rain_spread"] > cfg["rain_radius"] + 1.0:
            fl = _rain_field(n - near, cfg, t_center, rng, eye, ground_z,
                             ring=(cfg["rain_radius"], cfg["rain_spread"]),
                             top=cfg["rain_top"] * 1.3,
                             alpha_mul=0.30, seg=1)
            add(_bake(fl, TAG + "RainFar", mat, t_center))

    # ---- snow ------------------------------------------------------------
    if kind == "snow" and cfg["particle_rate"] > 0:
        n = int(cfg["particle_rate"])
        near = int(n * 0.62)
        # A flake is not a white object on a white world: at 640x360 it is 2-4 px,
        # and against a snowfield at display 148 a mid-grey flake measures 0.03 %
        # of the frame.  It has to *emit* to sit above the snow it falls on.
        mat = _soft_material(TAG + "Snow", (0.88, 0.92, 0.98),
                             alpha=float(cfg.get("flake_alpha", 0.78)),
                             emission=float(cfg.get("flake_emit", 0.9)))
        lk = look if look is not None else (cx, cy, ground_z + 8.0)
        cone = _cone_sampler(eye, lk, 1.5, cfg["flake_range"], 32.0, bias=1.5)
        fl = _snow_field(near, cfg, t_center, rng, eye, ground_z,
                         top=cfg["flake_top"], cone=cone)
        add(_bake(fl, TAG + "SnowNear", mat, t_center))
        fl = _snow_field(n - near, cfg, t_center, rng, eye, ground_z,
                         ring=(cfg["flake_range"] * 0.7, cfg["flake_range"] * 3.0),
                         top=cfg["flake_top"] * 1.5,
                         size=cfg["flake_size"] * 2.0, alpha_mul=0.40)
        add(_bake(fl, TAG + "SnowFar", mat, t_center))

    # ---- dust motes / pollen (clear, hazy) ------------------------------
    if kind == "dust" and cfg["particle_rate"] > 0:
        mat = _soft_material(TAG + "Dust", (1.0, 0.93, 0.78), alpha=0.42,
                             emission=1.6)
        fl = _rain_field(int(cfg["particle_rate"]), cfg, t_center, rng, eye,
                         ground_z, ring=(0.4, 26.0), top=9.0, length=0.055, seg=1,
                         alpha_mul=0.5)
        add(_bake(fl, TAG + "Dust", mat, t_center))

    # ---- splashes + standing water --------------------------------------
    if cfg["ripple"] > 0:
        # a splash is a *glint*: white-hot for a frame, so it carries emission
        # and almost no coverage.  At alpha 0.15 x 740 rings the ground was a
        # field of grey hoops; the ring is now small, bright and short-lived.
        mat = _soft_material(TAG + "Splash", (0.90, 0.94, 1.0), alpha=0.22,
                             emission=0.85)
        n = int(420 + 900 * min(2.0, cfg["ripple"]))
        add(_bake(_splash_field(n, cfg, t_center, rng, ground_z, eye=eye),
                  TAG + "Splash", mat, t_center))
    if cfg["puddle"] > 0:
        # Seen from 52 degrees a puddle is not a white disc: it is a *mirror*
        # of the bright dome, i.e. a dark, glassy patch with a hard sky
        # highlight.  Painting the sky colour into the base colour (the
        # 0.58*fog+0.30 version) turned 160 of them into white blobs of paint;
        # the sheen now comes from roughness 0.04 + spec 1.0, and emission is
        # only there to keep the water alive in a heavy storm.
        fc = cfg["fog_color"]
        pc = tuple(min(0.62, 0.42 * c + 0.06) for c in fc)
        mat = _solid_material(TAG + "Puddle", pc, rough=0.04, spec=1.0, emit=0.06)
        n = int(28 + 70 * min(1.5, cfg["puddle"]))
        add(_bake(_puddle_field(n, cfg, t_center, rng, ground_z),
                  TAG + "Puddles", mat, t_center))

    # ---- drifting fog banks ---------------------------------------------
    if cfg["fog_banks"] > 0:
        mat = _soft_material(TAG + "Bank", tuple(cfg["fog_color"]), alpha=0.085,
                             emission=1.1)
        n = int(18 + 34 * min(1.5, cfg["fog_banks"]))
        add(_bake(_puff_field(n, cfg, t_center, rng, ground_z,
                              ring_r=(35.0, max(90.0, radius * 0.22))),
                  TAG + "FogBanks", mat, t_center))

    # ---- lightning -------------------------------------------------------
    if cfg["bolt"] > 0:
        az = (cfg["sun_azim"] + 150.0) % 360.0
        me = _bolt_geometry(t_center, rng, ground_z + 55.0, ground_z + 130.0, 420.0, az,
                            width=7.0, seg=16)
        bolt_mat = _solid_material(TAG + "Bolt", (0.82, 0.88, 1.0), rough=0.5,
                                   emit=60.0)
        bolt = _new_obj(TAG + "Bolt", me)
        me.materials.append(bolt_mat)
        for attr, val in (("visible_shadow", False),):
            try:
                setattr(bolt, attr, val)
            except Exception:                                      # noqa: BLE001
                pass
        add(bolt)
        # the cloud bounce: a big soft additive card behind the channel
        glow = _soft_material(TAG + "BoltGlow", (0.55, 0.60, 1.0), alpha=0.55,
                              emission=3.0)
        D = 430.0
        cx2 = cx + math.sin(math.radians(az)) * D
        cy2 = cy + math.cos(math.radians(az)) * D
        # a billboard quad whose alpha fades from the channel upward; it has to
        # face the eye or from any other bearing it reads as a hard-edged
        # bright rectangle pasted into the sky
        c0 = Vector((cx2, cy2, ground_z + 95.0))
        nrm = c0 - Vector(eye)
        nrm.z = 0.0
        if nrm.length < 1e-3:
            nrm = Vector((0.0, 1.0, 0.0))
        nrm.normalize()
        right = Vector((nrm.y, -nrm.x, 0.0))
        hw, hh = 130.0, 62.0
        gl = _Flat()
        gl.v = [tuple(c0 - right * hw - Vector((0.0, 0.0, hh))),
                tuple(c0 + right * hw - Vector((0.0, 0.0, hh))),
                tuple(c0 + right * hw + Vector((0.0, 0.0, hh))),
                tuple(c0 - right * hw + Vector((0.0, 0.0, hh)))]
        gl.c = [(0.60, 0.65, 1.0, 0.55), (0.60, 0.65, 1.0, 0.55),
                (0.45, 0.50, 0.95, 0.0), (0.45, 0.50, 0.95, 0.0)]
        gl.f = [(0, 1, 2, 3)]
        gq = _bake(gl, TAG + "BoltGlow", glow, t_center)
        gq.visible_shadow = False
        add(gq)

    # ---- rainbow ---------------------------------------------------------
    if cfg["rainbow"] > 0:
        me = _rainbow_mesh(t_center, cfg)
        if me is not None:
            # vcol=True: the seven bands live in the vertex colours
            mat = _soft_material(TAG + "Rainbow", (1.0, 1.0, 1.0), alpha=0.62,
                                 emission=2.6, vcol=True)
            add(_bake_arc(me, mat))

    # ---- far rain curtain ------------------------------------------------
    if cfg["rain_veil"] > 0:
        mat = _soft_material(TAG + "RainVeil", (0.72, 0.78, 0.86), alpha=0.10,
                             emission=0.25)
        ve = _Flat()
        for r, h, a in ((cfg["rain_spread"] * 1.6, 70.0, 0.55),
                        (cfg["rain_spread"] * 2.6, 105.0, 0.30)):
            seg = 14
            for i in range(seg):
                ang = math.tau * i / seg
                x0 = cx + math.cos(ang) * r
                y0 = cy + math.sin(ang) * r
                b = len(ve.v)
                ve.v += [(x0, y0, ground_z + 0.0), (x0, y0, ground_z + h),
                         (x0, y0, ground_z + h), (x0, y0, ground_z + 0.0)]
                ve.c += [(0.9, 0.93, 1.0, a * 0.9), (0.9, 0.93, 1.0, a * 0.0),
                         (0.9, 0.93, 1.0, a * 0.0), (0.9, 0.93, 1.0, a * 0.9)]
                ve.f.append((b, b + 1, b + 2, b + 3))
        add(_bake(ve, TAG + "RainVeil", mat, t_center))

    # ---- the flash light (the 'exposure frame' carrier) ------------------
    if cfg["flash"] > 0 or cfg["bolt"] > 0:
        ld = bpy.data.lights.new(TAG + "FlashSunData", "SUN")
        ld.energy = 0.0
        ld.color = (0.82, 0.88, 1.0)
        ld.angle = math.radians(3.0)
        lo = bpy.data.objects.new(TAG + "FlashSun", ld)
        _link(lo)
        az = math.radians((cfg["sun_azim"] + 150.0) % 360.0)
        lo.rotation_euler = Euler((math.radians(90.0 - 46.0), 0.0, az + math.pi), "XYZ")
        add(lo)

    # ---- materials (optional convenience) --------------------------------
    changed = 0
    if MAT is not None:
        changed = apply_materials(MAT, cfg)
        print("[wx] %s materials changed=%d" % (cfg["name"], changed), flush=True)

    out = dict(objects=objs, cfg=cfg, tris=tris[0], objects_n=len(objs),
               assets=dict(_ASSETS), materials_changed=changed,
               center=t_center, eye=tuple(eye), ground_z=ground_z)
    print("[wx] build %-10s objects=%d tris=%d" % (cfg["name"], len(objs), tris[0]),
          flush=True)
    return out


def _bake_arc(me, mat):
    """Wrap a ready mesh (the rainbow) in an object without re-baking verts."""
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    ob = _new_obj(TAG + "Rainbow", me)
    ob.visible_shadow = False
    return ob


def _tri_count(ob):
    if ob is None or ob.type != "MESH":
        return 0
    me = ob.data
    try:
        me.calc_loop_triangles()
        return len(me.loop_triangles)
    except Exception:                                              # noqa: BLE001
        return sum(max(0, len(p.vertices) - 2) for p in me.polygons)


def clear():
    """Remove every object (and fat mesh) this module built."""
    n = 0
    for ob in list(bpy.data.objects):
        if ob.name.startswith(TAG):
            try:
                bpy.data.objects.remove(ob, do_unlink=True)
                n += 1
            except ReferenceError:
                pass
    del _OBJECTS[:]
    for key, me in list(_ASSETS.items()):
        try:
            if me.users == 0:
                bpy.data.meshes.remove(me)
                del _ASSETS[key]
        except (ReferenceError, RuntimeError):
            _ASSETS.pop(key, None)
    if n:
        print("[wx] clear removed %d objects" % n, flush=True)
    return n


# =========================================================================== #
#  7.  sky / sun / fog / grade
# =========================================================================== #
def apply_sky(scene, cfg, hd_sky=None):
    """hd_sky's procedural dome, tinted and raised for this weather."""
    if hd_sky is None:
        import hd_sky as hd_sky
    res = hd_sky.world(scene, cfg["sky_preset"], **dict(cfg["sky"]))
    # remember the base strength so the flash can multiply instead of drift
    try:
        scene.world["wx_strength"] = float(cfg["sky"].get("strength", 1.0)) \
            * float(cfg["sky"].get("gain", 1.0))
    except Exception:                                              # noqa: BLE001
        pass
    print("[wx] sky %-14s clouds=%.2f amb=%.2f gain=%.1f"
          % (cfg["sky_preset"], cfg["sky"].get("clouds", 0.0),
             cfg["sky"].get("ambient", 0.0), cfg["sky"].get("gain", 1.0)), flush=True)
    return res


def find_sun():
    for ob in bpy.data.objects:
        if ob.type == "LIGHT" and ob.data.type == "SUN" and not ob.name.startswith(
                TAG + "Flash"):
            return ob
    return None


def apply_sun(scene, cfg, sun=None):
    """Drive the key light.  Uses hd_light's sun when it already exists."""
    ob = sun or find_sun()
    if ob is None:
        d = bpy.data.lights.new(TAG + "SunData", "SUN")
        ob = bpy.data.objects.new(TAG + "Sun", d)
        _link(ob)
    d = ob.data
    d.energy = float(cfg["sun_energy"])
    try:
        d.color = tuple(cfg["sun_color"])[:3]
    except Exception:                                              # noqa: BLE001
        pass
    try:
        d.angle = math.radians(float(cfg["sun_angle"]))
    except Exception:                                              # noqa: BLE001
        pass
    d.use_shadow = True
    for attr, val in (("specular_factor", 1.0), ("diffuse_factor", 1.0)):
        try:
            setattr(d, attr, val)
        except Exception:                                          # noqa: BLE001
            pass
    ob.rotation_euler = Euler((math.radians(90.0 - float(cfg["sun_elev"])), 0.0,
                               math.radians(float(cfg["sun_azim"]))), "XYZ")
    print("[wx] sun elev=%.1f azim=%.1f E=%.1f ang=%.1f"
          % (cfg["sun_elev"], cfg["sun_azim"], cfg["sun_energy"], cfg["sun_angle"]),
          flush=True)
    return ob


def _fog_material(cfg):
    """Two stacked exponential layers + optional banks, in one volume shader."""
    name = TAG + "FogVolume"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = _n(nt, "ShaderNodeOutputMaterial", "out", (760, 0))
    pv = _n(nt, "ShaderNodeVolumePrincipled", "vol", (520, 0))
    _lnk(nt, pv.outputs["Volume"] if "Volume" in pv.outputs else pv.outputs[0],
         out.inputs["Volume"])
    col = tuple(cfg["fog_color"])
    for key, val in (("Color", (col[0], col[1], col[2], 1.0)),
                     ("Anisotropy", float(cfg["fog_aniso"])),
                     ("Density", 1.0)):
        sock = pv.inputs.get(key)
        if sock is not None:
            try:
                sock.default_value = val
            except Exception:                                      # noqa: BLE001
                pass
    if "Absorption Color" in pv.inputs:
        pv.inputs["Absorption Color"].default_value = (0.0, 0.0, 0.0, 1.0)

    geo = _n(nt, "ShaderNodeNewGeometry", "geo", (-1000, 0))
    sep = _n(nt, "ShaderNodeSeparateXYZ", "sep", (-820, 0))
    _lnk(nt, geo.outputs["Position"], sep.inputs["Vector"])
    zc = _math(nt, "MAXIMUM", sep.outputs["Z"], 0.0, "zmax", (-640, 60))

    def layer(hname, dens, y):
        inv = _math(nt, "MULTIPLY", zc, -1.0 / max(1.0, float(hname)), "inv" + str(y),
                    (-470, y))
        pw = _math(nt, "POWER", None, None, "exp" + str(y), (-300, y))
        pw.node.inputs[0].default_value = _E
        _lnk(nt, inv, pw.node.inputs[1])
        mul = _math(nt, "MULTIPLY", pw, float(dens), "d" + str(y), (-140, y))
        return mul

    d1 = layer(cfg["fog_height"], float(cfg["fog_density"]), 120)

    # banks: a slow large-scale noise on the horizontal position, only ever
    # multiplying the *first* layer, so the second stays a clean ceiling
    if cfg.get("fog_noise", 0.0) > 0.001:
        nz = _n(nt, "ShaderNodeTexNoise", "banks", (-640, -220))
        nz.inputs["Scale"].default_value = 1.0 / max(8.0, float(cfg["fog_bank"]))
        nz.inputs["Detail"].default_value = 2.0
        nz.inputs["Roughness"].default_value = 0.5
        _lnk(nt, geo.outputs["Position"], nz.inputs["Vector"])
        k = float(cfg["fog_noise"])
        mr = _maprange(nt, nz.outputs["Fac"], 0.34, 0.68, 1.0 - 0.75 * k, 1.0 + 1.5 * k,
                       "bankmr", (-470, -220))
        d1 = _math(nt, "MULTIPLY", d1, mr, "d1bank", (-40, 40))

    total = d1
    if cfg.get("fog_layer2", 0.0) > 0.0:
        d2 = layer(cfg.get("fog_layer2_h", 120.0),
                   float(cfg["fog_density"]) * float(cfg["fog_layer2"]), -40)
        total = _math(nt, "ADD", d1, d2, "dtot", (140, 0))

    _lnk(nt, total, pv.inputs["Density"])
    m["wx"] = "fog"
    return m


def apply_fog(scene, cfg, center=(0, 0), extent=None, radius=1200.0):
    """Replace the atmosphere with this weather's exponential fog.

    `hd_light.haze()` builds an object called ``Atmosphere``; that is removed
    first, so calling this after ``hd_light.apply()`` *supersedes* the rig's
    haze instead of stacking a second medium on top of it.
    """
    for ob in list(bpy.data.objects):
        if ob.name == "Atmosphere" or ob.name.startswith("Atmosphere."):
            bpy.data.objects.remove(ob, do_unlink=True)
    for ob in list(bpy.data.objects):
        if ob.name.startswith(TAG + "Fog"):
            bpy.data.objects.remove(ob, do_unlink=True)

    # the box only needs to be wider than the farthest thing the camera can see;
    # 2.4x the build radius covers a 947 m city from 700 m up
    ext = float(extent) if extent else max(1200.0, 2.4 * float(radius))
    ext = max(ext, 1200.0)
    me = bpy.data.meshes.new(TAG + "FogBox")
    h = ext * 0.5
    v = [(-h, -h, -20.0), (h, -h, -20.0), (h, h, -20.0), (-h, h, -20.0),
         (-h, -h, ext), (h, -h, ext), (h, h, ext), (-h, h, ext)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
         (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(v, [], f)
    me.update()
    m = _fog_material(cfg)
    me.materials.append(m)
    ob = _new_obj(TAG + "Fog", me)
    ob.location = (float(center[0]), float(center[1]), 0.0)
    ob.visible_shadow = False
    print("[wx] fog sigma=%.5f H=%.0f layer2=%.2f@%.0f  T(20m)=%.2f T(50m)=%.2f "
          "T(1km)=%.2f"
          % (cfg["fog_density"], cfg["fog_height"], cfg["fog_layer2"],
             cfg["fog_layer2_h"], transmittance(cfg, 20), transmittance(cfg, 50),
             transmittance(cfg, 1000)), flush=True)
    return ob


def apply_flash(scene, cfg, flash=None):
    """The 'exposure frame': lightning as a short, huge, cool key light.

    `flash` 0..1 scales the flash sun, the cloud card and an exposure lift.  A
    renderer that animates weather can call this per frame (a bolt is 1-2
    frames of 40 ms); a still uses ``cfg['flash']``.
    """
    f = float(cfg["flash"] if flash is None else flash)
    f = max(0.0, min(1.5, f))
    ob = bpy.data.objects.get(TAG + "FlashSun")
    out = dict(flash=f, energy=0.0, exposure=float(cfg["exposure"]))
    if ob is not None and ob.type == "LIGHT":
        ob.data.energy = 140.0 * f
        out["energy"] = ob.data.energy
    try:
        scene.view_settings.exposure = float(cfg["exposure"]) + 0.55 * f
        out["exposure"] = scene.view_settings.exposure
    except Exception:                                              # noqa: BLE001
        pass
    # the cloud card behind the channel
    g = bpy.data.objects.get(TAG + "BoltGlow")
    if g is not None and g.data.materials:
        for n in g.data.materials[0].node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED" and "Emission Strength" in n.inputs:
                n.inputs["Emission Strength"].default_value = 3.0 * (0.15 + 2.2 * f)
    if f > 0.001:
        print("[wx] flash f=%.2f E=%.0f exposure=%.2f"
              % (f, out["energy"], out["exposure"]), flush=True)
    return out


def apply_post(scene, cfg):
    """Exposure + saturation (absolute, spliced into the compositor chain)."""
    try:
        scene.view_settings.exposure = float(cfg["exposure"])
    except Exception:                                              # noqa: BLE001
        pass
    try:
        scene.view_settings.view_transform = "AgX"
    except Exception:                                              # noqa: BLE001
        pass
    sat = float(cfg["saturation"])
    g = getattr(scene, "compositing_node_group", None)
    nt = g
    if nt is None:
        try:
            nt = scene.node_tree
        except Exception:                                          # noqa: BLE001
            nt = None
    if nt is None or not len(nt.nodes):
        return dict(saturation=sat, spliced=False)
    out = None
    for n in nt.nodes:
        if n.bl_idname in ("NodeGroupOutput", "CompositorNodeComposite"):
            out = n
    if out is None or "Image" not in out.inputs or not out.inputs["Image"].is_linked:
        return dict(saturation=sat, spliced=False)
    # neutralise whatever saturation the rig set, so ours is absolute
    for n in nt.nodes:
        if n.bl_idname == "CompositorNodeHueSat" and n is not None \
                and not n.name.startswith(TAG):
            try:
                n.inputs["Saturation"].default_value = 1.0
            except Exception:                                      # noqa: BLE001
                pass
    node = nt.nodes.get(TAG + "Sat")
    if node is None:
        try:
            node = nt.nodes.new("CompositorNodeHueSat")
            node.name = TAG + "Sat"
            node.location = (320, 0)
        except Exception:                                          # noqa: BLE001
            return dict(saturation=sat, spliced=False)
    node.inputs["Saturation"].default_value = sat
    sock = out.inputs["Image"]
    # Idempotent splice: upstream -> WX_Sat -> Image.  Compare nodes by *name*:
    # bpy hands out a fresh python wrapper on every attribute access, so an
    # `is` test would always say "different node" and link the node to itself
    # (which silently renders the whole frame black).
    inp = node.inputs["Image"]
    up = inp.links[0].from_socket if inp.is_linked else None
    if up is not None and up.node.name == node.name:
        up = None                                    # stale self-link
    if up is None and sock.is_linked:
        cand = sock.links[0].from_socket
        if cand.node.name != node.name:
            up = cand
    for lk in list(inp.links):
        nt.links.remove(lk)
    if up is not None:
        _lnk(nt, up, inp)
    _lnk(nt, node.outputs["Image"], sock)
    return dict(saturation=sat, spliced=True)


def apply_atmos(scene, cfg, center=(0, 0), extent=None, flash=None, sky=True):
    """sky + sun + flash + fog + grade: the whole non-geometry half of a state."""
    if sky:
        try:
            apply_sky(scene, cfg)
        except Exception as exc:                                   # noqa: BLE001
            print("[wx] sky failed:", exc, flush=True)
    sun = apply_sun(scene, cfg)
    fill = apply_fill(scene, cfg)
    fl = apply_flash(scene, cfg, flash)
    fog = apply_fog(scene, cfg, center=center, extent=extent,
                    radius=float(cfg.get("radius", 1200.0)))
    post = apply_post(scene, cfg)
    return dict(sun=sun, fill=fill, fog=fog, flash=fl, post=post)


def _sky_fill(scene, cfg):
    """A huge, shadowless card *above* the town: the missing half of the fill.

    `hd_light.bounce()` puts its card at z=0.30 emitting upward, so it lights
    undersides -- eaves, cart bellies, the shady side of an awning -- and nothing
    a 52-degree camera actually looks at.  Paving, roof slopes and upper walls
    are lit by the *dome*, and inside a weather state the dome's diffuse share
    (`hd_sky`'s flat ambient world) is the only fill that exists.  Measured, that
    was not enough: a clear morning's shadowed paving came out at 8/255.

    This is the sky half of a two-card fill (sky above, stone below).  It has no
    shadow and no specular, it is tinted by the weather's own fog colour, and it
    is scaled by `cfg["sky_fill"]` against hd_light's `BOUNCE_W_PER_RATIO`, so
    the brightness of "the sky fell on the town" is one number per weather
    instead of a per-shot fudge.  `sky_fill=0` removes it.
    """
    ob = bpy.data.objects.get(TAG + "SkyFill")
    try:
        import hd_light as _L
        k = float(_L.BOUNCE_W_PER_RATIO)
        size = float(_L.BOUNCE_SIZE)
    except Exception:                                              # noqa: BLE001
        k, size = 2.45e7, 1700.0
    watts = float(cfg.get("sky_fill", 0.0)) * k
    if watts <= 0.0:
        if ob is not None:
            bpy.data.objects.remove(ob, do_unlink=True)
        return None
    if ob is None or ob.type != "LIGHT":
        if ob is not None:
            bpy.data.objects.remove(ob, do_unlink=True)
        ld = bpy.data.lights.new(TAG + "SkyFillData", "AREA")
        ld.shape = "SQUARE"
        ld.use_shadow = False
        ld.specular_factor = 0.0
        ob = bpy.data.objects.new(TAG + "SkyFill", ld)
        _link(ob)
    d = ob.data
    d.shape = "SQUARE"
    d.size = size
    d.energy = watts
    try:
        d.color = tuple(float(c) for c in cfg["fog_color"])[:3]
    except Exception:                                              # noqa: BLE001
        pass
    d.use_shadow = False
    d.specular_factor = 0.0
    d.diffuse_factor = 1.0
    # a light's emission axis is its local -Z: default rotation points it down
    cx, cy = cfg.get("center", (0.0, 0.0))
    ob.location = (float(cx), float(cy), float(cfg.get("_ground_z", 0.0)) + 62.0)
    ob.rotation_euler = Euler((0.0, 0.0, 0.0), "XYZ")
    for attr, val in (("visible_camera", False), ("visible_glossy", False),
                      ("visible_transmission", False),
                      ("visible_volume_scatter", False), ("visible_shadow", False)):
        try:
            setattr(ob, attr, val)
        except Exception:                                          # noqa: BLE001
            pass
    print("[wx] sky_fill %.3f -> %.3g W @%.0fm" % (float(cfg["sky_fill"]), watts,
                                                   ob.location[2]), flush=True)
    return ob


def apply_fill(scene, cfg):
    """The rig's ground-bounce card and contact shadows (hd_light's `bounce`/`contact`).

    `hd_light.build_rig` always pairs a sun with an area bounce card; a weather
    state built without it has shadows three stops deeper than the rest of the
    project, which is what made the first sheets read as a black town.
    """
    mul = float(cfg.get("bounce_mul", 1.0))
    n = 0
    if _sky_fill(scene, cfg) is not None:
        n += 1
    if mul <= 0.0:
        return n
    try:
        import hd_light as _L
    except Exception:                                              # noqa: BLE001
        return n
    preset = cfg.get("grade_preset", "morning_town")
    try:
        _L.bounce(preset, energy_mul=mul)
        n += 1
    except Exception as exc:                                       # noqa: BLE001
        print("[wx] bounce failed:", exc, flush=True)
    try:
        _L.contact(preset, scene)
        n += 1
    except Exception as exc:                                       # noqa: BLE001
        print("[wx] contact failed:", exc, flush=True)
    return n


# =========================================================================== #
#  8.  material response
# =========================================================================== #
# Which materials may get wet / snowy.  Ground, roof, stone, bark and foliage
# are the surfaces that actually see rain and snow; everything else (glass,
# cloth, iron, water, glow) is explicitly excluded.
_ALLOW = ("stone", "stone_pale", "stone_warm", "tile", "slate", "cobble", "flag",
          "ground", "dirt", "earth", "road", "yard", "paving", "brick", "gravel",
          "sand", "rock", "marble", "thatch", "terrain", "plaster",
          "bark", "bark_dark", "bark_pale", "leaf", "leaf_mid", "leaf_dark",
          "leaf_autumn", "moss", "grass", "foliage", "trunk")
_SKIP = ("glass", "water", "river", "sea", "cloth", "banner", "iron", "metal",
         "gold", "glow", "fire", "flame", "torch", "lantern", "sky", "atmos",
         "fog", "rain", "flake", "snowp", "window", "mirror", "lamp")


def _kind_of(key, mat):
    """Canonical surface word for a MAT key / material name, or None to skip."""
    k = str(key if key else (mat.name if mat else "")).strip().lower()
    if k.startswith(TAG.lower()):
        return None
    for s in _SKIP:
        if s in k:
            return None
    for s in _ALLOW:
        if s == k or k.startswith(s) or ("_" + s) in k or s in k:
            return s
    return None


def _eligible(key, mat):
    if mat is None or not getattr(mat, "use_nodes", False) or mat.node_tree is None:
        return None
    if _principled(mat.node_tree) is None:
        return None
    return _kind_of(key, mat)


def _orig(mat, bsdf):
    """Cache the pre-weather shader values on the material (idempotent)."""
    if "wx_rough" not in mat:
        sock = bsdf.inputs.get("Roughness")
        mat["wx_rough"] = float(sock.default_value) if sock is not None else 0.8
        sock = bsdf.inputs.get("Base Color")
        col = tuple(sock.default_value)[:3] if sock is not None else (0.6, 0.6, 0.6)
        mat["wx_base"] = [round(float(c), 5) for c in col]
        sock = bsdf.inputs.get("Specular IOR Level")
        mat["wx_spec"] = float(sock.default_value) if sock is not None else 0.5
        if "wx_bump" not in mat:
            mat["wx_bump"] = 1.0
    return dict(rough=float(mat["wx_rough"]),
                base=tuple(float(x) for x in mat["wx_base"]),
                spec=float(mat["wx_spec"]))


def _bump_node(nt, bsdf):
    sock = bsdf.inputs.get("Normal")
    if sock is not None and sock.is_linked:
        src = sock.links[0].from_node
        if src is not None and src.bl_idname == "ShaderNodeBump":
            return src
    return None


def _color_source(nt, bsdf, my_name):
    """The socket that currently feeds Base Color, unless it is already mine."""
    sock = bsdf.inputs.get("Base Color")
    col = tuple(sock.default_value)[:3] if sock is not None else (0.6, 0.6, 0.6)
    if sock is not None and sock.is_linked:
        src = sock.links[0].from_socket
        if src.node is not None and src.node.name == my_name:
            # already wrapped: the upstream colour is what feeds my mix's Color1
            mine = nt.nodes.get(my_name)
            if mine is not None:
                for s in mine.inputs:
                    if s.name == "Color1" and s.is_linked:
                        return s.links[0].from_socket, mine
                return None, mine
        return src, None
    return (col[0], col[1], col[2], 1.0), None


def wet_material(mat, wetness):
    """Make a ground / roof / stone material read as rain-soaked.

    Spliced node chain (all names prefixed ``WX.Wet.``):

        Noise(0.35, object space) -> MapRange      = puddle patch mask
        x wetness                                  = m
        m -> MapRange(damp 0.55*orig, 0.025)       -> Roughness
        Base Color x (0.55,0.56,0.60) at 0.8m      -> darker stone
        ... x (0.18,0.20,0.24) at 0.95m^2          -> standing water
        Bump strength  x (1 - 0.65 m)              -> joints fill with water

    Idempotent: a second call only rewrites the factors.  Returns True when the
    material was modified.
    """
    if not mat or not getattr(mat, "use_nodes", False) or mat.node_tree is None:
        return False
    nt = mat.node_tree
    bsdf = _principled(nt)
    if bsdf is None:
        return False
    kind = _kind_of(mat.name, mat)
    if kind is None:
        return False
    w = max(0.0, min(1.0, float(wetness)))
    o = _orig(mat, bsdf)
    rough_sock = bsdf.inputs.get("Roughness")
    damp = max(0.48, min(0.68, o["rough"] * 0.72))
    pud = 0.240

    if nt.nodes.get("WX.Wet.Mask") is None:
        tc = _n(nt, "ShaderNodeNewGeometry", "WX.Wet.TC", (-1100, -420))
        nz = _n(nt, "ShaderNodeTexNoise", "WX.Wet.Noise", (-940, -420))
        nz.inputs["Scale"].default_value = 0.055
        nz.inputs["Detail"].default_value = 6.0
        nz.inputs["Roughness"].default_value = 0.55
        _lnk(nt, tc.outputs["Position"], nz.inputs["Vector"])
        patch = _maprange(nt, nz.outputs["Fac"], 0.46, 0.63, 0.0, 1.0,
                          "WX.Wet.Patch", (-760, -420))
        mask = _math(nt, "MULTIPLY", patch, w, "WX.Wet.Mask", (-600, -420))
        mr = _maprange(nt, mask, 0.0, 1.0, damp, pud, "WX.Wet.Rough", (-440, -420))
        _lnk(nt, mr, rough_sock)
        # colour: two multiplies, the second only in the puddle cores
        src, mine = _color_source(nt, bsdf, "WX.Wet.Color2")
        f1 = _math(nt, "MULTIPLY", mask, 0.62, "WX.Wet.F1", (-600, -560))
        c1 = _mix(nt, src, (0.86, 0.87, 0.90), f1, "WX.Wet.Color1", (-300, -560),
                  blend="MULTIPLY")
        m2 = _math(nt, "MULTIPLY", mask, mask, "WX.Wet.F2", (-600, -700))
        f2 = _math(nt, "MULTIPLY", m2, 0.70, "WX.Wet.F2b", (-440, -700))
        c2 = _mix(nt, c1, (0.46, 0.49, 0.55), f2, "WX.Wet.Color2", (-120, -560),
                  blend="MULTIPLY")
        _lnk(nt, c2, bsdf.inputs["Base Color"])
        bn = _bump_node(nt, bsdf)
        if bn is not None:
            mat["wx_bump"] = float(bn.inputs["Strength"].default_value)
            red = _maprange(nt, mask, 0.0, 1.0, 1.0, 0.35, "WX.Wet.Bump", (-440, -840))
            mul = _math(nt, "MULTIPLY", red, float(mat["wx_bump"]),
                        "WX.Wet.BumpS", (-280, -840))
            _lnk(nt, mul, bn.inputs["Strength"])
        # a wet surface is glossy but NOT a mirror: at roughness 0.03 the whole
        # plaza turned into a blown-out white sheet of sky
        spec_sock = bsdf.inputs.get("Specular IOR Level") or bsdf.inputs.get("Specular")
        if spec_sock is not None:
            sp = _maprange(nt, mask, 0.0, 1.0, o["spec"], o["spec"] * 0.55,
                           "WX.Wet.Spec", (-440, -1000))
            _lnk(nt, sp, spec_sock)
    else:
        # update in place
        nt.nodes["WX.Wet.Mask"].inputs[1].default_value = w
        r = nt.nodes.get("WX.Wet.Rough")
        if r is not None:
            r.inputs["To Min"].default_value = damp
        c1 = nt.nodes.get("WX.Wet.Color1")
        f1 = nt.nodes.get("WX.Wet.F1")
        if f1 is not None:
            f1.inputs[1].default_value = w * 0.62
        f2 = nt.nodes.get("WX.Wet.F2b")
        if f2 is not None:
            f2.inputs[1].default_value = w * 0.70
        if c1 is not None and not c1.inputs["Color1"].is_linked:
            pass
    return True


def snow_material(mat, cover):
    """Accumulate snow on a material, weighted by how horizontal the surface is.

    The mask is ``up_facing(normal.z) * cover * patch_noise``; that single
    product is what makes roofs and ground go white while the walls stay their
    own colour, without any vertex data or extra geometry:

        Normal.Z -> MapRange(0.30, 0.80)          up-facing weight
        x cover  x Noise(0.55) patch              = m
        m -> mix base colour toward (0.90,0.94,0.99)
        m -> MapRange(orig roughness, 0.86)       (snow is a diffuse white)
        m -> specular down, bump strength down    (snow fills the joints)

    Returns True when the material was modified.
    """
    if not mat or not getattr(mat, "use_nodes", False) or mat.node_tree is None:
        return False
    nt = mat.node_tree
    bsdf = _principled(nt)
    if bsdf is None:
        return False
    kind = _kind_of(mat.name, mat)
    if kind is None:
        return False
    c = max(0.0, min(1.0, float(cover)))
    o = _orig(mat, bsdf)
    # foliage and bark hold snow on top of thin members: accept a much wider
    # normal range so branches read white, not just horizontal tops
    leafy = kind in ("bark", "bark_dark", "bark_pale", "leaf", "leaf_mid",
                     "leaf_dark", "leaf_autumn", "moss", "grass", "foliage", "trunk")
    lo, hi = (0.06, 0.66) if leafy else (0.12, 0.74)
    strength = 0.55 if leafy else 1.0

    if nt.nodes.get("WX.Snow.Mask") is None:
        geo = _n(nt, "ShaderNodeNewGeometry", "WX.Snow.Geo", (-1100, -900))
        sep = _n(nt, "ShaderNodeSeparateXYZ", "WX.Snow.Sep", (-940, -900))
        _lnk(nt, geo.outputs["Normal"], sep.inputs["Vector"])
        # ABS: half the roofs in a mesh library are built with inverted
        # normals, and a 52 deg pitch is |n.z| = 0.61 either way round
        ab = _math(nt, "ABSOLUTE", sep.outputs["Z"], None, "WX.Snow.Abs", (-860, -900))
        up = _maprange(nt, ab, lo, hi, 0.0, 1.0, "WX.Snow.Up", (-780, -900))
        tc = _n(nt, "ShaderNodeNewGeometry", "WX.Snow.TC", (-1100, -1060))
        nz = _n(nt, "ShaderNodeTexNoise", "WX.Snow.Noise", (-940, -1060))
        nz.inputs["Scale"].default_value = 0.05
        nz.inputs["Detail"].default_value = 3.0
        _lnk(nt, tc.outputs["Position"], nz.inputs["Vector"])
        pat = _maprange(nt, nz.outputs["Fac"], 0.36, 0.66, 0.55, 1.0, "WX.Snow.Pat",
                        (-780, -1060))
        m1 = _math(nt, "MULTIPLY", up, pat, "WX.Snow.M1", (-620, -960))
        mask = _math(nt, "MULTIPLY", m1, c * strength, "WX.Snow.Mask", (-460, -960))
        _lnk(nt, mask, _maprange(nt, mask, 0.0, 1.0, 0.0, 1.0, "WX.Snow.Clamp",
                                 (-300, -1120)))
        # colour
        src, mine = _color_source(nt, bsdf, "WX.Snow.Color")
        if mine is not None:
            src = None
        cnode = _mix(nt, src if src is not None else (0.6, 0.6, 0.6, 1.0),
                     (0.90, 0.94, 0.99), mask, "WX.Snow.Color", (-120, -960))
        _lnk(nt, cnode, bsdf.inputs["Base Color"])
        # roughness / specular
        rs = _maprange(nt, mask, 0.0, 1.0, o["rough"], 0.86, "WX.Snow.Rough",
                       (-300, -1240))
        if bsdf.inputs.get("Roughness") is not None:
            _lnk(nt, rs, bsdf.inputs["Roughness"])
        sp = _maprange(nt, mask, 0.0, 1.0, o["spec"], 0.12, "WX.Snow.Spec",
                       (-300, -1340))
        if bsdf.inputs.get("Specular IOR Level") is not None:
            _lnk(nt, sp, bsdf.inputs["Specular IOR Level"])
        bn = _bump_node(nt, bsdf)
        if bn is not None:
            mat["wx_bump"] = float(bn.inputs["Strength"].default_value)
            red = _maprange(nt, mask, 0.0, 1.0, 1.0, 0.30, "WX.Snow.Bump", (-300, -1440))
            mul = _math(nt, "MULTIPLY", red, float(mat["wx_bump"]),
                        "WX.Snow.BumpS", (-140, -1440))
            _lnk(nt, mul, bn.inputs["Strength"])
    else:
        m1 = nt.nodes.get("WX.Snow.M1")
        if m1 is not None:
            # keep the up-facing weight, replace the cover factor
            sm = nt.nodes.get("WX.Snow.Mask")
            src = m1.inputs[0].links[0].from_socket if m1.inputs[0].is_linked else None
            if sm is not None:
                sm.inputs[1].default_value = c * strength
        n = nt.nodes.get("WX.Snow.Up")
        if n is not None:
            n.inputs["From Min"].default_value = lo
            n.inputs["From Max"].default_value = hi
    return True


def _scene_materials():
    """Every material actually assigned to a mesh in the current scene."""
    out = []
    sc = bpy.context.scene if IN_BLENDER else None
    if sc is None:
        return out
    try:
        obs = list(sc.objects)
    except Exception:                                          # noqa: BLE001
        return out
    for ob in obs:
        if ob.type != "MESH":
            continue
        for slot in getattr(ob, "material_slots", ()):
            m = slot.material
            if m is not None:
                out.append((m.name, m))
    return out


def apply_materials(MAT, cfg):
    """Apply wetness then snow cover.  Returns the number of materials changed.

    ``MAT`` may be the city palette dict, a list of materials, or ``None``; in
    every case the materials actually assigned to scene objects are merged in.
    That matters because a city can hold materials the palette dict never
    mentions -- ``capital_hd_glue.house_mats`` mints a separate
    ``hu_roof_<...>`` material per roof tint, and those are the ones on the
    roofs.  Weathering a dict keyed by ``tile`` alone leaves every roof dry.
    """
    wetness = float(cfg.get("wetness", 0.0))
    cover = float(cfg.get("snow_cover", 0.0))
    items = []
    if MAT is None:
        items = [(m.name, m) for m in bpy.data.materials]
    elif isinstance(MAT, dict):
        items = list(MAT.items())
    elif isinstance(MAT, (list, tuple, set)):
        items = [(getattr(m, "name", ""), m) for m in MAT]
    else:
        items = [(getattr(MAT, "name", ""), MAT)]
    seen = set()
    uniq = []
    for key, mat in items:
        if mat is None or mat.name in seen:
            continue
        seen.add(mat.name)
        uniq.append((key, mat))
    for key, mat in _scene_materials():
        if mat.name in seen:
            continue
        seen.add(mat.name)
        uniq.append((key, mat))
    items = uniq
    n = 0
    for key, mat in items:
        if _eligible(key, mat) is None:
            continue
        touched = False
        if wetness > 0.001 or mat.node_tree.nodes.get("WX.Wet.Mask") is not None:
            touched |= wet_material(mat, wetness)
        if cover > 0.001 or mat.node_tree.nodes.get("WX.Snow.Mask") is not None:
            touched |= snow_material(mat, cover)
        if touched:
            n += 1
    print("[wx] materials wet=%.2f snow=%.2f -> %d changed" % (wetness, cover, n),
          flush=True)
    return n


def reset_materials(MAT=None):
    """Neutralise the weather chain on every eligible material.  Returns count."""
    items = ([(m.name, m) for m in bpy.data.materials] if MAT is None
             else (list(MAT.items()) if isinstance(MAT, dict)
                   else [(getattr(m, "name", ""), m) for m in (MAT or [])]))
    seen = set()
    merged = []
    for key, mat in list(items) + _scene_materials():
        if mat is None or mat.name in seen:
            continue
        seen.add(mat.name)
        merged.append((key, mat))
    n = 0
    for key, mat in merged:
        if _eligible(key, mat) is None:
            continue
        nt = mat.node_tree
        hit = False
        for nm in ("WX.Wet.Mask", "WX.Snow.Mask"):
            nd = nt.nodes.get(nm)
            if nd is not None:
                nd.inputs[1].default_value = 0.0
                hit = True
        if hit:
            n += 1
    return n


# =========================================================================== #
#  9.  wind sway (trees)
# =========================================================================== #
def sway(objects, cfg, t=0.0, factor=1.0):
    """Lean objects with the wind, pivoting at their own origin.

    Geometry cannot be animated in a still, but a bent silhouette is most of
    what sells a storm: rain at 30 deg and trees standing straight look wrong
    together.  `factor` lets a caller differentiate heavy trunks (0.5) from
    crowns (1.0).  Idempotent -- the first call stores each object's rest
    matrix, and later calls transform from that.
    """
    sp = float(cfg.get("_wind_speed", math.hypot(*cfg.get("wind", (0, 0)))))
    if sp <= 0.02 or not objects:
        return 0
    gust = float(cfg.get("gust", 0.0))
    amp = math.radians(min(24.0, 1.35 * sp + 3.2 * gust * sp))
    osc = 0.74 + 0.26 * math.sin(t * 2.3 + 0.7)
    ang = amp * float(factor) * osc
    az = math.radians(cfg.get("_wind_azim", 0.0))
    axis = Vector((math.cos(az), -math.sin(az), 0.0)).normalized()
    n = 0
    for ob in objects:
        if ob is None:
            continue
        if "wx_rest" not in ob:
            ob["wx_rest"] = [float(v) for row in ob.matrix_world for v in row]
        rest = Matrix([ob["wx_rest"][i * 4:i * 4 + 4] for i in range(4)])
        p = rest.to_translation()
        m = (Matrix.Translation(p) @ Matrix.Rotation(ang, 4, axis)
             @ Matrix.Translation(-p) @ rest)
        ob.matrix_world = m
        n += 1
    return n


# =========================================================================== #
#  10.  self-test / CLI
# =========================================================================== #
def selftest():
    """No-Blender-needed sanity: state maths, transmittance, JSON."""
    print("[wx] version", VERSION)
    print(table())
    bad = []
    for n in ORDER:
        c = state(n)
        for k in ("sun_energy", "sun_color", "sun_elev", "sun_azim", "sky_preset",
                  "fog_density", "fog_height", "fog_color", "exposure",
                  "saturation", "wetness", "snow_cover", "wind", "particle_kind",
                  "particle_rate", "flash"):
            if k not in c:
                bad.append((n, k))
        t20, t50 = transmittance(c, 20), transmittance(c, 50)
        print("[wx] %-10s sun=%5.1f@%.0f  sigma=%.5f H=%.0f  T20=%.2f T50=%.2f "
              "vis=%.0fm  tilt=%.0fdeg" % (n, c["sun_energy"], c["sun_elev"],
                                           c["fog_density"], c["fog_height"],
                                           t20, t50, c["_vis_m"], c["_rain_tilt"]))
    if bad:
        print("[wx] MISSING KEYS:", bad)
    else:
        print("[wx] all 16 required keys present in all 8 states")
    c = state("fog")
    print("[wx] fog spec check: T(20m)=%.3f (visible)  T(50m)=%.3f (gone)"
          % (transmittance(c, 20), transmittance(c, 50)))
    c = state("storm")
    print("[wx] storm rain tilt = %.1f deg (target 30)" % c["_rain_tilt"])
    print("[wx] json ->", dump_json())
    return 0 if not bad else 1


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cmd = argv[0] if argv else "selftest"
    if cmd == "selftest":
        return selftest()
    if cmd == "table":
        print(table())
        return 0
    if cmd == "json":
        print(dump_json())
        return 0
    if cmd == "build":
        name = argv[1] if len(argv) > 1 else "rain"
        r = build(bpy.context.scene, name)
        print("[wx]", r["objects_n"], "objects", r["tris"], "tris")
        return 0
    print("commands: selftest | table | json | build <weather>")
    return 1


if __name__ == "__main__":
    _main()
