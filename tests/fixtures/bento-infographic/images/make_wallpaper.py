"""Synthetic hero wallpaper for the bento product example: layered curved fields in the library's badge blue
(#2f81f7), each with a light rim and a soft shadow on the layer beneath, so the surface reads as stacked sheets
(round 10 review: a flat gradient with three discs looked like a default wallpaper). One hue only; the middle
stays dark enough for white type (>= 3:1). Deterministic. Usage: python3 make_wallpaper.py out.jpg"""
import sys
import numpy as np
from PIL import Image

W, H = 2400, 1350
y, x = np.mgrid[0:H, 0:W].astype(np.float64)


def rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float64) / 255.0


def lin(c0, c1, t):
    t = np.clip(t, 0, 1)[..., None]
    return (1 - t) * rgb(c0) + t * rgb(c1)


# background: deep blue, lighter towards the upper left
img = lin("#2468da", "#0a2c7e", 0.45 * x / W + 0.55 * y / H)


def sheet(img, cx, cy, r, c_edge, c_inner, depth, rim="#9fd0ff", rim_w=10.0, shadow=0.30, shadow_w=90.0):
    """One curved sheet: a disc whose edge catches the light, shading inwards over `depth` px, casting a soft
    shadow on what lies under it."""
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    outside = np.clip(d - r, 0, None)
    img = img * (1 - shadow * np.exp(-outside / shadow_w) * (d > r))[..., None]
    inside = np.clip(r - d, 0, None)
    fill = lin(c_edge, c_inner, inside / depth)
    glow = np.exp(-(inside / rim_w) ** 2)[..., None]
    fill = fill * (1 - 0.55 * glow) + rgb(rim) * 0.55 * glow
    m = np.clip((r - d) / 2.0 + 0.5, 0, 1)[..., None]                 # anti-aliased edge
    return img * (1 - m) + fill * m


# back to front
img = sheet(img, W * 0.42, H * -2.20, H * 2.52, "#5fa8ff", "#2a78ee", 700, shadow=0.38)   # broad sheet over the top
img = sheet(img, W * 0.97, H * -0.70, H * 0.95, "#8cc4ff", "#3d8cf8", 520, shadow=0.30)   # pale field, top right
img = sheet(img, W * -0.12, H * 1.38, H * 0.84, "#3f8cff", "#0d3c9c", 460)                 # lower left swell
img = sheet(img, W * 1.10, H * 1.66, H * 1.10, "#5aa6ff", "#1c64e0", 600, shadow=0.40)    # lower right swell
img = sheet(img, W * 0.36, H * 1.94, H * 1.06, "#4f9bff", "#123f9e", 380, shadow=0.38)    # front ridge across the bottom

# soft light from the upper middle, darker corners
light = np.exp(-(((x - 0.48 * W) / (0.55 * W)) ** 2 + ((y - 0.30 * H) / (0.55 * H)) ** 2))
vignette = 1 - 0.18 * np.clip(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2 - 0.35, 0, 1)
img = img * (0.94 + 0.10 * light)[..., None] * vignette[..., None]

out = Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")
out.save(sys.argv[1], quality=92, optimize=True)
