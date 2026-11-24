import os
os.makedirs("main/assets", exist_ok=True)
def rgb565(r, g, b): return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
PAL = {".":0x0000,"K":rgb565(12,14,22),"D":rgb565(28,34,52),"M":rgb565(52,62,88),"L":rgb565(96,112,148),"W":rgb565(225,235,248),"C":rgb565(0,240,255),"P":rgb565(255,42,165),"G":rgb565(40,235,120),"A":rgb565(255,185,40),"R":rgb565(235,48,68),"S":rgb565(218,168,132),"B":rgb565(88,56,42)}
def make_iso_tile(v):
    w,h=64,32; px=[0]*(w*h)
    for y in range(h):
        for x in range(w):
            dx,dy=abs(x-31.5)/32.0,abs(y-15.5)/16.0
            if dx+dy<=1.0:
                edge=dx+dy>0.92
                if v==0:
                    c=PAL["K"] if edge else PAL["D"]
                    if not edge and (x*7+y*13)%29==0: c=PAL["M"]
                    if not edge and 22<=x<=40 and 12<=y<=19 and (x+y)%3==0: c=PAL["P"] if x%2==0 else PAL["C"]
                elif v==1:
                    c=PAL["K"] if edge else (PAL["L"] if dx+dy>0.84 else PAL["M"])
                    if not edge and (x%16==0 or y%8==0): c=PAL["D"]
                else:
                    c=PAL["C"] if edge else PAL["K"]
                    if not edge and (x%8==0 or y%4==0): c=PAL["P"]
                px[y*w+x]=c
    return px
def make_sprite(j=False):
    w,h=32,48; px=[0]*(w*h); coat="K" if j else "M"; trim="A" if j else "C"; hair="L" if j else "B"
    for y in range(4,46):
        for x in range(8,24):
            c="."
            if 6<=y<=14 and 12<=x<=19: c=hair if y<=8 else ("C" if y==10 and not j else "S")
            elif 15<=y<=33 and 10<=x<=21:
                c="W" if j and 15<=y<=22 and 14<=x<=17 else coat
                if x in (10,21): c=trim
            elif 34<=y<=44 and (11<=x<=14 or 17<=x<=20): c="K" if y>=41 else "D"
            if c!=".": px[y*w+x]=PAL[c]
    return px
def make_portrait(j=False):
    w,h=96,96; px=[0]*(w*h); bg1=PAL["P"] if not j else PAL["A"]; bg2=PAL["D"]
    for y in range(h):
        for x in range(w):
            if x<3 or x>=w-3 or y<3 or y>=h-3: px[y*w+x]=PAL["C"] if not j else PAL["A"]; continue
            bayer=((x&1)<<1)|(y&1); c=bg1 if (y*4)//h > bayer+1 else bg2
            dx,dy=(x-48)/22.0,(y-36)/26.0
            if dx*dx+dy*dy<1.0:
                c=PAL["S"]
                if y<24: c=PAL["L"] if j else PAL["B"]
                if 32<=y<=36 and 34<=x<=62 and not j: c=PAL["C"]
                if 33<=y<=36 and (37<=x<=43 or 53<=x<=59) and j: c=PAL["K"]
            elif y>58 and abs(x-48)<34:
                c=PAL["K"] if j else PAL["M"]
                if j and abs(x-48)<8: c=PAL["W"] if abs(x-48)>2 else PAL["R"]
            px[y*w+x]=c
    return px
def dump(f,name,arr):
    f.write(f"const uint16_t {name}[{len(arr)}] = {{\n")
    for i in range(0,len(arr),16): f.write("    "+", ".join(f"0x{v:04X}" for v in arr[i:i+16])+",\n")
    f.write("};\n\n")
with open("main/assets/vr_assets.h","w") as hf:
    hf.write("#pragma once\n#include <stdint.h>\nextern const uint16_t vr_tile_asphalt[64*32],vr_tile_sidewalk[64*32],vr_tile_jackpoint[64*32],vr_sprite_runner[32*48],vr_sprite_johnson[32*48],vr_portrait_runner[96*96],vr_portrait_johnson[96*96];\n")
with open("main/assets/vr_assets.c","w") as cf:
    cf.write("#include \"vr_assets.h\"\n\n")
    for n,a in [("vr_tile_asphalt",make_iso_tile(0)),("vr_tile_sidewalk",make_iso_tile(1)),("vr_tile_jackpoint",make_iso_tile(2)),("vr_sprite_runner",make_sprite(False)),("vr_sprite_johnson",make_sprite(True)),("vr_portrait_runner",make_portrait(False)),("vr_portrait_johnson",make_portrait(True))]: dump(cf,n,a)
print("ASSETS GENERATED")
