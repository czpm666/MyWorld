# -*- coding: utf-8 -*-
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

REPL = [
    (u'_mat_emit("ci_rgb0", "#0f3a86", 1.05, base="#07142e", rough=0.2)',
     u'_mat_emit("ci_rgb0", "#1250b4", 2.40, base="#0a1c3c", rough=0.2)'),
    (u'_mat_emit("ci_rgb1", "#2f6cc0", 1.30, base="#0d2244", rough=0.2)',
     u'_mat_emit("ci_rgb1", "#3f86e0", 3.00, base="#10294e", rough=0.2)'),
    (u'_mat_emit("ci_rgr0", "#80161f", 0.95, base="#220508", rough=0.2)',
     u'_mat_emit("ci_rgr0", "#a01c26", 2.40, base="#2a060a", rough=0.2)'),
    (u'_mat_emit("ci_rgr1", "#c02a30", 1.20, base="#2e0809", rough=0.2)',
     u'_mat_emit("ci_rgr1", "#d83438", 2.90, base="#380a0b", rough=0.2)'),
    (u'_mat_emit("ci_rgg0", "#b8801a", 1.35, base="#2e2007", rough=0.2)',
     u'_mat_emit("ci_rgg0", "#cf9420", 2.40, base="#382607", rough=0.2)'),
    (u'_mat_emit("ci_rgg1", "#e2ab3c", 1.55, base="#3a2a0c", rough=0.2)',
     u'_mat_emit("ci_rgg1", "#f0bd48", 3.00, base="#452f0c", rough=0.2)'),
    (u'_rose_glass("ci_rgl0", 0.04, 1.05, ROSE_GLASS_D, 20, 3, gold, 11)',
     u'_rose_glass("ci_rgl0", 0.04, 1.05, ROSE_GLASS_D, 14, 2, gold, 11)'),
    (u'_rose_glass("ci_rgl1", 1.05, 2.60, ROSE_GLASS_D, 48, 5, red, 23)',
     u'_rose_glass("ci_rgl1", 1.05, 2.60, ROSE_GLASS_D, 30, 3, red, 23)'),
    (u'_rose_glass("ci_rgl2", 2.60, RO - 0.14, ROSE_GLASS_D, 64, 5, blue, 37)',
     u'_rose_glass("ci_rgl2", 2.60, RO - 0.14, ROSE_GLASS_D, 42, 4, blue, 37)'),
    # triforium：原来是 M["shadow"]（近黑）贴在墙皮后 0.09 m，读成一排黑洞。
    (u'''Z_TRIF_SPR, 0.62, M["shadow"], M["stone_trim"],
                    tracery=0, sill=False, mosaic=False)''',
     u'''Z_TRIF_SPR, 0.62, M["stone_dark"], M["stone_trim"],
                    d_in=0.10, tracery=0, sill=False, mosaic=False)'''),
    (u'for k, y in enumerate((-30.0, -20.0, -10.0, 0.0)):',
     u'for k, y in enumerate((-21.0, -14.0, -7.0, 0.0)):'),
]

for old, new in REPL:
    n = s.count(old)
    assert n == 1, 'anchor %r count=%d' % (old[:40], n)
    s = s.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
