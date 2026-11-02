import io

p = r"E:\My World\Blender\kingdom\capital.py"
raw = open(p, "rb").read()
bad = b"\xe5\x9b?"
good = b"\xe5\x9b\xbd"          # 国
assert raw.count(bad) == 1, raw.count(bad)
raw = raw.replace(bad, good)
t = raw.decode("utf-8")          # must not raise
compile(t, p, "exec")
open(p, "wb").write(raw)
print("repaired, size", len(raw))
print(t.split("\n")[0])
