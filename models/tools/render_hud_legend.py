"""Легенда окна частот: лица всех раций, цветом - клавиши, которые в окне работают.

    python tools/render_hud_legend.py [out.jpg] [--lang ru|en|uk]      (системный Python с Pillow)

Без --lang - русская (docs/screenshots/hud_legend.jpg); en и uk пишут hud_legend.en.jpg / hud_legend.uk.jpg.

Рисует из того же, из чего собрано окно: лицо - assets/<рация>/work/hud/face.png (его
пишут render_hud_faces.py и make_hud_layouts.py), клавиши и экран - из hud_spec.py через
ту же Frame, что строит разметку. Поменяли роли клавиш или модель - перегенерировали окно -
перезапустили это, и картинка снова совпадает с игрой.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hud_spec as S  # noqa: E402
import make_hud_layouts as M  # noqa: E402

ARGS = sys.argv[1:]
LANG = ARGS[ARGS.index("--lang") + 1] if "--lang" in ARGS else "ru"
POS = [a for i, a in enumerate(ARGS) if not a.startswith("--") and (i == 0 or ARGS[i - 1] != "--lang")]
OUT = POS[0] if POS else os.path.join(S.ROOT, "docs", "screenshots",
                                      "hud_legend.jpg" if LANG == "ru" else "hud_legend.%s.jpg" % LANG)
SEG_TTF = r"D:\modding\PDrive\gui\fonts\7segment.ttf"      # тот же шрифт, что gui/fonts/7segment в игре
TEXT_TTF = r"C:\Windows\Fonts\bahnschrift.ttf"
K = 1.35                                                   # масштаб к пикселям окна при 1080p

ROLE = {   # роль -> (цвет, подпись в легенде)
    "digit": ((79, 195, 247), "цифры — набор частоты"),
    "step": ((255, 213, 79), "шаг: у T-388 и LXT сразу новый канал, у остальных — соседний в строку набора"),
    "go": ((102, 187, 106), "настроить (как TUNE у мода рации)"),
    "back": ((239, 83, 80), "стереть цифру, а если нечего — выйти"),
    "close": ((186, 104, 200), "выйти"),
    "dot": ((236, 236, 236), "точка (сама — когда целая часть больше не может расти)"),
}


def role_of(widget):
    if widget.startswith("Btn") and widget[3:].isdigit():
        return "digit"
    return {"BtnUp": "step", "BtnDown": "step", "BtnGo": "go", "BtnBack": "back", "BtnClose": "close",
            "BtnDot": "dot"}[widget]


NOTES = {   # под рацией: название и короткие строки, что где
    "pmr_t388": ("T-388 · 250 м", "стрелки — канал вниз / вверх, сразу", "красная кнопка — выйти", "экран: крупно канал, мелко частота"),
    "lxt": ("LXT · 500 м", "стрелки — канал вниз / вверх, сразу", "экран: крупно канал,", "мелко частота"),
    "uv5r": ("UV-5R · 1 км", "MENU — настроить", "EXIT — стереть / выйти, * — точка", "стрелки — соседний канал"),
    "uvs9": ("UV-S9 · 2 км", "MENU — настроить", "EXIT — стереть / выйти, * — точка", "стрелки — соседний канал"),
    "xts": ("XTS5000 · 5 км", "справа от джойстика — настроить", "слева — выйти, # — стереть / выйти",
            "* — точка, джойстик — соседний канал"),
    "prc152": ("PRC-152 · 10 км", "ENT — настроить", "CLR и < — стереть / выйти", "> — точка, PRE +/- — соседний канал"),
}
ORDER = ["pmr_t388", "lxt", "uv5r", "uvs9", "xts", "prc152"]
FOOTER = "Окно закрывают крестик в углу, клавиша K и Esc. Окно тянется мышью за корпус."

# Переводы: подписи ролей, строки под рациями и нижняя строка. Названия рацией-референсов - как в русской.
TRANSLATIONS = {
    "en": dict(
        roles={"digit": "digits — type a frequency",
               "step": "step: T-388, LXT — new channel at once; others — neighbour in the entry line",
               "go": "tune (like TUNE in the radio mod)",
               "back": "erase a digit, or exit if there is nothing to erase",
               "close": "exit",
               "dot": "dot (inserted automatically once the integer part cannot grow any more)"},
        notes={"pmr_t388": ("T-388 · 250 m", "arrows — channel down / up, at once", "red button — exit", "screen: big channel, small frequency"),
               "lxt": ("LXT · 500 m", "arrows — channel down / up, at once", "screen: big channel,", "small frequency"),
               "uv5r": ("UV-5R · 1 km", "MENU — tune", "EXIT — erase / exit, * — dot", "arrows — neighbouring channel"),
               "uvs9": ("UV-S9 · 2 km", "MENU — tune", "EXIT — erase / exit, * — dot", "arrows — neighbouring channel"),
               "xts": ("XTS5000 · 5 km", "right of the joystick — tune", "left — exit, # — erase / exit",
                       "* — dot, joystick — neighbouring channel"),
               "prc152": ("PRC-152 · 10 km", "ENT — tune", "CLR and < — erase / exit", "> — dot, PRE +/- — neighbouring channel")},
        footer="Close the window with the cross in the corner, the K key or Esc. Drag the window by the radio body."),
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

    # экран - как в игре: сегментный шрифт с погасшими 888 или текст точечной матрицы.
    # Текст - на отдельном слое: ImageDraw на RGBA заменяет пиксель вместе с альфой, и
    # полупрозрачные призраки протыкали бы лицо насквозь (та же ловушка, что была с ЖКИ).
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

    # клавиши: рамка цвета роли вокруг поля нажатия
    for widget, x, z, w, h, rnd in S.keys(radio):
        col = ROLE[role_of(widget)][0]
        bx, by, bw, bh = [v * K for v in f.ui_rect(x - w / 2 - M.KEY_PAD, x + w / 2 + M.KEY_PAD,
                                                    z - h / 2 - M.KEY_PAD, z + h / 2 + M.KEY_PAD)]
        box = (bx, by, bx + bw, by + bh)
        if rnd:
            d.ellipse(box, outline=col + (255,), width=3)
        else:
            d.rounded_rectangle(box, radius=min(bw, bh) * 0.25, outline=col + (255,), width=3)

    # крестик в углу окна - есть у всех
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

    # легенда: цвет - что делает клавиша
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
