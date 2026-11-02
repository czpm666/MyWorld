"""quick probe: bevel tri cost + render timing."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy
import hd_common as H
import medkit as K
from medkit import T_at as Ts

H._clear()
a = K.box("a", Ts(0, 0, 0), (1, 1, 1), None)
b = K.box("b", Ts(0, 0, 0), (1, 1, 1), None, bev=0.02)
dg = bpy.context.evaluated_depsgraph_get()
for ob in (a, b):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    print("[probe] %s tris=%d" % (ob.name, len(me.loop_triangles)))
    ev.to_mesh_clear()

# render timing on a trivial scene
H.diorama_floor(K.mat_flat if hasattr(K, "mat_flat") else K.mat_stone())
K.box("big", Ts(0, 0, 10), (40, 40, 20), K.mat_stone())
H.setup_world()
H.setup_engine(samples=32, res=(700, 450))
cam = H.camera("c", (60, -60, 40), (0, 0, 10), lens=50)
t0 = time.time()
H.render_to(r"E:\My World\Blender\renders\kingdom\_cath_timing.png", cam)
print("[probe] render 700x450 @32spp took %.1fs" % (time.time() - t0))
