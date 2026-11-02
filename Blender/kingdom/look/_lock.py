r"""One-Blender-at-a-time gate, shared by every agent on this box.

Why: on 2026-10-31 six Blender processes (each ~10 GB RSS) ran at once on a
31 GB machine.  The kernel killed an allocation mid-build and the box went
down.  A 25 minute city build was lost.

    import sys
    sys.path.insert(0, r"E:\My World\Blender\kingdom\look")
    from _lock import blender

    with blender("land_lab", timeout=2400):
        subprocess.run([...], check=True)

The lock is a directory: mkdir is atomic on NTFS.  The holder writes meta.json
and touches it every 20 s, so a crashed holder is detected either by a dead
pid or by a stale heartbeat and evicted instead of deadlocking the fleet.

ZOMBIE CHILD WATCHDOG (added 2026-11-02)
----------------------------------------
Two runs held the lock for 20+ minutes because a blender.exe had *finished its
work* but never exited (GPU driver stall / modal dialog / stdout buffer).  The
python holder was healthy, so the heartbeat kept the lock fresh and six agents
queued behind a process that was doing nothing.

`run_blender` now watches the child: if its kernel+user CPU time and its log
size both stop advancing for `idle_kill` seconds, the child is killed and the
lock is released with rc=-11.  A healthy Blender always burns CPU (depsgraph,
tessellation, denoise) and almost always writes to stdout, so a 6 minute flat
window means it is stuck, not slow.

`run_blender(args, tag, timeout)` is a convenience wrapper that also writes a
log next to the others in E:\\My World\\Logs.
"""
import atexit
import ctypes
import ctypes.wintypes as wt
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time

BLENDER = r"E:\SteamLibrary\steamapps\common\Blender\blender.exe"
LOGDIR = r"E:\My World\Logs"
LOCKDIR = os.path.join(LOGDIR, "_blender.lock")
META = os.path.join(LOCKDIR, "meta.json")
# Light runs (a lab scene, a single module preview, a 480x270 sheet) do not need
# the whole machine: 1.5 GB and one GPU queue.  Two of them fit beside an 8 GB
# city load in 32 GB, which is why a single global mutex was wrong -- it
# serialised ten agents against one build and everyone sat in the queue for
# forty minutes.  Heavy runs still demand exclusivity; light runs only have to
# wait for the heavy ones.
#
# The count was three until the box froze a second time: slots count processes,
# but what actually runs out is memory, and three "lab" runs turned out to be
# two landscape labs plus a 1.5 GB city load.  Any command naming a blend over
# BIG_BLEND is therefore forced onto the exclusive path no matter what the
# caller asked for -- see effective_light().
LIGHTDIR = os.path.join(LOGDIR, "_blender.light")
MAX_LIGHT = 3
LIGHT_STALE = 240.0
BIG_BLEND = 400 * 1024 * 1024
# While this file exists, run_blender refuses any command that names a blend
# over BIG_BLEND.  The owner asked for the city-scale work to be held back until
# every module is finished, and a rule written in a brief is not a rule: two
# freezes came from somebody loading a 1.5 GB scene while labs were running.
# Delete the file to re-open the big path.
NO_BIG = os.path.join(LOGDIR, "_NO_BIG")
HEARTBEAT = 20.0
STALE = 300.0
IDLE_KILL = 360.0          # flat CPU *and* flat log for this long -> stuck
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def blend_size(args):
    """Largest .blend mentioned in a blender command line, or 0."""
    best = 0
    for a in args:
        if not isinstance(a, str) or not a.lower().endswith(".blend"):
            continue
        try:
            best = max(best, os.path.getsize(a))
        except OSError:
            continue
    return best


def _pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid],
                                 capture_output=True, text=True, timeout=20)
            return str(pid) in (out.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def cpu_seconds(pid):
    """Kernel+user CPU seconds of a pid, or None.  Windows only, no deps."""
    if os.name != "nt":
        try:
            import resource
            return float(resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime)
        except Exception:
            return None
    try:
        h = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    except Exception:
        return None
    if not h:
        return None
    try:
        creation, exit_, kern, user = (wt.FILETIME(), wt.FILETIME(),
                                       wt.FILETIME(), wt.FILETIME())
        ok = ctypes.windll.kernel32.GetProcessTimes(
            h, ctypes.byref(creation), ctypes.byref(exit_),
            ctypes.byref(kern), ctypes.byref(user))
        if not ok:
            return None
        k = (kern.dwHighDateTime << 32) | kern.dwLowDateTime
        u = (user.dwHighDateTime << 32) | user.dwLowDateTime
        return (k + u) / 1e7
    except Exception:
        return None
    finally:
        try:
            ctypes.windll.kernel32.CloseHandle(h)
        except Exception:
            pass


def _read_meta():
    try:
        with open(META, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _owner_alive():
    """Is the holder still working?

    The wrapper pid and the blender child pid are checked first, because the
    mtime heartbeat alone produces a zombie: when a waiter kills the wrapper
    (Ctrl-C on the job, an editor re-run) the heartbeat thread dies with it, but
    meta.json keeps a fresh mtime for the whole STALE window, so seven agents
    sit in the queue for five minutes behind a process that does not exist.
    Only when neither pid is alive AND nothing is recorded do we trust mtime.
    """
    meta = _read_meta()
    pid = meta.get("pid")
    if pid and _pid_alive(pid):
        return True
    child = meta.get("child")
    if child and _pid_alive(child):
        # the wrapper exited (killed, or it detached) but blender.exe is still
        # running and still holds stdout: the lock is legitimately held
        return True
    if pid or child:
        return False
    try:
        age = time.time() - os.path.getmtime(META)
    except OSError:
        try:
            age = time.time() - os.path.getmtime(LOCKDIR)
        except OSError:
            return False
    return age < STALE


def _evict(reason):
    print("[lock] evicting %s (%s)" % (LOCKDIR, reason), flush=True)
    try:
        shutil.rmtree(LOCKDIR)
    except OSError:
        pass


def heavy_held():
    """True while a city-scale build owns the exclusive lock."""
    if not os.path.isdir(LOCKDIR):
        return False
    if _owner_alive():
        return True
    _evict("owner dead or stale")
    return False


class light_gate(object):
    """A shared slot for small Blender runs; waits only on heavy builds.

    Three slots, no ordering: a lab that takes 25 s should never be queued
    behind another lab.  A slot whose owner pid and blender pid are both gone is
    reclaimed immediately, so a killed lab does not cost anyone a slot.
    """

    def __init__(self, tag, timeout=1200, poll=2.0, verbose=True, pinned=False):
        self.tag = tag
        self.timeout = timeout
        self.poll = poll
        self.verbose = verbose
        self.pinned = pinned
        self.child = None
        self.slot = None

    def _meta(self):
        return {"tag": self.tag, "pid": os.getpid(), "child": self.child,
                "pinned": self.pinned, "host": socket.gethostname(),
                "t": time.time(), "light": True}

    def _write(self):
        try:
            with open(os.path.join(self.slot, "meta.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(self._meta(), fh)
        except OSError:
            pass

    def set_child(self, pid):
        self.child = int(pid) if pid else None
        if self.slot:
            self._write()

    @staticmethod
    def _slot_alive(path):
        meta = {}
        try:
            with open(os.path.join(path, "meta.json"), "r", encoding="utf-8") as fh:
                meta = json.load(fh)
        except Exception:
            try:
                return (time.time() - os.path.getmtime(path)) < LIGHT_STALE
            except OSError:
                return False
        for key in ("pid", "child"):
            pid = meta.get(key)
            if pid and _pid_alive(pid):
                return True
        return (time.time() - meta.get("t", 0.0)) < LIGHT_STALE

    def acquire(self):
        deadline = time.time() + self.timeout
        waited = False
        while True:
            if heavy_held():
                if time.time() > deadline:
                    raise TimeoutError(
                        "[lock] light %r gave up after %.0f s: a heavy build holds %s"
                        % (self.tag, self.timeout, LOCKDIR))
                if not waited and self.verbose:
                    print("[lock] light %r waiting for the heavy build (%r) ..."
                          % (self.tag, _read_meta().get("tag")), flush=True)
                waited = True
                time.sleep(self.poll)
                continue
            try:
                os.makedirs(LIGHTDIR, exist_ok=True)
            except OSError:
                pass
            for i in range(MAX_LIGHT):
                path = os.path.join(LIGHTDIR, "slot%d" % i)
                try:
                    os.makedirs(path)
                except FileExistsError:
                    if not self._slot_alive(path):
                        print("[lock] reclaiming stale light slot %d" % i, flush=True)
                        try:
                            shutil.rmtree(path)
                        except OSError:
                            pass
                    continue
                self.slot = path
                self._write()
                atexit.register(self.release)
                if waited and self.verbose:
                    print("[lock] light acquired slot %d after %.0f s"
                          % (i, time.time() - (deadline - self.timeout)), flush=True)
                return self
            if time.time() > deadline:
                raise TimeoutError(
                    "[lock] light %r gave up after %.0f s: all %d slots busy"
                    % (self.tag, self.timeout, MAX_LIGHT))
            if not waited and self.verbose:
                print("[lock] light %r waiting for a free slot (%d/%d used) ..."
                      % (self.tag, MAX_LIGHT, MAX_LIGHT), flush=True)
            waited = True
            time.sleep(self.poll)

    def release(self):
        if not self.slot:
            return
        try:
            shutil.rmtree(self.slot)
        except OSError:
            pass
        self.slot = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *a):
        self.release()
        return False


def light_status():
    """[(slot, tag, pid, alive), ...] for the light slots that exist."""
    out = []
    for i in range(MAX_LIGHT):
        path = os.path.join(LIGHTDIR, "slot%d" % i)
        if not os.path.isdir(path):
            continue
        try:
            with open(os.path.join(path, "meta.json"), "r", encoding="utf-8") as fh:
                m = json.load(fh)
        except Exception:
            m = {}
        pid = m.get("pid")
        out.append((i, m.get("tag"), pid, bool(pid and _pid_alive(pid))))
    return out


class blender(object):
    """with blender("tag", timeout=1800): ..."""

    def __init__(self, tag, timeout=2400, poll=3.0, verbose=True, pinned=False):
        self.tag = tag
        self.timeout = timeout
        self.poll = poll
        self.verbose = verbose
        self.pinned = bool(pinned)
        self.held = False
        self.child = None
        self._beat = None
        self._stop = threading.Event()
        self._t0 = time.time()

    # -- internals -----------------------------------------------------
    def _touch(self):
        try:
            with open(META, "w", encoding="utf-8") as fh:
                json.dump({"tag": self.tag, "pid": os.getpid(),
                           "child": self.child,
                           "pinned": self.pinned,
                           "host": socket.gethostname(),
                           "t": time.time()}, fh)
        except OSError:
            pass

    def set_child(self, pid):
        """Record the blender.exe pid so waiters can see what is running."""
        self.child = int(pid) if pid else None
        self._touch()

    def _heartbeat(self):
        while not self._stop.wait(HEARTBEAT):
            try:
                os.utime(META, None)
            except OSError:
                self._touch()

    def acquire(self):
        deadline = time.time() + self.timeout
        waited = False
        while True:
            try:
                os.makedirs(LOCKDIR)
                self._touch()
                self.held = True
                self._beat = threading.Thread(target=self._heartbeat, daemon=True)
                self._beat.start()
                atexit.register(self.release)
                if waited and self.verbose:
                    print("[lock] acquired after %.0f s" % (time.time() - self._t0,),
                          flush=True)
                return self
            except FileExistsError:
                if not _owner_alive():
                    _evict("owner dead or stale")
                    continue
                if time.time() > deadline:
                    raise TimeoutError(
                        "[lock] gave up after %.0f s waiting for %s (held by %r)"
                        % (self.timeout, LOCKDIR, _read_meta().get("tag")))
                if not waited and self.verbose:
                    m = _read_meta()
                    print("[lock] waiting for %r (pid=%s child=%s) ..."
                          % (m.get("tag"), m.get("pid"), m.get("child")),
                          flush=True)
                    waited = True
                time.sleep(self.poll)

    def release(self):
        if not self.held:
            return
        self.held = False
        self._stop.set()
        try:
            shutil.rmtree(LOCKDIR)
        except OSError:
            pass

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
        return False


def _wait_watched(p, log, timeout, idle_kill, tag):
    """p.wait() plus a stuck-child watchdog.  Returns (rc, why)."""
    t0 = time.time()
    last_cpu = None
    last_size = -1
    last_progress = t0
    while True:
        try:
            return p.wait(timeout=2.0), "exit"
        except subprocess.TimeoutExpired:
            pass
        now = time.time()
        if now - t0 > timeout:
            p.kill()
            return -9, "timeout %.0f s" % timeout
        cpu = cpu_seconds(p.pid)
        try:
            size = os.path.getsize(log)
        except OSError:
            size = -1
        moved = False
        if cpu is not None and last_cpu is not None and cpu - last_cpu > 0.4:
            moved = True
        if size != last_size:
            moved = True
        if moved:
            last_progress = now
        last_cpu = cpu if cpu is not None else last_cpu
        last_size = size
        if idle_kill and now - last_progress > idle_kill:
            p.kill()
            return -11, ("child stuck: no CPU and no log growth for %.0f s"
                         % (now - last_progress))


def run_blender(args, tag, timeout=2400, cwd=None, idle_kill=IDLE_KILL,
                pinned=False, light=False):
    """Run Blender under the lock, tee the output to Logs\\<tag>.log.

    Returns (returncode, log_path).  Raises nothing on a non-zero exit: the
    caller decides.  Prints the tail of the log so the agent sees the failure.
    rc=-11 means the watchdog killed a stuck child (see module docstring).

    pinned=True marks this run as un-killable by `python look\\_lock.py kill`
    (only `kill --force` can take it down).  Grand builds take 20-40 minutes and
    write one long line of progress every 2-10 seconds, so a waiter that reads a
    stale meta.json or decides the child "looks idle" must not be allowed to
    kill them: that is exactly how build_v25 died at block 91 with no error.

    light=True takes one of MAX_LIGHT shared slots instead of the exclusive
    lock, so small lab runs proceed while a build is going.  Use it for any run
    that opens a scene under ~200 MB; leave it off for the city blend.
    """
    os.makedirs(LOGDIR, exist_ok=True)
    log = os.path.join(LOGDIR, "%s.log" % tag)
    cmd = [BLENDER] + list(args)
    size = blend_size(args)
    if size > BIG_BLEND and os.path.exists(NO_BIG):
        msg = ("[lock] REFUSED %r: it opens a %.0f MB blend while %s exists.\n"
               "[lock] The city-scale path is being held back until the module "
               "work is finished.  Work in a lab scene (<200 MB) and keep the "
               "result in a module; the owner will run the big build himself."
               % (tag, size / 1048576.0, NO_BIG))
        print(msg, flush=True)
        try:
            with open(os.path.join(LOGDIR, "%s.log" % tag), "w",
                      encoding="utf-8") as fh:
                fh.write(msg + "\n")
        except OSError:
            pass
        return -7, os.path.join(LOGDIR, "%s.log" % tag)
    if light and size > BIG_BLEND:
        print("[lock] %r asked for a light slot but loads a %.0f MB blend: "
              "taking the exclusive lock instead (this is the memory guard)"
              % (tag, size / 1048576.0), flush=True)
        light = False
    if not light and size > BIG_BLEND:
        pinned = pinned or True
    gate_cls = light_gate if light else blender
    with gate_cls(tag, timeout=timeout, pinned=pinned) as gate:
        t0 = time.time()
        with open(log, "wb") as fh:
            p = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=cwd)
            gate.set_child(p.pid)
            rc, why = _wait_watched(p, log, timeout, idle_kill, tag)
        print("[lock] %s exit=%d (%s) in %.1f s -> %s"
              % (tag, rc, why, time.time() - t0, log), flush=True)
    try:
        with open(log, "r", encoding="utf-8", errors="replace") as fh:
            tail = fh.readlines()[-12:]
        print("".join(tail), flush=True)
    except OSError:
        pass
    return rc, log


def status():
    lights = light_status()
    ltxt = "  light slots: %d/%d used%s" % (
        len(lights), MAX_LIGHT,
        ("  [" + ", ".join("%d:%s" % (i, t) for (i, t, _p, _a) in lights) + "]")
        if lights else "")
    if not os.path.isdir(LOCKDIR):
        return "free" + ltxt
    meta = _read_meta()
    out = "held by %r pid=%s child=%s alive=%s%s" % (
        meta.get("tag"), meta.get("pid"), meta.get("child"), _owner_alive(),
        "  *** PINNED (do not kill) ***" if meta.get("pinned") else "")
    child = meta.get("child")
    if child:
        c = cpu_seconds(child)
        if c is not None:
            out += " child_cpu=%.1fs" % c
    if meta.get("pinned"):
        out += "  [pinned builds: only `kill --force` takes them down]"
    return out + ltxt


def kill_stuck(force=False):
    """Kill the holder's blender child if it is stuck.  Manual escape hatch."""
    meta = _read_meta()
    child = meta.get("child")
    if meta.get("pinned") and not force:
        print("[lock] refusing: %r is PINNED (a grand build). "
              "Waited builds must not kill them. Use `kill --force` only if you "
              "have watched it for minutes with a frozen log." % meta.get("tag"),
              flush=True)
        return False
    if child and _pid_alive(child):
        c0 = cpu_seconds(child)
        time.sleep(15.0)
        c1 = cpu_seconds(child)
        if c0 is not None and c1 is not None and (c1 - c0) < 0.4:
            subprocess.run(["taskkill", "/F", "/PID", str(child)],
                           capture_output=True)
            print("[lock] killed stuck child %s (cpu %.1f -> %.1f)"
                  % (child, c0, c1), flush=True)
            return True
        print("[lock] child %s is working (cpu %.1f -> %.1f)"
              % (child, c0 or -1, c1 or -1), flush=True)
        return False
    print("[lock] no live child", flush=True)
    return False


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "clear":
        _evict("manual")
    elif what == "kill":
        kill_stuck(force=("--force" in sys.argv[2:]))
    elif what == "cpu":
        for a in sys.argv[2:]:
            print("%s  %.1f s" % (a, cpu_seconds(a) or -1.0))
    print(status())
