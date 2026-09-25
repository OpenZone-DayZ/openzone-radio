"""Frequency window "as the radio's face": what to show and what each key does, per radio.

Shared numbers for three consumers: the face renderer (tools/render_hud_faces.py, Blender Python),
the layout generator (tools/make_hud_layouts.py, system Python) and - through widget names -
the OZR_FreqMenuFace.c script (main mod). Key coordinates are not repeated here: they come from
assets/<radio>/scripts/layout_<s>.py, the same numbers that built the model.

Key roles are the widget names of the companion window (OZR_FreqMenu.c) plus one of its own:
    Btn0..Btn9  digit                 BtnUp / BtnDown  step through its own channels
    BtnGo       tune (TUNE)           BtnDot           dot
    BtnClose    close immediately     BtnBack          erase a digit, or close if there is nothing to erase
"""
import importlib
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# The window frame around the face: margins on the sides (side buttons), above the body (knobs, antenna base)
# and below it. The antenna is cut off by the top edge.
SIDE = 0.012
ABOVE = 0.028
BELOW = 0.003
CAPTION = 46            # px: the strip below the radio - name and hint
TEX_W, TEX_H = 1024, 2048   # render canvas; the mod gets half that size (EDDS - see make_hud_layouts)
TEX_MAX_PPMM = 12.0     # render px per mm - a ceiling, past this it is too small to see anyway

RADIOS = {
    # step: no digits, the arrows switch channel at once; the screen shows the channel number big.
    # scale - window px per mm of the face at 1080p: the window comes out ~650-720 px tall, keys >= 25 px.
    # lcd: seg - segment LCD (7segment font and "ghost" 888), dot - dot matrix (text).
    # ink - the color of the characters on the screen; hint - the hint key under the radio (stringtable.csv).
    "pmr_t388": dict(stem="t388", mode="step", scale=4.9, lcd="seg", ink=(0.086, 0.106, 0.086), hint="STEP"),
    "lxt": dict(stem="lxt", mode="step", scale=4.3, lcd="seg", ink=(0.16, 0.10, 0.03), hint="STEP"),
    # keypad: frequency entry; it stands on top, is typed in below
    "uv5r": dict(stem="uv5r", mode="keypad", scale=5.0, lcd="seg", ink=(0.086, 0.106, 0.086), hint="MENU"),
    "uvs9": dict(stem="uvs9", mode="keypad", scale=4.5, lcd="seg", ink=(0.086, 0.106, 0.086), hint="MENU"),
    "xts": dict(stem="xts", mode="keypad", scale=3.6, lcd="dot", ink=(0.07, 0.13, 0.06), hint="ENTER"),
    "prc152": dict(stem="prc152", mode="keypad", scale=3.0, lcd="dot", ink=(0.06, 0.10, 0.05), hint="ENT"),
}

BAOFENG_ROLES = {"MENU": "BtnGo", "^": "BtnUp", "v": "BtnDown", "EXIT": "BtnBack", "*": "BtnDot"}


def layout_module(radio):
    """The radio's layout_<s>.py - the same numbers that built the model."""
    stem = RADIOS[radio]["stem"]
    scripts = os.path.join(ROOT, "assets", radio, "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return importlib.import_module("layout_" + stem)


def region(radio):
    """The face rectangle in model meters: x0, x1, z0, z1 (x right, z up)."""
    L = layout_module(radio)
    return (-L.W / 2 - SIDE, L.W / 2 + SIDE, -BELOW, L.H + ABOVE)


def tex_ppmm(radio):
    x0, x1, z0, z1 = region(radio)
    return min(TEX_W / ((x1 - x0) * 1000), TEX_H / ((z1 - z0) * 1000), TEX_MAX_PPMM)


def keys(radio):
    """[(role, x, z, w, h, round)] - the keys that work in the window, in model meters."""
    L = layout_module(radio)
    out = []
    if radio == "pmr_t388":
        for x, z, rx, rz, mat, txt in L.BUTTONS:
            # the red power button closes the window - like EXIT on the others (the owner's request, 25.09)
            role = {"^": "BtnUp", "v": "BtnDown", "pwr": "BtnClose"}.get(txt)
            if role:
                out.append((role, x, z, rx * 2, rz * 2, True))
    elif radio == "lxt":
        for x, z, side, label, sub in L.BUTTONS:
            role = {"^": "BtnUp", "v": "BtnDown"}.get(label)
            if role:
                out.append((role, x, z, L.BTN_W, L.BTN_H, False))
    elif radio in ("uv5r", "uvs9"):
        for r, row in enumerate(L.KEYS):
            for c, key in enumerate(row):
                name = key[0]
                role = "Btn" + name if name.isdigit() else BAOFENG_ROLES.get(name)
                if role:
                    out.append((role, L.KEY_COLS[c], L.KEY_ROWS[r], L.KEY_W, L.KEY_H, False))
    elif radio == "xts":
        # digits, * - dot, # - erase; joystick up/down - step; enter is to its right, exit to its left
        for r, row in enumerate(L.KEYS):
            for c, key in enumerate(row):
                name = key[0]
                role = "Btn" + name if name.isdigit() else {"*": "BtnDot", "#": "BtnBack"}.get(name)
                if role:
                    out.append((role, L.KEY_COLS[c], L.KEY_ROWS[r], L.KEY_RX * 2, L.KEY_RZ * 2, True))
        n = L.NAV
        out.append(("BtnUp", n["x"], n["z"] + n["rz"] * 0.55, n["rx"] * 0.9, n["rz"] * 0.8, True))
        out.append(("BtnDown", n["x"], n["z"] - n["rz"] * 0.55, n["rx"] * 0.9, n["rz"] * 0.8, True))
        (lx, lz), (rx_, rz_) = L.NAV_SIDE
        out.append(("BtnGo", rx_, rz_, 0.0065, 0.0065, True))
        out.append(("BtnClose", lx, lz, 0.0065, 0.0065, True))
    elif radio == "prc152":
        # digits, ENT - enter, CLR and < - erase, > - dot; the PRE +/- rocker - step
        for r, row in enumerate(L.KEYS):
            for c, key in enumerate(row):
                if key is None:
                    continue
                name = key[0]
                role = "Btn" + name if name.isdigit() else {"ENT": "BtnGo", "CLR": "BtnBack", "<": "BtnBack", ">": "BtnDot"}.get(name)
                if role:
                    out.append((role, L.KEY_COLS[c], L.KEY_ROWS[r], L.KEY_W, L.KEY_H, False))
        p = L.PRE
        zm = (p["z0"] + p["z1"]) / 2
        out.append(("BtnUp", p["x"], (zm + p["z1"]) / 2, L.KEY_W, (p["z1"] - zm) * 0.9, False))
        out.append(("BtnDown", p["x"], (p["z0"] + zm) / 2, L.KEY_W, (zm - p["z0"]) * 0.9, False))
    return out


def lcd_rect(radio):
    L = layout_module(radio)
    w = L.LCD_WIN
    return (w["cx"] - w["w"] / 2, w["cx"] + w["w"] / 2, w["cz"] - w["h"] / 2, w["cz"] + w["h"] / 2)

