import io

p = r"E:\My World\Blender\kingdom\hd_gate.py"
s = io.open(p, encoding="utf-8").read()
a = s.replace('"wet", "grass", "glow", "lamp")', '"wet", "leaf", "grass", "glow", "lamp")')
a = a.replace('H.cart("pr_cart", Ts(2.30, 38.50, 0.0, rz=PI - 0.10)',
              'H.cart("pr_cart", Ts(-7.60, 41.20, 0.0, rz=PI + 0.55)')
io.open(p, "w", encoding="utf-8", newline="\n").write(a)
print("leaf key:", a.count('"wet", "leaf", "grass"'))
print("cart:", a.count('-7.60, 41.20'))
