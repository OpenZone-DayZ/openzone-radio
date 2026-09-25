"""Layout of the 5000 m radio (modeled after the Motorola XTS5000, a "service" radio) - shared numbers.

Model coordinates: X right, Y back (the face looks toward -Y), Z up, meters; origin - center of the bottom.
Reference (zombitt, Sketchfab): a tall black body; on top a volume knob on the left, a 16-position
channel switch with a T-shaped head in the middle, a toggle between them, and a thin long antenna on
the right; on the face a logo with the brand, a grille of square holes, a green LCD in a grey frame
that at the bottom turns into three programmable keys, an oval joystick, and a 3x4 keypad of
oval keys; on the left side a large round PTT and a purple button on top.
"""

MODEL = "ТЕРРАН"      # OZ-COM model name (the owner's choice, 25.09)

W = 0.062
H = 0.160
YF = -0.022
YB = 0.022
R_FRONT, R_BACK = 0.0045, 0.0060
BEV_TB = 0.0030
# the face overlay (front cover) is slightly narrower than the body and raised
FACE = dict(w=0.056, z0=0.004, z1=0.150, r=0.004, proud=0.0012)

LOGO = dict(x=0.0, z=0.1395)
GRILLE = dict(x0=-0.0215, x1=0.0215, z0=0.0985, z1=0.1310, hole=0.0016, pitch=0.0033, depth=0.0012)

# LCD frame with three keys under the screen (grey plastic)
LCD_FRAME = dict(w=0.0400, z0=0.0600, z1=0.0930, r=0.0030, proud=0.0014)
LCD_WIN = dict(cx=0.0, cz=0.0815, w=0.0340, h=0.0185, r=0.0012, depth=0.0010)
SOFTKEYS = [(-0.0118, 0.0653), (0.0, 0.0653), (0.0118, 0.0653)]
SOFTKEY = dict(w=0.0100, h=0.0040)

NAV = dict(x=0.0, z=0.0515, rx=0.0105, rz=0.0055)
NAV_SIDE = [(-0.0200, 0.0520), (0.0200, 0.0520)]      # "star-home" and "enter" on the sides of the joystick
KEY_COLS = (-0.0155, 0.0, 0.0155)
KEY_ROWS = (0.0400, 0.0310, 0.0220, 0.0130)
KEY_RX, KEY_RZ = 0.0060, 0.0032
KEY_PROUD = 0.0015
KEYS = [
    [("1", ""), ("2", "abc"), ("3", "def")],
    [("4", "ghi"), ("5", "jkl"), ("6", "mno")],
    [("7", "pqrs"), ("8", "tuv"), ("9", "wxyz")],
    [("*", ""), ("0", ""), ("#", "")],
]

# top
VOL = dict(x=-0.0185, y=-0.0010, r=0.0080, z0=H + 0.0010, h=0.0130)
CHAN = dict(x=0.0015, y=-0.0010, r=0.0070, z0=H + 0.0010, h=0.0150, grip_w=0.0170, grip_t=0.0050)
TOGGLE = dict(x=-0.0080, y=0.0040, z0=H, h=0.0070)
ANT = dict(x=0.0205, y=-0.0010, base_r=0.0068, whip_r0=0.0040, whip_r1=0.0026, z_base=H + 0.0160,
           top=H + 0.1500)

# left side: round PTT and purple button; two small ones between them
PTT = dict(y=-0.0060, z=0.0930, r=0.0110, proud=0.0028)
TOP_BTN = dict(y=-0.0080, z=0.1350, r=0.0038, proud=0.0018)
SIDE_SMALL = [(-0.0080, 0.1180), (-0.0080, 0.1105)]

BAT = dict(w=0.058, y0=0.013, y1=0.022, top=0.120)
CLIP_W, CLIP_TOP, CLIP_BOT = 0.030, 0.118, 0.055


PPM = 40
FRONT_RECT = (-W / 2, W / 2, 0.0, H)
LEFT_RECT = (-0.026, 0.024, 0.080, 0.150)
TOP_RECT = (-W / 2, W / 2, -0.024, 0.024)             # top: a = x, b = -y (front is at the bottom of the image)
BACK_RECT = (-W / 2, W / 2, 0.0, H)
LCD_RECT = (LCD_WIN["cx"] - LCD_WIN["w"] / 2, LCD_WIN["cx"] + LCD_WIN["w"] / 2,
            LCD_WIN["cz"] - LCD_WIN["h"] / 2, LCD_WIN["cz"] + LCD_WIN["h"] / 2)

