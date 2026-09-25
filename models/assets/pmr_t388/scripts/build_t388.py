"""Radio, 50..250 m range (toy PMR T-388): detailed model, LODs, baking, textures, p3d.

    python make_prints_t388.py
    blender -b -P build_t388.py -- [--high-only] [--skip-bake] [--no-previews]

The body has two parts, like the reference: an upper shell with the LCD shield, and a lower,
rubberized part with grip waves on the sides and the speaker. The parts sit flush, and the seam
between them is an arc under the CALL / TALK / MON row with a narrow groove (previously both parts
were rounded across the seam too, and the buttons sat in a V-shaped gap).
"""
import math
import os
import sys

import bmesh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "_kit")))
import radiokit as K  # noqa: E402
import layout_t388 as L  # noqa: E402
from mathutils import Vector  # noqa: E402

TEX = os.path.normpath(os.path.join(HERE, "..", "textures"))
DIRT = (0.105, 0.072, 0.045)


def P(name):
    return os.path.join(TEX, name)


def materials():
    front = dict(image=P("print_front.png"), rect=L.FRONT_RECT, axis="-Y")
    back = dict(image=P("print_back.png"), rect=L.BACK_RECT, axis="+Y")
    grime = (DIRT, 0.38, 75.0)
    return {
        "body": K.mat_worn("M_Body", (0.024, 0.020, 0.017), rough=(0.5, 0.7), edge_col=(0.10, 0.085, 0.07),
                           dust=DIRT, dust_amount=0.85, prints=[back], noise_bump=0.2, grime=grime),
        "clip": K.mat_worn("M_Clip", (0.024, 0.020, 0.017), rough=(0.5, 0.7), edge_col=(0.10, 0.085, 0.07),
                           dust=DIRT, dust_amount=0.85, noise_bump=0.2, grime=grime),
        "grip": K.mat_worn("M_Grip", (0.020, 0.017, 0.015), rough=(0.66, 0.84), edge_col=(0.085, 0.075, 0.065),
                           dust=DIRT, dust_amount=0.9, noise_bump=0.4, grime=grime),
        "bezel": K.mat_worn("M_Bezel", (0.46, 0.46, 0.45), rough=(0.26, 0.42), metallic=0.65,
                            edge_col=(0.70, 0.70, 0.69), dust=DIRT, dust_amount=0.9, prints=[front],
                            grime=(DIRT, 0.65, 55.0)),
        "rubber": K.mat_worn("M_Buttons", (0.016, 0.015, 0.014), rough=(0.45, 0.62), edge_col=(0.08, 0.075, 0.07),
                             dust=DIRT, dust_amount=0.7, prints=[front], grime=(DIRT, 0.35, 60.0)),
        "btn_blue": K.mat_worn("M_BtnBlue", (0.05, 0.08, 0.30), rough=(0.3, 0.45), edge_col=(0.3, 0.35, 0.6),
                               dust=DIRT, prints=[front]),
        "btn_red": K.mat_worn("M_BtnRed", (0.35, 0.03, 0.03), rough=(0.3, 0.45), edge_col=(0.6, 0.25, 0.25),
                              dust=DIRT, prints=[front]),
        "lcd": K.mat_worn("M_LCD", (0.2, 0.2, 0.2), rough=(0.08, 0.16), edge_amount=0.0, dust=DIRT,
                          dust_amount=0.4, soft_edges=0.0, image=(P("lcd.png"), L.LCD_RECT, "-Y")),
        "led": K.mat_simple("M_LED", (0.05, 0.12, 0.05), 0.15),
        "antenna": K.mat_worn("M_Antenna", (0.022, 0.019, 0.016), rough=(0.6, 0.8), edge_amount=0.5, dust=DIRT,
                              dust_amount=0.8, noise_bump=0.3, grime=grime),
        "steel": K.mat_worn("M_Steel", (0.45, 0.43, 0.40), rough=(0.3, 0.5), metallic=1.0, dust=DIRT,
                            edge_col=(0.7, 0.68, 0.64)),
        "cloth": K.mat_simple("M_SpeakerCloth", (0.006, 0.006, 0.006), 0.9),
    }


# =============================================================================
# Body
# =============================================================================
def seam_line(m):
    """The seam runs left to right along the L.seam_z arc. Few segments on purpose: the side bevel,
    running into the seam, slides along the end segment across its full width, so that segment must be longer than it."""
    n = m.s(12, 8, 4, 2, 1)
    return [(x, L.seam_z(x)) for x in (-L.W / 2 + L.W * i / n for i in range(n + 1))]


def on_seam(v, line):
    """Is the vertex on the seam surface (the polyline "line", extruded along Y)?"""
    x, z = v.co.x, v.co.z
    for (xa, za), (xb, zb) in zip(line, line[1:]):
        if xa - 1e-7 <= x <= xb + 1e-7:
            return abs(z - (za + (zb - za) * (x - xa) / (xb - xa))) < 1e-5
    return False


def shell(m, bm, line):
    """Bevel of a body part: L.BEV everywhere except the seam edges - there it's only a narrow
    groove, and only on the detailed mesh (the LODs get it from baking). Previously the seam was
    beveled at the same 4.5 mm on both sides, with a deep V-shaped gap running along it. clamp is
    turned off: with it on, the bottom (grip waves) beveled at 2.9 mm, the top at 4.5, and the parts didn't meet."""
    def seam(e):
        return all(on_seam(v, line) for v in e.verts)
    # LOD2 is beveled the same way as LOD1: a single bevel face in its place used to take its UV
    # unwrap from the LOD1 bevel and drag foreign islands onto the top edge (pink stripes)
    sg = (5, 2, 2, 0)[min(m.q, 3)]
    if sg:
        K.bevel(bm, L.BEV, sg, angle=45.0, only=lambda e: not seam(e), clamp=False)
    if m.hi:
        K.bevel(bm, L.SEAM_BEV, 2, angle=45.0, only=seam)
    return bm


def upper_outline(m, line):
    """Shell outline, front view (x, z): bottom is the seam left to right, right side, rounded top, left side."""
    r, seg = L.R_TOP, m.s(8, 3, 2, 1, 0)
    if seg:
        top = (K.arc(L.W / 2 - r, L.H - r, r, 0.0, 0.5 * math.pi, seg)
               + K.arc(-L.W / 2 + r, L.H - r, r, 0.5 * math.pi, math.pi, seg))
    else:
        top = [(L.W / 2, L.H), (-L.W / 2, L.H)]
    return list(line) + top


def wave(z):
    """Grip waves. There are none right at the seam: the lower part's side is vertical there, like
    the shell's, and the bevels of both parts meet the seam the same way - in the LODs their vertices coincide and get stitched together."""
    d = L.seam_z(L.W / 2) - z
    fade = min(1.0, max(0.0, (d - 0.003) / 0.004))
    return fade * sum(a * math.exp(-((z - zc) / 0.0052) ** 2) for zc, a in L.GRIP_WAVES)


def lower_outline(line, seg, n_side):
    """Outline of the lower part (x, z): from the left end of the seam down the side with the grip
    waves, the rounded bottom, up the right side, and back along the seam."""
    r = 0.0085
    zt = line[0][1]
    # without the seam and without z = r: those are corners. The point 3 mm below the seam is the
    # same on every LOD: the side edge from the seam to it is vertical (no waves there), and the side bevel meets the seam the same way the shell's does
    zs = [zt - 0.003] + [z for z in (zt - (zt - r) * i / n_side for i in range(1, n_side)) if z < zt - 0.0035]
    left = [(-(L.W / 2 + wave(z)), z) for z in zs]
    right = [(L.W / 2 + wave(z), z) for z in reversed(zs)]
    if seg:
        cl = K.arc(-L.W / 2 + r, r, r, math.pi, 1.5 * math.pi, seg)
        cr = K.arc(L.W / 2 - r, r, r, 1.5 * math.pi, 2.0 * math.pi, seg)
    else:
        cl, cr = [(-L.W / 2, 0.0)], [(L.W / 2, 0.0)]
    return [line[0]] + left + cl + cr + right + list(reversed(line))[:-1]


def body(m):
    """Body: the upper shell and the rubberized bottom, flush along a shared seam. In the in-game
    LODs the end faces along the seam (they're internal) are removed, and the two parts merge into
    one mesh: the face unwraps as a single island, and the join between top and bottom doesn't cut the texture."""
    line = seam_line(m)
    up = shell(m, K.prism(upper_outline(m, line), L.YF, L.YB, "Y"), line)
    lo = shell(m, K.prism(lower_outline(line, m.s(6, 2, 1, 1, 0), m.s(40, 12, 6, 3, 2)), L.YF, L.YB, "Y"), line)
    if m.hi:
        m.add(up, "body", name="UpperBody")
        m.add(lo, "grip", name="LowerBody")
        return
    bm = K.merge(up, lo)
    caps = [f for f in bm.faces if all(on_seam(v, line) for v in f.verts)]
    bmesh.ops.delete(bm, geom=caps, context="FACES")
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    open_edges = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    print("  body LOD%d: %d seam caps removed, %d open edges" % (m.q, len(caps), open_edges))
    m.add(bm, "body", name="Body")


# =============================================================================
# Face
# =============================================================================
def button_outline(x, z, rx, rz, n, grow=0.0):
    return [(x + (rx + grow) * math.cos(2 * math.pi * i / n), z + (rz + grow) * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def button_seg(m, t):
    return m.s(28, 14 if t == "TALK" else 10, 6)


def bezel_outline(seg):
    b = L.BEZEL
    x1 = b["w"] / 2
    pts = [(x1, b["z_side"]), (x1, b["z1"]), (-x1, b["z1"]), (-x1, b["z_side"]), (-b["x_bot"], b["z0"]),
           (b["x_bot"], b["z0"])]
    return K.rounded_poly(pts, [0.002, b["r_top"], b["r_top"], 0.002, 0.0015, 0.0015], seg) if seg else pts


def bezel(m):
    b, w = L.BEZEL, L.LCD_WIN
    yf = L.YF - b["proud"]
    bm = K.prism(bezel_outline(m.s(6, 2, 1, 0)), L.YF + 0.0006, yf, "Y")
    cuts = []
    # cutouts - on LOD2 too: it still has buttons, and a shield without the LCD cutout used to break
    # into large triangles, one of which took its UV unwrap from a small LOD1 triangle at the window (a dark wedge on the shield)
    if m.upto(2):
        cuts.append(K.prism(K.rrect(w["w"], w["h"], w["r"], w["cx"], w["cz"], seg=m.s(4, 1)), yf - 0.001,
                            yf + w["depth"], "Y"))
        # the shield wraps around the buttons with a dark gap, like the reference; between CALL,
        # TALK and MON it leaves downward-pointing teeth
        for x, z, rx, rz, _mat, t in L.BUTTONS:
            cuts.append(K.prism(button_outline(x, z, rx, rz, button_seg(m, t), L.BEZEL_GAP), yf - 0.001,
                                L.YF + 0.001, "Y"))
    m.add(bm, "bezel", name="Bezel", bevel_=(0.0007, (3, 1, 0)), cuts=cuts, bevel_angle=50.0)
    y_lcd = yf + w["depth"] - 0.0001 if m.upto(2) else yf - 0.0001
    lcd = K.prism(K.rrect(w["w"] - 0.0003, w["h"] - 0.0003, w["r"], w["cx"], w["cz"], seg=m.s(4, 1, 0)),
                  y_lcd + 0.0003, y_lcd, "Y")
    m.add(lcd, "lcd", tag=K.T_LCD, name="LCD")


def buttons(m):
    if not m.upto(2):
        return
    front = L.YF - L.BEZEL["proud"] - 0.0011
    for x, z, rx, rz, mat, t in L.BUTTONS:
        f = front - (0.0010 if t == "TALK" else 0.0)
        # TALK has a smaller bevel: the label spans the whole button on a flat surface instead of sliding onto the side
        bev = min(rx, rz) * (0.28 if t == "TALK" else 0.42)
        m.add(K.prism(button_outline(x, z, rx, rz, button_seg(m, t)), L.YF + 0.0006, f, "Y"), mat, tag=K.T_KEYS,
              name="Button", bevel_=(bev, (3, 1, 0)), bevel_angle=50.0)
    if m.hi:
        x, z, r = L.LED
        m.add(K.lathe([(r, L.YF + 0.0004), (r, L.YF - 0.0003), (r * 0.6, L.YF - 0.0007), (0.0, L.YF - 0.0008)],
                      20, x, z, "Y"), "led", name="Led")


def speaker(m):
    s = L.SPK
    yf = L.YF - s["proud"]
    bm = K.prism(K.rrect(s["w"], s["h"], s["r"], s["cx"], s["cz"], seg=m.s(8, 3, 2, 0)), L.YF + 0.0012, yf, "Y")
    cuts = None
    if m.hi:
        hs = L.SPK_HOLES
        holes = []
        for rr, n in hs["rings"]:
            for i in range(n):
                a = 2 * math.pi * i / n + (math.pi / n if n == 12 and rr > 0.012 else 0.0)
                x, z = hs["cx"] + rr * math.cos(a), hs["cz"] + rr * math.sin(a)
                if abs(x - s["cx"]) < s["w"] / 2 - 0.003 and abs(z - s["cz"]) < s["h"] / 2 - 0.003:
                    holes.append(K.cyl(x, z, hs["r"], yf - 0.001, L.YF + 0.0020, 16, "Y"))
        cuts = [K.merge(*holes)]
    m.add(bm, "grip", name="Speaker", bevel_=(0.0012, (4, 1, 0)), cuts=cuts, bevel_angle=45.0)
    if m.hi:
        # dark speaker cloth behind the through-holes: without it, the bottom of each hole would
        # show the body's face, and the holes would read as bumps. The sheet sits inside the panel,
        # in front of the body's face: behind it, as before, the body itself hides it
        cloth = K.prism(K.rrect(s["w"] - 0.004, s["h"] - 0.004, s["r"] - 0.002, s["cx"], s["cz"], seg=6),
                        L.YF - 0.0001, L.YF - 0.0003, "Y")
        m.add(cloth, "cloth", name="SpeakerCloth")


def antenna(m):
    a = L.ANT
    x, y = a["x"], a["y"]
    n = m.s(32, 12, 8, 6, 4)
    zc, top = a["z_collar"], a["top"]
    if m.hi:
        prof = [(0.0, L.H - 0.006), (a["collar_r"], L.H - 0.006), (a["collar_r"], zc - 0.0012),
                (a["collar_r"] - 0.0008, zc), (a["r0"], zc + 0.0004)]
        for i in range(1, 9):
            t = i / 8
            prof.append((a["r0"] + (a["r1"] - a["r0"]) * t, zc + 0.0004 + (top - 0.006 - zc) * t))
        for k in range(1, 7):
            ang = math.radians(90 * k / 7)
            prof.append((a["r1"] * math.cos(ang), top - 0.006 + 0.006 * math.sin(ang)))
        prof.append((0.0, top))
    else:
        prof = [(0.0, L.H - 0.006), (a["collar_r"], L.H - 0.006), (a["collar_r"], zc), (a["r0"], zc + 0.0004),
                (a["r1"], top - 0.004)]
        if m.q <= 2:
            prof.append((a["r1"] * 0.6, top - 0.0008))
        prof.append((0.0, top))
    m.add(K.lathe(prof, n, x, y, "Z"), "antenna", name="Antenna")


def back_door(m):
    if not m.upto(1):
        return
    d = L.DOOR
    bm = K.prism(K.rrect(d["w"], d["z1"] - d["z0"], d["r"], 0.0, (d["z0"] + d["z1"]) / 2, seg=m.s(5, 2)),
                 L.YB - 0.0015, L.YB + 0.0010, "Y")
    m.add(bm, "body", name="BatteryDoor", bevel_=(0.0005, (3, 1)), bevel_angle=50.0)


def clip_offset(z):
    """Offset of the clip plate from the body: a pure shift, the plate stays FLAT. Bending it made
    a non-flat n-gon plate, and its fold triangulation gave a dark "diamond" in the middle."""
    return 0.0028 * (L.CLIP_TOP - z) / (L.CLIP_TOP - L.CLIP_BOT)


def belt_clip(m):
    if not m.upto(3):
        return
    y0 = L.YB - 0.0004
    mount = K.prism(K.rrect(0.018, 0.012, 0.003, 0.0, L.CLIP_TOP - 0.006, seg=m.s(4, 1, 0)), y0 - 0.001,
                    y0 + 0.0032, "Y")
    m.add(mount, "clip", name="ClipMount", bevel_=(0.0007, (3, 1, 0)), bevel_angle=50.0)
    pts = K.rrect(L.CLIP_W, L.CLIP_TOP - L.CLIP_BOT, (0.005, 0.003, 0.003, 0.005), 0.0,
                  (L.CLIP_TOP + L.CLIP_BOT) / 2, seg=m.s(5, 2, 1, 0))
    pts = K.densify(pts, m.s(0.003, 0.008, 0.02, 0.05))
    bm = K.prism(pts, y0 + 0.0032, y0 + 0.0050, "Y")
    for v in bm.verts:
        v.co.y += clip_offset(v.co.z)
    K.fix_normals(bm)
    m.add(bm, "clip", name="ClipPlate", bevel_=(0.0006, (3, 1, 0)), bevel_angle=50.0)



def build(m):
    body(m)
    bezel(m)
    buttons(m)
    speaker(m)
    antenna(m)
    back_door(m)
    belt_clip(m)


def collision(_lods):
    def bx(x0, x1, y0, y1, z0, z1):
        return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]

    body = bx(-L.W / 2 - 0.0015, L.W / 2 + 0.0015, L.YF - 0.003, L.YB + 0.004, 0.0, L.H)
    a = L.ANT
    ant = [(a["x"] + a["collar_r"] * math.cos(i * math.pi / 4), a["y"] + a["collar_r"] * math.sin(i * math.pi / 4),
            z) for i in range(8) for z in (L.H - 0.006, a["top"])]
    geom = [(body, ""), (ant, "")]
    view = [(body + ant, "")]
    fire = [(body, K.PEN + r"\plastic_material.rvmat"), (ant, K.PEN + r"\rubber.rvmat")]
    return geom, view, fire


SPEC = dict(
    name="pmr_t388",
    stem="oz_radio_t388",
    build=build,
    materials=materials,
    collision=collision,
    mass=0.15,
    grip_shift=-0.04,           # shift in the hand grip, m (+ toward the antenna), at the owner's request 25.09
    body_top=L.H,
    previews=[
        ("front", 0, 4, 0.62, (0.0, 0.0, 0.080)),
        ("threeq", -30, 14, 0.40, (0.0, 0.0, 0.060)),
        ("close", -15, 8, 0.24, (0.0, -0.01, 0.064)),
        ("back", 148, 12, 0.40, (0.0, 0.0, 0.055)),
        ("left", -80, 6, 0.38, (0.0, 0.0, 0.060)),
    ],
    bake=dict(cage=0.0025, ray=0.006, size=4096, out=2048),
)

if __name__ == "__main__":
    K.run(SPEC)
