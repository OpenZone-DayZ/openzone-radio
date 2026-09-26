"""Player-facing tutorial: how to use the radios - in one picture.

    python tools/render_tutorial.py [out.png] [--lang en|uk]       (system Python with Pillow)

Without --lang - English (../docs/tutorial/tutorial.en.png/.jpg); --lang uk writes tutorial.uk.png/.jpg there,
the text comes from tutorial_i18n.py laid over the same markup.

Assembled from the same things as the game and the window legend: faces - assets/<radio>/work/hud/face.png, keys -
hud_spec.keys through the window layout's Frame, the lineup - build/tutorial/lineup.png and lineup.json (rendered
by `blender -b -P tools/render_tutorial_lineup.py`). Markup - tools/tutorial.html, the shot is taken with
headless Chrome. Changed the model, key roles or text - rerun it, the picture matches the game again.
"""
import json
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hud_spec as S  # noqa: E402
import make_hud_layouts as M  # noqa: E402
import render_hud_legend as L  # noqa: E402

ARGS = sys.argv[1:]
LANG = ARGS[ARGS.index("--lang") + 1] if "--lang" in ARGS else "en"
POS = [a for i, a in enumerate(ARGS) if not a.startswith("--") and (i == 0 or ARGS[i - 1] != "--lang")]
DOCS = os.path.normpath(os.path.join(S.ROOT, "..", "docs", "tutorial"))   # the repository's docs, where players look
OUT = POS[0] if POS else os.path.join(DOCS, "tutorial.%s.png" % LANG)
BUILD = os.path.join(S.ROOT, "build", "tutorial")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
WIDTH = 1920
ORDER = L.ORDER
K = L.K

# the example screen: keypad radios dial 145.5, the no-digit radio shows channel 191 - the same 145.500
SHOWN = {"step": {"LcdMain": "191", "LcdSub": "145.500"}, "keypad": {"LcdMain": "136.000", "LcdSub": "145.5"}}


def panel(radio):
    """Face, tape and screen - like the legend's panel(), but without frames: the markup draws the keys."""
    f = M.Frame(radio)
    spec = f.spec
    W, H = int(f.w * K), int(f.h * K)
    tw, th = S.TEX_W / f.t * f.s * K, S.TEX_H / f.t * f.s * K
    face = Image.open(os.path.join(S.ROOT, "assets", radio, "work", "hud", "face.png")).convert("RGBA")
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.alpha_composite(face.resize((int(tw), int(th)), Image.LANCZOS).crop((0, 0, W, H)))

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ghosts = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d, dg = ImageDraw.Draw(layer), ImageDraw.Draw(ghosts)
    lx, ly, lw, lh = [v * K for v in f.ui_rect(*S.lcd_rect(radio))]
    ink = tuple(int(c * 255) for c in spec["ink"])
    seg = spec["lcd"] == "seg"
    y = ly
    for name, ghost, share, halign in M.lcd_lines(f):
        hh = lh * share
        pad = lw * 0.06
        fnt = L.font(L.SEG_TTF, hh * 0.95) if seg else L.font(L.TEXT_TTF, min(hh * 0.80, (lw - 2 * pad) / (7 * 0.60)))
        rect = (lx + pad, y, lw - 2 * pad, hh)
        L.put_text(dg, rect, ghost, fnt, ink + (18,), halign)
        L.put_text(d, rect, SHOWN[spec["mode"]][name], fnt, ink + (235,), halign)
        y += hh
    img.alpha_composite(ghosts)
    img.alpha_composite(layer)

    keys = []
    for widget, x, z, w, h, rnd in S.keys(radio):
        bx, by, bw, bh = [v * K for v in f.ui_rect(x - w / 2 - M.KEY_PAD, x + w / 2 + M.KEY_PAD,
                                                    z - h / 2 - M.KEY_PAD, z + h / 2 + M.KEY_PAD)]
        keys.append({"role": L.role_of(widget), "x": bx / W, "y": by / H, "w": bw / W, "h": bh / H, "round": rnd})
    cs = 26 * K     # the cross in the window's corner - every radio has one, same spot as in the legend
    keys.append({"role": "close", "x": (W - cs - 6 * K) / W, "y": 6 * K / H, "w": cs / W, "h": cs / H,
                 "round": True, "cross": True})
    name = "face_%s.png" % radio
    img.save(os.path.join(BUILD, name))
    return {"img": name, "w": W, "h": H, "keys": keys}


def chrome(*args):
    # Its own profile: headless Chrome's shared temp profile is left behind by hung runs, and
    # the next ones hang on it too. A hung run is killed by the timeout, then we try again.
    for attempt in range(3):
        try:
            return subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                                   "--force-device-scale-factor=1", "--allow-file-access-from-files",
                                   "--user-data-dir=" + os.path.join(BUILD, "chrome")] + list(args),
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        except subprocess.TimeoutExpired:
            print("render_tutorial: Chrome hung, attempt", attempt + 2)
    sys.exit("render_tutorial: Chrome is not responding")


def main():
    os.makedirs(BUILD, exist_ok=True)
    lineup = json.load(open(os.path.join(BUILD, "lineup.json"), encoding="utf-8"))
    data = {"faces": {r: panel(r) for r in ORDER}, "lineup": lineup, "colors": {k: "rgb(%d,%d,%d)" % v[0]
                                                                                 for k, v in L.ROLE.items()}}
    html = open(os.path.join(HERE, "tutorial.html"), encoding="utf-8").read()
    if LANG != "en":
        from tutorial_i18n import TRANSLATIONS
        for src, dst in TRANSLATIONS[LANG]:
            if src not in html:
                sys.exit("render_tutorial: no chunk to translate in the markup: %r" % src[:80])
            html = html.replace(src, dst)
        html = html.replace('<html lang="en">', '<html lang="%s">' % LANG)
    html = html.replace("/*DATA*/null", json.dumps(data))
    page = os.path.join(BUILD, "index.html")
    open(page, "w", encoding="utf-8").write(html)
    url = "file:///" + page.replace("\\", "/")

    # pass 1: only the markup knows the poster's height - it writes it into body data-h
    dom = chrome("--window-size=%d,1200" % WIDTH, "--dump-dom", url).stdout
    m = re.search(r'data-h="(\d+)"', dom)
    if not m:
        sys.exit("render_tutorial: the markup did not report a height\n" + dom[:500])
    height = int(m.group(1))
    shot = os.path.join(BUILD, "shot.png")
    chrome("--window-size=%d,%d" % (WIDTH, height), "--screenshot=" + shot, url)
    img = Image.open(shot).convert("RGB")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, optimize=True)
    img.save(os.path.splitext(OUT)[0] + ".jpg", quality=90)
    print("tutorial:", OUT, img.size)


if __name__ == "__main__":
    main()
