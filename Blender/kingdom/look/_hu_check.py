import io

s = io.open(r"E:\My World\Blender\kingdom\hd_houses.py", encoding="utf-8").read()
for k in ("def _age(", "roof_material(tile)", "_age(plaster", "lamp=False", "du = info"):
    print(("YES" if k in s else "NO "), k)

t = io.open(r"E:\My World\Blender\kingdom\hd_houses_parts.py", encoding="utf-8").read()
for k in ("def roof_material(", "def hip_roof(", "def quad_slab(", "riser=0.09", "_rt", "nm = int(5 + 7 * moss)"):
    print(("YES" if k in t else "NO "), k)
