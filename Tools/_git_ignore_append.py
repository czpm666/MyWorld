import os, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"E:\My World"
os.chdir(ROOT)

BLOCK = b"""
# =====================================================================
# Blender \xe7\x8e\x8b\xe9\x83\xbd\xe6\x8b\xbf\xe7\xae\xa1\xe7\xba\xbf\xef\xbc\x882026-11-02\xef\xbc\x89\xef\xbc\x9a\xe5\x8f\xaa\xe5\x85\xa5\xe5\xba\x93\xe6\xba\x90\xe7\xa0\x81\xef\xbc\x8c\xe4\xba\x8c\xe8\xbf\x9b\xe5\x88\xb6\xe4\xba\xa7\xe7\x89\xa9\xe4\xb8\x8d\xe5\x85\xa5\xe5\xba\x93
# =====================================================================
"""

LINES = [
    "",
    "# --- .blend / .blend1 / .fbx 导出（72 个 blend 合计 7.8 GB，单文件 1.4 GB）",
    "#     GitHub 硬限 100 MB/文件、建议仓库 < 1 GB。城市可用",
    "#     `python capital.py --stage full --hd --dense --plan2` 完整重建。",
    "/Blender/renders/",
    "/Blender/export/",
    "*.blend",
    "*.blend1",
    "",
    "# --- 素材候选池 / 质检产物 / 评审图（共 1.9 GB，属于过程物）",
    "/AssetCandidates/",
    "/WorkQC/",
    "/.hdreview/",
    "/.qc_tmp/",
    "/renders/",
    "",
    "# --- Python 缓存",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "",
]

with open(".gitignore", "ab") as fh:
    fh.write(b"\n" + "".join(l + "\n" for l in LINES).encode("utf-8"))

print("[ignore] appended %d lines to .gitignore" % len(LINES))
head = open(".gitignore", "rb").read(300)
print("[ignore] first bytes ok:", head[:8])
