"""Layout of the 10000 m radio (inspired by the AN/PRC-152, an army man-pack set) - shared numbers.

Model coordinates: X right, Y back (the face looks toward -Y), Z up, meters; origin is the center of the bottom.
References (r4m and pnuky, Sketchfab): an olive body with a "waist" at the keypad, at the top a
speaker grille in a stepped staircase of paired slots and the brand, the caption WIDEBAND
NETWORKING, a wide green LCD, a black rubber 4x4 keypad with a tall PRE +/- rocker, with the product name below it;
a large battery at the bottom. At the top: a headset connector, a large knob with numbers on the side, a thick
antenna. On the back: a nomenclature plate, like on army equipment.
"""

PRODUCT = "КРИСТАЛ"     # OZ-COM model name (the owner's choice, 25.09); the nomenclature on the back is the army one
NOMEN = "AN/PRC-152A"

W = 0.068
H = 0.200
Z_BAT = 0.058         # joint between the radio and the battery
YF = -0.020
YB = 0.020
R_PLAN = 0.0050
BEV = 0.0030
WAIST = dict(z=0.096, depth=0.0022, width=0.020)      # "waist" on the sides at the keypad

# speaker grille: paired "=" slots on a grid, in a staircase pattern
GRID = dict(x0=-0.0215, z0=0.1605, pitch_x=0.0072, pitch_z=0.0068, slot_w=0.0058, slot_h=0.0019, gap=0.0008,
            depth=0.0010)
GRID_CELLS = {0: (3, 4, 5), 1: (2, 3, 4, 5), 2: (1, 2, 3, 4), 3: (0, 1, 2, 3, 6)}   # row (from the top) -> columns
BRAND_POS = (-0.0175, 0.1925)
WIDEBAND_POS = (-0.0035, 0.1500)

LCD_FRAME = dict(cx=0.0, cz=0.1370, w=0.0540, h=0.0200, r=0.0020, depth=0.0006)
LCD_WIN = dict(cx=0.0, cz=0.1370, w=0.0500, h=0.0160, r=0.0010, depth=0.0010)

KEYPAD = dict(x0=-0.0265, x1=0.0265, z0=0.0715, z1=0.1260, r=0.0055, depth=0.0010)
KEY_COLS = (-0.0180, -0.0060, 0.0060, 0.0180)
KEY_ROWS = (0.1180, 0.1060, 0.0940, 0.0820)
KEY_W, KEY_H, KEY_R = 0.0094, 0.0084, 0.0018
KEY_PROUD = 0.0022
KEYS = [
    [("1", "ABC", "CALL"), ("2", "DEF", "LT"), ("3", "GHI", "MODE"), ("CLR", "", "")],
    [("4", "JKL", ""), ("5", "MNO", "ZERO"), ("6", "PQR", "lamp"), ("ENT", "", "")],
    [("7", "STU", "OPT"), ("8", "VWX", "PGM"), ("9", "YZ?", ""), None],
    [("0", "", "loop"), ("<", "", ""), (">", "", ""), None],
]
PRE = dict(x=0.0180, z0=0.0775, z1=0.0985)            # tall PRE +/- rocker in the right column
PRODUCT_POS = (0.0, 0.0655)

# top: headset connector at the left, knob in the center, antenna at the right
CONN = dict(x=-0.0205, y=-0.0010, r=0.0080, h=0.0150)
KNOB = dict(x=0.0010, y=-0.0010, r=0.0098, h=0.0150, teeth=24)
KNOB_MARKS = ["OFF", "PT", "1", "2", "3", "4", "5"]
ANT = dict(x=0.0215, y=-0.0010, nut_r=0.0070, base_r=0.0062, whip_r0=0.0056, whip_r1=0.0044, z_nut=H + 0.0060,
           z_spring=H + 0.0300, top=H + 0.1550)   # a third shorter (was 0.23): it used to poke through the head on the backpack

# sides: (y-center, z0, z1, width along y, protrusion)
PTT = (-0.0040, 0.1240, 0.1620, 0.0140, 0.0030)       # left side
SIDE_BTNS = [(-0.0040, 0.1700, 0.0040), (-0.0040, 0.1790, 0.0040)]
DATA_COVER = (-0.0020, 0.1300, 0.1650, 0.0120, 0.0015)  # right side

# battery
BAT = dict(w=0.0660, yf=-0.0195, yb=0.0205, latch_z=0.0505)
BAT_LABEL = dict(x0=-0.0240, x1=0.0240, z0=0.0080, z1=0.0440)

# back: nomenclature plate
PLATE = dict(w=0.0440, z0=0.0900, z1=0.1350, r=0.0020)


PPM = 40
FRONT_RECT = (-W / 2, W / 2, 0.0, H + 0.020)
KNOB_RECT = (KNOB["x"] - KNOB["r"], KNOB["x"] + KNOB["r"], H, H + KNOB["h"] + 0.001)
BACK_RECT = (-W / 2, W / 2, 0.0, H)
LCD_RECT = (LCD_WIN["cx"] - LCD_WIN["w"] / 2, LCD_WIN["cx"] + LCD_WIN["w"] / 2,
            LCD_WIN["cz"] - LCD_WIN["h"] / 2, LCD_WIN["cz"] + LCD_WIN["h"] / 2)

