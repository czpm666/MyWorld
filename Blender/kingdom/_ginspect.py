import sys
p = r"E:\My World\Blender\kingdom\_gaudit.py"
print("PY", sys.version)
raw = open(p, "rb").read()
print("bytes", len(raw), "CRLF", raw.count(b"\r\n"), "LF", raw.count(b"\n"), "CR", raw.count(b"\r"))
txt = raw.decode("utf-8")
lines = txt.split("\n")
for i in range(17, 30):
    print(i + 1, repr(lines[i]))
# try to compile and report the failure position
try:
    compile(txt, p, "exec")
    print("COMPILE OK")
except SyntaxError as e:
    print("FAIL line", e.lineno, "off", e.offset, e.msg)
    ln = txt.split("\n")[e.lineno - 1]
    print("LINE REPR:", repr(ln))
    print("CODES:", [hex(ord(c)) for c in ln[:12]])
