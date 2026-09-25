"""Layout of the 500/750 m radio (inspired by the Midland LXT600) - shared numbers for geometry and printing.

Model coordinates: X right, Y back (the face looks toward -Y), Z up, meters; origin is the center of the bottom.
The reference (mehmetfmalli, Sketchfab) shows the upper two-thirds of the radio at an angle from the right:
the face sits in a convex bezel, a silver frame around the amber LCD, six buttons in two rows (a
microphone in the middle of the bottom row), a large white logo, with long speaker slots below it; a
crown-shaped knob at the top left, a thick short antenna at the top right, PTT on the right side.
"""

MODEL = "БАЗАР"       # OZ-COM model name (the owner's choice, 25.09)
TAGLINE = "MAX-TALK"

# --- body -------------------------------------------------------------------
W = 0.056
H = 0.128
YF = -0.018          # plane of the face bezel
YB = 0.016           # back
R_FRONT, R_BACK = 0.0075, 0.0055
BEV_TOP = 0.0035     # top and bottom are heavily rounded
# recess of the front panel inside the bezel
PANEL = dict(w=0.040, z0=0.0045, z1=0.1215, r=0.0060, depth=0.0008)

# --- top: antenna on a boss at the right, crown knob at the left --------------------------
ANT = dict(x=0.0165, y=-0.0012, boss_r=0.0082, r0=0.0066, r1=0.0056, z0=H + 0.0035, top=H + 0.0640)
KNOB = dict(x=-0.0158, y=-0.0012, r_lo=0.0041, r_hi=0.0057, fins=6, z0=H - 0.0005, h=0.0125)

# --- bezel and LCD ------------------------------------------------------------------
BEZEL = dict(cx=0.0, cz=0.1040, w=0.0320, h=0.0290, r=0.0048, proud=0.0016)
LCD_WIN = dict(cx=0.0, cz=0.1020, w=0.0222, h=0.0168, r=0.0012, depth=0.0009)

# --- buttons: (x, z, w, h, outer-edge slant, label, sub-label) ---------------------
BTN_ROW1, BTN_ROW2 = 0.0795, 0.0682
BTN_W, BTN_H = 0.0106, 0.0086
BUTTONS = [
    (-0.0118, BTN_ROW1, -1, "CALL", "lock"),
    (0.0, BTN_ROW1, 0, "MENU", ""),
    (0.0118, BTN_ROW1, 1, "MON\nSCAN", ""),
    (-0.0118, BTN_ROW2, -1, "v", ""),
    (0.0118, BTN_ROW2, 1, "^", "WX"),
]
MIC = dict(x=0.0, z=BTN_ROW2, w=0.0098, h=0.0080, hole_r=0.0010)
BTN_PROUD = 0.0016

# --- logo and grille ---------------------------------------------------------------
BRAND_Z = 0.0505
GRILLE = dict(x0=-0.0170, x1=0.0170, zs=(0.0370, 0.0300, 0.0230, 0.0160), h=0.0024, depth=0.0012)

# --- sides: (y-center, z0, z1, width along y, protrusion) ------------------------------------
PTT = (-0.0035, 0.0815, 0.1060, 0.0100, 0.0021)       # right side (+X), as in the reference
JACK = (-0.0035, 0.0880, 0.1060, 0.0085, 0.0012)      # left side (-X)

# --- back: battery door and clip ------------------------------------------------------
DOOR = dict(w=0.044, z0=0.008, z1=0.092, r=0.004)
CLIP_W, CLIP_TOP, CLIP_BOT = 0.024, 0.100, 0.040

# --- print canvases -------------------------------------------------------------------
PPM = 40
FRONT_RECT = (-W / 2, W / 2, 0.0, H)                  # face: a = x, b = z
RIGHT_RECT = (-0.020, 0.018, 0.060, 0.120)            # right side: a = y (front on the left), b = z
BACK_RECT = (-W / 2, W / 2, 0.0, H)                   # back: a = -x, b = z
ANT_RECT = (ANT["x"] - 0.008, ANT["x"] + 0.008, ANT["z0"], ANT["top"])
LCD_RECT = (LCD_WIN["cx"] - LCD_WIN["w"] / 2, LCD_WIN["cx"] + LCD_WIN["w"] / 2,
            LCD_WIN["cz"] - LCD_WIN["h"] / 2, LCD_WIN["cz"] + LCD_WIN["h"] / 2)

