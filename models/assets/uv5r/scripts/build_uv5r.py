"""Radio with 1000 m range (modeled after the Baofeng UV-5R): detailed model, LODs, baking, textures, p3d.

    python make_prints_uv5r.py                                   (labels, LCD, strips)
    blender -b -P build_uv5r.py -- [--high-only] [--skip-bake] [--passes albedo,rough] [--no-previews]

Numbers live in layout_uv5r.py (the print script reads the same ones). Each part is built by an m.q-level function:
0 - detailed model (bake source only), 1..4 - in-game LODs. Whether something stays as geometry on the LOD
or goes into the normal map is decided by visibility: keys, buttons, the knob, the antenna,
the PTT and the clip - geometry down to LOD2; grille slots, screws, ribs, plates - baked only.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "_kit")))
import radiokit as K  # noqa: E402
import layout_uv5r as L  # noqa: E402
from mathutils import Vector  # noqa: E402

TEX = os.path.normpath(os.path.join(HERE, "..", "textures"))


def P(name):
    return os.path.join(TEX, name)


def materials():
    front = dict(image=P("print_front.png"), rect=L.FRONT_RECT, axis="-Y")
    left = dict(image=P("print_left.png"), rect=L.LEFT_RECT, axis="-X")
    back = dict(image=P("print_back.png"), rect=L.BACK_RECT, axis="+Y")
    brand = dict(image=P("print_brand.png"), rect=L.FRONT_RECT, axis="-Y")
    black = (0.016, 0.016, 0.018)
    return {
        "body": K.mat_worn("M_Body", black, rough=(0.55, 0.72), edge_col=(0.085, 0.085, 0.088), noise_bump=0.25,
                           prints=[brand]),
        "battery": K.mat_worn("M_Battery", (0.018, 0.018, 0.02), rough=(0.5, 0.68), edge_col=(0.09, 0.09, 0.09),
                              prints=[back], noise_bump=0.25),
        "clip": K.mat_worn("M_Clip", (0.018, 0.018, 0.02), rough=(0.5, 0.68), edge_col=(0.09, 0.09, 0.09),
                           noise_bump=0.25),
        "rubber": K.mat_worn("M_Rubber", (0.012, 0.012, 0.013), rough=(0.72, 0.86), edge_col=(0.05, 0.05, 0.05),
                             edge_amount=0.5, prints=[front, left]),
        "keys": K.mat_worn("M_Keys", (0.013, 0.013, 0.014), rough=(0.42, 0.58), edge_col=(0.07, 0.07, 0.07),
                           prints=[front]),
        "btn_orange": K.mat_worn("M_BtnOrange", (0.58, 0.085, 0.02), rough=(0.38, 0.52), edge_col=(0.8, 0.42, 0.25),
                                 prints=[front]),
        "btn_blue": K.mat_worn("M_BtnBlue", (0.025, 0.13, 0.52), rough=(0.38, 0.52), edge_col=(0.35, 0.5, 0.8),
                               prints=[front]),
        "chrome": K.mat_worn("M_Chrome", (0.64, 0.64, 0.66), rough=(0.16, 0.30), metallic=1.0,
                             edge_col=(0.85, 0.85, 0.86), dust_amount=0.5, prints=[front]),
        "plate": K.mat_worn("M_ModelPlate", (0.03, 0.03, 0.033), rough=(0.35, 0.5), prints=[front]),
        "lcd": K.mat_worn("M_LCD", (0.2, 0.2, 0.2), rough=(0.07, 0.13), edge_amount=0.0, dust_amount=0.25,
                          soft_edges=0.0, image=(P("lcd.png"), L.LCD_RECT, "-Y")),
        "led": K.mat_simple("M_LED", (0.10, 0.12, 0.11), 0.12),
        "lens": K.mat_simple("M_Lens", (0.30, 0.30, 0.28), 0.08, metallic=0.6),
        "steel": K.mat_worn("M_Steel", (0.52, 0.51, 0.49), rough=(0.22, 0.38), metallic=1.0,
                            edge_col=(0.75, 0.74, 0.72), dust=(0.2, 0.17, 0.13)),
        "antenna": K.mat_worn("M_Antenna", (0.013, 0.013, 0.014), rough=(0.6, 0.8), edge_amount=0.3),
    }


# =============================================================================
# Parts
# =============================================================================
def grille_slots():
    g = L.GRILLE
    slots = []
    rows = int(round((g["z1"] - g["z0"]) / g["pitch_z"])) + 1
    for r in range(rows):
        z = g["z1"] - r * g["pitch_z"]
        x = g["x0"] + (r % 2) * g["pitch_x"] / 2
        while x <= g["x1"] + 1e-6:
            if not any(a0 <= x <= a1 and b0 <= z <= b1 for a0, a1, b0, b1 in L.GRILLE_SKIP):
                slots.append(K.prism(K.rrect(g["slot_w"], g["slot_h"], g["slot_h"] * 0.45, x, z, seg=3),
                                     L.YF + g["depth"], L.YF - 0.002, "Y"))
            x += g["pitch_x"]
    return K.merge(*slots)


def shell(m):
    prof = K.rrect(L.W, L.YB - L.YF, (L.R_FRONT, L.R_BACK, L.R_BACK, L.R_FRONT), 0.0, (L.YF + L.YB) / 2,
                   seg=m.s(6, 2, 1, 0))
    bm = K.prism(prof, 0.0, L.H, "Z")
    cuts = []
    kp = L.KEYPAD
    cuts.append(K.prism(K.rrect(kp["x1"] - kp["x0"], kp["z1"] - kp["z0"], kp["r"], (kp["x0"] + kp["x1"]) / 2,
                                (kp["z0"] + kp["z1"]) / 2, seg=m.s(4, 2, 1, 0)), L.YF + kp["depth"], L.YF - 0.002, "Y"))
    if m.hi:
        cuts.append(grille_slots())
        t = L.TORCH
        cuts.append(K.cyl(t["x"], t["y"], t["r"] + 0.0006, L.H - 0.0012, L.H + 0.002, 24, "Z"))
        # seam between the front shell and the chassis: a shallow groove on the sides and top
        cuts.append(K.ring_prism(K.rect(L.W + 0.004, L.H * 2 + 0.01, 0.0, 0.0), K.rect(L.W - 0.0008, L.H * 2 - 0.0008 + 0.0,
                                                                                         0.0, 0.0), -0.0035, -0.0029,
                                 "Y"))
    m.add(bm, "body", name="Shell", bevel_=(L.BEV_TB, (4, 1, 0)), cuts=cuts, bevel_angle=50.0)


def lcd_block(m):
    b, w = L.LCD_BLOCK, L.LCD_WIN
    yf = L.YF - b["proud"]
    prof = K.rrect(b["w"], b["z1"] - b["z0"], b["r"], 0.0, (b["z0"] + b["z1"]) / 2, seg=m.s(6, 2, 1, 0))
    bm = K.prism(prof, L.YF + 0.001, yf, "Y")
    cuts = []
    if m.upto(1):
        cuts.append(K.prism(K.rrect(w["w"], w["h"], w["r"], w["cx"], w["cz"], seg=m.s(4, 1)), yf - 0.001,
                            yf + w["depth"], "Y"))
    m.add(bm, "body", name="LcdBlock", bevel_=(0.0008, (3, 1, 0)), cuts=cuts, bevel_angle=50.0)
    # the indicator itself: a plate at the bottom of the window (on far LODs - right on the face of the block)
    y_lcd = yf + w["depth"] - 0.0001 if m.upto(1) else yf - 0.0001
    lcd = K.prism(K.rrect(w["w"] - 0.0004, w["h"] - 0.0004, w["r"], w["cx"], w["cz"], seg=m.s(4, 1, 0)),
                  y_lcd + 0.0003, y_lcd, "Y")
    m.add(lcd, "lcd", tag=K.T_LCD, name="LCD")


def keypad(m):
    if not m.upto(2):
        return
    kp = L.KEYPAD
    for row, z in zip(L.KEYS, L.KEY_ROWS):
        for _, x in zip(row, L.KEY_COLS):
            bm = K.prism(K.rrect(L.KEY_W, L.KEY_H, L.KEY_R, x, z, seg=m.s(4, 2, 0)),
                         L.YF + kp["depth"] + 0.0003, L.YF - L.KEY_PROUD, "Y")
            m.add(bm, "keys", tag=K.T_KEYS, name="Key", bevel_=(0.0006, (3, 1, 0)), bevel_angle=60.0)


def front_buttons(m):
    if m.upto(2):
        for x, z, w, h, r, mat, _ in L.BUTTONS:
            bm = K.prism(K.rrect(w, h, r, x, z, seg=m.s(5, 2, 0)), L.YF + 0.0003, L.YF - 0.0012, "Y")
            m.add(bm, mat, tag=K.T_KEYS, name="Button", bevel_=(0.0005, (3, 1, 0)), bevel_angle=60.0)
    if m.hi:
        x, z, s = L.LED
        m.add(K.prism(K.rrect(s, s, 0.0005, x, z, seg=2), L.YF + 0.0003, L.YF - 0.0002, "Y"), "led", name="Led",
              bevel_=(0.0002, (2,)))
        x, z, w, h, r = L.MODEL_PLATE
        m.add(K.prism(K.rrect(w, h, r, x, z, seg=3), L.YF + 0.0003, L.YF - 0.0004, "Y"), "plate", name="ModelPlate",
              bevel_=(0.0002, (2,)))


def knob(m):
    k = L.KNOB
    z0, z1 = k["z0"], k["z0"] + k["h"]
    if m.hi:
        m.add(K.cyl(k["x"], k["y"], k["r"] * 0.86, L.H - 0.001, z0 + 0.0004, 32, "Z"), "rubber", name="KnobCollar",
              bevel_=(0.0003, (2,)))
        bm = K.prism(K.knurl(k["x"], k["y"], k["r"] * 0.93, k["r"], k["teeth"], (0.0, 0.2, 0.5, 0.7)), z0, z1, "Z")
        m.add(bm, "rubber", name="Knob", bevel_=(0.00025, (2,)), bevel_angle=60.0)
        # pointer dimple on the end face
        return
    n = m.s(0, 16, 10, 8, 6)
    m.add(K.cyl(k["x"], k["y"], k["r"] * 0.97, L.H - 0.001, z1, n, "Z"), "rubber", name="Knob",
          bevel_=(0.0007, (0, 1, 0)), bevel_angle=60.0)


def antenna(m):
    a = L.ANT
    x, y = a["x"], a["y"]
    n = m.s(28, 10, 8, 6, 4)
    if m.upto(2):
        m.add(K.prism(K.circle(x, y, a["nut_r"], 6, math.radians(30)), L.H - 0.001, a["z_nut"], "Z"), "steel",
              name="SmaNut", bevel_=(0.0003, (2, 0)))
    zb, zt = a["z_boot"], a["top"]
    if m.hi:
        prof = [(0.0, a["z_nut"] - 0.0005), (a["boot_r"] * 0.92, a["z_nut"] - 0.0005), (a["boot_r"], a["z_nut"] + 0.0008)]
        # three knurled rings at the base
        for i in range(3):
            z = a["z_nut"] + 0.0025 + i * 0.0028
            prof += [(a["boot_r"], z - 0.0006), (a["boot_r"] - 0.0005, z), (a["boot_r"], z + 0.0006)]
        prof += [(a["boot_r"], zb - 0.0015), (a["whip_r0"] + 0.0004, zb), (a["whip_r0"], zb + 0.002)]
        steps = 14
        for i in range(1, steps + 1):
            t = i / steps
            z = zb + 0.002 + (zt - 0.004 - zb - 0.002) * t
            prof.append((a["whip_r0"] + (a["whip_r1"] - a["whip_r0"]) * t, z))
        for k_ in range(1, 6):
            ang = math.radians(90 * k_ / 6)
            prof.append((a["whip_r1"] * math.cos(ang), zt - 0.004 + a["whip_r1"] * 1.1 * math.sin(ang)))
        prof.append((0.0, zt - 0.004 + a["whip_r1"] * 1.1))
    else:
        prof = [(0.0, a["z_nut"] - 0.0005), (a["boot_r"], a["z_nut"] - 0.0005), (a["boot_r"], zb - 0.0015),
                (a["whip_r0"], zb)]
        if m.q <= 2:
            prof.append((a["whip_r0"] + (a["whip_r1"] - a["whip_r0"]) * 0.5, zb + (zt - zb) * 0.5))
        prof += [(a["whip_r1"], zt - 0.003), (0.0, zt)]
    m.add(K.lathe(prof, n, x, y, "Z"), "antenna", name="Antenna")


def torch(m):
    if not m.hi:
        return
    t = L.TORCH
    m.add(K.cyl(t["x"], t["y"], t["r"] + 0.0005, L.H - 0.0012, L.H - 0.0006, 32, "Z"), "steel", name="TorchRing")
    m.add(K.cyl(t["x"], t["y"], t["r"], L.H - 0.0010, L.H - 0.0004, 32, "Z"), "lens", name="TorchLens",
          bevel_=(0.0003, (2,)))


def side_button(m, spec, left, name, ribs=0, lod_max=2):
    if not m.upto(lod_max):
        return
    yc, z0, z1, wy, proud = spec
    xs = -L.W / 2 if left else L.W / 2
    sgn = -1 if left else 1
    r = min(wy, z1 - z0) * 0.3
    bm = K.prism(K.rrect(wy, z1 - z0, r, yc, (z0 + z1) / 2, seg=m.s(5, 2, 0)), xs - sgn * 0.0012, xs + sgn * proud, "X")
    cuts = []
    if m.hi and ribs:
        for i in range(ribs):
            zg = z0 + (z1 - z0) * (i + 1) / (ribs + 1)
            cuts.append(K.prism(K.rect(wy + 0.002, 0.00055, yc, zg), xs + sgn * (proud - 0.00035),
                                xs + sgn * (proud + 0.002), "X"))
    m.add(bm, "rubber", name=name, bevel_=(min(0.0009, proud * 0.45), (3, 1, 0)), cuts=cuts or None,
          bevel_angle=60.0)


def jack_cover(m):
    if not m.upto(2):
        return
    yc, z0, z1, wy, proud = L.JACK
    xs = L.W / 2
    bm = K.prism(K.rrect(wy, z1 - z0, 0.0025, yc, (z0 + z1) / 2, seg=m.s(5, 2, 0)), xs - 0.0012, xs + proud, "X")
    m.add(bm, "rubber", name="JackCover", bevel_=(0.0006, (3, 1, 0)), bevel_angle=60.0)
    if m.hi:
        for dz in (-0.0055, 0.0055):
            m.add(K.cyl(yc, (z0 + z1) / 2 + dz, 0.0017, xs + proud - 0.0002, xs + proud + 0.00045, 20, "X"), "rubber",
                  name="JackPlug", bevel_=(0.0002, (2,)))


def battery(m):
    yc = (L.BAT_Y0 - 0.001 + L.BAT_Y1) / 2
    prof = K.rrect(L.BAT_W, L.BAT_Y1 - L.BAT_Y0 + 0.001, (0.001, 0.003, 0.003, 0.001), 0.0, yc, seg=m.s(5, 2, 1, 0))
    bm = K.prism(prof, 0.0, L.BAT_TOP, "Z")
    m.add(bm, "battery", name="Battery", bevel_=(0.0012, (3, 1, 0)), bevel_angle=50.0)
    if m.hi:
        # latch on top: a knurled key
        lat = K.prism(K.rrect(0.016, 0.006, 0.0015, 0.0, L.BAT_TOP - 0.003, seg=3), L.BAT_Y1 - 0.0005,
                      L.BAT_Y1 + 0.0011, "Y")
        ribs = [K.prism(K.rect(0.018, 0.0005, 0.0, L.BAT_TOP - 0.0045 + i * 0.001), L.BAT_Y1 + 0.0007,
                        L.BAT_Y1 + 0.002, "Y") for i in range(4)]
        m.add(lat, "battery", name="Latch", bevel_=(0.0004, (2,)), cuts=[K.merge(*ribs)])


def clip_offset(z):
    """Offset of the clip plate from the body: a pure shift, the plate stays FLAT. Bending produced
    a non-flat n-gon cap, and its fold triangulation gave a dark "diamond" in the middle."""
    return 0.0035 * (L.CLIP_TOP - z) / (L.CLIP_TOP - L.CLIP_BOT)


def belt_clip(m):
    y0 = L.BAT_Y1
    if m.upto(3):
        mount = K.prism(K.rrect(0.024, 0.013, 0.002, 0.0, 0.0655, seg=m.s(4, 1, 0)), y0 - 0.0005, y0 + 0.0035, "Y")
        m.add(mount, "clip", name="ClipMount", bevel_=(0.0006, (3, 1, 0)), bevel_angle=50.0)
    if not m.upto(3):
        return
    # plate: a flat outline with rounded corners, bowed along its height
    pts = K.rrect(L.CLIP_W, L.CLIP_TOP - L.CLIP_BOT, (0.004, 0.002, 0.002, 0.004), 0.0,
                  (L.CLIP_TOP + L.CLIP_BOT) / 2, seg=m.s(5, 2, 1, 0))
    pts = K.densify(pts, m.s(0.003, 0.008, 0.02, 0.05))
    bm = K.prism(pts, y0 + 0.0035, y0 + 0.0053, "Y")
    for v in bm.verts:
        v.co.y += clip_offset(v.co.z)
    K.fix_normals(bm)
    m.add(bm, "clip", name="ClipPlate", bevel_=(0.0005, (3, 1, 0)), bevel_angle=50.0)
    if m.hi:
        for sx in (-1, 1):
            ys = y0 + 0.0053
            prof = [(0.0019, ys - 0.0002), (0.0019, ys + 0.0003), (0.0012, ys + 0.0008), (0.0, ys + 0.0010)]
            m.add(K.lathe(prof, 20, sx * 0.0065, 0.0680, "Y"), "steel", name="ClipScrew")



def build(m):
    shell(m)
    lcd_block(m)
    keypad(m)
    front_buttons(m)
    knob(m)
    antenna(m)
    torch(m)
    side_button(m, L.PTT, True, "PTT", ribs=6)
    side_button(m, L.CALL, True, "Call", lod_max=1)
    side_button(m, L.MONI, True, "Moni", lod_max=1)
    jack_cover(m)
    battery(m)
    belt_clip(m)


# =============================================================================
# Collision: body as one shell (with the knob and clip), antenna as a second, like in vanilla
# =============================================================================
def collision(_lods):
    def bx(x0, x1, y0, y1, z0, z1):
        return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]

    body = bx(-L.W / 2, L.W / 2, L.YF - L.LCD_BLOCK["proud"], L.BAT_Y1, 0.0, L.H)
    body += bx(-L.CLIP_W / 2, L.CLIP_W / 2, L.BAT_Y1, L.BAT_Y1 + 0.0053 + clip_offset(L.CLIP_BOT), L.CLIP_BOT, L.CLIP_TOP)
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
    name="uv5r",
    stem="oz_radio_uv5r",
    build=build,
    materials=materials,
    collision=collision,
    mass=0.25,
    grip_shift=0.04,           # shift in the hand grip, m (+ toward the antenna), at the owner's request, 25.09
    body_top=L.H,
    previews=[
        ("front", 0, 4, 0.78, (0.0, 0.0, 0.140)),
        ("threeq", -32, 14, 0.42, (0.0, 0.0, 0.066)),
        ("close", -18, 8, 0.24, (0.0, -0.01, 0.052)),
        ("back", 148, 12, 0.42, (0.0, 0.0, 0.060)),
        ("left", -78, 6, 0.40, (0.0, 0.0, 0.070)),
        ("top", 25, 62, 0.34, (0.0, 0.0, 0.100)),
    ],
    bake=dict(cage=0.0025, ray=0.006, size=4096, out=2048),
)

if __name__ == "__main__":
    K.run(SPEC)
