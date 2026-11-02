def _arc_pts(hs, spring, rise, n=10):
    """Half a two-centred pointed arch, from (hs, spring) up to the apex."""
    P = []
    if rise < hs * 0.999:
        R = (hs * hs + rise * rise) / (2.0 * rise)
        zc = spring + rise - R
        for k in range(n + 1):
            x = hs * (1.0 - k / float(n))
            P.append((x, zc + math.sqrt(max(0.0, R * R - x * x))))
    else:
        R = (hs * hs + rise * rise) / (2.0 * hs)
        c = R - hs
        a_top = math.atan2(rise, c)
        for k in range(n + 1):
            a = a_top * k / float(n)
            P.append((-c + R * math.cos(a), spring + R * math.sin(a)))
    return P


def _glass_palette():
    return [(0.055, 0.105, 0.320), (0.560, 0.410, 0.115), (0.360, 0.045, 0.045),
            (0.055, 0.180, 0.105), (0.520, 0.570, 0.660), (0.230, 0.075, 0.210)]


def _glass_proc():
    """Stained glass: voronoi cells, leaded, a heraldic palette."""
    nm = "ci_glass_proc"
    m = bpy.data.materials.get(nm)
    if m:
        return m
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 4.6
    vor2 = nt.nodes.new("ShaderNodeTexVoronoi")
    vor2.feature = "F1"
    vor2.inputs["Scale"].default_value = 4.6
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    pal = _glass_palette()
    e = ramp.color_ramp.elements
    while len(e) > 1:
        e.remove(e[-1])
    e[0].position = 0.0
    e[0].color = (pal[0][0], pal[0][1], pal[0][2], 1.0)
    for k in range(1, len(pal)):
        el = e.new(pal[k][0] * 0.0 + (k / float(len(pal))))
        el.color = (pal[k][0], pal[k][1], pal[k][2], 1.0)
    mask = nt.nodes.new("ShaderNodeMapRange")
    mask.inputs["From Min"].default_value = 0.0
    mask.inputs["From Max"].default_value = 0.055
    mask.inputs["To Min"].default_value = 0.0
    mask.inputs["To Max"].default_value = 1.0
    dark = nt.nodes.new("ShaderNodeMix")
    dark.data_type = "RGBA"
    dark.blend_type = "MIX"
    dark.inputs["B"].default_value = (0.012, 0.012, 0.014, 1.0)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], vor.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], vor2.inputs["Vector"])
    nt.links.new(vor2.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(vor.outputs["Distance"], mask.inputs["Value"])
    nt.links.new(ramp.outputs["Color"], dark.inputs["A"])
    nt.links.new(mask.outputs["Result"], dark.inputs["Factor"])
    nt.links.new(dark.outputs["Result"], bsdf.inputs["Base Color"])
    nt.links.new(dark.outputs["Result"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.85
    bsdf.inputs["Roughness"].default_value = 0.14
    bsdf.inputs["Transmission Weight"].default_value = 0.90
    bsdf.inputs["IOR"].default_value = 1.52
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def glazed_window(nm, T, uc, vc, z0, hs, spring, rise, rng, order=None):
    """Leaded glass filling an arched opening, with stone mullions in front."""
    P = []
    gm = _glass_proc()
    poly = [(-hs, z0), (hs, z0)]
    half = _arc_pts(hs, spring, rise, 9)
    poly += half
    poly += [(-x, z) for (x, z) in reversed(half)]
    P.append(prism_y(nm + "_glass", T @ Ts(uc, vc, 0), poly, 0.024, gm))
    ms = _m({}, "stone_light")
    for c in (1, 2):
        P.append(bx(nm + "_mull", T @ Ts(uc - hs + c * 2 * hs / 3.0, vc - 0.05,
                                        (z0 + spring) * 0.5 + 0.02),
                    (0.11, 0.13, spring - z0 + 0.06), ms, bev=0.006))
    P.append(bx(nm + "_trans", T @ Ts(uc, vc - 0.05, z0 + (spring - z0) * 0.60),
                (2 * hs, 0.10, 0.10), ms, bev=0.006))
    return P


