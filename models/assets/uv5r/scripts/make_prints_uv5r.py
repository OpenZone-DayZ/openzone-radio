"""Print set for the 1000 m radio: face labels, LCD indicator, side, battery sticker, range strip.

    python make_prints_uv5r.py          (system Python with Pillow)

Everything is drawn from the numbers in layout_uv5r.py, so the labels land on the buttons without adjustment.
Result - ../textures/*.png; build_uv5r.py projects them onto the detailed model.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "_kit")))
import layout_uv5r as L  # noqa: E402
import texkit as T  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "textures"))
WHITE = (232, 233, 226, 255)
BLUE = (88, 150, 222, 255)
BLACK = (14, 14, 16, 255)


def key_icon(cv, x, z, s, fill):
    """Key icon (keyboard lock) next to '#'."""
    cv.ellipse(x - s * 0.35, z, s * 0.28, s * 0.28, outline=fill, width=s * 0.12)
    cv.line([(x - s * 0.08, z), (x + s * 0.55, z)], fill, s * 0.12)
    cv.line([(x + s * 0.40, z), (x + s * 0.40, z - s * 0.22)], fill, s * 0.1)
    cv.line([(x + s * 0.55, z), (x + s * 0.55, z - s * 0.22)], fill, s * 0.1)


def front():
    cv = T.Canvas(*L.FRONT_RECT, ppm=L.PPM)
    # front panel buttons
    for x, z, w, h, r, mat, txt in L.BUTTONS:
        cv.text(txt, x, z, h * (0.36 if len(txt) > 3 else 0.42), "din", WHITE)
    # model name - on the bottom plate; the brand - a separate print on the body (brand())
    mx, mz, mw, mh, _ = L.MODEL_PLATE
    cv.text(L.MODEL, mx, mz, mh * 0.50, "din", WHITE, fit=mw - 0.0024)
    # keys
    for row, z in zip(L.KEYS, L.KEY_ROWS):
        for (main, sub), x in zip(row, L.KEY_COLS):
            if main in ("^", "v"):
                cv.tri(x, z, 0.0026, up=main == "^", fill=WHITE)
            elif not sub:
                cv.text(main, x, z, 0.00135, "din", WHITE)
            else:
                cv.text(main, x - 0.0018, z, 0.0021 if main not in "*#" else 0.0024, "din", WHITE)
                if sub == "key":
                    key_icon(cv, x + 0.0016, z, 0.0028, BLUE)
                else:
                    cv.text(sub, x + 0.0015, z - 0.0001, 0.00085, "din", BLUE)
    # wear: digits 1..5 and the PTT zone rub more - a shared layer of worn patches
    img = T.wear_print(cv.img, amount=0.22, seed=11, cell=140)
    img.save(os.path.join(OUT, "print_front.png"))
    print("wrote print_front.png", img.size)


def brand():
    """Brand right on the body, like the other models: the body has no print of its own, hence a separate layer."""
    cv = T.Canvas(*L.FRONT_RECT, ppm=L.PPM)
    bx, bz, bw, bh, _ = L.BRAND_PLATE
    T.brand(cv, bx, bz, 0.0026, WHITE, T.BRAND_ACCENT)
    img = T.wear_print(cv.img, amount=0.25, seed=17, cell=120, scratches=30)
    img.save(os.path.join(OUT, "print_brand.png"))
    print("wrote print_brand.png", img.size)


def lcd():
    """Powered-off LCD: a grey-green field, barely visible DARK dead segments, dust specks."""
    bg, cv = T.lcd_canvas(L.LCD_RECT, L.PPM, (104, 114, 100), (70, 78, 68), vignette=0.35, blur=40)
    x0, x1, z0, z1 = L.LCD_RECT
    ghost = (40, 46, 40, 34)
    dh = (z1 - z0) * 0.30
    for zz in (z0 + (z1 - z0) * 0.55, z0 + (z1 - z0) * 0.12):
        T.seg7_text(cv, "888.888", x0 + (x1 - x0) * 0.22, zz, dh, on=ghost, ghost=ghost)
    cv.rect(x1 - 0.0062, z1 - 0.0030, x1 - 0.0022, z1 - 0.0012, outline=ghost, width=0.00022)
    for i in range(4):
        cv.rect(x0 + 0.0022 + i * 0.0011, z1 - 0.0034, x0 + 0.0029 + i * 0.0011, z1 - 0.0034 + 0.0005 * (i + 1),
                fill=ghost)
    for txt, fx in (("DW", 0.30), ("R", 0.45), ("CT", 0.55), ("+-", 0.66), ("N", 0.78)):
        cv.text(txt, x0 + (x1 - x0) * fx, z1 - 0.0021, 0.0011, "din", ghost)
    T.noise_speckle(cv, 90, (150, 156, 140, 90), (1, 4), seed=4)
    T.lcd_finish(bg, cv, os.path.join(OUT, "lcd.png"))


def left_side():
    cv = T.Canvas(*L.LEFT_RECT, ppm=L.PPM)
    yc, z0, z1, wy, _ = L.PTT
    cv.text("PTT", -yc, (z0 + z1) / 2, 0.0024, "din", (58, 58, 60, 210), rot=90)
    yc, z0, z1, wy, _ = L.MONI
    cv.text("MONI", -yc, (z0 + z1) / 2, 0.0015, "din", (58, 58, 60, 210), rot=90)
    yc, z0, z1, wy, _ = L.CALL
    cv.text("CALL", -yc, (z0 + z1) / 2, 0.0015, "din", (58, 58, 60, 210), rot=90)
    cv.save(os.path.join(OUT, "print_left.png"))


def back():
    """Battery sticker: a silvery film with dark print; the top goes under the clip."""
    cv = T.Canvas(*L.BACK_RECT, ppm=L.PPM)
    x0, x1, z0, z1 = -0.0235, 0.0235, 0.0030, 0.0520
    cv.rect(x0, z0, x1, z1, fill=(150, 152, 150, 255), r=0.0015)
    cv.rect(x0 + 0.0008, z0 + 0.0008, x1 - 0.0008, z1 - 0.0008, outline=(40, 40, 42, 255), width=0.00025, r=0.001)
    ink = (34, 34, 38, 255)
    T.brand(cv, 0.0, 0.0470, 0.0023, ink)
    cv.text("Li-ion BATTERY PACK  BL-5X", 0.0, 0.0420, 0.0014, "din", ink)
    cv.text("7.4V  1800mAh  13.32Wh", 0.0, 0.0385, 0.0017, "din", ink)
    for i, line in enumerate(("WARNING: DO NOT SHORT CIRCUIT, DISASSEMBLE",
                              "OR DISPOSE OF IN FIRE. CHARGE ONLY WITH",
                              "SPECIFIED CHARGER. KEEP AWAY FROM WATER.")):
        cv.text(line, 0.0, 0.0330 - i * 0.0019, 0.00095, "narrow", ink)
    # barcode and recycling icons at the bottom - visible from under the clip
    import random
    rng = random.Random(7)
    x = -0.0190
    while x < -0.0010:
        wbar = rng.choice((0.00018, 0.00030, 0.00045))
        cv.rect(x, 0.0055, x + wbar, 0.0125, fill=ink)
        x += wbar + rng.choice((0.00018, 0.00030))
    cv.text("6 942053 110372", -0.0100, 0.0043, 0.0009, "din", ink)
    cv.rect(0.0030, 0.0050, 0.0080, 0.0110, outline=ink, width=0.0003)
    cv.text("CE", 0.0055, 0.0080, 0.0030, "arial_b", ink)
    cv.ellipse(0.0130, 0.0080, 0.0028, 0.0028, outline=ink, width=0.0003)
    cv.text("Li", 0.0130, 0.0080, 0.0020, "arial_b", ink)
    cv.text("MADE IN CHINA", 0.0120, 0.0040, 0.0009, "din", ink)
    img = T.wear_print(cv.img, amount=0.18, seed=3, cell=120, scratches=25)
    img.save(os.path.join(OUT, "print_back.png"))
    print("wrote print_back.png", img.size)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    front()
    brand()
    lcd()
    left_side()
    back()
