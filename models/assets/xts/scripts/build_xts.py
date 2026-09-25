"""Radio with 5000 m range (modeled after the Motorola XTS5000): detailed model, LODs, baking, textures, p3d.

    python make_prints_xts.py
    blender -b -P build_xts.py -- [--high-only] [--skip-bake] [--no-previews]
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "_kit")))
import radiokit as K  # noqa: E402
import layout_xts as L  # noqa: E402
from mathutils import Vector  # noqa: E402

TEX = os.path.normpath(os.path.join(HERE, "..", "textures"))
YFF = L.YF - L.FACE["proud"]           # face of the front overlay


def P(name):
    return os.path.join(TEX, name)


def materials():
    front = dict(image=P("print_front.png"), rect=L.FRONT_RECT, axis="-Y")
    top = dict(image=P("print_top.png"), rect=L.TOP_RECT, axis="+Z")
    back = dict(image=P("print_back.png"), rect=L.BACK_RECT, axis="+Y")
    return {
        "body": K.mat_worn("M_Body", (0.016, 0.016, 0.017), rough=(0.5, 0.68), edge_col=(0.08, 0.08, 0.085),
                           prints=[back, top], noise_bump=0.3),
        "clip": K.mat_worn("M_Clip", (0.016, 0.016, 0.017), rough=(0.5, 0.68), edge_col=(0.08, 0.08, 0.085),
                           noise_bump=0.3),
        "face": K.mat_worn("M_Face", (0.014, 0.014, 0.015), rough=(0.42, 0.6), edge_col=(0.075, 0.075, 0.08),
                           prints=[front], noise_bump=0.3),
        "frame": K.mat_worn("M_Frame", (0.085, 0.086, 0.09), rough=(0.38, 0.52), edge_col=(0.22, 0.22, 0.23),
                            prints=[front]),
        "nav": K.mat_worn("M_Nav", (0.36, 0.37, 0.39), rough=(0.32, 0.45), edge_col=(0.6, 0.6, 0.62), prints=[front]),
        "keys": K.mat_worn("M_Keys", (0.012, 0.012, 0.013), rough=(0.25, 0.42), edge_col=(0.10, 0.10, 0.11),
                           prints=[front]),
        "rubber": K.mat_worn("M_Rubber", (0.013, 0.013, 0.014), rough=(0.6, 0.8), edge_col=(0.06, 0.06, 0.06),
                             edge_amount=0.6, prints=[top]),
        "purple": K.mat_worn("M_Purple", (0.10, 0.06, 0.38), rough=(0.3, 0.45), edge_col=(0.3, 0.25, 0.6)),
        "lcd": K.mat_worn("M_LCD", (0.2, 0.2, 0.2), rough=(0.06, 0.12), edge_amount=0.0, dust_amount=0.2,
                          soft_edges=0.0, image=(P("lcd.png"), L.LCD_RECT, "-Y")),
        "steel": K.mat_worn("M_Steel", (0.55, 0.54, 0.52), rough=(0.22, 0.36), metallic=1.0,
                            edge_col=(0.78, 0.77, 0.75)),
        "brass": K.mat_simple("M_Brass", (0.55, 0.40, 0.18), 0.3, metallic=1.0),
        "antenna": K.mat_worn("M_Antenna", (0.012, 0.012, 0.013), rough=(0.5, 0.7), edge_amount=0.3),
    }


def ellipse(x, z, rx, rz, n):
    return [(x + rx * math.cos(2 * math.pi * i / n), z + rz * math.sin(2 * math.pi * i / n)) for i in range(n)]


def shell(m):
    prof = K.rrect(L.W, L.YB - L.YF, (L.R_FRONT, L.R_BACK, L.R_BACK, L.R_FRONT), 0.0, (L.YF + L.YB) / 2,
                   seg=m.s(6, 2, 1, 0))
    m.add(K.prism(prof, 0.0, L.H, "Z"), "body", name="Shell", bevel_=(L.BEV_TB, (4, 1, 0)), bevel_angle=45.0)


def face(m):
    f = L.FACE
    bm = K.prism(K.rrect(f["w"], f["z1"] - f["z0"], f["r"], 0.0, (f["z0"] + f["z1"]) / 2, seg=m.s(6, 2, 1, 0)),
                 L.YF + 0.001, YFF, "Y")
    cuts = None
    if m.hi:
        g = L.GRILLE
        holes = []
        nx = int(round((g["x1"] - g["x0"]) / g["pitch"])) + 1
        nz = int(round((g["z1"] - g["z0"]) / g["pitch"])) + 1
        for i in range(nx):
            for j in range(nz):
                x, z = g["x0"] + i * g["pitch"], g["z0"] + j * g["pitch"]
                # like in the reference - a grille with gaps: corners are cut, every other one along the edges
                edge = i in (0, nx - 1) or j in (0, nz - 1)
                if (i + j) % 2 and edge:
                    continue
                if (i in (0, nx - 1)) and (j in (0, nz - 1)):
                    continue
                holes.append(K.prism(K.rrect(g["hole"], g["hole"], 0.0003, x, z, seg=2), YFF + g["depth"], YFF - 0.002,
                                     "Y"))
        cuts = [K.merge(*holes)]
    m.add(bm, "face", name="Face", bevel_=(0.0010, (3, 1, 0)), cuts=cuts, bevel_angle=45.0)


def lcd_frame(m):
    fr, w = L.LCD_FRAME, L.LCD_WIN
    yf = YFF - fr["proud"]
    bm = K.prism(K.rrect(fr["w"], fr["z1"] - fr["z0"], fr["r"], 0.0, (fr["z0"] + fr["z1"]) / 2, seg=m.s(5, 2, 1, 0)),
                 YFF + 0.0004, yf, "Y")
    cuts = []
    if m.upto(1):
        cuts.append(K.prism(K.rrect(w["w"], w["h"], w["r"], w["cx"], w["cz"], seg=m.s(4, 1)), yf - 0.001,
                            yf + w["depth"], "Y"))
    if m.hi:     # partitions between the programmable keys
        for x in (-0.0059, 0.0059):
            cuts.append(K.prism(K.rect(0.0004, 0.0090, x, 0.0670), yf - 0.001, yf + 0.0004, "Y"))
    m.add(bm, "frame", name="LcdFrame", bevel_=(0.0008, (3, 1, 0)), cuts=cuts, bevel_angle=45.0)
    y_lcd = yf + w["depth"] - 0.0001 if m.upto(1) else yf - 0.0001
    m.add(K.prism(K.rrect(w["w"] - 0.0003, w["h"] - 0.0003, w["r"], w["cx"], w["cz"], seg=m.s(4, 1, 0)),
                  y_lcd + 0.0003, y_lcd, "Y"), "lcd", tag=K.T_LCD, name="LCD")
    if m.upto(2):
        for x, z in L.SOFTKEYS:
            bm = K.prism(K.rrect(L.SOFTKEY["w"], L.SOFTKEY["h"], 0.0018, x, z, seg=m.s(4, 2, 0)), yf + 0.0003,
                         yf - 0.0010, "Y")
            m.add(bm, "frame", tag=K.T_KEYS, name="SoftKey", bevel_=(0.0005, (3, 1, 0)), bevel_angle=60.0)


def keypad(m):
    if not m.upto(2):
        return
    n = L.NAV
    nav = K.prism(ellipse(n["x"], n["z"], n["rx"], n["rz"], m.s(48, 16, 10)), YFF + 0.0004, YFF - 0.0016, "Y")
    cuts = [K.prism(ellipse(n["x"], n["z"], n["rx"] * 0.52, n["rz"] * 0.45, 32), YFF - 0.0030, YFF - 0.0010, "Y")] \
        if m.hi else None
    m.add(nav, "nav", tag=K.T_KEYS, name="NavPad", bevel_=(0.0008, (3, 1, 0)), cuts=cuts, bevel_angle=50.0)
    for x, z in L.NAV_SIDE:
        bm = K.prism(ellipse(x, z, 0.0034, 0.0042, m.s(28, 10, 6)), YFF + 0.0004, YFF - L.KEY_PROUD, "Y")
        m.add(bm, "keys", tag=K.T_KEYS, name="NavSide", bevel_=(0.0008, (3, 1, 0)), bevel_angle=50.0)
    for row, z in zip(L.KEYS, L.KEY_ROWS):
        for _, x in zip(row, L.KEY_COLS):
            bm = K.prism(ellipse(x, z, L.KEY_RX, L.KEY_RZ, m.s(32, 12, 6)), YFF + 0.0004, YFF - L.KEY_PROUD, "Y")
            m.add(bm, "keys", tag=K.T_KEYS, name="Key", bevel_=(0.0008, (3, 1, 0)), bevel_angle=50.0)


def top(m):
    v, c, t, a = L.VOL, L.CHAN, L.TOGGLE, L.ANT
    # volume knob: a knurled cylinder with a dome
    if m.hi:
        m.add(K.prism(K.knurl(v["x"], v["y"], v["r"] * 0.92, v["r"], 22, (0.0, 0.2, 0.5, 0.7)), v["z0"],
                      v["z0"] + v["h"] * 0.7, "Z"), "rubber", name="Volume", bevel_=(0.0003, (2,)), bevel_angle=60.0)
        prof = [(0.0, v["z0"] + v["h"] * 0.68), (v["r"] * 0.97, v["z0"] + v["h"] * 0.68)]
        for k in range(1, 7):
            ang = math.radians(90 * k / 7)
            prof.append((v["r"] * 0.97 * math.cos(ang), v["z0"] + v["h"] * 0.68 + v["h"] * 0.32 * math.sin(ang)))
        prof.append((0.0, v["z0"] + v["h"]))
        m.add(K.lathe(prof, 36, v["x"], v["y"], "Z"), "rubber", name="VolumeDome")
    else:
        m.add(K.cyl(v["x"], v["y"], v["r"] * 0.97, L.H - 0.001, v["z0"] + v["h"] * 0.9, m.s(0, 14, 8, 6, 5), "Z"),
              "rubber", name="Volume", bevel_=(0.0012, (0, 1, 0)), bevel_angle=60.0)
    # channel switch: a cylinder + a T-shaped head
    if m.upto(3):
        m.add(K.cyl(c["x"], c["y"], c["r"], L.H - 0.001, c["z0"] + 0.0055, m.s(36, 12, 8, 6), "Z"), "rubber",
              name="ChanBase", bevel_=(0.0006, (3, 1, 0)), bevel_angle=60.0)
        grip = K.prism(K.rrect(c["grip_w"], c["grip_t"], c["grip_t"] * 0.45, c["x"], c["y"], seg=m.s(4, 2, 0)),
                       c["z0"] + 0.004, c["z0"] + c["h"], "Z")
        m.add(grip, "rubber", name="ChanGrip", bevel_=(0.0015, (4, 1, 0)), bevel_angle=45.0)
    if m.hi:
        m.add(K.cyl(t["x"], t["y"], 0.0022, L.H - 0.001, L.H + 0.0015, 20, "Z"), "steel", name="ToggleNut")
        lever = K.cyl(t["x"], t["y"], 0.0009, L.H + 0.001, L.H + t["h"], 12, "Z")
        K.rotate(lever, 18.0, "Y", (t["x"], t["y"], L.H + 0.001))
        m.add(lever, "steel", name="ToggleLever")
    # antenna: a knurled base and a thin whip with a ball
    zb, zt = a["z_base"], a["top"]
    if m.hi:
        prof = [(0.0, L.H - 0.001), (a["base_r"], L.H - 0.001)]
        for i in range(4):
            z = L.H + 0.003 + i * 0.0030
            prof += [(a["base_r"], z - 0.0008), (a["base_r"] - 0.0006, z), (a["base_r"], z + 0.0008)]
        prof += [(a["base_r"] * 0.92, zb - 0.002), (a["whip_r0"] + 0.0008, zb), (a["whip_r0"], zb + 0.004)]
        for i in range(1, 13):
            tt = i / 12
            prof.append((a["whip_r0"] + (a["whip_r1"] - a["whip_r0"]) * tt, zb + 0.004 + (zt - 0.006 - zb - 0.004) * tt))
        for k in range(0, 7):
            ang = math.radians(-90 + 180 * k / 6)
            prof.append((0.0032 * math.cos(ang), zt - 0.0032 + 0.0032 * math.sin(ang)))
        m.add(K.lathe(prof, 24, a["x"], a["y"], "Z"), "antenna", name="Antenna")
    else:
        prof = [(0.0, L.H - 0.001), (a["base_r"], L.H - 0.001), (a["base_r"] * 0.9, zb), (a["whip_r0"], zb + 0.004)]
        if m.q <= 2:
            prof.append((a["whip_r1"], zt - 0.006))
            prof.append((0.0032, zt - 0.003))
        prof.append((0.0, zt))
        m.add(K.lathe(prof, m.s(0, 8, 6, 5, 4), a["x"], a["y"], "Z"), "antenna", name="Antenna")


def left_side(m):
    xs = -L.W / 2
    p = L.PTT
    if m.upto(2):
        n = m.s(40, 14, 8)
        bm = K.prism(ellipse(p["y"], p["z"], p["r"] * 0.82, p["r"] * 1.15, n), xs + 0.0015, xs - p["proud"], "X")
        cuts = None
        if m.hi:     # PTT knurling: transverse grooves
            cuts = [K.merge(*[K.prism(K.rect(0.03, 0.0006, p["y"], p["z"] + (i - 3) * 0.0028), xs - p["proud"] + 0.0004,
                                      xs - p["proud"] - 0.002, "X") for i in range(7)])]
        m.add(bm, "rubber", name="PTT", bevel_=(0.0012, (3, 1, 0)), cuts=cuts, bevel_angle=50.0)
    b = L.TOP_BTN
    if m.upto(1):
        m.add(K.cyl(b["y"], b["z"], b["r"], xs + 0.0012, xs - b["proud"], m.s(28, 10), "X"), "purple", name="TopBtn",
              bevel_=(0.0008, (3, 1)), bevel_angle=50.0)
    if m.hi:
        for y, z in L.SIDE_SMALL:
            m.add(K.cyl(y, z, 0.0016, xs + 0.001, xs - 0.0009, 20, "X"), "rubber", name="SideSmall",
                  bevel_=(0.0004, (2,)))


def battery(m):
    b = L.BAT
    yc = (b["y0"] + b["y1"]) / 2
    prof = K.rrect(b["w"], b["y1"] - b["y0"] + 0.001, (0.001, 0.005, 0.005, 0.001), 0.0, yc, seg=m.s(5, 2, 1, 0))
    m.add(K.prism(prof, 0.001, b["top"], "Z"), "body", name="Battery", bevel_=(0.0018, (3, 1, 0)), bevel_angle=50.0)


def clip_offset(z):
    """Offset of the clip plate from the body: a pure shift, the plate stays FLAT. Bending produced
    a non-flat n-gon cap, and its fold triangulation gave a dark "diamond" in the middle."""
    return 0.0038 * (L.CLIP_TOP - z) / (L.CLIP_TOP - L.CLIP_BOT)


def belt_clip(m):
    if not m.upto(3):
        return
    y0 = L.BAT["y1"] + 0.0005
    mount = K.prism(K.rrect(0.026, 0.016, 0.003, 0.0, L.CLIP_TOP - 0.008, seg=m.s(4, 1, 0)), y0 - 0.001, y0 + 0.0040,
                    "Y")
    m.add(mount, "clip", name="ClipMount", bevel_=(0.0008, (3, 1, 0)), bevel_angle=50.0)
    pts = K.rrect(L.CLIP_W, L.CLIP_TOP - L.CLIP_BOT, (0.006, 0.003, 0.003, 0.006), 0.0,
                  (L.CLIP_TOP + L.CLIP_BOT) / 2, seg=m.s(5, 2, 1, 0))
    pts = K.densify(pts, m.s(0.003, 0.008, 0.02, 0.05))
    bm = K.prism(pts, y0 + 0.0040, y0 + 0.0062, "Y")
    for v in bm.verts:
        v.co.y += clip_offset(v.co.z)
    K.fix_normals(bm)
    m.add(bm, "clip", name="ClipPlate", bevel_=(0.0007, (3, 1, 0)), bevel_angle=50.0)



def build(m):
    shell(m)
    face(m)
    lcd_frame(m)
    keypad(m)
    top(m)
    left_side(m)
    battery(m)
    belt_clip(m)


def collision(_lods):
    def bx(x0, x1, y0, y1, z0, z1):
        return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]

    body = bx(-L.W / 2, L.W / 2, YFF - 0.002, L.BAT["y1"] + 0.007, 0.0, L.H)
    for kn in (L.VOL, L.CHAN):
        body += [(kn["x"] + kn["r"] * math.cos(i * math.pi / 3), kn["y"] + kn["r"] * math.sin(i * math.pi / 3),
                  kn["z0"] + kn["h"]) for i in range(6)]
    a = L.ANT
    ant = [(a["x"] + a["base_r"] * math.cos(i * math.pi / 4), a["y"] + a["base_r"] * math.sin(i * math.pi / 4), z)
           for i in range(8) for z in (L.H, a["top"])]
    geom = [(body, ""), (ant, "")]
    view = [(body, "")]
    fire = [(body, K.PEN + r"\plastic_material.rvmat"), (ant, K.PEN + r"\rubber.rvmat")]
    return geom, view, fire


SPEC = dict(
    name="xts",
    stem="oz_radio_xts",
    build=build,
    materials=materials,
    collision=collision,
    mass=0.40,
    grip_shift=-0.02,           # shift in the hand grip, m (+ toward the antenna), at the owner's request, 25.09
    body_top=L.H,
    previews=[
        ("front", 0, 4, 0.82, (0.0, 0.0, 0.150)),
        ("threeq", -32, 14, 0.50, (0.0, 0.0, 0.090)),
        ("close", -15, 10, 0.26, (0.0, -0.01, 0.060)),
        ("back", 148, 12, 0.50, (0.0, 0.0, 0.080)),
        ("left", -80, 6, 0.46, (0.0, 0.0, 0.090)),
        ("top", 20, 60, 0.30, (0.0, 0.0, 0.165)),
    ],
    bake=dict(cage=0.0025, ray=0.006, size=4096, out=2048),
)

if __name__ == "__main__":
    K.run(SPEC)
