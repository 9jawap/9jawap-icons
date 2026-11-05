#!/usr/bin/env python3
from pathlib import Path
from PIL import Image
import cv2
import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parent
SRC = Path('/home/ubuntu/upload/1000478878.png')
OUT = ROOT / 'dist'
OUT.mkdir(parents=True, exist_ok=True)

# Isolate the light foreground mark; discard transparent pixels and the green tile.
im = Image.open(SRC).convert('RGBA')
a = np.array(im)
rgb = a[:, :, :3]
alpha = a[:, :, 3]
bright = rgb.min(axis=2) >= 175
low_chroma = (rgb.max(axis=2) - rgb.min(axis=2)) <= 42
mask = ((alpha > 0) & bright & low_chroma).astype(np.uint8) * 255
# Close tiny antialiasing gaps without changing the intended silhouette materially.
k = np.ones((3, 3), np.uint8)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
if not contours:
    raise RuntimeError('No foreground mark found')
# Retain meaningful contours and approximate only insignificant raster noise.
paths = []
for i, c in enumerate(contours):
    area = abs(cv2.contourArea(c))
    if area < 8:
        continue
    eps = max(0.45, 0.0015 * cv2.arcLength(c, True))
    poly = cv2.approxPolyDP(c, eps, True)[:, 0, :]
    if len(poly) >= 3:
        paths.append((i, poly))
if not paths:
    raise RuntimeError('Foreground contours were too small')

# Use source pixel coordinates, y-up for font construction.
scale_a = 512.0 / im.width
all_pts = np.vstack([p for _, p in paths]).astype(float)
x0, y0 = all_pts.min(axis=0)
x1, y1 = all_pts.max(axis=0)
# Convert to 512 square, preserving original image placement then center the mark.
def transform(points, size, margin=0.0):
    pts = points.astype(float)
    w, h = x1-x0, y1-y0
    s = (size - 2*margin) / max(w, h)
    ox = (size - w*s)/2 - x0*s
    oy = (size - h*s)/2 - y0*s
    # source y-down -> SVG y-down; font helper separately flips y.
    return pts*s + np.array([ox, oy])

def d_for(size, margin):
    chunks=[]
    for _, poly in paths:
        q=transform(poly,size,margin)
        chunks.append('M ' + ' L '.join(f'{x:.2f},{y:.2f}' for x,y in q) + ' Z')
    return ' '.join(chunks)

svg_a = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="{d_for(512, 24)}"/></svg>\n'''
svg_b = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="{d_for(24, 1.125)}"/></svg>\n'''
(OUT/'9jawap-512.svg').write_text(svg_a)
(OUT/'9jawap-24.svg').write_text(svg_b)

# Build a compact TTF from the same single-color contour geometry, then export WOFF/WOFF2.
upem=1000
font=FontBuilder(upem, isTTF=True)
font.setupGlyphOrder(['.notdef','9jawap'])
font.setupCharacterMap({0xE900:'9jawap'})
pen=TTGlyphPen(None)
# Font coordinates: use the 512 geometry scaled to 1000, y-up.
for _, poly in paths:
    q=transform(poly, upem, 46)
    pen.moveTo((q[0,0], upem-q[0,1]))
    for x,y in q[1:]: pen.lineTo((x, upem-y))
    pen.closePath()
glyph=pen.glyph()
font.setupGlyf({'.notdef': TTGlyphPen(None).glyph(), '9jawap': glyph})
font.setupHorizontalMetrics({'.notdef':(600,0),'9jawap':(1000,0)})
font.setupHorizontalHeader(ascent=800, descent=-200)
font.setupNameTable({'familyName':'9jawap Icons','styleName':'Regular','uniqueFontIdentifier':'9jawap Icons Regular','fullName':'9jawap Icons Regular','psName':'9jawapIcons-Regular','version':'Version 1.0'})
font.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200,usWeightClass=400)
font.setupPost()
ttf=OUT/'9jawap-icons.ttf'
font.save(str(ttf))
for flavor, target in [('woff', OUT/'9jawap-icons.woff'), ('woff2', OUT/'9jawap-icons.woff2')]:
    webfont = TTFont(str(ttf))
    webfont.flavor = flavor
    webfont.save(str(target))

def css_url(name): return f'url("./{name}") format("{name.split(".")[-1]}")'
css='''@font-face {\n  font-family: "9jawap Icons";\n  font-style: normal;\n  font-weight: 400;\n  font-display: block;\n  src: url("./9jawap-icons.woff2") format("woff2"),\n       url("./9jawap-icons.woff") format("woff");\n}\n\n.jw {\n  display: inline-block;\n  font-family: "9jawap Icons" !important;\n  font-style: normal;\n  font-weight: 400;\n  font-variant: normal;\n  line-height: 1;\n  text-rendering: auto;\n  -webkit-font-smoothing: antialiased;\n  -moz-osx-font-smoothing: grayscale;\n}\n\n.jw-9jawap::before { content: "\\e900"; }\n'''
(OUT/'9jawap-icons.min.css').write_text(css)
(OUT/'README.md').write_text('''# 9jawap Icons\n\nWebfont kit for the official 9jawap brand icon.\n\n```html\n<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/OWNER/9jawap-icons@v1.0.0/dist/9jawap-icons.min.css">\n<i class="jw jw-9jawap" aria-hidden="true"></i>\n```\n\nReplace `OWNER` with the GitHub account owner after publishing.\n''')
print(f'Wrote {OUT}')
