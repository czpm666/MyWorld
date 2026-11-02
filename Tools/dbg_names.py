import io

CAP = r"C:\Users\cl796\AppData\Local\Temp\dsh-workspace-changes-jvjs8a\captures\ef9128222f49d0d7595161641458397fe81cb5ed"
lines = io.open(CAP, encoding="utf-8", newline="").read().split("\n")
print("total", len(lines))

paren = [i for i, l in enumerate(lines) if l.rstrip().endswith("(")]
print("lines ending with ( :", len(paren))
for i in paren[:6]:
    s = lines[i]
    print("  line %4d indent=%2d len=%3d %r" % (i + 1, len(s) - len(s.lstrip(" ")), len(s), s[:75]))

sig = [i for i, l in enumerate(lines) if l.rstrip().endswith(")")]
print("lines ending with ) :", len(sig))
for i in sig[:6]:
    s = lines[i]
    print("  line %4d indent=%2d len=%3d %r" % (i + 1, len(s) - len(s.lstrip(" ")), len(s), s[:75]))
