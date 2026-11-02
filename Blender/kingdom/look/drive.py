r"""drive.py -- run a Blender lab under the shared lock and report peak RSS.

    python look\drive.py --tag t1 -- --module hd_cathedral_int --res 480x270

Everything after `--` is forwarded to Blender after the `--python <lab>` part.
`--lab` selects the script (default look\cath_lab.py).
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from _lock import blender, BLENDER, LOGDIR                          # noqa: E402

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010


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


def proc_mem(pid):
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ps = ctypes.WinDLL("psapi", use_last_error=True)
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        return None
    try:
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        if ps.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
            return pmc.WorkingSetSize / 1048576.0, pmc.PeakWorkingSetSize / 1048576.0
    finally:
        k32.CloseHandle(h)
    return None


def watch(p, box, stop):
    while not stop.is_set():
        try:
            m = proc_mem(p.pid)
        except Exception:
            m = None
        if m:
            box["cur"], box["peak"] = m
        time.sleep(1.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="lab")
    ap.add_argument("--lab", default="cath_lab.py")
    ap.add_argument("--timeout", type=float, default=3600.0)
    ap.add_argument("--blend", default="", help="open this .blend first")
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args()

    rest = list(a.rest)
    if rest and rest[0] == "--":
        rest = rest[1:]

    lab = a.lab if os.path.isabs(a.lab) else os.path.join(HERE, a.lab)
    cmd = [BLENDER, "-b"]
    cmd += ["--factory-startup"] if not a.blend else []
    if a.blend:
        cmd.append(a.blend)
    cmd += ["--python", lab, "--"] + rest

    os.makedirs(LOGDIR, exist_ok=True)
    log = os.path.join(LOGDIR, "%s.log" % a.tag)
    print("[drive] " + " ".join(cmd), flush=True)
    t0 = time.time()
    box = {"cur": 0.0, "peak": 0.0}
    stop = threading.Event()
    with blender(a.tag, timeout=a.timeout):
        with open(log, "wb") as fh:
            p = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=KING)
            th = threading.Thread(target=watch, args=(p, box, stop), daemon=True)
            th.start()
            rc = p.wait()
            stop.set()
    dt = time.time() - t0
    print("[drive] exit=%d in %.1fs  peakRSS=%.0f MB  log=%s"
          % (rc, dt, box["peak"], log), flush=True)
    try:
        with open(log, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        keep = [l for l in lines if l.startswith("[lab]") or l.startswith("[hd]")
                or "Error" in l or "Traceback" in l or l.startswith("  File")
                or l.startswith("    ") or "Exception" in l or "SUMMARY" in l]
        if len(keep) > 90:
            keep = keep[:6] + ["...\n"] + keep[-84:]
        sys.stdout.write("".join(keep))
    except OSError:
        pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
