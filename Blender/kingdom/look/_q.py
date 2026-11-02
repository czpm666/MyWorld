import re
import sys

g = open('capital_hd_glue.py', encoding='utf-8').read()
i = g.index('def hd_materials')
print(g[i:i + 700])
t = open('hd_streetlife.py', encoding='utf-8').read()
ks = set(re.findall(r'MAT\[["\']([A-Za-z0-9_.]+)["\']\]', t))
print('MAT[...] keys:', sorted(ks))
ks2 = set(re.findall(r'MAT\.get\(["\']([A-Za-z0-9_.]+)["\']', t))
print('MAT.get keys:', sorted(ks2))
