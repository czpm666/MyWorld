# -*- coding: utf-8 -*-
"""Choir stalls: replace the 4-post flat-awning look with a continuous back screen
plus a canopy that grows out of the back (the "market stall" read came from the
freestanding posts holding a flat slab at head height)."""
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

A = s.find(u'    # \u9760\u80cc\uff1a\u4e3b\u4f53 + 3 \u5757\u51f9\u5d4c\u677f')
B = s.find(u'def _choir_stalls', A)
assert A > 0 and B > A, 'anchors %d %d' % (A, B)

NEW = u'''    # \u9760\u80cc\uff1a\u4e0b\u6bb5 + \u4e0a\u6bb5\uff0c\u4e00\u76f4\u9876\u5230\u534e\u76d6\uff0c\u6210\u4e3a\u8fde\u7eed\u7684\u80cc\u5c4f
    # \uff08\u65e7\u7248\u9760\u80cc\u53ea\u5230 z=1.51\uff0c\u4e0a\u9762\u5230\u534e\u76d6 2.36 \u4e4b\u95f4\u662f\u7a7a\u6c14\uff0c
    #  \u534e\u76d6\u53c8\u9760\u56db\u6839\u72ec\u7acb\u67f1\u5b50\u6491\u7740\uff0c\u6240\u4ee5\u6574\u6392\u8bfb\u6210\u5e02\u96c6\u644a\u4f4d\u3002\uff09
    _box(tag + "_bk", Ts(xbk, y, 0.72), (0.12, 0.84, 0.95), M["wood"], bev=0.012)
    _box(tag + "_bk2", Ts(xbk, y, 1.83), (0.12, 0.84, 1.22), M["wood"], bev=0.012)
    for j, zz in enumerate((0.55, 0.82, 1.09, 1.45, 1.74, 2.03)):
        _box(tag + "_bp%d" % j, Ts(xbk - sx * 0.065, y, zz), (0.020, 0.66, 0.20),
             M["wood_light"], bev=0.005)
    _box(tag + "_bt", Ts(xout - sx * 0.05, y, 1.225), (0.22, 0.90, 0.075),
         M["wood_light"], bev=0.012)
    _box(tag + "_bcr", Ts(xout - sx * 0.11, y, 2.478), (0.34, 0.92, 0.10),
         M["wood_light"], bev=0.012)
    # \u4fa7\u9694\u677f + \u6276\u624b\uff08\u6bcf\u4e2a\u5ea7\u4f4d\u53ea\u753b +y \u4e00\u4fa7\uff0c\u9996\u5ea7\u518d\u8865 -y \u4e00\u4fa7\uff09
    sides = [y + 0.43] + ([y - 0.43] if first else [])
    for yy in sides:
        _box(tag + "_sd", Ts(0.5 * (xin + xout), yy, 0.46), (1.62, 0.055, 0.52),
             M["wood_dark"], bev=0.010)
        _box(tag + "_sd2", Ts(xout - sx * 0.52, yy, 1.62), (0.96, 0.05, 1.34),
             M["wood_dark"], bev=0.008)
        _box(tag + "_ar", Ts(xse, yy, 0.755), (0.72, 0.10, 0.075),
             M["wood_light"], bev=0.012)
        _sph(tag + "_av", Ts(xse - sx * 0.36, yy, 0.755), 0.070, M["wood_light"], 8, 6)
    # \u534e\u76d6\uff1a\u4ece\u80cc\u5c4f\u9876\u5411\u4e2d\u592e\u503e\u659c\uff0c\u524d\u7f18\u538b\u7ebf\u811a\uff0c\u4e0b\u9762\u4e24\u9053\u6258\u89d2
    zt0, zt1 = 2.55, 2.30
    xa, xb2 = xout - sx * 0.02, xout - sx * 1.02
    _polyv(tag + "_ca", [(xa, y - 0.43, zt0), (xa, y + 0.43, zt0),
                         (xb2, y + 0.43, zt1), (xb2, y - 0.43, zt1),
                         (xa, y - 0.43, zt0 - 0.10), (xa, y + 0.43, zt0 - 0.10),
                         (xb2, y + 0.43, zt1 - 0.10), (xb2, y - 0.43, zt1 - 0.10)],
           [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2),
            (2, 6, 7, 3), (3, 7, 4, 0)], M["wood_dark"], False)
    _box(tag + "_cf", Ts(xb2 + sx * 0.02, y, zt1 - 0.04), (0.075, 0.88, 0.16),
         M["wood_light"], bev=0.010)
    for j, yy in enumerate((y - 0.24, y + 0.24)):
        _box(tag + "_cbr%d" % j, Ts(xout - sx * 0.54, yy, 2.06, 0.0, sx * 0.34, 0.0),
             (0.78, 0.06, 0.075), M["wood_dark"])
    _lathe(tag + "_cp", [(0.0, 0.0), (0.075, -0.02), (0.10, -0.14), (0.055, -0.24),
                         (0.0, -0.27)], M["wood_light"], 10, Ts(xb2 + sx * 0.10, y, zt1 - 0.12))
    # \u524d\u51e0\uff08\u8dea\u819d\u7528\uff09
    _box(tag + "_dk", Ts(xin + sx * 0.35, y, 0.66), (0.24, 0.74, 0.06),
         M["wood"], bev=0.010)
    _box(tag + "_dl", Ts(xin + sx * 0.46, y, 0.42), (0.06, 0.22, 0.60), M["wood_dark"])


'''
s = s[:A] + NEW + s[B:]

# drop the freestanding canopy posts / front beam
C = s.find(u'        # \u534e\u76d6\u524d\u67f1\u6bcf 4 \u4e2a\u5ea7\u4f4d\u4e00\u6839')
D = s.find(u'def _rood_screen', C)
assert C > 0 and D > C, 'anchor C/D %d %d' % (C, D)
s = s[:C] + u'\n' + s[D:]

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
