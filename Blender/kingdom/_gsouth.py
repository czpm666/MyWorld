"""`south` at its original 1600x900 (the 15 + 1 shot set uses 1400x900)."""
import sys

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_gate as G                                            # noqa: E402

G.preview(samples=128, res=(1600, 900), only=["south"])
