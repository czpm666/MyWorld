"""One-shot: rescale the 10 presets' halo amplitudes for the Gaussian Mie.

The old values were amplitudes on a Henyey-Greenstein phase whose peak is
(1-g)^-1.5, so `halo_core=1.0` meant 68x the sky.  The new Mie is a Gaussian in
angle with a peak of 1.0, so the same *look* needs the old number / ~4.
"""
import io

P = r'E:\My World\Blender\kingdom\hd_sky.py'
PAIRS = [
    ('glow=0.85, halo_wide=0.62, halo_core=1.00', 'glow=0.85, halo_wide=0.13, halo_core=0.46'),
    ('glow=0.58, halo_wide=0.44, halo_core=0.80', 'glow=0.58, halo_wide=0.09, halo_core=0.36'),
    ('glow=0.34, halo_wide=0.30, halo_core=0.70', 'glow=0.34, halo_wide=0.06, halo_core=0.32'),
    ('glow=1.00, halo_wide=0.75, halo_core=1.10', 'glow=1.00, halo_wide=0.16, halo_core=0.50'),
    ('glow=0.10, halo_wide=0.05, halo_core=0.05', 'glow=0.10, halo_wide=0.02, halo_core=0.03'),
    ('glow=1.30, halo_wide=1.05, halo_core=1.20', 'glow=1.30, halo_wide=0.15, halo_core=0.45'),
    ('glow=0.20, halo_wide=0.22, halo_core=0.55', 'glow=0.20, halo_wide=0.04, halo_core=0.22'),
    ('glow=0.32, halo_wide=0.18, halo_core=0.30', 'glow=0.32, halo_wide=0.04, halo_core=0.14'),
    ('glow=0.55, halo_wide=0.55, halo_core=0.45', 'glow=0.55, halo_wide=0.10, halo_core=0.18'),
    ('glow=0.92, halo_wide=0.66, halo_core=0.95', 'glow=0.92, halo_wide=0.12, halo_core=0.40'),
]

s = io.open(P, encoding='utf-8').read()
for a, b in PAIRS:
    print(s.count(a), a)
    s = s.replace(a, b)
io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('written')
