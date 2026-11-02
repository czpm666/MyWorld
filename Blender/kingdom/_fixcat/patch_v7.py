# -*- coding: utf-8 -*-
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

REPL = [
    # mortar joints were ~30 % darker than the block: at 8 m every course reads
    # as a grout line and the whole interior looks tiled. Raise the joint value
    # so it reads as dressed ashlar with hairline joints.
    (u'K.mat_stone("ci_stone", "#cfc8b7", "#a9a292", "#e6e0d0", 2.4)',
     u'K.mat_stone("ci_stone", "#cfc8b7", "#bcb5a4", "#e6e0d0", 2.4)'),
    (u'K.mat_stone("ci_stone_warm", "#d6cdb7", "#b0a690", "#ece4cf", 2.0)',
     u'K.mat_stone("ci_stone_warm", "#d6cdb7", "#c2b8a2", "#ece4cf", 2.0)'),
    (u'K.mat_stone("ci_stone_dark", "#a49d8c", "#827c6c", "#c4bdac", 2.8)',
     u'K.mat_stone("ci_stone_dark", "#a49d8c", "#918b7b", "#c4bdac", 2.8)'),
    (u'K.mat_stone("ci_stone_trim", "#ddd6c6", "#b7b0a1", "#f2ecdd", 3.2)',
     u'K.mat_stone("ci_stone_trim", "#ddd6c6", "#c9c2b3", "#f2ecdd", 3.2)'),
    (u'K.mat_stone("ci_stone_vous", "#e2dccb", "#bdb6a5", "#f6f0e2", 4.0)',
     u'K.mat_stone("ci_stone_vous", "#e2dccb", "#cfc8b7", "#f6f0e2", 4.0)'),
    (u'K.mat_stone("ci_floor", "#bdb099", "#8f846f", "#d8cdb6", 1.5)',
     u'K.mat_stone("ci_floor", "#bdb099", "#a99e88", "#d8cdb6", 1.5)'),
    (u'K.mat_stone("ci_floor_l", "#d3c7ad", "#a89d85", "#ebe1ca", 1.5)',
     u'K.mat_stone("ci_floor_l", "#d3c7ad", "#c0b59d", "#ebe1ca", 1.5)'),
    (u'K.mat_stone("ci_floor_d", "#8d8373", "#6a6356", "#a79d8e", 1.5)',
     u'K.mat_stone("ci_floor_d", "#8d8373", "#7d7669", "#a79d8e", 1.5)'),
]

for old, new in REPL:
    n = s.count(old)
    assert n == 1, 'anchor %r count=%d' % (old[:40], n)
    s = s.replace(old, new)

# aisle fills: the side aisles render as pure black holes at the frame edges
ANCH = u'''                          1500.0, (0.97, 0.94, 0.88), 5.4, 3.6))
    return out
'''
assert s.count(ANCH) == 1
ADD = u'''                          1500.0, (0.97, 0.94, 0.88), 5.4, 3.6))
    # \u4fa7\u5eca\u8865\u5149\uff1a\u8179\u5ed6\u4e0b\u65b9\u7684\u4fa7\u5eca\u5728\u5e7f\u89d2\u91cc\u662f\u4e00\u7247\u6b7b\u9ed1
    for sx in (-1, 1):
        for yy in (-26.0, -8.0, 20.0):
            out.append(_light("ci_L_ai%d%d" % (sx, int(yy)), "AREA",
                              (sx * 11.7, yy, 9.6), (sx * 9.0, yy + 3.0, 3.0),
                              520.0, (1.0, 0.90, 0.74), 4.2, 3.0))
    return out
'''
s = s.replace(ANCH, ADD)

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
