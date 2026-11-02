"""Fresh-process FBX verification for the farm village variants.

Run:  blender -b --factory-startup --python verify_farm.py
Prints one FARMVERIFY json line per variant with object count, triangle count,
material count, overall bounding box and the imported root transform.
"""
import bpy
import os
import sys
import json

HERE = r"E:\My World\Blender"
EXPORT_DIR = os.path.join(HERE, "export", "kingdom", "farm")
VARIANTS = ["farm_a", "farm_b", "farm_c"]

from mathutils import Vector


def measure(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    sc = bpy.context.scene
    meshes = [o for o in sc.objects if o.type == "MESH"]
    tris = 0
    mats = set()
    verts = 0
    mn = [1e18, 1e18, 1e18]
    mx = [-1e18, -1e18, -1e18]
    for o in meshes:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
        verts += len(o.data.vertices)
        for ms in o.material_slots:
            if ms.material:
                mats.add(ms.material.name)
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], w[i])
                mx[i] = max(mx[i], w[i])
    roots = [o for o in sc.objects if o.parent is None]
    root = roots[0] if roots else None
    rt = None
    if root is not None:
        loc, rot, scl = root.matrix_world.decompose()
        rt = dict(name=root.name,
                  loc=[round(v, 4) for v in loc],
                  rot_deg=[round(v * 57.29578, 4) for v in rot.to_euler()],
                  scale=[round(v, 5) for v in scl])
    return dict(
        file=os.path.basename(path),
        bytes=os.path.getsize(path),
        objects=len(meshes),
        tris=tris,
        verts=verts,
        materials=len(mats),
        bbox=[round(v, 3) for v in (mn + mx)],
        size=[round(mx[i] - mn[i], 3) for i in range(3)],
        root=rt,
        mat_names=sorted(mats),
    )


def main():
    for v in VARIANTS:
        p = os.path.join(EXPORT_DIR, v + ".fbx")
        if not os.path.exists(p):
            print("FARMVERIFY " + json.dumps(dict(variant=v, error="missing")))
            continue
        try:
            d = measure(p)
            d["variant"] = v
            print("FARMVERIFY " + json.dumps(d))
        except Exception as exc:
            print("FARMVERIFY " + json.dumps(dict(variant=v, error=repr(exc))))


if __name__ == "__main__":
    main()
