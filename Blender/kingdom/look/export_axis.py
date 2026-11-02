"""
Axis / scale self-check fixture for the Unity export pipeline.

Builds a deliberately chiral marker set in Blender, exports it through every
axis recipe we might use, and dumps the Blender-space ground truth to JSON so a
Unity-side probe can compare what actually arrives.

Markers (Blender space, metres):
  cube10      : 10x10x10 cube centred at origin         -> measures scale
  mx / my / mz: 2 m cubes at (+14,0,0) / (0,+14,0) / (0,0,+14)
                sizes 3 / 5 / 7 so a reflection or axis swap is unmistakable
  fwd         : cone apex pointing +Y at origin (r 2, depth 6), base at -Y
  up          : cone apex pointing +Z at (0,-14,0)

Variants written to <out>:
  axis_default.fbx   axis_forward='-Z', axis_up='Y', FBX_SCALE_NONE, space xform
  axis_bake.fbx      same + bake_space_transform=True
  axis_nospace.fbx   same + use_space_transform=False
  axis_yaw180.fbx    objects pre-multiplied by Euler(0,180,0)*Euler(-90,0,0)

Run:
  blender -b --factory-startup --python look/export_axis.py -- --out <dir>
"""
import bpy, os, sys, json, math
from mathutils import Vector, Euler, Matrix

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default

OUT = arg("--out", r"E:\My World\WorkQC\uexport\axis")
os.makedirs(OUT, exist_ok=True)


def log(*a):
    print("[AXIS]", *a)
    sys.stdout.flush()


# ---------------------------------------------------------------- clean scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0

mat = bpy.data.materials.new("probe_mat")
mat.use_nodes = True
mat.diffuse_color = (0.8, 0.2, 0.1, 1.0)


def add_box(name, loc, size):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = (size[0] * 0.5, size[1] * 0.5, size[2] * 0.5)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    return o


def add_cone(name, loc, rot, radius, depth):
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=radius, radius2=0.0,
                                    depth=depth, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    o.data.materials.append(mat)
    return o


D = math.radians
add_box("cube10", (0, 0, 0), (10, 10, 10))
add_box("mx", (14, 0, 0), (3, 3, 3))
add_box("my", (0, 14, 0), (5, 5, 5))
add_box("mz", (0, 0, 14), (7, 7, 7))
# Blender cones point +Z by default; rotate -90 about X to aim +Y
add_cone("fwd", (0, 0, 0), (D(-90), 0, 0), 2.0, 6.0)
add_cone("up", (0, -14, 0), (0, 0, 0), 2.0, 6.0)

objs = [o for o in bpy.data.objects if o.type == 'MESH']

# ---------------------------------------------------------------- ground truth
truth = {"blender_axis_convention": "Z-up, -Y forward",
         "markers": {}, "objects": {}}
for o in objs:
    mw = o.matrix_world
    cs = [mw @ Vector(c) for c in o.bound_box]
    mn = [min(c[i] for c in cs) for i in range(3)]
    mx = [max(c[i] for c in cs) for i in range(3)]
    truth["objects"][o.name] = {
        "min": [round(v, 4) for v in mn], "max": [round(v, 4) for v in mx],
        "center": [round((mn[i] + mx[i]) * 0.5, 4) for i in range(3)],
        "verts": len(o.data.vertices), "polys": len(o.data.polygons),
    }
truth["markers"] = {
    "cube10": "centred origin, 10^3", "mx": "+X 3 m at 14", "my": "+Y 5 m at 14",
    "mz": "+Z 7 m at 14", "fwd": "cone apex +Y (Blender forward)",
    "up": "cone apex +Z (Blender up), at y=-14",
}
truth["expected_unity_if_xz_neg_y"] = {
    "mx": [14, 0, 0], "my": [0, 0, -14], "mz": [0, 14, 0],
    "fwd_apex_dir": [0, 0, -1], "up_apex_dir": [0, 1, 0],
}
truth["expected_unity_if_yaw180"] = {
    "mx": [-14, 0, 0], "my": [0, 0, 14], "mz": [0, 14, 0],
    "fwd_apex_dir": [0, 0, 1], "up_apex_dir": [0, 1, 0],
}

BASE = dict(use_selection=False, use_visible=False, use_active_collection=False,
            global_scale=1.0, apply_unit_scale=False,
            apply_scale_options='FBX_SCALE_NONE',
            use_space_transform=True, bake_space_transform=False,
            object_types={'MESH'}, use_mesh_modifiers=True,
            mesh_smooth_type='OFF', colors_type='SRGB',
            prioritize_active_color=False, use_subsurf=False,
            use_mesh_edges=False, use_tspace=False, use_custom_props=False,
            bake_anim=False, path_mode='AUTO', embed_textures=False,
            use_triangles=True, use_metadata=False,
            axis_forward='-Z', axis_up='Y', add_leaf_bones=False,
            batch_mode='OFF')


def export(fname, **over):
    kw = dict(BASE)
    kw.update(over)
    fp = os.path.join(OUT, fname)
    bpy.ops.export_scene.fbx(filepath=fp, **kw)
    log("wrote", fname, os.path.getsize(fp), "bytes")
    return fp


export("axis_default.fbx")
export("axis_bake.fbx", bake_space_transform=True)
export("axis_nospace.fbx", use_space_transform=False)

# ---- variant from the brief: pre-multiply Euler(0,180,0)*Euler(-90,0,0)
M = (Euler((0.0, math.pi, 0.0), 'XYZ').to_matrix().to_4x4()
     @ Euler((math.radians(-90.0), 0.0, 0.0), 'XYZ').to_matrix().to_4x4())
for o in objs:
    o.matrix_world = M @ o.matrix_world
for o in bpy.context.view_layer.objects:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
truth["yaw180_matrix_rows"] = [[round(v, 4) for v in row] for row in M]
for o in objs:
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    truth.setdefault("objects_after_yaw180", {})[o.name] = {
        "min": [round(min(c[i] for c in cs), 4) for i in range(3)],
        "max": [round(max(c[i] for c in cs), 4) for i in range(3)],
    }
export("axis_yaw180.fbx")

with open(os.path.join(OUT, "blender_truth.json"), "w", encoding="utf-8") as f:
    json.dump(truth, f, indent=1)
log("truth ->", os.path.join(OUT, "blender_truth.json"))

# also keep the lab scene around for repeat runs
blend = os.path.join(OUT, "axis_probe.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
log("blend ->", blend)
log("AXIS DONE")

# ---------------------------------------------------------------------------
# --lab-run: continue straight into the lab scene and the full export in THIS
# Blender process.  The lock is the scarce resource in this project (six agents
# queue on it), so paying one acquisition for axis + lab + export is worth the
# slightly rude exec().
# ---------------------------------------------------------------------------
if "--lab-run" in sys.argv:
    lab = os.path.join(os.path.dirname(os.path.abspath(__file__)), "export_lab.py")
    lab_out = r"E:\My World\WorkQC\uexport\lab\out"
    # export_lab.py parses everything after a bare "--", so it must be there.
    sys.argv = ["blender", "-b", "--python", lab, "--",
                "--blend", r"E:\My World\WorkQC\uexport\lab\lab.blend",
                "--export", "--out", lab_out,
                "--chunk-tris", "50000", "--lod", "--collision",
                "--materials", "both", "--cell-size", "64"]
    log("chaining into", lab)
    with open(lab, "r", encoding="utf-8") as fh:
        _src = fh.read()
    exec(compile(_src, lab, "exec"), {"__name__": "__main__", "__file__": lab})

