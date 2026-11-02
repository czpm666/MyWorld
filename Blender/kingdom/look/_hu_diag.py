import sys, io
sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
import hd_houses as H
import capital_hd_glue as G
import hd_surface as SFC
MAT = H.make_mats()
SFC.apply_weathering(MAT)
pal = G.house_mats(MAT, 3, False)
print("PLASTER NAME:", pal["plaster"].name, "weathered?", SFC.is_weathered(pal["plaster"]))
import random
H.house(pal, random.Random(1), kind="timber", w=7.0, d=8.5, floors=3, frontage="eaves")
print("AFTER:", SFC.is_weathered(pal["plaster"]))
print("TILE:", pal["tile"].name, "weathered?", SFC.is_weathered(pal["tile"]))
