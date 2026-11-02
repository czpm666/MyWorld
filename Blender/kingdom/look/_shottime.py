r"""Turn a render log into the per-shot timing table.

    python look/_shottime.py Logs\cam720.log [--md Docs\cam_timings.md]

render.py prints one `[rig-result] [{"shot": ..., "render_s": ...}]` line per
blend load and one `[rig] <name> render 31.0s (rig 6.8s)` line per camera, so
the table is read out of the log instead of being retyped (a retyped table is
how a 31 s frame becomes "about 20 seconds" in a report).

Blender writes its stdout log as UTF-16LE on Windows, so read bytes and sniff
the BOM -- opening these as utf-8 silently yields mojibake and zero matches.
"""
import json
import os
import re
import sys

SHOT = re.compile(r"\[rig\]\s+(\S+)\s+render\s+([\d.]+)s\s+\(rig\s+([\d.]+)s\)")
TOTAL = re.compile(r"\[rig\] done in ([\d.]+)s")
BLEND = re.compile(r'Read blend: "(.+?)"')
WEATHER = re.compile(r"weather = (\w+)\s+vis ([\d.]+) km")


def read_log(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in raw[:400]:
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")


def parse(path):
    rows, total, blend, weather = [], None, None, None
    for line in read_log(path).splitlines():
        m = BLEND.search(line)
        if m:
            blend = os.path.basename(m.group(1))
        m = WEATHER.search(line)
        if m:
            weather = (m.group(1), float(m.group(2)))
        m = SHOT.search(line)
        if m:
            rows.append(dict(shot=m.group(1), render=float(m.group(2)),
                             rig=float(m.group(3))))
        m = TOTAL.search(line)
        if m:
            total = float(m.group(1))
    for r in rows:
        r["total"] = r["render"] + r["rig"]
    return dict(blend=blend, weather=weather, total=total, rows=rows)


def markdown(d, path):
    rows = d["rows"]
    n = len(rows)
    if not n:
        return 0
    tot = sum(r["total"] for r in rows)
    worst = max(rows, key=lambda r: r["render"])
    lines = ["| shot | render s | rig s | total s |", "| --- | --- | --- | --- |"]
    for r in rows:
        lines.append("| `%s` | %.1f | %.1f | %.1f |"
                     % (r["shot"], r["render"], r["rig"], r["total"]))
    lines += ["", "**%d shots, %.0f s of render+rig, %.1f s per shot on average, "
              "slowest `%s` at %.1f s.**"
              % (n, tot, tot / n, worst["shot"], worst["render"])]
    if d["total"]:
        lines.append("Wall clock for the whole blend load (including open, rig, "
                     "roof rebuild): **%.0f s**. Blend: `%s`."
                     % (d["total"], d["blend"] or "?"))
    if d["weather"]:
        lines.append("Weather: `%s`, visibility %.1f km." % d["weather"])
    text = "\n".join(lines) + "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return text


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 2
    src = a[0]
    d = parse(src)
    md = None
    if "--md" in a:
        md = a[a.index("--md") + 1]
    if not d["rows"]:
        print("[time] no per-shot lines in %s" % src)
        return 1
    print("[time] %s: %d shots, blend %s"
          % (os.path.basename(src), len(d["rows"]), d["blend"]))
    for r in d["rows"]:
        print("  %-24s render %6.1f s  rig %5.1f s" % (r["shot"], r["render"],
                                                       r["rig"]))
    if d["total"]:
        print("[time] blend-load wall clock: %.0f s" % d["total"])
    if md:
        text = markdown(d, md)
        print("[time] wrote %s (%d chars)" % (md, len(text)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
