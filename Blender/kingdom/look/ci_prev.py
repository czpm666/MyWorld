"""Render the six design shots from the module's own preview()."""
import sys
import os
import time
import ctypes
import ctypes.wintypes as wt

sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")


def peak_mb():
    class PMC(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]
    pm = PMC()
    pm.cb = ctypes.sizeof(PMC)
    ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pm), pm.cb)
    return pm.PeakWorkingSetSize / 1048576.0


t0 = time.time()
import hd_castle_int as CI
print("IMPORT ok %.1fs" % (time.time() - t0), flush=True)
res = CI.preview(samples=int(os.environ.get("CI_S", "8")),
                 res=(int(os.environ.get("CI_X", "480")),
                      int(os.environ.get("CI_Y", "270"))),
                 tag=os.environ.get("CI_TAG", "p1"))
print("MEM peak %.0f MB" % peak_mb(), flush=True)
print("TOTAL %.1fs" % (time.time() - t0), flush=True)
