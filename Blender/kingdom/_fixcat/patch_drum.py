# -*- coding: utf-8 -*-
"""Lantern drum: cool daylight glass + two stone transom rings, so the drum reads
as glazing instead of a solid orange bulb (it was one flat glass_gold sector)."""
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

old = u'''        _sector("ci_lg%d" % i, r0 + 0.01, r0 + 0.10, zw0 + 0.05, zw1 - 0.05,
                a + half_p + 0.006, a + TAU / 8 - half_p - 0.006, 14, M["glass_gold"])'''
new = u'''        _sector("ci_lg%d" % i, r0 + 0.01, r0 + 0.10, zw0 + 0.05, zw1 - 0.05,
                a + half_p + 0.006, a + TAU / 8 - half_p - 0.006, 14, M["glass"])
    # \u73bb\u7483\u4e0a\u7684\u4e24\u9053\u6a2a\u6863\uff1a\u6ca1\u6709\u5b83\u6574\u5708\u73bb\u7483\u5728 8 m \u5916\u5c31\u662f
    # \u4e00\u4e2a\u5e73\u6d82\u7684\u6a59\u9ec4\u8272\u5149\u73af\u3002
    for j in range(2):
        zz = zw0 + (zw1 - zw0) * (j + 1) / 3.0
        _lathe("ci_lgt%d" % j,
               [(r0 - 0.03, zz - 0.07), (r0 + 0.14, zz - 0.07),
                (r0 + 0.14, zz + 0.07), (r0 - 0.03, zz + 0.07)],
               M["stone_trim"], 32, Ts(cx, cy, 0.0), False, False)'''
assert s.count(old) == 1
s = s.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
