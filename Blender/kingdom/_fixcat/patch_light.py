# -*- coding: utf-8 -*-
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

ANCHOR = u'''    out.append(_light("ci_L_cross", "AREA", (0.0, 7.5, 28.6), (0.0, 7.5, 2.0),
                      900.0, (0.88, 0.92, 1.0), 6.0, 6.0))
'''
assert s.count(ANCHOR) == 1, 'anchor count %d' % s.count(ANCHOR)

ADD = ANCHOR + u'''    # \u91c7\u5149\u5854\u5185\u90e8\uff1a\u9f13\u5ea7\u73bb\u7483\u4e0e\u7a79\u9876\u5185\u9762\u9700\u8981\u6709\u5149\uff0c
    # \u5426\u5219\u4ece\u4ea4\u53c9\u90e8\u62ac\u5934\u770b\u4e0a\u53bb\u662f\u4e00\u4e2a\u9ed1\u6d1e\u3002
    out.append(_light("ci_L_lant", "POINT", (0.0, 7.5, 34.4), (0.0, 7.5, 31.0),
                      1200.0, (1.0, 0.93, 0.80)))
'''
s = s.replace(ANCHOR, ADD)
io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
