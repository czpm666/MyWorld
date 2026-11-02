def _tris(parts):
    n = 0
    for ob in parts:
        if ob is None or ob.type != "MESH":
            continue
        for p in ob.data.polygons:
            n += max(1, len(p.vertices) - 2)
    return n


def preview(samples=8, res=(480, 270), tag="ci", shots=None):
    """Build in an empty scene, light it, and render the design shots."""
    K.reset_scene()
    MAT = make_mats()
    t0 = __import__("time").time()
    P = build(K, MAT, origin=(0.0, 0.0), seed=3)
    print("PREVIEW parts=%d tris=%d build=%.1fs"
          % (len(P), _tris(P), __import__("time").time() - t0), flush=True)
    H.setup_engine(samples=samples, res=res, gpu=True)
    sc = bpy.context.scene
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    w = bpy.data.worlds.new("ci_W")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (0.40, 0.48, 0.62, 1.0)
    bg.inputs[1].default_value = 0.055
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = 0.0034
    vol.inputs["Anisotropy"].default_value = 0.55
    vol.inputs["Color"].default_value = (0.92, 0.93, 0.97, 1.0)
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    sd = bpy.data.lights.new("ci_preview_sun", "SUN")
    sd.energy = 22.0
    sd.angle = math.radians(0.6)
    sd.color = (1.0, 0.93, 0.80)
    so = bpy.data.objects.new("ci_preview_sun", sd)
    K.link(so)
    so.rotation_euler = (math.radians(52.0), 0.0, math.radians(38.0))
    if shots is None:
        shots = [
            ("A_door", (HX - 2.6, 0.0, EYE), (-HX + 1.2, 0.0, 2.65), 30.0),
            ("B_throne", (-4.6, 1.60, 2.45), (THR_X + 0.4, 0.0, 2.60), 30.0),
            ("C_feast", (6.0, -5.2, FZ0 + 1.70), (-9.0, 2.0, FZ0 + 2.2), 24.0),
            ("D_stair", (ST_CX - 2.55, ST_CY - 0.95, 1.55),
             (ST_CX + 0.7, ST_CY + 0.5, 8.4), 18.0),
            ("E_torch", (ST_CX + 1.55 * math.cos(math.radians(243.0)),
                         ST_CY + 1.55 * math.sin(math.radians(243.0)), 2.30),
             (ST_CX + 3.1 * math.cos(math.radians(280.0)),
              ST_CY + 3.1 * math.sin(math.radians(280.0)), 3.30), 26.0),
            ("F_shaft", (-2.0, -7.4, 1.72), (6.0, -1.6, 8.6), 22.0),
        ]
    for (nm, loc, look, lens) in shots:
        cam = _cam("ci_" + nm, loc, look, lens=lens)
        H.render_to(os.path.join(OUT, "%s_%s.png" % (tag, nm)), cam)
    print("PREVIEW done %.1fs" % (__import__("time").time() - t0), flush=True)
    return P


