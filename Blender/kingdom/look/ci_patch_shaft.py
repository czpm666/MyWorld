"""One-shot patcher: insert light_shafts() into hd_cathedral_int.py."""
import io
import ast

P = r"E:\My World\Blender\kingdom\hd_cathedral_int.py"

CODE = r'''# ---------------------------------------------------------------------------
# 26b. light shafts -- soft additive air so the beams READ
# ---------------------------------------------------------------------------
# Cycles' haze does scatter for real (the sun is shadow-linked so only the
# lancets let it in), but in a sunlit room the single-scatter radiance of a
# 2 m wide beam is about a tenth of the wall behind it, so a side view of the
# beam shows nothing.  Every shaft photograph is helped by dust; here the dust
# is a very faint emission tube that follows the same DIR_TRAVEL as the sun, so
# the glow always sits exactly where the real light is.  A fade along the
# length plus a Fresnel fall-off at the silhouette keep it from reading as
# glass.
SHAFTS_ON = True
SHAFT_ALPHA = 0.115
SHAFT_STRENGTH = 1.75
_SHAFT_MATS = {}
_SHAFT_COLS = ("#ffe4bd", "#ffd79b", "#e2e9ff", "#dfe2ff", "#ffe9cc")


def _inp(node, names, val):
    for nm in names:
        sck = node.inputs.get(nm)
        if sck is not None:
            try:
                sck.default_value = val
                return True
            except Exception:
                pass
    return False


def shaft_mat(color, strength=None, alpha=None):
    strength = SHAFT_STRENGTH if strength is None else strength
    alpha = SHAFT_ALPHA if alpha is None else alpha
    key = "%s_%.2f_%.3f" % (color, strength, alpha)
    if key in _SHAFT_MATS:
        return _SHAFT_MATS[key]
    mat = bpy.data.materials.new("ci_shaft_" + key)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (620, 0)
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.location = (320, 0)
    nt.links.new(bs.outputs[0], out.inputs[0])
    _inp(bs, ("Base Color",), (0.0, 0.0, 0.0, 1.0))
    _inp(bs, ("Roughness",), 0.7)
    _inp(bs, ("Metallic",), 0.0)
    col = tuple(MK.c(color))[:3]
    _inp(bs, ("Emission Color", "Emission"), (col[0], col[1], col[2], 1.0))
    _inp(bs, ("Emission Strength",), strength)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.location = (-430, -50)
    _inp(lw, ("Blend",), 0.36)
    cr = nt.nodes.new("ShaderNodeValToRGB")
    cr.location = (-240, -50)
    cr.color_ramp.interpolation = "EASE"
    e0 = cr.color_ramp.elements[0]
    e0.position = 0.0
    e0.color = (0.0, 0.0, 0.0, 1.0)
    e1 = cr.color_ramp.elements[1]
    e1.position = 0.55
    e1.color = (1.0, 1.0, 1.0, 1.0)
    nt.links.new(lw.outputs["Facing"], cr.inputs["Fac"])
    at = nt.nodes.new("ShaderNodeAttribute")
    at.location = (-430, -260)
    at.attribute_name = "fade"
    m1 = nt.nodes.new("ShaderNodeMath")
    m1.operation = "MULTIPLY"
    m1.location = (20, -150)
    nt.links.new(at.outputs["Fac"], m1.inputs[0])
    nt.links.new(cr.outputs["Color"], m1.inputs[1])
    m2 = nt.nodes.new("ShaderNodeMath")
    m2.operation = "MULTIPLY"
    m2.location = (190, -150)
    m2.inputs[1].default_value = alpha
    nt.links.new(m1.outputs[0], m2.inputs[0])
    nt.links.new(m2.outputs[0], bs.inputs["Alpha"])
    try:
        mat.blend_method = "BLEND"
    except Exception:
        pass
    mat.use_backface_culling = False
    _SHAFT_MATS[key] = mat
    return mat


def _one_shaft(name, F, a0, a1, zsill, zspr, rise, seed, d0=0.07, flare=1.05):
    cont = arch_contour(a0, a1, zsill, zspr, rise, 10)
    ring0 = [F.p2(p, d0) for p in cont]
    n = len(ring0)
    if n < 4:
        return None
    cen = Vector((0.0, 0.0, 0.0))
    for p in ring0:
        cen = cen + p
    cen = cen / n
    L = (cen.z - 0.10) / max(0.22, abs(DIR_TRAVEL.z))
    L = max(2.5, min(L, 34.0))
    ring1 = [cen + (p - cen) * flare + DIR_TRAVEL * L for p in ring0]
    verts = [tuple(p) for p in ring0] + [tuple(p) for p in ring1]
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    ob = MK.mesh_obj(name, verts, faces, False)
    try:
        ca = ob.data.color_attributes.new(name="fade", type="FLOAT_COLOR",
                                          domain="POINT")
        for i in range(len(verts)):
            f = 1.0 if i < n else 0.0
            ca.data[i].color = (f, f, f, 1.0)
    except Exception as exc:
        L("shaft fade attr failed: %s" % exc)
    MK.assign(ob, shaft_mat(_SHAFT_COLS[seed % len(_SHAFT_COLS)]))
    ob.visible_shadow = False
    PARTS.append(ob)
    return ob


def light_shafts(gain=1.0):
    """Faint additive tubes that follow the sun through the lancets."""
    if not SHAFTS_ON:
        return []
    if gain != 1.0:
        global SHAFT_ALPHA
        SHAFT_ALPHA = SHAFT_ALPHA * gain
        _SHAFT_MATS.clear()
    objs = []
    k = 0
    for (F, a0, a1, zsill, zspr, rise, th, seed) in list(WINDOWS):
        if zsill < 12.0:
            continue
        d = F.N.normalized().dot(SUN_TO)
        if d < 0.05:
            continue
        if abs(F.N.x) > 0.6:
            k += 1
            if k % 2 == 0:
                continue
        ob = _one_shaft("ci_beam%02d" % k, F, a0, a1, zsill, zspr, rise, seed)
        if ob is not None:
            objs.append(ob)
        if k >= 26:
            break
    L("shafts: %d" % len(objs))
    return objs


'''

ANCHOR = 'def _sun_linked(receivers_extra=(), energy=None, angle=0.9, color="#fff3dc"):'
HOOK_A = "    build_furniture()\n\n    if _XFORM != Matrix.Identity(4):"
HOOK_B = "    build_furniture()\n    light_shafts()\n\n    if _XFORM != Matrix.Identity(4):"


def main():
    s = io.open(P, encoding="utf-8").read()
    if "def light_shafts(" in s:
        print("already patched")
        return 0
    n1 = s.count(ANCHOR)
    n2 = s.count(HOOK_A)
    print("anchor=%d hook=%d" % (n1, n2))
    if n1 != 1 or n2 != 1:
        print("!! anchor mismatch, nothing written")
        return 1
    s = s.replace(ANCHOR, CODE + ANCHOR)
    s = s.replace(HOOK_A, HOOK_B)
    ast.parse(s)
    io.open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("patched, %d lines" % len(s.splitlines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
