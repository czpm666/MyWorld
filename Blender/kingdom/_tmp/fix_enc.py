import io, os, sys, codecs

p = r"E:\My World\Blender\kingdom\capital.py"
raw = open(p, "rb").read()
print("size", len(raw))

cands = []
for enc in ("utf-8", "cp936", "gbk", "gb18030", "cp1252", "latin-1"):
    try:
        t = raw.decode(enc)
        cands.append((enc, t))
    except Exception as exc:
        print("decode %-8s FAIL %s" % (enc, exc))

for enc, t in cands:
    ok = True
    try:
        compile(t, p, "exec")
    except SyntaxError as exc:
        ok = False
        print("compile %-8s FAIL %s" % (enc, exc))
    if ok:
        out = p + "." + enc
        io.open(out, "w", encoding="utf-8", newline="\n").write(t)
        print("compile %-8s OK -> %s" % (enc, out))
print("--- head of file as bytes ---")
print(raw[:200])
