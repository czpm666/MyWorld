"""hd_weather_sheet.py -- stitch the 8 weather renders into look/WEATHER_sheet.png.

Plain CPython (PIL), not Blender:

    E:\\GameProject\\Python313\\python.exe hd_weather_sheet.py [--cam wide|game]

Reads  renders/kingdom/look/WX_<state>[_<cam>].png  +  _wx_stats.json, writes
renders/kingdom/look/WEATHER_sheet[_<cam>].png  (4 columns x 2 rows, 640x360
tiles, one caption bar per tile) and prints the measurement table as markdown.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

LOOK = r"E:\My World\Blender\renders\kingdom\look"
COLS = 4
TW, TH = 640, 360
BAR = 22
ORDER = ("clear", "hazy", "overcast", "rain", "storm", "fog", "snow", "sunshower")


def _font(size=14):
    for p in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf",
              r"C:\Windows\Fonts\consola.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:                            # noqa: BLE001
                pass
    return ImageFont.load_default()


def main():
    cam = "wide"
    if "--cam" in sys.argv:
        cam = sys.argv[sys.argv.index("--cam") + 1]
    suffix = "" if cam == "wide" else "_" + cam
    stats = {}
    sp = os.path.join(LOOK, "_wx_stats%s.json" % suffix)
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as fh:
            for s in json.load(fh)["states"]:
                stats[s["weather"]] = s

    rows = (len(ORDER) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TW, rows * (TH + BAR)), (14, 16, 20))
    draw = ImageDraw.Draw(sheet)
    big, small = _font(15), _font(13)
    missing = []
    for i, name in enumerate(ORDER):
        p = os.path.join(LOOK, "WX_%s%s.png" % (name, suffix))
        if not os.path.exists(p):
            missing.append(p)
            continue
        im = Image.open(p).convert("RGB")
        if im.size != (TW, TH):
            im = im.resize((TW, TH), Image.LANCZOS)
        x = (i % COLS) * TW
        y = (i // COLS) * (TH + BAR)
        sheet.paste(im, (x, y))
        st = stats.get(name, {})
        cap = "%-9s  vis %5.1f km   sun %3.0f W/m2   tris %5.1fk   obj %2d   %4.1fs" % (
            name.upper(),
            (st.get("report", {}).get("fog", {}) or {}).get("vis_m", 0) / 1000.0,
            (st.get("report", {}).get("sun", {}) or {}).get("energy", 0.0),
            st.get("tris", 0) / 1000.0, st.get("objects", 0), st.get("t_total", 0.0))
        draw.rectangle([x, y + TH, x + TW, y + TH + BAR], fill=(20, 23, 28))
        draw.text((x + 8, y + TH + 3), cap, fill=(228, 230, 235), font=small)
        # thin separator so the tiles read as separate frames
        draw.line([x, y, x, y + TH], fill=(8, 9, 11))
        draw.line([x, y + TH, x + TW, y + TH], fill=(8, 9, 11))

    out = os.path.join(LOOK, "WEATHER_sheet%s.png" % suffix)
    sheet.save(out)
    print(out, sheet.size)
    if missing:
        print("MISSING:", *missing, sep="\n  ")

    # measurement table for the doc
    print("\n| state | objects | tris | build s | atmos s | render s | total s | materials |)")
    print("|---|---|---|---|---|---|---|---|")
    for name in ORDER:
        s = stats.get(name)
        if not s:
            continue
        print("| `%s` | %d | %s | %.2f | %.2f | %.1f | %.1f | %d |" % (
            name, s["objects"], "{:,}".format(s["tris"]), s["t_build"],
            s["t_atmos"], s["t_render"], s["t_total"], s["materials"]))


if __name__ == "__main__":
    main()
