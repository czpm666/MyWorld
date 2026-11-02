# Unity export pipeline — `export_unity.py`

Owner: UEXPORT agent. Files created/owned:

| file | role |
|---|---|
| `Blender/kingdom/export_unity.py` | the exporter (CLI below) |
| `Blender/kingdom/look/export_lab.py` | lab scene builder (892 objects, 6 materials) — validation only |
| `Blender/kingdom/look/export_axis.py` | standalone axis fixture (older; superseded by `--axis-test`) |
| `Blender/kingdom/look/export_fbx.py` | dependency-free FBX 7.x **reader** (also runs outside Blender) |
| `Blender/kingdom/look/export_run.py` | lock-aware launcher: `python look/export_run.py <tag> <timeout> -- <blender args>` |
| `Assets/Editor/UexportLabProbe.cs` | Unity-side import verification + screenshots |
| `Assets/Editor/UexportAxisProbe.cs` | Unity-side axis/scale probe + screenshots |
| `Assets/Editor/UexportMenu.cs` | `Tools/UEXPORT/*` menu items that call the probes from the open editor |

Nothing else in the project was modified. `capital.py`, `hd_*.py` and the `capital_*.blend`
files are untouched (the exporter only reads the blend it is handed).

---

## 1. CLI

```
blender -b <blend> --python export_unity.py -- --out "E:\My World\Blender\export\capital_v2" \
        --chunk-tris 50000 --lod --collision --materials both
```

Always launch through the shared lock:

```
cd "E:\My World\Blender\kingdom"
python look\export_run.py <tag> 3600 -- -b --factory-startup --python export_unity.py -- ^
       --blend "E:\My World\Blender\renders\kingdom\capital_v24.blend" ^
       --out "E:\My World\Blender\export\capital_v2" --chunk-tris 50000 --lod --collision --materials both
```

(`look\export_run.py` wraps `_lock.run_blender()`, so it waits for the lock, tees the log to
`E:\My World\Logs\<tag>.log`, and now inherits the zombie watchdog.)

| flag | default | meaning |
|---|---|---|
| `--blend` | current file | blend to open |
| `--out` | **required** | output root |
| `--chunk-tris` | 50000 | triangle cap per chunk mesh |
| `--vert-cap` | 65535 | **Unity 16-bit index** cap; counted the way Unity counts (flat corners split) |
| `--cell-size` | `auto` | grid cell in metres; `auto` = √(area/`--target-chunks`) rounded to 8 m |
| `--target-chunks` | 700 | used only by `auto` |
| `--lod` / `--lod-ratio` | off / `0.5,0.15` | LOD1/LOD2, each decimated **from LOD0** (not chained) |
| `--collision` / `--col-ratio` / `--col-categories` | off / `0.10` / `terrain,walls` | `_col` meshes |
| `--col-min-tris` | 64 | never decimate a collider below this (thin walls used to collapse to 2 tris) |
| `--materials` | `json` | `json` (plan B) / `baked` (plan A) / `both` |
| `--bake-res` / `--tile-m` | 1024 / 4.0 | bake resolution; texture tile size in **metres** |
| `--bake-top` | 0 (all) | only bake the N most-used materials |
| `--audit-only` | off | write `audit.json` + `name_tokens.tsv`, export nothing |
| `--dry-run` | off | plan + report, export nothing |
| `--classify <json>` | — | `{"regex": "category"}` overrides, highest priority |
| `--landmarks` | `castle,cathedral,guild,market,gate` | name keywords for the unchunked landmark pass |
| `--axis-test <dir>` | — | write the 4-cube axis fixture and (if no `--blend`) stop |
| `--verify` | `all` | re-read every exported FBX and check it (`all`/`sample`/`none`) |
| `--keep-scratch`, `--no-clean`, `--include-hidden` | off | debugging |

`--audit-only` is the **first** command to run on a new blend: it prints per-category object
counts and the top name tokens, and writes `audit.json` (`blend`, `blend_bytes`, `objects`,
`total_tris`, `estimated_unity_verts`, `unit_scale_length`, `categories`, `materials`, `top_objects`,
`generated`) plus `name_tokens.tsv` (`token	objects	tris	categories`). Use it to tune `--classify`
before spending 30 minutes on a real export. Measured on the lab: 1.3 s for 892 objects.

---

## 2. Axis and units — measured, not assumed

**Contract: `unity = (blender.x, blender.z, -blender.y)`, 1 Blender unit = 1 metre = 1 Unity unit.**

How it was determined (three independent observations):

1. The production FBX settings
   (`axis_forward='-Z'`, `axis_up='Y'`, `apply_unit_scale=False`,
   `apply_scale_options='FBX_SCALE_NONE'`, `global_scale=1.0`, `use_space_transform=True`,
   `bake_space_transform=False`) make Blender write, in the binary FBX:
   * `GlobalSettings.UnitScaleFactor = 1.0`, `UpAxis = 1 (+Y)`, `FrontAxis = 2 (+Z)`, `CoordAxis = 0 (+X)`;
   * raw `Vertices` still in **Blender Z-up metres**;
   * the whole conversion on the **model node**: `Lcl Rotation = (-90, 0, 0)`, `Lcl Scaling = (100, 100, 100)`.
   This is byte-identical in structure to the known-good `Assets\Generated\MedievalKitBlender\house_a.fbx`
   and the old `ars_*.fbx` that already import correctly.
2. `--axis-test <dir>` writes `axis_default.fbx` (a 10 m cube at the origin plus 3/5/7 m cubes at
   `+14` on each Blender axis) and `axis_expect.json` with the expected Unity centres:
   `mx → (14,0,0)`, `my → (0,0,-14)`, `mz → (0,14,0)`. `look\export_fbx.py` re-reads the file and
   asserts `unit_scale_factor == 1.0`, `up_axis == 1`, identity node translation, rotation ≈ (-90,0,0),
   scaling = (100,100,100) → net scale `usf × scale/100 = 1.0`.
3. Every exported chunk is verified the same way (`--verify all`, results in `manifest.json → files[].verify`),
   and `expect.tsv` carries the **Unity-space** bbox for each file so the Unity importer can assert
   `mesh.bounds == bbox_unity` (that is what `UexportLabProbe.cs` does, tolerance 0.05 m).

**Status of the Unity-side proof (2026-11-02):** the binary evidence (#1), the fixture (#2) and the
per-file verification (#3, 46/46 lab files) are done; the *Unity import* run (`UexportLabProbe`)
has **not** executed yet because a GUI editor opened the project through Unity Hub and Unity refuses
a second instance on the same project. `Assets/Editor/UexportLabProbe.cs` +
`Assets/Editor/UexportMenu.cs` are ready and compile cleanly; run them via
`Tools/UEXPORT/Run Lab Probe` or batchmode at integration time.

**The brief's `Euler(0,180,0) * Euler(-90,0,0)` object pre-rotation is wrong for this path** — it comes
from a different exporter that had `export_yup` semantics. The node transform above already performs
the Z-up → Y-up conversion; pre-rotating the vertices rotates twice (the city would end up on its side
mirrored in Z). Do not reintroduce it. `export_yup` does not exist in Blender 5.2's FBX operator
(verified by enumerating all 43 operator properties).

---

## 3. Chunking

* Objects are classified first, then binned by **chunk centre** into a square grid
  (`cell = <cell-size>`, `cx = floor(x/cell)`, `cy = floor(y/cell)`), sorted by `(y, x)` and packed
  greedily until either cap would be exceeded. Expected 600–900 chunk meshes for the 30.6 M-face city
  (30.6 M / 50 k = 612 minimum; the vertex cap raises it).
* **Vertex counting is honest for Unity.** Unity splits every flat-shaded corner, so a 50 k-triangle
  box chunk can be ~120 k Unity vertices. `export_vert_estimate()` counts unique quantised
  `(position, corner-normal)` pairs with numpy on `mesh.corner_normals`; that number is what the
  planner budgets against (`verts_export` in the manifest).
* If a joined chunk still exceeds a cap, `split_until_fits()` bisects it on the longer X/Y axis and
  the extra pieces are exported as `<name>_s1`, `_s2`, … **with their own LODs and collider**.
  The cut plane deletes straddling faces (open hole) — acceptable as a rare safety net, not as normal
  operation: with the caps as configured the lab produced one such piece out of 46.
* Overflow from grid packing (many overlapping objects in one cell) is `<name>_pNN`.

Names:

```
chunk_<cx>_<cy>          primary chunk mesh
chunk_<cx>_<cy>_pNN      part NN when one cell overflows the tri cap
chunk_<cx>_<cy>_sN       piece N after a vertex-cap bisection
<name>_L1 / _L2          LODs
<name>_col               collision
landmarks/<name>.fbx     one file per landmark, never chunked
```

Negative cell indices are normal (`chunk_-2_-1`), and the folder (`city/`, `props/`, `walls/`, `terrain/`)
disambiguates identical `chunk_<cx>_<cy>` names between categories — a Unity importer must key on
`category + name`, not name alone.

---

## 4. Categories and classification

| category | folder | chunked | notes |
|---|---|---|---|
| `city` | `city/` | yes | houses, shops, roofs, walls of buildings |
| `props` | `props/` | yes | street furniture, barrels, carts, trees |
| `walls` | `walls/` | yes | city wall, towers, gates-as-geometry |
| `terrain` | `terrain/` | yes | ground, roads, fields (the big one) |
| `landmark` | `landmarks/` | **no** | castle / cathedral / guild / market / gates — one FBX each |

Priority: `--classify` override → collection name → object-name regex table → geometry heuristic
(footprint area / flatness). The lab's deliberately unnamed `obj_90417` sphere is used to keep the
geometry fallback honest.

---

## 5. Materials

Two independent paths are produced, both keyed on the **unchanged Blender material name**
(`materialImportMode = ImportStandard`, `materialLocation = InPrefab`), because the existing
`KingdomKitImporter.cs` / `KingdomMaterialDetail.cs` already resolve palettes and kit textures by name.

### Plan B — `materials.json` + `materials.tsv` (fast, ships immediately)

Per material: `base_hex`, `base_rgb_linear` (4 components), `rough`, `metal`, `emis_linear`, plus the kit
texture chosen by the same substring rules as `Assets/Editor/KingdomMaterialDetail.cs`
(`kit_cobble` 3.4 m, `kit_stone_wall` 2.2 m, `kit_roof_tile` 3.0 m, `kit_planks` 0.9 m,
`kit_plaster` 3.0 m, `kit_dirt` 3.0 m, `kit_grass` 3.0 m, `kit_brick` 1.4 m) and `tile_m`.

**`base_hex_srgb` is the area-mean of the baked albedo, not the Principled socket default.**
A linked Base Color socket has no meaningful `default_value`, so the first lab pass emitted `#e7e7e7`
for every material — a linked material would have washed the whole city concrete-grey. The exporter
now reads the baked `base.png` back with colorspace `Non-Color` (the only mode where `pixels` is
byte/255 with no transform), averages in linear space, and records `base_source: "baked_base_mean"`
alongside the original socket value in `base_hex_node_default`.

### Plan A — baked textures (quality)

Per unique material (deduped by node-graph signature, so `stone.001/stone.002` bake once):

```
textures/<material>/base.png     albedo, sRGB, DIFFUSE/COLOR only (no direct/indirect)
textures/<material>/normal.png   tangent-space normal incl. the material's bump chain
textures/<material>/ra.png       R = roughness, G = 1.0 (see AO note), B = 0
textures/<material>/metal.png    metallic, baked via an emission swap
```

Bake geometry: a single plane of `--tile-m` metres placed at `(tile/2, tile/2, 0)` with the material
applied, Cycles CPU. The offset matters: the Unity shader replays a tile as `p = positionWS / tile_m`
with **no** offset, so UV(0,0) must be world (0,0), not the plane centre.

Playback with the existing `MyWorld/TriplanarLit` (**no new shader needed**):

```
_BaseMap = base.png      _BaseMap_ST = (1, 1, tile_m, 0)      // z = metres per tile
_BaseColor = white       _DetailStrength = 0    _DetailGain = 1
_NormalMap = normal.png  _BumpScale = 1        // albedo then equals the baked texture exactly
```

With `_DetailStrength = 0` the shader's `mult` collapses to `_DetailGain = 1`, so the sampled
texture *is* the albedo — the baked tile replays 1:1.

**Known limits, deliberately not faked:**

* **AO is not baked** (`ra.png` G = 1.0, `ao_mean` 1.0, `ao_note` in every entry). Ambient occlusion
  is a property of the surrounding geometry; baking onto one isolated plane yields 1.0 everywhere.
  A real AO pass needs a per-chunk bake against the city, which needs UVs the chunks do not have.
  Shipping a grey-looking "AO" channel would be worse than shipping none.
* **`TriplanarLit` has no occlusion or roughness/metallic map slots** — roughness and metallic are
  scalars today. `ra.png` / `metal.png` are exported for a future shader and for `_Smoothness`
  (from `rough_mean`); do not wire them into slots that do not exist.
* **Tiles repeat**, so a non-periodic procedural pattern seams at every tile edge. Pick `tile_m` as an
  integer multiple of the pattern period: `medkit.mat_tile` uses Brick Width 0.30 / Row Height 0.17,
  so 5.1 m (= 17 × 0.30 = 30 × 0.17) tiles cleanly, 4.0 m does not.

---

## 6. LOD and collision

* LOD1 = 50 %, LOD2 = 15 % of **LOD0** (independent Decimate COLLAPSE from the LOD0 mesh). Measured
  on the lab: 149 877 → 74 937 (0.500) → 22 452 (0.150) triangles. Chained decimation (what the old
  exporter did) compounds to 7.5 % and is not used.
* Collision exists for `--col-categories` (default `terrain,walls`): WELD 1 mm → TRIANGULATE →
  DECIMATE `--col-ratio`, as `<name>_col.fbx`.
  * `--col-min-tris 64` prevents the collapse of small meshes: a 12-triangle wall segment at ratio 0.1
    became a **2-triangle** collider you can walk through. With the floor, lab walls keep all 12.
  * Each collider records `min_dim` and `thin` (`min_dim < 0.06 m`). Thin/one-sided colliders should
    get a `BoxCollider` (or be skipped) on the Unity side rather than a `MeshCollider`.

---

## 7. Output tree and manifest

```
<out>/
  manifest.json      everything below, machine-readable (schema "uexport/1")
  materials.json     plan B payload (schema "uexport-materials/1")
  materials.tsv      same, TSV for spreadsheet/importer
  expect.tsv         path, category, lod, tris, verts_export, submeshes, bbox_unity, materials
  verify.json        per-file FBX re-read results
  export.log         the run log
  city/ props/ walls/ terrain/ landmarks/ textures/
```

`manifest.json` top level:

| key | contents |
|---|---|
| `schema`, `generated`, `exporter` | `uexport/1`, timestamp, `{script, blender, seconds}` |
| `source` | blend path, bytes, objects, tris, `estimated_unity_verts`, `unit_scale_length` |
| `axis` | blender/unity axes, `mapping: "unity = (b.x, b.z, -b.y)"`, scale, node transforms, the FBX settings actually used, `verified_by` |
| `chunking` | `cell_m`, `chunk_tris`, `vert_cap`, naming templates, per-category strategy |
| `unity_import` | recommended ModelImporter settings (see §9) |
| `totals` | `files`, `bytes`, `tris`, `meshes`, `collisions`, `lods{0,1,2}`, `categories{files,bytes,tris,meshes}` |
| `files[]` | one entry per **LOD0 mesh** (below) |
| `materials[]` | per material: name, key, base colour (node + baked mean), rough, metal, emission, kit, kit_tile_m, signature, `baked{dir,tile_m,res,base,normal,ra,metal,bytes,rough_mean,ao_mean,ao_note}`, `tris` |
| `warnings[]` | every soft failure |
| `performance` | `seconds_total`, `peak_rss_mb`, `tris` |

`files[]` entry:

```json
{"path": "city/chunk_-2_-2.fbx", "category": "city", "landmark": null, "chunk": [-2,-2],
 "part": 0, "lod": 0, "tris": 424, "verts": 248, "verts_export": 912, "submeshes": 4,
 "bbox_blender": [[...],[...]], "bbox_unity": [[...],[...]],
 "center_unity": [...], "size_unity": [...],
 "materials": ["timber","plaster","stone","roof_tile"], "objects": 18,
 "files": {"0": 28284, "1": 23964, "2": 20988},     // bytes per LOD
 "bytes": 28284, "lod1_tris": 212, "lod1_verts": 142, "lod2_tris": 62, "lod2_verts": 67,
 "col": {"path": "…_col.fbx", "tris": 4499, "verts": 2411, "bytes": …, "ratio": 0.1,
         "min_dim": 2.354, "thin": false},
 "verify": {"ok": true, "fbx_verts": 248, "fbx_polys": 424, …}}
```

`totals.files` counts **real files on disk** (LODs + colliders), not manifest entries: the first lab
run reported 46 files while 137 existed.

---

## 8. Measured numbers (lab scene)

Lab scene `WorkQC\uexport\lab\lab.blend`: 892 objects, 139 380 tris, 6 procedural materials
(200 box houses with a BEVEL modifier, castle landmark, 300 m terrain grid, 2 roads, 12 wall segments,
60 barrels, an 82 k-triangle icosphere to force the split path, an unnamed sphere for the geometry
fallback). Run `ux_lab7.log`, `--chunk-tris 50000 --cell-size 64 --lod --collision --materials both`.

| metric | value |
|---|---|
| chunk meshes (LOD0) | **46** (city 16, walls 12, props 12, terrain 5, landmark 1) |
| FBX files on disk | **155** = 46 LOD0 + 46 LOD1 + 46 LOD2 + 17 colliders |
| total size | **9.67 MB** FBX (LOD0 4.62 / LOD1 2.89 / LOD2 1.50 / col 0.66) + **4.05 MB** textures (6 × 4 PNG @1K) |
| triangles | LOD0 **149 877** → LOD1 74 937 (0.500) → LOD2 22 452 (0.150) |
| chunk tris | min 12 / median 286 / p95 40 573 / max **45 000** (cap 50 000, 0 over) |
| Unity verts per chunk | median 156 / p95 20 479 / max **29 054** (cap 65 535, 0 over) |
| submeshes per chunk | mean 2.04 / max 4 |
| colliders | 17, total 12 782 tris, 0 flagged `thin` |
| wall-clock | **38.3 s** (≈0.8 s blend load + 0.1 s classify + 8.5 s geometry export + 24 s bake + verify) |
| peak RSS | **613 MB** |
| verification | 46/46 files re-read from disk, `unit_scale_factor`/node transforms/poly counts/material names all OK, 0 failures |

Extrapolation for the real city (30.6 M faces, ~130 materials), **projection, not yet measured**:

| quantity | projection | basis |
|---|---|---|
| chunk meshes | 600–900 | 30.6 M / 50 k = 612, raised by the vertex cap |
| FBX size | ~1.6–1.8 GB | 30.8 bytes/tri at LOD0 (4.62 MB / 149 877) × 30.6 M, plus 0.5 and 0.15 LODs |
| geometry time | ~25–35 min | 8.5 s per 150 k tris |
| bake time | ~9 min @1K, ~35 min @2K | ~4 s per material @1K (6 materials in 24 s) |
| peak RSS | 6–10 GB | blend load dominates; RAM is the 31.3 GB machine's bottleneck |

---

## 9. Contract for the Unity importer

The importer reads `<out>\manifest.json` (and `materials.json`); nothing else is authoritative.

1. **Model import settings** (per FBX, from `manifest.json → unity_import`):
   `globalScale=1`, `useFileScale=true`, `importCameras=false`, `importLights=false`,
   `importBlendShapes=false`, `importVisibility=false`, `addCollider=false`, `meshCompression=Off`,
   `animationType=None`, **`materialImportMode=ImportStandard`**, `materialLocation=InPrefab`,
   `isReadable=false` in production (true only for the probes), normals `Import`, no tangents
   (triplanar needs none), `importAnimation=false`.
2. **Grouping**: files whose name starts with `chunk_` belong to a chunk identified by
   `(category, cx, cy)`; `_pNN`, `_sN`, `_L1`, `_L2`, `_col` are variants of the same chunk.
   Build one prefab per chunk with a `LODGroup` (LOD0/LOD1/LOD2 renderers, suggest screen-height
   thresholds 0.30 / 0.08 / 0.01) and one child with the `_col` `MeshCollider` where `col` exists
   (`convex=false`; skip or box-ify entries with `thin: true`).
3. **Materials**: resolve each renderer material by name against `materials.json`.
   * Plan B: `MyWorld/TriplanarLit`, `_BaseMap` = `Assets/Art/Textures/kit_<kit>.jpg`,
     `_BaseMap_ST = (1,1,tile_m,0)`, `_BaseColor` = `base_hex_srgb`, `_DetailStrength` 0.7,
     `_DetailMean` = the kit texture's mean luminance, `_Smoothness = 1 - rough`, `_Metallic = metal`.
   * Plan A: same shader, `_BaseMap` = `textures/<name>/base.png`, `_BaseColor` white,
     `_DetailStrength` 0, `_DetailGain` 1, `_BumpMap` = `textures/<name>/normal.png`, `_BumpScale` 1.
     Copy the PNGs into the project (e.g. `Assets/Generated/CapitalV2/Textures/<name>/`) and set
     `wrapMode = Repeat`, `sRGB` on base only, `Non-Color` on normal/ra/metal.
4. **Sanity check** (cheap, catches axis/scale/name regressions): compare each imported
   `Mesh.bounds` to `files[].bbox_unity` (tolerance 0.05 m), `vertexCount` to
   `verts_export` (tolerance 5 %), triangle count to `tris`, and material-name sets exactly.
   That is what `Assets/Editor/UexportLabProbe.cs` implements; it also renders
   `importstd`/`planB`/`planA` screenshots and reports a `dark=%` pixel ratio.
5. **Streaming**: 600–900 prefabs should not all be scene objects from frame 0. Load per grid cell
   around the camera (Addressables or an AssetBundle per `city/props/walls/terrain` group), and keep
   `enableGPUInstancing` off (the SRP Batcher handles the shared materials better).
6. `expect.tsv` exists so a non-Unity consumer (or a human) can diff what was exported without
   parsing the manifest.

---

## 10. Run order on a new blend (do not skip step 1)

```
# 1) audit -- 1-2 min, no export.  Check the category counts before committing 30 min.
... --audit-only --out <out>_audit
     -> audit.json + name_tokens.tsv ; look for landmark:castle ≈ the castle object count
        (v24: 18 227 objects).  If most castle objects land in `city`, add --classify rules
        or extend the landmark keyword list before exporting.

# 2) dry run -- plan only (~1 s after the blend loads).  Shows the cell size and chunk counts.
... --dry-run --chunk-tris 50000 --lod --collision --materials both --cell-size auto

# 3) production
... --out "E:\My World\Blender\export\capital_v2" --chunk-tris 50000 --lod --collision --materials both
```

Peak memory is dominated by opening the blend, not by the export: the lab (3.2 MB, 139 k tris) peaked
at 613 MB. For the 860 MB / 30.6 M-face city expect several GB — run it alone, and watch
`manifest.json → performance.peak_rss_mb` afterwards.

## 11. Verification without Unity
`look/export_fbx.py` is a pure-Python FBX 7.x reader (no bpy, no numpy) — it parses the binary
container, walks `Objects/Model/Geometry`, and prints `unit_scale_factor`, up/front/coord axes,
per-model `Lcl Rotation`/`Scaling`/`Translation`, vertex/poly counts, material names and the raw
vertex bbox:

```
python "E:\My World\Blender\kingdom\look\export_fbx.py" "...\city\chunk_-2_-2.fbx"
```

`export_unity.py --verify all` runs the same reader inside Blender after export and fails loudly
(`verify.ok = false` + a warning) if anything drifts.

Unity-side, without closing anyone's editor: `Tools/UEXPORT/Run Lab Probe` and
`Tools/UEXPORT/Run Axis Probe` (`Assets/Editor/UexportMenu.cs`) call the same entry points as the
batchmode probes and append a full report to `E:\My World\Logs\uexport_probe.log`.

**Why batchmode could not be used on 2026-11-02:** a GUI editor opened the project through Unity Hub
(`Unity.exe -useHub -hubIPC`, pid 11492), and Unity refuses a second instance on the same project
(`Aborting batchmode due to fatal error: It looks like another Unity instance is running with this
project open`). The editor binary for this project is `D:\UnityHub\Editor\Unity.exe` (6000.3.0b1,
revision 0470b869db67) — *not* `D:\Unity\Editor\Tuanjie.exe`, which is a different 2022.3.62t3 install.

---

## 12. Failure modes seen while building this

| symptom | cause | fix in the script |
|---|---|---|
| `bpy_prop_collection: attribute "link" not found` | `bpy.context.view_layer.objects.link()` in 5.2 | `bpy.context.scene.collection.objects.link()` (`link_object()`) |
| "baking 6 unique materials" then "baked 0" | `orphans_purge()` freed materials with no users | pin `use_fake_user` on every material before the export loop |
| `StructRNA of type Object has been removed` | objects dropped twice (per-LOD and at end of chunk) | drop once, tolerate `ReferenceError` |
| `keyword "use_pass_direct" unrecognized` | those are **scene** bake settings, not operator args | set `scene.render.bake.use_pass_direct/indirect` before `bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'})` |
| every file "verify failed" | verification asserted the wrong contract (identity node rotation) | expect `Lcl Rotation ≈ (-90,0,0)`, `Lcl Scaling = (100,100,100)`, and check **net** scale |
| `proc_mem_mb()` always 0 | `GetCurrentProcess()` truncated to 32-bit | `restype = HANDLE` + `argtypes` on `GetProcessMemoryInfo` |
| walls got 2-triangle colliders | 10 % of 12 tris | `--col-min-tris 64` floor |
| plan B tinted everything grey | linked Base Color → socket default | baked-albedo mean per material |
| LODs missing on overflow pieces | overflow was exported on a separate code path | all pieces share one export path |

Operational note: the shared Blender lock was twice held by `blender.exe` processes that had already
finished their work and never exited; `_lock._owner_alive()` only checks the pid, so nothing evicted
them and six agents queued. Check CPU delta + log mtime of the holder before assuming it is working.
`_lock.py` now has a zombie watchdog plus `python look\_lock.py kill|clear`.
