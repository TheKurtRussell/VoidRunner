#!/usr/bin/env python3
"""
Painterly background generator for VoidRunner (visual novel).

Builds full-scene cyberpunk illustrations offline with numpy + Pillow. The goal is
a PAINTED look, not geometry:
  * lights are soft multi-radius glows (bokeh), never rectangles
  * silhouettes are noise-warped organic edges, never straight slabs
  * a Kuwahara ("oil paint") post filter flattens regions into brush-like strokes
    while preserving edges, then a soft-light + grade + grain + vignette pass
Scenes export as JPEGs; the ESP32-P4 decodes them with esp_jpeg.

Modes:  build | mock [out] | alley [seed] [out] | room [seed] [out]
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1280, 720

WARM = (1.0, 0.72, 0.42); COOL = (0.42, 0.85, 1.0); MAG = (1.0, 0.28, 0.62)
GRN = (0.45, 1.0, 0.72); AMB = (1.0, 0.68, 0.25); WHITE = (0.95, 0.97, 1.0)

def to_pil(a): return Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8), "RGB")
def from_pil(im): return np.asarray(im, np.float32) / 255.0
def blur(a, r): return from_pil(to_pil(a).filter(ImageFilter.GaussianBlur(r)))
def boxb(a, r):
    if r < 1: return a
    return np.asarray(to_pil(a).filter(ImageFilter.BoxBlur(r)), np.float32) / 255.0

def nfield(w, h, base=6, octaves=5, seed=0):
    rng = np.random.default_rng(seed); acc = np.zeros((h, w), np.float32); amp = 1.0; tot = 0.0
    for o in range(octaves):
        gw = base * (2 ** o); gh = max(2, int(gw * h / w))
        g = (rng.random((gh, gw)) * 255).astype(np.uint8)
        up = np.asarray(Image.fromarray(g).resize((w, h), Image.BICUBIC), np.float32) / 255.0
        acc += amp * up; tot += amp; amp *= 0.5
    return acc / tot

def noise1d(n, seed, cells=14):
    r = np.random.default_rng(seed).random(cells).astype(np.float32)
    return np.asarray(Image.fromarray((r[None, :] * 255).astype(np.uint8)).resize((n, 1), Image.BICUBIC), np.float32)[0] / 255.0

def vgrad(stops):
    ys = np.linspace(0, 1, H, dtype=np.float32); out = np.zeros((H, 3), np.float32)
    for c in range(3):
        out[:, c] = np.interp(ys, [s[0] for s in stops], [s[1][c] for s in stops])
    return np.repeat(out[:, None, :], W, axis=1)

def soft_light(base, blend):
    return (1 - 2 * blend) * base ** 2 + 2 * blend * base

def emissive(pts):
    """Crisp light cores + layered bloom -> lights stay punchy, edges glow."""
    core = blur(pts, 1.3) * 1.7
    bloom = blur(pts, 6) * 0.7 + blur(pts, 16) * 0.42 + blur(pts, 34) * 0.22
    return core + bloom

def add_window_lights(pts, mask, region, density, seed, palette):
    r = np.random.default_rng(seed); x0, y0, x1, y1 = region
    for _ in range(density):
        x = int(r.integers(x0, x1)); y = int(r.integers(y0, y1))
        if mask[min(H - 1, y), min(W - 1, x)] > 0.5:
            col = np.array(palette[int(r.integers(len(palette)))], np.float32)
            inten = (0.3 + 0.9 * r.random() ** 1.2) * 1.5
            pts[max(0, y - 1):y + 2, max(0, x):x + 2] += col * inten  # ~2px pane

def kuwahara(a, r=5):
    """Edge-preserving painterly flattening (brush-stroke look)."""
    rh = max(1, r // 2)
    def sh(x, dy, dx): return np.roll(np.roll(x, dy, 0), dx, 1)
    mean = boxb(a, rh)
    lum = a.mean(2, keepdims=True)
    ml = boxb(np.repeat(lum, 3, 2), rh)[:, :, :1]
    ml2 = boxb(np.repeat(lum ** 2, 3, 2), rh)[:, :, :1]
    var = np.clip(ml2 - ml ** 2, 0, None)[:, :, 0]
    offs = [(-rh, -rh), (-rh, rh), (rh, -rh), (rh, rh)]
    vars = np.stack([sh(var, dy, dx) for dy, dx in offs], 0)
    cols = [sh(mean, dy, dx) for dy, dx in offs]
    idx = np.argmin(vars, 0)
    out = np.zeros_like(a)
    for k in range(4):
        out = np.where((idx == k)[:, :, None], cols[k], out)
    return out

def painterly_base(base, paint=6):
    """Oil-paint the STRUCTURE only (lights are added on top afterwards)."""
    b = np.clip(base, 0, 1)
    b = kuwahara(b, paint) * 0.62 + b * 0.38
    b = soft_light(b, blur(b, 3)) * 0.4 + b * 0.6
    return b

def finish(img, seed, grade_shadow, grade_hi, vig=1.45):
    img = np.clip(img, 0, 1)
    canvas = nfield(W, H, 11, 3, seed + 77)[:, :, None]       # brush/canvas texture
    img = img * (0.94 + 0.12 * canvas)
    lum = img.mean(2, keepdims=True)
    img += (0.08 * (1 - lum)) * np.array(grade_shadow) + (0.08 * lum) * np.array(grade_hi)
    img += (np.random.default_rng(seed).random((H, W, 1)) - 0.5) * 0.02
    yy, xx = np.mgrid[0:H, 0:W]
    v = 1 - (((xx - W / 2) / (W / vig)) ** 2 + ((yy - H / 2) / (H / (vig - 0.1))) ** 2)
    img *= np.clip(v, 0.28, 1.0)[:, :, None]
    return to_pil(np.clip(img, 0, 1) ** 0.9)

# ----------------------------------------------------------------------------
def alley(seed=7):
    rng = np.random.default_rng(seed)
    base = vgrad([(0.0, (0.05, 0.03, 0.13)), (0.40, (0.18, 0.06, 0.26)),
                  (0.56, (0.07, 0.04, 0.13)), (1.0, (0.02, 0.02, 0.05))])
    # warped atmospheric fog
    fog = nfield(W, H, 5, 5, seed + 1)
    band = np.exp(-((np.linspace(0, 1, H) - 0.5) ** 2) / 0.04)[:, None]
    base += (fog * band)[:, :, None] * np.array([0.6, 0.26, 0.42]) * 0.55
    pts = np.zeros((H, W, 3), np.float32)
    # soft horizon pool
    hb = np.exp(-((np.linspace(0, 1, H) - 0.52) ** 2) / 0.01)[:, None]
    pts += (hb)[:, :, None] * np.array([0.55, 0.28, 0.32]) * 0.5

    yy, xx = np.mgrid[0:H, 0:W]
    # distant skyline (soft, atmospheric) — warped top edge
    sky_h = 180 + noise1d(W, seed + 2, 20) * 150
    sky_mask = (yy > (H * 0.56 - sky_h[None, :])).astype(np.float32)
    sky_mask = blur(np.repeat(sky_mask[:, :, None], 3, 2), 2)[:, :, 0]
    base = base * (1 - sky_mask[:, :, None] * 0.7) + np.array([0.1, 0.1, 0.19]) * (sky_mask[:, :, None] * 0.7)
    add_window_lights(pts, sky_mask, (0, int(H * 0.34), W, int(H * 0.56)), 500, seed + 3,
                      [(0.4, 0.4, 0.55), WARM, COOL])

    # framing buildings with ORGANIC warped inner edges leaving an alley slot
    warpL = (noise1d(H, seed + 4, 16) - 0.5) * 70
    warpR = (noise1d(H, seed + 5, 16) - 0.5) * 70
    edgeL = 300 + 150 * (yy[:, 0] / H) + warpL
    edgeR = 980 - 150 * (yy[:, 0] / H) + warpR
    maskL = (xx < edgeL[:, None]).astype(np.float32)
    maskR = (xx > edgeR[:, None]).astype(np.float32)
    frame = np.clip(maskL + maskR, 0, 1)
    frame = blur(np.repeat(frame[:, :, None], 3, 2), 1.5)[:, :, 0]
    grime = nfield(W, H, 8, 4, seed + 6)
    facade = (np.linspace(0.02, 0.10, H)[:, None] + grime * 0.05)[:, :, None] * np.ones(3)
    base = base * (1 - frame[:, :, None]) + facade * frame[:, :, None]
    add_window_lights(pts, maskL, (10, 20, 470, H), 420, seed + 7, [WARM, WARM, COOL, MAG])
    add_window_lights(pts, maskR, (810, 20, W - 10, H), 420, seed + 8, [COOL, WARM, COOL, GRN])

    # neon signs as soft capsules (blurred, not rectangles)
    sig = np.zeros((H, W, 3), np.float32)
    for x, y, w, h, col in [(96, 150, 10, 150, MAG), (330, 130, 110, 10, COOL),
                            (1000, 210, 10, 170, GRN), (1120, 130, 110, 9, AMB),
                            (170, 440, 95, 9, MAG)]:
        sig[y:y + h, x:x + w] += np.array(col)
    pts += sig
    # distant vanishing light (restrained)
    slot = np.exp(-(((xx - 640) / 46.0) ** 2) - (((yy - 340) / 100.0) ** 2))
    pts += slot[:, :, None] * np.array([0.4, 0.44, 0.62]) * 0.26

    img = painterly_base(base) + emissive(pts)

    # wet ground with wavy emissive reflection
    gy = int(H * 0.70)
    refl = np.flipud(emissive(pts))[:H - gy]
    wob = (nfield(W, H - gy, 3, 3, seed + 9) - 0.5) * 10
    idx = np.clip((np.arange(W)[None, :] + wob).astype(int), 0, W - 1)
    refl = np.take_along_axis(refl, idx[:, :, None].repeat(3, 2), axis=1)
    refl = blur(refl, 5)
    fade = np.linspace(0.6, 0.03, H - gy)[:, None, None]
    img[gy:] = img[gy:] * 0.14 + refl * fade * 1.5 + np.array([0.015, 0.015, 0.03])

    # rain
    rainim = Image.new("L", (W, H), 0); rd = ImageDraw.Draw(rainim)
    for _ in range(900):
        x = rng.integers(0, W); y = rng.integers(0, H); ln = rng.integers(12, 26)
        rd.line([(x, y), (x - 6, y + ln)], fill=int(rng.integers(30, 95)))
    img += (np.asarray(rainim.filter(ImageFilter.GaussianBlur(0.6)), np.float32)[:, :, None] / 255.0) * np.array([0.4, 0.5, 0.65]) * 0.4

    # foreground: soft fire-escape + lone runner with neon rim
    fg = Image.new("L", (W, H), 0); fdd = ImageDraw.Draw(fg)
    for yb in range(130, H, 84):
        fdd.line([(44, yb), (210, yb)], fill=255, width=5)
        fdd.line([(44, yb), (44, yb + 84)], fill=255, width=5)
        fdd.line([(210, yb), (210, yb + 84)], fill=255, width=5)
    fdd.rectangle([150, 566, 338, 708], fill=255)
    px, py = 742, 700
    fdd.polygon([(px - 20, py - 160), (px + 20, py - 160), (px + 28, py - 58), (px - 28, py - 58)], fill=255)
    fdd.ellipse([px - 15, py - 196, px + 15, py - 160], fill=255)
    fdd.polygon([(px - 26, py - 58), (px - 8, py - 58), (px - 10, py), (px - 28, py)], fill=255)
    fdd.polygon([(px + 8, py - 58), (px + 26, py - 58), (px + 28, py), (px + 10, py)], fill=255)
    fgm = np.asarray(fg.filter(ImageFilter.GaussianBlur(0.8)), np.float32)[:, :, None] / 255.0
    img = img * (1 - fgm) + np.array([0.02, 0.02, 0.04]) * fgm
    rimim = Image.new("RGB", (W, H), (0, 0, 0)); ri = ImageDraw.Draw(rimim)
    ri.line([(px + 20, py - 160), (px + 28, py - 58)], fill=(255, 70, 180), width=3)
    ri.line([(px - 20, py - 160), (px - 28, py - 58)], fill=(70, 210, 255), width=2)
    ri.line([(150, 566), (338, 566)], fill=(60, 200, 220), width=2)
    img += from_pil(rimim.filter(ImageFilter.GaussianBlur(0.5)))

    return finish(img, seed, [-0.2, 0.28, 0.5], [0.5, -0.05, 0.1])

def room(seed=5):
    rng = np.random.default_rng(seed)
    base = vgrad([(0.0, (0.11, 0.06, 0.07)), (0.5, (0.08, 0.05, 0.06)), (1.0, (0.03, 0.02, 0.03))])
    pts = np.zeros((H, W, 3), np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    # window: cool city light + soft bokeh beyond the glass
    wx0, wy0, wx1, wy1 = 756, 70, 1182, 520
    wmask = ((xx >= wx0) & (xx < wx1) & (yy >= wy0) & (yy < wy1)).astype(np.float32)
    g = vgrad([(0.0, (0.16, 0.24, 0.38)), (0.7, (0.09, 0.15, 0.26)), (1.0, (0.05, 0.07, 0.15))])
    base = base * (1 - wmask[:, :, None]) + g * wmask[:, :, None]
    add_window_lights(pts, wmask, (wx0, wy0, wx1, wy1), 180, seed + 1, [WARM, COOL, COOL])
    # rain beyond glass
    rainim = Image.new("L", (W, H), 0); rd = ImageDraw.Draw(rainim)
    for _ in range(360):
        x = rng.integers(wx0, wx1); y = rng.integers(wy0, wy1); ln = rng.integers(14, 28)
        rd.line([(x, y), (x - 7, y + ln)], fill=int(rng.integers(40, 100)))
    pts += (np.asarray(rainim, np.float32)[:, :, None] / 255.0) * np.array([0.25, 0.35, 0.5])
    # mullions (thin dark)
    base[wy0:wy1, (wx0 + wx1) // 2 - 2:(wx0 + wx1) // 2 + 2] *= 0.3
    base[(wy0 + wy1) // 2 - 2:(wy0 + wy1) // 2 + 2, wx0:wx1] *= 0.3
    # warm desk lamp pool + volumetric shaft from the window
    pts += np.exp(-(((xx - 300) / 130.0) ** 2 + ((yy - 360) / 130.0) ** 2))[:, :, None] * np.array([1.0, 0.6, 0.25]) * 0.55
    shaft = np.clip(1 - np.abs((xx - (yy - 200) * 1.3 - 520) / 320.0), 0, 1) * np.clip((yy - 200) / 500.0, 0, 1)
    pts += shaft[:, :, None] * np.array([0.12, 0.16, 0.26]) * 0.5

    img = painterly_base(base) + emissive(pts)

    # foreground silhouettes (soft): desk + seated contact, rim-lit by window
    fg = Image.new("L", (W, H), 0); fdd = ImageDraw.Draw(fg)
    fdd.rectangle([110, 470, 640, 566], fill=255)
    cxp = 430
    fdd.ellipse([cxp - 36, 296, cxp + 36, 380], fill=255)
    fdd.polygon([(cxp - 74, 474), (cxp + 74, 474), (cxp + 48, 356), (cxp - 48, 356)], fill=255)
    fgm = np.asarray(fg.filter(ImageFilter.GaussianBlur(0.8)), np.float32)[:, :, None] / 255.0
    img = img * (1 - fgm) + np.array([0.02, 0.015, 0.025]) * fgm
    rimim = Image.new("RGB", (W, H), (0, 0, 0)); ri = ImageDraw.Draw(rimim)
    ri.line([(cxp + 48, 356), (cxp + 74, 474)], fill=(90, 180, 240), width=3)
    ri.line([(cxp + 36, 316), (cxp + 32, 356)], fill=(120, 200, 255), width=2)
    ri.line([(110, 470), (640, 470)], fill=(255, 150, 60), width=2)
    img += from_pil(rimim.filter(ImageFilter.GaussianBlur(0.6)))

    return finish(img, seed, [-0.1, 0.12, 0.34], [0.5, 0.18, -0.05])

# ---- portraits -------------------------------------------------------------
def portrait_noir(tint=MAG, skin=(0.55, 0.42, 0.34), seed=1, pw=192, ph=240):
    rng = np.random.default_rng(seed)
    a = np.zeros((ph, pw, 3), np.float32)
    yy, xx = np.mgrid[0:ph, 0:pw]
    for y in range(ph):
        a[y, :] = np.array([0.06, 0.05, 0.09]) * (1 - y / ph) + np.array([0.02, 0.02, 0.04]) * (y / ph)
    a += np.exp(-(((xx - pw * 0.62) / (pw * 0.4)) ** 2 + ((yy - ph * 0.4) / (ph * 0.5)) ** 2))[:, :, None] * np.array(tint) * 0.22
    sil = Image.new("L", (pw, ph), 0); sd = ImageDraw.Draw(sil); cx = int(pw * 0.5)
    sd.ellipse([cx - 60, 70, cx + 60, 210], fill=255)
    sd.polygon([(cx - 120, ph), (cx + 120, ph), (cx + 90, 200), (cx - 90, 200)], fill=255)
    m = np.asarray(sil.filter(ImageFilter.GaussianBlur(1)), np.float32) / 255.0
    body = np.zeros((ph, pw, 3), np.float32) + np.array([0.02, 0.02, 0.03])
    body += np.exp(-(((xx - (cx + 26)) / 36.0) ** 2 + ((yy - 150) / 46.0) ** 2))[:, :, None] * np.array(skin) * 0.5 * m[:, :, None]
    a = a * (1 - m[:, :, None]) + body * m[:, :, None]
    rim = np.clip(-(np.roll(m, -3, 1) - m), 0, 1)
    rim = np.asarray(Image.fromarray((rim * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1)), np.float32) / 255.0
    a += rim[:, :, None] * np.array(tint) * 1.4
    a[150:156, cx + 10:cx + 20] += np.array(tint) * 0.8
    a = kuwahara(np.clip(a, 0, 1), 4) * 0.7 + np.clip(a, 0, 1) * 0.3
    a += (rng.random((ph, pw, 1)) - 0.5) * 0.02
    im = to_pil(a); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, pw - 1, ph - 1], outline=tuple(int(c * 255) for c in tint), width=3)
    return im

# ---- VN frame mock ---------------------------------------------------------
def wrap(draw, text, font, maxw):
    out = []
    for para in text.split("\n"):
        words = para.split(); cur = ""
        for w_ in words:
            t = (cur + " " + w_).strip()
            if draw.textlength(t, font=font) <= maxw: cur = t
            else: out.append(cur); cur = w_
        out.append(cur)
    return out

def compose_frame(bg, portrait, speaker, text, choices, out):
    from PIL import ImageFont
    im = bg.convert("RGBA")
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except Exception:
        f = fb = ImageFont.load_default()
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    d.rectangle([44, 486, 1236, 694], fill=(8, 10, 20, 205), outline=(0, 240, 255, 255), width=2)
    im.alpha_composite(portrait.convert("RGBA").resize((176, 220)), (64, 258))
    d.rectangle([64, 466, 64 + int(d.textlength(speaker, font=fb)) + 24, 496], fill=(255, 42, 165, 235))
    d.text((76, 470), speaker, font=fb, fill=(10, 10, 16))
    for i, ln in enumerate(wrap(d, text, f, 720)):
        d.text((300, 512 + i * 34), ln, font=f, fill=(222, 232, 246))
    for i, ch in enumerate(choices[:3]):
        y = 512 + i * 56
        d.rectangle([1040, y, 1216, y + 46], fill=(20, 40, 36, 150), outline=(124, 245, 194, 255), width=2)
        d.text((1056, y + 10), ch, font=f, fill=(124, 245, 194))
    Image.alpha_composite(im, ov).convert("RGB").save(out, quality=90); print("saved", out)

def build_all():
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main", "assets", "vn")
    os.makedirs(d, exist_ok=True)
    for name, im in {"scn_street": alley(7), "scn_office": room(5),
                     "scn_gallery": alley(3), "scn_vault": room(11)}.items():
        im.save(os.path.join(d, name + ".jpg"), quality=86)
    for name, im in {"por_vex": portrait_noir(MAG, seed=2),
                     "por_fixer": portrait_noir((1.0, 0.62, 0.2), seed=4),
                     "por_guard": portrait_noir(COOL, seed=6)}.items():
        im.save(os.path.join(d, name + ".jpg"), quality=90)
    print("built scenes + portraits ->", d)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "alley"
    if mode == "build":
        build_all()
    elif mode == "mock":
        compose_frame(alley(7), portrait_noir(MAG, seed=2), "VEX",
                      "Word is Saeder-Krupp moved the prototype to the downtown gallery. Security's light tonight. You want the job, or should I find someone steadier?",
                      ["Take the job", "Ask about pay", "Walk away"],
                      sys.argv[2] if len(sys.argv) > 2 else "/tmp/vn_frame.jpg")
    elif mode == "room":
        room(int(sys.argv[2]) if len(sys.argv) > 2 else 5).save(sys.argv[3] if len(sys.argv) > 3 else "/tmp/paint_room.jpg", quality=88)
        print("saved room")
    else:
        alley(int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 7).save(
            sys.argv[2] if len(sys.argv) > 2 else "/tmp/paint_alley.jpg", quality=88); print("saved")
