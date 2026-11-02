import io
p = "hd_sky.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('PRESET_NAMES = tuple(PRESETS)',
              'PRESET_NAMES = tuple(PRESETS)\n\n#: which node type the AP emitter actually became (diagnostic, see _ap_material)\n_AP_EM_KIND = {}')
s = s.replace('    print("[sky] AP installed on %d material(s), far=%s" %',
              '    print("[sky] AP em=%s  installed on %d material(s), far=%s" %\n          (_AP_EM_KIND.get("id"),')
assert '_AP_EM_KIND = {}' in s
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok")
