"""Drawing labels, LCD displays and stickers for radios (system Python + Pillow, no numpy).

The canvas is defined in model millimeters: rectangle x0..x1 (right) and z0..z1 (up) on the
front plane, as seen by someone looking from the front. This way labels are drawn using the
same numbers that build_<radio>.py uses to build the buttons, and they match the geometry
without any fitting.
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = r"C:\Windows\Fonts"
FONT_FILES = {
    "din": "bahnschrift.ttf",       # instrument grotesque: keys, nameplates
    "din_cond": "bahnschrift.ttf",
    "arial": "arial.ttf",
    "arial_b": "arialbd.ttf",
    "narrow": "ARIALN.TTF",
    "narrow_b": "ARIALNB.TTF",
    "agency": "AGENCYB.TTF",        # military stencils
    "agency_r": "AGENCYR.TTF",
    "ocr": "OCRAEXT.TTF",
    "impact": "impact.ttf",
    "verdana_b": "verdanab.ttf",
    "hand": "segoeprb.ttf",         # marker on masking tape
    "hand_r": "segoepr.ttf",
    "tahoma_b": "tahomabd.ttf",
}
# for the variable-font bahnschrift, the style is selected by name
FONT_VARIANTS = {"din": b"Bold", "din_cond": b"SemiBold Condensed"}

_cache = {}


def font(name, px):
    key = (name, int(px))
    if key not in _cache:
        f = ImageFont.truetype(os.path.join(FONTS, FONT_FILES[name]), max(4, int(round(px))))
        if name in FONT_VARIANTS:
            try:
                f.set_variation_by_name(FONT_VARIANTS[name])
            except Exception:
                pass
        _cache[key] = f
    return _cache[key]


class Canvas:
    """RGBA canvas over the model's rectangle. ppm - pixels per millimeter."""

    def __init__(self, x0, x1, z0, z1, ppm=24, bg=(0, 0, 0, 0)):
        self.x0, self.x1, self.z0, self.z1 = x0, x1, z0, z1
        self.ppm = ppm
        self.w = int(round((x1 - x0) * 1000 * ppm))
        self.h = int(round((z1 - z0) * 1000 * ppm))
        self.img = Image.new("RGBA", (self.w, self.h), bg)
        self.d = ImageDraw.Draw(self.img)

    # --- coordinates: model meters -> pixels
    def px(self, x, z):
        return ((x - self.x0) * 1000 * self.ppm, (self.z1 - z) * 1000 * self.ppm)

    def mm(self, v):
        return v * 1000 * self.ppm

    def text(self, s, x, z, h, fnt="din", fill=(235, 235, 230, 255), anchor="mm", rot=0.0, spacing=0.0, fit=None):
        """A string of height h (meters, cap height) centered at (x, z). fit - width in meters
        that the string must fit into: a long model name shrinks instead of overlapping
        neighboring buttons."""
        size = self.mm(h) * 1.38          # font size -> cap height ~0.72
        f = font(fnt, size)
        if fit:
            wide = f.getlength(s) + spacing * self.ppm * 1000 * len(s)
            if wide > self.mm(fit):
                size *= self.mm(fit) / wide
                f = font(fnt, size)
        if not rot and not spacing:
            self.d.text(self.px(x, z), s, font=f, fill=fill, anchor=anchor)
            return
        # rotation/letter-spacing: draw on our own layer and paste it in
        bbox = f.getbbox(s)
        tw = bbox[2] - bbox[0] + int(abs(spacing) * self.ppm * 1000 * len(s)) + 8
        th = int(size * 1.6) + 8
        layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        if spacing:
            cx = 4
            for ch in s:
                ld.text((cx, th / 2), ch, font=f, fill=fill, anchor="lm")
                cx += f.getlength(ch) + spacing * self.ppm * 1000
            layer = layer.crop((0, 0, int(cx) + 4, th))
        else:
            ld.text((tw / 2, th / 2), s, font=f, fill=fill, anchor="mm")
        if rot:
            layer = layer.rotate(rot, resample=Image.BICUBIC, expand=True)
        cx, cy = self.px(x, z)
        self.img.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))

    def rect(self, x0, z0, x1, z1, fill=None, outline=None, width=0.0, r=0.0):
        a, b = self.px(x0, z1), self.px(x1, z0)
        w = max(1, int(round(self.mm(width)))) if outline else 0
        if r > 0:
            self.d.rounded_rectangle((a, b), radius=self.mm(r), fill=fill, outline=outline, width=w)
        else:
            self.d.rectangle((a, b), fill=fill, outline=outline, width=w)

    def line(self, pts, fill, width):
        self.d.line([self.px(x, z) for x, z in pts], fill=fill, width=max(1, int(round(self.mm(width)))))

    def poly(self, pts, fill):
        self.d.polygon([self.px(x, z) for x, z in pts], fill=fill)

    def tri(self, x, z, s, up=True, fill=(235, 235, 230, 255)):
        """Arrow triangle with side s."""
        h = s * 0.8
        sgn = 1 if up else -1
        self.poly([(x - s / 2, z - sgn * h / 2), (x + s / 2, z - sgn * h / 2), (x, z + sgn * h / 2)], fill)

    def ellipse(self, x, z, rx, rz, fill=None, outline=None, width=0.0):
        a, b = self.px(x - rx, z + rz), self.px(x + rx, z - rz)
        self.d.ellipse((a, b), fill=fill, outline=outline, width=max(1, int(round(self.mm(width)))) if outline else 0)

    def save(self, path, size=None):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img = self.img
        if size:
            img = img.resize(size, Image.LANCZOS)
        img.save(path)
        print("wrote", path, img.size)


# =============================================================================
# Seven-segment digits
# =============================================================================
SEGS = {
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc",
    "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g", " ": "", "A": "abcefg", "b": "cdefg", "C": "adef",
    "d": "bcdeg", "E": "adefg", "F": "aefg", "H": "bcefg", "L": "def", "P": "abefg", "r": "eg", "o": "cdeg",
    "n": "ceg", "t": "defg", "U": "bcdef", "u": "cde", "S": "afgcd",
}


def seg7_polys(x, z, h, slant=0.1, thick=0.16):
    """Polygons of segments a..g of a digit of height h with its bottom-left corner at (x, z)."""
    w = h * 0.52
    t = h * thick
    g = t * 0.18                       # gap between segments

    def sk(px_, pz):
        return (px_ + (pz - z) * slant, pz)

    def hseg(zc):
        xa, xb = x + g + t * 0.5, x + w - g - t * 0.5
        return [sk(xa, zc), sk(xa + t * 0.5, zc + t / 2), sk(xb - t * 0.5, zc + t / 2), sk(xb, zc),
                sk(xb - t * 0.5, zc - t / 2), sk(xa + t * 0.5, zc - t / 2)]

    def vseg(xc, za, zb):
        za, zb = za + g + t * 0.5, zb - g - t * 0.5
        return [sk(xc, za), sk(xc + t / 2, za + t * 0.5), sk(xc + t / 2, zb - t * 0.5), sk(xc, zb),
                sk(xc - t / 2, zb - t * 0.5), sk(xc - t / 2, za + t * 0.5)]

    zm = z + h / 2
    return {
        "a": hseg(z + h - t / 2), "g": hseg(zm), "d": hseg(z + t / 2),
        "f": vseg(x + t / 2, zm, z + h), "b": vseg(x + w - t / 2, zm, z + h),
        "e": vseg(x + t / 2, z, zm), "c": vseg(x + w - t / 2, z, zm),
    }


def seg7_text(cv, s, x, z, h, on=(20, 24, 20, 255), ghost=(0, 0, 0, 22), pitch=0.66, dot_after=None):
    """A string of seven-segment characters; ghost - barely visible unlit segments (LCD off)."""
    cx = x
    for i, ch in enumerate(s):
        if ch == ".":
            continue
        polys = seg7_polys(cx, z, h)
        lit = SEGS.get(ch, "")
        for k, p in polys.items():
            col = on if k in lit else ghost
            if col and col[3] > 0:
                cv.poly(p, col)
        cx += h * pitch
        if i + 1 < len(s) and s[i + 1] == ".":
            cv.ellipse(cx - h * 0.1, z + h * 0.07, h * 0.06, h * 0.06, fill=on)
    return cx


# =============================================================================
# LCD display: backing + a transparent "ghosts" layer, blended on top
# =============================================================================
def lcd_canvas(rect, ppm, light, dark, vignette=0.45, blur=35):
    """Backing of a powered-off LCD (light center, dark edges) and a TRANSPARENT canvas for
    unlit segments and labels.

    Ghosts cannot be drawn directly on the opaque backing: ImageDraw does not blend, it
    REPLACES the pixel along with its alpha, so a segment with alpha 20 became a hole showing
    the material's gray color through the model - light digits, as if the screen were on."""
    bg = Canvas(*rect, ppm=ppm, bg=tuple(light) + (255,))
    shade = Image.radial_gradient("L").resize((bg.w, bg.h)).filter(ImageFilter.GaussianBlur(blur))
    bg.img = Image.composite(Image.new("RGBA", (bg.w, bg.h), tuple(dark) + (255,)), bg.img,
                             shade.point(lambda v: int(v * vignette)))
    return bg, Canvas(*rect, ppm=ppm)


def lcd_finish(bg, over, path, blur=0.8):
    over.img = Image.alpha_composite(bg.img, over.img).filter(ImageFilter.GaussianBlur(blur))
    over.save(path)


# =============================================================================
# Masking-tape sticker with marker writing (range marker)
# =============================================================================
def tape_label(path, text, size=(256, 128), seed=1, tape=(206, 190, 146), ink=(26, 28, 40), sub=None,
               font_name="hand", rot=-3.0):
    """A piece of masking tape: uneven tone, fibers, fold shadows, marker writing.

    The ragged edges are in the geometry, not the texture (the strap in the model has jagged
    ends) - the texture is opaque, _co. So no alpha or separate transparent-section sorting is needed."""
    rng = random.Random(seed)
    w, h = size
    img = Image.new("RGB", (w, h), tape)
    px = img.load()
    # lengthwise fibers and stains
    for yy in range(h):
        streak = rng.uniform(-6, 6)
        for xx in range(w):
            n = streak + rng.uniform(-5, 5)
            r, g, b = px[xx, yy]
            px[xx, yy] = (int(r + n), int(g + n), int(b + n * 0.8))
    d = ImageDraw.Draw(img)
    for _ in range(5):
        cx, cy, rr = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(8, 30)
        d.ellipse((cx - rr, cy - rr * 0.6, cx + rr, cy + rr * 0.6), fill=(tape[0] - 18, tape[1] - 20, tape[2] - 22))
    img = img.filter(ImageFilter.GaussianBlur(2.2))
    # folds: a couple of dark diagonal strokes
    d = ImageDraw.Draw(img)
    for _ in range(2):
        x0 = rng.uniform(0, w)
        d.line((x0, 0, x0 + rng.uniform(-30, 30), h), fill=(tape[0] - 30, tape[1] - 32, tape[2] - 30), width=1)
    # dirt toward the edges
    edge = Image.new("L", (w, h), 0)
    ed = ImageDraw.Draw(edge)
    for i in range(10):
        ed.rectangle((i, i, w - 1 - i, h - 1 - i), outline=int(60 - i * 6))
    dirt = Image.new("RGB", (w, h), (90, 80, 60))
    img = Image.composite(dirt, img, edge.filter(ImageFilter.GaussianBlur(3)))
    # marker writing: layer, rotation, slightly blurred edge - soaked into the paper
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    fs = int(h * (0.52 if sub is None else 0.46))
    f = font(font_name, fs)
    ty = h * (0.5 if sub is None else 0.40)
    ld.text((w / 2, ty), text, font=f, fill=ink + (235,), anchor="mm")
    if sub:
        ld.text((w / 2, h * 0.80), sub, font=font(font_name, int(h * 0.22)), fill=ink + (220,), anchor="mm")
    layer = layer.rotate(rot, resample=Image.BICUBIC).filter(ImageFilter.GaussianBlur(0.6))
    img = img.convert("RGBA")
    img.alpha_composite(layer)
    img = img.convert("RGB")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    print("wrote", path, img.size)


# =============================================================================
# OZ-COM mark - one for all radios, like BIS-COM on the vanilla one
# =============================================================================
# The mark is an open ring (a zone with an exit), a transmitter dot at the center, and a wave
# heading out through the gap. There is deliberately no separate letter Z in the mark: for the
# series' Ukrainian-speaking audience it is a foreign symbol; "OZ" lives only inside the text.
# The accent is the ACCENT color from the OpenZone Core palette (OZ_Palette, 4FB5E8).
BRAND = "OZ-COM"
BRAND_ACCENT = (79, 181, 232, 255)
BRAND_FONT, BRAND_TRACK = "din", 0.10          # bahnschrift Bold; tracking - fraction of cap height
_SS = 3                                        # the mark and letters are drawn three times larger - smooth edges


def _cap_font(name, cap):
    """A font where the capital H is exactly cap pixels tall."""
    size = max(6, int(cap / 0.72))
    for _ in range(4):
        bb = font(name, size).getbbox("H")
        size = max(6, int(round(size * cap / (bb[3] - bb[1]))))
    return font(name, size)


def _word(s, fnt, cap, fill, track):
    """A string with letter-spacing; capitals from y = 2 to y = 2 + cap."""
    f = _cap_font(fnt, cap)
    top = f.getbbox("H")[1]
    ws = [f.getlength(ch) for ch in s]
    img = Image.new("RGBA", (int(sum(ws) + track * cap * (len(s) - 1)) + 4, int(cap * 1.3) + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 2
    for ch, w in zip(s, ws):
        d.text((x, 2 - top), ch, font=f, fill=fill)
        x += w + track * cap
    return img


def _round_arc(d, cx, cy, r, a0, a1, w, fill):
    """An arc of thickness w with rounded ends; r - outer radius, PIL angles (from 3 o'clock, clockwise)."""
    d.arc((cx - r, cy - r, cx + r, cy + r), a0, a1, fill=fill, width=int(round(w)))
    for a in (a0, a1):
        rr = r - w / 2
        x, y = cx + rr * math.cos(math.radians(a)), cy + rr * math.sin(math.radians(a))
        d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=fill)


def brand_mark_art(cap, fill, accent=None):
    """Mark to go with the text, capitals cap px tall: the ring sits slightly above the capitals (1.2 cap).
    Returns the image and the ring's center in its pixel coordinates."""
    R = cap * 0.60
    w = R * 0.30
    c = R * 1.9
    img = Image.new("RGBA", (int(c * 2), int(c * 2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _round_arc(d, c, c, R, -12, 282, w, fill)                 # gap at the top right
    dot = R * 0.34
    d.ellipse((c - dot, c - dot, c + dot, c + dot), fill=accent or fill)
    _round_arc(d, c, c, R * 1.62, 292, 338, w * 0.85, accent or fill)
    x0, y0, x1, y1 = img.getbbox()
    return img.crop((x0, y0, x1, y1)), (c - x0, c - y0)


def brand_art(cap, fill, accent=None, name=True, suffix=None, suffix_font="din", suffix_scale=0.8):
    """Mark + OZ-COM (+ a tail, e.g. the model name) on one line. The ring's center sits at the
    middle of the capitals. Returns the image and the y of the capitals' middle in its pixel coordinates."""
    mark, (mcx, mcy) = brand_mark_art(cap, fill, accent)
    parts = []
    if name:
        parts.append((_word(BRAND, BRAND_FONT, cap, fill, BRAND_TRACK), int(cap * 0.30)))
    if suffix:
        sc = cap * suffix_scale
        parts.append((_word(suffix, suffix_font, sc, fill, 0.06), int(cap * 0.55)))
    above = max(mcy, cap / 2 + 2)                 # from the middle of the capitals to the top of the line
    below = max(mark.height - mcy, cap * 0.8 + 4)
    width = mark.width + sum(p.width + gap for p, gap in parts)
    img = Image.new("RGBA", (int(width) + 2, int(above + below) + 2), (0, 0, 0, 0))
    img.alpha_composite(mark, (0, int(round(above - mcy))))
    x = mark.width
    for i, (p, gap) in enumerate(parts):
        x += gap
        pc = cap if (i == 0 and name) else cap * suffix_scale
        # the tail is smaller than the mark and sits with it on the same letter baseline, not centered
        img.alpha_composite(p, (int(x), int(round(above + cap / 2 - 2 - pc))))
        x += p.width
    return img, above


def brand(cv, x, z, cap, fill, accent=None, anchor="m", **kw):
    """Mark on canvas cv: capitals of height cap meters, their middle at height z; anchor "m" -
    line centered at x, "l" - left edge at x. kw - same as brand_art (name, suffix...)."""
    art, mid = brand_art(cv.mm(cap) * _SS, fill, accent, **kw)
    art = art.resize((max(1, round(art.width / _SS)), max(1, round(art.height / _SS))), Image.LANCZOS)
    mid /= _SS
    px, pz = cv.px(x, z)
    left = px - art.width / 2 if anchor == "m" else px
    cv.img.alpha_composite(art, (int(round(left)), int(round(pz - mid))))


def noise_speckle(cv, count, color, size_px=(1, 3), seed=3):
    """Small specks (chipped print)."""
    rng = random.Random(seed)
    for _ in range(count):
        x, y = rng.uniform(0, cv.w), rng.uniform(0, cv.h)
        s = rng.uniform(*size_px)
        cv.d.ellipse((x - s, y - s, x + s, y + s), fill=color)


def value_noise(w, h, cell, seed, octaves=3):
    """Smooth 0..255 noise (L): a random grid stretched bicubically, several octaves."""
    rng = random.Random(seed)
    acc = None
    amp, total = 1.0, 0.0
    for o in range(octaves):
        c = max(2, int(cell / (2 ** o)))
        gw, gh = w // c + 2, h // c + 2
        small = Image.new("L", (gw, gh))
        small.putdata([rng.randint(0, 255) for _ in range(gw * gh)])
        layer = small.resize((w + 2 * c, h + 2 * c), Image.BICUBIC).crop((c, c, w + c, h + c))
        if acc is None:
            acc = layer.point(lambda v, a=amp: v * a)
        else:
            acc = Image.blend(acc, layer, amp / (total + amp))
        total += amp
        amp *= 0.5
    return acc


def wear_print(img, amount=0.35, seed=5, cell=90, scratches=40):
    """Worn print: patches of wear via smooth noise (not circles) and occasional scratches.

    amount - fraction of the area where the print has visibly faded. The noise threshold is
    chosen so the worn patches are ragged and uneven, like worn-off paint, while most of the
    text stays intact."""
    rng = random.Random(seed)
    w, h = img.size
    n = value_noise(w, h, cell, seed)
    lo = int(255 * (1.0 - amount))              # below the threshold - print intact
    mask = n.point(lambda v: 255 if v < lo else max(0, 255 - (v - lo) * 6))
    md = ImageDraw.Draw(mask)
    for _ in range(scratches):                   # thin scratches across
        x0, y0 = rng.uniform(0, w), rng.uniform(0, h)
        ang = rng.uniform(0, math.pi)
        ln = rng.uniform(0.02, 0.12) * w
        md.line((x0, y0, x0 + math.cos(ang) * ln, y0 + math.sin(ang) * ln), fill=rng.randint(40, 140),
                width=max(1, int(w / 900)))
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    r, g, b, a = img.split()
    a = Image.composite(a, Image.new("L", (w, h), 0), mask)
    return Image.merge("RGBA", (r, g, b, a))
