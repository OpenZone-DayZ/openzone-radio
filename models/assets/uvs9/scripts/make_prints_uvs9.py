"""Print set for the 2000 m radio: keys, brand, LCD, headset jack cover icons, PTT, back sticker, strip.

    python make_prints_uvs9.py          (system Python with Pillow)
"""
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "_kit")))
import layout_uvs9 as L  # noqa: E402
import texkit as T  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "textures"))
WHITE = (234, 232, 222, 255)
INK = (40, 38, 34, 255)


def key_icon(cv, x, z, s, fill):
    cv.ellipse(x - s * 0.35, z, s * 0.28, s * 0.28, outline=fill, width=s * 0.13)
    cv.line([(x - s * 0.08, z), (x + s * 0.55, z)], fill, s * 0.13)
    cv.line([(x + s * 0.42, z), (x + s * 0.42, z - s * 0.24)], fill, s * 0.11)


def front():
    cv = T.Canvas(*L.FRONT_RECT, ppm=L.PPM)
    for row, z in zip(L.KEYS, L.KEY_ROWS):
        for (main, sub), x in zip(row, L.KEY_COLS):
            if main in ("^", "v"):
                cv.tri(x, z, 0.0034, up=main == "^", fill=WHITE)
            elif not sub:
                cv.text(main, x, z, 0.0017, "din", WHITE)
            else:
                cv.text(main, x - 0.0020, z + 0.0002, 0.0027 if main not in "*#" else 0.0030, "din", WHITE)
                if sub == "key":
                    key_icon(cv, x + 0.0018, z - 0.0004, 0.0034, WHITE)
                else:
                    cv.text(sub, x + 0.0019, z - 0.0007, 0.0012, "din", WHITE)
    b = L.BRAND_LINE
    T.brand(cv, b["x"] - 0.0010, b["z"], 0.0029, WHITE, T.BRAND_ACCENT)
    x, z, w, h = L.BAND_BTN
    cv.text("BAND", x, z, 0.0019, "din", WHITE)
    for zz, w, h, mat, txt in L.COL_BTNS:
        if "\n" in txt:
            a, c = txt.split("\n")
            cv.text(a, L.SIDE_COL_X, zz + 0.0012, 0.0015, "din", WHITE)
            cv.line([(L.SIDE_COL_X - 0.003, zz), (L.SIDE_COL_X + 0.003, zz)], WHITE, 0.0002)
            cv.text(c, L.SIDE_COL_X, zz - 0.0012, 0.0015, "din", WHITE)
        elif txt:
            cv.text(txt, L.SIDE_COL_X, zz, 0.0020, "din", WHITE)
    cv.text(L.MODEL, 0.0, 0.0028, 0.0024, "din", (205, 203, 190, 255))
    img = T.wear_print(cv.img, amount=0.25, seed=41, cell=130)
    img.save(os.path.join(OUT, "print_front.png"))
    print("wrote print_front.png", img.size)


def lcd():
    bg, cv = T.lcd_canvas(L.LCD_RECT, L.PPM, (112, 118, 92), (74, 80, 58), vignette=0.5, blur=40)
    x0, x1, z0, z1 = L.LCD_RECT
    ghost = (44, 48, 30, 34)
    for zz in (z0 + (z1 - z0) * 0.53, z0 + (z1 - z0) * 0.12):
        T.seg7_text(cv, "888.888", x0 + (x1 - x0) * 0.20, zz, (z1 - z0) * 0.32, on=ghost, ghost=ghost)
    T.noise_speckle(cv, 120, (150, 150, 120, 80), (1, 4), seed=12)
    T.lcd_finish(bg, cv, os.path.join(OUT, "lcd.png"))


def right_side():
    """Icons on the headset jack cover: microphone and headphones, in a thin light line."""
    cv = T.Canvas(*L.RIGHT_RECT, ppm=L.PPM)
    yc, z0, z1, wy, _ = L.JACK
    col = (120, 118, 110, 220)
    zm, zh = z0 + (z1 - z0) * 0.30, z0 + (z1 - z0) * 0.75
    cv.ellipse(yc, zm + 0.0012, 0.0012, 0.0020, outline=col, width=0.00028)
    cv.line([(yc - 0.0022, zm + 0.0004), (yc - 0.0022, zm - 0.0006), (yc + 0.0022, zm - 0.0006),
             (yc + 0.0022, zm + 0.0004)], col, 0.00028)
    cv.line([(yc, zm - 0.0006), (yc, zm - 0.0022)], col, 0.00028)
    cv.ellipse(yc, zh, 0.0028, 0.0028, outline=col, width=0.0003)
    cv.rect(yc - 0.0032, zh - 0.0030, yc + 0.0032, zh - 0.0002, fill=(0, 0, 0, 0))
    cv.rect(yc - 0.0031, zh - 0.0026, yc - 0.0021, zh - 0.0002, fill=col)
    cv.rect(yc + 0.0021, zh - 0.0026, yc + 0.0031, zh - 0.0002, fill=col)
    cv.save(os.path.join(OUT, "print_right.png"))


def left_side():
    cv = T.Canvas(*L.LEFT_RECT, ppm=L.PPM)
    yc, z0, z1, wy, _ = L.PTT
    cv.text("PTT", -yc, (z0 + z1) / 2, 0.0026, "din", (46, 46, 40, 220), rot=90)
    cv.save(os.path.join(OUT, "print_left.png"))


def back():
    cv = T.Canvas(*L.BACK_RECT, ppm=L.PPM)
    x0, x1, z0, z1 = -0.0230, 0.0230, 0.0040, 0.0210
    cv.rect(x0, z0, x1, z1, fill=(40, 42, 34, 255), r=0.0012)
    ink = (200, 198, 186, 255)
    T.brand(cv, 0.0, z1 - 0.0030, 0.0017, ink, suffix="BL-S9")
    for i, s in enumerate(("Li-ion  7.4V  2200mAh  16.28Wh", "DO NOT SHORT CIRCUIT OR DISPOSE IN FIRE",
                           "MADE IN CHINA")):
        cv.text(s, 0.0, z1 - 0.0068 - i * 0.0030, 0.0011, "narrow", ink)
    img = T.wear_print(cv.img, amount=0.35, seed=6, cell=110, scratches=60)
    img.save(os.path.join(OUT, "print_back.png"))
    print("wrote print_back.png", img.size)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    front()
    lcd()
    right_side()
    left_side()
    back()
