import io

p = r"E:\My World\Blender\kingdom\capital.py"
raw = open(p, "rb").read()
out = []

# walk the bytes, reporting every position that is not a valid UTF-8 sequence
i = 0
bad = []
while i < len(raw):
    b = raw[i]
    if b < 0x80:
        i += 1
        continue
    n = 3 if (b & 0xF0) == 0xE0 else 2 if (b & 0xE0) == 0xC0 else 4 if (b & 0xF8) == 0xF0 else 0
    if n == 0:
        bad.append(i)
        i += 1
        continue
    ok = all(i + k < len(raw) and (raw[i + k] & 0xC0) == 0x80 for k in range(1, n))
    if not ok:
        bad.append(i)
    i += 1

out.append("bad positions: %d" % len(bad))
for pos in bad:
    ln = raw[:pos].count(b"\n") + 1
    line = raw.split(b"\n")[ln - 1]
    out.append("pos %-6d line %-5d ctx=%s" % (pos, ln, repr(raw[max(0, pos - 24):pos + 16])))
    out.append("        line=%s" % repr(line[:160]))
io.open(r"E:\My World\Blender\kingdom\_tmp\bad.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out[:2]))
