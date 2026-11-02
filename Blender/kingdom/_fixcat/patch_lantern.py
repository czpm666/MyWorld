# -*- coding: utf-8 -*-
"""Lantern: coffered dome soffit (thicker ribs + concentric rings + gold oculus
rim) and a re-balanced interior light so the soffit is not a blown-out disc."""
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

old = u'''    # 8 \u6761\u7a79\u9876\u808b
    for i in range(8):
        a = TAU * i / 8 + TAU / 16
        pts = [(cx + (r1 * (1.0 - u * 0.92)) * math.cos(a),
                cy + (r1 * (1.0 - u * 0.92)) * math.sin(a),
                z1 + 1.40 * (u ** 0.9)) for u in
               [k / 7 for k in range(8)]]
        sweep("ci_lr%d" % i, pts, _ribprof(0.20, 0.20), M["rib_stone"])'''
new = u'''    # 8 \u6761\u7a79\u9876\u808b\uff08\u52a0\u7c97\u3001\u5f80\u4e0b\u6302\uff0c\u5426\u5219\u88ab\u70b9\u5149\u6e85\u767d\u770b\u4e0d\u89c1\uff09
    for i in range(8):
        a = TAU * i / 8 + TAU / 16
        pts = [(cx + (r0 + 0.06) * (1.0 - 0.955 * u) * math.cos(a),
                cy + (r0 + 0.06) * (1.0 - 0.955 * u) * math.sin(a),
                z1 + 1.40 * (min(1.0, u / 0.955) ** 0.9) - 0.07) for u in
               [k / 11 for k in range(12)]]
        sweep("ci_lr%d" % i, pts, _ribprof(0.30, 0.30, sink=0.15), M["rib_stone"])
    # 两道同心圆环，把穹顶分成三圈（不然拱腹是一整片无尺度的光面）
    for j, uu in enumerate((0.34, 0.66)):
        rr2 = (r0 + 0.06) * (1.0 - 0.955 * uu)
        zz2 = z1 + 1.40 * (uu ** 0.9) - 0.07
        _lathe("ci_lrg%d" % j,
               [(rr2 + 0.13, zz2), (rr2 + 0.13, zz2 - 0.18),
                (rr2 - 0.13, zz2 - 0.18), (rr2 - 0.13, zz2)],
               M["rib_stone"], 40, Ts(cx, cy, 0.0), False, False)
    # \u91d1\u8272\u5f69\u773c\u5708
    _lathe("ci_lor", [(0.50, Z_LANT_DOME - 0.32), (0.78, Z_LANT_DOME - 0.34),
                      (0.78, Z_LANT_DOME - 0.20), (0.50, Z_LANT_DOME - 0.18)],
           M["gold"], 28, Ts(cx, cy, 0.0), False, False)'''
assert s.count(old) == 1
s = s.replace(old, new)

old2 = u'''        ("POINT", (0.0, 7.5, 34.4), (0.0, 7.5, 31.0), 1200.0, (1.0, 0.93, 0.80), 0.0, 0.0),'''
if s.count(old2) == 1:
    s = s.replace(old2, u'''        ("AREA", (0.0, 7.5, 32.30), (0.0, 7.5, 36.0), 900.0, (1.0, 0.93, 0.80), 4.2, 4.2),''')

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
