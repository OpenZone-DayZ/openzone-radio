"""Radio, 10000 m range (inspired by the AN/PRC-152): detailed model, LODs, baking, textures, p3d.

    python make_prints_prc152.py
    blender -b -P build_prc152.py -- [--high-only] [--skip-bake] [--no-previews]

The body is the face outline with a "waist" at the keypad, extruded in depth and beveled along the
edges; below it a separate, large battery. The speaker grille and the LCD and keypad recesses are cutouts; the keys and the PRE rocker sit on a rubber mat.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "_kit")))
import radiokit as K  # noqa: E402
import layout_prc152 as L  # noqa: E402
from mathutils import Vector  # noqa: E402

TEX = os.path.normpath(os.path.join(HERE, "..", "textures"))
GREEN = (0.038, 0.045, 0.026)


def P(name):
    return os.path.join(TEX, name)


def materials():
    front = dict(image=P("print_front.png"), rect=L.FRONT_RECT, axis="-Y")
    back = dict(image=P("print_back.png"), rect=L.BACK_RECT, axis="+Y")
    knob = dict(image=P("print_knob.png"), rect=L.KNOB_RECT, axis="-Y", min_dot=0.15)
    dust = (0.19, 0.17, 0.13)
    return {
        "body": K.mat_worn("M_Body", GREEN, rough=(0.5, 0.7), edge_col=(0.12, 0.13, 0.09), dust=dust,
                           dust_amount=0.5, prints=[front], noise_bump=0.2),
        "battery": K.mat_worn("M_Battery", (0.031, 0.035, 0.023), rough=(0.55, 0.72), edge_col=(0.15, 0.16, 0.12),
                              dust=dust, dust_amount=0.55, prints=[back], noise_bump=0.25),
        "plate": K.mat_worn("M_DataPlate", (0.52, 0.52, 0.50), rough=(0.3, 0.45), metallic=0.9,
                            edge_col=(0.75, 0.75, 0.73), dust=dust, prints=[back]),
        "keymat": K.mat_worn("M_KeyMat", (0.012, 0.012, 0.012), rough=(0.6, 0.78), edge_col=(0.05, 0.05, 0.05),
                             edge_amount=0.4, dust=dust),
        "keys": K.mat_worn("M_Keys", (0.014, 0.014, 0.015), rough=(0.35, 0.52), edge_col=(0.10, 0.10, 0.10),
                           dust=dust, prints=[front]),
        "rubber": K.mat_worn("M_Rubber", (0.014, 0.014, 0.014), rough=(0.62, 0.82), edge_col=(0.07, 0.07, 0.07),
                             edge_amount=0.5, dust=dust, prints=[knob]),
        "silver": K.mat_worn("M_Silver", (0.56, 0.56, 0.55), rough=(0.22, 0.36), metallic=1.0,
                             edge_col=(0.80, 0.80, 0.78), dust=dust),
        "gold": K.mat_simple("M_Pins", (0.80, 0.60, 0.28), 0.3, metallic=1.0),
        "insert": K.mat_simple("M_Insert", (0.02, 0.02, 0.02), 0.6),
        "lcd": K.mat_worn("M_LCD", (0.2, 0.2, 0.2), rough=(0.06, 0.12), edge_amount=0.0, dust=dust,
                          dust_amount=0.25, soft_edges=0.0, image=(P("lcd.png"), L.LCD_RECT, "-Y")),
        "antenna": K.mat_worn("M_Antenna", (0.013, 0.013, 0.013), rough=(0.55, 0.75), edge_amount=0.3, dust=dust),
    }


def waist(z):
    w = L.WAIST
    return w["depth"] * math.exp(-((z - w["z"]) / w["width"]) ** 2)


def body_outline(seg, n_side):
    r = 0.0075
    z0, z1 = L.Z_BAT - 0.0012, L.H - r
    zs = [z0 + (z1 - z0) * i / n_side for i in range(n_side + 1)]
    right = [(L.W / 2 - waist(z), z) for z in zs]
    left = [(-(L.W / 2 - waist(z)), z) for z in reversed(zs)]
    if seg:
        tr = K.arc(L.W / 2 - r, L.H - r, r, 0.0, math.pi / 2, seg)[1:]
        tl = K.arc(-L.W / 2 + r, L.H - r, r, math.pi / 2, math.pi, seg)[:-1]
    else:
        tr, tl = [(L.W / 2, L.H)], [(-L.W / 2, L.H)]
    return right + tr + tl + left


def body(m):
    bm = K.prism(body_outline(m.s(8, 3, 2, 1, 0), m.s(24, 8, 4, 2, 1)), L.YF, L.YB, "Y")
    cuts = []
    lf, kp = L.LCD_FRAME, L.KEYPAD
    if m.upto(1):
        cuts.append(K.prism(K.rrect(lf["w"], lf["h"], lf["r"], lf["cx"], lf["cz"], seg=m.s(4, 2)), L.YF + lf["depth"],
                            L.YF - 0.003, "Y"))
    cuts.append(K.prism(K.rrect(kp["x1"] - kp["x0"], kp["z1"] - kp["z0"], kp["r"], (kp["x0"] + kp["x1"]) / 2,
                                (kp["z0"] + kp["z1"]) / 2, seg=m.s(6, 2, 1, 0)), L.YF + kp["depth"], L.YF - 0.003, "Y"))
    if m.hi:
        g = L.GRID
        slots = []
        for row, cols in L.GRID_CELLS.items():
            zc = g["z0"] + (3 - row) * g["pitch_z"]
            for col in cols:
                xc = g["x0"] + col * g["pitch_x"]
                for dz in (-1, 1):
                    z = zc + dz * (g["slot_h"] + g["gap"]) / 2
                    slots.append(K.prism(K.rrect(g["slot_w"], g["slot_h"], g["slot_h"] * 0.45, xc, z, seg=3),
                                         L.YF + g["depth"], L.YF - 0.002, "Y"))
        cuts.append(K.merge(*slots))
        # screws at the back corners
    m.add(bm, "body", name="Body", bevel_=(L.BEV, (4, 1, 0)), cuts=cuts or None, bevel_angle=45.0)
    if m.hi:
        for sx in (-1, 1):
            for z in (L.Z_BAT + 0.008, L.H - 0.010):
                prof = [(0.0021, L.YB - 0.0003), (0.0021, L.YB + 0.0002), (0.0014, L.YB + 0.0006),
                        (0.0, L.YB + 0.0007)]
                x = sx * (L.W / 2 - 0.0065)
                cross = [K.prism(K.rect(0.0028, 0.0005, x, z), L.YB + 0.0003, L.YB + 0.002, "Y"),
                         K.prism(K.rect(0.0005, 0.0028, x, z), L.YB + 0.0003, L.YB + 0.002, "Y")]
                m.add(K.lathe(prof, 24, x, z, "Y"), "silver", name="BackScrew", cuts=cross)


def lcd(m):
    w, lf = L.LCD_WIN, L.LCD_FRAME
    y_floor = L.YF + lf["depth"] if m.upto(1) else L.YF
    y_lcd = y_floor - 0.0001
    m.add(K.prism(K.rrect(w["w"], w["h"], w["r"], w["cx"], w["cz"], seg=m.s(4, 1, 0)), y_floor + 0.0003, y_lcd, "Y"),
          "lcd", tag=K.T_LCD, name="LCD")


def keypad(m):
    kp = L.KEYPAD
    floor = L.YF + kp["depth"]
    mat_top = floor - 0.0007
    if m.upto(2):
        mat = K.prism(K.rrect(kp["x1"] - kp["x0"] - 0.0006, kp["z1"] - kp["z0"] - 0.0006, kp["r"] - 0.0003,
                              (kp["x0"] + kp["x1"]) / 2, (kp["z0"] + kp["z1"]) / 2, seg=m.s(6, 2, 1)),
                      floor + 0.0003, mat_top, "Y")
        m.add(mat, "keymat", name="KeyMat", bevel_=(0.0004, (2, 1, 0)), bevel_angle=50.0)
    if not m.upto(2):
        return
    for row, z in zip(L.KEYS, L.KEY_ROWS):
        for key, x in zip(row, L.KEY_COLS):
            if key is None:
                continue
            bm = K.prism(K.rrect(L.KEY_W, L.KEY_H, L.KEY_R, x, z, seg=m.s(4, 2, 0)), mat_top + 0.0003,
                         mat_top - L.KEY_PROUD, "Y")
            m.add(bm, "keys", tag=K.T_KEYS, name="Key", bevel_=(0.0009, (3, 1, 0)), bevel_angle=60.0)
    p = L.PRE
    bm = K.prism(K.rrect(L.KEY_W, p["z1"] - p["z0"], 0.0030, p["x"], (p["z0"] + p["z1"]) / 2, seg=m.s(5, 2, 0)),
                 mat_top + 0.0003, mat_top - L.KEY_PROUD, "Y")
    m.add(bm, "keys", tag=K.T_KEYS, name="PreRocker", bevel_=(0.0010, (3, 1, 0)), bevel_angle=60.0)


def battery(m):
    b = L.BAT
    prof = K.rrect(b["w"], b["yb"] - b["yf"], 0.0045, 0.0, (b["yf"] + b["yb"]) / 2, seg=m.s(6, 2, 1, 0))
    bm = K.prism(prof, 0.0, L.Z_BAT + 0.0015, "Z")
    cuts = None
    if m.hi:     # latch groove around the perimeter and ribs on the face
        cuts = [K.ring_prism(K.rrect(b["w"] + 0.004, b["yb"] - b["yf"] + 0.004, 0.006, 0.0, (b["yf"] + b["yb"]) / 2, 6),
                             K.rrect(b["w"] - 0.0010, b["yb"] - b["yf"] - 0.0010, 0.0040, 0.0, (b["yf"] + b["yb"]) / 2,
                                     6), b["latch_z"] - 0.0006, b["latch_z"] + 0.0006, "Z")]
    m.add(bm, "battery", name="Battery", bevel_=(0.0025, (4, 1, 0)), cuts=cuts, bevel_angle=45.0)


def top(m):
    c, k, a = L.CONN, L.KNOB, L.ANT
    # headset connector
    if m.hi:
        m.add(K.prism(K.circle(c["x"], c["y"], c["r"] * 1.12, 6, math.radians(30)), L.H - 0.001, L.H + 0.0030, "Z"),
              "insert", name="ConnNut", bevel_=(0.0004, (2,)))
        m.add(K.prism(K.knurl(c["x"], c["y"], c["r"] * 0.95, c["r"], 36, (0.0, 0.25, 0.5, 0.75)), L.H + 0.0028,
                      L.H + c["h"] - 0.004, "Z"), "silver", name="ConnRing", bevel_=(0.0003, (2,)), bevel_angle=60.0)
        m.add(K.cyl(c["x"], c["y"], c["r"] * 0.93, L.H + c["h"] - 0.0045, L.H + c["h"], 40, "Z"), "silver",
              name="ConnLip", bevel_=(0.0006, (3,)), cuts=[K.cyl(c["x"], c["y"], c["r"] * 0.72, L.H + c["h"] - 0.004,
                                                                   L.H + c["h"] + 0.001, 40, "Z")])
        m.add(K.cyl(c["x"], c["y"], c["r"] * 0.73, L.H + c["h"] - 0.006, L.H + c["h"] - 0.0035, 40, "Z"), "insert",
              name="ConnInsert")
        for i in range(6):
            ang = 2 * math.pi * i / 6
            m.add(K.cyl(c["x"] + 0.0033 * math.cos(ang), c["y"] + 0.0033 * math.sin(ang), 0.0006,
                        L.H + c["h"] - 0.0040, L.H + c["h"] - 0.0015, 12, "Z"), "gold", name="ConnPin")
    elif m.upto(3):
        m.add(K.cyl(c["x"], c["y"], c["r"], L.H - 0.001, L.H + c["h"], m.s(0, 12, 8, 6), "Z"), "silver", name="Conn",
              bevel_=(0.0008, (0, 1, 0)), bevel_angle=60.0)
    # knob
    if m.hi:
        m.add(K.prism(K.knurl(k["x"], k["y"], k["r"] * 0.94, k["r"], k["teeth"], (0.0, 0.14, 0.5, 0.64)),
                      L.H - 0.001, L.H + k["h"] * 0.45, "Z"), "rubber", name="KnobRibs", bevel_=(0.0004, (2,)),
              bevel_angle=60.0)
        m.add(K.cyl(k["x"], k["y"], k["r"], L.H + k["h"] * 0.44, L.H + k["h"], 48, "Z"), "rubber", name="KnobCap",
              bevel_=(0.0012, (4,)))
        ridge = K.prism(K.rrect(k["r"] * 1.6, 0.0030, 0.0012, k["x"], k["y"], seg=3), L.H + k["h"] - 0.0005,
                        L.H + k["h"] + 0.0025, "Z")
        m.add(ridge, "rubber", name="KnobRidge", bevel_=(0.0008, (3,)))
    else:
        m.add(K.cyl(k["x"], k["y"], k["r"], L.H - 0.001, L.H + k["h"], m.s(0, 16, 10, 8, 6), "Z"), "rubber",
              name="Knob", bevel_=(0.0012, (0, 1, 0)), bevel_angle=60.0)
    # antenna: TNC nut, spring section, thick whip
    x, y = a["x"], a["y"]
    if m.upto(2):
        m.add(K.prism(K.circle(x, y, a["nut_r"], 6, math.radians(30)), L.H - 0.001, a["z_nut"], "Z"), "silver",
              name="AntNut", bevel_=(0.0004, (2, 0)))
    zs, zt = a["z_spring"], a["top"]
    if m.hi:
        prof = [(0.0, a["z_nut"] - 0.001), (a["base_r"], a["z_nut"] - 0.001)]
        n_r = 9
        for i in range(n_r):
            z = a["z_nut"] + 0.0015 + i * (zs - a["z_nut"] - 0.003) / (n_r - 1)
            prof += [(a["base_r"], z - 0.0009), (a["base_r"] - 0.0007, z), (a["base_r"], z + 0.0009)]
        prof += [(a["base_r"], zs), (a["whip_r0"], zs + 0.002)]
        for i in range(1, 13):
            t = i / 12
            prof.append((a["whip_r0"] + (a["whip_r1"] - a["whip_r0"]) * t, zs + 0.002 + (zt - 0.006 - zs - 0.002) * t))
        for kk in range(1, 7):
            ang = math.radians(90 * kk / 7)
            prof.append((a["whip_r1"] * math.cos(ang), zt - 0.006 + 0.006 * math.sin(ang)))
        prof.append((0.0, zt))
    else:
        prof = [(0.0, a["z_nut"] - 0.001), (a["base_r"], a["z_nut"] - 0.001), (a["base_r"], zs), (a["whip_r0"], zs + 0.002)]
        if m.q <= 2:
            prof.append((a["whip_r1"], zt - 0.005))
            prof.append((a["whip_r1"] * 0.6, zt - 0.001))
        prof.append((0.0, zt))
    m.add(K.lathe(prof, m.s(28, 10, 8, 6, 4), x, y, "Z"), "antenna", name="Antenna")


def sides(m):
    xs = -L.W / 2 + waist((L.PTT[1] + L.PTT[2]) / 2)
    if m.upto(2):
        yc, z0, z1, wy, proud = L.PTT
        bm = K.prism(K.rrect(wy, z1 - z0, 0.004, yc, (z0 + z1) / 2, seg=m.s(5, 2, 0)), xs + 0.0020, xs - proud, "X")
        cuts = None
        if m.hi:
            cuts = [K.merge(*[K.prism(K.rect(wy + 0.002, 0.0008, yc, z0 + (z1 - z0) * (i + 1) / 9), xs - proud + 0.0005,
                                      xs - proud - 0.002, "X") for i in range(8)])]
        m.add(bm, "rubber", name="PTT", bevel_=(0.0012, (3, 1, 0)), cuts=cuts, bevel_angle=60.0)
    if m.upto(1):
        for yc, zc, r in L.SIDE_BTNS:
            m.add(K.cyl(yc, zc, r / 2, -L.W / 2 + 0.0015, -L.W / 2 - 0.0016, m.s(24, 10), "X"), "rubber",
                  name="SideBtn", bevel_=(0.0005, (3, 1)), bevel_angle=50.0)
        yc, z0, z1, wy, proud = L.DATA_COVER
        xr = L.W / 2 - waist((z0 + z1) / 2)
        bm = K.prism(K.rrect(wy, z1 - z0, 0.003, yc, (z0 + z1) / 2, seg=m.s(5, 2)), xr - 0.0015, xr + proud, "X")
        m.add(bm, "rubber", name="DataCover", bevel_=(0.0007, (3, 1)), bevel_angle=60.0)


def data_plate(m):
    if not m.upto(1):
        return
    p = L.PLATE
    bm = K.prism(K.rrect(p["w"], p["z1"] - p["z0"], p["r"], 0.0, (p["z0"] + p["z1"]) / 2, seg=m.s(4, 1)),
                 L.YB - 0.0004, L.YB + 0.0005, "Y")
    m.add(bm, "plate", name="DataPlate", bevel_=(0.0002, (2, 0)), bevel_angle=50.0)
    if m.hi:
        for sx in (-1, 1):
            for z in (p["z0"] + 0.0025, p["z1"] - 0.0025):
                prof = [(0.0010, L.YB + 0.0003), (0.0010, L.YB + 0.0006), (0.0006, L.YB + 0.0009), (0.0, L.YB + 0.0010)]
                m.add(K.lathe(prof, 16, sx * (p["w"] / 2 - 0.0025), z, "Y"), "silver", name="Rivet")



def build(m):
    body(m)
    lcd(m)
    keypad(m)
    battery(m)
    top(m)
    sides(m)
    data_plate(m)


def collision(_lods):
    def bx(x0, x1, y0, y1, z0, z1):
        return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]

    body = bx(-L.W / 2, L.W / 2, L.YF - 0.002, L.YB + 0.001, 0.0, L.H)
    for kn, hh in ((L.CONN, L.CONN["h"]), (L.KNOB, L.KNOB["h"] + 0.0025)):
        body += [(kn["x"] + kn["r"] * math.cos(i * math.pi / 3), kn["y"] + kn["r"] * math.sin(i * math.pi / 3),
                  L.H + hh) for i in range(6)]
    a = L.ANT
    ant = [(a["x"] + a["base_r"] * math.cos(i * math.pi / 4), a["y"] + a["base_r"] * math.sin(i * math.pi / 4), z)
           for i in range(8) for z in (L.H, a["top"])]
    geom = [(body, ""), (ant, "")]
    view = [(body, "")]
    fire = [(body, K.PEN + r"\plastic_material.rvmat"), (ant, K.PEN + r"\rubber.rvmat")]
    return geom, view, fire


SPEC = dict(
    name="prc152",
    stem="oz_radio_prc152",
    build=build,
    materials=materials,
    collision=collision,
    mass=0.60,
    grip_shift=-0.07,           # shift in the hand grip, m (+ toward the antenna), at the owner's request 25.09
    body_top=L.H,
    previews=[
        ("front", 0, 4, 1.05, (0.0, 0.0, 0.215)),
        ("threeq", -32, 14, 0.62, (0.0, 0.0, 0.110)),
        ("close", -15, 10, 0.30, (0.0, -0.01, 0.125)),
        ("back", 148, 12, 0.62, (0.0, 0.0, 0.100)),
        ("left", -80, 6, 0.58, (0.0, 0.0, 0.110)),
        ("top", 20, 60, 0.34, (0.0, 0.0, 0.205)),
    ],
    bake=dict(cage=0.0028, ray=0.007, size=4096, out=2048),
)

if __name__ == "__main__":
    K.run(SPEC)
