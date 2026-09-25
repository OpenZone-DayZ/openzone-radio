"""Prints for the 50..250 m radio: button captions, cracked LCD, back label, range bands.

    python make_prints_t388.py          (system Python with Pillow)
"""
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "_kit")))
import layout_t388 as L  # noqa: E402
import texkit as T  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "textures"))
LIGHT = (205, 205, 198, 255)
DARKINK = (30, 30, 32, 255)


def power_icon(cv, x, z, s, fill):
    cv.ellipse(x, z, s * 0.42, s * 0.42, outline=fill, width=s * 0.13)
    cv.rect(x - s * 0.16, z, x + s * 0.16, z + s * 0.55, fill=(0, 0, 0, 0))
    cv.rect(x - s * 0.06, z + s * 0.02, x + s * 0.06, z + s * 0.52, fill=fill)


def front():
    """Button captions get their own layer with light wear: the shield's overall wear was eating
    whole letters (the L in CALL, the T in TALK, the N in MON), so on the buttons they read as clipped. In the reference they are intact."""
    keys = T.Canvas(*L.FRONT_RECT, ppm=L.PPM)
    for x, z, rx, rz, mat, txt in L.BUTTONS:
        if txt == "pwr":
            power_icon(keys, x, z, rx * 1.4, (235, 225, 225, 230))
        elif txt in ("^", "v"):
            keys.tri(x, z, rz * 1.1, up=txt == "^", fill=LIGHT)
        elif txt == "TALK":
            keys.text(txt, x, z, 0.0019, "arial_b", (150, 150, 146, 255))
        elif mat in ("btn_blue",):
            keys.text(txt, x, z, 0.0009, "arial_b", LIGHT)
        elif rx == rz:                      # round SCAN / MENU: the label spans the whole button but not the bevel
            keys.text(txt, x, z, 0.00105, "arial_b", LIGHT)
        else:
            keys.text(txt, x, z, min(0.0019, rz * 0.62), "arial_b", LIGHT)
    face = T.Canvas(*L.FRONT_RECT, ppm=L.PPM)
    # model name on the shield - in the strip between the brand and the LCD (position specified by
    # the owner on 25.09); in black: grey on the grey shield wasn't legible
    # brand on the shield above the LCD - its own layer: the shield's wear (0.40) would eat it almost entirely
    brand = T.Canvas(*L.FRONT_RECT, ppm=L.PPM)
    T.brand(brand, 0.0, L.BRAND_Z, 0.0021, DARKINK, T.BRAND_ACCENT)
    brand.text(" ".join(L.MODEL), 0.0, L.MODEL_Z, 0.0019, "arial", (10, 10, 12, 255), fit=0.0170)
    img = T.wear_print(face.img, amount=0.40, seed=31, cell=110, scratches=80)
    img.alpha_composite(T.wear_print(brand.img, amount=0.22, seed=13, cell=80, scratches=30))
    img.alpha_composite(T.wear_print(keys.img, amount=0.10, seed=12, cell=60, scratches=25))
    img.save(os.path.join(OUT, "print_front.png"))
    print("wrote print_front.png", img.size)


def lcd():
    """Powered-off LCD with a crack in the glass on the left, grime in the corners."""
    bg, cv = T.lcd_canvas(L.LCD_RECT, L.PPM, (108, 114, 104), (64, 66, 58), vignette=0.55, blur=30)
    x0, x1, z0, z1 = L.LCD_RECT
    ghost = (40, 44, 38, 34)
    T.seg7_text(cv, "88", x0 + (x1 - x0) * 0.30, z0 + (z1 - z0) * 0.22, (z1 - z0) * 0.50, on=ghost, ghost=ghost)
    T.seg7_text(cv, "88", x0 + (x1 - x0) * 0.72, z0 + (z1 - z0) * 0.22, (z1 - z0) * 0.26, on=ghost, ghost=ghost)
    # crack: jagged rays from the point of impact
    rng = random.Random(8)
    cx, cz = x0 + (x1 - x0) * 0.14, z0 + (z1 - z0) * 0.62
    for k in range(7):
        ang = rng.uniform(0, 2 * math.pi)
        pts = [(cx, cz)]
        ln = rng.uniform(0.003, 0.009)
        for s in range(1, 5):
            ang += rng.uniform(-0.35, 0.35)
            d = ln * s / 4
            pts.append((cx + math.cos(ang) * d, cz + math.sin(ang) * d))
        cv.line(pts, (20, 22, 20, 120), 0.00016)
        cv.line(pts, (210, 214, 205, 200), 0.00008)
    T.noise_speckle(cv, 160, (70, 60, 44, 120), (1, 5), seed=10)
    T.lcd_finish(bg, cv, os.path.join(OUT, "lcd.png"), blur=0.7)


def back():
    cv = T.Canvas(*L.BACK_RECT, ppm=L.PPM)
    d = L.DOOR
    zc = (d["z0"] + d["z1"]) / 2
    ink = (170, 170, 165, 255)
    cv.text("OPEN", 0.0, d["z0"] + 0.0045, 0.0018, "arial_b", ink)
    cv.tri(0.0, d["z0"] + 0.0020, 0.0022, up=False, fill=ink)
    cv.text("3 x AAA  1.5V", 0.0, zc + 0.006, 0.0022, "arial_b", ink)
    for i, dx in enumerate((-0.012, 0.0, 0.012)):      # batteries: outlines with polarity marks
        cv.rect(dx - 0.0045, zc - 0.012, dx + 0.0045, zc + 0.002, outline=ink, width=0.00025, r=0.001)
        cv.text("+" if i % 2 == 0 else "-", dx, zc - 0.001, 0.0022, "arial_b", ink)
        cv.text("-" if i % 2 == 0 else "+", dx, zc - 0.010, 0.0022, "arial_b", ink)
    # on the door, under the clip: the body seam now runs above the door
    cv.text("PMR446  8 CH  0.5W", 0.0, zc + 0.0115, 0.0015, "arial_b", ink)
    img = T.wear_print(cv.img, amount=0.5, seed=5, cell=100, scratches=90)
    img.save(os.path.join(OUT, "print_back.png"))
    print("wrote print_back.png", img.size)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    front()
    lcd()
    back()
