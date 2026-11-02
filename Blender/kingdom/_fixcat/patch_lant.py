# -*- coding: utf-8 -*-
"""Replace the lantern drum glazing block (8 axis-aligned boxes -> 8 curved sectors)."""
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

A = '    # 8 \u6839\u7a97\u95f4\u67f1'
B = '    # \u4e0a\u73af'
a = s.find(A)
b = s.find(B, a)
assert a > 0, 'anchor A missing'
assert b > a, 'anchor B missing'

NEW = u'''    # 8 \u6839\u7a97\u95f4\u67f1 + 8 \u6247\u66f2\u9762\u73bb\u7483
    # \u65e7\u7248\u662f 8 \u4e2a\u8f74\u5bf9\u9f50\u76d2\u5b50\uff081.30 m \u5bbd\uff0c\u5374\u653e\u5728 3.69 m
    # \u5f27\u957f\u7684\u8de8\u4e2d\uff09\uff0c\u9f13\u5ea7\u5468\u957f 29.5 m \u91cc\u53ea\u76d6\u4f4f 10.4 m\uff0c
    # \u5269\u4e0b\u5168\u662f\u901a\u5411\u5929\u7a7a\u7684\u9ed1\u7f1d\u3002
    zw0, zw1 = z0 + 1.55, z1 - 1.35

    def _sector(name, ra, rb, za, zb, q0, q1, n, mat):
        vs = []
        for k in range(n + 1):
            q = q0 + (q1 - q0) * k / n
            cq, sq = math.cos(q), math.sin(q)
            vs += [(cx + ra * cq, cy + ra * sq, za), (cx + rb * cq, cy + rb * sq, za),
                   (cx + rb * cq, cy + rb * sq, zb), (cx + ra * cq, cy + ra * sq, zb)]
        fs = []
        for k in range(n):
            b0 = 4 * k
            for j in range(4):
                j2 = (j + 1) % 4
                fs.append((b0 + j, b0 + j2, b0 + 4 + j2, b0 + 4 + j))
        fs.append((3, 2, 1, 0))
        fs.append((4 * n, 4 * n + 1, 4 * n + 2, 4 * n + 3))
        _polyv(name, vs, fs, mat, True)

    half_p = math.atan2(0.31, r0)
    for i in range(8):
        a = TAU * i / 8
        mx, my = cx + r0 * math.cos(a), cy + r0 * math.sin(a)
        _box("ci_lp%d" % i, Ts(mx + 0.15 * math.cos(a), my + 0.15 * math.sin(a),
                               0.5 * (zw0 + zw1)),
             (0.62, 0.62, zw1 - zw0), M["stone_warm"], bev=0.02)
        _box("ci_lc%d" % i, Ts(mx + 0.15 * math.cos(a), my + 0.15 * math.sin(a), zw0),
             (0.80, 0.80, 0.16), M["stone_trim"], bev=0.02)
        _sector("ci_lg%d" % i, r0 + 0.01, r0 + 0.10, zw0 + 0.05, zw1 - 0.05,
                a + half_p + 0.006, a + TAU / 8 - half_p - 0.006, 14, M["glass_gold"])
    # \u73bb\u7483\u4e0b\u7684\u7a97\u53f0\u7ebf\u811a + \u73bb\u7483\u4e0a\u7684\u5916\u6311\u6a90\u53e3
    _lathe("ci_lgs", [(r0 - 0.30, zw0 - 0.13), (r1 + 0.08, zw0 - 0.13),
                      (r1 + 0.08, zw0 + 0.06), (r0 - 0.10, zw0 + 0.06),
                      (r0 - 0.30, zw0 - 0.13)], M["stone_trim"], 32,
           Ts(cx, cy, 0.0), False, False)
    _lathe("ci_lgc", [(r0 - 0.36, zw1 - 0.05), (r1 + 0.30, zw1 - 0.05),
                      (r1 + 0.42, zw1 + 0.10), (r1 + 0.42, zw1 + 0.30),
                      (r0 - 0.24, zw1 + 0.30), (r0 - 0.24, zw1 + 0.10),
                      (r0 - 0.36, zw1 - 0.05)], M["stone_warm"], 32,
           Ts(cx, cy, 0.0), False, False)
'''

s = s[:a] + NEW + s[b:]
io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
