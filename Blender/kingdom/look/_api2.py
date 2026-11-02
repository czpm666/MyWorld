import io, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
names = sys.argv[1:] or ["hd_sky.py"]
for name in names:
    p = os.path.join(here, name)
    if not os.path.exists(p):
        print("== %s MISSING" % name)
        continue
    s = io.open(p, encoding="utf-8").read()
    print("=" * 70)
    print("%s   %d lines  %d bytes" % (name, s.count(chr(10)), len(s)))
    m = re.match(r'\s*r?"""(.*?)"""', s, re.S)
    if m:
        print("-- docstring --")
        print(chr(10).join(m.group(1).strip().split(chr(10))[:18]))
    print("-- public surface --")
    for ln in s.split(chr(10)):
        if re.match(r"^(def [a-zA-Z]|[A-Z][A-Z0-9_]{2,} = )", ln):
            print("  " + ln[:118])
