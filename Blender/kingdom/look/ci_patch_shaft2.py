"""Replace the surface shaft shader with a real VOLUME shader."""
import io
import ast

P = r"E:\My World\Blender\kingdom\hd_cathedral_int.py"

NEW = '''def shaft_mat(color, strength=None, alpha=None):
    """Volume shader: the tube is a wedge of denser air, not a glass sheet.

    A surface shader (emission + alpha) always shows its silhouette as a hard
    edged pane.  A Principled Volume integrates along the ray instead, so the
    beam has soft ends, breathes with the distance and scatters towards the
    camera exactly like the real haze it is standing in for.
    """
    density = SHAFT_DENS if strength is None else strength
    key = "%s_%.3f" % (color, density)
    if key in _SHAFT_MATS:
        return _SHAFT_MATS[key]
    mat = bpy.data.materials.new("ci_shaft_" + key)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (620, 0)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.location = (320, 120)
    nt.links.new(tr.outputs[0], out.inputs["Surface"])
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.location = (320, -140)
    col = tuple(MK.c(color))[:3]
    _inp(vol, ("Color",), (col[0], col[1], col[2], 1.0))
    _inp(vol, ("Anisotropy",), 0.55)
    _inp(vol, ("Absorption Color",), (0.0, 0.0, 0.0, 1.0))
    _inp(vol, ("Absorption Density",), 0.0)
    _inp(vol, ("Emission Strength",), 0.0)
    at = nt.nodes.new("ShaderNodeAttribute")
    at.location = (-120, -260)
    at.attribute_name = "fade"
    m1 = nt.nodes.new("ShaderNodeMath")
    m1.operation = "MULTIPLY"
    m1.location = (60, -240)
    m1.use_clamp = True
    m1.inputs[1].default_value = density
    nt.links.new(at.outputs["Fac"], m1.inputs[0])
    nt.links.new(m1.outputs[0], vol.inputs["Density"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    mat.use_backface_culling = False
    _SHAFT_MATS[key] = mat
    return mat


'''

A = "def shaft_mat(color, strength=None, alpha=None):"
B = "def _one_shaft("


def main():
    s = io.open(P, encoding="utf-8").read()
    i = s.index(A)
    j = s.index(B, i)
    s = s[:i] + NEW + s[j:]
    s = s.replace("SHAFT_ALPHA = 0.105", "SHAFT_DENS = 0.16          # extra density inside a beam")
    s = s.replace("MK.assign(ob, shaft_mat(_SHAFT_COLS[seed % len(_SHAFT_COLS)]))",
                  "MK.assign(ob, shaft_mat(_SHAFT_COLS[seed % len(_SHAFT_COLS)]))")
    ast.parse(s)
    io.open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("volume shaft shader installed, %d lines" % len(s.splitlines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
