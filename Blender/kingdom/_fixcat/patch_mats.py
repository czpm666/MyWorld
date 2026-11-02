# -*- coding: utf-8 -*-
"""One-shot patch: give vault webs a plaster material and ribs a fine ashlar.

The "corrugated cardboard" look on the vault soffit is not geometry any more:
mat_stone feeds a Brick texture the vector (x+y, z), so on a domed web the
courses become concentric rings and the joints become radial spokes.
"""
import io
import os
import py_compile
import shutil

SRC = r"E:\My World\Blender\kingdom\hd_cathedral_int.py"
TMP = r"E:\My World\Blender\kingdom\_fixcat\_patched.py"

s = io.open(SRC, encoding="utf-8").read()

NEW_MATS = (
    '    M["stone_voussoir"] = K.mat_stone("ci_stone_vous", "#e2dccb", "#bdb6a5", "#f6f0e2", 4.0)\n'
)
NEW_MATS_OUT = (
    '    M["stone_voussoir"] = K.mat_stone("ci_stone_vous", "#e2dccb", "#bdb6a5", "#f6f0e2", 4.0)\n'
    '    # 拱腹：mat_stone 的砖纹是 (x+y, z) 投影，铺在穹面上的砖缝会变成同心圆\n'
    '    # 和放射线，远看就是"瓦楞纸"。拱腹改用抹面（只有噪声+凹凸），肋用更细的石纹。\n'
    '    M["vault_web"] = K.mat_plaster("ci_vault_web", "#d6ceba", "#b9b09b", 3.0)\n'
    '    M["rib_stone"] = K.mat_stone("ci_stone_rib", "#bdb5a3", "#968e7f", "#d6cfbe", 6.5)\n'
)

SUBS = [
    # --- vault webs -> plaster ---
    ('vault_sheet("ci_vb" + tag, x0, x1, y0, y1, zs, ht, hr, hc, 30, 14, M["stone_warm"])',
     'vault_sheet("ci_vb" + tag, x0, x1, y0, y1, zs, ht, hr, hc, 30, 14, M["vault_web"])'),
    ('vault_sheet("ci_av" + tag, x0, x1, y0, y1, zs, ht, hr, hc, 12, 10, M["stone"])',
     'vault_sheet("ci_av" + tag, x0, x1, y0, y1, zs, ht, hr, hc, 12, 10, M["vault_web"])'),
    ('Z_TR_SPRING, Z_TR_HT, Z_TR_HR, Z_TR_CROWN - Z_TR_SPRING, 14, 12, M["stone_warm"])',
     'Z_TR_SPRING, Z_TR_HT, Z_TR_HR, Z_TR_CROWN - Z_TR_SPRING, 14, 12, M["vault_web"])'),
    ('_polyv("ci_xsph", verts, faces, M["stone_warm"], True)',
     '_polyv("ci_xsph", verts, faces, M["vault_web"], True)'),
    ('_polyv("ci_apdome", verts, faces, M["stone_warm"], True)',
     '_polyv("ci_apdome", verts, faces, M["vault_web"], True)'),
    # --- ribs -> fine ashlar ---
    ('sweep("ci_vw%s_%d" % (tag, int(sx)), pts, _ribprof(0.28, 0.36), M["stone_dark"])',
     'sweep("ci_vw%s_%d" % (tag, int(sx)), pts, _ribprof(0.28, 0.36), M["rib_stone"])'),
    ('sweep("ci_ta" + tag, pts, _ribprof(w, d), M["stone_trim"])',
     'sweep("ci_ta" + tag, pts, _ribprof(w, d), M["rib_stone"])'),
    ('sweep("ci_at%s_%d" % (tag, int(yy * 10)), pts, _ribprof(0.34, 0.30), M["stone_dark"])',
     'sweep("ci_at%s_%d" % (tag, int(yy * 10)), pts, _ribprof(0.34, 0.30), M["rib_stone"])'),
    ('_ribprof(0.42, 0.38),\n                      M["stone_trim"])',
     '_ribprof(0.42, 0.38),\n                      M["rib_stone"])'),
    ('sweep("ci_lr%d" % i, pts, _ribprof(0.20, 0.20), M["stone_trim"])',
     'sweep("ci_lr%d" % i, pts, _ribprof(0.20, 0.20), M["rib_stone"])'),
    ('sweep("ci_apr%d" % i, pts, _ribprof(0.26, 0.30), M["stone_trim"])',
     'sweep("ci_apr%d" % i, pts, _ribprof(0.26, 0.30), M["rib_stone"])'),
    ('(px, py), (cx, cy), 0.34, 0.42, M["stone_dark"], 10)',
     '(px, py), (cx, cy), 0.34, 0.42, M["rib_stone"], 10)'),
    ('(0.0, y0), (0.0, y1), 0.30, 0.34, M["stone_dark"], 8)',
     '(0.0, y0), (0.0, y1), 0.30, 0.34, M["rib_stone"], 8)'),
    ('(px, py), (cx, cy), 0.24, 0.28, M["stone_dark"], 8)',
     '(px, py), (cx, cy), 0.24, 0.28, M["rib_stone"], 8)'),
    ('0.32, 0.40, M["stone_dark"], 8)', '0.32, 0.40, M["rib_stone"], 8)'),
    ('boss("ci_vboss" + tag, 0.0, cy, Z_CROWN, 0.46, M["stone_trim"], M["gold"])',
     'boss("ci_vboss" + tag, 0.0, cy, Z_CROWN, 0.46, M["rib_stone"], M["gold"])'),
    ('boss("ci_ab" + tag, cx, cy, Z_AIS_CROWN, 0.28, M["stone_trim"])',
     'boss("ci_ab" + tag, cx, cy, Z_AIS_CROWN, 0.28, M["rib_stone"])'),
    ('boss("ci_tb%d%d" % (sx, k), cx, cy, Z_TR_CROWN, 0.40, M["stone_trim"], M["gold"])',
     'boss("ci_tb%d%d" % (sx, k), cx, cy, Z_TR_CROWN, 0.40, M["rib_stone"], M["gold"])'),
    ('boss("ci_apboss", cen.x, cen.y, zc, 0.44, M["stone_trim"], M["gold"])',
     'boss("ci_apboss", cen.x, cen.y, zc, 0.44, M["rib_stone"], M["gold"])'),
]

assert s.count(NEW_MATS) == 1, "anchor for new materials not unique"
s = s.replace(NEW_MATS, NEW_MATS_OUT)
for old, new in SUBS:
    n = s.count(old)
    assert n == 1, "%d hits for %r" % (n, old[:60])
    s = s.replace(old, new)

io.open(TMP, "w", encoding="utf-8", newline="\n").write(s)
py_compile.compile(TMP, doraise=True)
shutil.copyfile(TMP, SRC)
print("patched OK, %d bytes, %d lines" % (len(s), s.count("\n") + 1))
