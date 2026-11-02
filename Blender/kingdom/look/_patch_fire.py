import io

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()

subs = [
    ('    mats = ["stone_floor", "stone_floor", "stone_floor", "stone_floor",\n'
     '            "stone_course", "stone_step"]',
     '    mats = ["stone_floor"] * 9 + ["stone_light"]'),
    ('M["fire"] = _emit("int_fire", "#ff8a2a", 26.0)',
     'M["fire"] = _emit("int_fire", "#ff8a2a", 62.0)'),
    ('M["ember"] = _emit("int_ember", "#ff5a12", 9.0)',
     'M["ember"] = _emit("int_ember", "#ff5a12", 22.0)'),
    ('M["candle"] = _emit("int_candle", "#ffd79a", 7.0)',
     'M["candle"] = _emit("int_candle", "#ffd79a", 14.0)'),
]
for a, b in subs:
    assert a in s, a[:40]
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCHED")
