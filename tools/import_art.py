#!/usr/bin/env python3
"""
Import AI-generated (or any) art into VoidRunner's VN asset slots.

Takes an arbitrary image, center-crops it to the slot's aspect ratio, resizes to
the exact pixel size the firmware decodes, and writes it as JPEG into
main/assets/vn/. Scene slots are 1280x720 (16:9); portrait slots 192x240 (4:5).

Usage:
  python3 tools/import_art.py <slot> <source_image>
      e.g. python3 tools/import_art.py scn_street ~/Downloads/alley.png
  python3 tools/import_art.py --batch <dir>
      processes <dir>/<slot>.*  for every known slot it finds
  python3 tools/import_art.py --list        # show the slots and their specs
"""
import os
import sys
from PIL import Image, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main", "assets", "vn")

# slot -> (width, height, jpeg_quality)
SCENE = (1280, 720, 86)
PORT = (192, 240, 92)
SLOTS = {
    "scn_street":  (SCENE, "Rain-soaked neon alley (prologue establishing shot)"),
    "scn_office":  (SCENE, "Fixer's dim office with a rainy city window"),
    "scn_gallery": (SCENE, "Upscale gallery / corp tower exterior at night"),
    "scn_vault":   (SCENE, "High-security gallery vault interior"),
    "por_vex":     (PORT,  "Vex — the fixer (magenta key light)"),
    "por_fixer":   (PORT,  "Mr. Johnson — corporate suit (amber light)"),
    "por_guard":   (PORT,  "Security guard (cyan rim light)"),
}

def condition(src, w, h, q, dst):
    im = Image.open(src).convert("RGB")
    sw, sh = im.size
    # center-crop to target aspect
    tar = w / h
    if sw / sh > tar:
        nw = int(sh * tar); im = im.crop(((sw - nw) // 2, 0, (sw - nw) // 2 + nw, sh))
    else:
        nh = int(sw / tar); im = im.crop((0, (sh - nh) // 2, sw, (sh - nh) // 2 + nh))
    im = im.resize((w, h), Image.LANCZOS)
    if (w, h) != SCENE[:2]:                 # gently sharpen small portraits
        im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=2))
    os.makedirs(OUT, exist_ok=True)
    im.save(dst, quality=q)
    print(f"  {os.path.basename(src)} -> {os.path.relpath(dst)}  ({w}x{h}, {os.path.getsize(dst)//1024} KiB)")

def do_slot(slot, src):
    if slot not in SLOTS:
        print(f"unknown slot '{slot}'. Known: {', '.join(SLOTS)}"); return False
    (w, h, q), _ = SLOTS[slot]
    condition(src, w, h, q, os.path.join(OUT, slot + ".jpg")); return True

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        print("VoidRunner art slots:")
        for s, ((w, h, q), desc) in SLOTS.items():
            print(f"  {s:12} {w}x{h:<4}  {desc}")
    elif sys.argv[1] == "--batch":
        d = sys.argv[2]
        found = 0
        for slot in SLOTS:
            for f in os.listdir(d):
                if os.path.splitext(f)[0] == slot:
                    do_slot(slot, os.path.join(d, f)); found += 1; break
        print(f"imported {found} image(s)")
    else:
        do_slot(sys.argv[1], sys.argv[2])
