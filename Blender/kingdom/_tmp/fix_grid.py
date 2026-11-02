import io

p = r'E:\My World\Blender\kingdom\hd_layout.py'
s = io.open(p, encoding='utf-8').read()

s = s.replace('        grid.add(aabb_of(s["poly"]))',
              '        grid.add(s["poly"])')

old = """        if grid.fits(box):
            grid.add(box)"""
new = """        bp = [(box[0], box[1]), (box[2], box[1]),
              (box[2], box[3]), (box[0], box[3])]
        if grid.fits(bp):
            grid.add(bp)"""
assert old in s, 'market fountain grid block not found'
s = s.replace(old, new)

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('patched ok')
