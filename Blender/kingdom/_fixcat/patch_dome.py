# -*- coding: utf-8 -*-
"""Lantern dome: drive the ribs and the concentric rings off the real lathe
profile instead of an estimated (r(u), z(u)) -- the estimate mismatched the
soffit, so the ribs were buried and only black slivers poked through."""
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

A = s.find(u'    # 8 \u6761\u7a79\u9876\u808b')
B = s.find(u'    # \u91d1\u8272\u5f69\u773c\u5708', A)
assert A > 0 and B > A, (A, B)

NEW = u'''    # 8 \u6761\u7a79\u9876\u808b\uff1a\u8def\u5f84\u76f4\u63a5\u53d6\u7a79\u9876\u5256\u9762 prof \u4e0a\u7684\u70b9\u518d\u4e0b\u538b 0.16\uff0c
    # \u4fdd\u8bc1\u8d34\u7740\u62f1\u8179\u751f\u957f\uff1b\u65e7\u7248\u7528\u53c2\u6570\u5316\u4f30\u7684 (r(u), z(u)) \u4e0e\u771f\u5b9e\u5256\u9762
    # \u5dee\u4e86 0.5 m\uff0c\u808b\u5927\u90e8\u57cb\u8fdb\u7a79\u9876\uff0c\u53ea\u5269\u51e0\u70b9\u9ed1\u8fb9\u5192\u51fa\u6765\u3002
    for i in range(8):
        a = TAU * i / 8 + TAU / 16
        ca, sa_ = math.cos(a), math.sin(a)
        pts = [(cx + (pr - 0.02) * ca, cy + (pr - 0.02) * sa_, pz - 0.16)
               for (pr, pz) in prof if pr > 0.02]
        sweep("ci_lr%d" % i, pts, _ribprof(0.26, 0.34, sink=0.17), M["rib_stone"])
    # \u4e24\u9053\u540c\u5fc3\u5706\u73af\uff08\u53d6\u5256\u9762\u91cc\u7684\u771f\u5b9e\u534a\u5f84/\u9ad8\u5ea6\uff09
    for j, (rr2, zz2) in enumerate(((3.96, 38.90), (2.52, 39.32))):
        _lathe("ci_lrg%d" % j,
               [(rr2 + 0.14, zz2 - 0.02), (rr2 + 0.14, zz2 - 0.24),
                (rr2 - 0.14, zz2 - 0.24), (rr2 - 0.14, zz2 - 0.02)],
               M["rib_stone"], 44, Ts(cx, cy, 0.0), False, False)
'''
s = s[:A] + NEW + s[B:]

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
