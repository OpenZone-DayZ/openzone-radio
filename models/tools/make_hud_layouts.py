"""Окно частот «лицом рации»: текстуры и разметка из рендера лица и чисел раскладки.

    python tools/make_hud_layouts.py [рация ...]      (системный Python с Pillow)

Перед ним - tools/render_hud_faces.py (Blender), он пишет assets/<рация>/work/hud/face_raw.png.
Этот скрипт:
  - стирает с экрана рации запечённые «призраки» сегментов: в окне экран живой, и призраки
    рисует разметка тем же шрифтом, что и цифры, - иначе они не совпали бы с цифрами;
  - пишет всё в .edds (формат ванильных картинок интерфейса: несжатый BGRA8 с мипами) в
    OpenZone_Radio/gui/faces/ основного мода, значения - линейные (см. write_edds: интерфейс сам
    кодирует пиксели в sRGB, и записанное как есть выходило блёклым). В .paa нельзя:
    DXT5 с линейными значениями ломает тёмные тона на пятна;
  - пишет разметку OpenZone_Radio/gui/layouts/oz_face_<s>.layout.

Имена виджетов читает OpenZone_Radio/scripts/5_Mission/OpenZone_Radio/OZR_FreqMenuFace.c
(см. hud_spec.py - роли клавиш).
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hud_spec as S  # noqa: E402

# Лица окна - часть основного мода: папка OpenZone_Radio рядом с models/, префикс pbo тот же.
PBO = os.path.normpath(os.path.join(S.ROOT, "..", "OpenZone_Radio"))
PREFIX = "OpenZone_Radio"

SEG_FONT = "gui/fonts/7segment48"
TEXT_FONT = "gui/fonts/sdf_MetronBook24"
KEY_PAD = 0.0008          # м: поле нажатия шире самой клавиши


# Интерфейс DayZ кодирует пиксели картинки в sRGB при выводе (цвет виджета, заданный числом,
# - нет). Значит, в текстуре окна должны лежать ЛИНЕЙНЫЕ значения. Проверено в игре 24.09 на
# одной сборке: лицо, записанное как есть, вышло блёклым (85 -> 156, 118 -> 181 - ровно
# формула sRGB), линеаризованное - с цветами рендера. Суффикс _ca у .paa на это не влияет.
_SRGB_TO_LIN = [int(round(255 * (((v / 255 + 0.055) / 1.055) ** 2.4 if v > 10 else v / 255 / 12.92)))
                for v in range(256)]


def write_edds(img, path, linear):
    """RGBA -> .edds в формате ванильных картинок интерфейса (P:/gui: 175 файлов из 197):
    DDS-заголовок с меткой ENF1, несжатый BGRA8, полная цепочка мипов; за заголовком таблица
    блоков от меньшего мипа к большему ("COPY" + размер), затем сами мипы в том же порядке.
    Разобрано по gui/fonts/7segment22.edds."""
    import struct
    img = img.convert("RGBA")
    if linear:
        r, g, b, a = img.split()
        img = Image.merge("RGBA", [ch.point(_SRGB_TO_LIN) for ch in (r, g, b)] + [a])
    mips = [img]
    while mips[-1].width > 1 or mips[-1].height > 1:
        m = mips[-1]
        mips.append(m.resize((max(1, m.width // 2), max(1, m.height // 2)), Image.BOX))
    w, h = img.size
    hdr = bytearray(128)
    hdr[0:4] = b"DDS "
    struct.pack_into("<7I", hdr, 4, 124, 0x2100F, h, w, w * 4, 0, len(mips))
    hdr[36:40] = b"ENF1"
    struct.pack_into("<2I4s5I", hdr, 76, 32, 0x41, b"\x00\x00\x00\x00", 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    struct.pack_into("<I", hdr, 108, 0x401008)
    blobs = [m.tobytes("raw", "BGRA") for m in reversed(mips)]
    table = b"".join(b"COPY" + struct.pack("<I", len(bl)) for bl in blobs)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(bytes(hdr) + table + b"".join(blobs))


class Frame:
    """Метры модели -> пиксели окна (1080p) и пиксели текстуры лица."""

    def __init__(self, radio):
        self.radio = radio
        self.spec = S.RADIOS[radio]
        self.s = self.spec["scale"]                   # px окна на мм
        self.t = S.tex_ppmm(radio)                    # px текстуры на мм
        self.x0, self.x1, self.z0, self.z1 = S.region(radio)
        self.w = (self.x1 - self.x0) * 1000 * self.s
        self.h = (self.z1 - self.z0) * 1000 * self.s

    def ui(self, x, z):
        return (x - self.x0) * 1000 * self.s, (self.z1 - z) * 1000 * self.s

    def tex(self, x, z):
        return (x - self.x0) * 1000 * self.t, (self.z1 - z) * 1000 * self.t

    def ui_rect(self, x0, x1, z0, z1):
        (a, b), (c, d) = self.ui(x0, z1), self.ui(x1, z0)
        return a, b, c - a, d - b


# ---------------------------------------------------------------------------- картинки
def clean_face(f):
    """Экран без запечённых призраков: ровная подложка цвета самого экрана."""
    src = os.path.join(S.ROOT, "assets", f.radio, "work", "hud", "face_raw.png")
    img = Image.open(src).convert("RGBA")
    x0, x1, z0, z1 = S.lcd_rect(f.radio)
    (a, b), (c, d) = f.tex(x0, z1), f.tex(x1, z0)
    inset = 0.0006 * 1000 * f.t                       # рамка стекла остаётся с рендера
    box = (int(a + inset), int(b + inset), int(c - inset), int(d - inset))
    core = img.crop((box[0] + (box[2] - box[0]) // 4, box[1] + (box[3] - box[1]) // 4,
                     box[2] - (box[2] - box[0]) // 4, box[3] - (box[3] - box[1]) // 4)).convert("RGB")
    base = core.resize((1, 1), Image.BOX).getpixel((0, 0))
    base = tuple(min(255, int(v * 1.06)) for v in base)
    # подложка с лёгкой виньеткой к краям - как у настоящего ЖКИ за стеклом
    bw, bh = box[2] - box[0], box[3] - box[1]
    pane = Image.new("RGBA", (bw, bh), base + (255,))
    shade = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(shade).rectangle((0, 0, bw - 1, bh - 1), outline=90, width=max(2, bh // 10))
    shade = shade.filter(ImageFilter.GaussianBlur(bh / 8))
    pane = Image.composite(Image.new("RGBA", (bw, bh), (0, 0, 0, 255)), pane, shade.point(lambda v: v // 3))
    mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw - 1, bh - 1), radius=max(2, int(0.0010 * 1000 * f.t)), fill=255)
    img.paste(pane, box[:2], mask)
    out = os.path.join(S.ROOT, "assets", f.radio, "work", "hud", "face.png")
    img.save(out)
    half = img.resize((S.TEX_W // 2, S.TEX_H // 2), Image.LANCZOS)
    write_edds(half, os.path.join(PBO, "gui", "faces", "oz_face_%s.edds" % f.spec["stem"]), True)



# ---------------------------------------------------------------------------- разметка
def attrs(x, y, w, h, prio, ignore=True, extra=()):
    lines = [" visible 1"]
    if ignore:
        lines.append(" ignorepointer 1")
    lines += [" position %.0f %.0f" % (x, y), " size %.0f %.0f" % (w, h), " hexactpos 1", " vexactpos 1",
              " hexactsize 1", " vexactsize 1", " priority %d" % prio]
    lines += [" " + e for e in extra]
    return lines


def widget(kind, name, lines, indent="  "):
    return [indent + "%s %s {" % (kind, name)] + [indent + l for l in lines] + [indent + "}"]


def text(name, x, y, w, h, value, font, size, color, halign, prio=4):
    return widget("TextWidgetClass", name, attrs(x, y, w, h, prio, extra=(
        'text "%s"' % value, 'font "%s"' % font, '"exact text" 1', '"exact text size" %d' % size,
        '"text halign" %s' % halign, '"text valign" center', "color %s" % color)))


def lcd_lines(f):
    """(имя, строка-призрак, доля высоты экрана, выравнивание) сверху вниз.

    Сегментный экран: призрак - погасшие сегменты тем же шрифтом, что и цифры, поэтому совпадает
    с ними знак в знак. У точечной матрицы погасших сегментов нет - и призрака нет."""
    seg = f.spec["lcd"] == "seg"
    if f.spec["mode"] == "step":
        return [("LcdMain", "888" if seg else "", 0.62, "right"), ("LcdSub", "888.888" if seg else "", 0.38, "center")]
    return [("LcdMain", "888.888" if seg else "", 0.54, "right" if seg else "left"),
            ("LcdSub", "888.888" if seg else "", 0.46, "left")]


def layout(f):
    stem = f.spec["stem"]
    out = ["// Окно частот «лицом рации» (%s). СГЕНЕРИРОВАНО tools/make_hud_layouts.py - руками не править." % stem,
           "// Имена читают OZR_FreqMenu.c и OZR_FreqMenuFace.c: DragBar, TitleText, HintText, BtnClose,",
           "// Btn0..Btn9, BtnUp, BtnDown, BtnGo, BtnDot, BtnBack, LcdMain, LcdSub, Face.",
           "",
           "FrameWidgetClass Card {",
           " visible 1", " position 0 0", " size %.0f %.0f" % (f.w, f.h + S.CAPTION), " hexactpos 1", " vexactpos 1",
           " hexactsize 1", " vexactsize 1", " priority 1", " {"]
    body = []
    tw, th = S.TEX_W / f.t * f.s, S.TEX_H / f.t * f.s
    body += widget("ImageWidgetClass", "Face", attrs(0, 0, tw, th, 1, extra=(
        'image0 "%s/gui/faces/oz_face_%s.edds"' % (PREFIX, stem), "mode blend", '"src alpha" 1', "stretch 1", "filter 1")))
    # за корпус тянут окно: всё, что не клавиша, - ручка перетаскивания (OZR_FreqMenu ждёт имя DragBar)
    body += widget("PanelWidgetClass", "DragBar", attrs(0, 0, f.w, f.h, 2, ignore=False, extra=("color 0 0 0 0",)))

    lx, ly, lw, lh = f.ui_rect(*S.lcd_rect(f.radio))
    ink = "%.3f %.3f %.3f " % tuple(f.spec["ink"])
    seg = f.spec["lcd"] == "seg"
    font = SEG_FONT if seg else TEXT_FONT
    y = ly
    for name, ghost, share, halign in lcd_lines(f):
        hh = lh * share
        pad = lw * 0.06
        # сегментный шрифт моноширинный и узкий; текстовый шире - «136.000» (7 знаков) должно
        # влезть в ширину экрана: на XTS при 0.8 высоты строки последний ноль обрезался
        size = int(round(hh * 0.95)) if seg else int(min(hh * 0.80, (lw - 2 * pad) / (7 * 0.60)))
        if ghost:
            body += text(name + "Ghost", lx + pad, y, lw - 2 * pad, hh, ghost, font, size, ink + "0.07", halign, prio=3)
        body += text(name, lx + pad, y, lw - 2 * pad, hh, "", font, size, ink + "0.92", halign, prio=4)
        y += hh

    for role, x, z, w, h, rnd in S.keys(f.radio):
        bx, by, bw, bh = f.ui_rect(x - w / 2 - KEY_PAD, x + w / 2 + KEY_PAD, z - h / 2 - KEY_PAD, z + h / 2 + KEY_PAD)
        body += widget("ButtonWidgetClass", role, attrs(bx, by, bw, bh, 5, ignore=False, extra=(
            'text ""', "color 1 1 1 0")))

    # крестик: у раций без EXIT это единственный выход мышью (K и Esc закрывают всегда)
    cs = 26
    body += widget("ImageWidgetClass", "BtnCloseBg", attrs(f.w - cs - 6, 6, cs, cs, 5, extra=(
        'image0 "set:dayz_gui image:circle"', "mode blend", '"src alpha" 1', "stretch 1",
        "color 0.10 0.10 0.11 0.85")))
    body += widget("ButtonWidgetClass", "BtnClose", attrs(f.w - cs - 6, 6, cs, cs, 6, ignore=False, extra=(
        'text ""', "color 1 1 1 0")))
    body += text("BtnCloseLabel", f.w - cs - 6, 7, cs, cs, "X", TEXT_FONT, 17, "0.92 0.92 0.92 1", "center", prio=7)

    # подпись под рацией: название и подсказка
    body += widget("PanelWidgetClass", "CaptionBg", attrs(0, f.h, f.w, S.CAPTION, 2, ignore=False, extra=(
        "color 0.055 0.059 0.071 0.85", "style rover_sim_colorable")))
    body += text("TitleText", 10, f.h + 3, f.w - 20, 20, "", TEXT_FONT, 17, "0.85 0.85 0.87 1", "left")
    body += text("HintText", 10, f.h + 23, f.w - 20, 20, "", TEXT_FONT, 14, "0.62 0.63 0.67 1", "left")

    out += body + [" }", "}", ""]
    path = os.path.join(PBO, "gui", "layouts", "oz_face_%s.layout" % stem)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out))
    print("layout %s: card %.0fx%.0f, %d keys, tex %.1f px/mm" % (stem, f.w, f.h + S.CAPTION, len(S.keys(f.radio)), f.t))


if __name__ == "__main__":
    for r in (sys.argv[1:] or list(S.RADIOS)):
        fr = Frame(r)
        clean_face(fr)
        layout(fr)
