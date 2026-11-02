"""_surf_probe_brick.py -- what does Brick.Color actually do per brick?

Renders a vertical quad in XZ with Blender's Brick texture exactly as
medkit.mat_stone drives it -- vector = (x + y, z), Scale 1, Brick Width
1.5/2.4, Row Height 0.75/2.4, Mortar 0.022, offset 0.5 -- but with
Color1 = black, Color2 = white, Mortar = mid grey, through an EMISSION shader.

Then the PNG is read outside Blender (numpy) to answer three questions:

  1. is a brick's colour a uniform random mix of Color1..Color2, or a binary
     pick, or a constant?
  2. is the value constant over the whole brick face (so it can drive a
     per-block tone) or does it vary inside a brick?
  3. does the random sequence repeat every 2 rows / every N bricks?  (the
     whole per-block trick dies if the hash has a short period)

USAGE
    blender.exe --background --factory-startup --python _surf_probe_brick.py
OUT
    renders/kingdom/_surf_brick_probe.png  (512 x 512, 8 bit grey)
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import bpy
import hd_common as H

OUT = H.OUT_DIR

# the geometry of the probe wall
X0, X1 = 0.0, 12.0
Z0, Z1 = -4.0, 4.0


def build():
    H._clear()
    sc = bpy.context.scene

    # vertical quad in the XZ plane, front facing -Y, camera on +Y
    verts = [(X0, 0.0, Z0), (X1, 0.0, Z0), (X1, 0.0, Z1), (X0, 0.0, Z1)]
    me = bpy.data.meshes.new("probe")
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("probe", me)
    bpy.context.collection.objects.link(ob)

    mat = bpy.data.materials.new("probe_brick")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.name = "EMIT"
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(sep.outputs["X"], add.inputs[0])
    nt.links.new(sep.outputs["Y"], add.inputs[1])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(add.outputs[0], comb.inputs["X"])
    nt.links.new(sep.outputs["Z"], comb.inputs["Y"])

    br = nt.nodes.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 1.5 / 2.4
    br.inputs["Row Height"].default_value = 0.75 / 2.4
    br.inputs["Mortar Size"].default_value = 0.022
    br.inputs["Mortar Smooth"].default_value = 0.25
    br.inputs["Bias"].default_value = 0.0
    br.offset = 0.5
    nt.links.new(comb.outputs["Vector"], br.inputs["Vector"])
    br.inputs["Color1"].default_value = (0.0, 0.0, 0.0, 1.0)
    br.inputs["Color2"].default_value = (1.0, 1.0, 1.0, 1.0)
    br.inputs["Mortar"].default_value = (0.5, 0.5, 0.5, 1.0)
    nt.links.new(br.outputs["Color"], emit.inputs["Color"])

    ob.data.materials.append(mat)

    cam = H.camera("cam", ((X0 + X1) * 0.5, 6.0, (Z0 + Z1) * 0.5),
                   ((X0 + X1) * 0.5, 0.0, (Z0 + Z1) * 0.5), ortho=(Z1 - Z0))
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 8
    sc.cycles.use_denoising = False
    sc.render.resolution_x = 512
    sc.render.resolution_y = 512
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "BW"
    sc.render.image_settings.color_depth = "8"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.filepath = os.path.join(OUT, "_surf_brick_probe.png")
    bpy.ops.render.render(write_still=True)
    print("[probe] wrote", sc.render.filepath, flush=True)
    print("[probe] world window x=%.2f..%.2f  z=%.2f..%.2f  (%.4f m / px)"
          % (X0, X1, Z0, Z1, (X1 - X0) / 512.0), flush=True)


build()
