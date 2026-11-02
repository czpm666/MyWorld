import sys, os, bpy

BL = r"E:\My World\Blender"
KING = os.path.join(BL, "kingdom")
for p in (KING, BL):
    sys.path.insert(0, p)
import capital as C            # noqa: E402
import kcommon as KC           # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
want = set(args[0].split(",")) if args else {"b5_gate_in"}

blend = os.path.join(C.OUT_PNG, "capital_full.blend")
bpy.ops.wm.open_mainfile(filepath=blend)
KC.clear_lights_cameras()
KC.setup_lighting()
KC.setup_render(w=1600, h=900, samples=32)

shots = {s[0]: s for s in C.hd_shots()}
for name in sorted(want):
    s = shots.get(name)
    if s is None:
        print("[reshoot] no such shot:", name, flush=True)
        continue
    KC.setup_camera(s[1], s[2], s[3])
    print("[render]", KC.render_to(os.path.join(C.OUT_PNG, name + ".png")), flush=True)
print("RESHOOT_DONE")
