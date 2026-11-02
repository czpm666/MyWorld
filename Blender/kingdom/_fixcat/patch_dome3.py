# -*- coding: utf-8 -*-
"""The dome was lathed with close_bottom=True, which puts a flat disc across the
drum at the rim plane -- that disc is the pale 'ceiling' we see from below and it
hides the ribs entirely."""
import io
import py_compile

P = r'E:\My World\Blender\kingdom\hd_cathedral_int.py'
s = io.open(P, encoding='utf-8').read()

old = u'    _lathe("ci_ld", prof, M["stone_warm"], 24, Ts(cx, cy, 0.0))'
new = u'    _lathe("ci_ld", prof, M["stone_warm"], 24, Ts(cx, cy, 0.0), False, False)'
assert s.count(old) == 1
s = s.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
py_compile.compile(P, doraise=True)
print('OK bytes=%d lines=%d' % (len(s.encode('utf-8')), s.count('\n') + 1))
