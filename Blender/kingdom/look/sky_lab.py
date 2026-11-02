"""sky_lab.py -- SKY's private measuring bench for hd_sky / hd_atmosphere.

Dual mode.  From a host shell::

    python look\\sky_lab.py strip            # 10 preset sky strips
    python look\\sky_lab.py gain             # gain -> display table
    python look\\sky_lab.py wide             # 3 wide shots w/ terrain + tower
    python look\\sky_lab.py ap               # aerial-perspective A/B
    python look\\sky_lab.py dbg              # sample pixels of one preset

Inside Blender it is driven as ``blender -b --python sky_lab.py -- <cmd>``;
the host mode just re-launches itself under ``look/_lock.py`` so every Blender
call goes through the project lock.

The lab never touches capital*.blend.  It builds its own two-scene bench:

  sky    - a camera, nothing else.  Used for strips / gain / pixel probes.
  wide   - a fake landscape: a ridge of low-poly peaks + a tower silhouette on
           a plateau, framed like the real ``castle`` camera, so "can you see
           clouds in a wide shot" can be answered without the capital.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KINGDOM = os.path.dirname(HERE)                 # ...\Blender\kingdom
ROOT = os.path.dirname(os.path.dirname(KINGDOM))  # ...\<workspace>
for p in (HERE, KINGDOM, os.path.dirname(KINGDOM)):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = os.path.join(ROOT, "renders", "kingdom", "look", "sky")
RES = (640, 360)

try:
    import bpy                                                    # noqa: F401
    IN_BLENDER = True
except ImportError:                                                # host mode
    IN_BLENDER = False


# --------------------------------------------------------------- host side ---
def _relaunch(cmd, *extra):
    import _lock
    args = ["-b", "--factory-startup", "--python", os.path.abspath(__file__),
            "--", cmd] + [str(e) for e in extra]
    os.makedirs(OUT, exist_ok=True)
    rc, log = _lock.run_blender(args, "skylab_%s" % cmd, timeout=5400,
                                light=True)
    return rc, log

def _isnum(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


# ------------------------------------------------------------ blender side ---
def _setup_render(sc, w=RES[0], h=RES[1], samples=24):
    r = sc.render
    r.engine = "BLENDER_EEVEE"
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.film_transparent = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    sc.eevee.taa_render_samples = samples
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:                                          # noqa: BLE001
        pass


def _cam(sc, loc, look_at=(0.0, 0.0, 0.0), lens=18.0):
    from mathutils import Vector
    ob = bpy.data.objects.get("labcam")
    if ob is None:
        cd = bpy.data.cameras.new("labcam")
        cd.clip_start = 0.1
        cd.clip_end = 40000.0
        ob = bpy.data.objects.new("labcam", cd)
        sc.collection.objects.link(ob)
    ob.data.lens = lens
    ob.location = loc
    d = Vector(look_at) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = ob
    return ob


def _render(sc, path):
    import time
    t0 = time.time()
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[time] %-22s %5.1f s  %dx%d" % (
        os.path.basename(path), time.time() - t0,
        sc.render.resolution_x, sc.render.resolution_y))
    return path


def _px(path, pts):
    """Sample a rendered PNG at UV points (0,0)=bottom-left; display values."""
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    buf = list(img.pixels)
    out = []
    for u, v in pts:
        x = min(w - 1, max(0, int(u * (w - 1))))
        y = min(h - 1, max(0, int(v * (h - 1))))
        i = (y * w + x) * 4
        out.append((buf[i], buf[i + 1], buf[i + 2]))
    bpy.data.images.remove(img)
    return out


def _band(path, v0=0.88, v1=1.0, cols=9):
    """Mean display value of the top band of a render (the sky's upper part)."""
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    buf = list(img.pixels)
    acc = [0.0, 0.0, 0.0]
    n = 0
    for y in range(int(h * v0), int(h * v1)):
        for xi in range(cols):
            x = int((xi + 0.5) * w / cols)
            i = (y * w + x) * 4
            acc[0] += buf[i]
            acc[1] += buf[i + 1]
            acc[2] += buf[i + 2]
            n += 1
    bpy.data.images.remove(img)
    return [c / n for c in acc]


# ------------------------------------------------------------------- bench ---
def sky_bench(gain=None, exposure=None, preset="morning_town", **extra):
    """A camera-only scene, sun lamp in place, sky world applied."""
    import hd_sky
    sc = bpy.context.scene
    _setup_render(sc)
    over = dict(extra)
    if gain is not None:
        over["gain"] = gain
    _cam(sc, (0.0, 0.0, 180.0), (0.0, 10.0, 180.0), lens=18.0)
    cfg = hd_sky.world(sc, preset, **over)
    hd_sky.sun(sc, cfg=cfg)
    sc.view_settings.exposure = float(cfg["exposure"] if exposure is None
                                      else exposure)
    return sc, cfg


def wide_bench(preset="castle_like", ap=True, glare=False, **over):
    """Ridge + tower silhouette on a plateau, framed like the castle camera.

    Elevation ~2.5 deg (horizon a hair below centre, exactly the problem case),
    lens 22 mm, so the sky only owns the top third of the frame.
    """
    import bmesh
    import hd_sky
    from mathutils import Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    _setup_render(sc, 960, 540)

    # ---- ground: a big plane at z=0, displaced into rolling hills
    me = bpy.data.meshes.new("ground")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=72, y_segments=72, size=24000.0)
    bm.to_mesh(me)
    bm.free()
    g = bpy.data.objects.new("ground", me)
    sc.collection.objects.link(g)
    mat = bpy.data.materials.new("groundmat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.20, 0.22, 0.14, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.92
    g.data.materials.append(mat)
    tex = bpy.data.textures.new("hill", "CLOUDS")
    try:
        tex.noise_scale = 900.0
    except Exception:                                          # noqa: BLE001
        pass
    d = g.modifiers.new("disp", "DISPLACE")
    d.texture = tex
    d.strength = 110.0
    d.mid_level = 0.5

    # ---- far ridge: two rows of peaks, deliberately tall enough to eat into
    #      the horizon the way hd_landscape's mountains do
    for row, (y0, hscale, seg) in enumerate(((5200.0, 1.0, 26), (7600.0, 1.35, 20))):
        pme = bpy.data.meshes.new("ridge%d" % row)
        verts, faces = [], []
        width = 16000.0
        for i in range(seg + 1):
            x = -width / 2 + width * i / seg
            hh = (0.45 + 0.55 * abs(__import__("math").sin(i * 2.3 + row * 1.7))) * 720 * hscale
            jitter = 900.0 * ((i * 37) % 11) / 11.0
            verts.append((x, y0 + jitter, -80.0))    # base, buried under the hills
            verts.append((x, y0 + jitter, hh))       # ridge line
            if i:
                b = 2 * i
                faces.append((b - 2, b - 1, b + 1, b))
        pme.from_pydata(verts, [], faces)
        pme.update()
        pm = bpy.data.objects.new("ridge%d" % row, pme)
        sc.collection.objects.link(pm)
        m2 = bpy.data.materials.new("ridgem%d" % row)
        m2.use_nodes = True
        b2 = m2.node_tree.nodes["Principled BSDF"]
        b2.inputs["Base Color"].default_value = (0.13, 0.16, 0.12, 1.0)
        b2.inputs["Roughness"].default_value = 0.95
        pm.data.materials.append(m2)
        pm.visible_shadow = True

    # ---- tower on a plateau, ~430 m to camera-left
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-430.0, 1750.0, 0.0))
    tw = bpy.context.object
    tw.scale = (58.0, 58.0, 300.0)
    tw.location.z = 150.0
    tm = bpy.data.materials.new("towermat")
    tm.use_nodes = True
    tb = tm.node_tree.nodes["Principled BSDF"]
    tb.inputs["Base Color"].default_value = (0.30, 0.28, 0.26, 1.0)
    tb.inputs["Roughness"].default_value = 0.8
    tw.data.materials.append(tm)
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=46.0, radius2=0.0,
                                    depth=190.0, location=(-430.0, 1750.0, 395.0))
    sp = bpy.context.object
    sp.data.materials.append(tm)

    # The camera has to exist *before* the world is built: `hd_sky.world`
    # parks the emissive dome on `scene.camera`, and with no camera the dome
    # either lands at the origin or is skipped, which is exactly how a bench
    # ends up with a black sky and a perfectly lit foreground.
    eye = (0.0, 0.0, 260.0)
    _cam(sc, eye, (0.0, 3000.0, 260.0 + 3000.0 * 0.0436), lens=22.0)
    cfg = hd_sky.world(sc, preset, **over)
    hd_sky.sun(sc, cfg=cfg)
    sc.view_settings.exposure = float(cfg["exposure"])
    if ap is not None:
        hd_sky.post(sc, cfg=cfg, ap=bool(ap), glare=glare)
    return sc, cfg
    # camera 260 m up, ~2.5 deg above the ground plane, so the horizon sits
    # just under the middle of the frame and the sky owns the top third --
    # the `castle` framing.
    return sc, cfg


# ---------------------------------------------------------------- commands ---
def cmd_dbg(preset="morning_town", gain=None, **over):
    sc, cfg = sky_bench(gain=gain, **over)
    _cam(sc, (0.0, 0.0, 180.0), (0.0, 10.0, 180.0), lens=18.0)
    p = _render(sc, os.path.join(OUT, "_dbg_raw.png"))
    pts = [(0.5, 0.99), (0.5, 0.90), (0.5, 0.80), (0.5, 0.72), (0.5, 0.66),
           (0.5, 0.60), (0.5, 0.55), (0.2, 0.95), (0.8, 0.95)]
    for (u, v), c in zip(pts, _px(p, pts)):
        print("[dbg] v=%.2f  %.3f %.3f %.3f" % (v, c[0], c[1], c[2]))
    print("[dbg] band(0.88-1.0) = %.3f %.3f %.3f" % tuple(_band(p)))
    return 0


def cmd_gain(vals="1,2,3.2,6,10,16"):
    print("[gain] preset=morning_town  band = mean display R,G,B of the top 12%")
    if isinstance(vals, str):
        vals = [float(v) for v in vals.replace(" ", "").split(",") if v]
    for gvalue in vals:
        sc, cfg = sky_bench(gain=gvalue)
        _cam(sc, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), lens=18.0)
        p = _render(sc, os.path.join(OUT, "_gain_%g.png" % gvalue))
        b = _band(p)
        print("[gain] %-6g -> %.3f  (%.3f %.3f %.3f)"
              % (gvalue, b[0], b[0], b[1], b[2]))
    return 0


def cmd_strip(pitch=5.0, lens=18.0, only=None):
    """Ten 640x360 sky strips, one per preset, on a clean empty scene.

    Pitch is +5 deg so the strip holds both the horizon haze band (bottom
    third) and the deck (top) -- a sky that only works at the zenith is not a
    sky.  The camera looks along the sun's azimuth, which is the hardest and
    most informative slice.
    """
    import math

    import hd_sky
    from mathutils import Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    _setup_render(sc, RES[0], RES[1], 16)
    names = list(hd_sky.PRESET_NAMES)
    if only:
        names = [only] if isinstance(only, str) else list(only)
    for name in names:
        cfg = hd_sky.world(sc, name)
        hd_sky.sun(sc, cfg=cfg)
        sc.view_settings.exposure = float(cfg["exposure"])
        az = math.radians(float(cfg["sun_azim"]))
        el = math.radians(pitch)
        d = Vector((math.sin(az) * math.cos(el),
                    math.cos(az) * math.cos(el), math.sin(el)))
        _cam(sc, (0.0, 0.0, 0.0), (d.x * 10, d.y * 10, d.z * 10), lens=lens)
        out = os.path.join(OUT, "%s.png" % name)
        _render(sc, out)
        b = _band(out, 0.86, 1.00)
        print("[strip] %-15s band=%.3f  -> %s" % (name, b[0], out))
    return 0


def cmd_wide():
    for name, over in (("wide_castle_noon", {}),
                       ("wide_castle_low20", {"sun_elev": 20.0, "sun_azim": 250.0}),
                       ("wide_castle_back", {"sun_elev": 14.0, "sun_azim": 8.0})):
        sc, cfg = wide_bench("morning_town", **over)
        out = os.path.join(OUT, "%s.png" % name)
        _render(sc, out)
        b = _band(out, 0.86, 1.0)
        print("[wide] %-20s top-band=%.3f -> %s" % (name, b[0], out))
    return 0


def _mat_report(tag=""):
    """Dump who feeds Material Output.Surface in every material."""
    for m in bpy.data.materials:
        if not m.use_nodes or not m.node_tree:
            continue
        o = None
        for n in m.node_tree.nodes:
            if n.bl_idname == "ShaderNodeOutputMaterial" and n.is_active_output:
                o = n
        src = (o.inputs["Surface"].links[0].from_node.bl_idname
               if (o and o.inputs["Surface"].links) else "NONE")
        ap = m.node_tree.nodes.get("AP_mix")
        fac = ""
        if ap is not None and ap.inputs[0].links:
            fac = ap.inputs[0].links[0].from_node.name
        print("[ap]%s %-12s surface<-%s ap=%s fac<-%s"
              % (tag, m.name, src, ap is not None, fac))


def cmd_ap():
    import hd_sky
    shots = {}
    for tag, on in (("off", False), ("on", True)):
        sc, cfg = wide_bench("morning_town", ap=None)
        if on:
            r = hd_sky.post(sc, cfg=cfg, ap=True, glare=False)
            print("[ap] on %s" % (r.get("ap"),))
            _mat_report()
        out = os.path.join(OUT, "_ap_%s.png" % tag)
        _render(sc, out)
        shots[tag] = out
    a = _px(shots["off"], [(0.5, 0.95), (0.5, 0.10), (0.30, 0.34)])
    b = _px(shots["on"], [(0.5, 0.95), (0.5, 0.10), (0.30, 0.34)])
    for i, tag in enumerate(("sky", "near-ground", "far-ridge")):
        d = [b[i][k] - a[i][k] for k in range(3)]
        print("[ap] %-12s off=%.3f on=%.3f  delta=%.3f" % (tag, a[i][0], b[i][0], d[0]))
    return 0


def cmd_stats(nodes="body", preset="morning_town"):
    """Histogram of named shader sockets over the sky hemisphere.

    Rendering a socket straight into an emission and reading it back with
    `Standard`/exposure 0 gives the *display-clipped* value per pixel; NaN comes
    back as 1.000, which is why a NaN in the chain shows up here as a uniform
    white frame.  Accepts a comma-separated list so one lock buys several.
    """
    names = [n.strip() for n in nodes.split(",") if n.strip()]
    for node in names:
        sc, cfg = sky_bench(preset=preset)
        _cam(sc, (0.0, 0.0, 180.0), (0.0, 10.0, 180.0), lens=18.0)
        nt = cfg["_mat"].node_tree
        src = nt.nodes[node].outputs[0]
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(src, em.inputs["Color"])
        for n in nt.nodes:
            if n.bl_idname == "ShaderNodeOutputMaterial":
                for lk in list(n.inputs[0].links):
                    nt.links.remove(lk)
                nt.links.new(em.outputs[0], n.inputs[0])
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.exposure = 0.0
        p = _render(sc, os.path.join(OUT, "_stats_%s.png" % node))
        img = bpy.data.images.load(p, check_existing=False)
        px = list(img.pixels)
        bpy.data.images.remove(img)
        vals = sorted(px[0::4])
        n = len(vals)
        pct = lambda q: vals[min(n - 1, int(q * n))]  # noqa: E731
        print("[stats] %-12s n=%d  p05=%.3f p25=%.3f p50=%.3f p75=%.3f "
              "p95=%.3f  mean=%.3f" % (node, n, pct(0.05), pct(0.25), pct(0.50),
                                       pct(0.75), pct(0.95), sum(vals) / n))
        print("[stats] %-12s min=%.3f max=%.3f  top=%.3f low=%.3f"
              % (node, vals[0], vals[-1], _px(p, [(0.5, 0.95)])[0][0],
                 _px(p, [(0.5, 0.10)])[0][0]))
    return 0


def cmd_links(node="thr"):
    """Print what feeds a node -- resolves 'why is this number not what I
    expect' without another render."""
    sc, cfg = sky_bench()
    nt = cfg["_mat"].node_tree
    n = nt.nodes.get(node)
    if n is None:
        print("[links] no node %r; have %s" % (node, sorted(x.name for x in nt.nodes)))
        return 1
    print("[links] %s  type=%s  op=%s" % (node, n.bl_idname,
                                          getattr(n, "operation", "")))
    for s in n.inputs:
        if s.is_linked:
            lk = s.links[0]
            print("   in  %-12s <- %s.%s" % (s.name, lk.from_node.name, lk.from_socket.name))
        else:
            print("   in  %-12s =  %s" % (s.name,
                                         getattr(s, "default_value", "<socket>")))
    for s in n.outputs:
        print("   out %-12s -> %s" % (s.name, [l.to_node.name for l in s.links]))
    # and the upstream chain for the first linked input, one level deeper
    for s in n.inputs:
        if s.is_linked:
            u = s.links[0].from_node
            print("[links]   ^ %s op=%s" % (u.name, getattr(u, "operation", "")))
            for si in u.inputs:
                if si.is_linked:
                    print("        %-10s <- %s.%s" % (si.name, si.links[0].from_node.name,
                                                      si.links[0].from_socket.name))
                else:
                    print("        %-10s =  %s" % (si.name,
                                                   getattr(si, "default_value", "?")))
    return 0


def cmd_all():
    """Everything one lock acquisition can buy: wide shots, strips, gain."""
    import time
    t0 = time.time()
    rc = 0
    rc |= cmd_wide()
    rc |= cmd_ap()
    rc |= cmd_strip()
    rc |= cmd_gain()
    print("[time] all of the above: %.1f s" % (time.time() - t0))
    return rc


def cmd_nodes(pat="Compositor"):
    """Which node types this build actually has -- 5.2 renamed a lot."""
    names = [n for n in dir(bpy.types) if pat.lower() in n.lower()]
    print("[nodes] %d matching %r" % (len(names), pat))
    for n in names:
        print("[nodes]   %s" % n)
    return 0


def _why(tag, sc, cfg):
    """Print what the sky is actually made of in this scene."""
    dome = bpy.data.objects.get("SKY_dome")
    w = sc.world
    print("[why] %s  world=%s  cam=%s  eng=%s  exposure=%.2f vt=%s" % (
        tag, getattr(w, "name", None),
        getattr(getattr(sc, "camera", None), "name", None),
        sc.render.engine, sc.view_settings.exposure,
        sc.view_settings.view_transform))
    print("[why] %s  dome=%s loc=%s scale=%s  rag=%s" % (
        tag, getattr(dome, "name", None),
        tuple(round(v, 1) for v in dome.location) if dome else None,
        tuple(round(v, 1) for v in dome.scale) if dome else None,
        sc.render.engine == "BLENDER_EEVEE" and getattr(sc.eevee, "ray_tracing_method", None)))
    if dome and dome.data.materials:
        m = dome.data.materials[0]
        nt = m.node_tree
        out = [n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
        if out:
            for lk in nt.links:
                if lk.to_node == out[0]:
                    print("[why] %s  dome surface <- %s.%s" % (
                        tag, lk.from_node.bl_idname, lk.from_socket.name))
        print("[why] %s  dome nodes=%d  blend=%s" % (tag, len(nt.nodes), m.blend_method))
    if w and w.node_tree:
        bg = [n for n in w.node_tree.nodes if n.bl_idname == "ShaderNodeBackground"]
        for b in bg:
            print("[why] %s  world bg strength=%.3f col=%s" % (
                tag, b.inputs["Strength"].default_value,
                tuple(round(v, 3) for v in b.inputs["Color"].default_value)))


def cmd_diag():
    """Same bench, three ways, to isolate a black sky."""
    for tag, ap in (("nopost", None), ("post_noap", False), ("post_ap", True)):
        sc, cfg = wide_bench("morning_town", ap=ap)
        if tag == "nopost":
            _why("wide", sc, cfg)
            d = bpy.data.objects.get("SKY_dome")
            print("[why] wide film_tp=%s hide_render=%s vis_cam=%s in_scene=%s "
                  "nobj=%d" % (sc.render.film_transparent,
                               getattr(d, "hide_render", None),
                               getattr(d, "visible_camera", None),
                               d.name in sc.objects, len(sc.objects)))
        out = os.path.join(OUT, "_diag_%s.png" % tag)
        _render(sc, out)
        s = _px(out, [(0.5, 0.95)])[0][0]
        g = _px(out, [(0.5, 0.10)])[0][0]
        print("[diag] %-10s sky=%.3f ground=%.3f -> %s" % (tag, s, g, out))
    sc, cfg = sky_bench()
    out = os.path.join(OUT, "_diag_skybench.png")
    _render(sc, out)
    print("[diag] skybench  sky=%.3f" % _px(out, [(0.5, 0.95)])[0][0])
    return 0


def _kw(args):
    """Parse trailing `key=value` overrides, so one bench can be poked blind."""
    over = {}
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            try:
                over[k] = float(v)
            except ValueError:
                over[k] = v
    return over


CMDS = {}


def cmd_mist():
    """Render the mist buffer itself: is EEVEE 5.2 filling it at all?"""
    import hd_sky
    sc, cfg = wide_bench("morning_town", ap=False)
    hd_sky.post(sc, cfg=cfg, ap=False, glare=False)
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 320, 180, 100
    tree = sc.compositing_node_group
    rl = [n for n in tree.nodes if n.bl_idname == "CompositorNodeRLayers"][0]
    print("[mist] rl outputs: %s" % [s.name for s in rl.outputs])
    for n in list(tree.nodes):
        if n.name.startswith("sky_") or n.name.startswith("AP_"):
            tree.nodes.remove(n)
    for k in ("Mist",):
        print("[mist] has %s: %s" % (k, k in [s.name for s in rl.outputs]))
    mul = tree.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    ins = [s for s in mul.inputs if s.type == "RGBA"]
    tree.links.new(rl.outputs["Image"], ins[0])
    for k in ("Mist", "Depth", "Z"):
        if k in [s.name for s in rl.outputs]:
            tree.links.new(rl.outputs[k], ins[1])
    for n in list(tree.nodes):
        if n.bl_idname == "NodeGroupOutput":
            for l in list(n.inputs[0].links):
                tree.links.remove(l)
            tree.links.new(mul.outputs[3] if len(mul.outputs) > 3 else mul.outputs[0],
                           n.inputs[0])
    out = os.path.join(OUT, "_mist.png")
    _render(sc, out)
    print("[mist] %s  %s" % (out, _band(out, 0.0, 1.0)))
    return 0


# =========================================================================== #
#  shadow bench -- "how bright is a surface that gets no sun?"
# =========================================================================== #
# The complaint this bench exists for: half of a street frame comes back at
# 8-20 / 255, i.e. black, and a real medieval street in shade sits at 60-90.
# Everything here is measured in *display* values (PNG byte / 255), because that
# is what the art direction and the screenshots are denominated in.
#
# The lighting chain is not a lab imitation: `street_shoot()` calls the real
# `render.setup_engine` / `render.make_camera` / `render.build_rig`, so
# hd_light (sun, bounce card, AO contact, haze, AgX grade) and hd_sky (world
# fill + dome) are wired exactly as in a production shot.  Only the geometry is
# synthetic: a 300 m district of 12 m streets with the capital's own medkit
# cobble / plaster / tile albedo.
FINAL = os.path.dirname(OUT)                      # renders\kingdom\look
SHADOW_TARGET = (0.235, 0.353)                    # display 60..90 / 255
SHADOW_AIM = 0.294                                # middle of the band
_CITY = [False]
_PS0 = {}


def _args(*a, **k):
    """Merge positional `key=value` words (what main() actually passes) with
    real kwargs, so every lab command can be poked either way."""
    o = dict(k)
    rest = []
    for s in a:
        if not isinstance(s, str):
            rest.append(s)
        elif "=" in s:
            key, v = s.split("=", 1)
            try:
                o[key] = float(v)
            except ValueError:
                o[key] = v
        else:
            rest.append(s)
    if rest:
        o["_"] = rest
    return o


def _lum(r, g, b):
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _read(path):
    """(w, h, flat RGBA) of a rendered PNG, in display values."""
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    buf = [0.0] * (w * h * 4)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    return w, h, buf


def _num(vals):
    if not vals:
        return None
    v = sorted(vals)
    n = len(v)

    def q(f):
        return v[min(n - 1, max(0, int(round(f * (n - 1)))))]

    m = sum(v) / n
    sd = (sum((x - m) ** 2 for x in v) / n) ** 0.5
    return dict(n=n, p05=q(0.05), p25=q(0.25), p50=q(0.50), p95=q(0.95),
                mean=m, sd=sd, min=v[0], max=v[-1])


def _fmt(s):
    if not s:
        return "n=0"
    return ("n=%-6d p05=%.3f p50=%.3f p95=%.3f sd=%.3f  (p50=%3.0f/255)"
            % (s["n"], s["p05"], s["p50"], s["p95"], s["sd"], 255.0 * s["p50"]))


def _preset(preset, **over):
    """Copy-on-write view of hd_light.PRESETS.

    `build_rig` reads `L.PRESETS[preset]`, so a bench knob is a dict entry --
    but the lab must never leave a knob set for the next shot in the same
    session, hence the pristine copy in `_PS0`.
    """
    import hd_light as L
    if preset not in _PS0:
        _PS0[preset] = dict(L.PRESETS[preset])
    p = dict(_PS0[preset])
    p.update(over)
    L.PRESETS[preset] = p
    return p


# ---------------------------------------------------------------- geometry ---
def _add_box(v, f, mi, cx, cy, sx, sy, z0, z1, idx=0):
    x0, x1 = cx - 0.5 * sx, cx + 0.5 * sx
    y0, y1 = cy - 0.5 * sy, cy + 0.5 * sy
    b = len(v)
    v.extend([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
              (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])
    f.extend([(b, b + 1, b + 2, b + 3), (b + 4, b + 7, b + 6, b + 5),
              (b, b + 4, b + 5, b + 1), (b + 1, b + 5, b + 6, b + 2),
              (b + 2, b + 6, b + 7, b + 3), (b + 3, b + 7, b + 4, b)])
    mi.extend([idx] * 6)


def _add_gable(v, f, mi, cx, cy, hx, hy, z0, rh, idx=1):
    """A gable roof: two slopes and two gable triangles, ridge along X."""
    x0, x1 = cx - hx, cx + hx
    y0, y1 = cy - hy, cy + hy
    zt = z0 + rh
    b = len(v)
    v.extend([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
              (x0, cy, zt), (x1, cy, zt)])
    f.extend([(b, b + 1, b + 5, b + 4), (b + 2, b + 3, b + 4, b + 5),
              (b, b + 4, b + 3), (b + 1, b + 2, b + 5)])
    mi.extend([idx] * 4)


def _district(sc, rings=2, pitch=60.0, street=12.0, wall=11.0, roof=4.5, seed=7):
    """(2*rings+1)^2 blocks, 12 m streets: 300 m of town, <1 s to build."""
    import bmesh
    import random

    import medkit as MK

    rnd = random.Random(seed)
    v, f, mi = [], [], []
    half = 0.5 * (pitch - street)
    for i in range(-rings, rings + 1):
        for j in range(-rings, rings + 1):
            cx, cy = i * pitch, j * pitch
            h = wall + rnd.uniform(-2.0, 3.0)
            _add_box(v, f, mi, cx, cy, 2.0 * half, 2.0 * half, 0.0, h, 0)
            _add_gable(v, f, mi, cx, cy, half, half, h,
                       roof + rnd.uniform(-1.2, 1.2), 1)
    me = bpy.data.meshes.new("district")
    me.from_pydata(v, [], f)
    me.update()
    ob = bpy.data.objects.new("district", me)
    sc.collection.objects.link(ob)
    ob.data.materials.append(MK.mat_plaster(name="lab_plaster"))
    ob.data.materials.append(MK.mat_tile(name="lab_tile"))
    for poly, idx in zip(me.polygons, mi):
        poly.material_index = idx
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()

    gm = bpy.data.meshes.new("street")
    gm.from_pydata([(-900.0, -900.0, 0.0), (900.0, -900.0, 0.0),
                    (900.0, 900.0, 0.0), (-900.0, 900.0, 0.0)], [],
                   [(0, 1, 2, 3)])
    gm.update()
    g = bpy.data.objects.new("street", gm)
    sc.collection.objects.link(g)
    g.data.materials.append(MK.mat_cobble(name="lab_cobble"))
    _CITY[0] = True
    return ob


# ------------------------------------------------------------------ camera ---
def _game_spec(pivot=(30.0, 0.0, 1.6), yaw=90.0, pitch=52.0, dist=34.0,
               vfov=30.0):
    """render.game_cam()'s framing: the player's 52 deg / 34 m / 30 deg vfov."""
    import math
    px, py, pz = pivot
    ry, rp = math.radians(yaw), math.radians(pitch)
    eye = (px - math.cos(ry) * dist * math.cos(rp),
           py - math.sin(ry) * dist * math.cos(rp),
           pz + dist * math.sin(rp))
    look = (px + math.cos(ry) * 1.5, py + math.sin(ry) * 1.5, pz)
    return dict(loc=eye, look=look, vfov=vfov)


def _hero_spec(eye=(30.0, -34.0, 1.75), look=(30.0, 120.0, 2.6), lens=24.0):
    """Standing in the street: the frame that holds *both* problems at once --
    shaded paving at the bottom, 0-20 deg of sky over the roofline at the top."""
    return dict(loc=eye, look=look, lens=lens)


# ------------------------------------------------------------------- bench ---
#: hd_light only ships the presets the game actually shoots; the other four sky
#: moods borrow the nearest rig so they can still be measured in a lit street.
LIGHT_OF = {
    "dawn_cold": "golden_street",
    "storm_dark": "overcast_soft",
    "fog_pale": "overcast_soft",
    "sunshower_warm": "morning_town",
}


def street_scene(w=640, h=360, samples=8, rebuild=True):
    import render as R
    if rebuild or not _CITY[0]:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        _district(bpy.context.scene)
    R.setup_engine("eevee", samples, (w, h), vols=True)
    return bpy.context.scene


def street_shoot(preset="morning_town", spec="game", w=640, h=360, samples=8,
                 ambient=None, contrast=None, ao=None, bounce=True,
                 haze_mul=0.45, sun=None, fix=True, elev=None, azim=None,
                 cloud=None, hero=None, light=None):
    """One production-shaped shot of the street.  Returns (scene, path-free)."""
    import hd_light as L
    import hd_sky as SKY
    import render as R

    rig = light or LIGHT_OF.get(preset, preset)
    sc = bpy.context.scene
    over = {}
    if contrast is not None:
        over["contrast"] = float(contrast)
    if ao is not None:
        over["ao_strength"] = float(ao)
    _preset(rig, **over)
    R.setup_engine("eevee", samples, (w, h), vols=True)
    R.wipe_rig()
    sp = _hero_spec() if spec == "hero" else _game_spec()
    if isinstance(hero, dict):
        sp = dict(hero)
    cam = R.make_camera(sp)
    b = L.bounce
    if not bounce:
        L.bounce = lambda *a, **k: None
    sover = {}
    if cloud is not None:
        sover["clouds"] = float(cloud)
    try:
        R.build_rig(rig, elev, azim, haze=True, haze_mul=haze_mul,
                    haze_extent=1400.0, cam=(cam.location.x, cam.location.y),
                    sky=preset, ambient=ambient, sun=sun)
    finally:
        L.bounce = b
    if sover:
        # rebuild the world only -- the rig (lights/haze/grade) is already up
        SKY.world(sc, preset, **sover)
    info = {}
    if fix:
        info = SKY.grade_fix(sc, verbose=True)
    return sc, info, sp


def _shoot(sc, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def _mask(on, off, stride=2, thr=1.12, v1=1.0):
    """Pixel indices whose luminance does not move when the sun is switched
    off, i.e. the pixels that receive *no direct sun* -- shaded paving and
    every wall facing away.  Geometric, so the mask can be reused while the
    fill is swept.

    The dome is independent of the sun lamp, so the *sky* also has a ratio of
    1 and would join the shade population.  With the game camera that never
    happens (it sees no sky); in a hero frame the sky is a quarter of the
    picture and would silently double the reading, hence `v1` -- keep only the
    rows below the horizon.
    """
    w, h, a = _read(on)
    _, _, b = _read(off)
    idx = []
    for y in range(0, min(h, int(h * v1)), stride):
        row = y * w * 4
        for x in range(0, w, stride):
            j = row + x * 4
            la = _lum(a[j], a[j + 1], a[j + 2])
            lb = _lum(b[j], b[j + 1], b[j + 2])
            if lb < 0.012:
                continue
            if la <= thr * lb:
                idx.append(j)
    return w, h, idx


def _masked(path, idx):
    _, _, a = _read(path)
    return [_lum(a[j], a[j + 1], a[j + 2]) for j in idx]


def _shadow_sweep(preset, on, off, amb, **kw):
    """Sweep the world fill and report the shadow band each time."""
    w, h, idx = _mask(on, off)
    if not idx:
        return []
    rows = []
    for a in amb:
        sc, info, _sp = street_shoot(preset, ambient=a, **kw)
        p = _shoot(sc, os.path.join(OUT, "_amb_%s_%03d.png" % (preset, int(a * 100))))
        s = _num(_masked(p, idx))
        rows.append((a, s))
        print("[amb] %-14s ambient=%.2f  %s" % (preset, a, _fmt(s)), flush=True)
    return rows


def _pair(tag, on, off, mask_thr=1.12):
    """Shadow / sunlit split of one A/B pair and the line the table prints."""
    w, h, a = _read(on)
    _, _, b = _read(off)
    sh, lt, tot = [], [], 0
    for y in range(0, h, 2):
        row = y * w * 4
        for x in range(0, w, 2):
            j = row + x * 4
            la = _lum(a[j], a[j + 1], a[j + 2])
            lb = _lum(b[j], b[j + 1], b[j + 2])
            tot += 1
            if lb < 0.012:
                continue
            r = la / max(lb, 1e-5)
            if r <= mask_thr:
                sh.append(la)
            elif r >= 1.55:
                lt.append(la)
    s, l = _num(sh), _num(lt)
    ok = "OK" if (s and SHADOW_TARGET[0] <= s["p50"] <= SHADOW_TARGET[1]) else "FAIL"
    print("[shad] %-13s shade %2.0f%%  %s   | sun %2.0f%%  p50=%.3f  -> %s"
          % (tag, 100.0 * len(sh) / max(tot, 1), _fmt(s),
             100.0 * len(lt) / max(tot, 1), (l or {}).get("p50", 0.0), ok),
          flush=True)
    return s, l


def cmd_bc(*a, **k):
    """The Bright/Contrast probe: prove the node clips at 0.4545, not 0.0.

    A row of emissive bands of known *linear* value, rendered through
    Standard + exposure 0, so the PNG byte is the linear value that reached the
    view transform.  Then the same row through a Bright/Contrast node at three
    Contrast settings: 0 (bypass), 0.10 (what the preset table means by
    `contrast: 1.10`) and 10.0 (what hd_light writes today).
    """
    import hd_sky as SKY

    vals = [0.02, 0.05, 0.10, 0.20, 0.30, 0.45, 0.60, 0.90]
    n = len(vals)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    _setup_render(sc, 640, 60, 4)
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    for i, val in enumerate(vals):
        cx = i - (n - 1) * 0.5
        me = bpy.data.meshes.new("band%d" % i)
        me.from_pydata([(cx - 0.5, 0.0, -1.0), (cx + 0.5, 0.0, -1.0),
                        (cx + 0.5, 0.0, 1.0), (cx - 0.5, 0.0, 1.0)], [],
                       [(0, 3, 2, 1)])
        me.update()
        ob = bpy.data.objects.new("band%d" % i, me)
        sc.collection.objects.link(ob)
        mat = bpy.data.materials.new("emit%d" % i)
        mat.use_nodes = True
        nt = mat.node_tree
        for nd in list(nt.nodes):
            nt.nodes.remove(nd)
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (val, val, val, 1.0)
        em.inputs["Strength"].default_value = 1.0
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(em.outputs[0], out.inputs[0])
        ob.data.materials.append(mat)
    cd = bpy.data.cameras.new("bcam")
    cd.type = "ORTHO"
    cd.ortho_scale = float(n)
    cam = bpy.data.objects.new("bcam", cd)
    sc.collection.objects.link(cam)
    cam.location = (0.0, -6.0, 0.0)
    cam.rotation_euler = (1.5707963, 0.0, 0.0)
    sc.camera = cam

    nt, mode = SKY._comp_tree()
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    bc = nt.nodes.new("CompositorNodeBrightContrast")
    nt.links.new(rl.outputs["Image"], bc.inputs["Image"])
    _o, outsock = SKY._comp_out(nt, mode)
    nt.links.new(bc.outputs["Image"], outsock)
    sc.render.use_compositing = True

    print("[bc] linear band values -> display value through Bright/Contrast",
          flush=True)
    pts = [((i + 0.5) / n, 0.5) for i in range(n)]
    res = {}
    for c in (0.0, 0.10, 10.0):
        bc.inputs["Contrast"].default_value = c
        p = _render(sc, os.path.join(OUT, "_bc_%g.png" % c))
        res[c] = [px[0] for px in _px(p, pts)]
    print("[bc]  linear |  c=0.00 |  c=0.10 |  c=10.00 | 11*x-5", flush=True)
    for i, val in enumerate(vals):
        print("[bc]  %6.3f | %7.3f | %7.3f | %8.3f | %6.3f"
              % (val, res[0.0][i], res[0.10][i], res[10.0][i],
                 11.0 * val - 5.0), flush=True)
    return 0


def _hook_off():
    """Unplug hd_sky's render_pre grade fix, so a variant can be shot exactly
    as shipped (with whatever number hd_light wrote into the node)."""
    h = bpy.app.handlers.render_pre
    gone = [f for f in list(h) if getattr(f, "__name__", "") == "_grade_pre"]
    for f in gone:
        h.remove(f)
    return gone


def _hook_on(gone):
    h = bpy.app.handlers.render_pre
    for f in gone:
        if f not in h:
            h.append(f)


def cmd_shadow(*a, **k):
    """The diagnosis: which knob turns a shaded street from black to 60-90?"""
    o = _args(*a, **k)
    preset = str(o.get("preset", "morning_town"))
    w, h = [int(x) for x in str(o.get("res", "480x270")).split("x")]
    samples = int(o.get("samples", 8))
    print("[shad] preset=%s  %dx%d  target p50 %.3f..%.3f (60..90/255)"
          % (preset, w, h, SHADOW_TARGET[0], SHADOW_TARGET[1]), flush=True)
    variants = [
        ("a_shipped", dict(fix=False)),
        ("b_gradefix", dict(fix=True)),
        ("c_nobounce", dict(fix=True, bounce=False)),
        ("d_noao", dict(fix=True, ao=0.0)),
        ("e_amb35", dict(fix=True, ambient=0.35)),
        ("f_amb55", dict(fix=True, ambient=0.55)),
        ("g_amb80", dict(fix=True, ambient=0.80)),
        ("z_raw", dict(fix=False, nohook=True)),
    ]
    street_scene(w, h, samples)
    keep = {}
    for tag, kw in variants:
        nohook = kw.pop("nohook", False)
        try:
            sc, info, _sp = street_shoot(preset, w=w, h=h, samples=samples, **kw)
            gone = _hook_off() if nohook else []
            on = _shoot(sc, os.path.join(OUT, "_sh_%s_on.png" % tag))
            sc, _i, _s = street_shoot(preset, w=w, h=h, samples=samples,
                                      sun=0.0, **kw)
            if nohook:
                _hook_off()
            off = _shoot(sc, os.path.join(OUT, "_sh_%s_off.png" % tag))
            _hook_on(gone)
            if tag == "a_shipped":
                print("[bc] socket as built: %s" % (info,), flush=True)
            keep[tag] = (on, off)
            _pair(tag, on, off)
        except Exception as exc:                             # noqa: BLE001
            import traceback
            traceback.print_exc()
            print("[shad] %s FAILED %s" % (tag, exc), flush=True)
    return 0


def _solve(fn, g0, tgt, lo=0.25, hi=900.0, tries=6, tol=0.012, tag=""):
    """Secant on log(knob) -- monotone and smooth for both gain and fill."""
    import math

    pts = []
    g = max(lo, min(hi, g0))
    best = (g, None)
    for i in range(tries):
        v = fn(g)
        pts.append((math.log(g), v))
        best = (g, v)
        if i == 0:
            print("[solve] %-14s start %.2f -> %.3f" % (tag, g, v), flush=True)
        if abs(v - tgt) <= tol:
            break
        if len(pts) >= 2:
            (x0, y0), (x1, y1) = pts[-2], pts[-1]
            if abs(y1 - y0) > 1e-6:
                x = x1 + (tgt - y1) * (x1 - x0) / (y1 - y0)
                if not (x1 - 5.0 <= x <= x1 + 5.0):
                    x = x1 + 0.35
            else:
                x = x1 + 0.35
        else:
            x = pts[0][0] + math.log(max(tgt, 1e-4) / max(v, 1e-4)) / 0.45
        g = max(lo, min(hi, math.exp(x)))
    print("[solve] %-14s knob %.2f -> band %.3f (%d evals)"
          % (tag, best[0], best[1] if best[1] is not None else -1, len(pts)),
          flush=True)
    return best[0], best[1]


def _sky_band(preset, gain, v0=0.88, v1=1.00, tag="g"):
    """The gain protocol: camera at the origin looking +Y, lens 18, mean
    display value of the top 12 % of the frame.  Identical to cmd_gain(), so
    the new numbers are comparable with the old 0.587 / 0.306 readings."""
    sc, cfg = sky_bench(preset=preset, gain=gain)
    _cam(sc, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), lens=18.0)
    p = _render(sc, os.path.join(OUT, "_g_%s.png" % preset))
    b = _band(p, v0, v1, cols=15)
    return b[0]


def cmd_gainall(*a, **k):
    """Re-measure every preset's gain for a top-band display value of 0.55-0.60."""
    import hd_sky

    o = _args(*a, **k)
    tgt = float(o.get("target", 0.575))
    only = o.get("only")
    names = ([str(only)] if isinstance(only, str) else list(only)) if only \
        else list(hd_sky.PRESET_NAMES)
    print("[gain] target top-band display = %.3f" % tgt, flush=True)
    rows = []
    for name in names:
        try:
            import hd_sky as S
            g0 = float(S.PRESETS[name]["gain"])
            amb0 = float(S.PRESETS[name]["ambient"])
            g, v = _solve(lambda x: _sky_band(name, x), g0, tgt, tag=name)
            rows.append((name, g0, g, v, amb0 * g0 / max(g, 1e-6)))
        except Exception as exc:                             # noqa: BLE001
            import traceback
            traceback.print_exc()
            print("[gain] %s FAILED %s" % (name, exc), flush=True)
    print("[gain] %-15s %8s %8s %7s %9s" % ("preset", "old", "new", "band",
                                            "amb*="), flush=True)
    for name, g0, g, v, an in rows:
        print("[gain] %-15s %8.2f %8.2f %7.3f %9.3f"
              % (name, g0, g, v if v is not None else -1.0, an), flush=True)
    return 0


def cmd_amball(*a, **k):
    """Solve the world fill per preset so a no-direct-sun surface lands at
    SHADOW_AIM.  One sun-off render per preset gives the mask, then the fill is
    swept against it."""
    import hd_sky

    o = _args(*a, **k)
    tgt = float(o.get("target", SHADOW_AIM))
    w, h = [int(x) for x in str(o.get("res", "480x270")).split("x")]
    samples = int(o.get("samples", 6))
    only = o.get("only")
    names = ([str(only)] if isinstance(only, str) else list(only)) if only \
        else list(hd_sky.PRESET_NAMES)
    print("[amb] target shadow p50 = %.3f  (%dx%d)" % (tgt, w, h), flush=True)
    street_scene(w, h, samples)
    rows = []
    for name in names:
        try:
            import hd_sky as S
            f0 = float(S.PRESETS[name].get("fill", 2.4))
            a0 = 1.0                                   # multiplier on `fill`
            sc, _i, _s = street_shoot(name, w=w, h=h, samples=samples)
            on = _shoot(sc, os.path.join(OUT, "_am_on_%s.png" % name))
            sc, _i, _s = street_shoot(name, w=w, h=h, samples=samples, sun=0.0)
            off = _shoot(sc, os.path.join(OUT, "_am_off_%s.png" % name))
            _w, _h, idx = _mask(on, off)
            base = _num(_masked(on, idx))
            if not idx:
                print("[amb] %s: empty mask, skipped" % name, flush=True)
                continue

            def f(x, _n=name, _idx=idx):
                sc, _i, _s = street_shoot(_n, w=w, h=h, samples=samples, ambient=x)
                p = _shoot(sc, os.path.join(OUT, "_am_p_%s.png" % _n))
                s = _num(_masked(p, _idx))
                return s["p50"] if s else 0.0

            a, v = _solve(f, a0, (float(o.get("night", 0.12))
                                  if name == "night_torch" else tgt),
                          lo=0.05, hi=8.0, tag=name)
            rows.append((name, f0, f0 * a, v, base))
        except Exception as exc:                             # noqa: BLE001
            import traceback
            traceback.print_exc()
            print("[amb] %s FAILED %s" % (name, exc), flush=True)
    print("[amb] %-15s %7s %7s %7s %7s" % ("preset", "fill0", "fill", "p50",
                                           "oldp50"), flush=True)
    for name, f0, fx, v, base in rows:
        print("[amb] %-15s %7.3f %7.3f %7.3f %7.3f"
              % (name, f0, fx, v if v is not None else -1.0,
                 base["p50"] if base else -1.0), flush=True)
    return 0


def _band_stats(path, v0=0.238, v1=0.762, step=2):
    """Luminance spread *and* horizontal edge energy inside a frame band.

    Edge energy is the honest test for "can you see a cloud": a smooth sky
    gradient has ~0.002, a deck with bases and edges has 10x that.  A band that
    is merely *darker* but flat is fog, not cloud.
    """
    w, h, a = _read(path)
    vals, edge = [], []
    for y in range(int(h * v0), int(h * v1), step):
        row = y * w * 4
        prev = None
        for x in range(0, w, step):
            j = row + x * 4
            lv = _lum(a[j], a[j + 1], a[j + 2])
            vals.append(lv)
            if prev is not None:
                edge.append(abs(lv - prev))
            prev = lv
    s = _num(vals)
    if s is not None:
        s["edge"] = (sum(edge) / len(edge)) if edge else 0.0
        s["spread"] = s["p95"] - s["p05"]
    return s


def cmd_lowcloud(*a, **k):
    """Prove the deck reads in 0-12 deg of elevation.

    A 52 deg game camera sees the horizon band and nothing else, so the only
    question that matters about a cumulus layer is what it does at 0-12 deg.
    Framed at pitch +6 deg, lens 50: the frame runs -5.4..+17.4 deg, so the
    band of interest owns the middle half of the picture instead of 60 pixels.
    """
    import math

    import hd_sky

    o = _args(*a, **k)
    pitch = float(o.get("pitch", 6.0))
    lens = float(o.get("lens", 50.0))
    only = o.get("only")
    names = ([str(only)] if isinstance(only, str) else list(only)) if only \
        else ["morning_town", "golden_street", "overcast_soft", "noon_harsh"]
    for name in names:
        try:
            for tag, cl in (("clear", 0.0), ("deck", 1.0)):
                sc, cfg = sky_bench(preset=name, clouds=cl)
                az = math.radians(float(cfg["sun_azim"]))
                el = math.radians(pitch)
                d = (math.sin(az) * math.cos(el),
                     math.cos(az) * math.cos(el), math.sin(el))
                _cam(sc, (0.0, 0.0, 0.0), (d[0] * 10, d[1] * 10, d[2] * 10),
                     lens=lens)
                p = _render(sc, os.path.join(OUT, "_lc_%s_%s.png" % (name, tag)))
                s = _band_stats(p)
                # and the 640x360 strip of the same frame for the report
                if tag == "deck":
                    _render(sc, os.path.join(FINAL, "sky2_lowcloud_%s.png" % name))
                print("[cloud] %-14s %-5s %s  edge=%.4f spread=%.3f"
                      % (name, tag, _fmt(s), s["edge"], s["spread"]), flush=True)
        except Exception as exc:                             # noqa: BLE001
            import traceback
            traceback.print_exc()
            print("[cloud] %s FAILED %s" % (name, exc), flush=True)
    return 0


def cmd_final(*a, **k):
    """Deliverables: one 640x360 frame per preset (street + sky in one picture),
    shadow number for each, then the two 960x540 wide shots."""
    import hd_sky

    o = _args(*a, **k)
    w, h = [int(x) for x in str(o.get("res", "640x360")).split("x")]
    samples = int(o.get("samples", 12))
    only = o.get("only")
    names = ([str(only)] if isinstance(only, str) else list(only)) if only \
        else list(hd_sky.PRESET_NAMES)
    street_scene(w, h, samples)
    rows = []
    for name in names:
        try:
            sc, info, _sp = street_shoot(name, spec="hero", w=w, h=h,
                                         samples=samples)
            p = _shoot(sc, os.path.join(FINAL, "sky2_%s.png" % name))
            sc, _i, _s = street_shoot(name, spec="hero", w=w, h=h,
                                      samples=samples, sun=0.0)
            off = _shoot(sc, os.path.join(OUT, "_fin_off_%s.png" % name))
            _w, _h, idx = _mask(p, off, v1=0.56)
            s = _num(_masked(p, idx))
            top = _band(p, 0.90, 1.00, cols=15)[0]
            rows.append((name, s, top))
            ok = "OK" if (s and SHADOW_TARGET[0] <= s["p50"] <= SHADOW_TARGET[1]) \
                else "FAIL"
            print("[final] %-15s shade %2.0f%%  %s  topband=%.3f -> %s"
                  % (name, 100.0 * len(idx) * 4.0 / (w * h * 0.56), _fmt(s),
                     top, ok), flush=True)
        except Exception as exc:                             # noqa: BLE001
            import traceback
            traceback.print_exc()
            print("[final] %s FAILED %s" % (name, exc), flush=True)
    print("[final] %-15s %7s %7s %7s" % ("preset", "shade", "p50/255", "topband"),
          flush=True)
    for name, s, top in rows:
        print("[final] %-15s %7.3f %7.0f %7.3f"
              % (name, s["p50"] if s else -1, 255.0 * s["p50"] if s else -1, top),
              flush=True)
    for tag, name, over in (
            ("sky2_wide_morning", "morning_town",
             dict(sky_elev=0.0)),
            ("sky2_wide_golden", "golden_street",
             dict(sky_elev=0.0))):
        try:
            over = {kk: vv for kk, vv in over.items() if not kk.startswith("sky_")}
            wide_bench(name, ap=True, glare=False, **over)
            _render(bpy.context.scene, os.path.join(FINAL, "%s.png" % tag))
            p = os.path.join(FINAL, "%s.png" % tag)
            s = _band_stats(p, 0.55, 1.0)
            print("[final] %-18s wide band edge=%.4f spread=%.3f p50=%.3f"
                  % (tag, s["edge"], s["spread"], s["p50"]), flush=True)
        except Exception as exc:                             # noqa: BLE001
            import traceback
            traceback.print_exc()
            print("[final] %s FAILED %s" % (tag, exc), flush=True)
    return 0


def cmd_domes(*a, **k):
    """Is the dome actually where the camera is?  The gain protocol only means
    something if the emissive shell encloses the camera at full size -- if its
    scale driver has no camera to read, the sphere collapses to 1 m and every
    'sky' measurement is the flat inside of a pebble."""
    o = _args(*a, **k)
    preset = str(o.get("preset", "morning_town"))
    sc, cfg = sky_bench(preset=preset)
    ob = bpy.data.objects.get("SKY_dome")

    def dump(tag):
        cam = sc.camera
        print("[dome] %-8s dome=%s loc=%s scale=%s | cam=%s loc=%s clip=%.1f"
              % (tag, "yes" if ob else "NO",
                 tuple(round(v, 1) for v in ob.location) if ob else "-",
                 tuple(round(v, 3) for v in ob.scale) if ob else "-",
                 getattr(cam, "name", None),
                 tuple(round(v, 1) for v in cam.location) if cam else "-",
                 (cam.data.clip_end if cam else -1)), flush=True)

    dump("after")
    cam = _cam(sc, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), lens=50.0)
    bpy.context.view_layer.update()
    dump("moved")
    _render(sc, os.path.join(OUT, "_dome_probe.png"))
    bpy.context.view_layer.update()
    dump("rendered")
    return 0


CMDS = {"dbg": cmd_dbg, "gain": cmd_gain, "strip": cmd_strip,
        "wide": cmd_wide, "ap": cmd_ap, "stats": cmd_stats,
        "links": cmd_links, "all": cmd_all, "nodes": cmd_nodes,
        "diag": cmd_diag, "mist": cmd_mist,
        "bc": cmd_bc, "shadow": cmd_shadow, "gainall": cmd_gainall,
        "amball": cmd_amball, "lowcloud": cmd_lowcloud, "final": cmd_final,
        "domes": cmd_domes}


def main():
    argv = sys.argv
    if "--" in argv:
        args = argv[argv.index("--") + 1:]
    elif IN_BLENDER:
        args = []
    else:
        args = argv[1:]
    if not IN_BLENDER:
        cmd = args[0] if args else "strip"
        return _relaunch(cmd, *args[1:])
    cmd = args[0] if args else "strip"
    os.makedirs(OUT, exist_ok=True)
    over = _kw(args)
    fn = CMDS.get(cmd)
    if fn is None:
        print("[lab] unknown command %r; have %s" % (cmd, sorted(CMDS)))
        return 2
    if cmd in ("dbg", "strip", "wide", "gain") and over:
        print("[lab] overrides %s" % over)
    if over and cmd in ("dbg", "strip", "wide"):
        return fn(*[a for a in args[1:] if "=" not in a], **over)
    if cmd == "strip" and len(args) > 1 and not _isnum(args[1]):
        return fn(only=",".join(args[1:]).split(","))
    return fn(*args[1:])


if __name__ == "__main__":
    rc = main()
    if isinstance(rc, tuple):
        rc = rc[0]
    print("[lab] done rc=%s" % rc)
