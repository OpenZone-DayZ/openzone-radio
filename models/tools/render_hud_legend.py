"""Frequency window legend: the faces of all radios, with color for the keys that work in the window.

    python tools/render_hud_legend.py [out.jpg] [--lang en|uk]      (system Python with Pillow)

Without --lang - English (docs/screenshots/hud_legend.en.jpg); --lang uk writes hud_legend.uk.jpg.

Draws from the same things the window is built from: the face - assets/<radio>/work/hud/face.png (written
by render_hud_faces.py and make_hud_layouts.py), keys and screen - from hud_spec.py through the same Frame
that builds the layout. Changed the key roles or the model - regenerated the window - rerun this, and the
picture matches the game again.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hud_spec as S  # noqa: E402
import make_hud_layouts as M  # noqa: E402

ARGS = sys.argv[1:]
LANG = ARGS[ARGS.index("--lang") + 1] if "--lang" in ARGS else "en"
POS = [a for i, a in enumerate(ARGS) if not a.startswith("--") and (i == 0 or ARGS[i - 1] != "--lang")]
OUT = POS[0] if POS else os.path.join(S.ROOT, "docs", "screenshots", "hud_legend.%s.jpg" % LANG)
SEG_TTF = r"D:\modding\PDrive\gui\fonts\7segment.ttf"      # the same font as gui/fonts/7segment in the game
TEXT_TTF = r"C:\Windows\Fonts\bahnschrift.ttf"
K = 1.35                                                   # scale to window pixels at 1080p

ROLE = {   # role -> (color, legend caption)
    "digit": ((79, 195, 247), "digits — type a frequency"),
    "step": ((255, 213, 79), "step: T-388, LXT — new channel at once; others — neighbour in the entry line"),
    "go": ((102, 187, 106), "tune (like TUNE in the radio mod)"),
    "back": ((239, 83, 80), "erase a digit, or exit if there is nothing to erase"),
    "close": ((186, 104, 200), "exit"),
    "dot": ((236, 236, 236), "dot (inserted automatically once the integer part cannot grow any more)"),
}


def role_of(widget):
    if widget.startswith("Btn") and widget[3:].isdigit():
        return "digit"
    return {"BtnUp": "step", "BtnDown": "step", "BtnGo": "go", "BtnBack": "back", "BtnClose": "close",
            "BtnDot": "dot"}[widget]


NOTES = {   # under the radio: name and short lines of what is where
    "pmr_t388": ("T-388 · 250 m", "arrows — channel down / up, at once", "red button — exit", "screen: big channel, small frequency"),
    "lxt": ("LXT · 500 m", "arrows — channel down / up, at once", "screen: big channel,", "small frequency"),
    "uv5r": ("UV-5R · 1 km", "MENU — tune", "EXIT — erase / exit, * — dot", "arrows — neighbouring channel"),
    "uvs9": ("UV-S9 · 2 km", "MENU — tune", "EXIT — erase / exit, * — dot", "arrows — neighbouring channel"),
    "xts": ("XTS5000 · 5 km", "right of the joystick — tune", "left — exit, # — erase / exit",
            "* — dot, joystick — neighbouring channel"),
    "prc152": ("PRC-152 · 10 km", "ENT — tune", "CLR and < — erase / exit", "> — dot, PRE +/- — neighbouring channel"),
}
ORDER = ["pmr_t388", "lxt", "uv5r", "uvs9", "xts", "prc152"]
FOOTER = "Close the window with the cross in the corner, the K key or Esc. Drag the window by the radio body."

# Translations: role captions, per-radio lines and the footer line. The reference-radio names are unchanged across languages.
TRANSLATIONS = {
    "uk": dict(
        roles={"digit": "цифри — набір частоти",
               "step": "крок: у T-388 і LXT одразу новий канал, в решти — сусідній у рядок набору",
               "go": "налаштувати (як TUNE у моді рації)",
               "back": "стерти цифру, а якщо нічого — вийти",
               "close": "вийти",
               "dot": "крапка (сама — коли ціла частина більше не може рости)"},
        notes={"pmr_t388": ("T-388 · 250 м", "стрілки — канал вниз / вгору, одразу", "червона кнопка — вийти", "екран: великий канал, дрібна частота"),
               "lxt": ("LXT · 500 м", "стрілки — канал вниз / вгору, одразу", "екран: великий канал,", "дрібна частота"),
               "uv5r": ("UV-5R · 1 км", "MENU — налаштувати", "EXIT — стерти / вийти, * — крапка", "стрілки — сусідній канал"),
               "uvs9": ("UV-S9 · 2 км", "MENU — налаштувати", "EXIT — стерти / вийти, * — крапка", "стрілки — сусідній канал"),
               "xts": ("XTS5000 · 5 км", "праворуч від джойстика — налаштувати", "ліворуч — вийти, # — стерти / вийти",
                       "* — крапка, джойстик — сусідній канал"),
               "prc152": ("PRC-152 · 10 км", "ENT — налаштувати", "CLR і < — стерти / вийти", "> — крапка, PRE +/- — сусідній канал")},
        footer="Вікно закривають хрестик у кутку, клавіша K і Esc. Вікно тягнеться мишею за корпус."),
}
if LANG in TRANSLATIONS:
    tr = TRANSLATIONS[LANG]
    ROLE = {k: (v[0], tr["roles"][k]) for k, v in ROLE.items()}
    NOTES = tr["notes"]
    FOOTER = tr["footer"]


def font(path, px):
    return ImageFont.truetype(path, max(6, int(round(px))))


def put_text(d, rect, text, fnt, fill, halign):
    x, y, w, h = rect
    if not text:
        return
    l, t, r, b = d.textbbox((0, 0), text, font=fnt)
    tw, th = r - l, b - t
    if halign == "right":
        tx = x + w - tw - l
    elif halign == "center":
        tx = x + (w - tw) / 2 - l
    else:
        tx = x - l
    d.text((tx, y + (h - th) / 2 - t), text, font=fnt, fill=fill)


def panel(radio):
    f = M.Frame(radio)
    spec = f.spec
    W, H = int(f.w * K), int(f.h * K)
    tw, th = S.TEX_W / f.t * f.s * K, S.TEX_H / f.t * f.s * K
    face = Image.open(os.path.join(S.ROOT, "assets", radio, "work", "hud", "face.png")).convert("RGBA")
    face = face.resize((int(tw), int(th)), Image.LANCZOS).crop((0, 0, W, H))
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.alpha_composite(face)

    # screen - like in the game: a segment font with unlit 888, or dot-matrix text.
    # Text is on a separate layer: ImageDraw on RGBA replaces the pixel together with the alpha, and
    # semi-transparent ghosts would punch straight through the face (the same trap the LCD had).
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ghosts = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    dg = ImageDraw.Draw(ghosts)
    lx, ly, lw, lh = [v * K for v in f.ui_rect(*S.lcd_rect(radio))]
    ink = tuple(int(c * 255) for c in spec["ink"])
    seg = spec["lcd"] == "seg"
    shown = {"LcdMain": "1", "LcdSub": "136.000"} if spec["mode"] == "step" else \
        {"LcdMain": "136.000", "LcdSub": "145.5"}
    y = ly
    for name, ghost, share, halign in M.lcd_lines(f):
        hh = lh * share
        pad = lw * 0.06
        if seg:
            fnt = font(SEG_TTF, hh * 0.95)
        else:
            fnt = font(TEXT_TTF, min(hh * 0.80, (lw - 2 * pad) / (7 * 0.60)))
        rect = (lx + pad, y, lw - 2 * pad, hh)
        put_text(dg, rect, ghost, fnt, ink + (18,), halign)
        put_text(d, rect, shown[name], fnt, ink + (235,), halign)
        y += hh
    img.alpha_composite(ghosts)
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)

    # keys: a frame in the role's color around the hit area
    for widget, x, z, w, h, rnd in S.keys(radio):
        col = ROLE[role_of(widget)][0]
        bx, by, bw, bh = [v * K for v in f.ui_rect(x - w / 2 - M.KEY_PAD, x + w / 2 + M.KEY_PAD,
                                                    z - h / 2 - M.KEY_PAD, z + h / 2 + M.KEY_PAD)]
        box = (bx, by, bx + bw, by + bh)
        if rnd:
            d.ellipse(box, outline=col + (255,), width=3)
        else:
            d.rounded_rectangle(box, radius=min(bw, bh) * 0.25, outline=col + (255,), width=3)

    # the cross in the window's corner - every radio has one
    cs = 26 * K
    x0, y0 = W - cs - 6 * K, 6 * K
    d.ellipse((x0, y0, x0 + cs, y0 + cs), fill=(26, 26, 28, 230), outline=ROLE["close"][0] + (255,), width=3)
    m = cs * 0.3
    d.line((x0 + m, y0 + m, x0 + cs - m, y0 + cs - m), fill=(235, 235, 235, 255), width=3)
    d.line((x0 + m, y0 + cs - m, x0 + cs - m, y0 + m), fill=(235, 235, 235, 255), width=3)
    return img


def main():
    panels = [panel(r) for r in ORDER]
    ph = max(p.height for p in panels)
    gap, margin = 28, 36
    title_f, note_f = font(TEXT_TTF, 30), font(TEXT_TTF, 19)
    legend_f = font(TEXT_TTF, 20)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    colw = [max(p.width, max(probe.textlength(t, font=note_f) for t in NOTES[r][1:]) + 24,
                probe.textlength(NOTES[r][0], font=title_f) + 24) for r, p in zip(ORDER, panels)]
    colw = [int(c) for c in colw]
    W = sum(colw) + gap * (len(panels) - 1) + 2 * margin
    H = margin + ph + 150 + 190
    sheet = Image.new("RGBA", (W, H), (34, 36, 40, 255))
    d = ImageDraw.Draw(sheet)
    x = margin
    for r, p, cw in zip(ORDER, panels, colw):
        sheet.alpha_composite(p, (x + (cw - p.width) // 2, margin + ph - p.height))
        title, *notes = NOTES[r]
        cx = x + cw // 2
        d.text((cx, margin + ph + 30), title, font=title_f, fill=(236, 236, 232), anchor="mm")
        for i, n in enumerate(notes):
            d.text((cx, margin + ph + 68 + 26 * i), n, font=note_f, fill=(176, 178, 184), anchor="mm")
        x += cw + gap

    # legend: color - what the key does
    ly = margin + ph + 170
    lx = margin
    items = list(ROLE.values())
    per_row = 3
    colw_leg = (W - 2 * margin) // per_row
    for i, (col, text) in enumerate(items):
        cx = lx + (i % per_row) * colw_leg
        cy = ly + (i // per_row) * 44
        d.rounded_rectangle((cx, cy, cx + 38, cy + 24), radius=6, outline=col + (255,), width=3)
        d.text((cx + 52, cy + 12), text, font=legend_f, fill=(222, 222, 222), anchor="lm")
    d.text((W - margin, H - 26), FOOTER,
           font=note_f, fill=(150, 152, 158), anchor="rm")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    sheet.convert("RGB").save(OUT, quality=90)
    print("legend:", OUT, sheet.size)


if __name__ == "__main__":
    main()
