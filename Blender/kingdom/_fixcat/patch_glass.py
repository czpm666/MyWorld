# -*- coding: utf-8 -*-
"""Stained glass: make the colour field cohere in ~0.47 m patches instead of
per-cell random salt-and-pepper, and drop the accent share from 44 % to 28 %."""
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

# 1) signature + docstring + palette setup
old1 = u'''def _glass_mosaic(name, O, U, V, N, poly, d0, d1, cell, mats, seed=0,
                  bpoly=None, bmat=None):
    """彩色玻璃马赛克：把窗口多边形切成小格，每格随机一种玻璃，
    格与格之间留 1.3 cm 铅条缝（背后是深色玻璃底板）。每个颜色合成一个
    网格对象，避免上百个碎对象。

    给了 bpoly/bmat 时，落在 bpoly 之外的格子统一用 bmat——这就是窗口四周
    那道彩色边饰，真实花窗都有，没有它整扇窗会读成一块彩色格子布。
    """
    rr = random.Random(seed)
    allm = list(mats)
    nb = None
    if bmat is not None:
        nb = len(allm)
        allm.append(bmat)'''
new1 = u'''def _glass_mosaic(name, O, U, V, N, poly, d0, d1, cell, mats, seed=0,
                  bpoly=None, bmat=None, blk=3):
    """彩色玻璃：把窗口多边形切成小格，格与格之间留 1.3 cm 铅条缝（背后
    是深色玻璃底板）。每个颜色合成一个网格对象，避免上百个碎对象。

    给了 bpoly/bmat 时，落在 bpoly 之外的格子统一用 bmat——这就是窗口四周
    那道彩色边饰，真实花窗都有，没有它整扇窗会读成一块彩色格子布。

    取色不是逐格随机的：0.155 m 的格子逐格换色，3 m 外就散成"彩色纸屑"。
    改成每 blk x blk 格共用同一张玻璃（约 0.47 m），颜色由格子坐标哈希决定，
    于是色块成片，接近中世纪的 pot-metal 玻璃。
    """
    rr = random.Random(seed)
    allm = list(mats)
    nb = None
    if bmat is not None:
        nb = len(allm)
        allm.append(bmat)'''
assert s.count(old1) == 1
s = s.replace(old1, new1)

# 2) deterministic block colour
old2 = u'''            if nb is not None and not _pt_in_poly(ca, cz, bpoly):
                k = nb
            else:
                k = rr.randrange(len(mats))'''
new2 = u'''            if nb is not None and not _pt_in_poly(ca, cz, bpoly):
                k = nb
            else:
                h = ((i // blk) * 73856093) ^ ((j // blk) * 19349663) ^ (seed * 83492791)
                h = (h ^ (h >> 13)) & 0x7FFFFFFF
                h = (h * 1274126177) & 0x7FFFFFFF
                k = h % len(mats)'''
assert s.count(old2) == 1
s = s.replace(old2, new2)

# 3) rebalance the palette: 18 dominant / 4 acc1 / 2 acc2 / 1 gold  (72/16/8/4 %)
old3 = u'''        pal = [glass, glass, glass, glass, glass, acc1, acc1, acc2, m["glass_gold"]]'''
new3 = u'''        pal = ([glass] * 18 + [acc1] * 4 + [acc2] * 2 + [m["glass_gold"]])'''
assert s.count(old3) == 1
s = s.replace(old3, new3)

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
