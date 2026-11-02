"""Dump a Blender material palette to JSON for the Unity importer.

The kingdom towns/capital are exported with 50..130 procedural materials and NO
textures, so Unity cannot reproduce them.  This walks every material's node graph,
collects the literal colour values feeding the Principled BSDF (base colour chain
plus any emission) and writes one average colour per material, together with
metallic / roughness / emission strength.

Usage (headless):
    blender.exe -b farm_a.blend --python dump_palette.py -- out.json
"""
import json
import os
import sys

import bpy

SKIP_PREFIX = ("Material", "Dots", "Default")


def srgb_hex(rgb):
    """Linear scene-referred colour -> #RRGGBB (sRGB encoded for display)."""
    out = []
    for c in rgb[:3]:
        c = max(0.0, min(1.0, float(c)))
        s = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055
        out.append(int(round(max(0.0, min(1.0, s)) * 255)))
    return "#%02X%02X%02X" % tuple(out)


COLOR_SOCKETS = ("A", "B", "Color", "Color1", "Color2", "Color A", "Color B",
                 "Base Color", "Base Colour", "Fac Color", "Color A ", "Colour")


def collect_colors(node, seen, acc, depth=0):
    """Gather every literal RGB feeding this socket chain (bounded walk)."""
    if node is None or depth > 7 or node.name in seen:
        return
    seen.add(node.name)
    if node.type in ("RGB", "RGB_CURVE"):
        v = node.outputs[0].default_value
        acc.append((v[0], v[1], v[2]))
        return
    if node.type in ("VALTORGB",):
        for el in node.color_ramp.elements:
            acc.append((el.color[0], el.color[1], el.color[2]))
        return
    for s in node.inputs:
        if s.is_linked:
            collect_colors(s.links[0].from_node, seen, acc, depth + 1)
        elif s.name in COLOR_SOCKETS:
            v = getattr(s, "default_value", None)
            if v is not None and hasattr(v, "__len__") and len(v) >= 3:
                acc.append((v[0], v[1], v[2]))


def average(acc):
    if not acc:
        return None
    n = float(len(acc))
    return (sum(c[0] for c in acc) / n, sum(c[1] for c in acc) / n,
            sum(c[2] for c in acc) / n)


def mat_entry(mat):
    bsdf = None
    if not mat.use_nodes or mat.node_tree is None:
        return None
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            bsdf = n
            break
    if bsdf is None:
        return None
    acc = []
    base = bsdf.inputs.get("Base Color") or bsdf.inputs.get("Base Colour")
    if base is not None:
        if base.is_linked:
            collect_colors(base.links[0].from_node, set(), acc)
        else:
            v = base.default_value
            acc.append((v[0], v[1], v[2]))
    rgb = average(acc)
    if rgb is None:
        # fall back to the viewport colour (Blender keeps it in sync with the
        # Principled base colour for most node-authored materials)
        d = mat.diffuse_color
        rgb = (d[0], d[1], d[2])

    metal = rough = 0.0
    if "Metallic" in bsdf.inputs and not bsdf.inputs["Metallic"].is_linked:
        metal = float(bsdf.inputs["Metallic"].default_value)
    if "Roughness" in bsdf.inputs and not bsdf.inputs["Roughness"].is_linked:
        rough = float(bsdf.inputs["Roughness"].default_value)

    emis_strength = 0.0
    emis_hex = None
    for key in ("Emission Strength",):
        if key in bsdf.inputs and not bsdf.inputs[key].is_linked:
            emis_strength = float(bsdf.inputs[key].default_value)
    ecol = None
    for key in ("Emission Color", "Emission"):
        if key in bsdf.inputs:
            ecol = bsdf.inputs[key]
            break
    if ecol is not None and emis_strength > 0.0:
        if ecol.is_linked:
            eacc = []
            collect_colors(ecol.links[0].from_node, set(), eacc)
            e = average(eacc)
        else:
            v = ecol.default_value
            e = (v[0], v[1], v[2])
        if e:
            emis_hex = srgb_hex(e)

    return {
        "name": mat.name,
        "hex": srgb_hex(rgb),
        "metal": round(metal, 3),
        "rough": round(rough if rough > 0.0 else 0.6, 3),
        "emis": round(emis_strength, 2),
        "emisHex": emis_hex,
    }


def main(argv):
    out = argv[-1]
    if not out.lower().endswith(".json"):
        out = os.path.join(os.path.dirname(bpy.data.filepath), "palette.json")
    colors = []
    for mat in bpy.data.materials:
        if mat.name.startswith(SKIP_PREFIX):
            continue
        e = mat_entry(mat)
        if e:
            colors.append(e)
    colors.sort(key=lambda d: d["name"].lower())
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"colors": colors}, f, indent=1)
    print("[palette] %s materials=%d -> %s" % (os.path.basename(bpy.data.filepath),
                                               len(colors), out))


if __name__ == "__main__":
    main(sys.argv)
