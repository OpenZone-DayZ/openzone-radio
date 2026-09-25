"""Печать рации на 5000 м: логотип и марка, клавиатура, джойстик, ЖКИ, метки ручек, наклейка, лента.

    python make_prints_xts.py          (системный Python с Pillow)
"""
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "_kit")))
import layout_xts as L  # noqa: E402
import texkit as T  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "textures"))
WHITE = (232, 232, 230, 255)
PURPLE = (120, 110, 210, 255)
LETTERS = (150, 200, 160, 255)
DARK = (26, 26, 28, 255)


def front():
    cv = T.Canvas(*L.FRONT_RECT, ppm=L.PPM)
    g = L.LOGO
    T.brand(cv, 0.0, g["z"] + 0.0010, 0.0026, WHITE, T.BRAND_ACCENT)
    cv.text(L.MODEL, 0.0115, g["z"] - 0.0034, 0.0020, "din", PURPLE)
    # точки на программируемых клавишах
    for i, (x, z) in enumerate(L.SOFTKEYS):
        for k in range(i + 1):
            cv.ellipse(x + (k - i / 2) * 0.0012, z, 0.00038, 0.00038, fill=(150, 140, 220, 255))
    n = L.NAV
    cv.tri(n["x"], n["z"] + n["rz"] * 0.62, 0.0022, up=True, fill=DARK)
    cv.tri(n["x"], n["z"] - n["rz"] * 0.62, 0.0022, up=False, fill=DARK)
    cv.poly([(n["x"] - n["rx"] * 0.80, n["z"]), (n["x"] - n["rx"] * 0.62, n["z"] + 0.0010),
             (n["x"] - n["rx"] * 0.62, n["z"] - 0.0010)], DARK)
    cv.poly([(n["x"] + n["rx"] * 0.80, n["z"]), (n["x"] + n["rx"] * 0.62, n["z"] + 0.0010),
             (n["x"] + n["rx"] * 0.62, n["z"] - 0.0010)], DARK)
    x, z = L.NAV_SIDE[0]
    cv.text("*", x, z - 0.0004, 0.0030, "arial_b", (230, 200, 90, 255))
    x, z = L.NAV_SIDE[1]
    cv.line([(x + 0.0010, z + 0.0012), (x + 0.0010, z - 0.0004), (x - 0.0010, z - 0.0004)], WHITE, 0.0003)
    cv.tri(x - 0.0011, z - 0.0004, 0.0011, up=True, fill=WHITE)
    for row, z in zip(L.KEYS, L.KEY_ROWS):
        for (main, sub), x in zip(row, L.KEY_COLS):
            if sub:
                cv.text(main, x - 0.0019, z, 0.0023, "din", WHITE)
                cv.text(sub, x + 0.0017, z - 0.0001, 0.0011, "din", LETTERS)
            else:
                cv.text(main, x, z - (0.0005 if main == "*" else 0.0), 0.0024 if main != "*" else 0.0032, "din", WHITE)
    img = T.wear_print(cv.img, amount=0.20, seed=51, cell=140)
    img.save(os.path.join(OUT, "print_front.png"))
    print("wrote print_front.png", img.size)


def top():
    """Метки на торцах ручек и подписи тумблера (смотрим сверху, перед внизу)."""
    cv = T.Canvas(*L.TOP_RECT, ppm=L.PPM)
    v, c = L.VOL, L.CHAN
    cv.line([(v["x"], -v["y"] + 0.0010), (v["x"], -v["y"] + v["r"] * 0.9)], WHITE, 0.0007)
    cv.line([(c["x"], -c["y"] + 0.0009), (c["x"], -c["y"] + c["grip_w"] * 0.45)], WHITE, 0.0008)
    t = L.TOGGLE
    cv.text("A", t["x"] - 0.0028, -t["y"], 0.0014, "din", (190, 190, 186, 255))
    cv.text("B", t["x"] + 0.0028, -t["y"], 0.0014, "din", (190, 190, 186, 255))
    cv.save(os.path.join(OUT, "print_top.png"))


def lcd():
    """Выключенный точечный ЖКИ: надписи не светятся, лишь чуть темнее поля."""
    bg, cv = T.lcd_canvas(L.LCD_RECT, L.PPM, (92, 108, 56), (60, 72, 36), vignette=0.55, blur=40)
    x0, x1, z0, z1 = L.LCD_RECT
    ghost = (30, 40, 18, 15)
    for i, s in enumerate(("ZONE 1", "CH 01  TAC", "", "SCAN  PHON  ZONE")):
        if s:
            cv.text(s, x0 + (x1 - x0) * 0.5, z1 - 0.0028 - i * 0.0042, 0.0023 if i < 2 else 0.0016, "din", ghost)
    T.noise_speckle(cv, 90, (130, 150, 90, 80), (1, 4), seed=14)
    T.lcd_finish(bg, cv, os.path.join(OUT, "lcd.png"))


def back():
    cv = T.Canvas(*L.BACK_RECT, ppm=L.PPM)
    x0, x1, z0, z1 = -0.0225, 0.0225, 0.0100, 0.0480
    cv.rect(x0, z0, x1, z1, fill=(44, 44, 46, 255), r=0.0015)
    ink = (196, 196, 192, 255)
    T.brand(cv, 0.0, z1 - 0.0035, 0.0022, ink)
    lines = ("IMPACT-RESISTANT BATTERY  NNTN-5X", "Li-ion  7.5V  2500mAh", "FOR OZ-COM RADIOS ONLY",
             "CAUTION: RISK OF FIRE IF REPLACED BY WRONG TYPE", "MADE IN MALAYSIA")
    for i, s in enumerate(lines):
        cv.text(s, 0.0, z1 - 0.0085 - i * 0.0042, 0.0012, "narrow", ink)
    rng = random.Random(9)
    x = -0.0160
    while x < 0.0:
        wbar = rng.choice((0.0002, 0.00032, 0.00048))
        cv.rect(x, z0 + 0.0015, x + wbar, z0 + 0.0050, fill=ink)
        x += wbar + rng.choice((0.0002, 0.0003))
    img = T.wear_print(cv.img, amount=0.3, seed=7, cell=110, scratches=50)
    img.save(os.path.join(OUT, "print_back.png"))
    print("wrote print_back.png", img.size)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    front()
    top()
    lcd()
    back()
