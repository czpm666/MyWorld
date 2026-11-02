import io
p = r"E:\My World\Blender\kingdom\capital.py"
src = io.open(p, encoding="utf-8").read()
lines = src.split("\n")
# locate the leftover duplicate block: a comment mentioning HD_INT near ROCK_TOP
start = None
for i, ln in enumerate(lines):
    if ln.startswith("# HD_INT (declared near ROCK_TOP above)"):
        start = i
        break
if start is None:
    print("anchor not found; nothing to do")
else:
    end = None
    for j in range(start, min(start + 12, len(lines))):
        if lines[j].startswith('HD_INT = {"on": False}'):
            end = j
            break
    if end is None:
        print("duplicate assignment not found near anchor")
    else:
        repl = ["# HD_INT is declared near ROCK_TOP, before any function that reads it."]
        lines[start:end + 1] = repl
        io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
        print("removed duplicate block at lines %d..%d" % (start + 1, end + 1))
