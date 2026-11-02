# -*- coding: utf-8 -*-
"""One-shot surgery on _cint_p2.py: start the aisle vault at the screen wall."""
import io

P = r"E:\My World\Blender\kingdom\_cint_p2.py"
src = io.open(P, encoding="utf-8").read()

a = src.index("    ylist = [-24.4]")
b = src.index("    # transverse ribs on the bay joints")
new = """    ylist = [Y_SCREEN]
    ylist += [p for p in PIERS]
    ylist += [Y_CHOR]
    for yy in sorted(set([round(v, 3) for v in ylist])):
        rows.append([(x, yy, z) for (x, z) in zip(xs, zs)])
    E.append(quad_strip("avault", rows, st))
"""
src = src[:a] + new + src[b:]

src = src.replace(
    '    E.append(bx("av_wr", Ts(X_IN - 0.10, (Y_S + Y_CHOR) * 0.5, Z_VAULT_SPRING + 0.06),\n'
    '                (0.24, Y_CHOR - Y_S, 0.26), sd, bev=0.02))\n'
    '    E.append(bx("av_wr2", Ts(XAIS + 0.06, (Y_S + Y_CHOR) * 0.5, Z_VAULT_SPRING + 0.06),\n'
    '                (0.22, Y_CHOR - Y_S, 0.24), sd, bev=0.02))',
    '    E.append(bx("av_wr", Ts(X_IN - 0.10, (Y_SCREEN + Y_CHOR) * 0.5, Z_VAULT_SPRING + 0.06),\n'
    '                (0.24, Y_CHOR - Y_SCREEN, 0.26), sd, bev=0.02))\n'
    '    E.append(bx("av_wr2", Ts(XAIS + 0.06, (Y_SCREEN + Y_CHOR) * 0.5, Z_VAULT_SPRING + 0.06),\n'
    '                (0.22, Y_CHOR - Y_SCREEN, 0.24), sd, bev=0.02))')

io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("PATCHED p2 aisle_vault -> starts at Y_SCREEN")
print("check:", "ylist = [Y_SCREEN]" in src, "Y_CHOR - Y_SCREEN" in src)
