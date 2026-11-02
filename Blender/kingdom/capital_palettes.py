"""Dump ONE palette JSON for the capital from a saved .blend.

Why: the kingdom towns each got a palette JSON from their own builder, but the
capital is authored by capital.py which never dumped one - so every ars_*.fbx
would import into Unity with a mid-grey fallback material for all 100+
procedural materials.

The colour extraction is the same node-graph walk used by dump_palette.py (a
Principled "Base Color" link is usually a Mix/Noise/ramp chain, so reading the
socket default would return grey for every material - the bug that produced
"#BCBCBC for everything" the first time round).

    blender.exe -b capital_full.blend --python capital_palettes.py
"""
import json
import os

import bpy

OUT = r"E:\My World\Blender\export\kingdom\palettes\capital.json"

SKIP_PREFIX = ("Material", "Dots", "Default")

COLOR_SOCKETS = ("A", "B", "Color", "Color1", "Color2", "Color A", "Color B",
                 "Base Color", "Base Colour", "Fac Color", "Color A ", "Colour")


def srgb_hex(rgb):
    out = []
    for c in rgb[:3]:
        c = max(0.0, min(1.0, float(c)))
        s = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055
        out.append(int(round(max(0.0, min(1.0, s)) * 255)))
    return "#%02X%02X%02X" % tuple(out)


def collect_colors(node, seen, acc, depth=0):
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
    if not mat.use_nodes or mat.node_tree is None:
        return None
    bsdf = None
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
        d = mat.diffuse_color
        rgb = (d[0], d[1], d[2])

    metal = 0.0
    rough = 0.0
    if "Metallic" in bsdf.inputs and not bsdf.inputs["Metallic"].is_linked:
        metal = float(bsdf.inputs["Metallic"].default_value)
    if "Roughness" in bsdf.inputs and not bsdf.inputs["Roughness"].is_linked:
        rough = float(bsdf.inputs["Roughness"].default_value)

    emis = 0.0
    if "Emission Strength" in bsdf.inputs and not bsdf.inputs["Emission Strength"].is_linked:
        emis = float(bsdf.inputs["Emission Strength"].default_value)

    emis_hex = None
    if emis > 0.0:
        ecol = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        if ecol is not None:
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
        "emis": round(emis, 2),
        "emisHex": emis_hex,
    }


def main():
    used = {}
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        for slot in ob.material_slots:
            m = slot.material
            if m is None or m.name in used or m.name.startswith(SKIP_PREFIX):
                continue
            e = mat_entry(m)
            if e is not None:
                used[m.name] = e

    data = {"colors": sorted(used.values(), key=lambda x: x["name"].lower())}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    print("[palette] materials=%d -> %s (%d bytes)" %
          (len(used), OUT, os.path.getsize(OUT)), flush=True)
    # a couple of spot checks so a wrong extraction is visible in the log
    for probe in ("tile_0", "stone", "grass_dry", "cloth_banner_crimson", "torch_glow"):
        for e in data["colors"]:
            if e["name"] == probe:
                print("[palette] %s -> %s" % (probe, e["hex"]), flush=True)


main()
