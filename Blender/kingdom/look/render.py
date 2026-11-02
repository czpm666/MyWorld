"""Look-dev renderer for the Asura capital.

Loads a saved city .blend, puts the hd_light rig on it, and renders named
cameras.  Everything is driven from the command line so a run can be repeated
exactly:

    blender -b capital_full.blend --python look/render.py -- \
        --preset golden_street --shots game,aerial --out renders/kingdom/look \
        --samples 48 --res 1280x720 --tag t1

Design notes
------------
* The rig is `hd_light` (sky / sun / ground bounce / haze / post).  That module
  was written for Cycles close-ups and never wired into the city build; this
  driver reuses it but adds an EEVEE path so an iteration costs seconds.
* EEVEE gets raytraced GI + fast-GI screen-space AO, which is what produces the
  contact darkening the old flat rig was missing.
* Camera framing for the `game` shot is copied from the real game camera:
  TopDownCameraRig defaults (pitch 52 deg, distance 34 m, vertical FOV 30 deg),
  so what we judge here is what the player sees.
"""
import bpy
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import hd_light as L          # noqa: E402
import hd_atmosphere as A     # noqa: E402

LAYOUT = os.path.join(ROOT, "layout.json")


# ---------------------------------------------------------------------------
# small utilities
# ---------------------------------------------------------------------------
def log(*a):
    print("[rig]", *a, flush=True)


def argv():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def opts():
    out, i = {}, 0
    a = argv()
    while i < len(a):
        k = a[i]
        if k.startswith("--"):
            key = k[2:]
            if i + 1 < len(a) and not a[i + 1].startswith("--"):
                out[key] = a[i + 1]
                i += 2
            else:
                out[key] = True
                i += 1
        else:
            i += 1
    return out


def fnum(o, k, d=None):
    v = o.get(k, d)
    return None if v is None else float(v)


def pair(s, d):
    if s is None:
        return d
    p = [float(x) for x in str(s).split(",")]
    return tuple(p)


# ---------------------------------------------------------------------------
# the layout: pick a spot on a real street frontage
# ---------------------------------------------------------------------------
_LAY = {"cache": None}


def layout():
    if _LAY["cache"] is None:
        try:
            with open(LAYOUT, "r", encoding="utf-8") as f:
                _LAY["cache"] = json.load(f)
        except Exception as exc:                                # noqa: BLE001
            log("layout unavailable:", exc)
            _LAY["cache"] = {}
    return _LAY["cache"]


def street_rays(want=6, kinds=None):
    """Camera standpoints picked by look/spots.py, which scores real enclosure.

    "Midpoint of the longest segment" kept landing in open yards: layout.json's
    street centre lines are loose pieces and the gaps between blocks are wider
    than any street polygon.  spots.py measures how much facade stands on each
    side of a standpoint instead, and the winners are cached as JSON.
    """
    import json as _json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spots.json")
    if not os.path.exists(path):
        log("no spots.json -- run: python look/spots.py")
        return [((0.0, -34.0), (0.0, 1.0), 8.0, "main")]
    data = _json.load(open(path, "r", encoding="utf-8"))
    out = []
    for q in data.get("picks") or ():
        if kinds and q.get("kind") not in kinds:
            continue
        out.append(((q["x"], q["y"]), (q["ux"], q["uy"]), float(q.get("w") or 6.0),
                    q.get("kind")))
        if len(out) >= want:
            break
    return out or [((0.0, -34.0), (0.0, 1.0), 8.0, "main")]


def street_views(want=6):
    """1.72 m eye-height views looking down a street's own centre line."""
    out = []
    for p, u, _w, _k in street_rays(want):
        out.append(((p[0], p[1], 1.72), (p[0] + u[0] * 46.0, p[1] + u[1] * 46.0, 3.2)))
    return out


def street_spot():
    return street_views(1)[0]


def game_cam(spot):
    """The player's own framing: pitch 52 deg, 34 m back, 30 deg vertical FOV.

    Copied from TopDownCameraRig (pitch 52, distance 34, fov 30) and reproduced
    exactly: the camera sits `distance` behind the pivot along a 52 deg descent,
    so pivot -> camera is (0, +20.93 m, +26.79 m) for a yaw looking back at us.
    """
    eye, look = spot
    yaw = math.atan2(look[1] - eye[1], look[0] - eye[0])
    pitch = math.radians(52.0)
    dist = 34.0
    px, py = eye[0], eye[1]
    pz = 1.0
    cx = px - math.cos(yaw) * dist * math.cos(pitch)
    cy = py - math.sin(yaw) * dist * math.cos(pitch)
    cz = pz + dist * math.sin(pitch)
    return (cx, cy, cz), (px + math.cos(yaw) * 1.5, py + math.sin(yaw) * 1.5, pz)


def shot_library(path=None):
    """look/shots.json -- the validated camera library, if it exists.

    `_shotgen.py` writes it from geometry measured in the blend (`_shotmap.json`)
    and the QA pass (`_shotqa.py`) can veto individual cameras, so this file, not
    the hand table above, is what the look-dev loop should be judged on.  The
    hand table stays as a fallback and as an A/B reference.
    """
    path = path or os.path.join(HERE, "shots.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        lib = json.load(fh).get("shots") or []
    out = {}
    for s in lib:
        spec = dict(loc=tuple(s["pos"]), look=tuple(s["look"]),
                    kind="wide" if s.get("kind") in ("aerial", "overview")
                    else "street",
                    shot_kind=s.get("kind"), note=s.get("note", ""))
        if s.get("fov"):
            spec["vfov"] = float(s["fov"])
        else:
            spec["lens"] = float(s.get("lens") or 35.0)
        for k in ("haze_mul", "haze_extent"):
            if k in s:
                spec[k] = s[k]
        out[s["name"]] = spec
    log("shot library: %d cameras from %s" % (len(out), os.path.basename(path)))
    return out


def shot_table(lib_path=None):
    # The city grew 1.48x (CITY_SCALE in capital.py), so every hand-placed
    # camera is scaled with it; the landmark ones are derived from the same
    # constants capital.py uses, not from the old hard numbers.
    S = 1.48
    rock = (0.0, 205.0 * S)
    cath = (-152.0 * S, 58.0 * S)
    table = {
        # --- hero / marketing cameras -----------------------------------------
        "aerial": dict(loc=(700.0 * S, -1240.0 * S, 480.0 * S),
                       look=(0.0, 20.0, 15.0),
                       lens=50.0, kind="wide", haze_mul=0.85, haze_extent=5200.0),
        "overview": dict(loc=(940.0 * S, -1180.0 * S, 610.0 * S),
                         look=(0.0, -20.0, 10.0),
                         lens=34.0, kind="wide", haze_mul=0.85, haze_extent=5200.0),
        "castle": dict(loc=(150.0 * S, 340.0 * S, 58.0),
                       look=(0.0, rock[1] + 60.0, 40.0),
                       lens=50.0, kind="street"),
        "cathedral": dict(loc=(cath[0] + 200.0, cath[1] - 150.0, 20.0),
                          look=(cath[0], cath[1], 34.0),
                          lens=28.0, kind="street"),
        "plaza": dict(loc=(9.2 * S, 22.0 * S, 12.0), look=(9.2 * S, 92.0 * S, 6.0),
                      lens=35.0, kind="street"),
        "gate": dict(loc=(6.0 * S, 545.0 * S, 2.0), look=(0.0, 947.0, 19.0),
                     lens=35.0, kind="street"),
        "outer": dict(loc=(330.0 * S, -260.0 * S, 210.0 * S),
                      look=(600.0 * S, 90.0 * S, 16.0),
                      lens=30.0, kind="wide", haze_mul=1.4, haze_extent=3600.0),
        # --- the frame the player actually sees -------------------------------
    }
    table.update(shot_library(lib_path))
    views = street_views(6)
    for i, spot in enumerate(views):
        geye, glook = game_cam(spot)
        table["game" if i == 0 else "game%d" % (i + 1)] = dict(
            loc=geye, look=glook, vfov=30.0, kind="wide")
    for i, spot in enumerate(views):
        table["street" if i == 0 else "street%d" % (i + 1)] = dict(
            loc=spot[0], look=spot[1], lens=24.0, kind="street")
    return table


# ---------------------------------------------------------------------------
# scene surgery
# ---------------------------------------------------------------------------
def wipe_rig():
    """Drop every light, camera and volume object the rig owns.

    `WX_` is hd_weather's namespace: its precipitation, puddles and fog volume
    belong to one shot, so they must not survive into the next one.
    """
    keep = []
    for ob in list(bpy.data.objects):
        if ob.type in ("LIGHT", "CAMERA") or ob.name.startswith("Atmosphere") \
                or ob.name.startswith("LIGHT_") or ob.name.startswith("WX_"):
            keep.append(ob)
    for ob in keep:
        bpy.data.objects.remove(ob, do_unlink=True)
    return len(keep)


def build_rig(preset, elev, azim, haze=True, haze_mul=1.0, haze_extent=2800.0,
              contact=True, cam=None, sky=None, clouds=None, sky_strength=None,
              ambient=None, exposure=None, sun=None):
    p = L.PRESETS[preset]
    elev = p["sun_elev_wide"] if elev is None else elev
    azim = p["sun_azim"] if azim is None else azim
    L.sky(preset, elev, azim)
    if sky:
        # hd_sky builds a real gradient + sun disc + cumulus sky; the module it
        # replaces (hd_atmosphere.world_sky) collapses to a flat constant above
        # the horizon, which is what made every wide shot look fogged.
        import hd_sky as SKY
        over = {"elevation": float(elev), "azimuth": float(azim)}
        if clouds is not None:
            over["clouds"] = float(clouds)
        if sky_strength is not None:
            over["strength"] = float(sky_strength)
        if ambient is not None:
            over["ambient"] = float(ambient)
        SKY.world(bpy.context.scene, sky, **over)
        log("sky: hd_sky preset=%s elev=%.1f azim=%.1f clouds=%s amb=%s"
            % (sky, elev, azim, "preset" if clouds is None else "%.2f" % clouds,
               "preset" if ambient is None else "%.2f" % ambient))
    L.sun(preset, elev, azim)
    if sun is not None:
        for ob in bpy.data.objects:
            if ob.type == "LIGHT" and ob.data.type == "SUN":
                ob.data.energy = float(sun)
        log("sun energy -> %.1f" % float(sun))
    if exposure is not None:
        bpy.context.scene.view_settings.exposure = float(exposure)
        log("exposure -> %.2f" % float(exposure))
    L.bounce(preset)
    if contact:
        try:
            L.contact(preset)
        except Exception as exc:                                # noqa: BLE001
            log("contact pass skipped:", exc)
    if haze:
        L.haze(preset, center=None if cam is None else (cam[0], cam[1]),
               mul=haze_mul, extent=haze_extent)
    try:
        L.post(preset)
    except Exception as exc:                                    # noqa: BLE001
        log("post failed:", exc)
    return elev, azim


def setup_engine(kind="eevee", samples=48, res=(1280, 720), vols=True):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = int(res[0]), int(res[1])
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.compression = 15
    if kind.lower().startswith("cyc"):
        try:
            bpy.ops.preferences.addon_enable(module="cycles")
        except Exception:                                       # noqa: BLE001
            pass
        sc.render.engine = "CYCLES"
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = "OPTIX"
            prefs.get_devices()
            for d in prefs.devices:
                d.use = d.type == "OPTIX"
            sc.cycles.device = "GPU"
        except Exception as exc:                                # noqa: BLE001
            log("cycles gpu:", exc)
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 6
        sc.cycles.diffuse_bounces = 3
        sc.cycles.glossy_bounces = 3
        sc.cycles.transmission_bounces = 2
        sc.cycles.caustics_reflective = False
        sc.cycles.caustics_refractive = False
        sc.cycles.filter_width = 1.4
        return "CYCLES"
    sc.render.engine = "BLENDER_EEVEE"
    ee = sc.eevee
    ee.taa_render_samples = samples
    ee.use_raytracing = True
    ee.ray_tracing_method = "SCREEN"
    o = ee.ray_tracing_options
    o.resolution_scale = "1"
    o.screen_trace_quality = 0.6
    o.screen_trace_thickness = 0.25
    o.use_denoise = True
    o.denoise_spatial = True
    o.trace_max_roughness = 0.6
    ee.use_fast_gi = True
    ee.fast_gi_method = "GLOBAL_ILLUMINATION"
    ee.fast_gi_distance = 2.5
    ee.fast_gi_resolution = "1"
    ee.fast_gi_ray_count = 4
    ee.fast_gi_step_count = 12
    ee.use_shadows = True
    ee.shadow_ray_count = 2
    ee.shadow_step_count = 8
    ee.shadow_resolution_scale = 1.0
    ee.shadow_pool_size = "1024"
    if vols:
        ee.use_volumetric_shadows = False
        ee.use_volume_custom_range = True
        ee.volumetric_start = 0.5
        ee.volumetric_end = 4000.0
        ee.volumetric_tile_size = "4"
        ee.volumetric_samples = 64
        ee.volumetric_sample_distribution = 0.75
    return "EEVEE"


def make_camera(spec, elev_unused=None):
    cam = bpy.data.cameras.new("rig_cam")
    ob = bpy.data.objects.new("rig_cam", cam)
    bpy.context.scene.collection.objects.link(ob)
    eye, look = spec["loc"], spec["look"]
    import mathutils
    ob.location = eye
    d = mathutils.Vector(look) - mathutils.Vector(eye)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.clip_start = 0.25
    cam.clip_end = 8000.0
    if "vfov" in spec:
        # sensor_fit AUTO uses the larger dimension (36 mm here, 16:9)
        cam.sensor_fit = "VERTICAL"
        cam.sensor_height = 24.0
        cam.lens = (12.0 / math.tan(math.radians(spec["vfov"] / 2.0)))
    else:
        cam.sensor_fit = "HORIZONTAL"
        cam.lens = spec.get("lens", 35.0)
    bpy.context.scene.camera = ob
    return ob


def tune_world(preset, strength=None):
    """The sky model, plus a strength override if a preset renders too dark."""
    if strength is None:
        return
    w = bpy.context.scene.world
    if w is None or w.node_tree is None:
        return
    for n in w.node_tree.nodes:
        if n.type == "BACKGROUND":
            n.inputs["Strength"].default_value = strength


def apply_weather(scene, name, center=(0.0, 0.0), ground_z=0.1,
                  radius=200.0, extent=1200.0, own_sky=True):
    """Hand one shot to hd_weather.  Contract fixed by the WEATHER agent.

    Order matters and is not negotiable:

      1. this driver's own rig (hd_light sun/bounce/contact, hd_sky world, the
         exposure knob) has already been applied by the caller;
      2. `WX.reset_materials()` -- drop masks left by the previous state;
      3. `WX.build(...)` -- the rain/snow/puddle/puff *meshes*; `apply_atmos`
         cannot make them;
      4. `WX.apply_atmos(...)` -- world + sun + exposure + `WX_Fog` volume +
         a `WX_Sat` node spliced into the compositor.  It deletes
         `Atmosphere*`, i.e. hd_light's haze, and it OWNS the compositor from
         here on: nothing may call `build_rig()`/`L.apply()` afterwards or the
         saturation node is silently rebuilt away;
      5. `WX.apply_materials(MAT, cfg)` -- wet/snow, unions over the scene.

    Imported inside the function on purpose: a missing or broken hd_weather must
    not take down every ordinary render in the project.
    """
    try:
        import hd_weather as WX
    except Exception as exc:                                    # noqa: BLE001
        log("weather: hd_weather unavailable (%s) -- ignoring --weather" % exc)
        return None
    try:
        cfg = WX.state(name)
    except Exception as exc:                                    # noqa: BLE001
        log("weather: %s" % exc)
        return None
    MAT = {m.name: m for m in bpy.data.materials}
    cx, cy = float(center[0]), float(center[1])
    try:
        WX.reset_materials()
    except Exception as exc:                                    # noqa: BLE001
        log("weather: reset_materials failed (%s)" % exc)
    try:
        WX.build(scene, name, MAT, radius=radius, center=(cx, cy), seed=9)
    except Exception as exc:                                    # noqa: BLE001
        log("weather: build failed (%s)" % exc)
    info = {}
    try:
        info = WX.apply_atmos(scene, cfg, center=(cx, cy), extent=extent,
                              sky=bool(own_sky))
    except Exception as exc:                                    # noqa: BLE001
        log("weather: apply_atmos failed (%s)" % exc)
    try:
        WX.apply_materials(MAT, cfg)
    except Exception as exc:                                    # noqa: BLE001
        log("weather: apply_materials failed (%s)" % exc)
    log("weather = %s  vis %.1f km  sun elev %.0f azim %.0f  "
        "took over: world=%s sun=%s fog=%s post=%s  (radius %.0f extent %.0f)"
        % (name, float(cfg.get("visibility_km") or 0.0),
           float(cfg.get("sun_elev") or 0.0), float(cfg.get("sun_azim") or 0.0),
           bool(own_sky), info.get("sun") is not None,
           info.get("fog") is not None, info.get("post") is not None,
           radius, extent))
    return info


def main():
    o = opts()
    preset = o.get("preset", "morning_town")
    if preset not in L.PRESETS:
        log("unknown preset %r; have %s" % (preset, sorted(L.PRESETS)))
        return
    outdir = o.get("out", os.path.join(ROOT, "..", "renders", "kingdom", "look"))
    outdir = os.path.abspath(outdir)
    os.makedirs(outdir, exist_ok=True)
    tag = o.get("tag", "")
    kind = o.get("engine", "eevee")
    samples = int(fnum(o, "samples", 48))
    res = [int(x) for x in str(o.get("res", "1280x720")).split("x")]
    wants = str(o.get("only") or o.get("shots") or "game,aerial").split(",")
    table = shot_table(o.get("shots-file"))
    if o.get("shots-file"):
        # a library file defines the set: drop the hand-written extras and the
        # spots.json-derived cameras so `--shots all` means exactly this file.
        lib = shot_library(o.get("shots-file"))
        dropped = sorted(set(table) - set(lib))
        table = {k: v for k, v in table.items() if k in lib}
        log("shot library only: %d cameras (%d non-library dropped)"
            % (len(table), len(dropped)))
    # `--shots all` and shell-style prefixes ("game_*", "landmark_*")
    expand = []
    for w in wants:
        w = w.strip()
        if not w:
            continue
        if w == "all":
            expand.extend(sorted(table))
        elif "*" in w or "?" in w:
            import fnmatch
            hit = sorted(k for k in table if fnmatch.fnmatchcase(k, w))
            if not hit:
                log("no shot matches %r" % w)
            expand.extend(hit)
        else:
            expand.append(w)
    wants = expand
    tilt = fnum(o, "elev")
    tazim = fnum(o, "azim")
    weather = o.get("weather")
    if weather in ("0", "no", "off", "none", True):
        weather = None
    weather_sky = str(o.get("weather-sky", "1")).lower() not in ("0", "no", "false")
    # hd_weather builds its own fog volume; keeping hd_light's haze as well
    # would stack two atmospheres on the same street.
    haze = "no-haze" not in o and not weather
    if weather:
        log("weather mode: hd_weather owns sun/fog/exposure/grade; --haze-mul "
            "is ignored (pass --weather-sky 0 to keep hd_sky's world)")
    haze_mul_o = fnum(o, "haze-mul", 1.0)
    exposure = fnum(o, "exposure")
    sky = o.get("sky")
    if sky in ("0", "no", "off"):
        sky = None
    clouds = fnum(o, "clouds")
    sky_strength = fnum(o, "sky-strength")
    ambient = fnum(o, "ambient")
    sun_e = fnum(o, "sun")
    only = o.get("list")
    if only:
        log("shots:", ", ".join(sorted(table)))
        return

    t0 = time.time()
    n = wipe_rig()
    log("wiped %d rig objects" % n)
    if "roofs" in o:
        import hd_roof
        hd_roof.rebuild(verbose=True)
    setup_engine(kind, samples, res, vols=haze)

    results = []
    for name in wants:
        name = name.strip()
        if name not in table:
            log("no shot %r" % name)
            continue
        spec = dict(table[name])
        t1 = time.time()
        wipe_rig()
        cam_ob = make_camera(spec)
        c = cam_ob.location
        build_rig(preset, tilt if tilt is not None else
                  L.PRESETS[preset]["sun_elev_wide" if spec["kind"] == "wide"
                                    else "sun_elev_street"],
                  tazim, haze=haze,
                  haze_mul=spec.get("haze_mul", 1.0) * haze_mul_o,
                  haze_extent=spec.get("haze_extent", 2800.0),
                  cam=(c.x, c.y), sky=sky, clouds=clouds, sky_strength=sky_strength,
                  ambient=ambient, exposure=exposure, sun=sun_e)
        if weather:
            # extent/radius per WEATHER: the fog box is +/-extent around the
            # centre, so a street shot only needs 1200 m of it while an aerial
            # needs the whole basin; 1200 is the documented floor.
            big = spec.get("shot_kind") in ("aerial", "overview")
            apply_weather(bpy.context.scene, weather, center=(c.x, c.y),
                          ground_z=0.1,
                          radius=1400.0 if big else 200.0,
                          extent=2800.0 if big else 1200.0,
                          own_sky=weather_sky)
            # hd_weather re-grades the scene; the explicit exposure knob still
            # wins so a sheet stays consistent across states.  build_rig() must
            # NOT be called again here -- it would rebuild the compositor group
            # and drop WX_Sat.
            if exposure is not None:
                bpy.context.scene.view_settings.exposure = exposure
            if sun_e is not None:
                for ob in bpy.data.objects:
                    if ob.type == "LIGHT" and ob.data.type == "SUN":
                        ob.data.energy = float(sun_e)
        if exposure is not None:
            bpy.context.scene.view_settings.exposure = exposure
        bpy.context.scene.render.filepath = os.path.join(
            outdir, "%s%s.png" % (("{}_".format(tag)) if tag else "", name))
        t2 = time.time()
        bpy.ops.render.render(write_still=True)
        t3 = time.time()
        results.append(dict(shot=name, path=bpy.context.scene.render.filepath,
                            rig_s=round(t2 - t1, 2), render_s=round(t3 - t2, 2)))
        log("%-9s render %.1fs  (rig %.1fs)" % (name, t3 - t2, t2 - t1))
    log("done in %.1fs" % (time.time() - t0))
    print("[rig-result] " + json.dumps(results))


if __name__ == "__main__":
    main()
