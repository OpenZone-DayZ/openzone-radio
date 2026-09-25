"""Печать рации на 500/750 м: логотип, подписи кнопок, янтарный ЖКИ, PTT, наклейка тыла, ленты.

    python make_prints_lxt.py          (системный Python с Pillow)
"""
import os
import random
import sys

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "_kit")))
import layout_lxt as L  # noqa: E402
import texkit as T  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "textures"))
WHITE = (236, 237, 232, 255)
GREY = (150, 152, 150, 255)
RED = (200, 30, 26, 255)
INK = (22, 22, 24, 255)


def lock_icon(cv, x, z, s, fill):
    cv.rect(x - s * 0.45, z - s * 0.5, x + s * 0.45, z + s * 0.05, fill=fill, r=s * 0.08)
    cv.ellipse(x, z + s * 0.12, s * 0.28, s * 0.33, outline=fill, width=s * 0.14)


def front():
    cv = T.Canvas(*L.FRONT_RECT, ppm=L.PPM)
    b = L.BEZEL
    # надпись над ЖКИ на рамке: красное начало, тёмный хвост
    zt = b["cz"] + b["h"] / 2 - 0.0026
    cv.text("MAX", -0.0046, zt, 0.0013, "verdana_b", RED)
    cv.text("-TALK", 0.0032, zt, 0.0013, "verdana_b", INK)
    for x, z, _slant, txt, sub in L.BUTTONS:
        if txt in ("^", "v"):
            cv.tri(x, z + (0.0008 if sub else 0.0), 0.0032, up=txt == "^", fill=WHITE)
            if sub:
                cv.text(sub, x, z - 0.0026, 0.0011, "arial_b", WHITE)
        elif "\n" in txt:
            a, c = txt.split("\n")
            cv.text(a, x, z + 0.0013, 0.0015, "narrow_b", WHITE)
            cv.text(c, x, z - 0.0011, 0.0015, "narrow_b", WHITE)
        else:
            dz = -0.0010 if sub else 0.0
            cv.text(txt, x, z + dz, 0.0016 if len(txt) > 3 else 0.0019, "narrow_b", WHITE)
            if sub == "lock":
                lock_icon(cv, x, z + 0.0019, 0.0022, WHITE)
    m = L.MIC
    cv.text("MIC", m["x"], m["z"] + 0.0024, 0.0009, "arial_b", GREY)
    T.brand(cv, 0.0, L.BRAND_Z, 0.0030, WHITE, T.BRAND_ACCENT)
    cv.text(L.MODEL, 0.0, 0.0072, 0.0025, "din", GREY)
    img = T.wear_print(cv.img, amount=0.18, seed=21, cell=150)
    img.save(os.path.join(OUT, "print_front.png"))
    print("wrote print_front.png", img.size)


def lcd():
    """Выключенный янтарный ЖКИ: тёплое серо-жёлтое поле, тёмные призрачные сегменты и значки."""
    bg, cv = T.lcd_canvas(L.LCD_RECT, L.PPM, (150, 132, 86), (104, 90, 58), vignette=0.45, blur=30)
    x0, x1, z0, z1 = L.LCD_RECT
    ghost = (60, 48, 20, 34)
    T.seg7_text(cv, "88", x0 + (x1 - x0) * 0.24, z0 + (z1 - z0) * 0.18, (z1 - z0) * 0.52, on=ghost, ghost=ghost)
    for txt, fx, fz in (("VOX", 0.20, 0.84), ("RX", 0.86, 0.80), ("TX", 0.86, 0.64), ("DCS CTCSS", 0.52, 0.09)):
        cv.text(txt, x0 + (x1 - x0) * fx, z0 + (z1 - z0) * fz, 0.0011, "arial_b", ghost)
    cv.rect(x0 + (x1 - x0) * 0.42, z1 - 0.0016, x0 + (x1 - x0) * 0.58, z1 - 0.0008, fill=ghost)
    T.noise_speckle(cv, 60, (190, 175, 130, 80), (1, 3), seed=9)
    T.lcd_finish(bg, cv, os.path.join(OUT, "lcd.png"))


def right_side():
    cv = T.Canvas(*L.RIGHT_RECT, ppm=L.PPM)
    yc, z0, z1, wy, _ = L.PTT
    cv.text("PTT", yc, (z0 + z1) / 2, 0.0026, "din", (70, 70, 72, 220), rot=90)
    cv.save(os.path.join(OUT, "print_right.png"))


def back():
    """Наклейка на крышке отсека: паспорт рации мелким шрифтом."""
    cv = T.Canvas(*L.BACK_RECT, ppm=L.PPM)
    x0, x1, z0, z1 = -0.0185, 0.0185, 0.012, 0.038
    cv.rect(x0, z0, x1, z1, fill=(176, 176, 170, 255), r=0.0012)
    ink = (30, 30, 34, 255)
    T.brand(cv, 0.0, z1 - 0.0035, 0.0020, ink, suffix=L.MODEL)
    lines = ("FRS/GMRS TWO-WAY RADIO  22 CH", "BATTERY PACK 3.6V Ni-MH 700mAh", "SN 60-4471902",
             "THIS DEVICE COMPLIES WITH PART 95", "MADE IN CHINA")
    for i, s in enumerate(lines):
        cv.text(s, 0.0, z1 - 0.0075 - i * 0.0036, 0.0013, "narrow", ink)
    rng = random.Random(3)
    x = x0 + 0.002
    while x < x0 + 0.014:
        wbar = rng.choice((0.0002, 0.00032, 0.00048))
        cv.rect(x, z0 + 0.0012, x + wbar, z0 + 0.0048, fill=ink)
        x += wbar + rng.choice((0.0002, 0.0003))
    img = T.wear_print(cv.img, amount=0.35, seed=4, cell=110, scratches=50)
    img.save(os.path.join(OUT, "print_back.png"))
    print("wrote print_back.png", img.size)


def antenna():
    cv = T.Canvas(*L.ANT_RECT, ppm=L.PPM)
    T.brand(cv, L.ANT["x"], L.ANT["top"] - 0.020, 0.0024, (52, 52, 54, 200), name=False)
    cv.save(os.path.join(OUT, "print_antenna.png"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    front()
    lcd()
    right_side()
    back()
    antenna()
