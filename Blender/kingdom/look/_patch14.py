import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()


def rep(a, b, tag, n=1):
    global s
    assert a in s, tag
    s = s.replace(a, b, n)
    print("rep", tag)


# The Mix node multiplies at full strength (the RGBA "Factor" socket is not the
# one that ends up wired), which painted the walls with 2 m camouflage blotches.
# Ashlar variation now comes from the brick node itself.
i = s.index('    noi = nt.nodes.new("ShaderNodeTexNoise")')
j = s.index('    bp = nt.nodes.new("ShaderNodeBump")', i)
s = s[:i] + (
    '    nt.links.new(br.outputs["Color"], b.inputs["Base Color"])\n'
    '    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])\n') + s[j:]
print("cut noise mix")

rep('M["stone_wall"] = _ashlar("ci_flag", (0.205, 0.194, 0.175),\n'
    '                          (0.212, 0.201, 0.181), (0.062, 0.058, 0.052),\n',
    'M["stone_wall"] = _ashlar("ci_flag", (0.212, 0.201, 0.180),\n'
    '                          (0.169, 0.160, 0.142), (0.055, 0.051, 0.046),\n', "flag tones")

rep('M["stone_floor"] = _ashlar("ci_floor", (0.196, 0.186, 0.168),\n'
    '                             (0.176, 0.166, 0.150), (0.052, 0.049, 0.044),',
    'M["stone_floor"] = _ashlar("ci_floor", (0.268, 0.252, 0.226),\n'
    '                             (0.222, 0.208, 0.184), (0.062, 0.058, 0.052),',
    "floor albedo")

rep('    sd.energy = 130.0', '    sd.energy = 92.0', "sun")

ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCHED")
