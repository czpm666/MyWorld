# -*- coding: utf-8 -*-
"""_run.py - run one Blender python script under the shared one-at-a-time lock.

    python look\\_run.py <tag> <script.py> [timeout] [LIGHT]

`LIGHT` takes one of the three shared light slots instead of the exclusive
heavy lock -- correct for these small interior scenes, and it means a 20 s
acceptance render never queues behind the 20-minute city rebuild.

Prints the lock's tail so the caller sees failures without opening the log.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _lock import run_blender  # noqa: E402

tag = sys.argv[1]
script = sys.argv[2]
timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 2400
light = any(a.upper() == "LIGHT" for a in sys.argv[4:])
rc, log = run_blender(["-b", "--factory-startup", "--python", script],
                      tag, timeout=timeout, cwd=os.path.dirname(HERE),
                      light=light)
print("RC", rc)
sys.exit(0)
