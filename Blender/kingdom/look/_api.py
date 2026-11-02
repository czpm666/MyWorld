import io, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for name in ("hd_rock.py", "hd_cathedral_int.py", "hd_castle_int.py", "hd_weather.py"):
    p = os.path.join(here, name)
    if not os.path.exists(p):
        print("== %s MISSING" % name)
        continue
    s = io.open(p, encoding="utf-8").read()
    print("=" * 70)
    print("%s   %d lines  %d bytes" % (name, s.count("\n"), len(s)))
    m = re.match(r'\s*r?"""(.*?)"""', s, re.S)
    if m:
        print("-- docstring --")
        print("\n".join(m.group(1).strip().split("\n")[:22]))
    print("-- public surface --")
    for ln in s.split("\n"):
        if re.match(r"^(def [a-zA-Z]|[A-Z][A-Z0-9_]* = )", ln):
            print("  " + ln[:118])
