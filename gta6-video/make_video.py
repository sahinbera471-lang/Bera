#!/usr/bin/env python3
"""
GTA 6 – Das musst du wissen (Hochkant-Video 1080x1920, 30 fps).

Baut aus den 10 Voiceover-Clips in ./voiceover ein fertiges MP4:
animierte Grafiken (PIL), Untertitel, synthetische Hintergrundmusik,
Whoosh-Effekte, Ducking und Lautheits-Normalisierung (ffmpeg).

    python3 make_video.py                 # rendert GTA6_Das_musst_du_wissen.mp4
    python3 make_video.py --preview 3,12  # schreibt Vorschau-PNGs (Sekunden)
"""
import functools
import math
import os
import re
import subprocess
import sys
import tempfile
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
VO_DIR = os.path.join(HERE, "voiceover")
OUT = os.path.join(HERE, "GTA6_Das_musst_du_wissen.mp4")

W, H, FPS, SR = 1080, 1920, 30, 44100
HORIZON = 1265
LEAD, TAIL, END_HOLD = 0.25, 0.45, 1.0
SH = 28  # Schatten-Rand der Panels

FONT_DIR = "/usr/share/fonts/opentype/inter/"
FONT_FILES = {"black": "Inter-Black.otf", "xb": "Inter-ExtraBold.otf", "b": "Inter-Bold.otf",
              "sb": "Inter-SemiBold.otf", "m": "Inter-Medium.otf"}

WHITE = (255, 255, 255)
MUTED = (168, 174, 204)
CYAN = (34, 211, 238)
PINK = (255, 61, 139)
ORANGE = (255, 159, 67)
RED = (255, 64, 64)
GREEN = (46, 229, 157)
YELLOW = (255, 214, 64)
DARK = (12, 10, 26)

# Untertitel (Anzeige-Schreibweise des gesprochenen Textes)
CAPTIONS = [
    "GTA 6 erscheint in nur sechs Tagen! Hier ist alles, was du vorher wissen musst – und warum du dich am Release-Tag auf keinen Fall krankmelden solltest.",
    "Release ist am Donnerstag, dem 19. November 2026. Das Spiel wurde zweimal verschoben – jetzt ist es endlich so weit.",
    "Zum Start gibt es GTA 6 nur für PlayStation 5 und Xbox Series X und S. Eine PC-Version ist noch nicht offiziell angekündigt.",
    "Die Standard Edition kostet 79,99 €, die Ultimate Edition 99,99 €. Bei manchen Händlern bekommst du die Disc sogar etwas günstiger.",
    "Die Story spielt im Bundesstaat Leonida, rund um Vice City. Du spielst Lucia und Jason – ein Duo, das immer tiefer in die Kriminalität rutscht.",
    "Mein Tipp: Räum jetzt schon Speicherplatz auf deiner Konsole frei, und check im Store, ob du das Spiel vorab herunterladen kannst. Dann zockst du ab Minute eins.",
    "Und jetzt das Wichtigste: Meld dich nicht krank, nur um GTA zu zocken! Wer eine Krankheit vortäuscht, riskiert die fristlose Kündigung.",
    "Schon der Satz „Wenn ich keinen Urlaub kriege, bin ich halt krank“ kann reichen. Und Zock-Clips in deiner Story können als Beweis gegen dich verwendet werden.",
    "Mach es lieber richtig: Beantrag jetzt Urlaub und sprich früh mit deinem Chef – oder zock ganz entspannt nach Feierabend und am Wochenende.",
    "Also: 19. November – Urlaub statt Krankschein! Folg mir für mehr GTA-6-News, und schreib in die Kommentare, ob du am Release-Tag zockst!",
]
HIGHLIGHT = {"gta", "6", "krankmelden", "krank", "urlaub", "kündigung", "fristlose", "beweis", "leonida",
             "krankschein", "lucia", "jason", "playstation", "xbox", "pc-version", "speicherplatz"}


# ---------------------------------------------------------------- helpers
@functools.lru_cache(None)
def font(weight, size):
    return ImageFont.truetype(FONT_DIR + FONT_FILES[weight], size)


def c4(c, a=255):
    return tuple(c[:3]) + (a,)


def fit(text, weight, max_size, max_w):
    s = max_size
    while s > 12 and font(weight, s).getlength(text) > max_w:
        s -= 2
    return font(weight, s)


def text_img(text, f, fill=WHITE):
    l, t, r, b = f.getbbox(text)
    im = Image.new("RGBA", (r - l + 8, b - t + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - l, 4 - t), text, font=f, fill=c4(fill))
    return im


def grad(size, c1, c2, horizontal=True):
    w, h = size
    if horizontal:
        k = np.linspace(0, 1, w)[None, :, None]
    else:
        k = np.linspace(0, 1, h)[:, None, None]
    arr = np.array(c1, float) * (1 - k) + np.array(c2, float) * k
    arr = np.broadcast_to(arr, (h, w, 3)).astype(np.uint8)
    return Image.fromarray(np.ascontiguousarray(arr), "RGB").convert("RGBA")


def grad_text(text, f, c1, c2):
    m = text_img(text, f)
    g = grad(m.size, c1, c2)
    g.putalpha(m.getchannel("A"))
    return g


def rrect(w, h, r, fill, outline=None, width=0, ss=2):
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=fill,
                                         outline=outline, width=width * ss)
    return im.resize((w, h), Image.LANCZOS)


def panel(w, h, accent=None, fill=(20, 22, 46, 236), r=34, bw=3):
    """Abgerundete Karte mit weichem Schatten. Inhalt bei (SH+x, SH+y) einfügen."""
    im = Image.new("RGBA", (w + 2 * SH, h + 2 * SH), (0, 0, 0, 0))
    sh = Image.new("L", im.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((SH, SH + 12, SH + w, SH + h + 12), r, fill=150)
    im.putalpha(sh.filter(ImageFilter.GaussianBlur(16)))
    card = rrect(w, h, r, fill, outline=c4(accent) if accent else None, width=bw if accent else 0)
    im.alpha_composite(card, (SH, SH))
    return im


def paste(dst, src, x, y):
    x, y = int(round(x)), int(round(y))
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(src.width, dst.width - x), min(src.height, dst.height - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    if (sx0, sy0, sx1, sy1) != (0, 0, src.width, src.height):
        src = src.crop((sx0, sy0, sx1, sy1))
    dst.alpha_composite(src, (x + sx0, y + sy0))


def paste_c(dst, src, cx, y):
    paste(dst, src, cx - src.width / 2, y)


def with_alpha(img, a):
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
    return out


def ss_shape(size, draw_fn, ss=3):
    w, h = size
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), ss)
    return im.resize((w, h), Image.LANCZOS)


def icon(kind, size=96, color=GREEN):
    def fn(d, s):
        S = size * s
        d.ellipse((0, 0, S - 1, S - 1), fill=c4(color))
        lw = int(S * 0.11)
        if kind == "check":
            d.line([(S * .27, S * .53), (S * .44, S * .70), (S * .75, S * .35)], fill=c4(DARK), width=lw, joint="curve")
        elif kind == "x":
            d.line([(S * .32, S * .32), (S * .68, S * .68)], fill=c4(DARK), width=lw)
            d.line([(S * .68, S * .32), (S * .32, S * .68)], fill=c4(DARK), width=lw)
    return ss_shape((size, size), fn)


def warning_triangle(w=260):
    h = int(w * 0.88)

    def fn(d, s):
        d.polygon([(w * s / 2, 0), (w * s - 1, h * s - 1), (0, h * s - 1)], fill=c4(RED))
        iw = w * s * 0.80
        d.polygon([(w * s / 2, h * s * 0.16), (w * s / 2 + iw / 2 * 0.82, h * s * 0.90), (w * s / 2 - iw / 2 * 0.82, h * s * 0.90)],
                  fill=c4(YELLOW))
        bx = w * s / 2
        d.rounded_rectangle((bx - w * s * .045, h * s * .38, bx + w * s * .045, h * s * .70), int(w * s * .04), fill=c4(DARK))
        d.ellipse((bx - w * s * .05, h * s * .74, bx + w * s * .05, h * s * .84), fill=c4(DARK))
    return ss_shape((w, h), fn)


def pill(text, bg, fg=DARK, size=34, weight="xb", padx=28, pady=14):
    ti = text_img(text, font(weight, size), fg)
    w, h = ti.width + 2 * padx, ti.height + 2 * pady
    im = rrect(w, h, h // 2, c4(bg))
    paste(im, ti, padx, pady)
    return im


HALO = 22


def halo(img):
    """Weicher dunkler Schein hinter Text, damit er auch vor der Sonne lesbar bleibt."""
    out = Image.new("RGBA", (img.width + 2 * HALO, img.height + 2 * HALO), (0, 0, 0, 0))
    a = Image.new("L", out.size, 0)
    a.paste(img.getchannel("A"), (HALO, HALO))
    a = a.filter(ImageFilter.GaussianBlur(9)).point(lambda v: min(255, int(v * 2.2)) * 7 // 10)
    out.putalpha(a)
    out.alpha_composite(img, (HALO, HALO))
    return out


def ease_out(p):
    return 1 - (1 - p) ** 3


def back_out(p):
    c1 = 1.70158
    return 1 + (c1 + 1) * (p - 1) ** 3 + c1 * (p - 1) ** 2


# ---------------------------------------------------------------- background
def build_backgrounds():
    y = np.arange(H, dtype=float)
    stops = [(0, (7, 8, 22)), (650, (16, 10, 40)), (1050, (48, 14, 70)), (HORIZON, (120, 26, 96))]
    sky = np.zeros((H, 3))
    for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
        m = (y >= y0) & (y <= y1)
        k = ((y[m] - y0) / (y1 - y0))[:, None]
        sky[m] = np.array(c0) * (1 - k) + np.array(c1) * k
    floor_top, floor_bot = np.array((14, 6, 30)), np.array((6, 4, 14))
    m = y > HORIZON
    k = ((y[m] - HORIZON) / (H - HORIZON))[:, None]
    sky[m] = floor_top * (1 - k) + floor_bot * k
    arr = np.broadcast_to(sky[:, None, :], (H, W, 3)).astype(np.uint8)
    bg = Image.fromarray(np.ascontiguousarray(arr), "RGB").convert("RGBA")

    rng = np.random.default_rng(7)
    stars = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(stars)
    for _ in range(170):
        sx, sy = rng.uniform(0, W), rng.uniform(0, 1050) ** 1.0
        r = rng.choice([1, 1, 1, 2, 2, 3])
        d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(255, 255, 255, int(rng.uniform(40, 170))))
    bg.alpha_composite(stars)

    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((-200, HORIZON - 260, W + 200, HORIZON + 120), fill=140)
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    gl = Image.new("RGBA", (W, H), c4(PINK))
    gl.putalpha(glow)
    bg.alpha_composite(gl)

    R = 330
    sun = grad((2 * R, 2 * R), (255, 200, 90), PINK, horizontal=False)
    mask = Image.new("L", (2 * R * 3, 2 * R * 3), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((0, 0, 6 * R - 1, 6 * R - 1), fill=105)
    for i in range(7):  # Retro-Streifen
        yy = 3 * R * (1.0 + 0.11 * i) - 3 * R * 0.25
        th = 6 + i * 7
        md.rectangle((0, yy, 6 * R, yy + th), fill=0)
    mask = mask.resize((2 * R, 2 * R), Image.LANCZOS)
    sun.putalpha(mask)
    sun = sun.crop((0, 0, 2 * R, R))
    bg.alpha_composite(sun, (W // 2 - R, HORIZON - R))

    # Bodenraster: Fluchtlinien
    lines = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    for i in range(-16, 17):
        ld.line([(W / 2 + i * 14, HORIZON), (W / 2 + i * 190, H)], fill=c4(PINK, 255), width=2)
    ramp = np.zeros((H, W), np.uint8)
    rr = np.clip((np.arange(H) - HORIZON) / (H - HORIZON), 0, 1) ** 0.8 * 120
    ramp[:] = rr[:, None].astype(np.uint8)
    la = np.minimum(np.array(lines.getchannel("A")), ramp)
    lines.putalpha(Image.fromarray(la))
    bg.alpha_composite(lines)
    ImageDraw.Draw(bg).line([(0, HORIZON), (W, HORIZON)], fill=c4((255, 120, 170)), width=3)

    red = bg.copy()
    tint = grad((W, H), (150, 0, 24), (60, 0, 10), horizontal=False)
    tint.putalpha(110)
    red.alpha_composite(tint)
    return bg, red


def draw_floor_lines(frame, t):
    d = ImageDraw.Draw(frame)
    phase = (t * 1.3) % 1.0
    base = np.array((11, 5, 24))
    for k in range(0, 26):
        z = k + 1 - phase
        if z < 0.55:
            continue
        yy = HORIZON + (H - HORIZON) * 0.62 / z
        if yy > H or yy <= HORIZON + 1:
            continue
        a = min(1.0, 0.9 / z) * 0.75
        col = tuple(int(v) for v in base * (1 - a) + np.array(PINK) * a)
        d.line([(0, yy), (W, yy)], fill=c4(col), width=max(1, int(4 / z)))


# ---------------------------------------------------------------- captions
def chunk_text(text):
    chunks, cur = [], []
    for w in text.split():
        if w == "–":
            if cur:
                chunks.append(" ".join(cur))
            cur = [w]
            continue
        cand = " ".join(cur + [w])
        if cur and len(cand) > 24:
            chunks.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
        ordinal = re.fullmatch(r"\d+\.", w) is not None
        if cur and not ordinal and (w[-1] in ".!?" or (w[-1] in ",:“" and len(" ".join(cur)) >= 9)):
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def silences(path, dur):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "silencedetect=n=-40dB:d=0.1", "-f", "null", "-"],
                       capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", r.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr)]
    return list(zip(st, en))


def caption_times(chunks, dur, sil):
    n = len(chunks)
    s0, s1 = 0.05, dur - 0.2
    for a, b in sil:
        if b >= dur - 0.05:
            s1 = a
    wts = [len(c) + 2 + (8 if c[-1] in ".!?" else 4 if c[-1] in ",:" else 0) for c in chunks]
    cum = np.concatenate([[0], np.cumsum(wts)]) / sum(wts)
    prop = s0 + cum * (s1 - s0)
    anchors = {0: s0, n: s1}
    for a, b in sil:
        if b >= dur - 0.05 or a < 0.1:
            continue
        mid = (a + b) / 2
        cands = [k for k in range(1, n) if k not in anchors and
                 (chunks[k - 1][-1] in ".!?,:“" or chunks[k].startswith("–"))]
        if not cands:
            continue
        k = min(cands, key=lambda k: abs(prop[k] - mid))
        if abs(prop[k] - mid) < 1.2:
            anchors[k] = b
    ks = sorted(anchors)
    times = np.zeros(n + 1)
    for ka, kb in zip(ks, ks[1:]):
        ta, tb = anchors[ka], max(anchors[kb], anchors[ka] + 0.15 * (kb - ka))
        seg = cum[ka:kb + 1]
        frac = (seg - seg[0]) / max(1e-9, seg[-1] - seg[0])
        times[ka:kb + 1] = ta + frac * (tb - ta)
    return times[:n]


@functools.lru_cache(None)
def caption_img(text):
    size = 62
    while True:
        f = font("xb", size)
        words = text.split()
        sp = f.getlength(" ")
        widths = [f.getlength(w) for w in words]
        tw = sum(widths) + sp * (len(words) - 1)
        if tw <= 900 or size <= 40:
            break
        size -= 2
    asc, desc = f.getmetrics()
    padx, pady = 30, 16
    im = rrect(int(tw) + 2 * padx, asc + desc + 2 * pady, 26, (0, 0, 0, 170))
    d = ImageDraw.Draw(im)
    x = padx
    for w, ww in zip(words, widths):
        key = re.sub(r"[^\wäöüß\-]", "", w.lower())
        col = YELLOW if (key in HIGHLIGHT or re.search(r"\d|€", w)) else WHITE
        d.text((x, pady), w, font=f, fill=c4(col), stroke_width=2, stroke_fill=(0, 0, 0, 255))
        x += ww + sp
    return im


# ---------------------------------------------------------------- scenes
class Scene:
    def __init__(self, idx, dur, tag=None, tag_color=CYAN, red_bg=False):
        self.idx, self.dur, self.items, self.dyn, self.red_bg = idx, dur, [], [], red_bg
        if tag:
            self.add(pill(tag, tag_color), W / 2, 228, 0.0, "down")

    def add(self, img, x, y, t=0.0, anim="up", center=True, glow=True):
        if center:
            x = x - img.width / 2
        if glow:
            img, x, y = halo(img), x - HALO, y - HALO
        self.items.append(dict(img=img, x=int(x), y=int(y), t=t, anim=anim))
        return self.items[-1]

    def add_panel(self, img, cx, top, t=0.0, anim="up"):
        """top = Oberkante der eigentlichen Karte (ohne Schatten-Rand)."""
        return self.add(img, cx, top - SH, t, anim, glow=False)

    def render(self, frame, st):
        for it in self.items:
            lt = st - it["t"]
            if lt < 0:
                continue
            p = min(1.0, lt / 0.45)
            img, x, y, a = it["img"], it["x"], it["y"], 1.0
            if p < 1:
                e = ease_out(p)
                an = it["anim"]
                if an == "up":
                    y += (1 - e) * 80
                    a = e
                elif an == "down":
                    y -= (1 - e) * 60
                    a = e
                elif an == "left":
                    x -= (1 - e) * 160
                    a = e
                elif an == "right":
                    x += (1 - e) * 160
                    a = e
                elif an == "fade":
                    a = e
                elif an == "pop":
                    sc = 0.35 + 0.65 * back_out(p)
                    nw, nh = max(1, int(img.width * sc)), max(1, int(img.height * sc))
                    cx, cy = x + img.width / 2, y + img.height / 2
                    img = img.resize((nw, nh), Image.BILINEAR)
                    x, y, a = cx - nw / 2, cy - nh / 2, min(1.0, p * 3)
            if a < 0.999:
                img = with_alpha(img, max(0.0, a))
            paste(frame, img, x, y)
        for fn in self.dyn:
            fn(frame, st)


def T(x):
    return x + LEAD


def scene_hook(s):
    s.add(grad_text("GTA 6", font("black", 250), (255, 205, 95), PINK), W / 2, 300, 0.0, "pop")
    s.add(text_img("ERSCHEINT IN", font("xb", 64)), W / 2, 560, 0.45)
    R, cy = 200, 830
    ring = ss_shape((2 * R + 40, 2 * R + 40), lambda d, k: d.ellipse((20 * k, 20 * k, (2 * R + 20) * k, (2 * R + 20) * k),
                                                                    outline=c4(CYAN), width=22 * k))
    track = ss_shape((2 * R + 40, 2 * R + 40), lambda d, k: d.ellipse((20 * k, 20 * k, (2 * R + 20) * k, (2 * R + 20) * k),
                                                                     fill=(16, 13, 36, 235), outline=(70, 66, 100, 255),
                                                                     width=22 * k))
    s.add(track, W / 2, cy - R - 20, 0.6, "fade")

    def ring_fn(frame, st, ring=ring):
        p = (st - 0.7) / 1.1
        if p <= 0:
            return
        ang = 360 * ease_out(min(1.0, p))
        m = Image.new("L", ring.size, 0)
        ImageDraw.Draw(m).pieslice((-50, -50, ring.width + 50, ring.height + 50), -90, -90 + ang, fill=255)
        r2 = ring.copy()
        r2.putalpha(Image.fromarray(np.minimum(np.array(ring.getchannel("A")), np.array(m))))
        paste(frame, r2, W / 2 - ring.width / 2, cy - ring.height / 2)
    s.dyn.append(ring_fn)
    six = text_img("6", font("black", 280))
    s.add(six, W / 2, cy - 150, 0.85, "pop")
    s.add(text_img("TAGEN", font("xb", 54), CYAN), W / 2, cy + 105, 1.1, "fade")
    p = panel(900, 160, PINK)
    paste_c(p, text_img("Alles, was du wissen musst", font("b", 48)), SH + 450, SH + 26)
    paste_c(p, text_img("+ warum du NICHT krankfeiern solltest", font("b", 40), RED), SH + 450, SH + 96)
    s.add_panel(p, W / 2, 1085, T(2.6))


def scene_release(s):
    p = panel(560, 540, CYAN)
    band = rrect(560, 130, 34, c4(CYAN))
    ImageDraw.Draw(band).rectangle((0, 60, 559, 129), fill=c4(CYAN))
    paste(p, band, SH, SH)
    paste_c(p, text_img("NOVEMBER 2026", font("xb", 50), DARK), SH + 280, SH + 38)
    paste_c(p, text_img("19", font("black", 290)), SH + 280, SH + 170)
    paste_c(p, text_img("DONNERSTAG", font("xb", 50), CYAN), SH + 280, SH + 450)
    s.add_panel(p, W / 2, 320, 0.15, "pop")
    rows = [("Herbst 2025", False, T(4.3)), ("26. Mai 2026", False, T(4.75)), ("19. November 2026", True, T(5.9))]
    for i, (txt, final, t) in enumerate(rows):
        p = panel(860, 96, GREEN if final else None, fill=(20, 22, 46, 236) if final else (20, 22, 46, 200))
        ti = text_img(txt, font("xb", 44), WHITE if final else MUTED)
        if not final:
            ImageDraw.Draw(ti).line([(0, ti.height / 2 + 2), (ti.width, ti.height / 2 + 2)], fill=c4(RED), width=5)
        paste(p, ti, SH + 34, SH + 48 - ti.height / 2)
        lab = pill("OFFIZIELL" if final else "VERSCHOBEN", GREEN if final else (120, 24, 40),
                   DARK if final else (255, 160, 160), size=28)
        paste(p, lab, SH + 860 - 24 - lab.width, SH + 48 - lab.height / 2)
        s.add_panel(p, W / 2, 900 + i * 118, t, "left")


def scene_platforms(s):
    rows = [("PlayStation 5", "Zum Release verfügbar", "check", T(1.5)),
            ("Xbox Series X|S", "Zum Release verfügbar", "check", T(3.0)),
            ("PC", "Noch nicht offiziell angekündigt", "x", T(5.45))]
    for i, (title, sub, kind, t) in enumerate(rows):
        ok = kind == "check"
        p = panel(900, 170, GREEN if ok else RED)
        paste(p, icon(kind, 100, GREEN if ok else RED), SH + 36, SH + 35)
        paste(p, text_img(title, font("xb", 60), WHITE if ok else MUTED), SH + 170, SH + 30)
        paste(p, text_img(sub, font("m", 34), MUTED if ok else (255, 150, 150)), SH + 172, SH + 108)
        s.add_panel(p, W / 2, 330 + i * 200, t, "left" if i % 2 == 0 else "right")
    p = panel(900, 110, ORANGE)
    paste_c(p, text_img("Keine Version für PS4 & Xbox One", font("b", 42)), SH + 450, SH + 32)
    s.add_panel(p, W / 2, 970, T(6.8))


def scene_price(s):
    for i, (name, price, t, c1, c2) in enumerate([("STANDARD", "79,99 €", T(0.4), WHITE, WHITE),
                                                  ("ULTIMATE", "99,99 €", T(3.3), (255, 205, 95), PINK)]):
        p = panel(450, 480, ORANGE if i else (90, 96, 140))
        paste_c(p, text_img(name, font("xb", 48), ORANGE if i else MUTED), SH + 225, SH + 50)
        paste_c(p, text_img("EDITION", font("sb", 32), MUTED), SH + 225, SH + 112)
        f = fit(price, "black", 104, 400)
        paste_c(p, grad_text(price, f, c1, c2), SH + 225, SH + 215)
        paste_c(p, text_img("PS5 · Xbox Series X|S", font("m", 28), MUTED), SH + 225, SH + 400)
        s.add(p, 55 + 225 + (520 * i), 335 - SH, t, "pop")
    p = panel(900, 210, GREEN)
    lab = pill("SPAR-TIPP", GREEN, size=30)
    paste_c(p, lab, SH + 450, SH + 22)
    paste_c(p, text_img("Disc bei manchen Händlern", font("b", 46)), SH + 450, SH + 92)
    paste_c(p, text_img("etwas günstiger!", font("xb", 46), GREEN), SH + 450, SH + 148)
    s.add_panel(p, W / 2, 890, T(7.0))
    s.add(text_img("Stand: 13.11.2026 · Preise je nach Händler", font("m", 28), MUTED), W / 2, 1135, T(7.4), "fade")


def scene_story(s):
    s.add(text_img("SCHAUPLATZ", font("sb", 38), MUTED), W / 2, 335, T(0.2), "fade")
    s.add(grad_text("LEONIDA", fit("LEONIDA", "black", 200, 920), (255, 205, 95), PINK), W / 2, 390, T(1.2), "pop")
    s.add(text_img("Bundesstaat · rund um Vice City", font("b", 48)), W / 2, 610, T(2.5))
    s.add(text_img("DU SPIELST", font("sb", 38), MUTED), W / 2, 730, T(3.9), "fade")
    for i, (name, col, t) in enumerate([("LUCIA", PINK, T(4.3)), ("JASON", CYAN, T(5.0))]):
        p = panel(380, 170, col)
        paste_c(p, text_img(name, font("black", 80), col), SH + 190, SH + 45)
        s.add_panel(p, 70 + 190 + i * 560, 795, t, "left" if i == 0 else "right")
    s.add(text_img("&", font("black", 96), ORANGE), W / 2, 830, T(4.65), "pop")
    s.add(text_img("Ein Duo auf der schiefen Bahn", font("b", 50)), W / 2, 1035, T(5.8))


def scene_tips(s):
    s.add(text_img("Bereit machen!", font("xb", 84)), W / 2, 330, T(0.0), "pop")
    p = panel(900, 270, GREEN)
    paste(p, text_img("KONSOLENSPEICHER", font("sb", 34), MUTED), SH + 50, SH + 36)
    paste(p, rrect(800, 64, 32, c4((50, 52, 84))), SH + 50, SH + 100)
    px, py = W / 2 - 450, 470
    s.add_panel(p, W / 2, py, T(0.1))

    def bar(frame, st):
        if st < T(0.1) + 0.45:
            return
        k = ease_out(min(1.0, max(0.0, (st - T(1.2)) / 2.4)))
        used = 0.93 - 0.63 * k
        col = tuple(int(a * (1 - k) + b * k) for a, b in zip(RED, GREEN))
        bw = int(800 * used)
        paste(frame, rrect(bw, 64, 32, c4(col)), px + 50, py + 100)
        d = ImageDraw.Draw(frame)
        d.text((px + 50, py + 190), f"{round(used * 100)} % belegt", font=font("b", 42), fill=c4(col))
        d.text((px + 850, py + 190), "frei machen!" if k < 0.99 else "bereit ✓", font=font("b", 42),
               fill=c4(WHITE), anchor="ra")
    s.dyn.append(bar)
    for i, (txt, t) in enumerate([("Speicherplatz freiräumen", T(1.2)), ("Pre-Load im Store checken", T(3.6))]):
        p = panel(900, 120, None)
        paste(p, icon("check", 76), SH + 30, SH + 22)
        paste(p, text_img(txt, font("b", 48)), SH + 130, SH + 34)
        s.add_panel(p, W / 2, 800 + i * 150, t, "left")
    s.add(text_img("Zocken ab Minute 1!", font("xb", 66), GREEN), W / 2, 1110, T(6.6), "pop")


def scene_warning(s):
    s.add(warning_triangle(250), W / 2, 270, 0.0, "pop")
    s.add(text_img("ACHTUNG!", fit("ACHTUNG!", "black", 170, 900), RED), W / 2, 530, T(0.1), "pop")
    s.add(text_img("NICHT KRANKFEIERN!", fit("NICHT KRANKFEIERN!", "xb", 92, 920)), W / 2, 730, T(1.7), "pop")
    p = panel(920, 250, RED)
    paste_c(p, text_img("Krankheit vortäuschen", font("b", 52)), SH + 460, SH + 34)
    paste_c(p, text_img("= fristlose Kündigung möglich", font("xb", 52), RED), SH + 460, SH + 108)
    paste_c(p, text_img("§ 626 BGB · wichtiger Grund", font("m", 32), MUTED), SH + 460, SH + 186)
    s.add_panel(p, W / 2, 900, T(4.6))
    s.add(text_img("Keine Rechtsberatung", font("m", 28), MUTED), W / 2, 1185, T(5.0), "fade")

    def border(frame, st):
        if st < 2.2 and (st * 4) % 1 > 0.5:
            return
        ImageDraw.Draw(frame).rectangle((10, 10, W - 11, H - 11), outline=c4(RED), width=16)
    s.dyn.append(border)


def scene_law(s):
    s.add(text_img("SCHON DIESER SATZ KANN REICHEN:", font("sb", 36), RED), W / 2, 330, T(0.0), "fade")
    lines = ["„Wenn ich keinen Urlaub", "kriege, bin ich halt krank.“"]
    bw, bh = 860, 70 + 70 * len(lines)
    bub = Image.new("RGBA", (bw + 2 * SH, bh + 2 * SH + 40), (0, 0, 0, 0))
    bub.alpha_composite(panel(bw, bh, None, fill=(46, 50, 84, 245)))
    tail = ss_shape((70, 50), lambda d, k: d.polygon([(0, 0), (70 * k, 0), (8 * k, 50 * k)], fill=(46, 50, 84, 245)))
    paste(bub, tail, SH + 90, SH + bh - 2)
    for i, ln in enumerate(lines):
        paste(bub, text_img(ln, font("b", 54)), SH + 44, SH + 38 + i * 72)
    s.add(bub, W / 2, 390 - SH, T(0.8), "up")
    stamp_txt = text_img("KÜNDIGUNGSGEFAHR", font("black", 56), RED)
    st_im = Image.new("RGBA", (stamp_txt.width + 60, stamp_txt.height + 40), (0, 0, 0, 0))
    st_im.alpha_composite(rrect(st_im.width, st_im.height, 16, (30, 6, 14, 200), outline=c4(RED), width=6))
    paste(st_im, stamp_txt, 30, 20)
    st_im = st_im.rotate(8, resample=Image.BICUBIC, expand=True)
    s.add(st_im, W / 2 + 60, 600, T(3.2), "pop")
    p = panel(900, 230, RED)
    d = ImageDraw.Draw(p)
    rec = ss_shape((34, 34), lambda dd, k: dd.ellipse((0, 0, 34 * k - 1, 34 * k - 1), fill=c4(RED)))
    paste(p, rec, SH + 40, SH + 34)
    d.text((SH + 86, SH + 30), "REC", font=font("xb", 34), fill=c4(RED))
    paste(p, text_img("Zock-Clips in deiner Story", font("b", 50)), SH + 40, SH + 92)
    paste(p, text_img("= Beweis gegen dich!", font("xb", 52), RED), SH + 40, SH + 156)
    s.add_panel(p, W / 2, 830, T(4.45))
    s.add(text_img("Keine Rechtsberatung", font("m", 28), MUTED), W / 2, 1100, T(5.0), "fade")


def scene_solution(s):
    s.add(text_img("Besser so:", font("xb", 84)), W / 2, 330, T(0.1), "pop")
    rows = [("Urlaub beantragen", "Am besten noch heute", T(1.4)),
            ("Früh mit dem Chef reden", "Offen und rechtzeitig", T(2.9)),
            ("Nach Feierabend zocken", "oder entspannt am Wochenende", T(4.55))]
    for i, (a, b, t) in enumerate(rows):
        p = panel(900, 150, GREEN)
        paste(p, icon("check", 92), SH + 30, SH + 29)
        paste(p, text_img(a, font("b", 50)), SH + 150, SH + 30)
        paste(p, text_img(b, font("m", 34), MUTED), SH + 152, SH + 96)
        s.add_panel(p, W / 2, 470 + i * 180, t, "left")
    s.add(text_img("Job behalten & trotzdem zocken!", fit("Job behalten & trotzdem zocken!", "xb", 58, 920), GREEN),
          W / 2, 1050, T(6.5), "pop")


def scene_outro(s):
    s.add(grad_text("19.11.", fit("19.11.", "black", 250, 900), (255, 205, 95), PINK), W / 2, 270, 0.0, "pop")
    s.add(text_img("URLAUB", font("black", 120), GREEN), W / 2, 560, T(2.0), "pop")
    s.add(text_img("STATT KRANKSCHEIN", font("xb", 66)), W / 2, 715, T(2.5))
    s.add(pill("FOLG MIR FÜR MEHR GTA-6-NEWS", PINK, DARK, size=42, padx=40, pady=24), W / 2, 850, T(3.2), "pop")
    s.add(text_img("Zockst du am Release-Tag?", font("xb", 56)), W / 2, 1010, T(5.3))
    s.add(text_img("Schreib's in die Kommentare!", font("sb", 42), MUTED), W / 2, 1090, T(5.8))
    s.add(text_img("Inoffizielles Fan-Video · nicht mit Rockstar Games verbunden", font("m", 25), MUTED), W / 2, 1180, 0.6, "fade")
    s.add(text_img("Keine Rechtsberatung · Stand: 13.11.2026", font("m", 25), MUTED), W / 2, 1215, 0.6, "fade")


SCENES = [
    (scene_hook, None, CYAN, False),
    (scene_release, "#1 RELEASE-DATUM", CYAN, False),
    (scene_platforms, "#2 PLATTFORMEN", CYAN, False),
    (scene_price, "#3 PREIS", ORANGE, False),
    (scene_story, "#4 STORY & MAP", PINK, False),
    (scene_tips, "#5 PROFI-TIPP", GREEN, False),
    (scene_warning, None, RED, True),
    (scene_law, "#7 ARBEITSRECHT", RED, True),
    (scene_solution, "#8 SO GEHT'S RICHTIG", GREEN, False),
    (scene_outro, None, PINK, False),
]


# ---------------------------------------------------------------- timeline
def load_voice(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def build_timeline():
    clips, scenes, t0 = [], [], 0.0
    for i in range(10):
        path = os.path.join(VO_DIR, f"s{i + 1:02d}.mp3")
        v = load_voice(path)
        dur = len(v) / SR
        sdur = LEAD + dur + TAIL + (END_HOLD if i == 9 else 0)
        chunks = chunk_text(CAPTIONS[i])
        times = caption_times(chunks, dur, silences(path, dur))
        clips.append(dict(voice=v, start=t0, dur=dur, sdur=sdur, chunks=chunks, ctimes=times + LEAD))
        t0 += sdur
    return clips, t0


_STATE = {}


def init_worker():
    clips, total = build_timeline()
    bg, red = build_backgrounds()
    scenes = []
    for i, (fn, tag, col, red_bg) in enumerate(SCENES):
        s = Scene(i, clips[i]["sdur"], tag, col, red_bg)
        fn(s)
        scenes.append(s)
    header = text_img("GTA 6 · DAS MUSST DU WISSEN", font("sb", 28), MUTED)
    _STATE.update(clips=clips, total=total, bg=bg, red=red, scenes=scenes, header=header)


def render_frame(t):
    S = _STATE
    clips = S["clips"]
    i = 0
    while i < 9 and t >= clips[i + 1]["start"]:
        i += 1
    c, sc = clips[i], S["scenes"][i]
    st = t - c["start"]
    if sc.red_bg:
        k = 0.55 + 0.45 * math.sin(st * 2 * math.pi * 1.2)
        frame = Image.blend(S["bg"], S["red"], k)
    else:
        frame = S["bg"].copy()
    draw_floor_lines(frame, t)
    sc.render(frame, st)

    # Untertitel
    ct = c["ctimes"]
    j = int(np.searchsorted(ct, st, side="right")) - 1
    if j >= 0:
        cap = caption_img(c["chunks"][j])
        lt = st - ct[j]
        if lt < 0.08:
            cap = with_alpha(cap, lt / 0.08)
        paste_c(frame, cap, W / 2, 1395)

    # Fortschritt (Story-Style)
    d = ImageDraw.Draw(frame)
    seg_w = (W - 120 - 9 * 8) / 10
    for k in range(10):
        x0 = 60 + k * (seg_w + 8)
        d.rounded_rectangle((x0, 52, x0 + seg_w, 60), 4, fill=(255, 255, 255, 255) if k < i else (70, 70, 96, 255))
        if k == i:
            f = min(1.0, st / c["sdur"])
            if f * seg_w > 8:
                d.rounded_rectangle((x0, 52, x0 + f * seg_w, 60), 4, fill=(255, 255, 255, 255))
    paste(frame, S["header"], 56, 78)

    # kurzer Blitz beim Szenenwechsel
    if i > 0 and st < 0.12:
        frame = Image.blend(frame, Image.new("RGBA", (W, H), (255, 255, 255, 255)), 0.22 * (1 - st / 0.12))
    return frame.convert("RGB")


def render_segment(args):
    f0, f1, path = args
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                          "-pix_fmt", "yuv420p", "-profile:v", "high", path], stdin=subprocess.PIPE)
    for n in range(f0, f1):
        p.stdin.write(render_frame(n / FPS).tobytes())
    p.stdin.close()
    p.wait()
    return path


# ---------------------------------------------------------------- audio
def lowpass(x, fc, order=4):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / np.sqrt(1 + (f / fc) ** order)
    return np.fft.irfft(X, len(x))


def highpass(x, fc, order=4):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / np.sqrt(1 + (fc / np.maximum(f, 1e-3)) ** order)
    return np.fft.irfft(X, len(x))


def add_at(out, x, i):
    i = int(i)
    if i >= len(out) or i + len(x) <= 0:
        return
    if i < 0:
        x, i = x[-i:], 0
    n = min(len(x), len(out) - i)
    out[i:i + n] += x[:n]


def movavg(x, n):
    c = np.cumsum(np.concatenate([[0], x]))
    y = (c[n:] - c[:-n]) / n
    return np.concatenate([np.full(n // 2, y[0]), y, np.full(len(x) - len(y) - n // 2, y[-1])])


def build_audio(clips, total, path, booms=(0, 6)):
    n = int(total * SR) + SR
    rng = np.random.default_rng(3)
    bpm = 104
    beat = 60 / bpm
    # Drums
    drums = np.zeros(n)
    kt = np.arange(int(0.4 * SR)) / SR
    kick = np.sin(2 * np.pi * np.cumsum(45 + 90 * np.exp(-kt * 30)) / SR) * np.exp(-kt * 8)
    stt = np.arange(int(0.22 * SR)) / SR
    snare = highpass(rng.standard_normal(len(stt)), 1200) * np.exp(-stt * 20) * 0.6 + \
        np.sin(2 * np.pi * 190 * stt) * np.exp(-stt * 30) * 0.4
    ht = np.arange(int(0.06 * SR)) / SR
    hat = highpass(rng.standard_normal(len(ht)), 7000) * np.exp(-ht * 70)
    for b in range(int(total / beat) + 2):
        i = b * beat * SR
        add_at(drums, kick, i)
        if b % 4 in (1, 3):
            add_at(drums, snare * 0.45, i)
        add_at(drums, hat * 0.18, i + beat * SR / 2)
    # Bass + Pad (Am – F – C – G)
    chords = [(110.0, [220.0, 261.63, 329.63]), (87.31, [174.61, 220.0, 261.63]),
              (130.81, [196.0, 261.63, 329.63]), (98.0, [196.0, 246.94, 293.66])]
    bass, pad = np.zeros(n), np.zeros(n)
    bar_len = 4 * beat
    e8 = beat / 2
    for b in range(int(total / bar_len) + 2):
        root, notes = chords[b % 4]
        for k in range(8):
            f = root * (2 if k % 2 else 1)
            L = int(e8 * SR)
            tt = np.arange(L) / SR
            note = (2 * ((tt * f) % 1) - 1) * np.exp(-tt * 6)
            add_at(bass, note, (b * bar_len + k * e8) * SR)
        L = int(bar_len * SR)
        tt = np.arange(L) / SR
        env = np.minimum(1, tt / 0.35) * np.minimum(1, (bar_len - tt) / 0.3)
        chord = sum((2 * ((tt * f * dt) % 1) - 1) for f in notes for dt in (0.997, 1.003))
        add_at(pad, chord * env, b * bar_len * SR)
    bass = lowpass(bass, 380)
    pad = lowpass(pad, 1400)
    music = drums * 0.6 + bass / np.abs(bass).max() * 0.38 + pad / np.abs(pad).max() * 0.22
    music = music / np.abs(music).max() * 0.30
    tt = np.arange(n) / SR
    music *= np.minimum(1, tt / 0.4) * np.clip((total - tt) / 1.5, 0, 1)

    voice = np.zeros(n)
    for c in clips:
        add_at(voice, c["voice"], (c["start"] + LEAD) * SR)
    voice = voice / np.abs(voice).max() * 0.9

    env = movavg(np.abs(voice), int(0.03 * SR))
    gain = 1 - 0.6 * np.clip(env / 0.04, 0, 1)
    gain = movavg(gain, int(0.15 * SR))
    music *= gain

    sfx = np.zeros(n)
    wl = int(0.6 * SR)
    wt = np.arange(wl) / SR
    whoosh = highpass(lowpass(rng.standard_normal(wl), 3000), 300)
    whoosh *= np.where(wt < 0.45, (wt / 0.45) ** 2, np.exp(-(wt - 0.45) * 25))
    whoosh = whoosh / np.abs(whoosh).max() * 0.22
    bt = np.arange(int(0.9 * SR)) / SR
    boom = np.sin(2 * np.pi * np.cumsum(38 + 40 * np.exp(-bt * 10)) / SR) * np.exp(-bt * 4) * 0.55
    for k, c in enumerate(clips):
        if k > 0:
            add_at(sfx, whoosh, (c["start"] - 0.45) * SR)
        if k in booms:
            add_at(sfx, boom, c["start"] * SR)

    mix = voice + music + sfx
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)
    mix = (mix / np.abs(mix).max() * 0.95).astype(np.float32)
    stereo = np.repeat(mix[:, None], 2, axis=1)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s16le", path], input=stereo.tobytes(), check=True)


# ---------------------------------------------------------------- main
def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--preview":
        init_worker()
        outdir = os.path.join(HERE, "preview")
        os.makedirs(outdir, exist_ok=True)
        for tok in sys.argv[2].split(","):
            t = float(tok)
            render_frame(t).save(os.path.join(outdir, f"t{t:06.2f}.png"))
        print("total", _STATE["total"])
        return
    init_worker()
    clips, total = _STATE["clips"], _STATE["total"]
    nframes = int(math.ceil(total * FPS))
    print(f"Dauer {total:.2f}s, {nframes} Frames")
    tmp = tempfile.mkdtemp(prefix="gta6_")
    wav = os.path.join(tmp, "mix.wav")
    build_audio(clips, total, wav)
    workers = max(1, os.cpu_count() or 1)
    bounds = np.linspace(0, nframes, workers + 1).astype(int)
    jobs = [(int(a), int(b), os.path.join(tmp, f"seg{k}.mp4")) for k, (a, b) in enumerate(zip(bounds, bounds[1:]))]
    with Pool(workers, initializer=init_worker) as pool:
        parts = pool.map(render_segment, jobs)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{p}'\n" for p in parts)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100", "-c:a", "aac", "-b:a", "192k",
                    "-t", f"{total:.3f}", "-movflags", "+faststart", OUT], check=True)
    print("fertig:", OUT)


if __name__ == "__main__":
    main()
