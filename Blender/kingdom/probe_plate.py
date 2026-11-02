"""Probe an exported farm FBX for large flat plates and fence anatomy."""
import bpy
import os
import sys
import json

FBX_DIR = r"E:\My World\Blender\export\kingdom\farm"
variant = "farm_a"
for i, a in enumerate(sys.argv):
    if a == "--":
        if len(sys.argv) > i + 1:
            variant = sys.argv[i + 1]
        break

bpy.ops.wm.read_factory_settings(use_empty=True)
path = os.path.join(FBX_DIR, variant + ".fbx")
bpy.ops.import_scene.fbx(filepath=path)

rows = []
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices]
    xs = [(ob.matrix_world @ v.co).x for v in ob.data.vertices]
    ys = [(ob.matrix_world @ v.co).y for v in ob.data.vertices]
    # FBX import: Y up, so height is Y in blender? report all three
    mw = ob.matrix_world
    vs = [mw @ v.co for v in ob.data.vertices]
    rows.append(dict(
        name=ob.name,
        xs=[min(v.x for v in vs), max(v.x for v in vs)],
        ys=[min(v.y for v in vs), max(v.y for v in vs)],
        zs=[min(v.z for v in vs), max(v.z for v in vs)],
        area=(max(v.x for v in vs) - min(v.x for v in vs)) *
             (max(v.y for v in vs) - min(v.y for v in vs)),
        mats=[m.name for m in ob.data.materials if m],
        tris=len(ob.data.loop_triangles) if ob.data.loop_triangles else sum(
            max(0, len(p.vertices) - 2) for p in ob.data.polygons),
    ))

big = sorted(rows, key=lambda r: -r["area"])[:14]
print("PLATES", json.dumps([dict(name=r["name"], area=round(r["area"], 1),
                                 zs=[round(r["zs"][0], 4), round(r["zs"][1], 4)],
                                 ys=[round(r["ys"][0], 3), round(r["ys"][1], 3)],
                                 mats=r["mats"][:2]) for r in big]))

hi = [r for r in rows if r["zs"][1] > 0.05 and r["area"] > 20]
print("RAISED", json.dumps([dict(name=r["name"], area=round(r["area"], 1),
                                 zs=[round(r["zs"][0], 4), round(r["zs"][1], 4)],
                                 mats=r["mats"][:2]) for r in
                            sorted(hi, key=lambda r: -r["area"])[:12]]))

fences = [r for r in rows if any(k in r["name"] for k in
                                 ("fence", "bnd", "gate", "hedge"))]
print("FENCES", json.dumps([dict(name=r["name"], area=round(r["area"], 1),
                                 zs=[round(r["zs"][0], 3), round(r["zs"][1], 3)],
                                 tris=r["tris"]) for r in
                            sorted(fences, key=lambda r: -r["area"])[:10]]))

for m in bpy.data.materials:
    if not m.use_nodes:
        continue
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            c = n.inputs["Base Color"].default_value
            print("MATCOL", m.name,
                  "#%02x%02x%02x" % (int(c[0] * 255), int(c[1] * 255),
                                     int(c[2] * 255)))
            break
