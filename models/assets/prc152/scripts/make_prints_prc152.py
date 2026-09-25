"""Prints for the 10000 m radio: brand, captions, keypad, LCD, numbers on the knob, sticker and plate.

    python make_prints_prc152.py          (system Python with Pillow)
"""
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "_kit")))
import layout_prc152 as L  # noqa: E402
import texkit as T  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "textures"))
WHITE = (226, 228, 220, 255)
KEYINK = (238, 238, 232, 255)


def front():
    cv = T.Canvas(*L.FRONT_RECT, ppm=L.PPM)
    bx, bz = L.BRAND_POS
    # brand on the army radio in a single color, from the left edge of the face
    T.brand(cv, bx - 0.0110, bz, 0.0030, WHITE, anchor="l")
    wx, wz = L.WIDEBAND_POS
    cv.text("WIDEBAND NETWORKING", wx, wz, 0.0020, "din", WHITE, spacing=0.00012)
    # keypad: large digit/word, small letters on the right, function label below
    for row, z in zip(L.KEYS, L.KEY_ROWS):
        for key, x in zip(row, L.KEY_COLS):
            if key is None:
                continue
            main, letters, fn = key
            if main in ("<", ">"):
                sgn = -1 if main == "<" else 1
                cv.poly([(x + sgn * 0.0018, z), (x - sgn * 0.0010, z + 0.0018), (x - sgn * 0.0010, z - 0.0018)], KEYINK)
                continue
            if main in ("CLR", "ENT"):
                cv.text(main, x, z, 0.0020, "ocr", KEYINK)
                continue
            dz = 0.0012 if fn else 0.0
            cv.text(main, x - 0.0016, z + dz, 0.0026, "ocr", KEYINK)
            if letters:
                cv.text(letters, x + 0.0019, z + dz + 0.0003, 0.0011, "ocr", KEYINK)
            if fn == "lamp":
                cv.poly([(x - 0.0022, z - 0.0026), (x + 0.0022, z - 0.0026), (x, z - 0.0006)], KEYINK)
            elif fn == "loop":
                cv.ellipse(x + 0.0010, z - 0.0006, 0.0015, 0.0015, outline=KEYINK, width=0.0003)
            elif fn:
                cv.text(fn, x, z - 0.0020, 0.0011, "ocr", KEYINK)
    p = L.PRE
    zc = (p["z0"] + p["z1"]) / 2
    cv.text("+", p["x"], p["z1"] - 0.0030, 0.0032, "ocr", KEYINK)
    cv.text("PRE", p["x"], zc, 0.0020, "ocr", KEYINK)
    cv.text("-", p["x"], p["z0"] + 0.0030, 0.0032, "ocr", KEYINK)
    px, pz = L.PRODUCT_POS
    cv.text(L.PRODUCT, px, pz, 0.0034, "verdana_b", WHITE, spacing=0.0002)
    img = T.wear_print(cv.img, amount=0.30, seed=61, cell=140, scratches=70)
    img.save(os.path.join(OUT, "print_front.png"))
    print("wrote print_front.png", img.size)


def knob():
    """Numbers on the side of the knob: the half of the cylinder visible from the front, stepped by angle, compressed toward the edges."""
    cv = T.Canvas(*L.KNOB_RECT, ppm=L.PPM)
    k = L.KNOB
    zt = L.H + k["h"] * 0.62
    n = len(L.KNOB_MARKS)
    for i, s in enumerate(L.KNOB_MARKS):
        ang = math.radians(-66 + 132 * i / (n - 1))
        x = k["x"] + k["r"] * math.sin(ang)
        layer = T.Canvas(*L.KNOB_RECT, ppm=L.PPM)
        layer.text(s, x, zt, 0.0016, "din", WHITE)
        sq = max(0.35, math.cos(ang))
        cx, _ = layer.px(x, zt)
        img = layer.img.transform(layer.img.size, Image.AFFINE, (1 / sq, 0, cx - cx / sq, 0, 1, 0),
                                  resample=Image.BICUBIC)
        cv.img.alpha_composite(img)
    cv.d = ImageDraw.Draw(cv.img)
    cv.line([(k["x"], L.H + k["h"] * 0.20), (k["x"], L.H + k["h"] * 0.38)], WHITE, 0.0006)
    cv.save(os.path.join(OUT, "print_knob.png"))


def lcd():
    bg, cv = T.lcd_canvas(L.LCD_RECT, L.PPM, (74, 92, 50), (46, 58, 30), vignette=0.55, blur=40)
    x0, x1, z0, z1 = L.LCD_RECT
    ghost = (24, 32, 12, 15)
    rows = ("R  BAT ####  VULOS  TON ------ PT", "01-FSKVCECT01", "LOS  VOC -----  CVSD --",
            "TYPE  TRF  DATA  VOICE  KEY")
    for i, s in enumerate(rows):
        cv.text(s, x0 + 0.0015, z1 - 0.0022 - i * 0.0038, 0.0019 if i in (1, 2) else 0.0013, "ocr", ghost,
                anchor="lm")
    T.noise_speckle(cv, 120, (110, 130, 80, 80), (1, 4), seed=15)
    T.lcd_finish(bg, cv, os.path.join(OUT, "lcd.png"))


def back():
    """Nomenclature plate on the back (like on army equipment) and the battery sticker."""
    cv = T.Canvas(*L.BACK_RECT, ppm=L.PPM)
    p = L.PLATE
    ink = (28, 30, 24, 255)
    zc = p["z1"] - 0.004
    lines = [("RADIO SET  " + L.NOMEN, 0.0021), ("RT-1943A/U", 0.0018), ("NSN 5820-01-555-0152", 0.0016),
             ("CONTRACT DAAB07-04-D-B0XX", 0.0014), ("SER NO  15A 040127", 0.0016), ("MFR 0X9K7", 0.0014),
             ("U.S.", 0.0026)]
    for s, hh in lines:
        cv.text(s, 0.0, zc, hh, "din", ink)
        zc -= hh + 0.0024
    # battery: a black stripe with white text
    b = L.BAT_LABEL
    cv.rect(b["x0"], b["z0"], b["x1"], b["z1"], fill=(26, 28, 24, 255), r=0.0012)
    wink = (205, 206, 198, 255)
    zc = b["z1"] - 0.0045
    for s, hh in (("BATTERY, RECHARGEABLE", 0.0019), ("BB-2590/U  Li-ION  12 VDC", 0.0019),
                  ("DANGER: DO NOT HEAT, CRUSH,", 0.0014), ("DISASSEMBLE, SHORT CIRCUIT", 0.0014),
                  ("OR INCINERATE", 0.0014)):
        cv.text(s, 0.0, zc, hh, "din", wink)
        zc -= hh + 0.0026
    img = T.wear_print(cv.img, amount=0.2, seed=8, cell=110, scratches=30)
    img.save(os.path.join(OUT, "print_back.png"))
    print("wrote print_back.png", img.size)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    front()
    knob()
    lcd()
    back()
