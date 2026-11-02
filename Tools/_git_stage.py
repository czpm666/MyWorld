import os, shutil, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"E:\My World"
LOOK = os.path.join(ROOT, r"Blender\renders\kingdom\look")
DEST = os.path.join(ROOT, r"Docs\shots")
os.makedirs(DEST, exist_ok=True)

WANT = [
    ("01_roofs_R7.png", "01_roofs.png"),
    ("02_aerial_R7.png", "02_aerial_v23.png"),
    ("V24_overview.png", "03_overview_v24.png"),
    ("V24_castle.png", "04_castle_v24.png"),
    ("V24_cathedral.png", "05_cathedral_v24.png"),
    ("C1_aerial.png", "06_aerial_c1.png"),
    ("C1_game4.png", "07_street_c1.png"),
    ("v25a_overview_city.png", "08_overview_v25.png"),
    ("v25a_game_avenue_north.png", "09_avenue_v25.png"),
    ("v25a_eye_plaza_south.png", "10_plaza_v25.png"),
    ("fac2_cmp_ends.png", "11_party_wall_before_after.png"),
    ("fac2_after_game.png", "12_facade_after.png"),
    ("TYPES_sheet.png", "13_types_sheet.png"),
    ("gate2_wall.png", "14_gate.png"),
    ("sky2_morning_town.png", "15_sky.png"),
    ("WX_rain.png", "16_weather_rain.png"),
    ("L_ci21_nave_up.png", "17_cathedral_int.png"),
    ("ACC_A_door.png", "18_throne_hall.png"),
]

copied, missing = [], []
for src, dst in WANT:
    sp = os.path.join(LOOK, src)
    if os.path.exists(sp):
        shutil.copy2(sp, os.path.join(DEST, dst))
        copied.append((dst, os.path.getsize(sp)))
    else:
        missing.append(src)

print("[shots] copied %d, missing %d" % (len(copied), len(missing)))
for dst, n in copied:
    print("   %6.0f KB  %s" % (n / 1024.0, dst))
if missing:
    print("[shots] missing:", ", ".join(missing))

# fallback: if the gate shot name differs, take the first gate2_*.png
if not os.path.exists(os.path.join(DEST, "14_gate.png")):
    import glob
    cands = sorted(glob.glob(os.path.join(LOOK, "gate2_*.png")))
    if cands:
        shutil.copy2(cands[0], os.path.join(DEST, "14_gate.png"))
        print("[shots] fallback gate ->", os.path.basename(cands[0]))

def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")

targets = ["Blender/kingdom", "Blender/medkit.py", "Blender/kcommon.py",
           "Docs", "Tools", "ProjectSettings", "Assets", "README.md", ".gitignore"]
for t in targets:
    p = os.path.join(ROOT, t.replace("/", os.sep))
    if not os.path.exists(p):
        print("[add] skip (missing):", t)
        continue
    rc, out, err = git("add", "-A", "--", t)
    print("[add] %-22s rc=%d %s" % (t, rc, (err or out).strip()[:160]))

rc, out, err = git("status", "--porcelain=v1")
staged = [l for l in out.splitlines() if l[:2].strip() and l[0] not in " ?"]
print("\nstaged entries:", len(staged))

rc, out, err = git("diff", "--cached", "--name-only", "-z")
names = [n for n in out.split("\0") if n]
total = 0
big = []
for n in names:
    fp = os.path.join(ROOT, n.replace("/", os.sep))
    try:
        s = os.path.getsize(fp)
    except OSError:
        s = 0
    total += s
    big.append((s, n))
big.sort(reverse=True)
print("staged files: %d   total %.1f MB" % (len(names), total / 1024 ** 2))
print("\n=== 12 largest staged ===")
for s, n in big[:12]:
    print("%8.1f MB  %s" % (s / 1024 ** 2, n))
over = [(s, n) for s, n in big if s > 95 * 1024 ** 2]
print("\nstaged files >95 MB:", len(over))
for s, n in over:
    print("  ", n)
