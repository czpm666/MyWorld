# -*- coding: utf-8 -*-
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

REPL = [
    # rib_stone: brick 1.5/6.5=0.23 m wide on a 0.34 m rib -> braided-rope look.
    # scale 0.40 -> 3.75 x 1.88 m blocks, a rib sits inside one dressed stone.
    (u'M["rib_stone"] = K.mat_stone("ci_stone_rib", "#bdb5a3", "#968e7f", "#d6cfbe", 6.5)',
     u'M["rib_stone"] = K.mat_stone("ci_stone_rib", "#b6ae9c", "#7d7666", "#ded7c5", 0.40)'),
    # heavier diagonal ribs
    (u'(px, py), (cx, cy), 0.34, 0.42, M["rib_stone"], 10)',
     u'(px, py), (cx, cy), 0.46, 0.42, M["rib_stone"], 10)'),
    (u'              (0.0, y0), (0.0, y1), 0.30, 0.34, M["rib_stone"], 8)',
     u'              (0.0, y0), (0.0, y1), 0.34, 0.34, M["rib_stone"], 8)'),
    # 31 m hanging rod reads as a black wire across every wide shot
    (u'_cyl(tag + "_rod", Ts(x, y, 0.5 * (zh + ztop)), 0.032, ztop - zh, M["iron"], 8)',
     u'_cyl(tag + "_rod", Ts(x, y, 0.5 * (zh + ztop)), 0.014, ztop - zh, M["iron"], 8)'),
]

for old, new in REPL:
    n = s.count(old)
    assert n == 1, 'anchor %r count=%d' % (old[:40], n)
    s = s.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
