#!/usr/bin/env python3
"""
VoidRunner — full-resolution isometric pixel-art asset generator.

Authors a cyberpunk isometric tileset offline with Pillow at the device's native
on-screen resolution (floor diamonds are 128x64) and emits VoidRunner's asset
format: flat RGB565 C arrays with colour-key transparency (0x0000 == clear).
game_world.c blits these 1:1 (no upscale), so the detail you see here is the
detail on the Tab5.

Sprites anchor by convention:
  floor tiles  -> diamond centre  (ax=W/2, ay=H/2)
  objects      -> bottom centre   (ax=W/2, ay=H)   so they rise above the floor

Runs locally (needs Pillow + numpy); the generated vr_assets.c/.h are committed,
so CI just compiles them. Regenerate:  python3 tools/gen_assets.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "main", "assets")
os.makedirs(OUT, exist_ok=True)

TW, TH = 128, 64          # floor tile size (full res)
HW, HH = 64, 32

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

DIAMOND = [(64, 0), (128, 32), (64, 64), (0, 32)]

# ---- floor tiles -----------------------------------------------------------
def floor(base, variant=None, seed=1):
    im = img(TW, TH)
    grad = img(TW, TH)
    gd = ImageDraw.Draw(grad)
    for y in range(TH):
        t = y / TH
        gd.line([(0, y), (TW, y)], fill=sh(base, 1.10 - 0.32 * t) + (255,))
    mask = Image.new("L", (TW, TH), 0)
    ImageDraw.Draw(mask).polygon(DIAMOND, fill=255)
    im = Image.composite(grad, im, mask)
    im = noise(im, 6, seed)
    d = ImageDraw.Draw(im)
    hi, lo = sh(base, 1.7), sh(base, 0.5)
    d.line([(0, 32), (64, 0)], fill=hi + (255,))
    d.line([(64, 0), (128, 32)], fill=hi + (255,))
    d.line([(0, 32), (64, 64)], fill=lo + (255,))
    d.line([(64, 64), (128, 32)], fill=lo + (255,))
    if variant == "sidewalk":
        for k in range(-2, 3):
            o = k * 20
            d.line([(64 + o, 2 + abs(k)), (96 + o, 18)], fill=sh(base, 0.55) + (150,))
        d.line([(0, 32), (64, 0)], fill=sh(CYAN, 0.8) + (120,))
        d.line([(64, 0), (128, 32)], fill=sh(CYAN, 0.8) + (120,))
    elif variant == "puddle":
        pud = img(TW, TH)
        pd = ImageDraw.Draw(pud)
        small = [(64, 14), (108, 32), (64, 50), (20, 32)]
        for yy in range(14, 51):
            t = (yy - 14) / 36
            pd.line([(0, yy), (TW, yy)], fill=lerp((14, 20, 32), CYAN, 0.10 + 0.5 * t) + (255,))
        pm = Image.new("L", (TW, TH), 0)
        ImageDraw.Draw(pm).polygon(small, fill=255)
        im = Image.composite(pud, im, pm)
        d = ImageDraw.Draw(im)
        d.line([(30, 40), (58, 44)], fill=MAG + (160,), width=2)
        d.line([(70, 28), (98, 32)], fill=CYAN + (180,), width=2)
    elif variant == "jackpoint":
        def pl(a, b, t):
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        ctr = (64, 32)
        for k in range(1, 7):
            t = k / 7
            col = sh(CYAN, 1.05 - t * 0.55) if k % 2 else sh(MAG, 1.0 - t * 0.5)
            dp = [pl((64, 0), ctr, t), pl((128, 32), ctr, t),
                  pl((64, 64), ctr, t), pl((0, 32), ctr, t)]
            d.polygon(dp, outline=col + (255,))
        d.line([(0, 32), (64, 0)], fill=CYAN + (255,))
        d.line([(64, 0), (128, 32)], fill=CYAN + (255,))
        d.line([(0, 32), (64, 64)], fill=MAG + (255,))
        d.line([(64, 64), (128, 32)], fill=MAG + (255,))
        d.ellipse([60, 28, 68, 36], fill=WHT + (255,))
    return im

# ---- building / wall cube --------------------------------------------------
def building(base, win_color, height=128, door=False, windows=(3, 5), seed=2):
    W, H = TW, TH + height
    im = img(W, H)
    d = ImageDraw.Draw(im)
    top = [(64, 0), (128, 32), (64, 64), (0, 32)]
    left = [(0, 32), (64, 64), (64, 64 + height), (0, 32 + height)]
    right = [(64, 64), (128, 32), (128, 32 + height), (64, 64 + height)]
    d.polygon(left, fill=sh(base, 0.58) + (255,))
    d.polygon(right, fill=sh(base, 0.9) + (255,))
    d.polygon(top, fill=sh(base, 1.25) + (255,))
    im = noise(im, 5, seed)
    d = ImageDraw.Draw(im)
    d.line([(0, 32), (64, 0)], fill=sh(base, 1.75) + (255,))
    d.line([(64, 0), (128, 32)], fill=sh(base, 1.75) + (255,))
    d.line([(64, 64), (64, 64 + height)], fill=sh(base, 0.38) + (255,))
    d.line([(0, 32), (0, 32 + height)], fill=sh(base, 0.42) + (255,))
    d.line([(128, 32), (128, 32 + height)], fill=sh(base, 1.1) + (255,))
    L = ((0, 32), (64, 64), (0, 32 + height))
    R = ((64, 64), (128, 32), (64, 64 + height))
    cols, rows = windows
    for face, bias in ((L, 0.0), (R, 0.12)):
        for r in range(rows):
            for c in range(cols):
                lit = ((c * 7 + r * 5 + seed) % 10) / 10.0 > (0.42 - bias)
                q = fquad(face, (c + 0.22) / cols, (c + 0.78) / cols,
                          (r + 0.16) / rows, (r + 0.74) / rows)
                if lit:
                    d.polygon(q, fill=sh(win_color, 0.8) + (255,))
                    cq = fquad(face, (c + 0.33) / cols, (c + 0.67) / cols,
                               (r + 0.26) / rows, (r + 0.52) / rows)
                    d.polygon(cq, fill=sh(win_color, 1.35) + (255,))
                else:
                    d.polygon(q, fill=sh(base, 0.3) + (255,))
    if door:
        d.polygon(fquad(R, 0.28, 0.72, 0.30, 0.97), fill=sh(base, 0.18) + (255,))
        d.polygon(fquad(R, 0.35, 0.65, 0.36, 0.93), fill=sh(CYAN, 0.5) + (255,))
        d.line([fpt(R, 0.5, 0.36), fpt(R, 0.5, 0.93)], fill=CYAN + (255,), width=2)
        lk = fpt(R, 0.61, 0.46)
        d.ellipse([lk[0] - 3, lk[1] - 3, lk[0] + 3, lk[1] + 3], fill=GRN + (255,))
    return im

# ---- props -----------------------------------------------------------------
def sign(seed=3):
    h = 92
    W, H = TW, TH + h
    im = img(W, H)
    d = ImageDraw.Draw(im)
    d.line([(64, TH + h), (64, 66)], fill=(44, 48, 62, 255), width=4)
    d.rectangle([18, 8, 110, 64], fill=(10, 12, 22, 255), outline=CYAN + (255,), width=2)
    cols = [MAG, CYAN, GRN, AMB]
    x = 30
    for k in range(4):
        c = cols[k]
        d.rectangle([x, 20, x + 6, 54], fill=c + (255,))
        d.rectangle([x + 10, 20, x + 16, 34], fill=c + (255,))
        x += 22
    return im

def lamp(seed=4):
    h = 150
    W, H = TW, TH + h
    im = img(W, H)
    d = ImageDraw.Draw(im)
    d.line([(64, TH + h), (64, 44)], fill=(42, 46, 60, 255), width=5)
    d.line([(63, TH + h), (63, 44)], fill=(74, 80, 98, 255), width=1)
    d.rectangle([42, 26, 86, 48], fill=sh(MAG, 1.05) + (255,), outline=WHT + (255,))
    d.rectangle([48, 30, 80, 44], fill=sh(MAG, 1.3) + (255,))
    return im

def crate(seed=5):
    h = 48
    W, H = TW, TH + h
    im = img(W, H)
    d = ImageDraw.Draw(im)
    b = (82, 66, 44)
    top = [(64, 0), (128, 32), (64, 64), (0, 32)]
    left = [(0, 32), (64, 64), (64, 64 + h), (0, 32 + h)]
    right = [(64, 64), (128, 32), (128, 32 + h), (64, 64 + h)]
    d.polygon(left, fill=sh(b, 0.6) + (255,))
    d.polygon(right, fill=sh(b, 0.95) + (255,))
    d.polygon(top, fill=sh(b, 1.3) + (255,))
    L = ((0, 32), (64, 64), (0, 32 + h))
    R = ((64, 64), (128, 32), (64, 64 + h))
    for face in (L, R):
        d.line([fpt(face, 0.1, 0.1), fpt(face, 0.9, 0.9)], fill=sh(b, 0.4) + (255,), width=2)
        d.line([fpt(face, 0.9, 0.1), fpt(face, 0.1, 0.9)], fill=sh(b, 0.4) + (255,), width=2)
    d.polygon(fquad(R, 0.34, 0.66, 0.4, 0.62), fill=AMB + (200,))
    return im

# ---- characters (bottom-centre anchor) -------------------------------------
def person(coat, trim, hair, skin=(214, 170, 140), suit=False, visor=None, seed=6):
    W, H = 60, 104
    im = img(W, H)
    d = ImageDraw.Draw(im)
    cx, feet = 30, 100
    d.ellipse([cx - 16, feet - 5, cx + 16, feet + 4], fill=(0, 0, 0, 120))
    # legs
    d.polygon([(cx - 11, 66), (cx - 2, 66), (cx - 3, 98), (cx - 12, 98)], fill=sh(coat, 0.45) + (255,))
    d.polygon([(cx + 2, 66), (cx + 11, 66), (cx + 12, 98), (cx + 3, 98)], fill=sh(coat, 0.55) + (255,))
    d.line([(cx + 11, 66), (cx + 12, 98)], fill=sh(coat, 0.9) + (255,))
    # coat / torso
    body = [(cx - 15, 32), (cx + 15, 32), (cx + 19, 70), (cx - 19, 70)]
    d.polygon(body, fill=coat + (255,))
    d.polygon([(cx - 15, 32), (cx, 32), (cx, 70), (cx - 19, 70)], fill=sh(coat, 0.72) + (255,))
    d.line([(cx + 15, 32), (cx + 19, 70)], fill=sh(coat, 1.6) + (255,), width=2)
    if suit:
        d.polygon([(cx - 7, 32), (cx + 7, 32), (cx, 54)], fill=WHT + (255,))
        d.line([(cx, 34), (cx, 54)], fill=trim + (255,), width=2)
    else:
        d.line([(cx, 38), (cx, 70)], fill=trim + (255,), width=2)
    d.polygon([(cx - 11, 29), (cx + 11, 29), (cx + 8, 36), (cx - 8, 36)], fill=sh(coat, 1.2) + (255,))
    d.ellipse([cx - 20, 32, cx - 10, 56], fill=sh(coat, 0.8) + (255,))
    d.ellipse([cx + 10, 32, cx + 20, 56], fill=sh(coat, 1.05) + (255,))
    # head
    d.ellipse([cx - 9, 8, cx + 9, 28], fill=skin + (255,))
    d.pieslice([cx - 10, 4, cx + 10, 26], 180, 360, fill=hair + (255,))
    d.line([(cx + 7, 12), (cx + 8, 24)], fill=lerp(skin, WHT, 0.4) + (255,))
    if visor:
        d.line([(cx - 7, 17), (cx + 7, 17)], fill=visor + (255,), width=2)
    if suit:
        d.ellipse([cx - 6, 15, cx - 2, 19], fill=(10, 10, 14, 255))
        d.ellipse([cx + 2, 15, cx + 6, 19], fill=(10, 10, 14, 255))
    return im

# ---- portraits (96x96) -----------------------------------------------------
def portrait(coat, accent, hair, skin=(214, 170, 140), suit=False, visor=None):
    W = 96
    im = Image.new("RGBA", (W, W), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    for y in range(W):
        d.line([(0, y), (W, y)], fill=lerp((18, 22, 40), sh(accent, 0.5), y / W) + (255,))
    d.rectangle([0, 0, W - 1, W - 1], outline=accent + (255,), width=3)
    d.polygon([(14, W), (W - 14, W), (W - 20, 66), (20, 66)], fill=coat + (255,))
    d.polygon([(14, W), (48, W), (48, 66), (20, 66)], fill=sh(coat, 0.75) + (255,))
    if suit:
        d.polygon([(40, 66), (56, 66), (48, 86)], fill=WHT + (255,))
        d.line([(48, 68), (48, 86)], fill=accent + (255,), width=2)
    d.ellipse([30, 20, 66, 64], fill=skin + (255,))
    d.pieslice([28, 14, 68, 58], 180, 360, fill=hair + (255,))
    d.line([(62, 30), (64, 54)], fill=lerp(skin, WHT, 0.4) + (255,))
    if visor:
        d.rectangle([34, 38, 62, 44], fill=visor + (255,))
    elif suit:
        d.rectangle([36, 38, 44, 43], fill=(14, 16, 24, 255))
        d.rectangle([52, 38, 60, 43], fill=(14, 16, 24, 255))
    return im

# ---- registry --------------------------------------------------------------
ASSETS = []   # (name, img, w, h)

def reg(name, im):
    ASSETS.append((name, im, im.size[0], im.size[1]))

reg("vr_tile_asphalt",  floor((30, 32, 44), None, 11))
reg("vr_tile_sidewalk", floor((54, 56, 66), "sidewalk", 12))
reg("vr_tile_puddle",   floor((24, 28, 40), "puddle", 13))
reg("vr_tile_jackpoint", floor((26, 30, 46), "jackpoint", 14))
reg("vr_building_cyan", building((34, 38, 58), CYAN, 128, windows=(3, 5), seed=21))
reg("vr_building_mag",  building((42, 32, 54), MAG, 144, windows=(3, 6), seed=22))
reg("vr_building_door", building((38, 42, 60), CYAN, 128, door=True, seed=23))
reg("vr_sign",  sign(31))
reg("vr_lamp",  lamp(32))
reg("vr_crate", crate(33))
reg("vr_sprite_runner",  person((36, 60, 96), CYAN, (24, 26, 36), visor=CYAN, seed=41))
reg("vr_sprite_johnson", person((22, 24, 34), AMB, (150, 150, 160), suit=True, seed=42))
reg("vr_portrait_runner",  portrait((36, 60, 96), CYAN, (24, 26, 36), visor=CYAN))
reg("vr_portrait_johnson", portrait((22, 24, 34), AMB, (150, 150, 160), suit=True))

# ---- emit ------------------------------------------------------------------
def to_rgb565_colorkey(im):
    a = np.array(im)
    r = (a[:, :, 0].astype(np.uint16) >> 3) << 11
    g = (a[:, :, 1].astype(np.uint16) >> 2) << 5
    b = (a[:, :, 2].astype(np.uint16) >> 3)
    v = (r | g | b)
    opaque = a[:, :, 3] >= 128
    v = np.where((v == 0) & opaque, 1, v)
    v = np.where(opaque, v, 0)
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
    tot = sum(w * h * 2 for _, _, w, h in ASSETS)
    print(f"generated {len(ASSETS)} assets ({tot//1024} KiB in flash) -> main/assets/vr_assets.c/.h")


if __name__ == "__main__":
    emit()
