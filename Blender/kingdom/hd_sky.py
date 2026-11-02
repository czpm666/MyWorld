r"""hd_sky.py -- the procedural sky dome: gradient, horizon band, Mie halo, a
cloud deck that survives a wide shot, aerial perspective, night sky.

    import hd_sky
    cfg = hd_sky.world(scene, "golden_street")        # world only
    hd_sky.sun(scene, cfg)                            # + the key light
    hd_sky.post(scene, cfg)                           # + AP and glare
    hd_sky.atmosphere(cfg)                            # + hd_atmosphere's haze

    # or one call, which is what a driver should use:
    hd_sky.apply_all(scene, "golden_street")

`world(scene, preset, **over)` is the frozen entry point: every preset key can
be overridden by keyword, and `hd_weather` drives it exactly that way
(`hd_sky.world(scene, cfg["sky_preset"], **cfg["sky"])`), so the old key names
-- `elevation`, `azimuth`, `haze`, `glow`, `strength`, `gain`, `sat`,
`ambient`, `clouds`, `cloud_scale`, `cloud_soft`, `cloud_alt`, `cloud_lift`,
`haze_mix`, `haze_band`, `sun_disc` -- all still work and all still mean what
they meant.  New keys are additive; nothing was renamed away.


WHY THIS VERSION EXISTS
-----------------------
Three real bugs, not a taste problem:

1. **The elevation coordinate was wrong.**  `Generated` in a world shader is
   already the (unit) view direction -- measured, see the Numbers section --
   but v1 did `normalize(2*Generated - 1)`.  That maps every pixel into the
   +X+Y+Z octant: the "elevation" it produced never fell below 0.577, so the
   horizon band and the cloud projection were operating on a coordinate that
   had already been flattened.  That is why the sky read as one smooth paste
   with no layers, no horizon line and no clouds in a wide shot.  The fix is
   `dir = normalize(Generated)`, i.e. z = sin(elevation).

2. **Nothing was authored for 0-12 deg of elevation.**  A wide shot
   (`overview` / `aerial` / `castle`) puts the horizon in the top third of the
   frame, so the only sky it ever shows is the bottom 10 deg of the dome, where
   v1 had a 4 deg haze band and a cloud mask that only turned on at 6 deg.
   Section 5 below now owns that band explicitly.

3. **No sun-dependent structure at all.**  A flat gradient cannot tell you
   where the sun is.  Section 4 adds a two-lobe Mie halo plus an air-mass term,
   Section 6 lights the cloud deck from the sun side, and Section 7 fuses the
   deck into the horizon band instead of stopping above it.


WHAT IS WHERE  (build order, bottom to top)
-------------------------------------------
  1. direction      Generated -> z = sin(elevation)
  2. gradient       horizon -> zenith, pow() shaped
  3. horizon band   additive exp() band, keeps the horizon brighter than the sky
  4. Mie            wide Gaussian + narrow core, both air-mass boosted
  5. sun disc       additive, so it clips to white like a real sun
  6. clouds         three altitude bands + a lower deck, shaded by the sun
  7. fusion         haze veil + a tight 0-2 deg fuse into the horizon band
  8. colour         saturation (AgX pulls channel ratios apart, see Numbers)
  9. night          stars, a phased moon, city glow, ground bounce
 10. output         strength * gain, LightPath split for the ambient ray

THE NUMBERS  (measured, do not fiddle without re-measuring)
----------------------------------------------------------
* `gain` and `sat` are calibrated against the *display* value of the sky band,
  not against linear colour.  Scene exposure is -2.55 and AgX is the view
  transform; the sky target is a display value of 0.55-0.60 in the R channel.
  1.0 * gain 14.0 lands there.  The relation is not linear in display space:

      gain   1.0   2.0   3.2   6.0  10.0  14.0  16.0
      R      0.171 0.228 0.284 0.383 0.492 0.556 0.591

  so gain is *not* an exposure knob, it is a lookup-table knob.  If a preset
  needs the sky darker, move `zenith`/`horizon`, not `gain`.
* `sat = 1.55` is the AgX compensation: AgX desaturates highlights, so a sky
  authored at sat 1.0 renders grey-blue.  `ambient = 0.22` is how much of the
  dome the *diffuse* rays see; the camera ray always sees the full sky.
* `Geometry.Incoming` in a world shader is the *negated* view direction
  (it points back at the camera), so it is unusable directly; `Generated` is
  the view direction with |v| = 1.  Measured on 5.2.3 LTS: Generated.z at
  y=0.98/0.70/0.50 of a horizon-locked 16 mm frame was +0.491/+0.234/-0.006,
  i.e. exactly sin(elevation) for the +30/+13.5/0 degree rows.
* EEVEE renders the sky at `taa_render_samples`; nothing here is animated, so
  the dome is cheap -- 0.7-1.9 s for 640x360 on the lab box.
"""
import math
import os
import sys

import bpy

_TAU = math.pi * 2.0


# =========================================================================== #
#  presets
# =========================================================================== #
#: Every preset is a full description of one lighting *and* seeing situation:
#: the key light, the dome, the deck, the grade and the exposure.  `exposure`
#: is applied by `apply_all()` only -- `world()` never touches the scene's
#: exposure, because that is the driver's business.
BASE = dict(
    # --- key light ---------------------------------------------------------
    sun_elev=22.0, sun_azim=-58.0, sun_energy=77.0,
    sun_color=(1.0, 0.870, 0.720), sun_angle=0.60,
    # --- dome --------------------------------------------------------------
    zenith="#1b4a80", horizon="#a9c8dc", haze="#c2d0d8",
    strength=1.00, gain=14.0, sat=1.55, ambient=1.00,
    # `gain` scales the *dome* (camera rays) only.  `fill` is the absolute
    # world-datablock strength that lights everything else (diffuse rays); it is
    # calibrated per preset so a surface in shade lands at SHADOW_TARGET.
    # `ambient` is a *multiplier* on `fill` -- 1.0 by default, so a caller that
    # passes ambient=0.5 means "half the fill", not "a magic number that also
    # moves when gain changes".  See _ambient_world().
    fill=2.40,
    # --- horizon band / Mie -------------------------------------------------
    glow=0.55,            # broad sun-ward brightening (the old knob)
    halo_wide=0.10,       # Mie: wide aureole amplitude (linear, on a ~0.035 sky)
    halo_core=0.40,       # Mie: narrow core right at the disc
    halo_scale=0.10,      # <-- the aureole is a *fraction* of the sky magnitude:
                          #     the dome is multiplied by gain=14 later, so a
                          #     halo authored at 0.4+ clipped to a hard white
                          #     disc with a visible rim.  One dial, all presets.
    halo_w_w=0.34,        # ... wide Gaussian sigma, radians (~19 deg)
    halo_c_w=0.075,       # ... core Gaussian sigma, radians (~4.3 deg)
    mie_g_wide=0.72, mie_g_core=0.94,
    airmass=0.60,         # how much a low sun reddens/spreads its own halo
    disc_gain=1.0, sun_disc=1.0,
    # --- cloud deck --------------------------------------------------------
    clouds=0.62, cloud_scale=0.50, cloud_soft=0.30,
    cloud_alt=-0.008, cloud_rise=0.020, cloud_lift=1.0,
    cloud_low=0.55,       # extra cover in the 0-6 deg band (perspective pile-up)
    cloud_bank=0.55,      # solidity of the flat deck at 0-2 deg
    cloud_low_top=0.100,  # the band ends here (0.1 = 5.7 deg)
    cloud_col_low="#c9d2dc", cloud_col_high="#ffffff", cloud_shade="#8ea2b8",
    # --- haze --------------------------------------------------------------
    haze_mix=0.35, haze_band=0.060, haze_fuse=0.048, fuse_mix=0.62,
    # --- night -------------------------------------------------------------
    stars=0.0, star_scale=46.0,
    moon=0.0, moon_elev=34.0, moon_azim=118.0, moon_size=0.0042, moon_phase=0.45,
    moon_col="#e8eeff", moon_halo=0.35,
    city_glow=0.0, city_col="#ffb06a", city_elev=12.0, city_width=0.055,
    ground_glow=0.0,
    # --- grade -------------------------------------------------------------
    exposure=-2.55,
    # --- aerial perspective (see aerial_perspective()) ---------------------
    ap=0.85, ap_start=500, ap_depth=6100, ap_gamma=1.0,
    ap_near="#c2d0d8", ap_far=None, ap_warm=0.35,
    # --- post --------------------------------------------------------------
    flare=0.0, flare_thr=18.0, flare_type="FOG_GLOW",
)

#: The ten presets.  Ordered as a day: dawn, morning, noon, afternoon, overcast,
#: dusk, night, storm, fog, sunshower.  `WEATHER` below maps hd_weather's eight
#: states onto these.
PRESETS = {

    # 1. dawn_cold -- the sun is still behind the ridge, everything is blue and
    #    the deck is lit only by the sky, so it goes violet-grey at the base.
    "dawn_cold": dict(
        sun_elev=2.2, sun_azim=-96.0, sun_energy=34.0,
        sun_color=(1.00, 0.560, 0.330), sun_angle=0.75,
        zenith="#12335c", horizon="#8fa9bd", haze="#b8c4cc",
        gain=34.30, sat=1.62, strength=0.98, fill=13.88,
        glow=0.85, halo_wide=0.13, halo_core=0.46, airmass=1.00,
        clouds=0.66, cloud_scale=0.46, cloud_soft=0.34,
        cloud_low=0.70, cloud_bank=0.70, cloud_low_top=0.115,
        cloud_col_low="#c9c2cc", cloud_col_high="#e8dcd8",
        cloud_shade="#6c7f96",
        haze_mix=0.46, haze_band=0.075, haze_fuse=0.040, fuse_mix=0.60,
        ap=0.95, ap_start=400, ap_depth=5000, ap_near="#8ea3b4",
        ap_warm=0.55, exposure=-2.10,
    ),

    # 2. morning_town -- the reference look: 20 km visibility, warm low sun,
    #    crisp cumulus deck that starts right at the horizon.
    "morning_town": dict(
        sun_elev=34.0, sun_azim=112.0, sun_energy=96.0,
        sun_color=(1.00, 0.862, 0.706), sun_angle=1.10,
        zenith="#1b5b9c", horizon="#a9cee2", haze="#c3d2d6",
        gain=46.25, sat=1.55, strength=1.00, fill=10.11,
        glow=0.58, halo_wide=0.09, halo_core=0.36, airmass=0.55,
        clouds=0.62, cloud_scale=0.50, cloud_soft=0.30,
        cloud_low=0.50, cloud_bank=0.50, cloud_low_top=0.095,
        cloud_col_low="#cbd4de", cloud_col_high="#ffffff",
        cloud_shade="#8ea4bb",
        haze_mix=0.34, haze_band=0.055, haze_fuse=0.046, fuse_mix=0.62,
        ap=0.75, ap_start=500, ap_depth=6100, ap_near="#93aabb",
        ap_warm=0.30, exposure=-2.55,
    ),

    # 3. noon_harsh -- small hard sun, deep blue zenith, a high thin deck that
    #    is white anyway; every edge in the town gets a hard shadow.
    "noon_harsh": dict(
        sun_elev=64.0, sun_azim=8.0, sun_energy=120.0,
        sun_color=(1.00, 0.975, 0.945), sun_angle=0.32,
        zenith="#0d3f78", horizon="#9dc0d8", haze="#c6d4dc",
        gain=75.93, sat=1.62, strength=1.04, fill=9.52,
        glow=0.34, halo_wide=0.06, halo_core=0.32, airmass=0.22,
        clouds=0.42, cloud_scale=0.62, cloud_soft=0.22,
        cloud_low=0.30, cloud_bank=0.38, cloud_alt=0.030,
        cloud_col_low="#eef4f8", cloud_col_high="#ffffff",
        cloud_shade="#b6c6d4",
        haze_mix=0.26, haze_band=0.042, haze_fuse=0.020, fuse_mix=0.45,
        ap=0.62, ap_start=800, ap_depth=7700, ap_near="#9fb6c6",
        ap_warm=0.18, exposure=-2.85,
    ),

    # 4. golden_street -- sun 8 deg up, haze thick and warm, the deck is lit
    #    from underneath so its bases glow orange.
    "golden_street": dict(
        sun_elev=8.0, sun_azim=-74.0, sun_energy=88.0,
        sun_color=(1.00, 0.640, 0.375), sun_angle=0.55,
        zenith="#24446e", horizon="#c9a887", haze="#d3b795",
        gain=30.30, sat=1.50, strength=0.96, fill=12.88,
        glow=1.00, halo_wide=0.16, halo_core=0.50, airmass=1.15,
        clouds=0.70, cloud_scale=0.44, cloud_soft=0.36,
        cloud_low=0.72, cloud_bank=0.72, cloud_low_top=0.125,
        cloud_col_low="#f0c79a", cloud_col_high="#fde3c0",
        cloud_shade="#7b7386",
        haze_mix=0.56, haze_band=0.090, haze_fuse=0.048, fuse_mix=0.66,
        ap=1.00, ap_start=300, ap_depth=4400, ap_near="#b39a86",
        ap_warm=0.75, exposure=-2.42, flare=0.22,
    ),

    # 5. overcast_soft -- no sun disc, no halo, a 100% deck: the dome *is* the
    #    light source, so ambient has to carry the scene.
    "overcast_soft": dict(
        sun_elev=40.0, sun_azim=178.0, sun_energy=7.0,
        sun_color=(0.86, 0.905, 0.955), sun_angle=16.0,
        zenith="#7b8a96", horizon="#b9c3c9", haze="#c1c9cd",
        gain=20.73, sat=1.10, strength=1.20, fill=4.47,
        glow=0.10, halo_wide=0.02, halo_core=0.03, airmass=0.0,
        sun_disc=0.0,
        clouds=1.00, cloud_scale=0.20, cloud_soft=0.56, cloud_alt=0.0,
        cloud_low=0.55, cloud_bank=0.80, cloud_low_top=0.140,
        cloud_col_low="#c8cfd4", cloud_col_high="#dae0e4",
        cloud_shade="#a2adb6",
        haze_mix=0.58, haze_band=0.100, haze_fuse=0.060, fuse_mix=0.70,
        ap=0.55, ap_start=500, ap_depth=5000, ap_near="#aeb8be",
        ap_warm=0.10, exposure=-4.00,
    ),

    # 6. dusk_city -- sun 3 deg under the ridge, the dome is the only light.
    #    Cool zenith against a hot horizon, and the deck goes violet.
    "dusk_city": dict(
        sun_elev=-1.0, sun_azim=-86.0, sun_energy=6.0,
        sun_color=(1.00, 0.470, 0.290), sun_angle=1.20,
        zenith="#161f46", horizon="#c9764a", haze="#b5825f",
        gain=11.34, sat=1.42, strength=0.92, fill=15.72,
        glow=1.30, halo_wide=0.15, halo_core=0.45, airmass=1.60,
        clouds=0.74, cloud_scale=0.40, cloud_soft=0.30,
        cloud_low=0.85, cloud_bank=0.80, cloud_low_top=0.150,
        cloud_col_low="#e08a5a", cloud_col_high="#f2b48c",
        cloud_shade="#4c4a63",
        haze_mix=0.50, haze_band=0.085, haze_fuse=0.055, fuse_mix=0.72,
        ap=1.00, ap_start=400, ap_depth=5500, ap_near="#7d6e78",
        ap_warm=0.65, city_glow=0.35, exposure=-1.85, flare=0.16,
    ),

    # 7. night_torch -- moon at 38 deg, a real star field, and a warm city
    #    skyglow along the horizon plus its bounce on the ground.
    "night_torch": dict(
        sun_elev=38.0, sun_azim=-70.0, sun_energy=3.6,
        sun_color=(0.52, 0.640, 0.920), sun_angle=0.90,
        zenith="#050b1e", horizon="#182a45", haze="#1e2c40",
        gain=25.51, sat=1.35, strength=0.90, fill=11.26,
        glow=0.20, halo_wide=0.04, halo_core=0.22, airmass=0.40,
        sun_disc=0.0,
        clouds=0.30, cloud_scale=0.46, cloud_soft=0.40, cloud_alt=0.020,
        cloud_low=0.45, cloud_bank=0.45,
        cloud_col_low="#2b3648", cloud_col_high="#3d4a60",
        cloud_shade="#151d2c",
        haze_mix=0.30, haze_band=0.070, haze_fuse=0.045, fuse_mix=0.60,
        stars=1.00, star_scale=52.0,
        moon=1.00, moon_elev=38.0, moon_azim=-70.0, moon_size=0.0046,
        moon_phase=0.62, moon_col="#e8eeff", moon_halo=0.45,
        city_glow=0.85, city_elev=9.0, city_width=0.050, ground_glow=0.30,
        ap=0.70, ap_start=300, ap_depth=5000, ap_near="#1d2a3d",
        ap_warm=0.45, exposure=-0.90,
    ),

    # 8. storm_dark -- a 60 deg deck, almost no direct light, green-grey light
    #    from above and a bright slot near the horizon.
    "storm_dark": dict(
        sun_elev=42.0, sun_azim=-30.0, sun_energy=2.4,
        sun_color=(0.66, 0.720, 0.840), sun_angle=8.0,
        zenith="#2b333c", horizon="#5d6a70", haze="#6b757a",
        gain=30.51, sat=1.22, strength=1.05, fill=21.71,
        glow=0.32, halo_wide=0.04, halo_core=0.14, airmass=0.30,
        sun_disc=0.0,
        clouds=1.00, cloud_scale=0.30, cloud_soft=0.62, cloud_alt=-0.050,
        cloud_low=0.80, cloud_bank=0.92, cloud_low_top=0.170,
        cloud_col_low="#7d868c", cloud_col_high="#95a0a6",
        cloud_shade="#39424b",
        haze_mix=0.60, haze_band=0.130, haze_fuse=0.075, fuse_mix=0.78,
        ap=0.85, ap_start=400, ap_depth=4400, ap_near="#6e7a7e",
        ap_warm=0.05, exposure=-2.30,
    ),

    # 9. fog_pale -- nothing above 40 deg is visible, the sun is a grey disc.
    "fog_pale": dict(
        sun_elev=24.0, sun_azim=-62.0, sun_energy=5.0,
        sun_color=(0.92, 0.920, 0.950), sun_angle=7.0,
        zenith="#9aa7b0", horizon="#c3cbd0", haze="#cdd3d6",
        gain=8.80, sat=1.00, strength=1.15, fill=3.91,
        glow=0.55, halo_wide=0.10, halo_core=0.18, airmass=0.85,
        clouds=0.55, cloud_scale=0.26, cloud_soft=0.70, cloud_alt=-0.020,
        cloud_low=0.70, cloud_bank=0.85, cloud_low_top=0.200,
        cloud_col_low="#c6ccd0", cloud_col_high="#d2d8db",
        cloud_shade="#b0b7bc",
        haze_mix=0.78, haze_band=0.180, haze_fuse=0.110, fuse_mix=0.88,
        ap=0.95, ap_start=180, ap_depth=2800, ap_near="#c3cbd0",
        ap_warm=0.0, exposure=-3.34,
    ),

    # 10. sunshower_warm -- sun out, rain falling three valleys away: the deck
    #     is broken, bright-sided, and there is a rainbow band under it.
    "sunshower_warm": dict(
        sun_elev=26.0, sun_azim=-40.0, sun_energy=72.0,
        sun_color=(1.00, 0.800, 0.560), sun_angle=1.4,
        zenith="#20507e", horizon="#bcc3c0", haze="#cdc4b4",
        gain=24.64, sat=1.48, strength=1.0, fill=11.63,
        glow=0.92, halo_wide=0.12, halo_core=0.40, airmass=0.80,
        clouds=0.80, cloud_scale=0.38, cloud_soft=0.34,
        cloud_low=0.62, cloud_bank=0.60, cloud_low_top=0.110,
        cloud_col_low="#e9dcc4", cloud_col_high="#fff3e2",
        cloud_shade="#8a93a0",
        haze_mix=0.44, haze_band=0.070, haze_fuse=0.038, fuse_mix=0.58,
        ap=0.90, ap_start=400, ap_depth=5000, ap_near="#a8a89e",
        ap_warm=0.55, exposure=-2.62, flare=0.12,
    ),
}
for _k, _v in PRESETS.items():
    PRESETS[_k] = dict(BASE, **_v)
del _k, _v
PRESET_NAMES = tuple(PRESETS)

#: which node type the AP emitter actually became (diagnostic, see _ap_material)
_AP_EM_KIND = {}

#: hd_weather's eight states -> the nearest sky preset.  Also the reverse
#: direction, via `weather_of()`.
WEATHER = {
    "clear": "morning_town",
    "hazy": "morning_town",
    "overcast": "overcast_soft",
    "rain": "storm_dark",
    "storm": "storm_dark",
    "fog": "fog_pale",
    "snow": "overcast_soft",
    "sunshower": "sunshower_warm",
}

#: The old spellings stay valid -- hd_weather and render.py both send them.
ALIASES = {
    "elevation": "sun_elev",
    "azimuth": "sun_azim",
    "sun": "sun_energy",
    "haze_color": "haze",
    "cloud_lift_speed": None,          # accepted and ignored (v1 was static)
    # hd_weather's cloud colour names -> this file's
    "cloud_lit": "cloud_col_high",
    "cloud_dark": "cloud_shade",
    "cloud_base": "cloud_col_low",
}

#: hd_weather uses weather-state names as `sky_preset` in a few places
#: (`storm`, `hazy`, ...).  Accept both vocabularies instead of exploding.
PRESET_ALIASES = dict(WEATHER)


def _metres_to_z(alt_m):
    """Cloud-base altitude in metres -> sin(elevation) of the deck.

    A 900 m deck seen from a 300 m camera is only ~4 deg above the horizon;
    compressing it through a nominal 12 km reference gives 0.075, which lands
    the whole deck in the low band where the perspective pile-up lives.
    """
    return max(0.0, min(0.35, float(alt_m) / 12000.0))


# =========================================================================== #
#  colour / vector helpers (python side)
# =========================================================================== #
def _srgb(hexstr, gain=None):
    """'#rrggbb' -> linear RGB.  `gain` scales (None = no scale)."""
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    if gain is not None:
        out = [c * gain for c in out]
    return out


def _lerp3(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(3)]


def _sun_vec(elev, azim):
    """Unit vector pointing *at* the sun.  +Z up, azimuth += clockwise from +Y."""
    e = math.radians(elev)
    a = math.radians(azim)
    return (math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e))


def _perp_basis(vec):
    """Two unit vectors spanning the plane perpendicular to `vec`."""
    v = vec
    ref = (0.0, 0.0, 1.0) if abs(v[2]) < 0.9 else (1.0, 0.0, 0.0)
    a = (v[1] * ref[2] - v[2] * ref[1], v[2] * ref[0] - v[0] * ref[2],
         v[0] * ref[1] - v[1] * ref[0])
    n = math.sqrt(sum(c * c for c in a)) or 1.0
    return tuple(c / n for c in a)


def _cfg(preset, **over):
    """Merge a preset with keyword overrides, resolve aliases, parse colours.

    Returns a *flat* dict that also carries the derived vectors a caller needs
    (`_svec`, `_haze`, `_zenith`, ...).
    """
    preset = PRESET_ALIASES.get(preset, preset)
    if preset in PRESETS:
        cfg = dict(PRESETS[preset])
    else:
        # An unknown name is not fatal: treat it as a base to override.
        cfg = dict(BASE)
        cfg["_unknown"] = preset
    for k, v in over.items():
        k2 = ALIASES.get(k, k)
        if k2 is None:
            continue
        if k2 == "cloud_alt" and isinstance(v, (int, float)) and v > 1.5:
            # hd_weather passes a cloud *base altitude in metres* (900.0).
            # Everything inside this file works in the sin(elevation) domain,
            # where 0.0 is the horizon and 1.0 the zenith, so a 900 m deck seen
            # from a 300 m camera sits at about 4-5 deg: 900/12000 = 0.075.
            # Without this the lift mask is smoothstep(z, 900, 920) == 0 over
            # the entire sky and every weather preset renders cloudless.
            v = _metres_to_z(v)
        cfg[k2] = v
    # colours
    for key, out in (("zenith", "_zenith"), ("horizon", "_horizon"),
                     ("haze", "_haze"), ("cloud_col_low", "_cl"),
                     ("cloud_col_high", "_ch"), ("cloud_shade", "_sh"),
                     ("moon_col", "_moon"), ("city_col", "_city"),
                     ("ap_near", "_apn")):
        v = cfg.get(key)
        cfg[out] = _srgb(v) if isinstance(v, str) else list(v)[:3]
    if cfg.get("ap_far") is None:
        cfg["_apf"] = list(cfg["_horizon"])
    else:
        v = cfg["ap_far"]
        cfg["_apf"] = _srgb(v) if isinstance(v, str) else list(v)[:3]
    sc_ = cfg.get("sun_color", (1.0, 0.9, 0.8))
    cfg["_sun_rgb"] = _srgb(sc_) if isinstance(sc_, str) else list(sc_)[:3]
    cfg["_svec"] = _sun_vec(cfg["sun_elev"], cfg["sun_azim"])
    cfg["_mvec"] = _sun_vec(cfg["moon_elev"], cfg["moon_azim"])
    cfg["_maxis"] = _perp_basis(cfg["_mvec"])
    cfg["preset"] = preset
    return cfg


# =========================================================================== #
#  node wrappers
# =========================================================================== #
def _n(nt, kind, name, loc=(0, 0), **kw):
    nd = nt.nodes.new(kind)
    nd.name = name
    nd.label = name
    nd.location = loc
    for k, v in kw.items():
        try:
            setattr(nd, k, v)
        except Exception:                                    # noqa: BLE001
            print("[sky] %s has no %s" % (kind, k))
    return nd


def _math(nt, op, a, b=None, name="m", loc=(0, 0), clamp=False):
    nd = _n(nt, "ShaderNodeMath", name, loc, operation=op)
    nd.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            nd.inputs[i].default_value = float(v)
        else:
            nt.links.new(v, nd.inputs[i])
    return nd.outputs[0]


def _math2(nt, op, a, b, c, name="ma", loc=(0, 0)):
    """a * b + c  (one MULTIPLY_ADD node)."""
    nd = _n(nt, "ShaderNodeMath", name, loc, operation=op)
    for i, v in enumerate((a, b, c)):
        if isinstance(v, (int, float)):
            nd.inputs[i].default_value = float(v)
        elif v is not None:
            nt.links.new(v, nd.inputs[i])
    return nd.outputs[0]


def _vmath(nt, op, a, b=None, name="v", loc=(0, 0), scale=None):
    nd = _n(nt, "ShaderNodeVectorMath", name, loc, operation=op)
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (tuple, list)):
            nd.inputs[i].default_value = v
        elif isinstance(v, (int, float)):
            nd.inputs[i].default_value = (v, v, v)
        else:
            nt.links.new(v, nd.inputs[i])
    if scale is not None:
        # SCALE's factor is input 3 and is named "Scale" only on some builds
        sock = nd.inputs[3] if len(nd.inputs) > 3 else nd.inputs[2]
        if isinstance(scale, (int, float)):
            sock.default_value = float(scale)
        else:
            nt.links.new(scale, sock)
    return nd.outputs[0]


def _mixc(nt, a, b, fac, name="mix", loc=(0, 0), blend="MIX"):
    """Colour mix that works on the 4.x and the 5.x node API."""
    try:
        nd = _n(nt, "ShaderNodeMix", name, loc, data_type="RGBA", blend_type=blend)
        ins = [s for s in nd.inputs if s.type == "RGBA"]
        outs = [s for s in nd.outputs if s.type == "RGBA"]
        fac_in = nd.inputs[0]
        out = outs[0]
    except Exception:                                        # noqa: BLE001
        nd = _n(nt, "ShaderNodeMixRGB", name, loc, blend_type=blend)
        ins = [nd.inputs["Color1"], nd.inputs["Color2"]]
        fac_in = nd.inputs["Fac"]
        out = nd.outputs[0]
    if isinstance(fac, (int, float)):
        fac_in.default_value = float(fac)
    else:
        nt.links.new(fac, fac_in)
    for sock, v in zip(ins, (a, b)):
        if isinstance(v, (tuple, list)):
            sock.default_value = tuple(v[:3]) + (1.0,)
        else:
            nt.links.new(v, sock)
    return out


def _smooth(nt, src, lo, hi, name="sm", loc=(0, 0)):
    """smoothstep(lo, hi, src) with the edges pre-clamped.

    Map Range's SMOOTHSTEP does *not* reliably clamp the factor outside
    ``[From Min, From Max]``: at ``src = 10 * hi`` the cubic ``t*t*(3-2t)``
    evaluates to about -1700, so a "fade out by 9 deg" mask came back as -0.70
    and poisoned every threshold downstream (this is what made the cloud mask
    vanish).  Clamping the *ratio* first is cheap (one MATH node, whose own
    Clamp flag is honoured) and makes the result 0..1 by construction.
    """
    if not isinstance(hi, (int, float)):
        dt = _math(nt, "SUBTRACT", hi, lo, name + "_r", (loc[0] - 160, loc[1] - 60))
        dr = _math(nt, "SUBTRACT", src, lo, name + "_s",
                   (loc[0] - 160, loc[1]))
        t = _math(nt, "DIVIDE", dr, dt, name + "_t", (loc[0] - 60, loc[1]),
                  clamp=True)
    else:
        if not isinstance(lo, (int, float)):
            dr = _math(nt, "SUBTRACT", src, lo, name + "_s",
                       (loc[0] - 160, loc[1]))
            d = dr
        else:
            d = _math(nt, "SUBTRACT", src, float(lo), name + "_s",
                      (loc[0] - 160, loc[1]))
        t = _math(nt, "DIVIDE", d, max(1e-6, float(hi) - float(lo)),
                  name + "_t", (loc[0] - 60, loc[1]), clamp=True)
    nd = _n(nt, "ShaderNodeMapRange", name, loc, interpolation_type="SMOOTHSTEP")
    nd.clamp = True
    nt.links.new(t, nd.inputs["Value"])
    nd.inputs["From Min"].default_value = 0.0
    nd.inputs["From Max"].default_value = 1.0
    return nd.outputs["Result"]


def _noise(nt, vec, scale, detail, rough, name="n", loc=(0, 0), dist=0.0):
    nd = _n(nt, "ShaderNodeTexNoise", name, loc)
    nd.noise_dimensions = "3D"
    nt.links.new(vec, nd.inputs["Vector"])
    for key, val in (("Scale", scale), ("Detail", detail),
                     ("Roughness", rough), ("Distortion", dist)):
        try:
            nd.inputs[key].default_value = float(val)
        except Exception:                                    # noqa: BLE001
            pass
    return nd.outputs["Fac"]


def _hg(nt, sdot, g, name="hg", loc=(0, 0)):
    """Henyey-Greenstein phase, normalised so the forward peak is 1.0.

    phi = (1 - g)^1.5 / (1 + g^2 - 2 g cos)^1.5
    """
    d = _math2(nt, "MULTIPLY_ADD", sdot, -2.0 * g, 1.0 + g * g,
               name + "_d", loc)
    inv = _math(nt, "POWER", d, -1.5, name + "_p", (loc[0] + 120, loc[1]))
    return _math(nt, "MULTIPLY", inv, (1.0 - g) ** 1.5, name, (loc[0] + 240, loc[1]))


def _dot(nt, a, b, name="dot", loc=(0, 0)):
    nd = _n(nt, "ShaderNodeVectorMath", name, loc, operation="DOT_PRODUCT")
    for i, v in enumerate((a, b)):
        if isinstance(v, (tuple, list)):
            nd.inputs[i].default_value = v
        elif isinstance(v, (int, float)):
            nd.inputs[i].default_value = (v, v, v)
        else:
            nt.links.new(v, nd.inputs[i])
    return nd.outputs["Value"]


def _torgb(nt, sock, name="rgb", loc=(0, 0)):
    """A scalar socket -> a colour socket (same value in R, G and B)."""
    nd = _n(nt, "ShaderNodeCombineXYZ", name, loc)
    for k in ("X", "Y", "Z"):
        nt.links.new(sock, nd.inputs[k])
    return nd.outputs[0]


def _addc(nt, a, b, fac=1.0, name="add", loc=(0, 0)):
    """a + b*fac, as one colour MIX in ADD mode (cheaper than a vector add)."""
    if fac == 0.0:
        return a
    return _blendc(nt, "ADD", a, b, name, loc, fac)


def _blendc(nt, mode, a, b, name="bl", loc=(0, 0), fac=1.0):
    if isinstance(a, (int, float)):
        a = (a, a, a)
    if isinstance(b, (int, float)):
        b = (b, b, b)
    if not isinstance(b, (tuple, list)) and getattr(b, "type", "") not in ("RGBA", "VECTOR"):
        b = _torgb(nt, b, name + "_rgb", (loc[0] - 140, loc[1] - 140))
    nd = _n(nt, "ShaderNodeMix", name, loc, data_type="RGBA", blend_type=mode)
    ins = [s for s in nd.inputs if s.type == "RGBA"]
    outs = [s for s in nd.outputs if s.type == "RGBA"]
    for sock, v in ((ins[0], a), (ins[1], b)):
        if isinstance(v, (tuple, list)):
            sock.default_value = tuple(v[:3]) + (1.0,)
        else:
            nt.links.new(v, sock)
    nd.inputs[0].default_value = float(min(1.0, fac))
    return outs[0]


def _mulc(nt, a, b, name="mul", loc=(0, 0), fac=1.0):
    if isinstance(a, (int, float)):
        a = (a, a, a)
    if isinstance(b, (int, float)):
        b = (b, b, b)
    if not isinstance(b, (tuple, list)) and getattr(b, "type", "") not in ("RGBA", "VECTOR"):
        b = _torgb(nt, b, name + "_rgb", (loc[0] - 140, loc[1] - 140))
    nd = _n(nt, "ShaderNodeMix", name, loc, data_type="RGBA", blend_type="MULTIPLY")
    ins = [s for s in nd.inputs if s.type == "RGBA"]
    outs = [s for s in nd.outputs if s.type == "RGBA"]
    for sock, v in ((ins[0], a), (ins[1], b)):
        if isinstance(v, (tuple, list)):
            sock.default_value = tuple(v[:3]) + (1.0,)
        else:
            nt.links.new(v, sock)
    nd.inputs[0].default_value = float(min(1.0, fac))
    return outs[0]


def _sat(nt, col, sat, name="hs", loc=(0, 0)):
    nd = _n(nt, "ShaderNodeHueSaturation", name, loc)
    nt.links.new(col, nd.inputs["Color"])
    nd.inputs["Saturation"].default_value = sat
    return nd.outputs["Color"]


# =========================================================================== #
#  the dome
# =========================================================================== #
#  Why a mesh and not the world background
#  ---------------------------------------
#  Measured on this build (Blender 5.2.3 LTS, EEVEE, `look/sky_lab.py`):
#  inside a *world* shader `TexCoord.Generated`, `Geometry.Incoming` and even
#  `Sky Texture` are evaluated at ONE direction for the whole frame, so a
#  world-shaded sky can only ever be a flat colour -- no gradient, no horizon
#  band, no clouds.  A real surface is shaded per pixel, so the sky lives on an
#  emissive sphere ("SKY_dome") parented in practice to the camera position,
#  and `dir` is computed exactly from the hit position:
#      dir = normalize(P_world - camera_position)
#  The world datablock keeps its job -- a *flat* ambient fill for diffuse rays
#  -- so `ambient` still means what it meant before.
def _ambient_world(scene, cfg):
    """The world datablock: a flat ambient fill, nothing else.

    EEVEE evaluates a world shader at one direction only (see the note above),
    so a world can never be a sky.  What it *can* do is fill the shadows with a
    plausible average of the dome, which is all `ambient` ever meant.

    Strength is ``strength * fill * ambient``.  `fill` is an *absolute* number
    calibrated per preset (see SHADOW_TARGET) and deliberately **not** a
    function of `gain`: when the dome's gain is recalibrated -- and it moved by
    2x to 5x when the shader was rewritten -- the shadow must not move with it.
    `ambient` stays a plain multiplier at 1.0, so ``--ambient 0.5`` still means
    "half the fill".
    """
    name = "SKY_world"
    w = bpy.data.worlds.get(name)
    if w is None:
        w = bpy.data.worlds.new(name)
    scene.world = w
    try:
        w.use_nodes = True
    except Exception:                                        # noqa: BLE001
        pass
    nt = w.node_tree
    nt.nodes.clear()
    hz, zn = cfg["_horizon"], cfg["_zenith"]
    mix = [float(hz[i]) * 0.55 + float(zn[i]) * 0.45 for i in range(3)]
    lum = 0.2126 * mix[0] + 0.7152 * mix[1] + 0.0722 * mix[2]
    col = [mix[i] * 0.78 + lum * 0.22 for i in range(3)]
    k = (float(cfg["strength"]) * float(cfg.get("fill", 2.4))
         * float(cfg["ambient"]))
    cfg["_fill"] = k
    bg = _n(nt, "ShaderNodeBackground", "bg", (0, 0))
    bg.inputs["Color"].default_value = (col[0], col[1], col[2], 1.0)
    bg.inputs["Strength"].default_value = k
    out = _n(nt, "ShaderNodeOutputWorld", "out", (260, 0))
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return w


def _dome_radius(scene, cam):
    ce = float(getattr(getattr(cam, "data", None), "clip_end", 20000.0) or 20000.0)
    return max(400.0, min(120000.0, 0.90 * ce))


def _dome_obj(scene, loc, radius, mat):
    """The emissive sphere.  Created once, then moved/rescaled every build."""
    name = "SKY_dome"
    ob = bpy.data.objects.get(name)
    if ob is None:
        import bmesh
        me = bpy.data.meshes.new("SKY_dome_mesh")
        bm = bmesh.new()
        try:
            bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=1.0)
        except TypeError:                                    # pre-3.0 spelling
            bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24,
                                      diameter=1.0)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        scene.collection.objects.link(ob)
    ob.location = tuple(loc)
    ob.scale = (radius, radius, radius)
    ob.rotation_euler = (0.0, 0.0, 0.0)
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    # the dome must never shade, shadow or bounce: it is a picture, not a lamp
    for attr, val in (("visible_shadow", False), ("visible_diffuse", False),
                      ("visible_transmission", False),
                      ("visible_volume_scatter", False),
                      ("visible_glossy", True), ("hide_probe", True)):
        try:
            setattr(ob, attr, val)
        except Exception:                                    # noqa: BLE001
            pass
    _dome_drivers(ob, scene)
    return ob


def _dome_drivers(ob, scene):
    """Follow whatever camera the shot ends up using.

    A static dome silently breaks the moment a driver swaps cameras between
    shots (`look/render.py` builds one per shot), so bind the dome to
    `scene.camera` with two cheap single-property drivers: position from
    `camera.location`, size from `camera.data.clip_end`.  Both compile to a
    simple expression, so they need no Python auto-exec.
    """
    try:
        for i in range(3):
            fc = ob.driver_add("location", i)
            drv = fc.driver
            drv.type = "SCRIPTED"
            var = drv.variables.new()
            var.name = "cam"
            var.type = "SINGLE_PROP"
            tgt = var.targets[0]
            tgt.id_type = "SCENE"
            tgt.id = scene
            tgt.data_path = "camera.location[%d]" % i
            drv.expression = "cam"
        for i in range(3):
            fc = ob.driver_add("scale", i)
            drv = fc.driver
            drv.type = "SCRIPTED"
            var = drv.variables.new()
            var.name = "ce"
            var.type = "SINGLE_PROP"
            tgt = var.targets[0]
            tgt.id_type = "SCENE"
            tgt.id = scene
            tgt.data_path = "camera.data.clip_end"
            drv.expression = "0.9*ce"
    except Exception:                                        # noqa: BLE001
        pass


def dome_follow(scene, cfg=None, camera=None):
    """Re-centre the dome on the camera and re-bake its origin."""
    cfg = cfg or _LAST.get("cfg")
    cam = camera or scene.camera
    if not cfg or cam is None:
        return None
    loc = tuple(cam.matrix_world.translation)
    ob = bpy.data.objects.get("SKY_dome")
    if ob is not None:
        ob.location = loc
        ob.scale = (_dome_radius(scene, cam),) * 3
    node = cfg.get("_camloc_node")
    if node is not None:
        for i, ax in enumerate("XYZ"):
            node.inputs[ax].default_value = float(loc[i])
    return ob


def world(scene, preset="morning_town", **over):
    """Build (or rebuild) the sky and return its config dict."""
    cfg = _cfg(preset, **over)
    X, Y = 0, 0
    cam = scene.camera
    cam_loc = tuple(cam.matrix_world.translation) if cam is not None else (0.0, 0.0, 0.0)

    mat = bpy.data.materials.get("SKY_mat")
    if mat is None:
        mat = bpy.data.materials.new("SKY_mat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    dome = _dome_obj(scene, cam_loc, _dome_radius(scene, cam), mat)

    # ------------------------------------------------------------------ 1 ---
    # direction: exact and per pixel, from the hit point on the sphere.  The
    # camloc node is a constant the dome_follow() helper re-bakes, so moving
    # the camera does not need a rebuild.
    geo = _n(nt, "ShaderNodeNewGeometry", "geo", (-2700, Y))
    cl = _n(nt, "ShaderNodeCombineXYZ", "camloc", (-2700, Y - 260))
    for i, ax in enumerate("XYZ"):
        cl.inputs[ax].default_value = float(cam_loc[i])
    rel = _vmath(nt, "SUBTRACT", geo.outputs["Position"], cl.outputs[0],
                 name="rel", loc=(-2500, Y))
    nrm = _vmath(nt, "NORMALIZE", rel, name="dir", loc=(-2300, Y))
    sep = _n(nt, "ShaderNodeSeparateXYZ", "sep", (-2120, Y))
    nt.links.new(nrm, sep.inputs["Vector"])
    z = sep.outputs["Z"]
    xy = _vmath(nt, "MULTIPLY", nrm, (1.0, 1.0, 0.0), name="xy", loc=(-2120, Y - 260))
    elev = _math(nt, "MAXIMUM", z, 0.0, "elev", (-1940, Y))

    # ------------------------------------------------------------------ 2 ---
    # vertical gradient.  A pure pow() of elevation is what makes a sky read as
    # a sky instead of a backdrop: the top half has to be much darker than the
    # bottom half, and the knee has to sit near 20-30 deg.
    gpow = _math(nt, "POWER", elev, float(cfg.get("grad_pow", 0.46)),
                 "gpow", (-1640, Y))
    sky = _mixc(nt, cfg["_horizon"], cfg["_zenith"], gpow, "grad", (-1460, Y))

    # ------------------------------------------------------------------ 3 ---
    # horizon band.  A thin additive exp() term, brightest exactly *at* the
    # horizon and gone by ~8 deg.  This is what a wide shot actually sees, so
    # it has to carry its own structure: it is brighter than the gradient and
    # it is warm toward the sun.
    hz = _math2(nt, "MULTIPLY_ADD", elev, -1.0 / 0.055, 1.0, "hz_e", (-1640, Y - 200))
    hz = _math(nt, "POWER", _math(nt, "MAXIMUM", hz, 0.0, "hz_m", (-1500, Y - 200)),
               2.2, "hz_p", (-1360, Y - 200))
    to_sun = _dot(nt, nrm, cfg["_svec"], "to_sun", (-1840, Y - 380))
    to_sun = _math(nt, "MINIMUM", to_sun, 1.0, "ts_c", (-1700, Y - 380))
    to_sun = _math(nt, "MAXIMUM", to_sun, -1.0, "ts_c2", (-1560, Y - 380))
    s01 = _math2(nt, "MULTIPLY_ADD", to_sun, 0.5, 0.5, "s01", (-1660, Y - 380))
    sun_side = _math(nt, "POWER", s01, 2.4, "sun_side", (-1500, Y - 380))
    hz_amt = _math2(nt, "MULTIPLY_ADD", sun_side, 1.35, 0.42, "hz_a", (-1340, Y - 380))
    hz_col = _mixc(nt, cfg["_haze"], cfg["_horizon"], 0.45, "hz_col", (-1340, Y - 260))
    band = _mulc(nt, hz_col, _math(nt, "MULTIPLY", hz, hz_amt, "hz_k", (-1180, Y - 300)),
                 "band", (-1020, Y - 300))
    sky = _addc(nt, sky, band, 1.0, "sky_band", (-860, Y))

    # ------------------------------------------------------------------ 4 ---
    # Mie: one wide angular Gaussian (the aureole you see through the air) plus
    # one narrow one at the disc, both scaled by air mass: a low sun travels a
    # much longer path, so sunrise warms the whole sun-side sky and not just the
    # few degrees around the disc.
    #
    # The angle is measured explicitly instead of leaning on a
    # Henyey-Greenstein phase.  HG peaks at (1-g)^-1.5, which is 68x at g=0.94
    # and 9x at g=0.72: one such addition is 20-70x the sky itself, and the
    # first strip run came out as a white frame.  Gaussians in *angle* are what
    # a camera records, and they let the width be a knob in degrees.
    air = _math2(nt, "MULTIPLY_ADD", elev, 1.0, 0.085, "air_d", (-1840, Y - 560))
    air = _math(nt, "DIVIDE", 1.0, air, "air_i", (-1700, Y - 560), clamp=True)
    air = _math(nt, "POWER", air, 1.0 + 1.6 * float(cfg["airmass"]),
                "air_p", (-1560, Y - 560))
    ang = _math(nt, "SUBTRACT", 1.0, to_sun, "ang_u", (-1900, Y - 740))
    # exp(-(a/sigma)^2) with a^2 = 2(1-cos) -> exp(-u * 2/sigma^2), which needs
    # no acos and no EXPONENT node: POWER(2.718..., x) with x <= 0 is finite on
    # every backend, while the EXPONENT node underflowed to a value EEVEE turned
    # into a black frame at these widths.
    w_r = _math(nt, "MULTIPLY", ang, -2.0 / (float(cfg["halo_w_w"]) ** 2),
                "gw_r", (-1760, Y - 700))
    w_e = _math(nt, "POWER", 2.718281828459045, w_r, "gw_e", (-1480, Y - 700))
    c_r = _math(nt, "MULTIPLY", ang, -2.0 / (float(cfg["halo_c_w"]) ** 2),
                "gc_r", (-1760, Y - 860))
    c_e = _math(nt, "POWER", 2.718281828459045, c_r, "gc_e", (-1480, Y - 860))
    halo = _math2(nt, "MULTIPLY_ADD", c_e, float(cfg["halo_core"]),
                  _math(nt, "MULTIPLY", w_e, float(cfg["halo_wide"]), "gw_k",
                        (-1480, Y - 780)), "halo", (-1340, Y - 780))
    mie = _math(nt, "MULTIPLY", halo, air, "mie_air", (-1200, Y - 780))
    mie = _math(nt, "MULTIPLY", mie, float(cfg["halo_scale"]),
                "mie_scale", (-1100, Y - 780))
    # the legs of the legacy `glow` knob: a broad pow() toward the sun, kept for
    # hd_weather's `glow=` (scaled down to the new amplitudes)
    g1 = _math(nt, "POWER", _math(nt, "MAXIMUM", to_sun, 0.0, "gl_m", (-1480, Y - 1060)),
               2.6, "gl_p", (-1320, Y - 1060))
    glow = _math(nt, "MULTIPLY", g1, float(cfg["glow"]) * 0.10, "glow",
                 (-1160, Y - 1060))
    glow = _math(nt, "MULTIPLY", glow, _math(nt, "POWER", air, 0.6, "air2", (-1320, Y - 1200)),
                 "glow_a", (-1000, Y - 1060))
    mie = _math(nt, "ADD", mie, glow, "mie_all", (-860, Y - 900))
    mie_c = _mulc(nt, cfg["_haze"], mie, "mie_col", (-700, Y - 900), fac=1.0)
    sun_col = _mulc(nt, cfg["_sun_rgb"], mie, "mie_sun", (-540, Y - 900), fac=1.0)
    sky = _addc(nt, sky, mie_c, float(cfg.get("mie_mix", 0.65)), "sky_mie", (-380, Y))
    sky = _addc(nt, sky, sun_col, float(cfg.get("mie_mix2", 0.85)), "sky_mie2", (-220, Y))
    del mie_c

    # ------------------------------------------------------------------ 5 ---
    # the disc itself: an additive step, not a mix, so it saturates to white.
    r = math.radians(max(0.12, float(cfg["sun_angle"])) * 0.5)
    disc = _smooth(nt, to_sun, math.cos(r * 1.35), math.cos(r * 0.85),
                   "disc", (-1840, Y - 1360))
    disc_k = _math(nt, "MULTIPLY", disc,
                   float(cfg["sun_disc"]) * float(cfg["disc_gain"]), "disc_k",
                   (-1680, Y - 1360))
    dcol = _mulc(nt, cfg["_sun_rgb"], disc_k, "disc_c", (-1520, Y - 1360), fac=1.0)
    if float(cfg["sun_disc"]) > 0.0 and cfg["sun_elev"] > -3.0:
        sky = _addc(nt, sky, dcol, 0.9, "sky_disc", (-60, Y))
    del dcol

    # ------------------------------------------------------------------ 6 ---
    # clouds, in *angular* space.
    #
    # v1 projected the deck at cloud altitude -- xy/z -- which is right for a
    # thin plane overhead and wrong exactly where a wide shot looks.  At 2 deg
    # of elevation that projection stretches the texture 14x more than at
    # 30 deg, so the low band turns to confetti while the *shape* of a real low
    # cloud (long horizontally stretched banks piling up on the horizon) is a
    # property of the direction and not of any plane.  So the body is sampled
    # on `dir` with a per-axis scale (z varies ~2x faster than x/y -> banks),
    # which is stable from 0 to 90 deg, and the plane projection survives only
    # as a high-elevation detail layer.
    cs = float(cfg["cloud_scale"]) * 5.0
    clouds = float(cfg["clouds"])
    cl_low = float(cfg["cloud_low"])
    # "looking along the deck" weight.  This is the whole trick of the low
    # band, so it is a *wide* fade (0..25 deg, not 0..6): a step at 6 deg
    # leaves a bare ring of sky between the horizon bank and the zenith deck,
    # which is exactly what a wide shot spends its pixels on.
    lowband = _math(nt, "SUBTRACT", 1.0,
                    _smooth(nt, elev, 0.02, 0.45, "lb", (-2060, Y - 2700)),
                    "lowband", (-1920, Y - 2700))
    # a cloud 20 km away is 8x wider than it is tall on screen: near the
    # horizon the noise has to vary ~8x faster in z than in x/y or the deck
    # reads as a flat sheet with no banks at all.
    zs = _math2(nt, "MULTIPLY_ADD", lowband, 5.0, 1.75, "zs", (-1920, Y - 2400))
    zvec = _n(nt, "ShaderNodeCombineXYZ", "zvec", (-1760, Y - 2400))
    zvec.inputs["X"].default_value = 1.0
    zvec.inputs["Y"].default_value = 1.0
    nt.links.new(zs, zvec.inputs["Z"])
    vdir = _vmath(nt, "SCALE", nrm, None, name="c_s", loc=(-1920, Y - 1560),
                  scale=cs)
    v_body = _vmath(nt, "MULTIPLY", vdir, zvec.outputs[0], "c_vb",
                    (-1760, Y - 1560))
    v_det = _vmath(nt, "MULTIPLY", vdir, (4.2, 4.2, 13.0), "c_vd",
                   (-1760, Y - 1700))
    v_bro = _vmath(nt, "MULTIPLY", vdir, (0.30, 0.30, 0.44), "c_vr",
                   (-1760, Y - 1840))
    n_body = _noise(nt, v_body, 1.0, 7.0, 0.55, "c_body", (-1660, Y - 1560), 0.20)
    n_det = _noise(nt, v_det, 1.0, 4.0, 0.55, "c_det", (-1660, Y - 1700))
    n_broad = _noise(nt, v_bro, 1.0, 2.5, 0.50, "c_broad", (-1660, Y - 1840))
    n_shade = _noise(nt, v_body, 0.42, 3.0, 0.50, "c_shade", (-1660, Y - 1980))
    det_fade = _smooth(nt, elev, 0.004, 0.060, "det_fade", (-1500, Y - 2120))
    d_h = _math(nt, "SUBTRACT", n_det, 0.5, "d_h", (-1500, Y - 1700))
    d_k = _math(nt, "MULTIPLY", d_h, 0.26, "d_k", (-1360, Y - 1700))
    d_f = _math(nt, "MULTIPLY", d_k, det_fade, "d_f", (-1220, Y - 1700))
    b_h = _math(nt, "SUBTRACT", n_broad, 0.5, "b_h", (-1500, Y - 1840))
    b_k = _math(nt, "MULTIPLY", b_h, 0.42, "b_k", (-1360, Y - 1840))
    body = _math(nt, "ADD", n_body, d_f, "c_bd1", (-1060, Y - 1780))
    body = _math(nt, "ADD", body, b_k, "body_add", (-900, Y - 1780))
    # Measured (`look/sky_lab.py stats`): the raw fBM sits in 0.66..0.87, a
    # spread of +-0.08, which turns `clouds` into an on/off switch -- 0.05 of
    # threshold flips the whole deck.  Stretch it about its median so a 0.1
    # change of threshold moves coverage by ~20% instead.
    body = _math2(nt, "MULTIPLY_ADD", body, 3.2, -1.22, "body01", (-740, Y - 1780))
    body = _math(nt, "MAXIMUM", body, 0.0, "body", (-600, Y - 1780), clamp=True)

    # coverage.  `clouds` moves the threshold; the low band gets its own,
    # slightly lower one, because at the horizon you are looking along the deck
    # instead of up through it and there is simply more cloud in the way.
    # Calibrated against the measured body01 distribution (p25=0.44, p50=0.65,
    # p75=0.79, p90=0.91) so that clouds=0.5 is half cover, not "all or
    # nothing": 0.93-0.52*0.62 = 0.61 sits just under the median.
    thr = 0.93 - 0.52 * clouds
    thr_eff = _math2(nt, "MULTIPLY_ADD", lowband, -(0.09 + 0.10 * cl_low), thr,
                     "thr", (-1060, Y - 2400))
    thr_hi = _math(nt, "ADD", thr_eff, 0.05 + float(cfg["cloud_soft"]) * 0.35,
                   "thr_hi", (-900, Y - 2400))
    mask = _smooth(nt, body, thr_eff, thr_hi, "mask", (-740, Y - 2200))

    # the base line: below `cloud_alt` there is nothing to see but haze, and
    # the deck has to *fade into* that band rather than be cut off by it.
    lift = _smooth(nt, elev, float(cfg["cloud_alt"]),
                   float(cfg["cloud_alt"]) + float(cfg["cloud_rise"]), "lift",
                   (-740, Y - 1560))
    mask = _math(nt, "MULTIPLY", mask, lift, "mask_l", (-580, Y - 1900))
    # plus a solid bank right on the horizon: 0 means a clean blue horizon,
    # 1 a wall of cloud with no sky under it at all.  It must be *only* the
    # 0-4 deg strip -- feeding `deck` in positively coated the entire upper
    # sky in a flat white veil and flattened the deck.
    bank = float(cfg["cloud_bank"]) * clouds
    deck = _math(nt, "SUBTRACT", 1.0,
                 _smooth(nt, elev, 0.0, float(cfg["cloud_low_top"]) * 0.80,
                         "deck_in", (-1060, Y - 2560)), "deck", (-900, Y - 2560))
    bankm = _math(nt, "MULTIPLY", deck, bank, "bank", (-740, Y - 2560))
    m_a = _math(nt, "ADD", mask, bankm, "m_a", (-420, Y - 2100))
    m_b = _math(nt, "MULTIPLY", bankm, mask, "m_b", (-420, Y - 2240))
    mask = _math(nt, "SUBTRACT", m_a, m_b, "mask_bank", (-260, Y - 2100),
                 clamp=True)

    # shading.  A cloud is a bucket of white spheres: the side facing the sun
    # is warm and slightly over-exposed, the base is cold grey-blue, and the
    # low band catches light from underneath because the sun rakes along it.
    lit = _math2(nt, "MULTIPLY_ADD", to_sun, 0.5, 0.5, "lit", (-1360, Y - 2720))
    shp = _smooth(nt, n_shade, 0.36, 0.70, "shp", (-1360, Y - 2860))
    tone = _mixc(nt, cfg["_sh"], cfg["_ch"], shp, "c_tone", (-1180, Y - 2720))
    # The low band is NOT paler than the sky it sits on: near the horizon you
    # look at the shaded *base* of the deck, which is a clear step darker than
    # the bright haze behind it.  Mixing it 78% toward a pale `cloud_col_low`
    # made the clouds tonally identical to the horizon sky, so the deck
    # disappeared from every wide shot even though the mask was full.
    tone = _mixc(nt, tone, cfg["_cl"], _math(nt, "MULTIPLY", lowband, 0.55, "lb78",
                                            (-1180, Y - 2860)), "c_low",
                 (-1020, Y - 2720))
    lk = _math2(nt, "MULTIPLY_ADD", lit, 0.86, 0.40, "lk", (-1180, Y - 3000))
    tone = _mulc(nt, tone, lk, "c_lit", (-860, Y - 2720), fac=1.0)
    warm = _math(nt, "MULTIPLY", lit, lowband, "w_ll", (-1020, Y - 3140))
    warm = _math(nt, "MULTIPLY", warm, 0.55, "w_k", (-880, Y - 3140))
    tone = _addc(nt, tone, _mulc(nt, cfg["_sun_rgb"], warm, "w_c",
                                 (-720, Y - 3140)), 1.0, "c_warm",
                 (-560, Y - 2860))
    under = _math(nt, "MULTIPLY", lowband,
                  _math(nt, "SUBTRACT", 1.0, sun_side, "u_1", (-1020, Y - 3300)),
                  "u_k", (-860, Y - 3300))
    underc = _math2(nt, "MULTIPLY_ADD", under, -0.22, 1.0, "u_c", (-700, Y - 3300))
    tone = _mulc(nt, tone, underc, "c_under", (-400, Y - 2860), fac=1.0)
    sky = _mixc(nt, sky, tone, mask, "sky_cloud", (60, Y))
    # ------------------------------------------------------------------ 7 ---
    # haze veil over the deck, then a tight fuse into the horizon band.  The
    # veil is what air does to a deck 20 km away; the fuse makes the deck
    # *start to exist* out of the horizon instead of sitting on a hard edge.
    veil = _math(nt, "SUBTRACT", 1.0,
                 _smooth(nt, z, 0.0, float(cfg["haze_band"]), "vb", (-1180, Y - 3060)),
                 "veil_1", (-1020, Y - 3060))
    veil = _math(nt, "MULTIPLY", veil, float(cfg["haze_mix"]), "veil", (-860, Y - 3060))
    sky = _mixc(nt, sky, cfg["_haze"], veil, "sky_veil", (200, Y))
    fuse = _math(nt, "SUBTRACT", 1.0,
                 _smooth(nt, z, 0.0, float(cfg["haze_fuse"]), "fb", (-1180, Y - 3240)),
                 "fuse_1", (-1020, Y - 3240))
    fuse = _math(nt, "MULTIPLY", fuse, float(cfg["fuse_mix"]), "fuse", (-860, Y - 3240))
    fcol = _mixc(nt, cfg["_haze"], band, 0.55, "fcol", (-860, Y - 3380))
    sky = _mixc(nt, sky, fcol, fuse, "sky_fuse", (340, Y))

    # ------------------------------------------------------------------ 8 ---
    # grade.  AgX compresses channel ratios, so the dome is authored saturated
    # and pulled back here; this is a *display* correction, not a taste knob.
    sky = _sat(nt, sky, float(cfg["sat"]), "sat", (480, Y))

    # ------------------------------------------------------------------ 9 ---
    # night
    night_add = None
    if float(cfg["stars"]) > 0.0:
        # stars are at infinity, so they live on the *direction* sphere: no
        # horizon squashing, one cell of noise per solid angle.
        sxy = nrm
        up = _smooth(nt, z, 0.02, 0.30, "up", (-1180, Y - 3840))
        st = None
        for i, (sc, lo, hi, amp) in enumerate(((float(cfg["star_scale"]), 0.80, 0.975, 1.0),
                                               (float(cfg["star_scale"]) * 2.7, 0.92, 0.995, 0.8))):
            nz = _noise(nt, sxy, sc, 2.0, 0.75, "nst%d" % i, (-860, Y - 3560 - 200 * i))
            sp = _math(nt, "MULTIPLY", _smooth(nt, nz, lo, hi, "st%d" % i,
                                              (-700, Y - 3560 - 200 * i)), amp,
                       "stk%d" % i, (-540, Y - 3560 - 200 * i))
            st = sp if st is None else _math(nt, "ADD", st, sp, "st_a%d" % i,
                                             (-380, Y - 3560 - 200 * i))
        st = _math(nt, "MULTIPLY", st, up, "st_up", (-220, Y - 3660))
        st = _math(nt, "MULTIPLY", st, float(cfg["stars"]) * 0.16, "st_k",
                   (-60, Y - 3660))
        star_col = _mulc(nt, (1.0, 1.0, 1.0), st, "st_c", (100, Y - 3660), fac=1.0)
        night_add = (star_col if night_add is None
                     else _addc(nt, night_add, star_col, 1.0, "na_st", (240, Y)))

    if float(cfg["moon"]) > 0.0:
        mv = cfg["_mvec"]
        mdot = _dot(nt, nrm, mv, "mdot", (-1180, Y - 3960))
        mr = float(cfg["moon_size"])
        mdisc = _smooth(nt, mdot, math.cos(mr * 1.5), math.cos(mr * 0.9),
                        "mdisc", (-1020, Y - 3960))
        # phase: project the offset from the disc centre onto the perpendicular
        # axis and use that as the terminator coordinate.  A straight terminator
        # is wrong for a sphere but right for a 2-degree moon.
        off = _vmath(nt, "SCALE", mv, mdot, name="moff", loc=(-1180, Y - 4120))
        off = _vmath(nt, "SUBTRACT", nrm, off, name="mperp", loc=(-1020, Y - 4120))
        u = _dot(nt, off, cfg["_maxis"], "mu", (-860, Y - 4120))
        u = _math(nt, "DIVIDE", u, max(1e-5, math.sin(mr)), "mun", (-700, Y - 4120))
        k = 1.0 - 2.0 * float(cfg["moon_phase"])
        lit = _smooth(nt, u, k - 0.22, k + 0.22, "mlit", (-540, Y - 4120))
        lit_c = _mulc(nt, cfg["_moon"], lit, "mlit_c", (-380, Y - 4120), fac=1.0)
        dk = _math2(nt, "MULTIPLY_ADD", _math(nt, "SUBTRACT", 1.0, lit, "md1",
                                             (-540, Y - 4260)), 0.10, 0.0, "mdk",
                   (-380, Y - 4260))
        dk_c = _mulc(nt, cfg["_moon"], dk, "mdk_c", (-220, Y - 4260), fac=1.0)
        mfull = _mixc(nt, dk_c, lit_c, lit, "mface", (-60, Y - 4180))
        mfull = _mulc(nt, mfull, mdisc, "mdisc_c", (100, Y - 4180), fac=1.0)
        mfull = _mulc(nt, mfull, float(cfg["moon"]) * 1.6, "mk", (240, Y - 4180),
                      fac=1.0)
        night_add = (mfull if night_add is None
                     else _addc(nt, night_add, mfull, 1.0, "na_moon", (380, Y)))
        # Moon halo: a compact angular Gaussian (about 7 degrees across), NOT a
        # Henyey-Greenstein lobe.  HG has no scale, so at moon_halo=0.45 it
        # lifted the whole hemisphere by ~0.2 and night_torch rendered as a
        # white field (band 0.942) with no stars at all.
        u_ = _math(nt, "SUBTRACT", 1.0, mdot, "mhu", (-700, Y - 4400))
        u_ = _math(nt, "MULTIPLY", u_, -2.0 / (float(cfg.get("moon_halo_w", 0.12)) ** 2),
                   "mhr", (-540, Y - 4400))
        halo = _math(nt, "POWER", 2.718281828459045, u_, "mhg", (-380, Y - 4400))
        halo = _math(nt, "MULTIPLY", halo, float(cfg["moon_halo"]) * float(cfg["moon"])
                     * 0.30, "mha", (-220, Y - 4400))
        mh_c = _mulc(nt, cfg["_moon"], halo, "mh_c", (-60, Y - 4400))
        night_add = (mh_c if night_add is None
                     else _addc(nt, night_add, mh_c, 1.0, "na_mhalo", (380, Y - 200)))

    if float(cfg["city_glow"]) > 0.0:
        # warm skyglow hugging the horizon: the haze layer over a lit city
        hxy = _vmath(nt, "NORMALIZE", xy, name="hxy", loc=(-1180, Y - 4600))
        gvec = _sun_vec(0.0, float(cfg.get("city_azim", cfg["sun_azim"] + 180.0)))
        gd = _dot(nt, hxy, gvec, "gd", (-1020, Y - 4600))
        gd = _math(nt, "POWER", _math(nt, "MAXIMUM", gd, 0.0, "gdm", (-860, Y - 4600)),
                   2.0, "gdp", (-700, Y - 4600))
        gband = _math(nt, "SUBTRACT", 1.0,
                      _smooth(nt, elev, 0.0, float(cfg["city_width"]), "gb",
                              (-860, Y - 4760)), "gb1", (-700, Y - 4760))
        gk = _math(nt, "MULTIPLY", gd, gband, "gk", (-540, Y - 4660))
        gk = _math(nt, "MULTIPLY", gk, float(cfg["city_glow"]), "gkk", (-380, Y - 4660))
        sky = _addc(nt, sky, _mulc(nt, cfg["_city"], gk, "gc", (-220, Y - 4660)),
                    1.0, "sky_city", (380, Y - 400))
        if float(cfg["ground_glow"]) > 0.0:
            # light coming *up* off the lit ground: only the lower hemisphere can
            # carry it, and that is exactly where a glossy floor reads it back
            gn = _math(nt, "MINIMUM", z, 0.0, "gn", (-1180, Y - 4920))
            gn = _math(nt, "MULTIPLY", gn, -1.0, "gn1", (-1020, Y - 4920))
            gn = _math(nt, "POWER", gn, 1.6, "gnp", (-860, Y - 4920))
            gn = _math(nt, "MULTIPLY", gn, float(cfg["ground_glow"]), "gnk",
                       (-700, Y - 4920))
            gn = _math(nt, "MULTIPLY", gn, gband, "gnb", (-540, Y - 4920))
            sky = _addc(nt, sky, _mulc(nt, cfg["_city"], gn, "gnc", (-380, Y - 4920)),
                        1.0, "sky_gnd", (380, Y - 600))

    # ----------------------------------------------------------------- 10 ---
    # output.  The dome is emissive, so camera rays and reflections get the
    # full grade; `ambient` is handled by the flat world fill below, which is
    # what diffuse saturation actually needs (see `_ambient_world`).
    k = float(cfg["strength"]) * float(cfg["gain"])
    kw = _n(nt, "ShaderNodeValue", "gain", (600, Y - 200))
    kw.outputs[0].default_value = k
    cam_c = _mulc(nt, sky, kw.outputs[0], "cam_c", (760, Y), fac=1.0)
    if night_add is not None:
        # Stars, the moon disc and its halo are *emitters at a known display
        # brightness*, not sky radiance: they go in after the gain multiply.
        # Before this, gain=11 turned a 0.45 moon halo into a +0.79 linear
        # wash and night_torch rendered as a white field (band 0.942) with
        # no stars at all.
        cam_c = _addc(nt, cam_c, night_add, 1.0, "cam_night", (900, Y - 120))
    em = _n(nt, "ShaderNodeEmission", "emit", (1080, Y))
    nt.links.new(cam_c, em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    out = _n(nt, "ShaderNodeOutputMaterial", "out", (1290, Y))
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    w = _ambient_world(scene, cfg)

    cfg["_world"] = w
    cfg["_mat"] = mat
    cfg["_dome"] = dome
    cfg["_camloc_node"] = cl
    cfg["_scene"] = scene
    _LAST["cfg"] = cfg
    cfg["_gain"] = k
    _install_grade_hook()
    print("[sky] %-16s clouds=%.2f low=%.2f gain=%.1f sat=%.2f amb=%.2f "
          "elev=%.1f az=%.0f" % (preset, cfg["clouds"], cfg["cloud_low"],
                                 cfg["gain"], cfg["sat"], cfg["ambient"],
                                 cfg["sun_elev"], cfg["sun_azim"]), flush=True)
    return cfg


# =========================================================================== #
#  sun
# =========================================================================== #
def sun(scene, preset="morning_town", cfg=None, name="Sun", **over):
    """Create or update the key light from the same preset.

    Returns the light object.  `world()` and `sun()` reading one dict is the
    whole point: a driver cannot light a scene against a sky that disagrees
    with it, which is what v1's separate tables allowed.
    """
    cfg = cfg if isinstance(cfg, dict) and "_svec" in cfg else _cfg(preset, **over)
    ob = None
    for o in bpy.data.objects:
        if o.type == "LIGHT" and o.data.type == "SUN" and o.name == name:
            ob = o
            break
    if ob is None:
        for o in bpy.data.objects:
            if o.type == "LIGHT" and o.data.type == "SUN":
                ob = o
                break
    if ob is None:
        data = bpy.data.lights.new(name + "Data", "SUN")
        ob = bpy.data.objects.new(name, data)
        scene.collection.objects.link(ob)
    d = ob.data
    d.energy = float(cfg["sun_energy"])
    d.color = tuple(cfg["sun_color"])[:3]
    try:
        d.angle = math.radians(float(cfg["sun_angle"]))
    except Exception:                                        # noqa: BLE001
        pass
    d.use_shadow = True
    ob.rotation_euler = (math.radians(90.0 - float(cfg["sun_elev"])), 0.0,
                         math.radians(float(cfg["sun_azim"])))
    return ob


# =========================================================================== #
#  aerial perspective
# =========================================================================== #
def aerial_perspective(cfg, **over):
    """The AP parameter block for a preset (or for a plain dict of overrides).

    Aerial perspective is *scattering within the viewing cone*: a surface
    20 km away loses contrast and slides toward the colour of the air between
    it and the camera.  `hd_atmosphere.haze` is the other half of the same
    physics -- a volume you can see through, with banks and god rays, that owns
    the near and middle ground (0.3-3 km).  AP owns everything past that, where
    the volume is too thin to shade but the accumulated scattering is not.

    Rendered per pixel from the camera's *view distance*, inside every
    material, because EEVEE Next does not hand the compositor a Mist pass (see
    `_mist_ok`); the compositor path is kept for Cycles and older builds.

        fac = ((dist - start) / depth) ^ gamma        clamped to 0..1
        far = mix(haze_colour, sky_horizon_colour, warm * max(sun_dot,0))

    `fac` is 0 at the horizon (the sky already *is* the air) and 1 at `depth`.
    Returns a dict; pass it to `post()`, or read the keys yourself.
    """
    src = dict(cfg) if isinstance(cfg, dict) else dict(PRESETS.get(
        str(cfg), BASE))
    src.update(over)
    hz = src.get("_haze") or _srgb(src.get("haze", "#c2d0d8"))
    hor = src.get("_horizon") or _srgb(src.get("horizon", "#a9c8dc"))
    near = src.get("_apn") or _srgb(src.get("ap_near", "#7c8f9c"))
    far = src.get("_apf") or list(hor)
    warm = float(src.get("ap_warm", 0.35))
    sun_c = src.get("sun_color", (1.0, 0.9, 0.8))
    return {
        "on": float(src.get("ap", 0.0)) > 0.0,
        "fac": float(src.get("ap", 0.0)),
        "start_m": float(src.get("ap_start", 700.0)),
        "depth_m": float(src.get("ap_depth", 22000.0)),
        "gamma": float(src.get("ap_gamma", 1.35)),
        # near colour is the shadowed air, far is the sky the object is seen
        # against; the sun side of the far colour is pushed warm
        "near": near,
        "far": [min(1.0, far[i] + (sun_c[i] - far[i]) * warm * 0.55)
                for i in range(3)],
        "haze": hz,
        "horizon": hor,
        "sun": list(sun_c)[:3],
    }


def _mist_ok(scene):
    """Does this engine hand the compositor a Mist pass?

    Measured on Blender 5.2.3: a `CompositorNodeRLayers` created over EEVEE Next
    has exactly two outputs, ``['Image', 'Alpha']`` -- no Mist and no Depth --
    so a compositor AP chain reads 0.0 everywhere and changes nothing.  Cycles
    still exposes Mist.  We probe instead of trusting the engine name.
    """
    try:
        tmp = bpy.data.node_groups.new("_sky_mist_probe", "CompositorNodeTree")
    except Exception:                                        # noqa: BLE001
        return False
    try:
        nd = tmp.nodes.new("CompositorNodeRLayers")
        names = [s.name for s in nd.outputs]
    except Exception:                                        # noqa: BLE001
        names = []
    finally:
        bpy.data.node_groups.remove(tmp)
    # The socket appears as soon as the view layer asks for the pass, but under
    # EEVEE Next the buffer behind it stays empty (measured: a chain reading
    # only `Mist` renders a flat 0.0004 frame), so the socket existing is not
    # enough -- the engine has to actually fill it.
    if scene.render.engine.startswith("BLENDER_EEVEE"):
        return False
    return "Mist" in names


def _ap_material(mat, ap):
    """Blend one material toward the air colour by camera view distance.

    MixShader(orig, Emission(air_colour)) with fac from the Camera Data node:
    an unlit haze card in front of the surface.  That is what aerial
    perspective does optically -- the surface's own shading is replaced by the
    light scattered toward the camera.
    """
    if not mat or not mat.use_nodes or not mat.node_tree:
        return False
    if mat.name.startswith("SKY"):
        return False                       # the dome *is* the air
    nt = mat.node_tree
    old = nt.nodes.get("AP_mix")
    if old is not None:
        # Already installed: retune in place.  Tearing it down instead would
        # leave Material Output with no surface link (the old AP_mix was its
        # only input) and the whole material renders black -- which is exactly
        # what a second post() call used to do.
        try:
            nt.nodes["AP_d0"].inputs[1].default_value = ap["start_m"]
            nt.nodes["AP_u"].inputs[1].default_value = ap["depth_m"]
            nt.nodes["AP_k"].inputs[1].default_value = ap["fac"]
            for nd in nt.nodes:
                if nd.name.startswith("AP_em"):
                    nd.inputs["Color"].default_value = (
                        ap["far"][0], ap["far"][1], ap["far"][2], 1.0)
            return True
        except Exception:                                    # noqa: BLE001
            pass
    for n in list(nt.nodes):
        if n.name.startswith("AP_"):
            nt.nodes.remove(n)
    out = None
    for n in nt.nodes:
        if n.bl_idname == "ShaderNodeOutputMaterial" and n.is_active_output:
            out = n
            break
    if out is None or not out.inputs["Surface"].links:
        return False
    src = out.inputs["Surface"].links[0].from_socket
    cam = _n(nt, "ShaderNodeCameraData", "AP_cam", (-700, 320))
    # fac = 1 - exp(-(d - start)/depth), i.e. Beer-Lambert extinction with a
    # 1/e scale of `ap_depth` metres.  A linear ramp puts 100% of the air
    # colour at `depth`, which needs depth >= the farthest visible surface and
    # then leaves no contrast at all in the 0-2 km range where most of the
    # picture lives.  Exponential compresses the near field and keeps ramping
    # out to the horizon: at 3 km with depth 5200 the blend is 0.44, not 0.23.
    # POWER(2.718..., -x) is used instead of ShaderNodeMath's EXPONENT: the
    # latter underflows to NaN for large negative x in 5.2.3 and poisons the
    # whole frame (see the note in the Mie section).
    d0 = _math(nt, "SUBTRACT", cam.outputs["View Distance"], ap["start_m"],
               "AP_d0", (-540, 320))
    d0 = _math(nt, "MAXIMUM", d0, 0.0, "AP_d1", (-420, 320))
    u = _math(nt, "DIVIDE", d0, ap["depth_m"], "AP_u", (-300, 320))
    nu = _math(nt, "MULTIPLY", u, -1.0, "AP_nu", (-180, 320))
    ex = _math(nt, "POWER", 2.718281828459045, nu, "AP_ex", (-60, 320))
    k1 = _math(nt, "SUBTRACT", 1.0, ex, "AP_k1", (60, 320))
    if abs(ap["gamma"] - 1.0) > 1.0e-4:
        k1 = _math(nt, "POWER", k1, ap["gamma"], "AP_pow", (180, 320), clamp=True)
    k = _math(nt, "MULTIPLY", k1, ap["fac"], "AP_k", (300, 320), clamp=True)
    em = _n(nt, "ShaderNodeEmission", "AP_em", (120, 180))
    if em.bl_idname != "ShaderNodeEmission":       # pragma: no cover - 5.x
        # A Background closure mixed into a *surface* renders black, so never
        # let the node helper fall back to it here.
        nt.nodes.remove(em)
        em = _n(nt, "ShaderNodeBsdfPrincipled", "AP_em", (120, 180))
        for key, val in (("Base Color", (0.0, 0.0, 0.0, 1.0)),
                         ("Roughness", 1.0), ("Metallic", 0.0)):
            try:
                em.inputs[key].default_value = val
            except Exception:                                # noqa: BLE001
                pass
        for key in ("Emission Color", "Emission"):
            try:
                em.inputs[key].default_value = (ap["far"][0], ap["far"][1],
                                                ap["far"][2], 1.0)
                break
            except Exception:                                # noqa: BLE001
                continue
        for key in ("Emission Strength",):
            try:
                em.inputs[key].default_value = 1.0
            except Exception:                                # noqa: BLE001
                pass
    _AP_EM_KIND["id"] = em.bl_idname
    _AP_EM_KIND["n"] = _AP_EM_KIND.get("n", 0) + 1
    try:
        em.inputs["Strength"].default_value = 1.0
    except Exception:                                        # noqa: BLE001
        pass
    mix = _n(nt, "ShaderNodeMixShader", "AP_mix", (320, 120))
    nt.links.new(k, mix.inputs[0])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return True


def ap_materials(scene, cfg=None, **over):
    """Install the AP blend into every material the scene actually uses."""
    ap = aerial_perspective(cfg if cfg is not None else "morning_town", **over)
    seen, n = set(), 0
    for ob in scene.objects:
        for slot in getattr(ob, "material_slots", ()):
            m = slot.material
            if m is None or m.name in seen:
                continue
            seen.add(m.name)
            if _ap_material(m, ap):
                n += 1
    print("[sky] AP em=%s  installed on %d material(s), far=%s"
          % (_AP_EM_KIND.get("id"), n, ["%.2f" % c for c in ap["far"]]))
    return n


def _comp_mix(nt, name, loc=(0, 0)):
    """A colour mix node on the compositor, 4.x and 5.x spellings.

    5.x unified the compositor onto the shader node system: `CompositorNodeMix`
    and `CompositorNodeMixRGB` are both gone, and the plain `ShaderNodeMix`
    (data_type=RGBA) is what a compositor tree takes now.  Returns
    (node, a_socket, b_socket, fac_socket, out_socket).
    """
    for kind in ("ShaderNodeMix", "CompositorNodeMix", "CompositorNodeMixRGB"):
        try:
            nd = nt.nodes.new(kind)
        except Exception:                                    # noqa: BLE001
            continue
        try:
            if kind.startswith("Shader"):
                nd.data_type = "RGBA"
                ins = [s for s in nd.inputs if s.type == "RGBA"]
                outs = [s for s in nd.outputs if s.type == "RGBA"]
                if len(ins) < 2 or not outs:
                    raise RuntimeError("no RGBA sockets on %s" % kind)
                return nd, ins[0], ins[1], nd.inputs[0], outs[0]
            nd.data_type = "RGBA"
            ins = [s for s in nd.inputs if s.type == "RGBA"]
            outs = [s for s in nd.outputs if s.type == "RGBA"]
            if len(ins) < 2 or not outs:
                raise RuntimeError("no RGBA sockets on %s" % kind)
            return nd, ins[0], ins[1], nd.inputs[0], outs[0]
        except Exception:                                    # noqa: BLE001
            nt.nodes.remove(nd)
            continue
    # last resort: MixRGB by name, which some forks keep around
    nd = nt.nodes.new("CompositorNodeMixRGB")
    return (nd, nd.inputs["Color1"], nd.inputs["Color2"],
            nd.inputs["Fac"], nd.outputs[0])


def _cn(nt, names, loc=(0, 0), **kw):
    """New node, trying 5.x (shader-unified) spellings before the 4.x ones.

    Blender 5.x deleted CompositorNodeMath / MapRange / Mix / ValToRGB from the
    compositor and expects the shader-family nodes instead; both spellings are
    requested in order so the file loads on either.
    """
    err = None
    for kind in names:
        try:
            nd = nt.nodes.new(kind)
        except Exception as exc:                             # noqa: BLE001
            err = exc
            continue
        nd.location = loc
        for key, val in kw.items():
            try:
                setattr(nd, key, val)
            except Exception:                                # noqa: BLE001
                pass
        return nd
    raise RuntimeError("no node of %r: %s" % (names, err))


def _cmath(nt, op, loc=(0, 0), clamp=False, a=None, b=None, name=""):
    nd = _cn(nt, ("ShaderNodeMath", "CompositorNodeMath"), loc,
             operation=op, use_clamp=clamp)
    if name:
        nd.name = name
    if a is not None:
        nd.inputs[0].default_value = a
    if b is not None:
        nd.inputs[1].default_value = b
    return nd


def _ap_nodes(nt, ap, loc=(0, 0)):
    """Build the AP chain on top of the Mist pass; returns (image, fac)."""
    rl = None
    for n in nt.nodes:
        if n.bl_idname == "CompositorNodeRLayers":
            rl = n
            break
    if rl is None:
        rl = _cn(nt, ("CompositorNodeRLayers",), (loc[0] - 400, loc[1]))
    mix, mix_a, mix_b, mix_f, mix_o = _comp_mix(nt, "sky_ap_mix", (loc[0] + 200, loc[1]))
    mix.name = "sky_ap_mix"
    mix_f.default_value = 0.0
    nt.links.new(rl.outputs["Image"], mix_a)
    # distance -> 0..1
    sub = _cmath(nt, "SUBTRACT", (loc[0] - 200, loc[1] - 200), b=ap["start_m"])
    nt.links.new(rl.outputs["Mist"], sub.inputs[0])
    div = _cmath(nt, "DIVIDE", (loc[0] - 60, loc[1] - 200),
                 b=max(1.0, ap["depth_m"] - ap["start_m"]))
    nt.links.new(sub.outputs[0], div.inputs[0])
    pw = _cmath(nt, "POWER", (loc[0] + 70, loc[1] - 200), clamp=True, b=ap["gamma"])
    nt.links.new(div.outputs[0], pw.inputs[0])
    # the background comes back as mist = 1.0, and the background is already
    # the colour of the air: nothing may be mixed into it
    skym = _cmath(nt, "SUBTRACT", (loc[0] + 70, loc[1] - 340), clamp=True, a=1.0)
    ramp = _cn(nt, ("ShaderNodeMapRange", "CompositorNodeMapRange"),
               (loc[0] - 60, loc[1] - 340), interpolation_type="SMOOTHSTEP")
    for key, val in (("From Min", 0.982), ("From Max", 0.9995),
                     ("To Min", 0.0), ("To Max", 1.0)):
        try:
            ramp.inputs[key].default_value = val
        except Exception:                                    # noqa: BLE001
            pass
    nt.links.new(rl.outputs["Mist"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], skym.inputs[1])
    fac = _cmath(nt, "MULTIPLY", (loc[0] + 200, loc[1] - 300), clamp=True)
    nt.links.new(pw.outputs[0], fac.inputs[0])
    nt.links.new(skym.outputs[0], fac.inputs[1])
    if ap["fac"] != 1.0:
        sc_ = _cmath(nt, "MULTIPLY", (loc[0] + 300, loc[1] - 300), clamp=True,
                     b=ap["fac"])
        nt.links.new(fac.outputs[0], sc_.inputs[0])
        fac = sc_
    # the far colour as a gradient between the two air colours, so near objects
    # pick up the shadowed air and distant ones the sky they sit against
    grd = _cn(nt, ("ShaderNodeValToRGB", "CompositorNodeValToRGB"),
              (loc[0] + 320, loc[1] - 480))
    cr = grd.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = tuple(ap["near"]) + (1.0,)
    cr.elements[1].position = 1.0
    cr.elements[1].color = tuple(ap["far"]) + (1.0,)
    mid = cr.elements.new(0.55)
    mid.color = tuple([(ap["near"][i] + ap["far"][i]) * 0.5 for i in range(3)]) + (1.0,)
    nt.links.new(div.outputs[0], grd.inputs[0])
    nt.links.new(grd.outputs[0], mix_b)
    nt.links.new(fac.outputs[0], mix_f)
    return mix_o, fac.outputs[0]


_LAST = {}


def post(scene, preset=None, cfg=None, ap=True, glare=True, **over):
    """Compositor: aerial perspective on the Mist pass, then an optional Glare.

    Inserted between the render layer's Image output and whoever was consuming
    it, so it composes with whatever the driver already built instead of
    replacing it.  Idempotent: calling it twice just rebuilds its own nodes.
    """
    if cfg is None:
        cfg = _LAST.get("cfg")
        if cfg is None or cfg.get("_scene") is not scene:
            cfg = preset if isinstance(preset, dict) else _cfg(
                preset or "morning_town", **over)
    if isinstance(cfg, str):
        cfg = _cfg(cfg, **over)
    nt, mode = _comp_tree()
    # drop our own nodes from a previous call
    for n in list(nt.nodes):
        if n.name.startswith("sky_") or n.name.startswith("AP_"):
            nt.nodes.remove(n)
    rl = None
    for n in nt.nodes:
        if n.bl_idname == "CompositorNodeRLayers":
            rl = n
            break
    if rl is None:
        rl = nt.nodes.new("CompositorNodeRLayers")
        rl.location = (-600, 0)
    out, sock = _comp_out(nt, mode)
    # who was reading the render result?
    img_sock = rl.outputs["Image"]
    consumers = [lk.to_socket for lk in nt.links if lk.from_socket == img_sock]
    if not consumers:
        consumers = [sock]
    for c in consumers:
        for lk in [l for l in nt.links if l.to_socket == c and l.from_socket == img_sock]:
            nt.links.remove(lk)
    last = img_sock
    res = {}
    if ap and aerial_perspective(cfg)["on"]:
        apcfg = aerial_perspective(cfg)
        scene.view_layers[0].use_pass_mist = True
        try:
            ms = scene.world.mist_settings
            ms.use_mist = True
            ms.start = apcfg["start_m"]
            ms.depth = apcfg["depth_m"]
            ms.falloff = "LINEAR"
        except Exception:                                    # noqa: BLE001
            pass
        if _mist_ok(scene):
            last, _ = _ap_nodes(nt, apcfg, (0, 0))
            apcfg["method"] = "compositor-mist"
        else:
            # EEVEE Next 5.x: no Mist in the compositor.  Colour the geometry
            # in the materials instead, from the Camera Data node.
            ap_materials(scene, cfg=cfg)
            apcfg["method"] = "materials-view-distance"
        res["ap"] = apcfg
    if glare and float(cfg.get("flare", 0.0)) > 0.0:
        g = nt.nodes.new("CompositorNodeGlare")
        g.name = "sky_glare"
        g.location = (700, -260)
        for attr, val in (("glare_type", cfg.get("flare_type", "FOG_GLOW")),
                          ("quality", "HIGH"),
                          ("threshold", float(cfg.get("flare_thr", 18.0))),
                          ("mix", -1.0 + 2.0 * min(1.0, float(cfg["flare"]))),
                          ("size", 8)):
            try:
                setattr(g, attr, val)
            except Exception:                                # noqa: BLE001
                pass
        nt.links.new(last, g.inputs[0])
        last = g.outputs[0]
        res["glare"] = float(cfg["flare"])
    for c in consumers:
        nt.links.new(last, c)
    scene.render.use_compositing = True
    _LAST["cfg"] = cfg
    return res


def _comp_tree():
    """(node_tree, mode) for the compositor, on the 4.x and 5.x APIs."""
    sc = bpy.context.scene
    if hasattr(sc, "compositing_node_group"):
        g = sc.compositing_node_group
        if g is None:
            g = bpy.data.node_groups.new("SkyComp", "CompositorNodeTree")
            sc.compositing_node_group = g
        return g, "group"
    try:
        sc.use_nodes = True
    except Exception:                                        # noqa: BLE001
        pass
    return sc.node_tree, "tree"


def _comp_out(nt, mode):
    for n in nt.nodes:
        if n.bl_idname in ("NodeGroupOutput", "CompositorNodeComposite"):
            return n, n.inputs[0]
    if mode == "group":
        out = nt.nodes.new("NodeGroupOutput")
        names = [i.name for i in nt.interface.items_tree
                 if getattr(i, "in_out", "") == "OUTPUT"]
        if "Image" not in names:
            nt.interface.new_socket(name="Image", in_out="OUTPUT",
                                    socket_type="NodeSocketColor")
    else:
        out = nt.nodes.new("CompositorNodeComposite")
    return out, out.inputs[0]


# =========================================================================== #
#  grade repair: the black-shadow bug
# =========================================================================== #
# What a surface that gets no direct sun has to come out at, in the *display*
# values the screenshots are made of.  Measured with `look/sky_lab.py shadow`
# on a 300 m cobbled street canyon (albedo = medkit cobble, i.e. the capital's
# real paving), AgX + the preset's own exposure, sun switched off as the
# reference.  Below 0.20 a stone surface reads as "black plastic"; above 0.40
# it stops being shade and starts being a second light.  0.235..0.353 is
# 60..90 / 255, the range the art direction asks for.
SHADOW_TARGET = (0.235, 0.353)

# Bright/Contrast's own socket scale is -1..+1 around the mid-grey pivot.
GRADE_CONTRAST_MAX = 1.0


def grade_fix(scene=None, contrast_max=GRADE_CONTRAST_MAX, verbose=False):
    """Put the compositor grade back on the scale the node actually uses.

    `hd_light.post()` writes ``(preset["contrast"] - 1.0) * 100.0`` into
    Bright/Contrast's *Contrast* socket, so the documented ``contrast: 1.10``
    that every preset carries lands on the node as **10.0**.  The node's maths
    in Blender 5.2 is::

        out = color * (1 + c) + (brightness - 0.5 * c)

    which at c = 10 is ``11 * color - 5``: *every linear value below 0.4545 is
    clipped to exactly zero*.  A street in shade lives at 0.02-0.10 linear, so
    a whole half-frame comes back as a flat 8-20 / 255 once AgX and the fog
    glow have lifted the zeros a little -- the "shadow is painted black, this
    looks like a model" complaint.

    The socket wants ``contrast - 1.0`` (0.10 for 1.10): a +10 % punch around
    the pivot, which is what the preset table has always meant.  Anything on
    the *other* scale (|c| > 1) is divided by 100, which is exactly right for
    the ``(x - 1) * 100`` idiom and a no-op once the wiring is fixed.

    Idempotent, never raises, safe to call before every render.  Returns a dict
    so a caller can log what it touched.
    """
    out = {"found": 0, "before": None, "after": None, "fixed": 0}
    sc = scene
    if sc is None:
        try:
            sc = bpy.context.scene
        except Exception:                                    # noqa: BLE001
            return out
    nt = getattr(sc, "compositing_node_group", None)
    if nt is None:
        try:
            nt = sc.node_tree
        except Exception:                                    # noqa: BLE001
            nt = None
    if nt is None:
        return out
    for n in nt.nodes:
        if n.bl_idname != "CompositorNodeBrightContrast":
            continue
        out["found"] += 1
        sock = n.inputs.get("Contrast")
        if sock is None or sock.is_linked:
            continue
        v = float(sock.default_value)
        if out["before"] is None:
            out["before"] = v
        new = v
        if abs(v) > contrast_max:
            new = v / 100.0
        if new != v:
            sock.default_value = new
            out["fixed"] += 1
        if out["after"] is None:
            out["after"] = new
        if verbose:
            print("[sky] grade %-14s contrast %.3f -> %.3f"
                  % (n.name, v, new), flush=True)
    return out


_GRADE_HOOKED = [False]


def _grade_pre(scene, *_a):
    """render_pre: repair the grade on the way into every frame.

    `look/render.py` calls ``L.post()`` *after* ``hd_sky.world()`` and
    hd_light rebuilds the whole compositor per shot, so a one-shot repair from
    here would be thrown away one line later.  A ``render_pre`` handler is the
    only place that is immune to that call order -- and to hd_weather splicing
    its own nodes in afterwards.
    """
    try:
        grade_fix(scene)
    except Exception:                                        # noqa: BLE001
        pass


def _install_grade_hook():
    """Arm `_grade_pre` once per session (idempotent)."""
    if _GRADE_HOOKED[0]:
        return True
    try:
        h = bpy.app.handlers.render_pre
        if _grade_pre not in h:
            h.append(_grade_pre)
        _GRADE_HOOKED[0] = True
    except Exception:                                        # noqa: BLE001
        return False
    return True


try:                                        # survive a .blend load, not just a session
    bpy.app.handlers.persistent(_grade_pre)
except Exception:                                            # noqa: BLE001
    pass


# =========================================================================== #
#  atmosphere bridge
# =========================================================================== #
def atmosphere(cfg, weather=None, **over):
    """Match hd_atmosphere's volumetric haze to a sky preset.

    The haze owns 0.3-3 km (banks, god rays, the volume you can look *through*);
    AP owns the far field.  Both read their colour from this preset so a ridge
    at 400 m and a mountain at 9 km sit in the same air.
    """
    import hd_atmosphere as ATM
    if not isinstance(cfg, dict):
        cfg = _cfg(str(cfg), **over)
    wx = weather or weather_of(cfg["preset"])
    a = aerial_perspective(cfg)
    kw = dict(color=tuple(a["haze"]),
              density=float(cfg.get("haze_density", 0.00034)),
              height=float(cfg.get("haze_height", 900.0)),
              aniso=float(cfg.get("haze_aniso", 0.55)))
    kw.update({k: v for k, v in over.items() if k in
               ("density", "height", "extent", "center", "color", "aniso",
                "band", "band_height")})
    return ATM.haze(wx, **kw)


def weather_of(sky_preset):
    """Nearest hd_weather state for a sky preset (for hd_atmosphere's lookup)."""
    for wx, sp in WEATHER.items():
        if sp == sky_preset:
            return wx
    return "clear"


def apply_all(scene, preset="morning_town", **over):
    """world + sun + exposure + post, in the one order that works."""
    cfg = world(scene, preset, **over)
    sun(scene, cfg=cfg)
    if over.get("apply_exposure", True):
        try:
            scene.view_settings.exposure = float(cfg["exposure"])
        except Exception:                                    # noqa: BLE001
            pass
    post(scene, cfg=cfg)
    return cfg


# =========================================================================== #
#  cli: a one-off sky render, used to sanity check a preset in isolation
# =========================================================================== #
def preview(args=None):
    """blender -b --python hd_sky.py -- morning_town [out.png] [azim] [elev]"""
    argv = list(sys.argv)
    rest = argv[argv.index("--") + 1:] if "--" in argv else []
    preset = rest[0] if rest else "morning_town"
    out = rest[1] if len(rest) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..",
        "renders", "kingdom", "look", "sky", "%s.png" % preset)
    az = float(rest[2]) if len(rest) > 2 else None
    el = float(rest[3]) if len(rest) > 3 else None
    out = os.path.abspath(out)
    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out), exist_ok=True)
    sc = bpy.context.scene
    over = {}
    if az is not None:
        over["sun_azim"] = float(az)
    cfg = world(sc, preset, **over)
    if az is not None or el is not None:
        cam = sc.camera
        if cam is None:
            cd = bpy.data.cameras.new("preview")
            cam = bpy.data.objects.new("preview", cd)
            sc.collection.objects.link(cam)
            sc.camera = cam
        cd = cam.data
        cd.lens = 18.0
        look_az = float(az if az is not None else cfg["sun_azim"])
        look_el = float(el if el is not None else 6.0)
        cam.location = (0.0, 0.0, 0.0)
        cam.rotation_euler = (math.radians(90.0 - look_el), 0.0,
                              math.radians(look_az))
    for attr, val in (("engine", "BLENDER_EEVEE"), ("resolution_x", 640),
                      ("resolution_y", 360), ("filepath", out),
                      ("file_format", "PNG")):
        try:
            setattr(sc.render, attr, val)
        except Exception:                                    # noqa: BLE001
            pass
    try:
        sc.render.image_settings.file_format = "PNG"
        sc.eevee.taa_render_samples = 16
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.exposure = float(cfg["exposure"])
    except Exception:                                        # noqa: BLE001
        pass
    bpy.ops.render.render(write_still=True)
    print("[sky] wrote %s" % out, flush=True)
    return cfg


if __name__ == "__main__" and "--" in sys.argv:
    preview(sys.argv)
