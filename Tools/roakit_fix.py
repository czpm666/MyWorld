import io

CAP = r"C:\Users\cl796\AppData\Local\Temp\dsh-workspace-changes-jvjs8a\captures\ef9128222f49d0d7595161641458397fe81cb5ed"
DST = r"E:\My World\Assets\Scripts\MyWorld\Maps\RoaKit.cs"
REP = r"C:\Users\cl796\AppData\Local\Temp\roakit_fix_report.txt"

lines = io.open(CAP, encoding="utf-8", newline="").read().split("\n")
rep = []

SP = " "


def indent_of(s):
    n = 0
    while n < len(s) and s[n] == SP:
        n += 1
    return n


def method_name(s):
    """method name = identifier immediately before the trailing ')' of a signature line"""
    if not s.endswith(")"):
        return None
    k = s.index("(") - 1 if "(" in s else len(s) - 2
    while k >= 0 and (s[k].isalnum() or s[k] == "_"):
        k -= 1
    name = s[k + 1:s.index("(")].strip()
    return name or None


spans = []
for i, raw in enumerate(lines):
    s = raw.rstrip()
    if indent_of(s) != 8:
        continue
    if not s.endswith(")"):
        continue
    if ";" in s or "//" in s:
        continue
    end = None
    for j in range(i + 1, len(lines)):
        if lines[j].rstrip() == "        }":
            end = j
            break
    name = method_name(s)
    if end is not None and name:
        spans.append((i, end, name))

rep.append("methods detected: %d" % len(spans))
rep.append("sample: %s" % [(n, a + 1, b + 1) for (a, b, n) in spans[:4]])


def owner(idx):
    best = None
    for (a, b, n) in spans:
        if a <= idx <= b and (best is None or (b - a) < (best[1] - best[0])):
            best = (a, b, n)
    return best


def is_d_token(s, k):
    if s[k] != "d":
        return False
    if k > 0 and (s[k - 1].isalnum() or s[k - 1] == "_" or s[k - 1] == "."):
        return False
    if k + 1 < len(s) and (s[k + 1].isalnum() or s[k + 1] == "_"):
        return False
    return True


def rename_line(s):
    out = []
    n = 0
    for k, ch in enumerate(s):
        if is_d_token(s, k):
            out.append("dir")
            n += 1
        else:
            out.append(ch)
    return "".join(out), n


decls = [k for k, l in enumerate(lines) if l.strip().startswith("Vector3 d ") and "KitMath" in l]
rep.append("declarations: %s" % [d + 1 for d in decls])

total = 0
for d in decls:
    o = owner(d)
    if o is None:
        rep.append("!! line %d has no owning method (end of file?)" % (d + 1))
        continue
    a, b, name = o
    sub = 0
    for j in range(a, b + 1):
        new, n = rename_line(lines[j])
        if n:
            lines[j] = new
            sub += n
    total += sub
    rep.append("decl %4d method=%-16s span %4d-%-4d renames=%d" % (d + 1, name, a + 1, b + 1, sub))
rep.append("total renames: %d" % total)

# verify no bare-d token remains in any method we touched
for (d) in decls:
    o = owner(d)
    if not o:
        continue
    a, b, name = o
    left = [j + 1 for j in range(a, b + 1) if any(is_d_token(lines[j], k) for k in range(len(lines[j])))]
    if left:
        rep.append("LEFT in %s: %s" % (name, left[:10]))

txt = "\n".join(lines)
io.open(DST, "w", encoding="utf-8", newline="").write(txt)
rep.append("written %d lines / %d bytes" % (len(lines), len(txt.encode("utf-8"))))
io.open(REP, "w", encoding="utf-8").write("\n".join(rep))
print("done")
