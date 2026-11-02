import io

p = r"E:\My World\Blender\kingdom\capital.py"
raw = open(p, "rb").read()
t = raw.decode("utf-8", "replace")
lines = t.split("\n")
bad = [i for i, ln in enumerate(lines) if "\ufffd" in ln]
print("lines with U+FFFD:", len(bad), " total chars:", t.count("\ufffd"))

# also count raw 0x3f-looking damage: '?' directly after a multibyte start
i = 0
rawbad = []
while i < len(raw):
    b = raw[i]
    if b < 0x80:
        i += 1
        continue
    n = 3 if (b & 0xF0) == 0xE0 else 2 if (b & 0xE0) == 0xC0 else 4 if (b & 0xF8) == 0xF0 else 0
    if n == 0:
        rawbad.append(i)
        i += 1
        continue
    for k in range(1, n):
        if i + k >= len(raw) or (raw[i + k] & 0xC0) != 0x80:
            rawbad.append(i)
            break
    i += 1
print("invalid lead positions:", len(rawbad))
for i in bad[:40]:
    print("%5d: %s" % (i + 1, lines[i].strip()[:120]))
