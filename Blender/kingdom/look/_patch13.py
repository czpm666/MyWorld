import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()


def rep(a, b, tag, n=1):
    global s
    assert a in s, tag
    s = s.replace(a, b, n)
    print("rep", tag)


rep('    noi.inputs["Scale"].default_value = 1.7\n'
    '    noi.inputs["Detail"].default_value = 6.0\n'
    '    noi.inputs["Roughness"].default_value = 0.62\n',
    '    noi.inputs["Scale"].default_value = 0.42\n'
    '    noi.inputs["Detail"].default_value = 3.0\n'
    '    noi.inputs["Roughness"].default_value = 0.50\n', "noise")

rep('    gr.inputs["Factor"].default_value = grime',
    '    gr.inputs["Factor"].default_value = grime * 0.30', "grime weight")

rep('    bp.inputs["Distance"].default_value = 0.02',
    '    bp.inputs["Distance"].default_value = 0.030', "bump dist")

for a, b in (("bw=1.40, bh=0.50", "bw=1.40, bh=0.50"),
             ("grime=0.26, bump=0.16", "grime=0.26, bump=0.38")):
    if a in s:
        s = s.replace(a, b)
        print("rep", b)

rep('("A_door", (11.4, 0.0, EYE), (-11.70, 0.0, 3.40), 34.0, 0.0022)',
    '("A_door", (8.8, 0.0, EYE), (-11.70, 0.0, 3.30), 37.0, 0.0022)', "cam A")

ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCHED")
