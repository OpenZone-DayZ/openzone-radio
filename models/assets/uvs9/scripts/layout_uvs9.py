"""Layout of the 2000 m radio (modeled after the Baofeng UV-S9, "military" olive) - shared numbers.

Model coordinates: X right, Y back (the face looks toward -Y), Z up, meters; origin - center of the bottom.
Reference (Archivz, Sketchfab) shows the radio lying down, top to the right: an olive bumper body,
with dark grey-brown overlays on it - a 4x4 keypad, a grille with six transverse slots and
the brand name below it, a large LCD frame on top; along the left edge of the grille - a column of A/B buttons,
microphone, flashlight, VFO/MR; on the right side - a rubber headset jack cover with a screw; at the bottom corners
of the face - screws. On top, a thick knurled antenna and a large knob.
"""

MODEL = "СКРИНЯ"      # OZ-COM model name (the owner's choice, 25.09)

W = 0.060
H = 0.120
YF = -0.017
YB = 0.015
R_PLAN = 0.0055
BEV_TB = 0.0030

# --- overlays (dark): keypad, grille, LCD frame ---------------------------------
KEY_DECK = dict(x0=-0.0265, x1=0.0265, z0=0.0065, z1=0.0505, r=0.0030, proud=0.0012)
GRILLE_DECK = dict(x0=-0.0125, x1=0.0265, z0=0.0535, z1=0.0895, r=0.0025, proud=0.0016)
LCD_FRAME = dict(x0=-0.0275, x1=0.0275, z0=0.0925, z1=0.1175, r=0.0035, proud=0.0026)
LCD_WIN = dict(cx=0.0, cz=0.1050, w=0.0440, h=0.0180, r=0.0012, depth=0.0015)

KEY_W, KEY_H, KEY_R = 0.0100, 0.0070, 0.0016
KEY_COLS = (-0.0186, -0.0062, 0.0062, 0.0186)
KEY_ROWS = (0.0435, 0.0335, 0.0235, 0.0135)
KEY_PROUD = 0.0020     # above the overlay
KEYS = [
    [("MENU", ""), ("^", ""), ("v", ""), ("EXIT", "")],
    [("1", "STEP"), ("2", "TXP"), ("3", "SAVE"), ("*", "SCAN")],
    [("4", "VOX"), ("5", "WN"), ("6", "ABR"), ("0", "SQL")],
    [("7", "TDR"), ("8", "BEEP"), ("9", "TOT"), ("#", "key")],
]

# grille: transverse slots above the brand line
SLOTS = dict(x0=-0.0060, x1=0.0225, z=(0.0655, 0.0700, 0.0745, 0.0790, 0.0835), h=0.0024, depth=0.0012)
BRAND_LINE = dict(x=0.0015, z=0.0585)
BAND_BTN = (0.0195, 0.0585, 0.0080, 0.0048)

# column of buttons along the left edge of the grille: (z, w, h, material, label)
SIDE_COL_X = -0.0205
COL_BTNS = [
    (0.0590, 0.0090, 0.0056, "btn_green", "A/B"),
    (0.0685, 0.0060, 0.0050, "mic", ""),
    (0.0770, 0.0085, 0.0056, "btn_grey", ""),
    (0.0860, 0.0095, 0.0060, "btn_orange", "VFO\nMR"),
]
FACE_SCREWS = [(-0.0255, 0.0035), (0.0255, 0.0035)]

KNOB = dict(x=0.0160, y=-0.0040, r=0.0086, z0=H + 0.0008, h=0.0135, teeth=16)
ANT = dict(x=-0.0150, y=-0.0040, boot_r=0.0074, whip_r0=0.0056, whip_r1=0.0036, z_boot=H + 0.0230,
           top=H + 0.1900)

# sides: (y-center, z0, z1, width along y, protrusion)
PTT = (-0.0055, 0.0600, 0.0880, 0.0110, 0.0024)       # left side
JACK = (-0.0045, 0.0480, 0.0860, 0.0150, 0.0016)      # right side: headset jack cover
JACK_SCREW = (-0.0045, 0.0425, 0.0034)

BAT = dict(w=0.056, y0=0.010, y1=0.019, top=0.092)
CLIP_W, CLIP_TOP, CLIP_BOT = 0.030, 0.082, 0.024


PPM = 40
FRONT_RECT = (-W / 2, W / 2, 0.0, H)
RIGHT_RECT = (-0.022, 0.018, 0.030, 0.100)            # right side: a = y (front is on the left), b = z
LEFT_RECT = (-0.018, 0.022, 0.050, 0.100)             # left side: a = -y (front is on the right), b = z
BACK_RECT = (-W / 2, W / 2, 0.0, H)
LCD_RECT = (LCD_WIN["cx"] - LCD_WIN["w"] / 2, LCD_WIN["cx"] + LCD_WIN["w"] / 2,
            LCD_WIN["cz"] - LCD_WIN["h"] / 2, LCD_WIN["cz"] + LCD_WIN["h"] / 2)

