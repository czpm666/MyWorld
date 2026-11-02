"""Final deliverable renders: every shipped camera at 1400x900 / 128 spp.

`south` is 1600x900 (its own original size) and therefore runs in a separate
process: a second preview() call in the same process dies with
"ReferenceError: StructRNA of type Material has been removed", because
H._clear() invalidates the palette the module still holds.

    blender -b --factory-startup --python _gfinal.py
    blender -b --factory-startup --python _gsouth.py
"""
import sys

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_gate as G                                            # noqa: E402

G.preview(samples=128, res=(1400, 900), only=[n for n, *_ in G.SHOTS if n != "south"])
print("[final] done")
