# -*- coding: utf-8 -*-
"""West wall: add a five-bay blind arcade under the rose + a string course,
so the rose camera no longer frames 40 % blank wall.  ASCII anchors only."""
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

old = u'    _rose_ring(M, O, U, V, N, th)\n'
assert s.count(old) == 1, s.count(old)

new = old + u'''    # \u7396\u73ab\u7a97\u4e0b\u65b9\u7684\u5e95\u5c42\u5899\u9762\uff1a\u4e94\u8fde\u76f2\u62f1 + \u5f26\u5e26\u7ebf\uff0c
    # \u5426\u5219 rose \u673a\u4f4d\u4e0b\u534a\u5e45\u662f\u4e00\u7247\u7a7a\u767d\u7816\u5899\u3002
    def _blind(nm, aa0, aa1, zs, zspr, rise):
        prism2d(nm + "_in", O, U, V, N, -0.055, -0.012,
                lancet(aa0, aa1, zs, zspr, rise, inset=0.14), M["stone_dark"])
        arch_band(nm + "_ar", O, U, V, N, aa0, aa1, zspr, rise, 0.13,
                  -0.105, 0.0, M["stone_trim"], 14)
        for k, (ja, jb) in enumerate(((aa0 - 0.13, aa0), (aa1, aa1 + 0.13))):
            prism2d(nm + "_j%d" % k, O, U, V, N, -0.105, 0.0,
                    [(ja, zs), (jb, zs), (jb, zspr + 0.03), (ja, zspr + 0.03)],
                    M["stone_trim"])
        prism2d(nm + "_sl", O, U, V, N, -0.15, 0.0,
                [(aa0 - 0.24, zs - 0.17), (aa1 + 0.24, zs - 0.17),
                 (aa1 + 0.24, zs), (aa0 - 0.24, zs)], M["stone_trim"])

    for i in range(5):
        cx_ = -2.0 * 3.388 + i * 3.388
        _blind("ci_wbl%d" % i, cx_ - 1.245, cx_ + 1.245, 8.90, 15.90, 1.55)
    course("ci_wsc", O, U, V, N, -hw + 0.02, hw - 0.02, 20.28, 0.20,
           out=0.20, mat=M["stone_trim"], up=0.10)
    course("ci_wsc2", O, U, V, N, -hw + 0.02, hw - 0.02, 8.42, 0.34,
           out=0.16, mat=M["stone_trim"], up=0.10)
'''
s = s.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
