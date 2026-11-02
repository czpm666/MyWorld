

# ===========================================================================
# PART E - materials tuning, light rig, and the public build()
# ===========================================================================
def _ashlar(name, c1, c2, mortar, bw=1.15, bh=0.46, ms=0.020, rough=0.80,
            bump=0.30, grime=0.35):
    """Big, mostly flat ashlar blocks: what a keep is really built of."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.5
    br.offset_frequency = 1
    br.squash = 1.0
    br.inputs["Color1"].default_value = c1
    br.inputs["Color2"].default_value = c2
    br.inputs["Mortar"].default_value = mortar
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = ms
    br.inputs["Brick Width"].default_value = bw
    br.inputs["Row Height"].default_value = bh
    noi = nt.nodes.new("ShaderNodeTexNoise")
    noi.inputs["Scale"].default_value = 1.7
    noi.inputs["Detail"].default_value = 6.0
    noi.inputs["Roughness"].default_value = 0.62
    gr = nt.nodes.new("ShaderNodeMix")
    gr.data_type = "RGBA"
    gr.blend_type = "MULTIPLY"
    gr.inputs["Factor"].default_value = grime
    nt.links.new(noi.outputs["Fac"], gr.inputs["B"])
    nt.links.new(br.outputs["Color"], gr.inputs["A"])
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], noi.inputs["Vector"])
    nt.links.new(gr.outputs["Result"], b.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.02
    nt.links.new(br.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    return m


def prep(MAT):
    """Swap in the interior's own stone, so the hall does not read as bricks."""
    M = dict(MAT)
    M["stone_wall"] = _ashlar("ci_ash_wall", (0.150, 0.140, 0.126),
                              (0.185, 0.172, 0.152), (0.075, 0.070, 0.063),
                              bw=1.18, bh=0.47, grime=0.42)
    M["stone"] = M["stone_wall"]
    M["stone_light"] = _ashlar("ci_ash_light", (0.250, 0.235, 0.208),
                               (0.290, 0.272, 0.238), (0.150, 0.141, 0.124),
                               bw=0.62, bh=0.34, ms=0.012, rough=0.72, grime=0.30)
    M["stone_course"] = _ashlar("ci_ash_course", (0.300, 0.282, 0.250),
                                (0.340, 0.320, 0.282), (0.180, 0.170, 0.150),
                                bw=1.60, bh=0.30, ms=0.014, rough=0.68, grime=0.26)
    M["stone_dark"] = _ashlar("ci_ash_dark", (0.085, 0.080, 0.074),
                              (0.110, 0.104, 0.094), (0.045, 0.042, 0.038),
                              bw=0.90, bh=0.40, grime=0.5)
    M["stone_floor"] = _ashlar("ci_flag", (0.185, 0.176, 0.160),
                               (0.225, 0.212, 0.192), (0.070, 0.066, 0.060),
                               bw=1.02, bh=0.68, ms=0.016, rough=0.52, bump=0.42,
                               grime=0.5)
    M["stone_step"] = _ashlar("ci_step", (0.245, 0.230, 0.205),
                              (0.280, 0.262, 0.230), (0.120, 0.113, 0.100),
                              bw=1.30, bh=0.33, ms=0.010, rough=0.55)
    M["marble"] = _ashlar("ci_marble", (0.420, 0.400, 0.360),
                          (0.470, 0.450, 0.405), (0.300, 0.285, 0.255),
                          bw=1.70, bh=0.60, ms=0.006, rough=0.30, bump=0.10)
    return M


def build_lights(MAT, rng):
    """Warm points in the hall, the hearth, the torches and the feast hall."""
    P = []
    fire = (1.0, 0.42, 0.12)
    cand = (1.0, 0.74, 0.40)
    # braziers flanking the dais
    for s in (-1, 1):
        L = bpy.data.lights.new("ci_br_light", "POINT")
        L.energy = 900.0
        L.shadow_soft_size = 0.34
        L.color = fire
        o = bpy.data.objects.new("ci_br_light", L)
        o.location = (DAIS_X1 + STEP_D * N_STEP + 1.35, s * 4.35, 1.45)
        K.link(o)
        P.append(o)
    # candles on the dais
    for s in (-1, 1):
        L = bpy.data.lights.new("ci_cd_light", "POINT")
        L.energy = 260.0
        L.shadow_soft_size = 0.10
        L.color = cand
        o = bpy.data.objects.new("ci_cd_light", L)
        o.location = (DAIS_X0 + 1.15, s * 3.95, Z_DAIS + 1.55)
        K.link(o)
        P.append(o)
    # a key on the throne, so the seat and the crown read
    L = bpy.data.lights.new("ci_thr_key", "SPOT")
    L.energy = 2600.0
    L.spot_size = math.radians(52.0)
    L.spot_blend = 0.55
    L.shadow_soft_size = 0.30
    L.color = (1.0, 0.86, 0.66)
    o = bpy.data.objects.new("ci_thr_key", L)
    o.location = (THR_X + 4.6, 0.35, 6.30)
    o.rotation_euler = (math.radians(58.0), 0.0, math.radians(-96.0))
    K.link(o)
    P.append(o)
    # a cool rim from the great window behind the throne
    L = bpy.data.lights.new("ci_thr_rim", "AREA")
    L.energy = 1400.0
    L.size = 4.6
    L.size_y = 1.7
    L.color = (0.62, 0.74, 1.0)
    o = bpy.data.objects.new("ci_thr_rim", L)
    o.location = (-HX + 0.30, 0.0, 12.6)
    o.rotation_euler = (0.0, math.radians(-90.0), 0.0)
    K.link(o)
    P.append(o)
    # warm pools in the arcade, so the niches do not go dead
    for i in range(NBAY):
        xm = 0.5 * (BAYX[i] + BAYX[i + 1])
        for s in (-1, 1):
            L = bpy.data.lights.new("ci_arc_light", "POINT")
            L.energy = 150.0
            L.shadow_soft_size = 0.22
            L.color = cand
            o = bpy.data.objects.new("ci_arc_light", L)
            o.location = (xm, s * (HY - 0.34), 3.9)
            K.link(o)
            P.append(o)
    # hearth in the feast hall
    L = bpy.data.lights.new("ci_fp_light", "POINT")
    L.energy = 3200.0
    L.shadow_soft_size = 0.55
    L.color = fire
    o = bpy.data.objects.new("ci_fp_light", L)
    o.location = (-HX + 0.85, 0.0, FZ0 + 0.95)
    K.link(o)
    P.append(o)
    # chandelier
    L = bpy.data.lights.new("ci_ch_light", "POINT")
    L.energy = 1100.0
    L.shadow_soft_size = 0.40
    L.color = cand
    o = bpy.data.objects.new("ci_ch_light", L)
    o.location = (-1.0, 0.0, FZ1 - 3.70)
    K.link(o)
    P.append(o)
    # torches up the shaft, and the lantern over the well
    for k in range(9):
        i = 6 + k * 12
        a = ST_A0 + i * ST_STEP_A
        z = ST_RISE * (i + 1)
        rr = ST_R - 0.28
        L = bpy.data.lights.new("ci_st_light", "POINT")
        L.energy = 240.0
        L.shadow_soft_size = 0.12
        L.color = fire
        o = bpy.data.objects.new("ci_st_light", L)
        o.location = (ST_CX + rr * math.cos(a), ST_CY + rr * math.sin(a), z + 2.05)
        K.link(o)
        P.append(o)
    L = bpy.data.lights.new("ci_st_lampL", "POINT")
    L.energy = 900.0
    L.shadow_soft_size = 0.30
    L.color = (1.0, 0.82, 0.55)
    o = bpy.data.objects.new("ci_st_lampL", L)
    o.location = (ST_CX, ST_CY, Z_TOP - 0.70)
    K.link(o)
    P.append(o)
    # soft daylight fills just inside the clerestory, keyed to the sun
    for i in range(NBAY):
        xm = 0.5 * (BAYX[i] + BAYX[i + 1])
        for s in (-1, 1):
            L = bpy.data.lights.new("ci_win_fill", "AREA")
            L.energy = 520.0
            L.size = 2.6
            L.size_y = 3.2
            L.color = (0.80, 0.86, 1.0)
            o = bpy.data.objects.new("ci_win_fill", L)
            o.location = (xm, s * (HY - 0.45), 11.6)
            o.rotation_euler = (math.radians(90.0) * (-s if s > 0 else 1) + 0.0,
                                0.0, 0.0)
            if s < 0:
                o.rotation_euler = (math.radians(-90.0), 0.0, math.radians(180.0))
            K.link(o)
            P.append(o)
    # and for the feast hall windows
    for i in range(4):
        xc = -HX + (i + 0.5) * (2 * HX / 4.0)
        for s in (-1, 1):
            L = bpy.data.lights.new("ci_f_winfill", "AREA")
            L.energy = 900.0
            L.size = 3.0
            L.size_y = 2.4
            L.color = (0.86, 0.90, 1.0)
            o = bpy.data.objects.new("ci_f_winfill", L)
            o.location = (xc, s * (HY - 0.40), FZ0 + 3.10)
            o.rotation_euler = (math.radians(90.0) if s > 0 else math.radians(90.0),
                                0.0, math.radians(0.0) if s > 0 else math.radians(180.0))
            K.link(o)
            P.append(o)
    return P


def build(KM, MAT, origin=(0.0, 0.0), rot=0.0, scale=1.0, seed=3, lights=True):
    """Build the whole keep interior and return its objects.

    The module is modelled with its floor at z=0, centred on x=0 and spanning
    y -HY..+HY, and its +X end is the entrance.  Call it as::

        obj = hd_castle_int.build(medkit, MAT, origin=(0.0, -21.0), rot=0.0,
                                  scale=1.0, seed=3)
        hd_common.apply(obj, hd_common.Ts(0, 0, 1.30))   # up to the courtyard

    which puts it inside hd_castle.keep()'s 30 x 22 x 42 m void with 0.75 m
    to spare on every side.
    """
    rng = random.Random(seed)
    M = prep(MAT)
    P = []
    P += build_floor(M, rng)
    P += side_wall(1, M, rng)
    P += side_wall(-1, M, rng)
    P += end_wall(1, M, rng)
    P += end_wall(-1, M, rng)
    P += build_roof(M, rng)
    P += build_dais(M)
    P += build_throne(M, rng)
    P += build_guards(M)
    P += build_braziers(M)
    P += build_candles(M)
    P += build_banners(M, rng)
    P += build_side_door(M)
    P += build_carpet(M)
    P += build_stair_tower(M, rng)
    P += build_feast_floor(M, rng)
    P += build_feast_ceiling(M, rng)
    P += feast_wall(1, M, rng)
    P += feast_wall(-1, M, rng)
    P += feast_long_wall(1, M, rng)
    P += feast_long_wall(-1, M, rng)
    P += build_fireplace(M, rng)
    P += build_smoke(M)
    P += build_feast_tables(M, rng)
    P += build_chandelier(M, rng)
    P += build_barrels(M, rng)
    P += build_feast_props(M, rng)
    if lights:
        P += build_lights(M, rng)
    P = [o for o in P if o is not None]
    T = (Matrix.Translation((origin[0], origin[1], 0.0))
         @ Matrix.Rotation(rot, 4, "Z") @ Matrix.Scale(scale, 4))
    H.apply(P, T)
    return P


def preview(samples=8, res=(480, 270), tag="ci"):
    """Build in an empty scene, light it, and render the design shots."""
    K.reset_scene()
    MAT = make_mats()
    t0 = __import__("time").time()
    P = build(K, MAT, origin=(0.0, 0.0), seed=3)
    print("PREVIEW parts=%d tris=%d build=%.1fs"
          % (len(P), H.tri_count(P), __import__("time").time() - t0), flush=True)
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
    bg.inputs[0].default_value = (0.42, 0.50, 0.64, 1.0)
    bg.inputs[1].default_value = 0.10
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = 0.010
    vol.inputs["Anisotropy"].default_value = 0.40
    vol.inputs["Color"].default_value = (0.90, 0.91, 0.95, 1.0)
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    sd = bpy.data.lights.new("ci_preview_sun", "SUN")
    sd.energy = 14.0
    sd.angle = math.radians(0.7)
    sd.color = (1.0, 0.94, 0.82)
    so = bpy.data.objects.new("ci_preview_sun", sd)
    K.link(so)
    so.rotation_euler = (math.radians(52.0), 0.0, math.radians(38.0))
    shots = [
        ("A_entry", (HX - 2.4, 0.0, EYE), (-HX + 1.0, 0.0, 3.2), 32.0),
        ("B_throne", (-5.2, 1.35, 2.05), (THR_X, 0.0, 2.10), 42.0),
        ("C_wide", (10.4, 7.0, 1.72), (-9.0, -2.4, 3.0), 21.0),
        ("D_roof", (-2.0, 0.5, 1.72), (-9.6, 2.0, 15.0), 20.0),
        ("E_feast", (7.6, -6.4, FZ0 + 1.70), (-8.6, 2.4, FZ0 + 2.6), 22.0),
        ("F_stair", (ST_CX - 1.0, ST_CY - 1.0, 0.2), (ST_CX + 1.4, ST_CY + 1.0, 9.0),
         16.0),
    ]
    for (nm, loc, look, lens) in shots:
        cam = _cam("ci_" + nm, loc, look, lens=lens)
        H.render_to(os.path.join(OUT, "%s_%s.png" % (tag, nm)), cam)
    print("PREVIEW done", flush=True)
    return P


if __name__ == "__main__":
    preview()
