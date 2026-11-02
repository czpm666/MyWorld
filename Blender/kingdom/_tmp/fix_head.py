import io

path = r"E:\My World\Blender\kingdom\capital.py"
src = io.open(path, encoding="utf-8").read()
lines = src.split("\n")
lines[0] = '"""Asura Kingdom capital -- Ars (the king\'s city on the river).'
for i, line in enumerate(lines):
    if "\ufeff" in line:
        lines[i] = line.replace("\ufeff", "")
io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
print("[fix] line 1 ->", lines[0][:60])
print("[fix] non-ascii lines now:",
      sum(1 for l in lines if any(ord(c) > 127 for c in l)))
