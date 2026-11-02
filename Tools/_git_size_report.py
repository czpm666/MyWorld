import os, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"E:\My World"

def out(args):
    return subprocess.run(args, cwd=ROOT, capture_output=True).stdout

raw = out(["git", "ls-files", "--others", "--exclude-standard", "-z"])
paths = [p.decode("utf-8", "surrogateescape") for p in raw.split(b"\0") if p]
print("untracked files:", len(paths))

rows = []
total = 0
for p in paths:
    fp = os.path.join(ROOT, p)
    try:
        n = os.path.getsize(fp)
    except OSError:
        n = 0
    total += n
    rows.append((n, p))
print("untracked total: %.2f GB" % (total / 1024 ** 3))

rows.sort(reverse=True)
print("\n=== 25 largest untracked ===")
for n, p in rows[:25]:
    print("%8.1f MB  %s" % (n / 1024 ** 2, p))

big = [r for r in rows if r[0] > 90 * 1024 ** 2]
print("\nfiles over 90 MB (GitHub hard-blocks >100 MB): %d" % len(big))
for n, p in big[:20]:
    print("  %8.1f MB  %s" % (n / 1024 ** 2, p))

by_ext = {}
for n, p in rows:
    e = os.path.splitext(p)[1].lower() or "(none)"
    a = by_ext.setdefault(e, [0, 0])
    a[0] += 1
    a[1] += n
print("\n=== by extension (top 20 by size) ===")
for e, (c, s) in sorted(by_ext.items(), key=lambda kv: -kv[1][1])[:20]:
    print("%6d files %8.1f MB  %s" % (c, s / 1024 ** 2, e))
