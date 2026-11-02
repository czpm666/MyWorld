# -*- coding: utf-8 -*-
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

old = u'''    prof = [(r0 + 0.02, z1), (r1, z1), (r1 * 0.96, z1 + 0.25), (r1 * 0.80, z1 + 0.72),
            (r1 * 0.52, z1 + 1.14), (r1 * 0.24, z1 + 1.36), (0.0, Z_LANT_DOME)]
    _lathe("ci_ld", prof, M["stone_warm"], 24, Ts(cx, cy, 0.0))
    _lathe("ci_ld2", [p for p in prof][::-1] + [(r0 * 0.5, Z_LANT_DOME - 0.04)],
           M["stone_trim"], 24, Ts(cx, cy, 0.0), False, False)'''
new = u'''    # \u7a79\u9876\u3002\u8d77\u62f1\u5904\u6bd4\u4e0a\u73af\u9876\u9762\u4f4e 0.05 m\uff0c\u5426\u5219\u7a79\u9876\u8fb9\u7f18\u7684\u73af\u5f62\u9762
    # \u548c ci_lt1 \u7684\u9876\u9762\u5b8c\u5168\u5171\u9762\u2014\u2014\u4ece\u4e0b\u9762\u4fef\u89c6\u5c31\u662f\u4e00\u5708\u9ed1\u6591\u3002
    # \u539f\u4f5c\u8005\u8fd8\u6709\u4e00\u4e2a ci_ld2\uff08\u5256\u9762\u53cd\u5411\u91cd\u590d + \u4e00\u4e2a\u8df3\u70b9\u3001\u6750\u8d28\u4e0d\u540c\uff09\uff0c
    # \u548c ci_ld \u51e0\u4e4e\u5171\u9762\uff0c\u662f\u62f1\u8179\u4e0a\u90a3\u5c42\u300c\u9ebb\u70b9\u300d\u7684\u6765\u6e90\uff0c\u5df2\u5220\u9664\u3002
    prof = [(r0 - 0.06, z1 - 0.05), (r1 + 0.02, z1 - 0.05),
            (r1 * 0.96, z1 + 0.25), (r1 * 0.80, z1 + 0.72),
            (r1 * 0.52, z1 + 1.14), (r1 * 0.24, z1 + 1.36), (0.0, Z_LANT_DOME)]
    _lathe("ci_ld", prof, M["stone_warm"], 24, Ts(cx, cy, 0.0))'''
assert s.count(old) == 1
s = s.replace(old, new)

old2 = u'''        pts = [(cx + (pr - 0.02) * ca, cy + (pr - 0.02) * sa_, pz - 0.16)
               for (pr, pz) in prof if pr > 0.02]
        sweep("ci_lr%d" % i, pts, _ribprof(0.26, 0.34, sink=0.17), M["rib_stone"])'''
new2 = u'''        pts = [(cx + (pr - 0.02) * ca, cy + (pr - 0.02) * sa_, pz - 0.10)
               for (pr, pz) in prof if pr > 0.02]
        sweep("ci_lr%d" % i, pts, _ribprof(0.30, 0.44, sink=0.24), M["rib_stone"])'''
assert s.count(old2) == 1
s = s.replace(old2, new2)

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
