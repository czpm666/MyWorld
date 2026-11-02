def _smoke_mat():
    m = bpy.data.materials.get("ci_smoke_vol")
    if m:
        return m
    m = bpy.data.materials.new("ci_smoke_vol")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.62, 0.58, 0.54, 1.0)
    vol.inputs["Density"].default_value = 0.16
    vol.inputs["Anisotropy"].default_value = 0.52
    vol.inputs["Absorption Color"].default_value = (0.22, 0.20, 0.18, 1.0)
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return m


def build_smoke(M):
    """A thin plume lifting off the hearth and curling into the room."""
    P = []
    T = WF(-HX, 0.0, 0.0, "-x")
    sm = _smoke_mat()
    rings = []
    for k in range(6):
        t = k / 5.0
        z = FZ0 + 2.05 + t * 3.15
        r = 0.26 + t * 0.34
        yy = -0.06 - t * 0.42
        xx = math.sin(t * 3.1) * 0.20
        ring = []
        for j in range(10):
            a = TAU * j / 10.0
            ring.append(Vector((xx + r * math.cos(a), yy + r * 0.62 * math.sin(a), z)))
        rings.append(ring)
    ob = loft("ci_smoke", T, rings, sm, closed=True, cap0=False, cap1=False)
    P.append(ob)
    return P


