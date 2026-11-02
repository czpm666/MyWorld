"""Offline sanity check for look/shots.json -- no Blender, no lock, <1 s.

The QA tool needs a 31 GB scene to answer "is this a good frame".  This answers
a cheaper and different question: "is this even a well-formed camera?"  It has
caught the boring failures that waste a four-minute QA slot -- a name that does
not match its kind, a lens and a fov both missing, a look point behind the
camera, a game shot whose pos is not the rig's pos for its stated player.

Usage:
    python look/_shotcheck.py [--shots look/shots.json]
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "shots.json")

KINDS = ("game", "eye", "aerial", "overview", "landmark", "extra")
# the Unity rig the game_* entries must reproduce
CAM_UP = 26.790      # 34 * sin(52)
CAM_BACK = 20.931    # 34 * cos(52)
EYE_H = 1.72


def arg(name, default=None):
    a = [v for v in sys.argv[1:] if v != "--"]
    if name in a:
        return a[a.index(name) + 1]
    return default


def norm(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n else [0.0, 0.0, 0.0]


def main():
    path = arg("--shots", DEFAULT)
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    shots = d.get("shots") or []
    bad, warn = [], []
    seen = set()
    counts = {}
    for s in shots:
        name = s.get("name", "?")
        kind = s.get("kind")
        counts[kind] = counts.get(kind, 0) + 1
        if name in seen:
            bad.append("%s: duplicate name" % name)
        seen.add(name)
        pre = name.split("_")[0]
        if pre not in KINDS:
            bad.append("%s: name prefix %r is not one of %s" % (name, pre, KINDS))
        elif kind and pre != kind and not (pre == "extra" and kind == "landmark"):
            bad.append("%s: name prefix %r but kind %r" % (name, pre, kind))
        pos, look = s.get("pos"), s.get("look")
        for k, v in (("pos", pos), ("look", look)):
            if not (isinstance(v, (list, tuple)) and len(v) == 3
                    and all(isinstance(x, (int, float)) for x in v)):
                bad.append("%s: %s is not 3 numbers" % (name, k))
        if not (pos and look):
            continue
        if not s.get("lens") and not s.get("fov"):
            bad.append("%s: neither lens nor fov" % name)
        if s.get("lens") and s.get("fov"):
            warn.append("%s: both lens and fov -- fov wins" % name)
        d3 = [look[i] - pos[i] for i in range(3)]
        if math.sqrt(sum(x * x for x in d3)) < 1.0:
            bad.append("%s: look is inside 1 m of pos" % name)
            continue
        # does the stated yaw/pitch agree with the geometry?
        yaw = math.degrees(math.atan2(d3[1], d3[0])) % 360.0
        pitch = math.degrees(math.asin(norm(d3)[2]))
        if "yaw" in s and abs((s["yaw"] - yaw + 180.0) % 360.0 - 180.0) > 0.5:
            bad.append("%s: yaw %s but geometry says %.2f" % (name, s["yaw"], yaw))
        if "pitch" in s and abs(s["pitch"] - pitch) > 0.5:
            bad.append("%s: pitch %s but geometry says %.2f" % (name, s["pitch"], pitch))
        if kind == "eye" and abs(pos[2] - EYE_H) > 0.01:
            bad.append("%s: eye shot at z %.2f, not %.2f" % (name, pos[2], EYE_H))
        if kind == "game":
            pl, hd = s.get("player"), s.get("heading")
            if not (pl and hd):
                bad.append("%s: game shot without player/heading" % name)
            else:
                want = [pl[0] - hd[0] * CAM_BACK, pl[1] - hd[1] * CAM_BACK,
                        EYE_H + CAM_UP]
                if max(abs(want[i] - pos[i]) for i in range(3)) > 0.02:
                    bad.append("%s: pos is not the rig's pos for player %s/%s "
                               "(want %s)" % (name, pl, hd,
                                              [round(v, 2) for v in want]))
                if abs(math.hypot(hd[0], hd[1]) - 1.0) > 0.01:
                    bad.append("%s: heading is not unit" % name)
            if s.get("fov") and abs(s["fov"] - 30.0) > 0.01:
                warn.append("%s: fov %.1f is not the rig's 30" % (name, s["fov"]))
        if not str(s.get("note") or "").strip():
            bad.append("%s: empty note" % name)
        elif len(s["note"]) < 30:
            warn.append("%s: note is %.0f chars, that is not a sentence"
                        % (name, len(s["note"])))
    print("[check] %d shots  %s" % (len(shots), counts))
    for b in bad:
        print("  BAD  " + b)
    for w in warn:
        print("  warn " + w)
    print("[check] %s" % ("OK" if not bad else "%d bad" % len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
