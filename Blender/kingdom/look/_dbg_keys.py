import sys, os
KING = r"E:\My World\Blender\kingdom"
sys.path.insert(0, KING)
os.chdir(KING)
import spots as S
lay = S.load()
u = S.units_for(lay)
print(len(u))
print(sorted(u[0].keys()))
print({k: u[0][k] for k in u[0] if k != 'quad'})
print(u[0].get('quad'))
