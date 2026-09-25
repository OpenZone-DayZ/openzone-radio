"""Рация на 2000 м (по мотивам Baofeng UV-S9, олива): детальная модель, лоды, запекание, p3d.

    python make_prints_uvs9.py
    blender -b -P build_uvs9.py -- [--high-only] [--skip-bake] [--no-previews]

Оливковый корпус-бампер и тёмные накладки поверх: клавиатура, решётка, рамка ЖКИ. Геометрией до
LOD2 - накладки, клавиши, кнопки, ручка, антенна, PTT, заглушка; прорези решётки - до LOD1.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "_kit")))
import radiokit as K  # noqa: E402
import layout_uvs9 as L  # noqa: E402
from mathutils import Vector  # noqa: E402

TEX = os.path.normpath(os.path.join(HERE, "..", "textures"))
OLIVE = (0.086, 0.093, 0.043)
DECK = (0.058, 0.050, 0.040)


def P(name):
    return os.path.join(TEX, name)


def materials():
    front = dict(image=P("print_front.png"), rect=L.FRONT_RECT, axis="-Y")
    right = dict(image=P("print_right.png"), rect=L.RIGHT_RECT, axis="+X")
    left = dict(image=P("print_left.png"), rect=L.LEFT_RECT, axis="-X")
    back = dict(image=P("print_back.png"), rect=L.BACK_RECT, axis="+Y")
    dust = (0.20, 0.18, 0.14)
    return {
        "body": K.mat_worn("M_Olive", OLIVE, rough=(0.45, 0.62), edge_col=(0.30, 0.30, 0.22), dust=dust,
                           dust_amount=0.5, prints=[front, back], noise_bump=0.15),
        "deck": K.mat_worn("M_Deck", DECK, rough=(0.5, 0.66), edge_col=(0.20, 0.18, 0.15), dust=dust,
                           dust_amount=0.5, prints=[front], noise_bump=0.12),
        "keys": K.mat_worn("M_Keys", (0.075, 0.066, 0.054), rough=(0.45, 0.6), edge_col=(0.22, 0.20, 0.17),
                           dust=dust, prints=[front]),
        "rubber": K.mat_worn("M_Rubber", (0.018, 0.018, 0.017), rough=(0.7, 0.85), edge_col=(0.07, 0.07, 0.07),
                             edge_amount=0.5, dust=dust, prints=[right, left]),
        "btn_green": K.mat_worn("M_BtnGreen", (0.16, 0.34, 0.14), rough=(0.4, 0.55), edge_col=(0.45, 0.6, 0.4),
                                dust=dust, prints=[front]),
        "btn_orange": K.mat_worn("M_BtnOrange", (0.80, 0.30, 0.03), rough=(0.4, 0.55), edge_col=(0.95, 0.6, 0.3),
                                 dust=dust, prints=[front]),
        "btn_grey": K.mat_worn("M_BtnGrey", (0.30, 0.30, 0.29), rough=(0.45, 0.6), edge_col=(0.55, 0.55, 0.53),
                               dust=dust),
        "lcd": K.mat_worn("M_LCD", (0.2, 0.2, 0.2), rough=(0.07, 0.13), edge_amount=0.0, dust=dust,
                          dust_amount=0.3, soft_edges=0.0, image=(P("lcd.png"), L.LCD_RECT, "-Y")),
        "steel": K.mat_worn("M_Steel", (0.50, 0.49, 0.46), rough=(0.25, 0.42), metallic=1.0, dust=dust,
                            edge_col=(0.75, 0.74, 0.70)),
        "antenna": K.mat_worn("M_Antenna", (0.016, 0.016, 0.016), rough=(0.55, 0.75), edge_amount=0.3, dust=dust),
        "dark": K.mat_simple("M_Hole", (0.005, 0.005, 0.005), 0.9),
    }


def deck_rect(d, seg):
    return K.rrect(d["x1"] - d["x0"], d["z1"] - d["z0"], d["r"], (d["x0"] + d["x1"]) / 2, (d["z0"] + d["z1"]) / 2,
                   seg=seg)


def shell(m):
    prof = K.rrect(L.W, L.YB - L.YF, L.R_PLAN, 0.0, (L.YF + L.YB) / 2, seg=m.s(8, 3, 2, 1, 0))
    bm = K.prism(prof, 0.0, L.H, "Z")
    cuts = None
    if m.hi:
        # бамперные канавки по бокам: длинная выемка у низа, как на референсе
        cuts = [K.prism(K.rrect(0.010, 0.030, 0.004, -0.004, 0.018, seg=6), -L.W / 2 - 0.002, -L.W / 2 + 0.0012, "X"),
                K.prism(K.rrect(0.010, 0.030, 0.004, -0.004, 0.018, seg=6), L.W / 2 - 0.0012, L.W / 2 + 0.002, "X")]
    m.add(bm, "body", name="Shell", bevel_=(L.BEV_TB, (5, 2, 1, 0)), cuts=cuts, bevel_angle=45.0)
    if m.hi:
        for x, z in L.FACE_SCREWS:
            prof = [(0.0022, L.YF + 0.0003), (0.0022, L.YF - 0.0002), (0.0015, L.YF - 0.0006), (0.0, L.YF - 0.0007)]
            scr = K.lathe(prof, 24, x, z, "Y")
            cross = [K.prism(K.rect(0.0028, 0.0005, x, z), L.YF - 0.0003, L.YF - 0.002, "Y"),
                     K.prism(K.rect(0.0005, 0.0028, x, z), L.YF - 0.0003, L.YF - 0.002, "Y")]
            m.add(scr, "steel", name="FaceScrew", cuts=cross)


def decks(m):
    kd, gd, lf = L.KEY_DECK, L.GRILLE_DECK, L.LCD_FRAME
    m.add(K.prism(deck_rect(kd, m.s(5, 2, 1, 0)), L.YF + 0.0006, L.YF - kd["proud"], "Y"), "deck", name="KeyDeck",
          bevel_=(0.0008, (3, 1, 0)), bevel_angle=45.0)
    cuts = []
    if m.upto(1):
        s = L.SLOTS
        cuts.append(K.merge(*[K.prism(K.rrect(s["x1"] - s["x0"], s["h"], s["h"] / 2 * 0.98, (s["x0"] + s["x1"]) / 2, z,
                                              seg=m.s(6, 2)), L.YF - gd["proud"] + s["depth"], L.YF - 0.004, "Y")
                              for z in s["z"]]))
    m.add(K.prism(deck_rect(gd, m.s(5, 2, 1, 0)), L.YF + 0.0006, L.YF - gd["proud"], "Y"), "deck", name="GrilleDeck",
          bevel_=(0.0008, (3, 1, 0)), cuts=cuts, bevel_angle=45.0)
    w = L.LCD_WIN
    yf = L.YF - lf["proud"]
    cuts = []
    if m.upto(1):
        cuts.append(K.prism(K.rrect(w["w"], w["h"], w["r"], w["cx"], w["cz"], seg=m.s(4, 1)), yf - 0.001,
                            yf + w["depth"], "Y"))
    m.add(K.prism(deck_rect(lf, m.s(6, 2, 1, 0)), L.YF + 0.0006, yf, "Y"), "deck", name="LcdFrame",
          bevel_=(0.0012, (3, 1, 0)), cuts=cuts, bevel_angle=45.0)
    y_lcd = yf + w["depth"] - 0.0001 if m.upto(1) else yf - 0.0001
    lcd = K.prism(K.rrect(w["w"] - 0.0003, w["h"] - 0.0003, w["r"], w["cx"], w["cz"], seg=m.s(4, 1, 0)),
                  y_lcd + 0.0003, y_lcd, "Y")
    m.add(lcd, "lcd", tag=K.T_LCD, name="LCD")


def keys(m):
    if not m.upto(2):
        return
    base = L.YF - L.KEY_DECK["proud"]
    for row, z in zip(L.KEYS, L.KEY_ROWS):
        for _, x in zip(row, L.KEY_COLS):
            bm = K.prism(K.rrect(L.KEY_W, L.KEY_H, L.KEY_R, x, z, seg=m.s(4, 2, 0)), base + 0.0004,
                         base - L.KEY_PROUD, "Y")
            m.add(bm, "keys", tag=K.T_KEYS, name="Key", bevel_=(0.0008, (3, 1, 0)), bevel_angle=60.0)
    # BAND - на нижней кромке решётки
    x, z, w, h = L.BAND_BTN
    gbase = L.YF - L.GRILLE_DECK["proud"]
    m.add(K.prism(K.rrect(w, h, 0.0012, x, z, seg=m.s(4, 2, 0)), gbase + 0.0008, gbase - 0.0016, "Y"), "keys",
          tag=K.T_KEYS, name="Band", bevel_=(0.0006, (3, 1, 0)), bevel_angle=60.0)


def column_buttons(m):
    x = L.SIDE_COL_X
    for z, w, h, mat, _t in L.COL_BTNS:
        if mat == "mic":
            if m.hi:
                pad = K.prism(K.rrect(w, h, 0.0008, x, z, seg=3), L.YF + 0.0004, L.YF - 0.0006, "Y")
                m.add(pad, "deck", name="MicPad", cuts=[K.cyl(x, z, 0.0009, L.YF - 0.002, L.YF + 0.001, 16, "Y")],
                      bevel_=(0.0003, (2,)))
            continue
        if not m.upto(2):
            continue
        cuts = None
        if m.hi and mat == "btn_grey":      # фонарь: рифлёная клавиша
            cuts = [K.merge(*[K.prism(K.rect(w + 0.001, 0.00045, x, z - h / 2 + 0.0008 + i * 0.0009),
                                      L.YF - 0.0016 + 0.0003, L.YF - 0.004, "Y") for i in range(5)])]
        bm = K.prism(K.rrect(w, h, 0.0014, x, z, seg=m.s(4, 2, 0)), L.YF + 0.0004, L.YF - 0.0016, "Y")
        m.add(bm, mat, tag=K.T_KEYS, name="ColButton", bevel_=(0.0006, (3, 1, 0)), cuts=cuts, bevel_angle=60.0)


def knob(m):
    k = L.KNOB
    z0, z1 = k["z0"], k["z0"] + k["h"]
    if m.hi:
        m.add(K.cyl(k["x"], k["y"], k["r"] * 0.84, L.H - 0.001, z0 + 0.0006, 40, "Z"), "rubber", name="KnobCollar",
              bevel_=(0.0004, (2,)))
        bm = K.prism(K.knurl(k["x"], k["y"], k["r"] * 0.88, k["r"], k["teeth"], (0.0, 0.18, 0.46, 0.64)), z0, z1, "Z")
        m.add(bm, "rubber", name="Knob", bevel_=(0.0005, (2,)), bevel_angle=60.0)
        return
    m.add(K.cyl(k["x"], k["y"], k["r"] * 0.96, L.H - 0.001, z1, m.s(0, 16, 10, 8, 6), "Z"), "rubber", name="Knob",
          bevel_=(0.0008, (0, 1, 0)), bevel_angle=60.0)


def antenna(m):
    a = L.ANT
    x, y = a["x"], a["y"]
    zb, zt = a["z_boot"], a["top"]
    if m.hi:
        prof = [(0.0, L.H - 0.001), (a["boot_r"], L.H - 0.001)]
        for i in range(5):                    # толстые рёбра основания, как на референсе
            z = L.H + 0.0030 + i * 0.0036
            prof += [(a["boot_r"], z - 0.0010), (a["boot_r"] - 0.0010, z - 0.0004), (a["boot_r"] - 0.0010, z + 0.0004),
                     (a["boot_r"], z + 0.0010)]
        prof += [(a["boot_r"], zb - 0.002), (a["whip_r0"] + 0.0006, zb), (a["whip_r0"], zb + 0.002)]
        for i in range(1, 15):
            t = i / 14
            prof.append((a["whip_r0"] + (a["whip_r1"] - a["whip_r0"]) * t, zb + 0.002 + (zt - 0.004 - zb - 0.002) * t))
        for k in range(1, 6):
            ang = math.radians(90 * k / 6)
            prof.append((a["whip_r1"] * math.cos(ang), zt - 0.004 + a["whip_r1"] * 1.1 * math.sin(ang)))
        prof.append((0.0, zt - 0.004 + a["whip_r1"] * 1.1))
    else:
        prof = [(0.0, L.H - 0.001), (a["boot_r"], L.H - 0.001), (a["boot_r"], zb - 0.002), (a["whip_r0"], zb)]
        if m.q <= 2:
            prof.append((a["whip_r0"] + (a["whip_r1"] - a["whip_r0"]) * 0.5, zb + (zt - zb) * 0.5))
        prof += [(a["whip_r1"], zt - 0.003), (0.0, zt)]
    m.add(K.lathe(prof, m.s(28, 10, 8, 6, 4), x, y, "Z"), "antenna", name="Antenna")


def sides(m):
    # PTT слева
    if m.upto(2):
        yc, z0, z1, wy, proud = L.PTT
        xs = -L.W / 2
        bm = K.prism(K.rrect(wy, z1 - z0, 0.003, yc, (z0 + z1) / 2, seg=m.s(5, 2, 0)), xs + 0.0015, xs - proud, "X")
        cuts = None
        if m.hi:
            cuts = [K.merge(*[K.prism(K.rect(wy + 0.002, 0.0006, yc, z0 + (z1 - z0) * (i + 1) / 8),
                                      xs - proud + 0.0004, xs - proud - 0.002, "X") for i in range(7)])]
        m.add(bm, "rubber", name="PTT", bevel_=(0.0010, (3, 1, 0)), cuts=cuts, bevel_angle=60.0)
        # заглушка гарнитуры справа
        yc, z0, z1, wy, proud = L.JACK
        xs = L.W / 2
        bm = K.prism(K.rrect(wy, z1 - z0, 0.0025, yc, (z0 + z1) / 2, seg=m.s(5, 2, 0)), xs - 0.0015, xs + proud, "X")
        m.add(bm, "rubber", name="JackCover", bevel_=(0.0007, (3, 1, 0)), bevel_angle=60.0)
    if m.upto(1):
        y, z, r = L.JACK_SCREW
        xs = L.W / 2
        prof = [(r, xs - 0.001), (r, xs + 0.0008), (r * 0.7, xs + 0.0016), (0.0, xs + 0.0018)]
        m.add(K.lathe(prof, m.s(32, 10), y, z, "X"), "steel", name="JackScrew")


def battery(m):
    b = L.BAT
    yc = (b["y0"] + b["y1"]) / 2
    prof = K.rrect(b["w"], b["y1"] - b["y0"], (0.001, 0.004, 0.004, 0.001), 0.0, yc, seg=m.s(5, 2, 1, 0))
    m.add(K.prism(prof, 0.0015, b["top"], "Z"), "body", name="Battery", bevel_=(0.0015, (3, 1, 0)), bevel_angle=50.0)


def clip_offset(z):
    """Отход пластины клипсы от корпуса: чистый сдвиг, пластина остаётся ПЛОСКОЙ. Изгиб делал
    неплоскую n-угольную крышку, и её триангуляция складкой давала тёмный «ромб» посередине."""
    return 0.0036 * (L.CLIP_TOP - z) / (L.CLIP_TOP - L.CLIP_BOT)


def belt_clip(m):
    if not m.upto(3):
        return
    y0 = L.BAT["y1"]
    mount = K.prism(K.rrect(0.026, 0.014, 0.002, 0.0, L.CLIP_TOP - 0.007, seg=m.s(4, 1, 0)), y0 - 0.0005, y0 + 0.0035,
                    "Y")
    m.add(mount, "antenna", name="ClipMount", bevel_=(0.0006, (3, 1, 0)), bevel_angle=50.0)
    pts = K.rrect(L.CLIP_W, L.CLIP_TOP - L.CLIP_BOT, (0.005, 0.002, 0.002, 0.005), 0.0,
                  (L.CLIP_TOP + L.CLIP_BOT) / 2, seg=m.s(5, 2, 1, 0))
    pts = K.densify(pts, m.s(0.003, 0.008, 0.02, 0.05))
    bm = K.prism(pts, y0 + 0.0035, y0 + 0.0055, "Y")
    for v in bm.verts:
        v.co.y += clip_offset(v.co.z)
    K.fix_normals(bm)
    m.add(bm, "antenna", name="ClipPlate", bevel_=(0.0006, (3, 1, 0)), bevel_angle=50.0)
    if m.hi:
        for sx in (-1, 1):
            ys = y0 + 0.0055
            prof = [(0.0019, ys - 0.0002), (0.0019, ys + 0.0003), (0.0012, ys + 0.0008), (0.0, ys + 0.0010)]
            m.add(K.lathe(prof, 20, sx * 0.0075, L.CLIP_TOP - 0.007, "Y"), "steel", name="ClipScrew")



def build(m):
    shell(m)
    decks(m)
    keys(m)
    column_buttons(m)
    knob(m)
    antenna(m)
    sides(m)
    battery(m)
    belt_clip(m)


def collision(_lods):
    def bx(x0, x1, y0, y1, z0, z1):
        return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]

    body = bx(-L.W / 2, L.W / 2, L.YF - L.LCD_FRAME["proud"], L.BAT["y1"] + 0.0055, 0.0, L.H)
    k = L.KNOB
    body += [(k["x"] + k["r"] * math.cos(i * math.pi / 4), k["y"] + k["r"] * math.sin(i * math.pi / 4),
              k["z0"] + k["h"]) for i in range(8)]
    a = L.ANT
    ant = [(a["x"] + a["boot_r"] * math.cos(i * math.pi / 4), a["y"] + a["boot_r"] * math.sin(i * math.pi / 4), z)
           for i in range(8) for z in (L.H, a["top"])]
    geom = [(body, ""), (ant, "")]
    view = [(body, "")]
    fire = [(body, K.PEN + r"\plastic_material.rvmat"), (ant, K.PEN + r"\rubber.rvmat")]
    return geom, view, fire


SPEC = dict(
    name="uvs9",
    stem="oz_radio_uvs9",
    build=build,
    materials=materials,
    collision=collision,
    mass=0.30,
    grip_shift=0.03,           # сдвиг в хвате руки, м (+ к антенне), по просьбе пользователя 25.09
    body_top=L.H,
    previews=[
        ("front", 0, 4, 0.82, (0.0, 0.0, 0.150)),
        ("threeq", -32, 14, 0.44, (0.0, 0.0, 0.070)),
        ("close", 20, 30, 0.26, (0.0, -0.01, 0.060)),
        ("back", 148, 12, 0.44, (0.0, 0.0, 0.065)),
        ("right", 80, 6, 0.42, (0.0, 0.0, 0.070)),
    ],
    bake=dict(cage=0.0028, ray=0.007, size=4096, out=2048),
)

if __name__ == "__main__":
    K.run(SPEC)
