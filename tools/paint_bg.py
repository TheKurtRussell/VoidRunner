#!/usr/bin/env python3
"""
Painterly background generator for a side-scrolling VoidRunner (proof of concept).

Builds full-scene cyberpunk illustrations offline with numpy + Pillow using
atmosphere instead of geometry. Structure (dark, textured facades) is kept
separate from EMISSION (neon, lit windows, glows); emission drives bloom and
wet-ground reflections, which is what sells the painted, cinematic look.
On the ESP32-P4 these ship as JPEGs decoded by the hardware codec.

Usage: python3 tools/paint_bg.py [seed] [out.jpg]
"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1280, 720

def nfield(w, h, base=6, octaves=5, seed=0):
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32); amp = 1.0; tot = 0.0
    for o in range(octaves):
        gw = base * (2 ** o); gh = max(2, int(gw * h / w))
        g = (rng.random((gh, gw)) * 255).astype(np.uint8)
        up = np.asarray(Image.fromarray(g).resize((w, h), Image.BICUBIC), np.float32) / 255.0
        acc += amp * up; tot += amp; amp *= 0.5
    return acc / tot

def to_pil(a): return Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8), "RGB")
def from_pil(im): return np.asarray(im, np.float32) / 255.0
def blur(a, r): return from_pil(to_pil(a).filter(ImageFilter.GaussianBlur(r)))

def vgrad(stops):
    ys = np.linspace(0, 1, H, dtype=np.float32); out = np.zeros((H, 3), np.float32)
    for c in range(3):
        out[:, c] = np.interp(ys, [s[0] for s in stops], [s[1][c] for s in stops])
    return np.repeat(out[:, None, :], W, axis=1)

def soft_light(base, blend):
    return (1 - 2 * blend) * base ** 2 + 2 * blend * base

def add_rect(arr, x, y, w, h, color, val):
    x0, y0 = max(0, x), max(0, y); x1, y1 = min(W, x + w), min(arr.shape[0], y + h)
    if x1 <= x0 or y1 <= y0: return
    arr[y0:y1, x0:x1] += np.array(color, np.float32) * val

WARM = (1.0, 0.72, 0.40); COOL = (0.40, 0.85, 1.0); MAG = (1.0, 0.25, 0.65); GRN = (0.3, 1.0, 0.7)

def facade(struct, emis, mask, bbox, seed, ambient):
    """Dark textured facade + irregular glowing windows into the emission layer."""
    r = np.random.default_rng(seed)
    x0, y0, x1, y1 = bbox
    # tone: vertical gradient, darker up high, with grime noise + faint neon ambient wash
    grime = nfield(W, H, 7, 4, seed + 3)
    tone = np.zeros((H, W, 3), np.float32)
    vg = np.linspace(0.02, 0.11, H)[:, None]
    for c in range(3):
        tone[:, :, c] = (vg[:, 0, None] + grime * 0.05) + ambient[c] * 0.05
    struct[:] = struct * (1 - mask[:, :, None]) + tone * mask[:, :, None]
    # windows
    cx = x0
    while cx < x1:
        colw = r.integers(26, 40); dark_col = r.random() < 0.12
        cy = y0
        while cy < y1:
            rowh = r.integers(40, 56)
            if not dark_col and r.random() > 0.42:
                wx = cx + r.integers(3, 10); wy = cy + r.integers(6, 16)
                ww = r.integers(10, colw - 8); wh = r.integers(16, rowh - 12)
                if mask[min(H - 1, wy + wh // 2), min(W - 1, wx + ww // 2)] > 0.5:
                    pick = r.random()
                    col = WARM if pick < 0.6 else (COOL if pick < 0.9 else MAG)
                    bright = r.uniform(0.25, 1.0) ** 1.4
                    add_rect(emis, wx, wy, ww, wh, col, bright * 0.9)
                    add_rect(emis, wx - 3, wy - 3, ww + 6, wh + 6, col, bright * 0.25)  # room glow
            cy += rowh
        cx += colw

def alley(seed=7):
    rng = np.random.default_rng(seed)
    base = vgrad([(0.0, (0.05, 0.03, 0.12)), (0.42, (0.17, 0.06, 0.24)),
                  (0.58, (0.05, 0.035, 0.11)), (1.0, (0.02, 0.02, 0.05))])
    emis = np.zeros((H, W, 3), np.float32)
    struct = base.copy()

    # fog + horizon glow (atmosphere)
    fog = nfield(W, H, 5, 5, seed + 1)
    band = np.exp(-((np.linspace(0, 1, H) - 0.5) ** 2) / 0.03)[:, None]
    base += (fog * band)[:, :, None] * np.array([0.7, 0.28, 0.45]) * 0.5
    glow = np.exp(-((np.linspace(0, 1, H) - 0.52) ** 2) / 0.004)[:, None]
    emis += (glow)[:, :, None] * np.array([0.7, 0.3, 0.3]) * 0.5
    struct = base.copy()

    # far skyline (soft, atmospheric)
    im = Image.new("L", (W, H), 0); d = ImageDraw.Draw(im); x = -20
    while x < W + 20:
        bw = rng.integers(40, 110); bh = rng.integers(120, 250)
        d.rectangle([x, int(H * 0.56) - bh, x + bw, H], fill=255); x += bw + rng.integers(-4, 8)
    farm = blur(np.repeat((np.asarray(im, np.float32) / 255.0)[:, :, None], 3, 2), 2)[:, :, 0]
    far = np.zeros((H, W, 3), np.float32) + np.array([0.11, 0.11, 0.2])
    struct = struct * (1 - farm[:, :, None] * 0.8) + far * (farm[:, :, None] * 0.8)
    for _ in range(300):
        wx = rng.integers(0, W); wy = rng.integers(int(H * 0.36), int(H * 0.56))
        if farm[wy, wx] > 0.5: add_rect(emis, wx, wy, rng.integers(2, 4), rng.integers(2, 5), (0.5, 0.5, 0.65), 0.4)

    # framing buildings leaving an alley slot
    frame = Image.new("L", (W, H), 0); fd = ImageDraw.Draw(frame)
    fd.polygon([(0, 0), (440, 0), (478, H), (0, H)], fill=255)
    fd.polygon([(W, 0), (846, 0), (806, H), (W, H)], fill=255)
    fm = np.asarray(frame, np.float32) / 255.0
    facade(struct, emis, fm, (10, 20, 460, H), seed + 10, np.array(MAG))
    facade(struct, emis, fm, (820, 20, W - 10, H), seed + 20, np.array(COOL))

    # neon signs (vertical blade + horizontal marquees)
    sim = Image.new("RGB", (W, H), (0, 0, 0)); sd = ImageDraw.Draw(sim)
    for x, y, w, h, col in [(66, 150, 24, 165, MAG), (300, 120, 118, 26, COOL),
                            (986, 210, 26, 185, GRN), (1120, 120, 120, 24, WARM),
                            (150, 440, 104, 24, MAG), (860, 470, 90, 20, COOL)]:
        sd.rectangle([x, y, x + w, y + h], fill=tuple(int(c * 255) for c in col))
    emis += from_pil(sim)

    # vanishing-point light + god rays (restrained — distant, not a supernova)
    slot = np.exp(-(((np.arange(W) - 642) / 58.0) ** 2))[None, :] * \
           np.exp(-(((np.arange(H)[:, None] - 330) / 130.0) ** 2))
    emis += slot[:, :, None] * np.array([0.4, 0.45, 0.62]) * 0.38
    rays = np.exp(-(((np.arange(W) - 642) / 160.0) ** 2))[None, :] * \
           np.linspace(1, 0, H)[:, None]
    emis += (rays * fog)[:, :, None] * np.array([0.4, 0.38, 0.6]) * 0.28

    # compose upper scene: structure + emission + bloom
    bloom = blur(emis, 8) * 0.9 + blur(emis, 22) * 0.6
    img = struct + emis + bloom

    # wet ground with emissive reflections
    gy = int(H * 0.70)
    refl_src = np.flipud(emis)[:H - gy]
    wob = (nfield(W, H - gy, 3, 3, seed + 30) - 0.5) * 8
    idx = np.clip((np.arange(W)[None, :] + wob).astype(int), 0, W - 1)
    refl = np.take_along_axis(refl_src, idx[:, :, None].repeat(3, 2), axis=1)
    refl = blur(np.vstack([refl, np.zeros((gy, W, 3), np.float32)]), 5)[:H - gy]
    fade = np.linspace(0.6, 0.02, H - gy)[:, None, None]
    ground = struct[gy:] * 0.18 + refl * fade * 1.6 + np.array([0.015, 0.015, 0.03])
    img[gy:] = ground
    img[gy:gy + 2] += np.array([0.15, 0.2, 0.3])

    # rain
    rainim = Image.new("L", (W, H), 0); rd = ImageDraw.Draw(rainim)
    for _ in range(1100):
        x = rng.integers(0, W); y = rng.integers(0, H); ln = rng.integers(12, 28)
        rd.line([(x, y), (x - 6, y + ln)], fill=int(rng.integers(30, 110)))
    img += (np.asarray(rainim, np.float32)[:, :, None] / 255.0) * np.array([0.45, 0.55, 0.7]) * 0.45

    # foreground silhouettes: fire escape, dumpster, lone runner (rim-lit)
    fg = Image.new("RGBA", (W, H), (0, 0, 0, 0)); fdd = ImageDraw.Draw(fg)
    for yy in range(120, H, 80):  # fire escape rails on left building
        fdd.line([(40, yy), (200, yy)], fill=(8, 8, 12, 255), width=4)
        fdd.line([(40, yy), (40, yy + 80)], fill=(8, 8, 12, 255), width=4)
        fdd.line([(200, yy), (200, yy + 80)], fill=(8, 8, 12, 255), width=4)
    fdd.rectangle([150, 568, 330, 706], fill=(5, 5, 9, 255))               # dumpster
    fdd.line([(150, 568), (330, 568)], fill=(60, 200, 220, 230), width=2)
    px, py = 740, 694                                                      # runner
    fdd.polygon([(px - 20, py - 158), (px + 20, py - 158), (px + 28, py - 60), (px - 28, py - 60)], fill=(3, 3, 7, 255))
    fdd.ellipse([px - 15, py - 192, px + 15, py - 158], fill=(3, 3, 7, 255))
    fdd.polygon([(px - 26, py - 60), (px - 8, py - 60), (px - 10, py), (px - 28, py)], fill=(3, 3, 7, 255))
    fdd.polygon([(px + 8, py - 60), (px + 26, py - 60), (px + 28, py), (px + 10, py)], fill=(3, 3, 7, 255))
    fdd.line([(px + 20, py - 158), (px + 28, py - 60)], fill=(255, 70, 180, 240), width=3)
    fdd.line([(px - 20, py - 158), (px - 28, py - 60)], fill=(70, 210, 255, 170), width=2)
    fdd.line([(px - 15, py - 186), (px + 2, py - 176)], fill=(255, 70, 180, 120), width=2)
    fga = np.asarray(fg, np.float32)[:, :, :3] / 255.0; fgm = np.asarray(fg, np.float32)[:, :, 3:4] / 255.0
    img = img * (1 - fgm) + fga * fgm

    # painterly post
    img = soft_light(img, blur(img, 3)) * 0.45 + img * 0.55          # soft self-mix
    brush = nfield(W, H, 10, 3, seed + 99)[:, :, None]
    img = img * (0.94 + 0.12 * brush)                                # subtle brush texture
    lum = img.mean(2, keepdims=True)
    img += (0.07 * (1 - lum)) * np.array([-0.2, 0.25, 0.5]) + (0.07 * lum) * np.array([0.5, -0.05, 0.1])
    img += (rng.random((H, W, 1)) - 0.5) * 0.025                     # grain
    yy, xx = np.mgrid[0:H, 0:W]
    vig = 1 - (((xx - W / 2) / (W / 1.45)) ** 2 + ((yy - H / 2) / (H / 1.35)) ** 2)
    img *= np.clip(vig, 0.3, 1.0)[:, :, None]
    return to_pil(np.clip(img, 0, 1) ** 0.9)


def room(seed=5):
    """Warm noir interior: a dim room with a rain-streaked city window throwing cool light."""
    rng = np.random.default_rng(seed)
    base = vgrad([(0.0, (0.10, 0.06, 0.07)), (0.5, (0.08, 0.05, 0.06)), (1.0, (0.03, 0.02, 0.03))])
    emis = np.zeros((H, W, 3), np.float32)
    # window on the right: cool city light + bokeh + rain
    wx0, wy0, wx1, wy1 = 760, 70, 1180, 520
    win = np.zeros((H, W, 3), np.float32)
    g = vgrad([(0.0, (0.18, 0.26, 0.40)), (0.7, (0.10, 0.16, 0.28)), (1.0, (0.06, 0.08, 0.16))])
    win[wy0:wy1, wx0:wx1] = g[wy0:wy1, wx0:wx1]
    for _ in range(120):               # city bokeh beyond the glass
        bx = rng.integers(wx0, wx1); by = rng.integers(wy0, wy1)
        col = WARM if rng.random() < 0.5 else COOL
        add_rect(win, bx, by, rng.integers(3, 8), rng.integers(3, 8), col, rng.uniform(0.2, 0.8))
    win = blur(win, 2)
    rainim = Image.new("L", (W, H), 0); rd = ImageDraw.Draw(rainim)
    for _ in range(400):
        x = rng.integers(wx0, wx1); y = rng.integers(wy0, wy1); ln = rng.integers(14, 30)
        rd.line([(x, y), (x - 7, y + ln)], fill=int(rng.integers(40, 110)))
    win += (np.asarray(rainim, np.float32)[:, :, None] / 255.0) * np.array([0.3, 0.4, 0.55])
    emis[wy0:wy1, wx0:wx1] += win[wy0:wy1, wx0:wx1]
    # mullions
    mull = np.zeros((H, W, 3), np.float32)
    mx = (wx0 + wx1) // 2; my = (wy0 + wy1) // 2
    mull[wy0:wy1, mx - 3:mx + 3] = 0.02; mull[my - 3:my + 3, wx0:wx1] = 0.02
    base[wy0:wy1, wx0:wx1] = base[wy0:wy1, wx0:wx1] * 0.2 + mull[wy0:wy1, wx0:wx1]
    base += emis
    # volumetric shaft from window across the floor
    shaft = np.zeros((H, W), np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    shaft = np.clip(1 - np.abs((xx - (yy - 200) * 1.3 - 500) / 300.0), 0, 1) * np.clip((yy - 200) / 500.0, 0, 1)
    base += (shaft[:, :, None]) * np.array([0.12, 0.16, 0.24]) * 0.5
    # warm desk lamp glow (left)
    lamp = np.exp(-(((xx - 300) / 120.0) ** 2 + ((yy - 360) / 120.0) ** 2))
    base += lamp[:, :, None] * np.array([1.0, 0.6, 0.25]) * 0.5
    # foreground silhouettes: desk + seated figure (rim lit by window)
    fg = Image.new("RGBA", (W, H), (0, 0, 0, 0)); fdd = ImageDraw.Draw(fg)
    fdd.rectangle([120, 470, 620, 560], fill=(4, 3, 5, 255))                 # desk
    fdd.rectangle([120, 470, 620, 478], fill=(0, 0, 0, 0))
    fdd.line([(120, 470), (620, 470)], fill=(255, 150, 60, 160), width=2)    # lamp rim on desk
    # seated figure behind desk
    cxp = 430
    fdd.ellipse([cxp - 34, 300, cxp + 34, 380], fill=(3, 3, 5, 255))         # head
    fdd.polygon([(cxp - 70, 470), (cxp + 70, 470), (cxp + 46, 360), (cxp - 46, 360)], fill=(3, 3, 5, 255))
    fdd.line([(cxp + 46, 360), (cxp + 70, 470)], fill=(90, 180, 240, 200), width=3)  # cool rim from window
    fdd.line([(cxp + 34, 318), (cxp + 30, 360)], fill=(120, 200, 255, 180), width=2)
    fga = np.asarray(fg, np.float32)[:, :, :3] / 255.0; fgm = np.asarray(fg, np.float32)[:, :, 3:4] / 255.0
    base = base * (1 - fgm) + fga * fgm
    # post
    img = base
    img = soft_light(img, blur(img, 3)) * 0.45 + img * 0.55
    img = img * (0.94 + 0.12 * nfield(W, H, 10, 3, seed + 9)[:, :, None])
    lum = img.mean(2, keepdims=True)
    img += (0.06 * (1 - lum)) * np.array([-0.1, 0.1, 0.35]) + (0.07 * lum) * np.array([0.5, 0.15, -0.05])
    img += (rng.random((H, W, 1)) - 0.5) * 0.025
    yy2, xx2 = np.mgrid[0:H, 0:W]
    vig = 1 - (((xx2 - W / 2) / (W / 1.45)) ** 2 + ((yy2 - H / 2) / (H / 1.3)) ** 2)
    img *= np.clip(vig, 0.3, 1.0)[:, :, None]
    return to_pil(np.clip(img, 0, 1) ** 0.9)

def portrait_noir(tint=MAG, skin=(0.55, 0.42, 0.34), seed=1, pw=320, ph=400):
    """Rim-lit bust in shadow — noir 'contact' portrait that reads as intentional, not low-detail."""
    rng = np.random.default_rng(seed)
    a = np.zeros((ph, pw, 3), np.float32)
    for y in range(ph):
        a[y, :] = np.array([0.06, 0.05, 0.09]) * (1 - y / ph) + np.array([0.02, 0.02, 0.04]) * (y / ph)
    # back glow
    yy, xx = np.mgrid[0:ph, 0:pw]
    glow = np.exp(-(((xx - pw * 0.62) / (pw * 0.4)) ** 2 + ((yy - ph * 0.4) / (ph * 0.5)) ** 2))
    a += glow[:, :, None] * np.array(tint) * 0.22
    sil = Image.new("L", (pw, ph), 0); sd = ImageDraw.Draw(sil)
    cx = int(pw * 0.5)
    sd.ellipse([cx - 60, 70, cx + 60, 210], fill=255)                     # head
    sd.polygon([(cx - 120, ph), (cx + 120, ph), (cx + 90, 200), (cx - 90, 200)], fill=255)  # shoulders
    m = np.asarray(sil, np.float32) / 255.0
    body = np.zeros((ph, pw, 3), np.float32) + np.array([0.02, 0.02, 0.03])
    # faint skin on the lit cheek
    cheek = np.exp(-(((xx - (cx + 26)) / 36.0) ** 2 + ((yy - 150) / 46.0) ** 2))
    body += cheek[:, :, None] * np.array(skin) * 0.5 * m[:, :, None]
    a = a * (1 - m[:, :, None]) + body * m[:, :, None]
    # rim light along the right edge of the silhouette
    rim = (np.roll(m, -3, axis=1) - m)
    rim = np.clip(-rim, 0, 1)
    rim = np.asarray(Image.fromarray((rim * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1)), np.float32) / 255.0
    a += rim[:, :, None] * np.array(tint) * 1.4
    # eye glint
    a[150:156, cx + 10:cx + 20] += np.array(tint) * 0.8
    a = soft_light(a, from_pil(to_pil(a).filter(ImageFilter.GaussianBlur(2)))) * 0.5 + a * 0.5
    a += (rng.random((ph, pw, 1)) - 0.5) * 0.02
    im = to_pil(np.clip(a, 0, 1))
    d = ImageDraw.Draw(im); d.rectangle([0, 0, pw - 1, ph - 1], outline=tuple(int(c * 255) for c in tint), width=3)
    return im

def wrap(draw, text, font, maxw):
    words = text.split(); lines = []; cur = ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if draw.textlength(t, font=font) <= maxw: cur = t
        else: lines.append(cur); cur = w_
    if cur: lines.append(cur)
    return lines

def compose_frame(bg, portrait, speaker, text, choices, out):
    """Mock an in-game VN frame: background + portrait + dialogue box + choices."""
    from PIL import ImageFont
    im = bg.convert("RGBA")
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        fc = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 23)
    except Exception:
        f = fb = fc = ImageFont.load_default()
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    # dialogue panel
    d.rectangle([44, 486, 1236, 694], fill=(8, 10, 20, 205), outline=(0, 240, 255, 255), width=2)
    # portrait
    im.alpha_composite(portrait.convert("RGBA").resize((176, 220)), (64, 250))
    d.rectangle([64, 250, 240, 470], outline=(255, 42, 165, 255), width=2)
    # speaker + text
    d.rectangle([64, 470, 64 + int(d.textlength(speaker, font=fb)) + 24, 500], fill=(255, 42, 165, 235))
    d.text((76, 474), speaker, font=fb, fill=(10, 10, 16))
    for i, ln in enumerate(wrap(d, text, f, 760)):
        d.text((300, 512 + i * 34), ln, font=f, fill=(222, 232, 246))
    # choices on the right
    for i, ch in enumerate(choices[:3]):
        y = 512 + i * 56
        d.rectangle([1040, y, 1216, y + 46], outline=(124, 245, 194, 255), width=2)
        d.rectangle([1040, y, 1216, y + 46], fill=(20, 40, 36, 150))
        d.text((1056, y + 10), ch, font=fc, fill=(124, 245, 194))
    im = Image.alpha_composite(im, ov)
    im.convert("RGB").save(out, quality=90); print("saved", out)

def build_all():
    import os
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main", "assets", "vn")
    os.makedirs(d, exist_ok=True)
    scenes = {"scn_street": alley(7), "scn_office": room(5),
              "scn_gallery": alley(3), "scn_vault": room(11)}
    for name, im in scenes.items():
        im.save(os.path.join(d, name + ".jpg"), quality=86)
    ports = {"por_vex": portrait_noir(MAG, seed=2, pw=192, ph=240),
             "por_fixer": portrait_noir((1.0, 0.62, 0.2), seed=4, pw=192, ph=240),
             "por_guard": portrait_noir(COOL, seed=6, pw=192, ph=240)}
    for name, im in ports.items():
        im.save(os.path.join(d, name + ".jpg"), quality=90)
    print("built", len(scenes), "scenes +", len(ports), "portraits ->", d)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "alley"
    if mode == "build":
        build_all()
    elif mode == "mock":
        bg = alley(7)
        p = portrait_noir(MAG, seed=2)
        compose_frame(bg, p,
                      "VEX",
                      "Word is Saeder-Krupp moved the prototype to the downtown gallery. Security's light tonight. You want the job, or should I call someone with a steadier trigger finger?",
                      ["Take the job", "Ask about pay", "Walk away"],
                      sys.argv[2] if len(sys.argv) > 2 else "/tmp/vn_frame.jpg")
    elif mode == "room":
        room(int(sys.argv[2]) if len(sys.argv) > 2 else 5).save(sys.argv[3] if len(sys.argv) > 3 else "/tmp/paint_room.jpg", quality=88)
        print("saved room")
    else:
        seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
        out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/paint_alley.jpg"
        alley(seed).save(out, quality=88); print("saved", out)
