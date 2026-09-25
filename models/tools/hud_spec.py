"""Окно частот «лицом рации»: что показывать и какие клавиши что делают, по рациям.

Общие числа для трёх потребителей: рендера лица (tools/render_hud_faces.py, Python Blender),
генератора разметки (tools/make_hud_layouts.py, системный Python) и - через имена виджетов -
скрипта OZR_FreqMenuFace.c (основной мод). Координаты клавиш не повторяются здесь: их берут из
assets/<рация>/scripts/layout_<s>.py, тех же чисел, что построили модель.

Роли клавиш - это имена виджетов окна друга (OZR_FreqMenu.c) плюс одна своя:
    Btn0..Btn9  цифра                 BtnUp / BtnDown  шаг по своим каналам
    BtnGo       настроить (TUNE)      BtnDot           точка
    BtnClose    закрыть сразу         BtnBack          стереть цифру, а если стирать нечего - закрыть
"""
import importlib
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Кадр окна вокруг лица: поля по бокам (боковые кнопки), над корпусом (ручки, низ антенны)
# и под ним. Антенна срезается верхним краем.
SIDE = 0.012
ABOVE = 0.028
BELOW = 0.003
CAPTION = 46            # px: полоска под рацией - название и подсказка
TEX_W, TEX_H = 1024, 2048   # холст рендера; в мод идёт вдвое меньше (EDDS - см. make_hud_layouts)
TEX_MAX_PPMM = 12.0     # px рендера на мм - потолок, дальше мельче уже не видно

RADIOS = {
    # step: цифр нет, стрелки сразу переключают канал; на экране крупно номер канала.
    # scale - px окна на мм лица при 1080p: окно выходит ~650-720 px в высоту, клавиши >= 25 px.
    # lcd: seg - сегментный ЖКИ (шрифт 7segment и «призраки» 888), dot - точечная матрица (текст).
    # ink - цвет символов на экране; hint - ключ подсказки под рацией (stringtable.csv).
    "pmr_t388": dict(stem="t388", mode="step", scale=4.9, lcd="seg", ink=(0.086, 0.106, 0.086), hint="STEP"),
    "lxt": dict(stem="lxt", mode="step", scale=4.3, lcd="seg", ink=(0.16, 0.10, 0.03), hint="STEP"),
    # keypad: набор частоты; сверху стоит, снизу набирается
    "uv5r": dict(stem="uv5r", mode="keypad", scale=5.0, lcd="seg", ink=(0.086, 0.106, 0.086), hint="MENU"),
    "uvs9": dict(stem="uvs9", mode="keypad", scale=4.5, lcd="seg", ink=(0.086, 0.106, 0.086), hint="MENU"),
    "xts": dict(stem="xts", mode="keypad", scale=3.6, lcd="dot", ink=(0.07, 0.13, 0.06), hint="ENTER"),
    "prc152": dict(stem="prc152", mode="keypad", scale=3.0, lcd="dot", ink=(0.06, 0.10, 0.05), hint="ENT"),
}

BAOFENG_ROLES = {"MENU": "BtnGo", "^": "BtnUp", "v": "BtnDown", "EXIT": "BtnBack", "*": "BtnDot"}


def layout_module(radio):
    """layout_<s>.py рации - те же числа, что построили модель."""
    stem = RADIOS[radio]["stem"]
    scripts = os.path.join(ROOT, "assets", radio, "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return importlib.import_module("layout_" + stem)


def region(radio):
    """Прямоугольник лица в метрах модели: x0, x1, z0, z1 (x вправо, z вверх)."""
    L = layout_module(radio)
    return (-L.W / 2 - SIDE, L.W / 2 + SIDE, -BELOW, L.H + ABOVE)


def tex_ppmm(radio):
    x0, x1, z0, z1 = region(radio)
    return min(TEX_W / ((x1 - x0) * 1000), TEX_H / ((z1 - z0) * 1000), TEX_MAX_PPMM)


def keys(radio):
    """[(роль, x, z, w, h, круглая)] - клавиши, которые работают в окне, в метрах модели."""
    L = layout_module(radio)
    out = []
    if radio == "pmr_t388":
        for x, z, rx, rz, mat, txt in L.BUTTONS:
            # красная кнопка питания закрывает окно - как EXIT у других (просьба пользователя 25.09)
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
        # цифры, * - точка, # - стереть; джойстик вверх/вниз - шаг; справа от него ввод, слева выход
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
        # цифры, ENT - ввод, CLR и < - стереть, > - точка; качелька PRE +/- - шаг
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

