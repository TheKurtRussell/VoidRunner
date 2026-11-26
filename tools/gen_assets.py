#!/usr/bin/env python3
"""
VoidRunner — isometric pixel-art asset generator.

Authors a cyberpunk isometric tileset offline with Pillow and emits VoidRunner's
asset format: flat RGB565 C arrays with colour-key transparency (0x0000 == clear),
consumed by game_world.c's blit_2x (2x nearest-neighbour upscale on device).

Tiles are authored at a 64-wide base and doubled on the Tab5, so a floor diamond
is 128x64 on screen. Buildings/props rise above their base diamond; characters
stand bottom-centre on their tile.

This runs locally (needs Pillow + numpy); the generated vr_assets.c/.h are
committed, so CI just compiles them — no image libs needed in the build.
Regenerate after editing:  python3 tools/gen_assets.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "main", "assets")
os.makedirs(OUT, exist_ok=True)

TW, TH = 64, 32          # floor tile base size
HW, HH = 32, 16          # half

# ---- palette (RGB) ---------------------------------------------------------
CYAN = (0, 240, 255)
MAG  = (255, 42, 165)
GRN  = (40, 235, 120)
AMB  = (255, 185, 40)
WHT  = (225, 235, 248)

def sh(c, f):
    return tuple(max(0, min(255, int(c[i] * f))) for i in range(3))

def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))

def img(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))

def noise(im, amt, seed):
    rng = np.random.default_rng(seed)
    a = np.array(im).astype(np.int16)
    m = a[:, :, 3] > 0
    n = rng.integers(-amt, amt + 1, size=a.shape[:2])
    for c in range(3):
        a[:, :, c] = np.where(m, np.clip(a[:, :, c] + n, 0, 255), a[:, :, c])
    return Image.fromarray(a.astype(np.uint8), "RGBA")

def fpt(corners, u, v):
    TL, TR, BL = corners
    return (TL[0] + u * (TR[0] - TL[0]) + v * (BL[0] - TL[0]),
            TL[1] + u * (TR[1] - TL[1]) + v * (BL[1] - TL[1]))

def fquad(c, u0, u1, v0, v1):
    return [fpt(c, u0, v0), fpt(c, u1, v0), fpt(c, u1, v1), fpt(c, u0, v1)]

DIAMOND = [(32, 0), (64, 16), (32, 32), (0, 16)]

# ---- floor tiles -----------------------------------------------------------
def floor(base, variant=None, seed=1):
    im = img(TW, TH)
    grad = img(TW, TH)
    gd = ImageDraw.Draw(grad)
    for y in range(TH):
        t = y / TH
        gd.line([(0, y), (TW, y)], fill=sh(base, 1.10 - 0.34 * t) + (255,))
    mask = Image.new("L", (TW, TH), 0)
    ImageDraw.Draw(mask).polygon(DIAMOND, fill=255)
    im = Image.composite(grad, im, mask)
    im = noise(im, 7, seed)
    d = ImageDraw.Draw(im)
    hi, lo = sh(base, 1.7), sh(base, 0.5)
    d.line([(0, 16), (32, 0)], fill=hi + (255,))
    d.line([(32, 0), (64, 16)], fill=hi + (255,))
    d.line([(0, 16), (32, 32)], fill=lo + (255,))
    d.line([(32, 32), (64, 16)], fill=lo + (255,))
    if variant == "sidewalk":
        for gx in range(8, 60, 12):
            d.line([(gx, 16 + gx // 8), (gx + 8, 12)], fill=sh(base, 0.55) + (120,))
        d.line([(0, 16), (32, 0)], fill=CYAN + (120,))
    elif variant == "puddle":
        pud = img(TW, TH)
        pd = ImageDraw.Draw(pud)
        small = [(32, 7), (54, 16), (32, 25), (10, 16)]
        for yy in range(7, 26):
            t = (yy - 7) / 19
            pd.line([(0, yy), (TW, yy)], fill=lerp((14, 20, 32), CYAN, 0.12 + 0.5 * t) + (255,))
        pm = Image.new("L", (TW, TH), 0)
        ImageDraw.Draw(pm).polygon(small, fill=255)
        im = Image.composite(pud, im, pm)
        d = ImageDraw.Draw(im)
        d.line([(16, 20), (30, 22)], fill=MAG + (150,))
        d.line([(36, 14), (50, 16)], fill=CYAN + (170,))
    elif variant == "jackpoint":
        def pl(a, b, t):
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        ctr = (32, 16)
        for k in range(1, 5):
            t = k / 5
            dp = [pl((32, 0), ctr, t), pl((64, 16), ctr, t),
                  pl((32, 32), ctr, t), pl((0, 16), ctr, t)]
            d.polygon(dp, outline=sh(CYAN, 1.0 - t * 0.5) + (255,))
        d.line([(0, 16), (32, 0)], fill=CYAN + (255,))
        d.line([(32, 0), (64, 16)], fill=CYAN + (255,))
        d.line([(0, 16), (32, 32)], fill=MAG + (255,))
        d.line([(32, 32), (64, 16)], fill=MAG + (255,))
    return im, 32, 16   # anchor: diamond centre

# ---- building / wall cube --------------------------------------------------
def building(base, win_color, height=64, door=False, windows=(3, 4), seed=2):
    W, H = TW, TH + height
    im = img(W, H)
    d = ImageDraw.Draw(im)
    top = [(32, 0), (64, 16), (32, 32), (0, 16)]
    left = [(0, 16), (32, 32), (32, 32 + height), (0, 16 + height)]
    right = [(32, 32), (64, 16), (64, 16 + height), (32, 32 + height)]
    d.polygon(left, fill=sh(base, 0.6) + (255,))
    d.polygon(right, fill=sh(base, 0.9) + (255,))
    d.polygon(top, fill=sh(base, 1.25) + (255,))
    im = noise(im, 6, seed)
    d = ImageDraw.Draw(im)
    d.line([(0, 16), (32, 0)], fill=sh(base, 1.7) + (255,))
    d.line([(32, 0), (64, 16)], fill=sh(base, 1.7) + (255,))
    d.line([(32, 32), (32, 32 + height)], fill=sh(base, 0.4) + (255,))
    d.line([(0, 16), (0, 16 + height)], fill=sh(base, 0.4) + (255,))
    L = ((0, 16), (32, 32), (0, 16 + height))
    R = ((32, 32), (64, 16), (32, 32 + height))
    cols, rows = windows
    for face, bias in ((L, 0.0), (R, 0.12)):
        for r in range(rows):
            for c in range(cols):
                lit = ((c * 7 + r * 5 + seed) % 10) / 10.0 > (0.45 - bias)
                q = fquad(face, (c + 0.24) / cols, (c + 0.76) / cols,
                          (r + 0.18) / rows, (r + 0.72) / rows)
                if lit:
                    d.polygon(q, fill=win_color + (255,))
                    cq = fquad(face, (c + 0.36) / cols, (c + 0.64) / cols,
                               (r + 0.28) / rows, (r + 0.5) / rows)
                    d.polygon(cq, fill=sh(win_color, 1.4) + (255,))
                else:
                    d.polygon(q, fill=sh(base, 0.32) + (255,))
    if door:
        d.polygon(fquad(R, 0.30, 0.70, 0.30, 0.96), fill=sh(base, 0.2) + (255,))
        d.polygon(fquad(R, 0.36, 0.64, 0.36, 0.92), fill=sh(CYAN, 0.55) + (255,))
        d.line([fpt(R, 0.5, 0.36), fpt(R, 0.5, 0.92)], fill=CYAN + (255,), width=1)
        lk = fpt(R, 0.6, 0.46)
        d.ellipse([lk[0] - 2, lk[1] - 2, lk[0] + 2, lk[1] + 2], fill=GRN + (255,))
    return im, 32, 32 + height   # anchor: base diamond centre

# ---- props -----------------------------------------------------------------
def sign(seed=3):
    h = 48
    W, H = TW, TH + h
    im = img(W, H)
    d = ImageDraw.Draw(im)
    d.line([(32, TH + h), (32, 34)], fill=(40, 44, 58, 255), width=2)
    d.rectangle([10, 4, 54, 34], fill=(10, 12, 22, 255), outline=CYAN + (255,), width=1)
    cols = [MAG, CYAN, GRN, AMB]
    x = 16
    for k in range(4):
        c = cols[k]
        d.rectangle([x, 10, x + 3, 28], fill=c + (255,))
        d.rectangle([x + 5, 10, x + 8, 17], fill=c + (255,))
        x += 11
    return im, 32, TH + h

def lamp(seed=4):
    h = 72
    W, H = TW, TH + h
    im = img(W, H)
    d = ImageDraw.Draw(im)
    d.line([(32, TH + h), (32, 20)], fill=(60, 66, 84, 255), width=3)
    d.rectangle([20, 12, 44, 24], fill=sh(MAG, 1.1) + (255,), outline=WHT + (255,))
    return im, 32, TH + h

def crate(seed=5):
    h = 26
    im, ax, ay = building((70, 58, 40), AMB, height=h, windows=(1, 1), seed=seed)
    # overwrite windows with crate bracing
    im = img(TW, TH + h)
    d = ImageDraw.Draw(im)
    top = [(32, 0), (64, 16), (32, 32), (0, 16)]
    left = [(0, 16), (32, 32), (32, 32 + h), (0, 16 + h)]
    right = [(32, 32), (64, 16), (64, 16 + h), (32, 32 + h)]
    b = (82, 66, 44)
    d.polygon(left, fill=sh(b, 0.6) + (255,))
    d.polygon(right, fill=sh(b, 0.95) + (255,))
    d.polygon(top, fill=sh(b, 1.3) + (255,))
    L = ((0, 16), (32, 32), (0, 16 + h))
    R = ((32, 32), (64, 16), (32, 32 + h))
    for face in (L, R):
        d.line([fpt(face, 0.1, 0.1), fpt(face, 0.9, 0.9)], fill=sh(b, 0.4) + (255,))
        d.line([fpt(face, 0.9, 0.1), fpt(face, 0.1, 0.9)], fill=sh(b, 0.4) + (255,))
    d.polygon(fquad(R, 0.35, 0.65, 0.4, 0.65), fill=AMB + (180,))
    return im, 32, 32 + h

# ---- characters (bottom-centre anchor) -------------------------------------
def person(coat, trim, hair, skin=(214, 170, 140), suit=False, visor=None, seed=6):
    W, H = 32, 48
    im = img(W, H)
    d = ImageDraw.Draw(im)
    cx, feet = 16, 46
    d.ellipse([cx - 9, feet - 3, cx + 9, feet + 2], fill=(0, 0, 0, 120))
    # legs
    d.polygon([(cx - 6, 30), (cx - 1, 30), (cx - 2, 45), (cx - 7, 45)], fill=sh(coat, 0.45) + (255,))
    d.polygon([(cx + 1, 30), (cx + 6, 30), (cx + 7, 45), (cx + 2, 45)], fill=sh(coat, 0.55) + (255,))
    # coat / torso
    body = [(cx - 8, 15), (cx + 8, 15), (cx + 10, 32), (cx - 10, 32)]
    d.polygon(body, fill=coat + (255,))
    d.polygon([(cx - 8, 15), (cx, 15), (cx, 32), (cx - 10, 32)], fill=sh(coat, 0.72) + (255,))
    d.line([(cx + 8, 15), (cx + 10, 32)], fill=sh(coat, 1.6) + (255,))
    if suit:
        d.polygon([(cx - 4, 15), (cx + 4, 15), (cx, 26)], fill=WHT + (255,))
        d.line([(cx, 16), (cx, 26)], fill=trim + (255,), width=1)
    else:
        d.line([(cx, 18), (cx, 32)], fill=trim + (255,), width=1)
    d.polygon([(cx - 6, 13), (cx + 6, 13), (cx + 4, 17), (cx - 4, 17)], fill=sh(coat, 1.2) + (255,))
    # shoulders
    d.ellipse([cx - 11, 15, cx - 5, 26], fill=sh(coat, 0.8) + (255,))
    d.ellipse([cx + 5, 15, cx + 11, 26], fill=sh(coat, 1.05) + (255,))
    # head
    d.ellipse([cx - 5, 4, cx + 5, 14], fill=skin + (255,))
    d.pieslice([cx - 6, 2, cx + 6, 13], 180, 360, fill=hair + (255,))
    d.line([(cx + 4, 6), (cx + 4, 12)], fill=lerp(skin, WHT, 0.4) + (255,))
    if visor:
        d.line([(cx - 4, 9), (cx + 4, 9)], fill=visor + (255,), width=1)
    if suit:
        d.line([(cx - 3, 9), (cx - 1, 9)], fill=(10, 10, 14, 255))
        d.line([(cx + 1, 9), (cx + 3, 9)], fill=(10, 10, 14, 255))
    return im, cx, feet

# ---- portraits (96x96) -----------------------------------------------------
def portrait(coat, accent, hair, skin=(214, 170, 140), suit=False, visor=None):
    W = 96
    im = Image.new("RGBA", (W, W), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    for y in range(W):
        d.line([(0, y), (W, y)], fill=lerp((18, 22, 40), sh(accent, 0.5), y / W) + (255,))
    d.rectangle([0, 0, W - 1, W - 1], outline=accent + (255,), width=3)
    # shoulders
    d.polygon([(14, W), (W - 14, W), (W - 20, 66), (20, 66)], fill=coat + (255,))
    d.polygon([(14, W), (48, W), (48, 66), (20, 66)], fill=sh(coat, 0.75) + (255,))
    if suit:
        d.polygon([(40, 66), (56, 66), (48, 86)], fill=WHT + (255,))
        d.line([(48, 68), (48, 86)], fill=accent + (255,), width=2)
    # head
    d.ellipse([30, 20, 66, 64], fill=skin + (255,))
    d.pieslice([28, 14, 68, 58], 180, 360, fill=hair + (255,))
    d.line([(62, 30), (64, 54)], fill=lerp(skin, WHT, 0.4) + (255,))
    if visor:
        d.rectangle([34, 38, 62, 44], fill=visor + (255,))
    elif suit:
        d.rectangle([36, 38, 44, 43], fill=(14, 16, 24, 255))
        d.rectangle([52, 38, 60, 43], fill=(14, 16, 24, 255))
    return im, 0, 0

# ---- registry --------------------------------------------------------------
ASSETS = []   # (name, img, w, h)

def reg(name, triple):
    im = triple[0]
    ASSETS.append((name, im, im.size[0], im.size[1]))

reg("vr_tile_asphalt",  floor((30, 32, 44), None, 11))
reg("vr_tile_sidewalk", floor((54, 56, 66), "sidewalk", 12))
reg("vr_tile_puddle",   floor((24, 28, 40), "puddle", 13))
reg("vr_tile_jackpoint", floor((26, 30, 46), "jackpoint", 14))
reg("vr_building_cyan", building((34, 38, 58), CYAN, 64, windows=(3, 4), seed=21))
reg("vr_building_mag",  building((42, 32, 54), MAG, 72, windows=(3, 5), seed=22))
reg("vr_building_door", building((38, 42, 60), CYAN, 64, door=True, seed=23))
reg("vr_sign",  sign(31))
reg("vr_lamp",  lamp(32))
reg("vr_crate", crate(33))
reg("vr_sprite_runner",  person((36, 60, 96), CYAN, (24, 26, 36), visor=CYAN, seed=41))
reg("vr_sprite_johnson", person((22, 24, 34), AMB, (150, 150, 160), suit=True, seed=42))
reg("vr_portrait_runner",  portrait((36, 60, 96), CYAN, (24, 26, 36), visor=CYAN))
reg("vr_portrait_johnson", portrait((22, 24, 34), AMB, (150, 150, 160), suit=True))

# ---- emit ------------------------------------------------------------------
def to_rgb565_colorkey(im):
    """Opaque -> RGB565 (never 0x0000); transparent -> 0x0000."""
    a = np.array(im)
    r = (a[:, :, 0].astype(np.uint16) >> 3) << 11
    g = (a[:, :, 1].astype(np.uint16) >> 2) << 5
    b = (a[:, :, 2].astype(np.uint16) >> 3)
    v = (r | g | b)
    opaque = a[:, :, 3] >= 128
    v = np.where((v == 0) & opaque, 1, v)          # bump pure black so it isn't keyed
    v = np.where(opaque, v, 0)                      # force transparent to 0
    return v.astype('<u2').flatten()

def emit():
    hdr = ["#pragma once", "#include <stdint.h>", ""]
    for name, im, w, h in ASSETS:
        hdr.append(f"extern const uint16_t {name}[{w}*{h}];")
        hdr.append(f"#define {name.upper()}_W {w}")
        hdr.append(f"#define {name.upper()}_H {h}")
    with open(os.path.join(OUT, "vr_assets.h"), "w") as f:
        f.write("\n".join(hdr) + "\n")

    lines = ['#include "vr_assets.h"', ""]
    for name, im, w, h in ASSETS:
        arr = to_rgb565_colorkey(im)
        lines.append(f"const uint16_t {name}[{w}*{h}] = {{")
        for i in range(0, len(arr), 16):
            lines.append("    " + ", ".join(f"0x{v:04X}" for v in arr[i:i + 16]) + ",")
        lines.append("};")
        lines.append("")
    with open(os.path.join(OUT, "vr_assets.c"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"generated {len(ASSETS)} assets -> main/assets/vr_assets.c/.h")


if __name__ == "__main__":
    emit()
    if os.environ.get("VR_PREVIEW"):
        import render_preview  # noqa
