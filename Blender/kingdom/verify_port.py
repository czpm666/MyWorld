"""Fresh-process FBX verification for the river port variants.

Run:  blender -b --factory-startup --python verify_port.py
Prints one PORTVERIFY json line per variant with object count, triangle count,
material count, overall bounding box, per-object detail and the imported root
transform (Unity expects loc 0, rot (270,0,0) -> i.e. 90 X in Blender terms,
scale 1) and writes port_verify.json next to the .blend files.
"""
import bpy
import os
import sys
import json

from mathutils import Vector

HERE = r"E:\My World\Blender"
EXPORT_DIR = os.path.join(HERE, "export", "kingdom", "port")
OUT_JSON = os.path.join(HERE, "kingdom", "port_verify.json")
VARIANTS = ["port_a", "port_b", "port_c"]


def measure(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    sc = bpy.context.scene
    meshes = [o for o in sc.objects if o.type == "MESH"]
    tris = 0
    polys = 0
    mats = set()
    verts = 0
    detail = {}
    mn = [1e18, 1e18, 1e18]
    mx = [-1e18, -1e18, -1e18]
    for o in meshes:
        o.data.calc_loop_triangles()
        t = len(o.data.loop_triangles)
        tris += t
        polys += len(o.data.polygons)
        verts += len(o.data.vertices)
        detail[o.name] = [len(o.data.polygons), t]
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
    # the terrain-plate contract: any object that is (or is named like) the
    # ground plate must not rise above grade
    plate = []
    for o in meshes:
        nm = o.name.lower()
        if any(k in nm for k in ("ground", "plate", "slab", "mole")):
            top = max((o.matrix_world @ Vector(c)).z for c in o.bound_box)
            plate.append(dict(name=o.name, max_z=round(top, 5),
                              ok=bool(top <= 0.001)))
    return dict(
        file=os.path.basename(path),
        bytes=os.path.getsize(path),
        objects=len(meshes),
        tris=tris,
        polys=polys,
        verts=verts,
        materials=len(mats),
        bbox=[round(v, 3) for v in (mn + mx)],
        size=[round(mx[i] - mn[i], 3) for i in range(3)],
        detail=detail,
        root=rt,
        plate_check=plate,
        mat_names=sorted(mats),
    )


def main():
    out = []
    for v in VARIANTS:
        p = os.path.join(EXPORT_DIR, v + ".fbx")
        if not os.path.exists(p):
            rec = dict(variant=v, error="missing")
        else:
            try:
                rec = measure(p)
                rec["variant"] = v
            except Exception as exc:
                rec = dict(variant=v, error=repr(exc))
        out.append(rec)
        rec2 = dict(rec)
        rec2.pop("mat_names", None)
        print("PORTVERIFY " + json.dumps(rec2))
    with open(OUT_JSON, "w") as fh:
        json.dump(out, fh, indent=1)
    print("PORTVERIFY wrote " + OUT_JSON)


if __name__ == "__main__":
    main()
