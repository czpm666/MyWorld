import io
import ast

p = r"E:\My World\Blender\kingdom\hd_castle_int.py"
s = io.open(p, encoding="utf-8", newline="").read()


def rep(a, b, tag, n=1):
    global s
    assert a in s, tag
    s = s.replace(a, b, n)
    print("rep", tag)


# Fill lamps sit 0.45 m off the wall: shadow rays from there never converge at
# preview sample counts and the denoiser smears them into leopard spots.
rep('''            L.color = (0.80, 0.86, 1.0)
            o = bpy.data.objects.new("ci_win_fill", L)''',
    '''            L.color = (0.80, 0.86, 1.0)
            L.use_shadow = False
            o = bpy.data.objects.new("ci_win_fill", L)''', "hall fill shadow")
rep('''            L.color = (0.86, 0.90, 1.0)
            o = bpy.data.objects.new("ci_f_winfill", L)''',
    '''            L.color = (0.86, 0.90, 1.0)
            L.use_shadow = False
            o = bpy.data.objects.new("ci_f_winfill", L)''', "feast fill shadow")

# sub-pixel bump aliases into mush; keep the tooth coarse enough to resolve
rep('    fine.inputs["Scale"].default_value = 11.0',
    '    fine.inputs["Scale"].default_value = 3.2', "fine scale")
rep('                              bw=1.40, bh=0.50, grime=0.26, bump=0.38)',
    '                              bw=1.40, bh=0.50, grime=0.26, bump=0.12)',
    "wall bump")

ast.parse(s)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCHED")
