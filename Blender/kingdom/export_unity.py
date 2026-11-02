#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
export_unity.py -- turn a Blender capital scene into Unity-ready FBX chunks.

The input is a procedurally built city (39 k objects / 30 M faces for v24, all
transforms identity, hard-surface flat-shaded geometry, no UVs).  Unity cannot
eat that as one asset and the materials are procedural node trees, so this
exporter does four things at once:

  * splits the world into spatial chunks small enough that every FBX is a
    single Unity mesh under the 65 535-vertex / 50 000-triangle budget,
  * keeps the material slots (so material *names* survive the import, which is
    what the Unity importer keys its palette / triplanar lookups on),
  * writes a manifest that describes every file in Unity space, and
  * optionally bakes each unique procedural material into 4 textures
    (BaseColor / Normal / Roughness+AO / Metallic) with a triplanar-friendly
    tile convention, so the shader can replay the Blender look without UVs.

USAGE (the contract the build script calls):

    blender -b <blend> --python export_unity.py -- \
        --out "E:\My World\Blender\export\capital_v2" \
        --chunk-tris 50000 --lod --collision --materials both

Other modes:

    ... --audit-only            # no export: inventory + classification report
    ... --materials json        # plan B only (material JSON, no textures)
    ... --materials baked       # plan A only (bakes, no JSON change: always written)
    ... --bake-only             # skip geometry, only (re)bake textures
    ... --axis-test <dir>       # write the 10 m cube axis/scale self-check FBX
    ... --dry-run               # plan + report, no files written

AXIS CONTRACT (measured, see Docs/AGENT_UEXPORT.md): the FBX is written with
`axis_forward='-Z', axis_up='Y'`, all object transforms applied and identity
node transforms, so Unity maps world position as

    unity = (b.x, b.z, -b.y)          # Blender Z-up -> Unity Y-up, no mirror

The manifest reports every bbox in *Unity* space using exactly that mapping, so
the importer never has to guess.  `--axis-test` writes the fixture that proves
it (10 m cube + chirality markers) and a JSON of the expected numbers.
"""
from __future__ import print_function

import bpy
import bmesh
import json
import math
import os
import re
import shutil
import sys
import time

import numpy as np
from mathutils import Vector

T0 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
LOOK = os.path.join(HERE, "look")

LOG_PATH = None


def log(*a):
    msg = " ".join(str(x) for x in a)
    line = "[EXP %8.1fs] %s" % (time.time() - T0, msg)
    print(line)
    sys.stdout.flush()
    if LOG_PATH:
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass


def warn(*a):
    msg = " ".join(str(x) for x in a)
    log("WARNING:", msg)
    WARNINGS.append(msg)


WARNINGS = []


# --------------------------------------------------------------------------- args
argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []


def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def flag(name):
    return name in argv


def farg(name, default):
    try:
        return float(arg(name, default))
    except (TypeError, ValueError):
        return float(default)


def iarg(name, default):
    try:
        return int(arg(name, default))
    except (TypeError, ValueError):
        return int(default)


BLEND = arg("--blend")                      # optional: usually already open (-b file)
OUT = arg("--out") or os.path.join(r"E:\My World\Blender\export", "capital_v2")
CHUNK_TRIS = iarg("--chunk-tris", 50000)
VERT_CAP = iarg("--vert-cap", 65535)
CELL = arg("--cell-size", "64")             # metres, or "auto"
TARGET_CHUNKS = iarg("--target-chunks", 700)
LOD_ON = flag("--lod")
LOD_RATIO = [float(x) for x in arg("--lod-ratio", "0.5,0.15").split(",") if x.strip()]
COL_ON = flag("--collision")
COL_RATIO = farg("--col-ratio", 0.10)
COL_MIN_TRIS = iarg("--col-min-tris", 64)
COL_CATS = [s.strip() for s in arg("--col-categories", "terrain,walls").split(",") if s.strip()]
MATERIALS = (arg("--materials", "json") or "json").lower()   # json | baked | both | none
BAKE_TOP = iarg("--bake-top", 0)            # 0 = all unique materials
BAKE_RES = iarg("--bake-res", 1024)
BAKE_AO_SAMPLES = iarg("--bake-ao-samples", 48)
TILE_M = farg("--tile-m", 4.0)
AUDIT_ONLY = flag("--audit-only")
DRY_RUN = flag("--dry-run")
BAKE_ONLY = flag("--bake-only")
NO_CLEAN = flag("--no-clean")
SKIP_HIDDEN = not flag("--include-hidden")
LANDMARK_KEYS = [s.strip().lower() for s in
                 arg("--landmarks", "castle,cathedral,guild,market,gate").split(",") if s.strip()]
CLASSIFY_JSON = arg("--classify")
VERIFY = (arg("--verify", "all") or "all").lower()     # all | sample | none
CELL_MAX = iarg("--cell-max-objects", 400)
KEEP_WORKING = flag("--keep-scratch")
AXIS_TEST_DIR = arg("--axis-test")

FBX_SETTINGS = dict(
    use_selection=True,
    use_visible=False,
    use_active_collection=False,
    global_scale=1.0,
    apply_unit_scale=False,
    apply_scale_options='FBX_SCALE_NONE',
    use_space_transform=True,
    bake_space_transform=False,
    object_types={'MESH'},
    use_mesh_modifiers=False,        # we apply them ourselves, exactly once
    mesh_smooth_type='OFF',
    colors_type='SRGB',
    prioritize_active_color=False,
    use_subsurf=False,
    use_mesh_edges=False,
    use_tspace=False,
    use_custom_props=False,
    bake_anim=False,
    path_mode='AUTO',
    embed_textures=False,
    use_triangles=True,
    use_metadata=False,
    axis_forward='-Z',
    axis_up='Y',
    add_leaf_bones=False,
    batch_mode='OFF',
)


def fbx_kwargs(extra=None):
    """Only pass properties this Blender actually has (guards API drift)."""
    d = dict(FBX_SETTINGS)
    if extra:
        d.update(extra)
    try:
        props = set(bpy.ops.export_scene.fbx.get_rna_type().properties.keys())
    except Exception:
        return d
    out, dropped = {}, []
    for k, v in d.items():
        if k in props:
            out[k] = v
        else:
            dropped.append(k)
    if dropped:
        warn("FBX settings not present in this Blender, ignored: %s" % dropped)
    return out


# --------------------------------------------------------------------------- memory
def proc_mem_mb():
    """Working set of this process, in MB (Windows ctypes; -1 if unavailable)."""
    try:
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = wt.HANDLE     # -1 truncates to 32 bit
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE,
                                               ctypes.POINTER(PMC),
                                               wt.DWORD]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(),
                                          ctypes.byref(pmc), pmc.cb):
            return -1.0
        return pmc.WorkingSetSize / 1e6
    except Exception:
        return -1.0


MEM_PEAK = [0.0]


def sample_mem():
    m = proc_mem_mb()
    if m > MEM_PEAK[0]:
        MEM_PEAK[0] = m
    return m


# --------------------------------------------------------------------------- misc
def safe_name(s, maxlen=80):
    s = re.sub(r"[^A-Za-z0-9_.+-]+", "_", s or "")
    s = s.strip("._") or "x"
    return s[:maxlen]


def mesh_counts(me):
    """(triangles, verts) for a mesh, exact for tris via loop totals."""
    npoly = len(me.polygons)
    if npoly == 0:
        return 0, len(me.vertices)
    lt = np.empty(npoly, dtype=np.int32)
    me.polygons.foreach_get("loop_total", lt)
    return int((lt - 2).sum()), len(me.vertices)


def mesh_corner_stats(me):
    """(tris, verts, corners, smooth_face_fraction)."""
    npoly = len(me.polygons)
    if npoly == 0:
        return 0, len(me.vertices), 0, 0.0
    lt = np.empty(npoly, dtype=np.int32)
    me.polygons.foreach_get("loop_total", lt)
    sm = np.empty(npoly, dtype=bool)
    try:
        me.polygons.foreach_get("use_smooth", sm)
    except Exception:
        sm[:] = False
    return (int((lt - 2).sum()), len(me.vertices), int(lt.sum()),
            float(sm.mean()) if npoly else 0.0)


def export_vert_estimate(me):
    """Vertices Unity will see: unique (position, normal) pairs.

    Flat-shaded hard-surface geometry splits every face corner, so a 50 k-tri
    box chunk is not 25 k vertices but ~120 k.  This is measured, not assumed.
    """
    nloops = len(me.loops)
    if nloops == 0:
        return 0
    if len(me.vertices) == 0:
        return 0
    try:
        pos = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get("co", pos)
        vidx = np.empty(nloops, dtype=np.int32)
        me.loops.foreach_get("vertex_index", vidx)
        nrm = np.empty(nloops * 3, dtype=np.float32)
        me.corner_normals.foreach_get("vector", nrm)
    except Exception:
        return 3 * len(me.polygons)
    P = np.rint(pos.reshape(-1, 3) * 1000.0).astype(np.int64)[vidx]
    N = np.rint(nrm.reshape(-1, 3) * 64.0).astype(np.int64)
    arr = np.ascontiguousarray(np.concatenate([P, N], axis=1))
    try:
        view = arr.view([('', arr.dtype)] * 6).ravel()
        return int(len(np.unique(view)))
    except Exception:
        return 3 * len(me.polygons)


def box_world(obj):
    """World-space AABB of an object's evaluated-ish mesh (8 corners)."""
    mw = obj.matrix_world
    xs, ys, zs = [], [], []
    for c in obj.bound_box:
        v = mw @ Vector(c)
        xs.append(v.x)
        ys.append(v.y)
        zs.append(v.z)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def b_union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return ((min(a[0][0], b[0][0]), min(a[0][1], b[0][1]), min(a[0][2], b[0][2])),
            (max(a[1][0], b[1][0]), max(a[1][1], b[1][1]), max(a[1][2], b[1][2])))


def unity_box(bx):
    """Blender AABB -> Unity AABB under unity = (x, z, -y)."""
    if bx is None:
        return None
    (x0, y0, z0), (x1, y1, z1) = bx
    return ((round(x0, 4), round(z0, 4), round(-y1, 4)),
            (round(x1, 4), round(z1, 4), round(-y0, 4)))


def r4(v):
    return [round(float(x), 4) for x in v]


# --------------------------------------------------------------------------- scene
def prepare_scene():
    """Make every mesh object visible/selectable so ops and joins work."""
    vl = bpy.context.view_layer
    n_ex = 0

    def walk(lc):
        nonlocal n_ex
        try:
            if lc.exclude:
                lc.exclude = False
                n_ex += 1
        except Exception:
            pass
        for c in lc.children:
            walk(c)

    walk(vl.layer_collection)
    if n_ex:
        log("re-enabled %d excluded collections" % n_ex)
    hid = 0
    for o in bpy.data.objects:
        try:
            if o.hide_viewport:
                o.hide_viewport = False
                hid += 1
        except Exception:
            pass
        try:
            o.hide_set(False)
        except Exception:
            pass
    if hid:
        log("un-hid %d viewport-hidden objects" % hid)
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def unit_scale_of_scene():
    try:
        return float(bpy.context.scene.unit_settings.scale_length)
    except Exception:
        return 1.0


# --------------------------------------------------------------------------- classify
KEYWORDS = [
    # (regex, category, landmark key or None)
    # NOTE: no \b before "castl"/"gate" — joined landmark objects are named
    # ars_castle / ars_gate, and "_" is a word character so \b never fires there.
    (r"castl|donjon|bailey|barbican|keep_|portcullis|postern|curtain", "landmark", "castle"),
    (r"cathedral|nave|transept|apse|cloister|belfry|spire|buttress_?church|rose_?window", "landmark", "cathedral"),
    (r"guild", "landmark", "guild"),
    (r"market|stall|bazaar|awning_?row", "landmark", "market"),
    (r"gate|drawbridge|ogate", "landmark", "gate"),
    # streetlife_<cx>_<cy> chunks are 7.2M tris of props; they must be caught
    # BEFORE the road/street rule below, which would otherwise file them as terrain.
    (r"street_?life", "props", None),
    (r"wall|rampart|battlement|merlon|crenel|parapet|hoarding|enceinte|curtain|quay_?wall", "walls", None),
    (r"terrain|landscape|land_|ground|heightfield|hill|plateau|river|water|sea_|pond|shoreline|cliff", "terrain", None),
    (r"road|street|lane|avenue|plaza|square|cobble|paving|pavement|kerb|curb|flag_?stone|bridge|quay|dock|pier|harbour|harbor", "terrain", None),
    (r"field|farm|crop|wheat|orchard|pasture|meadow|grass_?patch|hedge|vinyard", "terrain", None),
    (r"prop|street_?life|streetlife|lantern|barrel|crate|cart|bench|well|fountain|statue|sign|banner|flag_?pole|fence|bucket|sack|hay|trough|firewood|pot|amphora|table|chair|wheelbarrow|stall_?goods|vine|ivy|bush|shrub|flower|tree|crowd|npc|boat|ship|skiff|barge", "props", None),
    (r"house|shop|tavern|inn|smith|bakery|butcher|tannery|warehouse|barn|home|dwelling|tenement|chimney|roof_?house|city|row_?house|plot|block", "city", None),
]

COLLECTION_KEYWORDS = list(KEYWORDS)

DEFAULT_CATEGORY = "city"


def load_classify_overrides(path):
    """JSON: {"rules":[{"match":"prefix","category":"city|props|walls|terrain|landmark:castle"}],
              "exact":{"object name":"category"}}"""
    if not path or not os.path.exists(path):
        return [], {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        rules = [(r["match"].lower(), r["category"].lower()) for r in d.get("rules", [])]
        exact = {k: v.lower() for k, v in d.get("exact", {}).items()}
        log("classify overrides:", len(rules), "rules,", len(exact), "exact")
        return rules, exact
    except Exception as exc:
        warn("classify json unreadable: %s" % exc)
        return [], {}


OVERRIDE_RULES, OVERRIDE_EXACT = load_classify_overrides(CLASSIFY_JSON)


def category_from_token(cat, lm=None):
    cat = (cat or "").lower()
    if cat.startswith("landmark"):
        if ":" in cat:
            return "landmark", cat.split(":", 1)[1]
        return "landmark", (lm or "misc")
    if cat in ("city", "props", "walls", "terrain", "other"):
        return cat, None
    return DEFAULT_CATEGORY, None


def classify(name, colnames, bx, tris):
    """-> (category, landmark_key, reason).  Priority: exact > collection > name > geometry."""
    low = (name or "").lower()
    if low in OVERRIDE_EXACT:
        c, lm = category_from_token(OVERRIDE_EXACT[low])
        return c, lm, "override-exact"
    for pat, cat in OVERRIDE_RULES:
        if pat in low:
            c, lm = category_from_token(cat)
            return c, lm, "override-rule:" + pat

    for cn in colnames:
        cl = (cn or "").lower()
        for pat, cat, lm in COLLECTION_KEYWORDS:
            if re.search(pat, cl):
                c, lmk = category_from_token(cat, lm)
                return c, lmk, "collection:" + cn

    for pat, cat, lm in KEYWORDS:
        if re.search(pat, low):
            c, lmk = category_from_token(cat, lm)
            return c, lmk, "name:" + pat

    # ---- geometry fallback (no name hint): still try to be sensible
    if bx is not None:
        (x0, y0, z0), (x1, y1, z1) = bx
        sx, sy, sz = max(1e-6, x1 - x0), max(1e-6, y1 - y0), max(1e-6, z1 - z0)
        area = sx * sy
        diag = math.sqrt(sx * sx + sy * sy + sz * sz)
        if area > 20000.0 and sz < 12.0:
            return "terrain", None, "geom:large-flat"
        if max(sx, sy) > 6.0 * min(sx, sy) and sz > 1.2 and max(sx, sy) > 8.0:
            return "walls", None, "geom:long-thin"
        if diag < 2.5:
            return "props", None, "geom:small"
        if diag > 30.0 and area > 400.0:
            return "terrain", None, "geom:big-ground"
    return DEFAULT_CATEGORY, None, "default"


# --------------------------------------------------------------------------- plan
def plan_chunks(items, cell, max_tris, vert_cap, prefix="chunk", cell_max=None):
    """Spatial grid -> chunk list honouring the tri and vertex budget.

    items: [{"name","tris","vest","cen","bx"}]  ->  [{"name","cell","items"}]
    A cell that does not fit becomes chunk_<cx>_<cy> then _p01, _p02, ...
    """
    cells = {}
    for it in items:
        cx = int(math.floor(it["cen"][0] / cell))
        cy = int(math.floor(it["cen"][1] / cell))
        cells.setdefault((cx, cy), []).append(it)

    out = []
    for cellkey in sorted(cells.keys(), key=lambda k: (k[1], k[0])):
        group = cells[cellkey]
        group.sort(key=lambda it: (round(it["cen"][1], 3), round(it["cen"][0], 3)))
        parts = []
        cur, ct, cv = [], 0, 0
        for it in group:
            over = cur and (ct + it["tris"] > max_tris or cv + it["vest"] > vert_cap)
            full = cell_max and len(cur) >= cell_max
            if over or full:
                parts.append(cur)
                cur, ct, cv = [], 0, 0
            cur.append(it)
            ct += it["tris"]
            cv += it["vest"]
        if cur:
            parts.append(cur)
        cx, cy = cellkey
        for k, part in enumerate(parts):
            nm = "%s_%d_%d" % (prefix, cx, cy) if k == 0 else \
                 "%s_%d_%d_p%02d" % (prefix, cx, cy, k)
            out.append({"name": nm, "cell": [cx, cy], "part": k, "items": part})
    out.sort(key=lambda c: (c["cell"][1], c["cell"][0], c["part"]))
    return out


def auto_cell(cat_items, target):
    allbx = None
    for it in cat_items:
        allbx = b_union(allbx, it["bx"])
    if allbx is None:
        return 64.0
    (x0, y0, _), (x1, y1, _) = allbx
    area = max(1.0, (x1 - x0) * (y1 - y0))
    cell = math.sqrt(area / max(1.0, target))
    cell = max(8.0, min(512.0, round(cell / 8.0) * 8.0))
    log("auto cell size: area %.0f m2, target %d chunks -> %.0f m" % (area, target, cell))
    return cell


# --------------------------------------------------------------------------- mesh ops
def select_only(objs):
    for o in tuple(bpy.context.selected_objects):
        try:
            o.select_set(False)
        except Exception:
            pass
    for o in objs:
        try:
            o.select_set(True)
        except Exception:
            pass
    bpy.context.view_layer.objects.active = objs[0] if objs else None


def apply_modifiers_bulk(objs):
    """Apply modifiers with one depsgraph evaluation (fast, no ops)."""
    todo = [o for o in objs if len(o.modifiers) > 0]
    if not todo:
        return 0
    dg = bpy.context.evaluated_depsgraph_get()
    done = 0
    for o in todo:
        try:
            ev = o.evaluated_get(dg)
            me = bpy.data.meshes.new_from_object(
                ev, preserve_all_data_layers=True, depsgraph=dg)
        except Exception as exc:
            warn("modifier apply failed on %s: %s" % (o.name, exc))
            continue
        old = o.data
        o.modifiers.clear()
        o.data = me
        me.name = safe_name(o.name) + "_mesh"
        done += 1
        if old.users == 0:
            try:
                bpy.data.meshes.remove(old)
            except Exception:
                pass
    return done


def join_group(objs, name):
    """Join into a single mesh object, world-space geometry, identity transform."""
    select_only(objs)
    if len(objs) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    if obj.data is not None:
        obj.data.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def link_object(dup):
    """Link a copied object into the scene.

    NOTE: `bpy.context.view_layer.objects` is a *view* collection with no
    .link() -- the 2026-11-02 lab run failed every LOD and collision mesh with
    `bpy_prop_collection: attribute "link" not found` because of that.  Use the
    scene's master collection.
    """
    bpy.context.scene.collection.objects.link(dup)
    return dup


def decimate_copy(src, ratio, name):
    dup = src.copy()
    dup.data = src.data.copy()
    dup.name = name
    dup.data.name = name
    link_object(dup)
    if ratio < 0.999:
        mod = dup.modifiers.new("dec", 'DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = max(0.001, min(1.0, ratio))
        mod.use_collapse_triangulate = True
        select_only([dup])
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return dup


def weld_and_decimate_copy(src, ratio, name):
    """Collision grade: weld the seams first, then collapse hard."""
    dup = src.copy()
    dup.data = src.data.copy()
    dup.name = name
    dup.data.name = name
    link_object(dup)
    select_only([dup])
    w = dup.modifiers.new("weld", 'WELD')
    w.merge_threshold = 0.001
    dup.modifiers.new("tri", 'TRIANGULATE')
    if ratio < 0.999:
        d = dup.modifiers.new("dec", 'DECIMATE')
        d.decimate_type = 'COLLAPSE'
        d.ratio = max(0.001, min(1.0, ratio))
        d.use_collapse_triangulate = True
    for m in list(dup.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    return dup


def drop(objs):
    """Remove objects and any mesh they leave orphaned (tolerates stale refs)."""
    for o in objs:
        try:
            me = o.data
        except ReferenceError:
            continue
        try:
            bpy.data.objects.remove(o, do_unlink=True)
        except Exception:
            pass
        if me is not None and me.users == 0:
            try:
                bpy.data.meshes.remove(me)
            except Exception:
                pass


def purge():
    try:
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    except Exception:
        pass


def export_obj(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    select_only([obj])
    bpy.ops.export_scene.fbx(filepath=path, **fbx_kwargs())
    return os.path.getsize(path)


def split_object(obj, axis, coord, suffix):
    """Bisect a too-large mesh at a world coordinate. Returns [low, high] objects."""
    me = obj.data
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    keep_low = co[:, axis] <= coord
    out = []
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    for side, mask in ((0, keep_low), (1, ~keep_low)):
        bm2 = bmesh.new()
        bm2.from_mesh(me)
        bm2.verts.ensure_lookup_table()
        bm2.faces.ensure_lookup_table()
        kill = [f for f in bm2.faces
                if not all(bool(mask[v.index]) for v in f.verts)]
        if kill:
            bmesh.ops.delete(bm2, geom=kill, context='FACES')
        newme = bpy.data.meshes.new(me.name + "_%s%d" % (suffix, side))
        bm2.to_mesh(newme)
        bm2.free()
        if len(newme.polygons) == 0:
            bpy.data.meshes.remove(newme)
            continue
        nobj = bpy.data.objects.new(newme.name, newme)
        bpy.context.scene.collection.objects.link(nobj)
        out.append(nobj)
    bm.free()
    drop([obj])
    return out


def split_until_fits(obj, vert_cap, tri_cap, name, max_parts=16):
    """Bisect until every piece is inside the Unity mesh budget."""
    out, queue, guard = [], [obj], 0
    while queue and guard < 64:
        ob = queue.pop(0)
        guard += 1
        t_, v_ = mesh_counts(ob.data)
        ve_ = export_vert_estimate(ob.data)
        if v_ <= vert_cap and t_ <= tri_cap:
            out.append(ob)
            continue
        if len(out) + len(queue) >= max_parts:
            warn("%s: staying over budget (%d tris, %d est verts) at the %d-part limit"
                 % (name, t_, ve_, max_parts))
            out.append(ob)
            continue
        bx = box_world(ob)
        axis = 0 if (bx[1][0] - bx[0][0]) >= (bx[1][1] - bx[0][1]) else 1
        halves = split_object(ob, axis, (bx[0][axis] + bx[1][axis]) * 0.5, "v")
        if len(halves) < 2:
            warn("%s: cannot split further (%d tris, %d est verts)" % (name, t_, ve_))
            out.append(ob)
            continue
        queue.extend(halves)
    return out or [obj]


# --------------------------------------------------------------------------- materials
KIT_RULES = [
    # (regex, kit name, suggested metres per tile) -- mirrors
    # Assets/Editor/KingdomMaterialDetail.cs so plan B reproduces the existing look
    (r"cobble|paving|flag|plaza|lane|street|road", "kit_cobble", 3.4),
    (r"stone|ashlar|riser|kerb|curb|step|boulder|rock|cliff|quay|dock|plinth|"
     r"dressed|slab|coping|wall_cap|granite|marble", "kit_stone_wall", 2.2),
    (r"roof|tile|slate|shingle", "kit_roof_tile", 3.0),
    (r"thatch|straw", "kit_thatch", 2.6),
    (r"wood|plank|fence|door|frame|beam|trunk|bark|timber|board|log", "kit_planks", 0.9),
    (r"plaster|stucco|daub|wall", "kit_plaster", 3.0),
    (r"earth|soil|dirt|gravel|mud|sand|yard|field|terra|clay|path", "kit_dirt", 3.0),
    (r"grass|leaf|pasture|moss|hedge|crop|wheat|pine|foliage|tree|bush|ivy", "kit_grass", 3.0),
    (r"cloth|banner|awning|sail|canvas|fabric|wool", "kit_plaster", 1.2),
    (r"brick|terracotta", "kit_brick", 1.4),
    (r"metal|iron|steel|bronze|gold|brass|copper|lead|tin", "kit_metal", 1.0),
    (r"glass|window", "kit_glass", 1.0),
    (r"water|river|sea|lake", "kit_water", 6.0),
]


def kit_hint(name):
    low = (name or "").lower()
    for pat, kit, tile in KIT_RULES:
        if re.search(pat, low):
            return kit, tile
    return "kit_stone_wall", 2.2


def principled_of(mat):
    if not mat or not mat.use_nodes or mat.node_tree is None:
        return None
    for n in mat.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return None


def lin_to_srgb_hex(c):
    out = []
    for v in c[:3]:
        v = max(0.0, min(1.0, float(v)))
        s = 12.92 * v if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055
        out.append(int(round(max(0.0, min(1.0, s)) * 255)))
    return "#%02x%02x%02x" % tuple(out)


def material_info(mat):
    """Everything Unity needs to rebuild this material without Blender."""
    bsdf = principled_of(mat)
    base = [0.8, 0.8, 0.8, 1.0]
    rough, metal = 0.62, 0.0
    emis = [0.0, 0.0, 0.0]
    linked = {}
    if bsdf is not None:
        bc = bsdf.inputs.get("Base Color")
        if bc is not None:
            if bc.is_linked:
                linked["base"] = bc.links[0].from_node.type
            else:
                base = list(bc.default_value)
        ri = bsdf.inputs.get("Roughness")
        if ri is not None:
            if ri.is_linked:
                linked["rough"] = ri.links[0].from_node.type
            else:
                rough = float(ri.default_value)
        mi = bsdf.inputs.get("Metallic")
        if mi is not None:
            if mi.is_linked:
                linked["metal"] = mi.links[0].from_node.type
            else:
                metal = float(mi.default_value)
        ei = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        es = bsdf.inputs.get("Emission Strength")
        if ei is not None and not ei.is_linked:
            st = 1.0
            if es is not None and not es.is_linked:
                st = float(es.default_value)
            emis = [float(ei.default_value[0]) * st, float(ei.default_value[1]) * st,
                    float(ei.default_value[2]) * st]
    if bsdf is None:
        base = list(mat.diffuse_color) if mat else base
    kit, tile = kit_hint(mat.name)
    return {
        "name": mat.name,
        "key": safe_name(re.sub(r"\.\d+$", "", mat.name)),
        "base_rgb_linear": [round(float(x), 5) for x in base],
        "base_hex_srgb": lin_to_srgb_hex(base),
        "rough": round(rough, 4),
        "metal": round(metal, 4),
        "emis_linear": [round(float(x), 5) for x in emis],
        "linked": linked,
        "node_count": len(mat.node_tree.nodes) if (mat and mat.use_nodes and mat.node_tree) else 0,
        "kit": kit,
        "kit_tile_m": tile,
        "use_nodes": bool(mat and mat.use_nodes),
    }


def material_signature(mat):
    """Cheap structural fingerprint so near-duplicate materials bake once."""
    if not mat or not mat.use_nodes or mat.node_tree is None:
        return "nonode:" + (mat.name if mat else "?")
    parts = []
    for n in sorted(mat.node_tree.nodes, key=lambda n: (n.type, n.name)):
        bits = [n.type]
        for key in ("Scale", "Detail", "Roughness", "Brick Width", "Row Height",
                    "Mortar Size", "Base Color", "Strength", "Distance"):
            s = n.inputs.get(key) if hasattr(n, "inputs") else None
            if s is None:
                continue
            try:
                if not s.is_linked:
                    v = s.default_value
                    bits.append("%s=%s" % (key, [round(float(x), 4) for x in v]
                                           if hasattr(v, "__len__") else round(float(v), 4)))
            except Exception:
                pass
        parts.append("|".join(str(b) for b in bits))
    return "%.0f:%s" % (len(mat.node_tree.nodes), "#".join(parts))


# --------------------------------------------------------------------------- bake
def bake_materials(mat_infos, out_dir, res, tile_m, top, ao_samples):
    """Plan A: bake each unique material to base/normal/ra/metal tiles."""
    import bpy as _bpy

    tex_root = os.path.join(out_dir, "textures")
    os.makedirs(tex_root, exist_ok=True)

    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    try:
        scene.cycles.device = 'CPU'
        scene.cycles.use_denoising = False
    except Exception:
        pass
    scene.render.bake.margin = 6
    scene.render.bake.use_clear = True
    scene.render.bake.use_selected_to_active = False

    # an isolated plane in a scratch scene: AO must not see the city
    #
    # The materials MUST survive this wipe: orphans_purge() would delete every
    # material the moment the last object holding it is removed (measured: the
    # 2026-11-02 lab run logged "baking 6 unique materials" and then "baked 0
    # materials", because purge had already freed all six).  Fake users pin
    # them, and no purge runs here at all.
    keep_mats = [m for m in bpy.data.materials]
    for m in keep_mats:
        m.use_fake_user = True
    for o in list(bpy.data.objects):
        try:
            bpy.data.objects.remove(o, do_unlink=True)
        except Exception:
            pass
    for me in list(bpy.data.meshes):
        if me.users == 0:
            try:
                bpy.data.meshes.remove(me)
            except Exception:
                pass

    # The plane must sit so that its Object coordinates run 0..tile_m, because
    # the Unity side replays the tile as p = positionWS / tile_m with no offset
    # (`_BaseMap_ST.zw` is fixed at (0,0) in TriplanarLit).  A plane centred on
    # the origin would band the pattern half a tile away from where world 0 is.
    bpy.ops.mesh.primitive_plane_add(size=tile_m,
                                     location=(tile_m * 0.5, tile_m * 0.5, 0.0))
    plane = bpy.context.object
    plane.name = "bake_plane"
    if not plane.data.uv_layers:
        plane.data.uv_layers.new(name="UVMap")

    def new_image(name, colorspace):
        img = bpy.data.images.new(name, res, res, alpha=False, float_buffer=False)
        img.colorspace_settings.name = colorspace
        return img

    def bake_to(mat, img, btype, **kw):
        nt = mat.node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        node.label = "UEXPORT_BAKE"
        node.location = (-1200, 800)
        for n in nt.nodes:
            n.select = False
        node.select = True
        nt.nodes.active = node
        plane.data.materials.clear()
        plane.data.materials.append(mat)
        select_only([plane])
        # The pass toggles belong to the SCENE bake settings, not to the operator:
        # `bpy.ops.object.bake(..., use_pass_direct=False)` dies with
        # "keyword \"use_pass_direct\" unrecognized" in 5.2 (measured).
        bk = bpy.context.scene.render.bake
        for attr, val in (("use_pass_direct", False), ("use_pass_indirect", False),
                          ("use_pass_color", True)):
            if hasattr(bk, attr):
                try:
                    setattr(bk, attr, val)
                except Exception:
                    pass
        bpy.ops.object.bake(type=btype, **kw)
        nt.nodes.remove(node)
        return img

    def save(img, path, non_color=True):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.filepath_raw = path
        img.file_format = 'PNG'
        if non_color:
            img.colorspace_settings.name = 'Non-Color'
        img.save()
        bpy.data.images.remove(img)
        return os.path.getsize(path)

    def image_pixels(img):
        buf = np.empty(res * res * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        return buf.reshape(res, res, 4)

    def png_mean_linear(path):
        """Average albedo of a saved PNG, in linear RGB.

        Read the file back through Blender with colorspace 'Non-Color': that is
        the one mode where `pixels` hands back byte/255 with no transform, so the
        sRGB->linear conversion is done here, explicitly, instead of hoping the
        colour management of an 'sRGB' image buffer does what we think (it does
        not always: `pixels` on an 8-bit sRGB image is already converted, on a
        Non-Color one it is not).
        """
        try:
            chk = bpy.data.images.load(path, check_existing=False)
            chk.colorspace_settings.name = 'Non-Color'
            buf = np.empty(chk.size[0] * chk.size[1] * 4, dtype=np.float32)
            chk.pixels.foreach_get(buf)
            px = buf.reshape(-1, 4)[:, :3].astype(np.float64)
            bpy.data.images.remove(chk)
        except Exception as exc:
            warn("base mean failed for %s: %s" % (path, exc))
            return None
        lin = np.where(px <= 0.04045, px / 12.92, ((px + 0.055) / 1.055) ** 2.4)
        mean = lin.mean(axis=0)
        return [round(float(v), 4) for v in mean]

    def lineartosrgb(v):
        return v * 12.92 if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055

    results = {}
    n_done = 0
    t_bake = time.time()
    for i, mi in enumerate(mat_infos):
        mat = bpy.data.materials.get(mi["name"])
        if mat is None or not mat.use_nodes:
            warn("bake: material %r vanished (found=%s use_nodes=%s)"
                 % (mi["name"], mat is not None, getattr(mat, "use_nodes", None)))
            continue
        d = os.path.join(tex_root, mi["bake_key"])
        os.makedirs(d, exist_ok=True)
        entry = {"dir": os.path.relpath(d, out_dir).replace("\\", "/"),
                 "tile_m": tile_m, "res": res}
        tb = time.time()
        try:
            # --- base colour: pure albedo, no direct/indirect light
            img = new_image("uex_base", 'sRGB')
            bake_to(mat, img, 'DIFFUSE', pass_filter={'COLOR'})
            entry["base"] = "base.png"
            entry["base_bytes"] = save(img, os.path.join(d, "base.png"), non_color=False)
            # The mean of the baked albedo is what plan B should put in
            # _BaseColor: replaying a kit texture tinted by the *node default*
            # grey is how the first lab pass came out pale (#e7e7e7 for a cobble
            # material whose real albedo is dark).
            mean_lin = png_mean_linear(os.path.join(d, "base.png"))
            if mean_lin:
                entry["base_rgb_mean_linear"] = mean_lin
                entry["base_hex_mean_srgb"] = "#%02x%02x%02x" % tuple(
                    max(0, min(255, int(round(lineartosrgb(v) * 255)))) for v in mean_lin)
            base_px = None

            # --- normal (tangent space, includes the material's bump chain)
            img = new_image("uex_nrm", 'Non-Color')
            bake_to(mat, img, 'NORMAL', normal_space='TANGENT')
            entry["normal"] = "normal.png"
            entry["normal_bytes"] = save(img, os.path.join(d, "normal.png"))

            # --- roughness (R) + occlusion (G), packed.
            # AO is NOT baked: ambient occlusion is a function of the surrounding
            # geometry, and this bake sees a single isolated plane, so every AO
            # sample would read 1.0 -- a fake channel that looks like data.  Real
            # AO has to be baked per chunk against the city, which needs UVs the
            # chunks do not have (triplanar only).  G stays 1.0 and the manifest
            # says so; a future importer can fill it from a chunk-space bake.
            scene.cycles.samples = max(1, int(ao_samples / 4))
            img = new_image("uex_rough", 'Non-Color')
            bake_to(mat, img, 'ROUGHNESS')
            rough_px = image_pixels(img)
            bpy.data.images.remove(img)

            packed = np.empty((res, res, 4), dtype=np.float32)
            packed[..., 0] = rough_px[..., 0]
            packed[..., 1] = 1.0
            packed[..., 2] = 0.0
            packed[..., 3] = 1.0
            img = bpy.data.images.new("uex_ra", res, res, alpha=False)
            img.colorspace_settings.name = 'Non-Color'
            img.pixels.foreach_set(packed.ravel())
            entry["ra"] = "ra.png"
            entry["ra_bytes"] = save(img, os.path.join(d, "ra.png"))
            entry["rough_mean"] = round(float(packed[..., 0].mean()), 4)
            entry["ao_mean"] = 1.0
            entry["ao_note"] = "not baked: AO needs the chunk geometry, see AGENT_UEXPORT.md"

            # --- metallic via an emission swap (no native metallic bake)
            scene.cycles.samples = 1
            dup = mat.copy()
            dup.name = mat.name + "_uex_emit"
            nt = dup.node_tree
            out = None
            for n in nt.nodes:
                if n.type == 'OUTPUT_MATERIAL':
                    out = n
                    break
            src = None
            m_in = None
            bsdf = principled_of(dup)
            if bsdf is not None:
                m_in = bsdf.inputs.get("Metallic")
                if m_in is not None and m_in.is_linked:
                    src = m_in.links[0].from_socket
            emit = nt.nodes.new("ShaderNodeEmission")
            emit.inputs["Strength"].default_value = 1.0
            if src is not None:
                nt.links.new(src, emit.inputs["Color"])
            elif m_in is not None:
                v = 0.0 if m_in.is_linked else float(m_in.default_value)
                emit.inputs["Color"].default_value = (v, v, v, 1.0)
            if out is not None:
                nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
            img = new_image("uex_metal", 'Non-Color')
            bake_to(dup, img, 'EMIT')
            entry["metal"] = "metal.png"
            entry["metal_bytes"] = save(img, os.path.join(d, "metal.png"))
            bpy.data.materials.remove(dup)

            entry["seconds"] = round(time.time() - tb, 2)
            results[mi["name"]] = entry
            n_done += 1
            if n_done <= 8 or n_done % 10 == 0:
                log("  baked %d/%d %-24s %.2fs (base %.0f KB, total so far %.0f s)"
                    % (n_done, len(mat_infos), mi["name"], entry["seconds"],
                       entry["base_bytes"] / 1e3, time.time() - t_bake))
        except Exception as exc:
            import traceback
            traceback.print_exc()
            warn("bake failed for %s: %s" % (mi["name"], exc))
        sample_mem()
    log("baked %d materials in %.1f s" % (n_done, time.time() - t_bake))
    try:
        bpy.data.objects.remove(plane, do_unlink=True)
    except Exception:
        pass
    return results


# --------------------------------------------------------------------------- verify
def load_fbx_reader():
    try:
        if LOOK not in sys.path:
            sys.path.insert(0, LOOK)
        import export_fbx
        return export_fbx
    except Exception as exc:
        warn("FBX reader unavailable (%s): verification limited" % exc)
        return None


def verify_fbx_file(reader, path, expect):
    """Read the FBX back and check what actually landed on disk."""
    rep = {"path": path, "ok": True, "issues": []}
    if reader is None:
        rep["ok"] = False
        rep["issues"].append("no-reader")
        return rep
    try:
        doc = reader.read(path)
        s = doc.summary()
    except Exception as exc:
        rep["ok"] = False
        rep["issues"].append("parse: %s" % exc)
        return rep
    rep["verts"] = s.get("verts")
    rep["polys"] = s.get("polys")
    rep["materials"] = list(s.get("materials") or [])
    rep["unit_scale_factor"] = s.get("unit_scale_factor")
    rep["up_axis"] = s.get("up_axis")
    rep["front_axis"] = s.get("front_axis")
    rep["raw_bbox"] = [s.get("bbox_min"), s.get("bbox_max")]
    xf = s.get("model_xforms") or {}
    rep["model_xforms"] = xf
    try:
        usf = float(s.get("unit_scale_factor", 1.0))
    except (TypeError, ValueError):
        usf = 1.0
    if abs(usf - 1.0) > 1e-4:
        rep["issues"].append("unit_scale_factor=%s (Unity would rescale)" % usf)
    up = s.get("up_axis")
    if up is not None and int(up) != 1:
        rep["issues"].append("up_axis=%s (expected 1 = +Y)" % up)
    # The Blender FBX exporter does NOT bake the axis change into the vertices:
    # it keeps them in Blender Z-up metres and puts the conversion on the model
    # node as Lcl Rotation (-90,0,0) and Lcl Scaling (100,100,100) against a
    # centimetre UnitScaleFactor.  That is the canonical arrangement (the
    # project's known-good Assets\Generated\MedievalKitBlender\house_a.fbx has
    # exactly these numbers), so the check is "canonical", not "identity".
    # What must hold is the PRODUCT: units * node scale / 100 == 1 m.
    xiter = xf.items() if isinstance(xf, dict) else [(None, x) for x in (xf or [])]
    for nm, x in xiter:
        if not isinstance(x, dict):
            continue
        rot = x.get("Lcl Rotation") or [0, 0, 0]
        scl = x.get("Lcl Scaling") or [1, 1, 1]
        tra = x.get("Lcl Translation") or [0, 0, 0]
        rot_ok = (abs(float(rot[0]) + 90.0) < 0.05
                  and abs(float(rot[1])) < 0.05 and abs(float(rot[2])) < 0.05)
        if not rot_ok:
            rep["issues"].append("model rotation %s on %s (canonical is -90,0,0)"
                                 % (rot, nm))
        net = usf * (sum(abs(float(v)) for v in scl) / 3.0) / 100.0
        if abs(net - 1.0) > 0.01:
            rep["issues"].append(
                "net scale %.4f on %s (1 Blender m must be 1 Unity m)" % (net, nm))
        if max(abs(float(v)) for v in tra) > 1e-2:
            rep["issues"].append("model translation %s on %s" % (tra, nm))
    if expect:
        if s.get("verts") and s["verts"] > max(expect.get("vert_cap", 65535),
                                               expect.get("allow_verts", 0)):
            rep["issues"].append("verts %d > cap" % s["verts"])
        if expect.get("tris") and s.get("polys"):
            got = int(s["polys"])
            if abs(got - expect["tris"]) > max(4, 0.02 * expect["tris"]):
                rep["issues"].append("polys %d != expected %d" % (got, expect["tris"]))
        if expect.get("materials"):
            want = set(expect["materials"])
            got = set(rep["materials"])
            missing = [m for m in want if m not in got]
            if missing:
                rep["issues"].append("material names missing: %s" % missing[:6])
    rep["ok"] = not rep["issues"]
    return rep


# --------------------------------------------------------------------------- axis test
def axis_test(outdir):
    """Write the 10 m cube + chirality markers through the production FBX settings."""
    os.makedirs(outdir, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mat = bpy.data.materials.new("axis_probe")
    mat.use_nodes = True
    mat.diffuse_color = (0.8, 0.2, 0.1, 1.0)

    def box(name, loc, size):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        o = bpy.context.object
        o.name = name
        o.scale = (size[0] * 0.5, size[1] * 0.5, size[2] * 0.5)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        o.data.materials.append(mat)
        return o

    box("cube10", (0, 0, 0), (10, 10, 10))
    box("mx", (14, 0, 0), (3, 3, 3))
    box("my", (0, 14, 0), (5, 5, 5))
    box("mz", (0, 0, 14), (7, 7, 7))
    fp = os.path.join(outdir, "axis_default.fbx")
    bpy.ops.export_scene.fbx(filepath=fp, **fbx_kwargs({"use_selection": False}))
    doc = {
        "blender_axes": "Z-up, forward -Y",
        "fbx_settings": {k: (list(v) if isinstance(v, set) else v)
                         for k, v in FBX_SETTINGS.items()},
        "expected_unity_center": {"mx": [14, 0, 0], "my": [0, 0, -14], "mz": [0, 14, 0]},
        "expected_unity_box": {"cube10": {"min": [-5, -5, -5], "max": [5, 5, 5]}},
        "mapping": "unity = (b.x, b.z, -b.y)",
        "file": fp, "bytes": os.path.getsize(fp),
    }
    with open(os.path.join(outdir, "axis_expect.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    log("axis test ->", fp, doc["bytes"], "bytes")
    return doc


# --------------------------------------------------------------------------- main
def main():
    global LOG_PATH
    if not OUT:
        raise SystemExit("--out is required")

    src_hint = BLEND or bpy.data.filepath
    if AXIS_TEST_DIR:
        axis_test(AXIS_TEST_DIR)
        if not src_hint or not os.path.exists(src_hint):
            log("axis test only (no scene to export)")
            return
        log("re-opening", src_hint, "after the axis fixture")
        bpy.ops.wm.open_mainfile(filepath=src_hint)
    elif BLEND:
        log("opening", BLEND)
        bpy.ops.wm.open_mainfile(filepath=BLEND)
    src = bpy.data.filepath
    log("source:", src or "<unsaved>")
    try:
        src_bytes = os.path.getsize(src) if src else 0
    except OSError:
        src_bytes = 0

    os.makedirs(OUT, exist_ok=True)
    LOG_PATH = os.path.join(OUT, "export.log")
    try:
        with open(LOG_PATH, "w", encoding="utf-8") as fh:
            fh.write("export_unity.py %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    except OSError:
        LOG_PATH = None

    us = unit_scale_of_scene()
    log("unit scale_length =", us, " system =",
        bpy.context.scene.unit_settings.system)
    if abs(us - 1.0) > 1e-6:
        warn("scene unit scale is %s (1 BU = %s m); applying it to geometry" % (us, us))

    prepare_scene()

    # ---------------- collect
    t_collect = time.time()
    items = []
    skipped_hidden = 0
    non_mesh = 0
    for o in bpy.data.objects:
        if o.type != 'MESH':
            non_mesh += 1
            continue
        if SKIP_HIDDEN and o.hide_render:
            skipped_hidden += 1
            continue
        me = o.data
        if me is None or len(me.polygons) == 0:
            continue
        tris, verts, corners, smoothf = mesh_corner_stats(me)
        if tris <= 0:
            continue
        bx = box_world(o)
        cen = ((bx[0][0] + bx[1][0]) * 0.5, (bx[0][1] + bx[1][1]) * 0.5,
               (bx[0][2] + bx[1][2]) * 0.5)
        # Unity splits flat-shaded corners: estimate the real vertex count
        vest = int(round(verts + (1.0 - smoothf) * max(0, corners - verts)))
        colnames = [c.name for c in o.users_collection if c is not None]
        cat, lmk, why = classify(o.name, colnames, bx, tris)
        mats = [s.material.name for s in o.material_slots if s.material is not None]
        items.append({"obj": o, "name": o.name, "tris": tris, "verts": verts,
                      "cest": vest, "vest": vest, "corners": corners,
                      "bx": bx, "cen": cen, "cat": cat, "lm": lmk, "why": why,
                      "mats": mats, "mods": len(o.modifiers)})
    log("collected %d mesh objects in %.1f s (%d hidden skipped, %d non-mesh)"
        % (len(items), time.time() - t_collect, skipped_hidden, non_mesh))

    TOTAL_TRIS = sum(it["tris"] for it in items)
    TOTAL_VEST = sum(it["vest"] for it in items)
    log("source tris=%d  estimated unity verts=%d  objects=%d"
        % (TOTAL_TRIS, TOTAL_VEST, len(items)))
    if not items:
        warn("nothing to export")
        return

    # ---------------- category stats
    cats = {}
    for it in items:
        key = it["cat"] if it["cat"] != "landmark" else "landmark:" + (it["lm"] or "misc")
        d = cats.setdefault(key, {"objects": 0, "tris": 0, "vest": 0, "bx": None,
                                  "mats": set(), "reasons": {}})
        d["objects"] += 1
        d["tris"] += it["tris"]
        d["vest"] += it["vest"]
        d["bx"] = b_union(d["bx"], it["bx"])
        d["mats"].update(it["mats"])
        d["reasons"][it["why"]] = d["reasons"].get(it["why"], 0) + 1
    for k in sorted(cats):
        d = cats[k]
        log("  category %-22s objects=%-6d tris=%-9d vest=%d"
            % (k, d["objects"], d["tris"], d["vest"]))
    log("materials referenced:", len(set(m for it in items for m in it["mats"])))

    if AUDIT_ONLY:
        audit = {
            "blend": src, "blend_bytes": src_bytes,
            "objects": len(items), "total_tris": TOTAL_TRIS,
            "estimated_unity_verts": TOTAL_VEST,
            "unit_scale_length": us,
            "categories": {k: {"objects": v["objects"], "tris": v["tris"],
                               "estimated_verts": v["vest"],
                               "bbox_blender": [r4(v["bx"][0]), r4(v["bx"][1])] if v["bx"] else None,
                               "bbox_unity": [r4(unity_box(v["bx"])[0]),
                                              r4(unity_box(v["bx"])[1])] if v["bx"] else None,
                               "materials": sorted(v["mats"]),
                               "reasons": dict(sorted(v["reasons"].items())[:12])}
                           for k, v in sorted(cats.items())},
            "materials": [material_info(bpy.data.materials[n])
                          for n in sorted(set(m for it in items for m in it["mats"]))
                          if bpy.data.materials.get(n)],
            "top_objects": sorted(
                [{"name": it["name"], "tris": it["tris"], "cat": it["cat"],
                  "lm": it["lm"], "why": it["why"]} for it in items],
                key=lambda d: -d["tris"])[:60],
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(os.path.join(OUT, "audit.json"), "w", encoding="utf-8") as fh:
            json.dump(audit, fh, indent=1, ensure_ascii=False)
        # name tokens, so the classification table can be tuned against reality
        tok = {}
        for it in items:
            for t in set(re.findall(r"[A-Za-z_]{3,}", it["name"])):
                d = tok.setdefault(t.lower(), [0, 0, set()])
                d[0] += 1
                d[1] += it["tris"]
                d[2].add(it["cat"])
        rows = sorted(tok.items(), key=lambda kv: -kv[1][1])[:400]
        with open(os.path.join(OUT, "name_tokens.tsv"), "w", encoding="utf-8") as fh:
            fh.write("token\tobjects\ttris\tcategories\n")
            for t, (n, tr, cs) in rows:
                fh.write("%s\t%d\t%d\t%s\n" % (t, n, tr, ",".join(sorted(cs))))
        log("audit ->", os.path.join(OUT, "audit.json"), "and name_tokens.tsv")
        return

    # ---------------- plan
    cell_arg = str(CELL).lower()
    chunked_cats = [c for c in cats if c in ("city", "props", "walls", "terrain", "other")]
    if cell_arg in ("auto", "0", ""):
        big = [it for it in items if it["cat"] in ("city", "props", "walls", "other")]
        cell = auto_cell(big or items, TARGET_CHUNKS)
    else:
        cell = float(cell_arg)
    log("chunk grid cell = %.1f m, tri budget %d, vert budget %d"
        % (cell, CHUNK_TRIS, VERT_CAP))

    plans = []   # {"cat","lm","chunks":[...]}
    for c in sorted(cats):
        if c.startswith("landmark:"):
            continue
        if c not in chunked_cats:
            continue
        its = [it for it in items if it["cat"] == c]
        # Every chunked category uses the documented name; the folder (and the
        # manifest path) disambiguates city / props / walls / terrain.
        chunks = plan_chunks(its, cell, CHUNK_TRIS, VERT_CAP, prefix="chunk",
                             cell_max=CELL_MAX)
        # A single object can be over budget on its own (one big merged mesh).
        # The post-join check splits those, so no pre-split pass is needed here.
        plans.append({"cat": c, "lm": None, "chunks": chunks})
        log("  %-8s -> %d chunks" % (c, len(chunks)))

    # landmarks: one file per landmark, unchunked (split only if --landmark-split)
    lm_groups = {}
    for it in items:
        if it["cat"] == "landmark":
            lm_groups.setdefault(it["lm"] or "misc", []).append(it)
    for k in sorted(lm_groups):
        its = lm_groups[k]
        tris = sum(i["tris"] for i in its)
        vest = sum(i["vest"] for i in its)
        log("  landmark %-12s objects=%-6d tris=%-8d vest=%d" % (k, len(its), tris, vest))
        parts = [{"name": k, "cell": None, "part": 0, "items": its}]
        if flag("--landmark-split"):
            parts = plan_chunks(its, cell, CHUNK_TRIS, VERT_CAP, prefix=k)
        plans.append({"cat": "landmark", "lm": k, "chunks": parts})

    n_chunks = sum(len(p["chunks"]) for p in plans)
    log("total output meshes planned:", n_chunks)

    if DRY_RUN:
        log("dry run: not writing files")
        return
    materials_mode = "baked" if BAKE_ONLY else MATERIALS
    log("materials mode:", materials_mode)

    # ---------------- out dir
    subdirs = {"city": "city", "props": "props", "walls": "walls",
               "terrain": "terrain", "other": "other", "landmark": "landmarks"}
    if not NO_CLEAN:
        for d in set(subdirs.values()):
            p = os.path.join(OUT, d)
            if os.path.isdir(p):
                log("clearing", p)
                shutil.rmtree(p, ignore_errors=True)
    for d in set(subdirs.values()):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)

    # ---------------- material table
    used_mats = sorted(set(m for it in items for m in it["mats"]))
    mat_infos = []
    sig_of = {}
    for mn in used_mats:
        mat = bpy.data.materials.get(mn)
        if mat is None:
            mat_infos.append({"name": mn, "key": safe_name(mn), "missing": True,
                              "base_rgb_linear": [0.8, 0.8, 0.8, 1.0],
                              "base_hex_srgb": "#cccccc", "rough": 0.62, "metal": 0.0,
                              "emis_linear": [0, 0, 0], "linked": {}, "kit": "kit_stone_wall",
                              "kit_tile_m": 2.2, "use_nodes": False, "node_count": 0})
            continue
        info = material_info(mat)
        sig = material_signature(mat)
        info["signature"] = sig[:40] + ("..." if len(sig) > 40 else "")
        info["sig_full"] = sig
        info["bake_key"] = sig_of.get(sig) or info["key"]
        sig_of.setdefault(sig, info["key"])
        info["tris"] = sum(it["tris"] for it in items if mn in it["mats"])
        mat_infos.append(info)
    log("unique materials used: %d (distinct node graphs: %d)"
        % (len(mat_infos), len(sig_of)))

    # Pin every material we are going to bake.  The export loop calls
    # orphans_purge() every 40 chunks; once a chunk's objects are dropped the
    # procedural materials have no users left and the purge silently frees them,
    # which is how the first lab run lost 'earth' before the bake stage
    # (`bake: material 'earth' vanished (found=False)`).  A fake user keeps them
    # resident; it is cleared again when the blend is not saved anyway.
    for mn in used_mats:
        m = bpy.data.materials.get(mn)
        if m is not None:
            m.use_fake_user = True

    # ---------------- export loop
    man_files = []
    t_export = time.time()
    chunk_index = 0
    total_chunks = n_chunks
    stats = {"files": 0, "bytes": 0, "tris": 0}

    for plan in plans:
        cat = plan["cat"]
        sub = subdirs[cat]
        for ch in plan["chunks"]:
            chunk_index += 1
            name = ch["name"]
            base_dir = os.path.join(OUT, sub)
            if cat == "landmark":
                base_dir = os.path.join(OUT, "landmarks")
            objs = [it["obj"] for it in ch["items"]]
            nmods = apply_modifiers_bulk(objs)
            if nmods:
                log("  applied modifiers on %d objects in %s" % (nmods, name))
            try:
                j = join_group(objs, name)
            except Exception as exc:
                warn("join failed for %s: %s" % (name, exc))
                continue
            tris, verts = mesh_counts(j.data)
            vest = export_vert_estimate(j.data)

            # safety net: the caps apply to the *exported* mesh, and Unity splits
            # flat-shaded corners, so measure instead of trusting the estimate
            parts = split_until_fits(j, VERT_CAP, CHUNK_TRIS, name)
            j = parts[0]
            base_part = ch.get("part") or 0
            # Every piece of the chunk -- the primary mesh and any over-budget
            # overflow piece -- goes through the same export path, so LODs and
            # collision exist for overflow pieces too.  (Before this, an overflow
            # piece was exported bare: the lab's 40 k-triangle overflow chunk had
            # no LOD1/LOD2, which would pop in game.)
            todo = [(j, name, base_part)]
            for k, extra in enumerate(parts[1:], start=1):
                extra.name = "%s_s%d" % (name, k)
                extra.data.name = extra.name
                todo.append((extra, extra.name, base_part + k))

            tmp = []
            primary_entry = None
            for obj, nm, part_i in todo:
                tris, verts = mesh_counts(obj.data)
                vest = export_vert_estimate(obj.data)
                obj.name = nm
                obj.data.name = nm
                bx = box_world(obj)
                ub = unity_box(bx)
                mats = [m.name for m in obj.data.materials if m is not None]
                entry = {"path": os.path.relpath(os.path.join(base_dir, nm + ".fbx"), OUT
                                                 ).replace("\\", "/"),
                         "category": cat, "landmark": plan["lm"],
                         "chunk": ch.get("cell"), "part": part_i,
                         "lod": 0, "tris": tris, "verts": verts, "verts_export": vest,
                         "submeshes": len(obj.data.materials),
                         "bbox_blender": [r4(bx[0]), r4(bx[1])],
                         "bbox_unity": [r4(ub[0]), r4(ub[1])],
                         "center_unity": r4([(ub[0][i] + ub[1][i]) * 0.5 for i in range(3)]),
                         "size_unity": r4([ub[1][i] - ub[0][i] for i in range(3)]),
                         "materials": mats,
                         "objects": len(ch["items"]) if part_i == base_part else 0,
                         "files": {}}

                fp = os.path.join(base_dir, nm + ".fbx")
                size = export_obj(obj, fp)
                entry["files"]["0"] = size
                entry["bytes"] = size
                stats["files"] += 1
                stats["bytes"] += size
                stats["tris"] += tris

                # ---- LODs
                if LOD_ON:
                    for li, ratio in enumerate(LOD_RATIO, start=1):
                        lname = "%s_L%d" % (nm, li)
                        try:
                            dup = decimate_copy(obj, ratio, lname)
                        except Exception as exc:
                            warn("decimate failed %s: %s" % (lname, exc))
                            continue
                        lfp = os.path.join(base_dir, lname + ".fbx")
                        lsize = export_obj(dup, lfp)
                        lt, lv = mesh_counts(dup.data)
                        entry["files"][str(li)] = lsize
                        entry["lod%d_tris" % li] = lt
                        entry["lod%d_verts" % li] = lv
                        stats["files"] += 1
                        stats["bytes"] += lsize
                        tmp.append(dup)

                # ---- collision
                if COL_ON and cat in COL_CATS:
                    cname = nm + "_col"
                    # A 12-triangle wall segment collapsed to 10 % leaves two
                    # triangles -- a collider players walk straight through.
                    # Never let the target fall below COL_MIN_TRIS: for small
                    # chunks that keeps the mesh nearly intact, which is cheap
                    # anyway (measured on the lab: walls came out as 2-triangle
                    # colliders before this floor existed).
                    cratio = COL_RATIO
                    if tris and tris * cratio < COL_MIN_TRIS:
                        cratio = min(1.0, COL_MIN_TRIS / float(tris))
                    try:
                        col = weld_and_decimate_copy(obj, cratio, cname)
                    except Exception as exc:
                        warn("collision failed %s: %s" % (cname, exc))
                        col = None
                    if col is not None:
                        cfp = os.path.join(base_dir, cname + ".fbx")
                        csize = export_obj(col, cfp)
                        ct, cv = mesh_counts(col.data)
                        cb = box_world(col)
                        cmin = min(abs(cb[1][k] - cb[0][k]) for k in range(3))
                        entry["col"] = {"path": os.path.relpath(cfp, OUT).replace("\\", "/"),
                                        "tris": ct, "verts": cv, "bytes": csize,
                                        "ratio": round(cratio, 3),
                                        "min_dim": round(cmin, 3),
                                        "thin": bool(cmin < 0.06)}
                        stats["files"] += 1
                        stats["bytes"] += csize
                        tmp.append(col)

                man_files.append(entry)
                tmp.append(obj)
                if part_i == base_part:
                    primary_entry = entry
                else:
                    log("  oversize split -> %s tris=%d vest=%d" % (nm, tris, vest))

            entry = primary_entry
            tris = entry["tris"]
            vest = entry["verts_export"]
            drop(tmp)

            if chunk_index <= 3 or chunk_index % 25 == 0 or chunk_index == total_chunks:
                el = time.time() - t_export
                per = el / max(1, chunk_index)
                log("chunk %d/%d %-22s tris=%-6d vest=%-6d files=%s  %.1f MB  "
                    "%.1f s (%.2f s/chunk, ETA %.1f min, mem %.0f MB)"
                    % (chunk_index, total_chunks, name, tris, vest,
                       {k: "%.2fMB" % (v / 1e6) for k, v in entry["files"].items()},
                       stats["bytes"] / 1e6, el, per,
                       per * (total_chunks - chunk_index) / 60.0, sample_mem()))
            if chunk_index % 40 == 0:
                purge()

    log("exported %d meshes, %d files, %.1f MB in %.1f s"
        % (chunk_index, stats["files"], stats["bytes"] / 1e6, time.time() - t_export))

    # ---------------- verification (read the FBX back)
    ver = {"checked": 0, "failed": 0, "files": []}
    reader = load_fbx_reader() if VERIFY != "none" else None
    if reader is not None:
        sample = man_files if VERIFY == "all" else man_files[:min(12, len(man_files))]
        t_ver = time.time()
        for f in sample:
            if f.get("lod", 0) != 0:
                continue
            allow = 0
            if f["category"] == "landmark":
                allow = 10 ** 9      # single-fbx landmark: 32-bit indices on purpose
            rep = verify_fbx_file(reader, os.path.join(OUT, f["path"]),
                                  {"tris": f["tris"], "materials": f["materials"],
                                   "vert_cap": VERT_CAP, "allow_verts": allow})
            ver["checked"] += 1
            if not rep["ok"]:
                ver["failed"] += 1
                warn("verify %s: %s" % (f["path"], rep["issues"]))
            ver["files"].append(rep)
            f["verify"] = {"ok": rep["ok"], "fbx_verts": rep.get("verts"),
                           "fbx_polys": rep.get("polys"),
                           "unit_scale_factor": rep.get("unit_scale_factor"),
                           "up_axis": rep.get("up_axis")}
            if f["category"] != "landmark" and rep.get("polys"):
                f["tris"] = int(rep["polys"])
        log("verified %d files in %.1f s, %d failed"
            % (ver["checked"], time.time() - t_ver, ver["failed"]))
        with open(os.path.join(OUT, "verify.json"), "w", encoding="utf-8") as fh:
            json.dump(ver, fh)

    # ---------------- bake (plan A)
    bake_entries = {}
    if materials_mode in ("baked", "both"):
        uniq = {}
        for mi in mat_infos:
            if mi.get("missing") or not mi.get("use_nodes"):
                continue
            key = mi["bake_key"]
            if key in uniq:
                continue
            uniq[key] = mi
        cand = sorted(uniq.values(), key=lambda m: -m.get("tris", 0))
        if BAKE_TOP > 0:
            cand = cand[:BAKE_TOP]
        log("baking %d unique materials at %dpx, %.1f m/tile" % (len(cand), BAKE_RES, TILE_M))
        bake_entries = bake_materials(cand, OUT, BAKE_RES, TILE_M, BAKE_TOP, BAKE_AO_SAMPLES)

    # ---------------- assemble manifest
    for mi in mat_infos:
        be = bake_entries.get(mi["name"]) or bake_entries.get(mi.get("bake_key"))
        if be:
            mi["baked"] = be
            mi["tile_m"] = be["tile_m"]
            # A linked Base Color has no meaningful default_value (it is the
            # node socket, not the colour), so the flat fallback was grey.  The
            # baked mean is the real albedo and is what plan B must tint with.
            if be.get("base_rgb_mean_linear"):
                mi["base_rgb_node_default"] = mi.get("base_rgb_linear")
                mi["base_hex_node_default"] = mi.get("base_hex_srgb")
                mi["base_rgb_linear"] = list(be["base_rgb_mean_linear"]) + [1.0]
                mi["base_hex_srgb"] = (be.get("base_hex_mean_srgb")
                                       or mi.get("base_hex_srgb"))
                mi["base_source"] = "baked_base_mean"
            mi["textures"] = {
                "base": be["dir"] + "/" + be["base"],
                "normal": be["dir"] + "/" + be["normal"],
                "rough_ao": be["dir"] + "/" + be["ra"],
                "metal": be["dir"] + "/" + be["metal"],
            }
    for mi in mat_infos:
        mi.pop("sig_full", None)

    totals = {"files": 0, "bytes": 0, "tris": 0, "lods": {}, "categories": {},
              "meshes": 0, "collisions": 0}
    for f in man_files:
        # A chunk entry stands for 1..n FBX files: LOD0 plus every extra LOD plus
        # an optional collision mesh.  Counting entries would understate the real
        # output (the first lab run reported 46 files for 137 on disk).
        n_files = len(f.get("files") or {}) or 1
        n_bytes = sum((f.get("files") or {}).values()) or f.get("bytes", 0)
        if f.get("col"):
            n_files += 1
            n_bytes += f["col"].get("bytes", 0)
            totals["collisions"] += 1
        totals["files"] += n_files
        totals["meshes"] += 1
        totals["bytes"] += n_bytes
        totals["tris"] += f.get("tris", 0)
        d = totals["categories"].setdefault(f["category"], {"files": 0, "bytes": 0,
                                                            "tris": 0, "meshes": 0})
        d["files"] += n_files
        d["bytes"] += n_bytes
        d["tris"] += f.get("tris", 0)
        d["meshes"] += 1
        for k, v in f.get("files", {}).items():
            ld = totals["lods"].setdefault(k, {"files": 0, "bytes": 0})
            ld["files"] += 1
            ld["bytes"] += v

    manifest = {
        "schema": "uexport/1",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "exporter": {"script": "export_unity.py", "blender": bpy.app.version_string,
                     "seconds": round(time.time() - T0, 1)},
        "source": {"blend": src, "bytes": src_bytes, "objects": len(items),
                   "tris": TOTAL_TRIS, "estimated_unity_verts": TOTAL_VEST,
                   "unit_scale_length": us},
        "axis": {
            "blender": "Z-up, -Y forward, metres",
            "unity": "Y-up, +Z forward, metres",
            "mapping": "unity = (b.x, b.z, -b.y)",
            "scale": "1 Blender unit = 1 metre = 1 Unity unit",
            "node_transforms": "identity (all object transforms applied before export)",
            "fbx_settings": {"axis_forward": "-Z", "axis_up": "Y",
                             "apply_unit_scale": False,
                             "apply_scale_options": "FBX_SCALE_NONE",
                             "global_scale": 1.0,
                             "use_space_transform": True,
                             "bake_space_transform": False,
                             "use_triangles": True,
                             "mesh_smooth_type": "OFF"},
            "verified_by": "Tests/AXIS (see Docs/AGENT_UEXPORT.md)",
        },
        "chunking": {"cell_m": cell, "chunk_tris": CHUNK_TRIS, "vert_cap": VERT_CAP,
                     "naming": {"chunk": "<prefix>_<cx>_<cy>",
                                "overflow": "<prefix>_<cx>_<cy>_pNN",
                                "lod": "<name>_L1 / _L2",
                                "collision": "<name>_col"},
                     "categories": {"city": "grid chunks", "props": "grid chunks",
                                    "walls": "grid chunks", "terrain": "grid chunks",
                                    "landmarks": "one FBX per landmark, unchunked"}},
        "unity_import": {
            "materialImportMode": "ImportStandard",
            "materialLocation": "InPrefab",
            "globalScale": 1.0,
            "useFileScale": True,
            "importCameras": False,
            "importLights": False,
            "importBlendShapes": False,
            "importVisibility": False,
            "addCollider": False,
            "meshCompression": "Off",
            "isReadable": False,
            "note": "materialImportMode=None loses every material name; "
                    "chunks carry no UVs, so shaders must be triplanar",
        },
        "totals": totals,
        "files": man_files,
        "materials": [{k: v for k, v in mi.items() if k != "sig_full"}
                      for mi in mat_infos],
        "warnings": WARNINGS[:200],
        "performance": {"seconds_total": round(time.time() - T0, 1),
                        "peak_rss_mb": round(MEM_PEAK[0], 1),
                        "tris": TOTAL_TRIS},
    }
    mpath = os.path.join(OUT, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)

    # materials.json = plan B payload (small, stable, no textures needed)
    planb = {
        "schema": "uexport-materials/1",
        "source": src,
        "tile_default_m": TILE_M,
        "colorspace": {"base": "sRGB", "normal": "linear", "rough_ao": "linear",
                       "metal": "linear"},
        "materials": [{"name": mi["name"], "base_hex": mi.get("base_hex_srgb"),
                       "base_rgb_linear": mi.get("base_rgb_linear"),
                       "rough": mi.get("rough"), "metal": mi.get("metal"),
                       "emis_linear": mi.get("emis_linear"),
                       "kit": mi.get("kit"), "kit_tile_m": mi.get("kit_tile_m"),
                       "linked": mi.get("linked"),
                       "textures": mi.get("textures"),
                       "tile_m": mi.get("tile_m", mi.get("kit_tile_m"))}
                      for mi in mat_infos],
    }
    with open(os.path.join(OUT, "materials.json"), "w", encoding="utf-8") as fh:
        json.dump(planb, fh, indent=1)

    # ---- expect.tsv / materials.tsv -------------------------------------
    # Deliberately dumb machine-readable side-cars: the Unity-side verifier is
    # C# and should not need a JSON parser to assert "the mesh arrived at the
    # size and place I planned".  Tab separated, one row per FBX.
    try:
        cols = ["path", "category", "lod", "tris", "verts_export", "submeshes",
                "minx", "miny", "minz", "maxx", "maxy", "maxz", "materials"]
        with open(os.path.join(OUT, "expect.tsv"), "w", encoding="utf-8") as fh:
            fh.write("\t".join(cols) + "\n")
            for f in man_files:
                b = f.get("bbox_unity") or [[0, 0, 0], [0, 0, 0]]
                row = [f["path"], f.get("category") or "", str(f.get("lod", 0)),
                       str(f.get("tris", 0)), str(f.get("verts_export", 0)),
                       str(f.get("submeshes", 0))]
                row += ["%.4f" % v for v in list(b[0]) + list(b[1])]
                row.append(",".join(f.get("materials") or []))
                fh.write("\t".join(row) + "\n")
        with open(os.path.join(OUT, "materials.tsv"), "w", encoding="utf-8") as fh:
            fh.write("name\tkit\ttile_m\tbase_hex\trough\tmetal\tbase_tex\t"
                     "normal_tex\trough_ao_tex\tmetal_tex\n")
            for mi in mat_infos:
                tx = mi.get("textures") or {}
                fh.write("\t".join([
                    mi["name"], str(mi.get("kit") or "").replace("kit_", ""),
                    "%.3f" % float(mi.get("tile_m") or mi.get("kit_tile_m") or 0.0),
                    str(mi.get("base_hex_srgb") or ""),
                    str(mi.get("rough") if mi.get("rough") is not None else ""),
                    str(mi.get("metal") if mi.get("metal") is not None else ""),
                    tx.get("base", ""), tx.get("normal", ""),
                    tx.get("rough_ao", ""), tx.get("metal", "")]) + "\n")
        log("side-cars -> expect.tsv / materials.tsv")
    except Exception as exc:
        warn("side-car write failed: %s" % exc)

    log("manifest ->", mpath)
    for k in sorted(totals["categories"]):
        d = totals["categories"][k]
        log("  %-10s files=%-5d tris=%-9d %.1f MB" % (k, d["files"], d["tris"],
                                                      d["bytes"] / 1e6))
    for k in sorted(totals["lods"]):
        d = totals["lods"][k]
        log("  lod%s files=%-5d %.1f MB" % (k, d["files"], d["bytes"] / 1e6))
    log("TOTAL files=%d bytes=%.1f MB tris=%d peak_rss=%.0f MB total=%.1f s"
        % (totals["files"], totals["bytes"] / 1e6, totals["tris"],
           MEM_PEAK[0], time.time() - T0))
    log("DONE")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        log("FAILED")
        raise
