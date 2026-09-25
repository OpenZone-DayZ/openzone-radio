"""Layout of the 50..250 m radio (toy PMR "soap-bar" T-388) - shared numbers for geometry and printing.

Model coordinates: X right, Y back (the face looks toward -Y), Z up, meters; origin is the center of the bottom.
Reference (biofrost, "Dirty Walkie Talkie", Sketchfab): the body has two parts - the top with a
silver-plastic shield-frame around the LCD and buttons, the bottom rubberized, with grip waves on
the sides and a large speaker whose holes radiate outward. A short, thick antenna at the top left.
Dirty, worn, the LCD glass is cracked.
Proportions taken from the render: body 400x770 px -> at a width of 56 mm the height is 108 mm.

The face detail heights were re-measured on 24.09 along the reference's central vertical (x = 867
px: bottom of the body y = 1030, top y = 253, 0.139 mm/px; horizontally the LCD is 178 px = 25 mm).
The previous layout sat 5-8 mm higher, and the body seam landed right on the CALL / TALK / MON row.
In the reference the seam is a "smile" under that row: the buttons sit entirely on the upper shell, and only the bottom of TALK reaches the seam.
"""

MODEL = "ШЕПТУН"      # OZ-COM model name (the owner's choice, 25.09); T-388 is only the reference

# --- body -------------------------------------------------------------------
W = 0.056
H = 0.108
YF = -0.015          # plane of the face
YB = 0.014           # back
R_TOP = 0.0075       # rounding of the top corners (front view)
BEV = 0.0045         # bevel of the face/back edges - a "toy-like" soft shape
# seam between the upper shell and the rubberized bottom: an arc, lowest under TALK, rising toward
# the sides. Both parts are flush, with only a narrow groove between them (SEAM_BEV, on the detailed model)
SEAM_Z = 0.0558      # seam at the middle
SEAM_RISE = 0.0044   # rise of the seam toward the sides
SEAM_BEV = 0.0006
# grip waves on the sides of the lower part: (z-center, protrusion), on both sides
GRIP_WAVES = [(0.050, 0.0010), (0.0345, 0.0016), (0.0195, 0.0015), (0.0085, 0.0008)]


def seam_z(x):
    return SEAM_Z + SEAM_RISE * (x / (W / 2)) ** 2


# --- LCD shield-frame (silver) ----------------------------------------------------
# from the top down to z1, the sides down to z_side, then it slants inward to the bottom z0 at
# +-x_bot; around the buttons the shield is cut out with a BEZEL_GAP gap, and between CALL, TALK and MON it leaves downward-pointing teeth
BEZEL = dict(w=0.0358, z1=0.1012, z_side=0.0745, z0=0.0653, x_bot=0.0138, r_top=0.0075, proud=0.0012)
BEZEL_GAP = 0.0006
LCD_WIN = dict(cx=0.0, cz=0.0827, w=0.0249, h=0.0158, r=0.0015, depth=0.0008)
MODEL_Z = 0.0920     # model name in the strip between the brand and the LCD
BRAND_Z = 0.0953     # brand on the silver shield above the LCD (middle of the capitals)

# --- buttons: (x, z, rx, rz, material, label) - ovals/circles ---------------------------
BUTTONS = [
    (-0.0191, 0.0857, 0.0027, 0.0027, "btn_blue", "LAMP"),
    (0.0191, 0.0832, 0.0024, 0.0024, "btn_red", "pwr"),
    (-0.0166, 0.0725, 0.0027, 0.0027, "rubber", "SCAN"),
    (0.0166, 0.0725, 0.0027, 0.0027, "rubber", "MENU"),
    (-0.0081, 0.0701, 0.00375, 0.0026, "rubber", "v"),
    (0.0081, 0.0701, 0.00375, 0.0026, "rubber", "^"),
    (-0.0126, 0.0632, 0.0050, 0.00335, "rubber", "CALL"),
    (0.0126, 0.0632, 0.0050, 0.00335, "rubber", "MON"),
    (0.0, 0.0626, 0.0052, 0.0052, "rubber", "TALK"),
]
LED = (0.0195, 0.0655, 0.0012)
BTN_PROUD = 0.0018

# --- speaker: raised panel with holes radiating outward --------------------------------------
SPK = dict(cx=0.0, cz=0.0296, w=0.0410, h=0.0504, r=0.0090, proud=0.0012)
SPK_HOLES = dict(cx=0.0, cz=0.0298, r=0.0015, rings=[(0.0, 1), (0.0050, 6), (0.0093, 12), (0.0134, 12),
                                                     (0.0174, 12)], depth=0.0014)

# --- top: thick short antenna at the left --------------------------------------------------
ANT = dict(x=-0.0145, y=-0.0005, collar_r=0.0082, r0=0.0070, r1=0.0060, z_collar=H + 0.0070, top=H + 0.052)

# --- back: battery door and clip ------------------------------------------------------
DOOR = dict(w=0.042, z0=0.007, z1=0.052, r=0.005)
CLIP_W, CLIP_TOP, CLIP_BOT = 0.022, 0.094, 0.050

PPM = 40
FRONT_RECT = (-W / 2, W / 2, 0.0, H)
BACK_RECT = (-W / 2, W / 2, 0.0, H)
LCD_RECT = (LCD_WIN["cx"] - LCD_WIN["w"] / 2, LCD_WIN["cx"] + LCD_WIN["w"] / 2,
            LCD_WIN["cz"] - LCD_WIN["h"] / 2, LCD_WIN["cz"] + LCD_WIN["h"] / 2)

