"""Radio, 500/750 m range (inspired by the Midland LXT600): detailed model, LODs, baking, textures, p3d.

    python make_prints_lxt.py
    blender -b -P build_lxt.py -- [--high-only] [--skip-bake] [--no-previews]

Numbers live in layout_lxt.py. Kept as geometry through LOD2: the LCD bezel, buttons, knob,
antenna, PTT and clip; the speaker slots through LOD1; the battery door seams, screws and
microphone only in baking.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "_kit")))
import radiokit as K  # noqa: E402
import layout_lxt as L  # noqa: E402
from mathutils import Vector  # noqa: E402

TEX = os.path.normpath(os.path.join(HERE, "..", "textures"))


def P(name):
    return os.path.join(TEX, name)


def materials():
    front = dict(image=P("print_front.png"), rect=L.FRONT_RECT, axis="-Y")
    right = dict(image=P("print_right.png"), rect=L.RIGHT_RECT, axis="+X")
    back = dict(image=P("print_back.png"), rect=L.BACK_RECT, axis="+Y")
    ant = dict(image=P("print_antenna.png"), rect=L.ANT_RECT, axis="-Y", min_dot=0.3)
    return {
        "body": K.mat_worn("M_Body", (0.020, 0.020, 0.021), rough=(0.58, 0.78), edge_col=(0.075, 0.075, 0.075),
                           prints=[front, back], noise_bump=0.35),
        "clip": K.mat_worn("M_Clip", (0.020, 0.020, 0.021), rough=(0.58, 0.78), edge_col=(0.075, 0.075, 0.075),
                           noise_bump=0.35),
        "rubber": K.mat_worn("M_Buttons", (0.016, 0.016, 0.017), rough=(0.48, 0.64), edge_col=(0.07, 0.07, 0.07),
                             prints=[front, right]),
        "bezel": K.mat_worn("M_Bezel", (0.50, 0.51, 0.52), rough=(0.28, 0.42), metallic=0.35,
                            edge_col=(0.72, 0.72, 0.73), dust_amount=0.45, prints=[front]),
        "lcd": K.mat_worn("M_LCD", (0.2, 0.2, 0.2), rough=(0.07, 0.13), edge_amount=0.0, dust_amount=0.2,
                          soft_edges=0.0, image=(P("lcd.png"), L.LCD_RECT, "-Y")),
        "antenna": K.mat_worn("M_Antenna", (0.017, 0.017, 0.018), rough=(0.55, 0.72), edge_amount=0.35,
                              prints=[ant], noise_bump=0.2),
        "steel": K.mat_worn("M_Steel", (0.52, 0.51, 0.49), rough=(0.22, 0.38), metallic=1.0,
                            edge_col=(0.75, 0.74, 0.72), dust=(0.2, 0.17, 0.13)),
        "dark": K.mat_simple("M_Hole", (0.004, 0.004, 0.004), 0.9),
    }


# =============================================================================
# Parts
# =============================================================================
YP = L.YF + L.PANEL["depth"]        # floor of the recessed front panel


def shell(m):
    prof = K.rrect(L.W, L.YB - L.YF, (L.R_FRONT, L.R_BACK, L.R_BACK, L.R_FRONT), 0.0, (L.YF + L.YB) / 2,
                   seg=m.s(8, 3, 2, 1, 0))
    bm = K.prism(prof, 0.0, L.H, "Z")
    cuts = []
    p = L.PANEL
    cuts.append(K.prism(K.rrect(p["w"], p["z1"] - p["z0"], p["r"], 0.0, (p["z0"] + p["z1"]) / 2,
                                seg=m.s(6, 2, 1, 1, 0)), YP, L.YF - 0.003, "Y"))
    if m.upto(1):
        g = L.GRILLE
        slots = [K.prism(K.rrect(g["x1"] - g["x0"], g["h"], g["h"] / 2 * 0.98, (g["x0"] + g["x1"]) / 2, z,
                                 seg=m.s(6, 2)), YP + g["depth"], YP - 0.002, "Y") for z in g["zs"]]
        cuts.append(K.merge(*slots))
    if m.hi:
        mc = L.MIC
        cuts.append(K.prism(K.rrect(mc["w"], mc["h"], 0.0018, mc["x"], mc["z"], seg=4), YP + 0.0004, YP - 0.002, "Y"))
        cuts.append(K.cyl(mc["x"], mc["z"] - 0.0006, mc["hole_r"], YP + 0.003, YP - 0.002, 20, "Y"))
    m.add(bm, "body", name="Shell", bevel_=(L.BEV_TOP, (5, 2, 1, 0)), cuts=cuts, bevel_angle=50.0)


def antenna(m):
    a = L.ANT
    x, y = a["x"], a["y"]
    boss = K.cyl(x, y, a["boss_r"], L.H - 0.014, a["z0"], m.s(40, 14, 10, 8, 6), "Z")
    m.add(boss, "body", name="AntennaBoss", bevel_=(0.0022, (4, 1, 0)), bevel_angle=50.0)
    top = a["top"]
    if m.hi:
        prof = [(0.0, a["z0"] - 0.001), (a["r0"], a["z0"] - 0.001)]
        for i in range(3):          # three ring grooves at the base
            z = a["z0"] + 0.0030 + i * 0.0022
            prof += [(a["r0"], z - 0.0005), (a["r0"] - 0.0004, z), (a["r0"], z + 0.0005)]
        n = 12
        for i in range(1, n + 1):
            t = i / n
            prof.append((a["r0"] + (a["r1"] - a["r0"]) * t, a["z0"] + 0.011 + (top - 0.005 - a["z0"] - 0.011) * t))
        for k in range(1, 7):
            ang = math.radians(90 * k / 7)
            prof.append((a["r1"] * math.cos(ang), top - 0.005 + 0.005 * math.sin(ang)))
        prof.append((0.0, top))
    else:
        prof = [(0.0, a["z0"] - 0.001), (a["r0"], a["z0"] - 0.001), (a["r1"], top - 0.0035)]
        if m.q <= 2:
            prof.append((a["r1"] * 0.6, top - 0.0008))
        prof.append((0.0, top))
    m.add(K.lathe(prof, m.s(32, 12, 8, 6, 4), x, y, "Z"), "antenna", name="Antenna")


def knob(m):
    k = L.KNOB
    z1 = k["z0"] + k["h"]
    if m.upto(0):
        bm = K.prism(K.knurl(k["x"], k["y"], k["r_lo"], k["r_hi"], k["fins"], (0.0, 0.16, 0.42, 0.58)),
                     k["z0"] - 0.004, z1, "Z")
        m.add(bm, "rubber", name="Knob", bevel_=(0.0009, (4,)), bevel_angle=50.0)
        return
    if m.upto(3):
        bm = K.cyl(k["x"], k["y"], k["r_hi"] * 0.92, k["z0"] - 0.004, z1, m.s(0, 12, 8, 6), "Z")
        m.add(bm, "rubber", name="Knob", bevel_=(0.0012, (0, 1, 0)), bevel_angle=50.0)


def bezel(m):
    b, w = L.BEZEL, L.LCD_WIN
    yf = YP - b["proud"]
    bm = K.prism(K.rrect(b["w"], b["h"], b["r"], b["cx"], b["cz"], seg=m.s(8, 3, 2, 0)), YP + 0.0004, yf, "Y")
    cuts = []
    if m.upto(1):
        cuts.append(K.prism(K.rrect(w["w"], w["h"], w["r"], w["cx"], w["cz"], seg=m.s(4, 1)), yf - 0.001,
                            yf + w["depth"], "Y"))
    m.add(bm, "bezel", name="Bezel", bevel_=(0.0008, (3, 1, 0)), cuts=cuts, bevel_angle=50.0)
    y_lcd = yf + w["depth"] - 0.0001 if m.upto(1) else yf - 0.0001
    lcd = K.prism(K.rrect(w["w"] - 0.0003, w["h"] - 0.0003, w["r"], w["cx"], w["cz"], seg=m.s(4, 1, 0)),
                  y_lcd + 0.0003, y_lcd, "Y")
    m.add(lcd, "lcd", tag=K.T_LCD, name="LCD")


def button_outline(x, z, slant, row, seg):
    """Button: a rounded quadrilateral; the outer corner is chamfered on the end buttons (top one
    in the first row, bottom one in the second), as in the reference - the buttons follow the oval of the face."""
    w, h = L.BTN_W, L.BTN_H
    cut = 0.0016
    pts = [(x + w / 2, z - h / 2), (x + w / 2, z + h / 2), (x - w / 2, z + h / 2), (x - w / 2, z - h / 2)]
    if slant < 0:
        i = 2 if row == 1 else 3
        pts[i] = (pts[i][0] + cut, pts[i][1])
    elif slant > 0:
        i = 1 if row == 1 else 0
        pts[i] = (pts[i][0] - cut, pts[i][1])
    return K.rounded_poly(pts, 0.0017, seg) if seg else pts


def buttons(m):
    if not m.upto(2):
        return
    for x, z, slant, _t, _s in L.BUTTONS:
        row = 1 if abs(z - L.BTN_ROW1) < 1e-4 else 2
        bm = K.prism(button_outline(x, z, slant, row, m.s(4, 2, 0)), YP + 0.0004, YP - L.BTN_PROUD, "Y")
        m.add(bm, "rubber", tag=K.T_KEYS, name="Button", bevel_=(0.0007, (3, 1, 0)), bevel_angle=60.0)


def side_button(m, spec, right, name, ridges=0, lod_max=2):
    if not m.upto(lod_max):
        return
    yc, z0, z1, wy, proud = spec
    xs = L.W / 2 if right else -L.W / 2
    sgn = 1 if right else -1
    r = min(wy, z1 - z0) * 0.3
    bm = K.prism(K.rrect(wy, z1 - z0, r, yc, (z0 + z1) / 2, seg=m.s(5, 2, 0)), xs - sgn * 0.0015, xs + sgn * proud,
                 "X")
    cuts = None
    if m.hi and ridges:
        cuts = [K.prism(K.rect(wy + 0.002, 0.0005, yc, z0 + (z1 - z0) * f), xs + sgn * (proud - 0.0003),
                        xs + sgn * (proud + 0.002), "X") for f in (0.12, 0.88)]
    m.add(bm, "rubber", name=name, bevel_=(min(0.0009, proud * 0.45), (3, 1, 0)), cuts=cuts, bevel_angle=60.0)


def back_door(m):
    d = L.DOOR
    if m.upto(1):
        bm = K.prism(K.rrect(d["w"], d["z1"] - d["z0"], d["r"], 0.0, (d["z0"] + d["z1"]) / 2, seg=m.s(5, 2)),
                     L.YB - 0.001, L.YB + 0.0005, "Y")
        cuts = None
        if m.hi:     # latch: ridges at the bottom of the door
            cuts = [K.merge(*[K.prism(K.rect(0.012, 0.0005, 0.0, d["z0"] + 0.004 + i * 0.0011), L.YB + 0.0002,
                                      L.YB + 0.002, "Y") for i in range(4)])]
        m.add(bm, "body", name="BatteryDoor", bevel_=(0.0005, (3, 1)), cuts=cuts, bevel_angle=50.0)


def clip_offset(z):
    """Offset of the clip plate from the body: a pure shift, the plate stays FLAT. Bending it made
    a non-flat n-gon plate, and its fold triangulation gave a dark "diamond" in the middle."""
    return 0.0030 * (L.CLIP_TOP - z) / (L.CLIP_TOP - L.CLIP_BOT)


def belt_clip(m):
    y0 = L.YB + 0.0005
    if not m.upto(3):
        return
    mount = K.prism(K.rrect(0.020, 0.012, 0.003, 0.0, L.CLIP_TOP - 0.006, seg=m.s(4, 1, 0)), y0 - 0.0005,
                    y0 + 0.0035, "Y")
    m.add(mount, "clip", name="ClipMount", bevel_=(0.0007, (3, 1, 0)), bevel_angle=50.0)
    pts = K.rrect(L.CLIP_W, L.CLIP_TOP - L.CLIP_BOT, (0.005, 0.003, 0.003, 0.005), 0.0,
                  (L.CLIP_TOP + L.CLIP_BOT) / 2, seg=m.s(5, 2, 1, 0))
    pts = K.densify(pts, m.s(0.003, 0.008, 0.02, 0.05))
    bm = K.prism(pts, y0 + 0.0035, y0 + 0.0054, "Y")
    for v in bm.verts:
        v.co.y += clip_offset(v.co.z)
    K.fix_normals(bm)
    m.add(bm, "clip", name="ClipPlate", bevel_=(0.0006, (3, 1, 0)), bevel_angle=50.0)
    if m.hi:
        ys = y0 + 0.0054
        prof = [(0.0026, ys - 0.0002), (0.0026, ys + 0.0003), (0.0017, ys + 0.0009), (0.0, ys + 0.0011)]
        m.add(K.lathe(prof, 24, 0.0, L.CLIP_TOP - 0.006, "Y"), "steel", name="ClipScrew")



def build(m):
    shell(m)
    antenna(m)
    knob(m)
    bezel(m)
    buttons(m)
    side_button(m, L.PTT, True, "PTT", ridges=2)
    side_button(m, L.JACK, False, "JackCover", lod_max=1)
    back_door(m)
    belt_clip(m)


def collision(_lods):
    def bx(x0, x1, y0, y1, z0, z1):
        return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]

    body = bx(-L.W / 2, L.W / 2, L.YF, L.YB + 0.006, 0.0, L.H)
    k = L.KNOB
    body += [(k["x"] + k["r_hi"] * math.cos(i * math.pi / 3), k["y"] + k["r_hi"] * math.sin(i * math.pi / 3),
              k["z0"] + k["h"]) for i in range(6)]
    a = L.ANT
    ant = [(a["x"] + a["r0"] * math.cos(i * math.pi / 4), a["y"] + a["r0"] * math.sin(i * math.pi / 4), z)
           for i in range(8) for z in (L.H - 0.01, a["top"])]
    geom = [(body, ""), (ant, "")]
    view = [(body + ant, "")]
    fire = [(body, K.PEN + r"\plastic_material.rvmat"), (ant, K.PEN + r"\rubber.rvmat")]
    return geom, view, fire


SPEC = dict(
    name="lxt",
    stem="oz_radio_lxt",
    build=build,
    materials=materials,
    collision=collision,
    mass=0.22,
    grip_shift=0.01,           # shift in the hand grip, m (+ toward the antenna), at the owner's request 25.09
    body_top=L.H,
    previews=[
        ("front", 0, 4, 0.72, (0.0, 0.0, 0.098)),
        ("threeq", -32, 14, 0.42, (0.0, 0.0, 0.075)),
        ("close", 22, 8, 0.24, (0.0, -0.01, 0.075)),
        ("back", 148, 12, 0.42, (0.0, 0.0, 0.070)),
        ("right", 78, 6, 0.40, (0.0, 0.0, 0.080)),
        ("top", -25, 62, 0.34, (0.0, 0.0, 0.110)),
    ],
    bake=dict(cage=0.0025, ray=0.006, size=4096, out=2048),
)

if __name__ == "__main__":
    K.run(SPEC)
