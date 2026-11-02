import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lock

print("status:", _lock.status())
print("self cpu: %.2f s" % (_lock.cpu_seconds(os.getpid()) or -1.0))
t = _lock.cpu_seconds(os.getpid())
x = 0
for i in range(4000000):
    x += i
print("delta after busy loop: %.2f s" % ((_lock.cpu_seconds(os.getpid()) or 0) - t))
print("bogus pid:", _lock.cpu_seconds(999999))
