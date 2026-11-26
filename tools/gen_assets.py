#!/usr/bin/env python3
"""
VoidRunner — interior isometric tileset generator (Shadowrun Dragonfall vibe).

Authors a warm, detailed interior scene offline with Pillow at the device's
native on-screen resolution (floor diamonds 128x64) and emits VoidRunner's asset
format: flat RGB565 C arrays with colour-key transparency (0x0000 == clear).
game_world.c blits these 1:1.

Setting: a marble corp gallery/lobby being infiltrated — marble floor + rug,
columns, framed art on warm stone walls, arched windows throwing cool light,
glass display cases, leather sofas, a statue, and runner/Johnson/guard sprites.

Anchors:  floor -> diamond centre (W/2, H/2);  everything else -> bottom centre.

Runs locally (Pillow + numpy); generated vr_assets.c/.h are committed, so CI just
compiles them. Regenerate:  python3 tools/gen_assets.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "main", "assets")
os.makedirs(OUT, exist_ok=True)

TW, TH = 128, 64
HW, HH = 64, 32

# ---- warm interior palette -------------------------------------------------
MARB_HI = (210, 202, 182)
MARB    = (170, 162, 142)
MARB_LO = (120, 114, 98)
GROUT   = (86, 80, 66)
WOOD    = (74, 52, 34)
WOOD_HI = (120, 86, 54)
BRASS   = (198, 158, 86)
BRASS_HI= (238, 208, 140)
RUG     = (104, 32, 42)
RUG_HI  = (150, 54, 60)
RUG_TR  = (200, 162, 92)
LEATH   = (46, 38, 48)
LEATH_HI= (84, 70, 90)
STONE   = (122, 112, 96)
WIN     = (120, 165, 205)
WIN_HI  = (188, 220, 240)
GLASS   = (150, 214, 232)
GOLD    = (206, 172, 98)
CYAN    = (0, 240, 255)
AMB     = (255, 185, 40)
WHT     = (232, 236, 240)

def sh(c, f):
    return tuple(max(0, min(255, int(c[i]*f))) for i in range(3))
def lerp(a, b, t):
    return tuple(int(round(a[i]+(b[i]-a[i])*t)) for i in range(3))
def img(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))
def noise(im, amt, seed):
    rng = np.random.default_rng(seed); a = np.array(im).astype(np.int16)
    m = a[:, :, 3] > 0; n = rng.integers(-amt, amt+1, size=a.shape[:2])
    for c in range(3): a[:, :, c] = np.where(m, np.clip(a[:, :, c]+n, 0, 255), a[:, :, c])
    return Image.fromarray(a.astype(np.uint8), "RGBA")
def fpt(c, u, v):
    TL, TR, BL = c
    return (TL[0]+u*(TR[0]-TL[0])+v*(BL[0]-TL[0]), TL[1]+u*(TR[1]-TL[1])+v*(BL[1]-TL[1]))
def fquad(c, u0, u1, v0, v1):
    return [fpt(c, u0, v0), fpt(c, u1, v0), fpt(c, u1, v1), fpt(c, u0, v1)]

DIAMOND = [(64, 0), (128, 32), (64, 64), (0, 32)]
def pl(a, b, t): return (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t)

# ---- floor tiles -----------------------------------------------------------
def marble(base, veins=True, variant=None, seed=1):
    im = img(TW, TH); grad = img(TW, TH); gd = ImageDraw.Draw(grad)
    for y in range(TH):
        t = y/TH; gd.line([(0, y), (TW, y)], fill=sh(base, 1.08-0.2*t)+(255,))
    mask = Image.new("L", (TW, TH), 0); ImageDraw.Draw(mask).polygon(DIAMOND, fill=255)
    im = Image.composite(grad, im, mask); im = noise(im, 4, seed)
    d = ImageDraw.Draw(im)
    if veins:
        rng = np.random.default_rng(seed+9)
        for _ in range(3):
            x0 = rng.integers(12, 60); y0 = rng.integers(10, 54)
            pts = [(x0, y0)]
            for k in range(4):
                x0 += rng.integers(6, 16); y0 += rng.integers(-6, 7); pts.append((x0, y0))
            d.line(pts, fill=sh(base, 0.78)+(90,), width=1)
    # grout edges (tile seams)
    d.line([(0, 32), (64, 0)], fill=sh(base, 1.4)+(255,))
    d.line([(64, 0), (128, 32)], fill=sh(base, 1.4)+(255,))
    d.line([(0, 32), (64, 64)], fill=sh(GROUT, 1.0)+(255,))
    d.line([(64, 64), (128, 32)], fill=sh(GROUT, 1.0)+(255,))
    if variant == "rug":
        r = img(TW, TH); rd = ImageDraw.Draw(r)
        inner = [(64, 6), (118, 32), (64, 58), (10, 32)]
        rd.polygon(inner, fill=RUG+(255,))
        rd.polygon([(64, 12), (110, 32), (64, 52), (18, 32)], outline=RUG_TR+(255,), width=2)
        rd.polygon([(64, 20), (98, 32), (64, 44), (30, 32)], outline=sh(RUG_HI, 1.0)+(255,))
        rd.line([(64, 24), (64, 40)], fill=RUG_TR+(255,)); rd.line([(48, 32), (80, 32)], fill=RUG_TR+(255,))
        rm = Image.new("L", (TW, TH), 0); ImageDraw.Draw(rm).polygon(inner, fill=255)
        im = Image.composite(r, im, rm)
    elif variant == "medallion":
        for k in range(1, 4):
            t = k/4; ctr = (64, 32)
            d.polygon([pl((64, 6), ctr, t), pl((118, 32), ctr, t), pl((64, 58), ctr, t), pl((10, 32), ctr, t)],
                      outline=sh(BRASS, 1.0+0.2*k)+(255,))
        d.ellipse([56, 26, 72, 38], outline=BRASS_HI+(255,))
        d.ellipse([60, 29, 68, 35], fill=sh(CYAN, 0.8)+(255,))
    return im

# ---- wall cube with interior decor ----------------------------------------
def wall(kind="plain", height=140, seed=2):
    W, H = TW, TH+height; im = img(W, H); d = ImageDraw.Draw(im)
    base = STONE
    top = [(64, 0), (128, 32), (64, 64), (0, 32)]
    left = [(0, 32), (64, 64), (64, 64+height), (0, 32+height)]
    right = [(64, 64), (128, 32), (128, 32+height), (64, 64+height)]
    d.polygon(left, fill=sh(base, 0.62)+(255,))
    d.polygon(right, fill=sh(base, 0.92)+(255,))
    d.polygon(top, fill=sh(base, 1.2)+(255,))
    im = noise(im, 4, seed); d = ImageDraw.Draw(im)
    d.line([(0, 32), (64, 0)], fill=sh(base, 1.5)+(255,))
    d.line([(64, 0), (128, 32)], fill=sh(base, 1.5)+(255,))
    L = ((0, 32), (64, 64), (0, 32+height)); R = ((64, 64), (128, 32), (64, 64+height))
    # wainscoting (lower wood band) on both faces
    for face in (L, R):
        d.polygon(fquad(face, 0.0, 1.0, 0.72, 1.0), fill=sh(WOOD, 1.0)+(255,))
        d.line([fpt(face, 0.0, 0.72), fpt(face, 1.0, 0.72)], fill=WOOD_HI+(255,))
    if kind == "window":
        for face, f in ((L, 0.62), (R, 0.9)):
            arch = fquad(face, 0.2, 0.8, 0.12, 0.66)
            d.polygon(arch, fill=sh(WIN, f)+(255,))
            # mullions
            d.line([fpt(face, 0.5, 0.12), fpt(face, 0.5, 0.66)], fill=sh(STONE, 1.3)+(255,), width=2)
            d.line([fpt(face, 0.2, 0.39), fpt(face, 0.8, 0.39)], fill=sh(STONE, 1.3)+(255,), width=2)
            # arched top highlight
            d.line([fpt(face, 0.2, 0.12), fpt(face, 0.8, 0.12)], fill=WIN_HI+(255,), width=2)
    elif kind == "door":
        d.polygon(fquad(R, 0.26, 0.74, 0.22, 0.99), fill=sh(WOOD, 0.7)+(255,))
        d.polygon(fquad(R, 0.31, 0.69, 0.27, 0.95), fill=(18, 14, 16, 255))
        d.line([fpt(R, 0.5, 0.27), fpt(R, 0.5, 0.95)], fill=sh(WOOD, 1.2)+(255,), width=2)
        lk = fpt(R, 0.6, 0.6); d.ellipse([lk[0]-2, lk[1]-2, lk[0]+2, lk[1]+2], fill=BRASS_HI+(255,))
    else:  # plain: framed painting on each face
        for face in (L, R):
            fr = fquad(face, 0.26, 0.74, 0.2, 0.6)
            d.polygon(fr, fill=BRASS+(255,))
            inr = fquad(face, 0.31, 0.69, 0.25, 0.55)
            d.polygon(inr, fill=sh((40, 34, 44), 1.0)+(255,))
            d.line([fpt(face, 0.4, 0.3), fpt(face, 0.62, 0.48)], fill=sh(AMB, 0.8)+(200,))
            d.line([fpt(face, 0.36, 0.46), fpt(face, 0.58, 0.5)], fill=sh(WIN, 1.0)+(180,))
    return im

# ---- props (bottom-centre anchor) -----------------------------------------
def column(seed=3):
    H = 176; W = 128; im = img(W, H); d = ImageDraw.Draw(im)
    cx = 64; base_y = H-6
    d.ellipse([cx-26, base_y-10, cx+26, base_y+4], fill=(0, 0, 0, 110))
    # plinth
    d.polygon([(cx-22, base_y-16), (cx, base_y-6), (cx+22, base_y-16), (cx, base_y-26)], fill=sh(MARB, 1.1)+(255,))
    d.rectangle([cx-20, base_y-44, cx+20, base_y-16], fill=sh(MARB, 0.9)+(255,))
    d.polygon([(cx-20, base_y-44), (cx-20, base_y-16), (cx, base_y-6), (cx, base_y-34)], fill=sh(MARB, 0.72)+(255,))
    # shaft with flutes
    for i in range(5):
        x = cx-16+i*8; f = 0.7+0.1*i
        d.rectangle([x, 40, x+7, base_y-44], fill=sh(MARB, f)+(255,))
    d.rectangle([cx-17, 40, cx-15, base_y-44], fill=sh(MARB, 1.3)+(255,))
    # capital
    d.rectangle([cx-22, 28, cx+22, 44], fill=sh(MARB, 1.15)+(255,))
    d.rectangle([cx-24, 22, cx+24, 30], fill=sh(MARB_HI, 1.0)+(255,))
    return im

def statue(seed=4):
    H = 180; W = 128; im = img(W, H); d = ImageDraw.Draw(im); cx = 64; by = H-6
    d.ellipse([cx-30, by-10, cx+30, by+4], fill=(0, 0, 0, 120))
    # plinth block (iso box)
    ph = 46
    top = [(cx, by-ph-20), (cx+34, by-ph), (cx, by-ph+20), (cx-34, by-ph)]
    d.polygon([(cx-34, by-ph), (cx, by-ph+20), (cx, by-6), (cx-34, by-26)], fill=sh(MARB, 0.68)+(255,))
    d.polygon([(cx+34, by-ph), (cx, by-ph+20), (cx, by-6), (cx+34, by-26)], fill=sh(MARB, 0.92)+(255,))
    d.polygon(top, fill=sh(MARB, 1.15)+(255,))
    # golden abstract figure
    fy = by-ph-6
    d.ellipse([cx-8, fy-54, cx+8, fy-38], fill=sh(GOLD, 1.1)+(255,))          # head
    d.polygon([(cx-10, fy-40), (cx+10, fy-40), (cx+14, fy), (cx-14, fy)], fill=GOLD+(255,))  # body
    d.polygon([(cx-10, fy-40), (cx, fy-40), (cx, fy), (cx-14, fy)], fill=sh(GOLD, 0.72)+(255,))
    d.line([(cx+10, fy-38), (cx+14, fy)], fill=BRASS_HI+(255,), width=2)       # rim light
    d.polygon([(cx+8, fy-36), (cx+22, fy-20), (cx+18, fy-14), (cx+6, fy-26)], fill=sh(GOLD, 0.9)+(255,))  # arm
    return im

def display_case(seed=5):
    H = 150; W = 128; im = img(W, H); d = ImageDraw.Draw(im); cx = 64; by = H-6
    d.ellipse([cx-34, by-10, cx+34, by+4], fill=(0, 0, 0, 120))
    # pedestal
    ph = 40
    d.polygon([(cx-34, by-ph), (cx, by-ph+18), (cx, by-4), (cx-34, by-22)], fill=sh(MARB, 0.66)+(255,))
    d.polygon([(cx+34, by-ph), (cx, by-ph+18), (cx, by-4), (cx+34, by-22)], fill=sh(MARB, 0.9)+(255,))
    d.polygon([(cx, by-ph-18), (cx+34, by-ph), (cx, by-ph+18), (cx-34, by-ph)], fill=sh(MARB, 1.1)+(255,))
    # glass box
    gh = 54; gy = by-ph-18
    tp = [(cx, gy-gh-18), (cx+30, gy-gh), (cx, gy-gh+18), (cx-30, gy-gh)]
    # glowing artifact inside
    d.ellipse([cx-8, gy-34, cx+8, gy-18], fill=sh(CYAN, 1.0)+(255,))
    g = img(W, H); ImageDraw.Draw(g).ellipse([cx-16, gy-42, cx+16, gy-10], fill=CYAN+(70,))
    im = Image.alpha_composite(im, g); d = ImageDraw.Draw(im)
    # translucent glass faces (light tint, drawn as thin edges + faint fill)
    d.polygon([(cx-30, gy-gh), (cx, gy-gh+18), (cx, gy), (cx-30, gy-18)], fill=sh(GLASS, 0.5)+(90,))
    d.polygon([(cx+30, gy-gh), (cx, gy-gh+18), (cx, gy), (cx+30, gy-18)], fill=sh(GLASS, 0.7)+(90,))
    d.polygon(tp, outline=WIN_HI+(255,))
    for e in [((cx-30, gy-gh), (cx-30, gy-18)), ((cx+30, gy-gh), (cx+30, gy-18)),
              ((cx, gy-gh+18), (cx, gy)), ((cx-30, gy-18), (cx, gy)), ((cx+30, gy-18), (cx, gy))]:
        d.line([e[0], e[1]], fill=sh(GLASS, 1.0)+(220,))
    return im

def sofa(seed=6):
    H = 96; W = 128; im = img(W, H); d = ImageDraw.Draw(im); cx = 64; by = H-6
    d.ellipse([cx-44, by-8, cx+44, by+4], fill=(0, 0, 0, 110))
    # seat base (iso slab)
    d.polygon([(cx, by-40), (cx+46, by-18), (cx, by+2), (cx-46, by-18)], fill=sh(LEATH, 1.15)+(255,))
    # back (raised along the far-left/right top edges)
    d.polygon([(cx-46, by-18), (cx, by-40), (cx, by-58), (cx-46, by-36)], fill=sh(LEATH, 0.8)+(255,))
    d.polygon([(cx, by-40), (cx+46, by-18), (cx+46, by-36), (cx, by-58)], fill=sh(LEATH, 1.0)+(255,))
    # cushions
    for u in (-1, 1):
        d.polygon([(cx+u*6, by-34), (cx+u*26, by-24), (cx+u*20, by-14), (cx, by-24)], fill=sh(LEATH_HI, 1.0)+(255,))
    d.line([(cx-46, by-36), (cx, by-58)], fill=LEATH_HI+(255,))
    d.line([(cx, by-58), (cx+46, by-36)], fill=sh(LEATH_HI, 1.2)+(255,))
    return im

def table(seed=7):
    H = 64; W = 128; im = img(W, H); d = ImageDraw.Draw(im); cx = 64; by = H-6
    d.ellipse([cx-40, by-8, cx+40, by+2], fill=(0, 0, 0, 100))
    tp = [(cx, by-30), (cx+40, by-14), (cx, by+2), (cx-40, by-14)]
    d.polygon([(cx-40, by-14), (cx, by+2), (cx, by+8), (cx-40, by-8)], fill=sh(WOOD, 0.7)+(255,))
    d.polygon([(cx+40, by-14), (cx, by+2), (cx, by+8), (cx+40, by-8)], fill=sh(WOOD, 0.9)+(255,))
    d.polygon(tp, fill=sh(WOOD_HI, 1.0)+(255,))
    d.polygon(tp, outline=sh(WOOD_HI, 1.3)+(255,))
    # a datapad + cup on top
    d.polygon([(cx-6, by-18), (cx+6, by-13), (cx+2, by-9), (cx-10, by-14)], fill=sh(CYAN, 0.7)+(255,))
    d.ellipse([cx+10, by-18, cx+18, by-12], fill=sh(BRASS, 1.1)+(255,))
    return im

def plant(seed=8):
    H = 120; W = 128; im = img(W, H); d = ImageDraw.Draw(im); cx = 64; by = H-6
    d.ellipse([cx-20, by-8, cx+20, by+2], fill=(0, 0, 0, 100))
    d.polygon([(cx-16, by-30), (cx, by-24), (cx+16, by-30), (cx+12, by-2), (cx-12, by-2)], fill=sh(BRASS, 0.8)+(255,))
    d.polygon([(cx-16, by-30), (cx, by-24), (cx, by-2), (cx-12, by-2)], fill=sh(BRASS, 0.6)+(255,))
    grn = (46, 86, 58)
    for a, dx, dy in [(0, 0, -64), (1, -16, -52), (-1, 16, -52), (1, -8, -44), (-1, 8, -44)]:
        d.polygon([(cx, by-30), (cx+dx-6, by+dy), (cx+dx+6, by+dy)], fill=sh(grn, 1.0+0.12*a)+(255,))
    d.ellipse([cx-18, by-66, cx+18, by-30], fill=grn+(255,))
    d.ellipse([cx-8, by-62, cx+14, by-40], fill=sh(grn, 1.3)+(255,))
    return im

# ---- characters ------------------------------------------------------------
def person(coat, trim, hair, skin=(214, 170, 140), suit=False, visor=None, gun=False, seed=6):
    W, H = 60, 104; im = img(W, H); d = ImageDraw.Draw(im); cx, feet = 30, 100
    d.ellipse([cx-16, feet-5, cx+16, feet+4], fill=(0, 0, 0, 120))
    d.polygon([(cx-11, 66), (cx-2, 66), (cx-3, 98), (cx-12, 98)], fill=sh(coat, 0.45)+(255,))
    d.polygon([(cx+2, 66), (cx+11, 66), (cx+12, 98), (cx+3, 98)], fill=sh(coat, 0.55)+(255,))
    body = [(cx-15, 32), (cx+15, 32), (cx+19, 70), (cx-19, 70)]
    d.polygon(body, fill=coat+(255,))
    d.polygon([(cx-15, 32), (cx, 32), (cx, 70), (cx-19, 70)], fill=sh(coat, 0.72)+(255,))
    d.line([(cx+15, 32), (cx+19, 70)], fill=sh(coat, 1.6)+(255,), width=2)
    if suit:
        d.polygon([(cx-7, 32), (cx+7, 32), (cx, 54)], fill=WHT+(255,)); d.line([(cx, 34), (cx, 54)], fill=trim+(255,), width=2)
    else:
        d.line([(cx, 38), (cx, 70)], fill=trim+(255,), width=2)
    d.polygon([(cx-11, 29), (cx+11, 29), (cx+8, 36), (cx-8, 36)], fill=sh(coat, 1.2)+(255,))
    d.ellipse([cx-20, 32, cx-10, 56], fill=sh(coat, 0.8)+(255,))
    d.ellipse([cx+10, 32, cx+20, 56], fill=sh(coat, 1.05)+(255,))
    if gun:
        d.rectangle([cx+16, 44, cx+34, 48], fill=(24, 24, 28, 255)); d.rectangle([cx+30, 44, cx+34, 54], fill=(24, 24, 28, 255))
    d.ellipse([cx-9, 8, cx+9, 28], fill=skin+(255,))
    d.pieslice([cx-10, 4, cx+10, 26], 180, 360, fill=hair+(255,))
    d.line([(cx+7, 12), (cx+8, 24)], fill=lerp(skin, WHT, 0.4)+(255,))
    if visor: d.line([(cx-7, 17), (cx+7, 17)], fill=visor+(255,), width=2)
    if suit:
        d.ellipse([cx-6, 15, cx-2, 19], fill=(10, 10, 14, 255)); d.ellipse([cx+2, 15, cx+6, 19], fill=(10, 10, 14, 255))
    return im

def portrait(coat, accent, hair, skin=(214, 170, 140), suit=False, visor=None):
    W = 96; im = Image.new("RGBA", (W, W), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    for y in range(W): d.line([(0, y), (W, y)], fill=lerp((28, 24, 22), sh(accent, 0.5), y/W)+(255,))
    d.rectangle([0, 0, W-1, W-1], outline=accent+(255,), width=3)
    d.polygon([(14, W), (W-14, W), (W-20, 66), (20, 66)], fill=coat+(255,))
    d.polygon([(14, W), (48, W), (48, 66), (20, 66)], fill=sh(coat, 0.75)+(255,))
    if suit:
        d.polygon([(40, 66), (56, 66), (48, 86)], fill=WHT+(255,)); d.line([(48, 68), (48, 86)], fill=accent+(255,), width=2)
    d.ellipse([30, 20, 66, 64], fill=skin+(255,))
    d.pieslice([28, 14, 68, 58], 180, 360, fill=hair+(255,))
    d.line([(62, 30), (64, 54)], fill=lerp(skin, WHT, 0.4)+(255,))
    if visor: d.rectangle([34, 38, 62, 44], fill=visor+(255,))
    elif suit:
        d.rectangle([36, 38, 44, 43], fill=(14, 16, 24, 255)); d.rectangle([52, 38, 60, 43], fill=(14, 16, 24, 255))
    return im

# ---- registry --------------------------------------------------------------
ASSETS = []
def reg(name, im): ASSETS.append((name, im, im.size[0], im.size[1]))

reg("vr_tile_marble",   marble(MARB, True, None, 11))
reg("vr_tile_marble2",  marble(sh(MARB, 1.1), True, None, 12))
reg("vr_tile_rug",      marble(MARB, False, "rug", 13))
reg("vr_tile_terminal", marble(MARB, False, "medallion", 14))
reg("vr_wall",          wall("plain", 140, 21))
reg("vr_wall_window",   wall("window", 140, 22))
reg("vr_wall_door",     wall("door", 140, 23))
reg("vr_column",        column(31))
reg("vr_statue",        statue(32))
reg("vr_case",          display_case(33))
reg("vr_sofa",          sofa(34))
reg("vr_table",         table(35))
reg("vr_plant",         plant(36))
reg("vr_sprite_runner",  person((36, 60, 96), CYAN, (24, 26, 36), visor=CYAN, seed=41))
reg("vr_sprite_johnson", person((34, 30, 40), AMB, (150, 150, 160), suit=True, seed=42))
reg("vr_sprite_guard",   person((40, 46, 58), (120, 130, 150), (30, 30, 36), gun=True, seed=43))
reg("vr_portrait_runner",  portrait((36, 60, 96), CYAN, (24, 26, 36), visor=CYAN))
reg("vr_portrait_johnson", portrait((34, 30, 40), AMB, (150, 150, 160), suit=True))

# ---- emit ------------------------------------------------------------------
def to_rgb565_colorkey(im):
    a = np.array(im)
    r = (a[:, :, 0].astype(np.uint16) >> 3) << 11
    g = (a[:, :, 1].astype(np.uint16) >> 2) << 5
    b = (a[:, :, 2].astype(np.uint16) >> 3)
    v = (r | g | b); opaque = a[:, :, 3] >= 128
    v = np.where((v == 0) & opaque, 1, v); v = np.where(opaque, v, 0)
    return v.astype('<u2').flatten()

def emit():
    hdr = ["#pragma once", "#include <stdint.h>", ""]
    for name, im, w, h in ASSETS:
        hdr += [f"extern const uint16_t {name}[{w}*{h}];",
                f"#define {name.upper()}_W {w}", f"#define {name.upper()}_H {h}"]
    with open(os.path.join(OUT, "vr_assets.h"), "w") as f:
        f.write("\n".join(hdr)+"\n")
    lines = ['#include "vr_assets.h"', ""]
    for name, im, w, h in ASSETS:
        arr = to_rgb565_colorkey(im)
        lines.append(f"const uint16_t {name}[{w}*{h}] = {{")
        for i in range(0, len(arr), 16):
            lines.append("    "+", ".join(f"0x{v:04X}" for v in arr[i:i+16])+",")
        lines += ["};", ""]
    with open(os.path.join(OUT, "vr_assets.c"), "w") as f:
        f.write("\n".join(lines)+"\n")
    tot = sum(w*h*2 for _, _, w, h in ASSETS)
    print(f"generated {len(ASSETS)} assets ({tot//1024} KiB in flash) -> main/assets/vr_assets.c/.h")

if __name__ == "__main__":
    emit()
