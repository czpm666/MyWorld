import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()

a = 'M["fire"] = _emit("int_fire", "#ff8a2a", 16.0)'
assert a in s, "fire"
s = s.replace(a, 'M["fire"] = _emit("int_fire", "#ff8a2a", 34.0)')

i = s.index("def build_stair_tower(")
j = s.index("def build_seals(") if "def build_seals(" in s[i:] else len(s)
seg = s[i:s.index("# ==========", i)]
assert "wd" in seg
seg2 = seg.replace("    st = _m(M, \"stone_wall\")",
                   "    st = _m(M, \"stone_wall\")\n    wd = _m(M, \"wood_dark\")", 1)
s = s[:i] + seg2 + s[i + len(seg):]

ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("OK", s.count("\n") + 1)
