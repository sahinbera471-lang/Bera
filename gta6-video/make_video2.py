#!/usr/bin/env python3
"""
GTA 6 – Map, Story & Figuren (Hochkant-Video 1080x1920, 30 fps, < 90 s).

Nutzt die Bausteine aus make_video.py und die Clips in ./voiceover2.

Logo: Liegt eine Datei assets/logo.png (am besten mit transparentem Hintergrund)
im Ordner, wird sie an allen Logo-Stellen eingeblendet. Ohne Datei erscheint ein
eigener „GTA 6“-Schriftzug als Platzhalter.

    python3 make_video2.py                 # rendert GTA6_Map_Story_Figuren.mp4
    python3 make_video2.py --preview 3,12  # Vorschau-PNGs (Sekunden)
"""
import math
import os
import subprocess
import sys
import tempfile
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import make_video as mv
from make_video import (CYAN, DARK, FPS, GREEN, H, MUTED, ORANGE, PINK, RED, SH, SR, W, WHITE, YELLOW, Scene,
                        back_out, build_backgrounds, c4, caption_img, caption_times, chunk_text, draw_floor_lines,
                        ease_out, fit, font, grad, grad_text, load_voice, panel, paste, paste_c, pill, rrect,
                        silences, ss_shape, text_img, with_alpha)

HERE = os.path.dirname(os.path.abspath(__file__))
VO_DIR = os.path.join(HERE, "voiceover2")
LOGO = os.path.join(HERE, "assets", "logo.png")
OUT = os.path.join(HERE, "GTA6_Map_Story_Figuren.mp4")

MAP_FILES = [os.path.join(HERE, "assets", n) for n in ("map.png", "map.jpg", "map.jpeg", "map.webp")]
RM_X, RM_Y, RM_W, RM_H, RM_ZOOM = 40, 285, 1000, 700, 1.12
_REAL = {}  # wird in init_worker gefüllt, wenn assets/map.* vorliegt

LEAD, TAIL, END_HOLD = 0.2, 0.35, 0.8
mv.LEAD = LEAD  # build_audio platziert die Stimme mit diesem Vorlauf
VIOLET = (165, 125, 255)
LIME = (150, 220, 90)

CAPTIONS = [
    "Alles, was du über GTA 6 wissen musst: die Map, die Story und die Figuren – in unter 90 Sekunden!",
    "GTA 6 spielt im Bundesstaat Leonida, einer Version von Florida. Laut Preview-Berichten ist die Map etwa doppelt so groß wie in GTA 5.",
    "Leonida hat sechs Regionen: Vice City mit Neon und Stränden, die Inselkette Leonida Keys und die Sümpfe von Grassrivers – mit Alligatoren.",
    "Dazu die Hafenstadt Port Gellhorn, die Zuckerstadt Ambrosia und im Norden der Mount-Kalaga-Nationalpark mit Wäldern und Bergen.",
    "Und jetzt: die Story!",
    "Du spielst Lucia und Jason, ein Verbrecher-Paar à la Bonnie und Clyde. Als ein sicherer Coup schiefgeht, landen sie mitten in einer Verschwörung quer durch Leonida.",
    "Lucia hat von ihrem Vater das Kämpfen gelernt. Für ihre Familie kam sie ins Gefängnis – ab jetzt will sie nur noch kluge Züge machen.",
    "Jason wuchs unter Gaunern auf, war bei der Army und arbeitet jetzt in den Keys für Drogenschmuggler. Dabei will er eigentlich nur ein einfaches Leben.",
    "Unterwegs treffen sie Figuren wie Cal, Boobie Ike und Raul Bautista. Und Vice City ist zurück – voller Social-Media-Chaos, wie in den Trailern.",
    "GTA 6 erscheint am 19. November für PS5 und Xbox Series. Folg mir für mehr – und schreib, auf welche Region du dich am meisten freust!",
]
mv.HIGHLIGHT = {"gta", "6", "map", "story", "figuren", "leonida", "florida", "vice", "city", "keys", "grassrivers",
                "gellhorn", "ambrosia", "mount-kalaga-nationalpark", "lucia", "jason", "bonnie", "clyde", "coup",
                "verschwörung", "gefängnis", "army", "drogenschmuggler", "cal", "boobie", "ike", "raul", "bautista",
                "social-media-chaos", "ps5", "xbox", "alligatoren", "region"}

# ---------------------------------------------------------------- Karte (schematisch)
LON0, LAT0, SX, SY = -87.8, 31.2, 120.0, 137.0
MX0, MY0, PADM = 70, 300, 40
MAP_W, MAP_H = int(7.8 * SX), int(6.8 * SY)

COAST = [(-87.6, 31.0), (-85.0, 31.0), (-84.9, 30.7), (-82.2, 30.57), (-81.45, 30.7), (-81.3, 29.9), (-81.0, 29.2),
         (-80.55, 28.45), (-80.4, 27.6), (-80.05, 26.9), (-80.1, 26.1), (-80.15, 25.75), (-80.35, 25.3),
         (-80.6, 25.2), (-80.9, 25.15), (-81.2, 25.35), (-81.7, 25.9), (-81.9, 26.5), (-82.3, 26.9), (-82.65, 27.5),
         (-82.8, 28.0), (-82.7, 28.7), (-83.0, 29.1), (-83.6, 29.9), (-84.0, 30.1), (-84.4, 29.9), (-85.0, 29.7),
         (-85.35, 29.68), (-85.7, 30.15), (-86.5, 30.4), (-87.2, 30.3), (-87.5, 30.3)]

REGIONS = [  # (Name, Kurzinfo, Farbe, lon, lat, Stichwort im Untertitel)
    ("Vice City", "Neon, Strände, Nachtleben", PINK, -80.25, 25.8, "vice"),
    ("Leonida Keys", "Inselkette im Süden", CYAN, -81.0, 24.75, "keys"),
    ("Grassrivers", "Sümpfe & Alligatoren", GREEN, -81.2, 25.95, "grassrivers"),
    ("Port Gellhorn", "Hafenstadt an der Küste", ORANGE, -85.2, 29.9, "gellhorn"),
    ("Ambrosia", "Zuckerraffinerie im Inland", YELLOW, -81.3, 27.2, "ambrosia"),
    ("Mount Kalaga", "Wälder & Berge im Norden", VIOLET, -83.2, 30.4, "kalaga"),
]


def proj(lon, lat, pad=PADM):
    return pad + (lon - LON0) * SX, pad + (LAT0 - lat) * SY


def to_frame(lon, lat):
    x, y = proj(lon, lat, 0)
    return MX0 + x, MY0 + y


def build_map():
    ss = 2
    size = (MAP_W + 2 * PADM, MAP_H + 2 * PADM)
    big = (size[0] * ss, size[1] * ss)

    def P(lon, lat):
        x, y = proj(lon, lat)
        return x * ss, y * ss

    mask = Image.new("L", big, 0)
    md = ImageDraw.Draw(mask)
    md.polygon([P(*p) for p in COAST], fill=255)
    keys = []
    for i in range(15):  # Inselkette
        u = i / 14
        lon = -80.42 - 1.38 * u
        lat = 25.17 - 0.95 * u + 0.33 * u * u
        r = (7 - 3 * u) * ss
        x, y = P(lon, lat)
        keys.append((x, y, r))
        md.ellipse((x - r * 1.5, y - r, x + r * 1.5, y + r), fill=255)
    lx, ly = P(-80.8, 26.95)
    lake = (lx - 26 * ss, ly - 28 * ss, lx + 26 * ss, ly + 28 * ss)
    md.ellipse(lake, fill=0)
    mask = mask.resize(size, Image.LANCZOS)

    land = grad(size, (24, 46, 74), (14, 28, 50), horizontal=False)
    land.putalpha(mask.point(lambda v: v * 245 // 255))

    tint = Image.new("RGBA", size, (0, 0, 0, 0))
    td = ImageDraw.Draw(tint)
    for name, _, col, lon, lat, _ in REGIONS:
        x, y = proj(lon, lat)
        r = 120 if name != "Leonida Keys" else 80
        td.ellipse((x - r, y - r, x + r, y + r), fill=c4(col, 120))
    tint = tint.filter(ImageFilter.GaussianBlur(45))
    ta = np.minimum(np.array(tint.getchannel("A")), np.array(mask)).astype(np.uint8)
    tint.putalpha(Image.fromarray(ta))
    land.alpha_composite(tint)

    grid = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for gx in range(0, size[0], 46):
        gd.line([(gx, 0), (gx, size[1])], fill=(255, 255, 255, 16), width=1)
    for gy in range(0, size[1], 46):
        gd.line([(0, gy), (size[0], gy)], fill=(255, 255, 255, 16), width=1)
    grid.putalpha(Image.fromarray(np.minimum(np.array(grid.getchannel("A")), np.array(mask))))
    land.alpha_composite(grid)

    line = Image.new("RGBA", big, (0, 0, 0, 0))
    ld = ImageDraw.Draw(line)
    pts = [P(*p) for p in COAST]
    ld.line(pts + [pts[0]], fill=c4(CYAN), width=4 * ss, joint="curve")
    for x, y, r in keys:
        ld.ellipse((x - r * 1.5, y - r, x + r * 1.5, y + r), outline=c4(CYAN), width=2 * ss)
    ld.ellipse(lake, fill=(20, 70, 125, 255), outline=c4(CYAN), width=3 * ss)
    line = line.resize(size, Image.LANCZOS)
    glow = line.filter(ImageFilter.GaussianBlur(10))
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(glow)
    out.alpha_composite(land)
    out.alpha_composite(line)

    # Nordpfeil
    nx, ny = size[0] - 70, 70
    arrow = ss_shape((40, 56), lambda d, k: d.polygon([(20 * k, 0), (40 * k - 1, 56 * k - 1), (20 * k, 42 * k),
                                                       (0, 56 * k - 1)], fill=c4(WHITE, 200)))
    paste(out, arrow, nx - 20, ny)
    paste_c(out, text_img("N", font("xb", 30), MUTED), nx, ny + 62)
    return out


def real_map_path():
    return next((f for f in MAP_FILES if os.path.exists(f)), None)


def load_real_map(path):
    """Echte Karte (vom Nutzer bereitgestellt) einpassen; etwas größer laden als Reserve für den Zoom."""
    im = Image.open(path).convert("RGBA")
    k = min(RM_W / im.width, RM_H / im.height)
    fw, fh = int(im.width * k), int(im.height * k)
    big = im.resize((int(fw * RM_ZOOM), int(fh * RM_ZOOM)), Image.LANCZOS)
    mask = np.array(rrect(fw, fh, 28, (255, 255, 255, 255)).getchannel("A"))
    border = rrect(fw, fh, 28, (0, 0, 0, 0), outline=c4(CYAN), width=4)
    shadow = panel(fw, fh, None, fill=(0, 0, 0, 0))
    x, y = RM_X + (RM_W - fw) // 2, RM_Y + (RM_H - fh) // 2
    return dict(big=big, fw=fw, fh=fh, mask=mask, border=border, shadow=shadow, x=x, y=y)


def real_map_fn(scene_start, reveal=False):
    """Zeichnet die echte Karte mit langsamem Zoom über alle Map-Szenen hinweg."""
    R = _REAL

    def fn(frame, st):
        t0, t1 = R["span"]
        p = min(1.0, max(0.0, (scene_start + st - t0) / (t1 - t0)))
        z = 1 + (RM_ZOOM - 1) * p
        big, fw, fh = R["big"], R["fw"], R["fh"]
        cw, ch = big.width / z, big.height / z
        cx, cy = big.width / 2, big.height / 2
        view = big.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2)))
        view = view.resize((fw, fh), Image.BILINEAR)
        view.putalpha(Image.fromarray(np.minimum(np.array(view.getchannel("A")), R["mask"])))
        view.alpha_composite(R["border"])
        yr = fh
        if reveal:
            yr = int(fh * ease_out(min(1.0, max(0.0, (st - 0.1) / 1.3))))
            if yr <= 0:
                return
        paste(frame, R["shadow"].crop((0, 0, R["shadow"].width, yr + 2 * SH)), R["x"] - SH, R["y"] - SH)
        paste(frame, view.crop((0, 0, fw, yr)) if yr < fh else view, R["x"], R["y"])
        if yr < fh:
            ImageDraw.Draw(frame).line([(R["x"] - 20, R["y"] + yr), (R["x"] + fw + 20, R["y"] + yr)],
                                       fill=c4(CYAN), width=4)
    return fn


def region_chips(s, c, show, animate):
    """Regionen als Chips unter der echten Karte (2 Spalten × 3 Zeilen)."""
    for i, (name, desc, col, lon, lat, word) in enumerate(REGIONS):
        cx, top = RM_X + 245 + (i % 2) * 510, 1003 + (i // 2) * 80
        t = kw(c, word) if i in animate else -5
        if i not in show or i in animate:
            g = panel(490, 70, None, fill=(16, 18, 40, 200))
            paste(g, marker(i + 1, (90, 92, 120), 22), SH + 16, SH + 13)
            paste(g, text_img(name, font("b", 36), (110, 114, 150)), SH + 72, SH + 16)
            it = s.add_panel(with_alpha(g, 0.7), cx, top, -5, "fade")
            it["until"] = t if i in show else 1e9
        if i not in show:
            continue
        p = panel(490, 70, col)
        paste(p, marker(i + 1, col, 22), SH + 16, SH + 13)
        paste(p, text_img(name, font("b", 36)), SH + 72, SH + 16)
        s.add_panel(p, cx, top, t, "left" if i % 2 == 0 else "right")


def real_map_credit(s, t):
    s.add(text_img("Leonida-Karte © Rockstar Games", font("m", 25), MUTED), W / 2, 1250, t, "fade")


def marker(num, col, r=27):
    def fn(d, k):
        R = r * k
        d.ellipse((0, 0, 2 * R - 1, 2 * R - 1), fill=c4(WHITE))
        d.ellipse((4 * k, 4 * k, 2 * R - 4 * k - 1, 2 * R - 4 * k - 1), fill=c4(col))
    im = ss_shape((2 * r, 2 * r), fn)
    paste_c(im, text_img(str(num), font("black", 30), DARK), r, r - 19)
    return im


def pulse_fn(fx, fy, col, t0):
    def fn(frame, st):
        lt = st - t0
        if lt < 0 or lt > 2.4:
            return
        for k in range(2):
            p = ((lt + k * 0.6) % 1.2) / 1.2
            r = 27 + 46 * p
            a = int(200 * (1 - p))
            sz = int(2 * r + 8)
            ring = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
            ImageDraw.Draw(ring).ellipse((4, 4, sz - 5, sz - 5), outline=c4(col, a), width=5)
            paste(frame, ring, fx - sz / 2, fy - sz / 2)
    return fn


# ---------------------------------------------------------------- Logo
def logo_img(max_w, max_h):
    if os.path.exists(LOGO):
        im = Image.open(LOGO).convert("RGBA")
        bbox = im.getchannel("A").getbbox()
        if bbox:
            im = im.crop(bbox)
        s = min(max_w / im.width, max_h / im.height)
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    else:  # Platzhalter: eigener Schriftzug, nicht das offizielle Logo
        im = grad_text("GTA 6", fit("GTA 6", "black", 300, max_w), (255, 205, 95), PINK)
        if im.height > max_h:
            s = max_h / im.height
            im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    pad = 46
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    a = Image.new("L", out.size, 0)
    a.paste(im.getchannel("A"), (pad, pad))
    g = Image.new("RGBA", out.size, c4(PINK))
    g.putalpha(a.filter(ImageFilter.GaussianBlur(22)).point(lambda v: v * 6 // 10))
    out.alpha_composite(g)
    out.alpha_composite(im, (pad, pad))
    return out


def add_logo(s, cx, y, t, max_w=760, max_h=360):
    img = logo_img(max_w, max_h)
    it = s.add(img, cx, y, t, "pop", glow=False)
    A = np.array(img.getchannel("A"), np.float32) / 255.0
    hh, ww = A.shape
    xs = np.arange(ww)[None, :] + 0.45 * np.arange(hh)[:, None]

    def shine(frame, st):
        p = (st - (t + 0.55)) / 0.9
        if p < 0 or p > 1:
            return
        pos = -150 + p * (ww + 0.45 * hh + 300)
        band = np.exp(-((xs - pos) ** 2) / (2 * 55.0 ** 2)) * 0.6 * A
        layer = Image.new("RGBA", (ww, hh), (255, 255, 255, 0))
        layer.putalpha(Image.fromarray((band * 255).astype(np.uint8)))
        paste(frame, layer, it["x"], it["y"])
    s.dyn.append(shine)
    return it["y"] + img.height  # Unterkante (inkl. Glow)


# ---------------------------------------------------------------- Szenen
class Scene2(Scene):
    """Scene mit Ebene *unter* den Elementen (für die Karte)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.pre, self.bg_mode = [], "normal"

    def render(self, frame, st):
        for fn in self.pre:
            fn(frame, st)
        allitems = self.items
        self.items = [it for it in allitems if st < it.get("until", 1e9)]
        try:
            super().render(frame, st)
        finally:
            self.items = allitems


def kw(clip, word, default=0.5):
    for ch, t in zip(clip["chunks"], clip["ctimes"]):
        if word.lower() in ch.lower():
            return float(t)
    return default + LEAD


def row_panel(num, text, col, w=900, h=112, size=46):
    p = panel(w, h, col)
    paste(p, marker(num, col, 30), SH + 26, SH + h / 2 - 30)
    f = fit(text, "b", size, w - 140)
    ti = text_img(text, f)
    paste(p, ti, SH + 108, SH + h / 2 - ti.height / 2)
    return p


def avatar(letter, c1, c2, d=200):
    disc = grad((d, d), c1, c2)
    m = ss_shape((d, d), lambda dd, k: dd.ellipse((0, 0, d * k - 1, d * k - 1), fill=(255, 255, 255, 255)))
    disc.putalpha(m.getchannel("A"))
    letter_img = text_img(letter, font("black", 120), WHITE)
    paste_c(disc, letter_img, d / 2, d / 2 - letter_img.height / 2)
    return disc


def scene_hook(s, c):
    bottom = add_logo(s, W / 2, 300, 0.0)
    s.add(text_img("Alles, was du wissen musst", font("b", 54)), W / 2, bottom + 10, 0.45)
    y = bottom + 120
    for (label, col, word), cx in zip([("MAP", CYAN, "map"), ("STORY", PINK, "story"), ("FIGUREN", ORANGE, "figuren")],
                                      (260, 540, 820)):
        s.add(pill(label, col, DARK, size=44, padx=34, pady=18), cx, y, kw(c, word), "pop")
    p = panel(620, 120, YELLOW)
    paste_c(p, text_img("IN UNTER 90 SEKUNDEN", font("xb", 46), YELLOW), SH + 310, SH + 36)
    s.add_panel(p, W / 2, y + 170, kw(c, "90"))


def scene_map_intro(s, c, mp):
    s.bg_mode = "dim"
    if _REAL:
        s.pre.append(real_map_fn(c["start"], reveal=True))
        p = panel(490, 230, PINK)
        paste_c(p, grad_text("LEONIDA", fit("LEONIDA", "black", 100, 440), (255, 205, 95), PINK), SH + 245, SH + 34)
        paste_c(p, text_img("inspiriert von Florida", font("b", 36)), SH + 245, SH + 160)
        s.add_panel(p, RM_X + 245, 1003, kw(c, "leonida"), "left")
        p = panel(490, 230, ORANGE)
        paste_c(p, text_img("MAP-GRÖSSE", font("sb", 30), MUTED), SH + 245, SH + 26)
        paste_c(p, text_img("≈ 2× GTA 5", font("black", 76), ORANGE), SH + 245, SH + 76)
        paste_c(p, text_img("laut Preview-Berichten", font("m", 28), MUTED), SH + 245, SH + 176)
        s.add_panel(p, RM_X + 755, 1003, kw(c, "doppelt"), "right")
        real_map_credit(s, 1.2)
        return
    it = {"x": MX0 - PADM, "y": MY0 - PADM}

    def reveal(frame, st):
        p = ease_out(min(1.0, max(0.0, (st - 0.1) / 1.3)))
        yr = int(mp.height * p)
        if yr <= 0:
            return
        paste(frame, mp.crop((0, 0, mp.width, yr)) if yr < mp.height else mp, it["x"], it["y"])
        if p < 1:
            ImageDraw.Draw(frame).line([(it["x"], it["y"] + yr), (it["x"] + mp.width, it["y"] + yr)],
                                       fill=c4(CYAN), width=4)
    s.pre.append(reveal)
    s.add(grad_text("LEONIDA", fit("LEONIDA", "black", 130, 520), (255, 205, 95), PINK), 322, 600, kw(c, "leonida"), "pop")
    s.add(text_img("inspiriert von Florida", font("b", 42)), 322, 745, kw(c, "florida"))
    p = panel(520, 240, ORANGE)
    paste_c(p, text_img("MAP-GRÖSSE", font("sb", 32), MUTED), SH + 260, SH + 28)
    paste_c(p, text_img("≈ 2× GTA 5", font("black", 84), ORANGE), SH + 260, SH + 80)
    paste_c(p, text_img("laut Preview-Berichten", font("m", 30), MUTED), SH + 260, SH + 186)
    s.add_panel(p, 322, 850, kw(c, "doppelt"))
    s.add(text_img("Schematische Karte · keine offizielle Map", font("m", 26), MUTED), W / 2, 1238, 1.2, "fade")


def regions_panel_items(s, c, show, animate, t_panel):
    p = panel(545, 615, None, fill=(16, 18, 40, 225))
    paste(p, text_img("6 REGIONEN", font("xb", 34), MUTED), SH + 30, SH + 26)
    s.add_panel(p, 322, 572, t_panel, "fade")
    for i, (name, desc, col, lon, lat, word) in enumerate(REGIONS):
        t = kw(c, word) if i in animate else -5
        if i not in show or i in animate:  # blasse Vorschau-Zeile, bis die Region genannt wird
            ghost = Image.new("RGBA", (500, 84), (0, 0, 0, 0))
            paste(ghost, marker(i + 1, (90, 92, 120), 24), 0, 12)
            paste(ghost, text_img(name, font("b", 38), (110, 114, 150)), 66, 6)
            g = s.add(with_alpha(ghost, 0.55), 70, 650 + i * 88, -5, "fade", center=False, glow=False)
            g["until"] = t if i in show else 1e9
        if i not in show:
            continue
        row = Image.new("RGBA", (500, 84), (0, 0, 0, 0))
        paste(row, marker(i + 1, col, 24), 0, 12)
        paste(row, text_img(name, font("b", 38)), 66, 6)
        paste(row, text_img(desc, font("m", 26), MUTED), 68, 52)
        s.add(row, 70, 650 + i * 88, t, "left", center=False, glow=False)
        fx, fy = to_frame(lon, lat)
        s.add(marker(i + 1, col), fx, fy - 27, t, "pop", glow=False)
        if i in animate:
            s.dyn.append(pulse_fn(fx, fy, col, t))


def scene_regions_a(s, c, mp):
    s.bg_mode = "dim"
    if _REAL:
        s.pre.append(real_map_fn(c["start"]))
        region_chips(s, c, show={0, 1, 2}, animate={0, 1, 2})
        real_map_credit(s, -5)
        return
    s.add(mp, MX0 - PADM + mp.width / 2, MY0 - PADM, -5, glow=False)
    regions_panel_items(s, c, show={0, 1, 2}, animate={0, 1, 2}, t_panel=0.0)
    s.add(text_img("Schematische Karte · keine offizielle Map", font("m", 26), MUTED), W / 2, 1238, -5, "fade")


def scene_regions_b(s, c, mp):
    s.bg_mode = "dim"
    if _REAL:
        s.pre.append(real_map_fn(c["start"]))
        region_chips(s, c, show=set(range(6)), animate={3, 4, 5})
        real_map_credit(s, -5)
        return
    s.add(mp, MX0 - PADM + mp.width / 2, MY0 - PADM, -5, glow=False)
    regions_panel_items(s, c, show=set(range(6)), animate={3, 4, 5}, t_panel=-5)
    s.add(text_img("Schematische Karte · keine offizielle Map", font("m", 26), MUTED), W / 2, 1238, -5, "fade")


def scene_story_sting(s, c):
    bottom = add_logo(s, W / 2, 520, 0.0)
    s.add(grad_text("DIE STORY", fit("DIE STORY", "black", 170, 900), PINK, ORANGE), W / 2, bottom + 10, 0.3, "pop")


def scene_premise(s, c):
    for i, (name, col, word) in enumerate([("LUCIA", PINK, "lucia"), ("JASON", CYAN, "jason")]):
        p = panel(380, 150, col)
        paste_c(p, text_img(name, font("black", 78), col), SH + 190, SH + 36)
        s.add_panel(p, 70 + 190 + i * 560, 330, kw(c, word) if i == 0 else kw(c, word) + 0.25, "left" if i == 0 else "right")
    s.add(text_img("&", font("black", 90), ORANGE), W / 2, 355, kw(c, "jason"), "pop")
    s.add(pill("à la Bonnie & Clyde", ORANGE, DARK, size=40, padx=34, pady=16), W / 2, 530, kw(c, "bonnie"), "pop")
    p = panel(900, 170, RED)
    paste_c(p, text_img("Ein sicherer Coup …", font("b", 50)), SH + 450, SH + 28)
    paste_c(p, text_img("… geht schief!", font("xb", 58), RED), SH + 450, SH + 96)
    s.add_panel(p, W / 2, 660, kw(c, "coup"))
    p = panel(900, 170, ORANGE)
    paste_c(p, text_img("VERSCHWÖRUNG", font("black", 64), ORANGE), SH + 450, SH + 26)
    paste_c(p, text_img("quer durch ganz Leonida", font("b", 46)), SH + 450, SH + 106)
    s.add_panel(p, W / 2, 870, kw(c, "verschwörung"))
    s.add(text_img("laut offizieller Story-Beschreibung", font("m", 26), MUTED), W / 2, 1080, kw(c, "verschwörung") + 0.4, "fade")


def scene_profile(s, c, first, last, col1, col2, rows):
    s.add(avatar(first[0], col1, col2), 90 + 100, 330, 0.0, "pop", glow=False)
    s.add(text_img(first, font("black", 112), col1), 330, 338, 0.2, "left", center=False)
    s.add(text_img(last, font("xb", 58)), 334, 474, 0.4, "left", center=False)
    y = 600
    h = 112 if len(rows) <= 3 else 104
    for i, (txt, word) in enumerate(rows):
        s.add_panel(row_panel(i + 1, txt, col1, h=h), W / 2, y, kw(c, word), "left")
        y += h + 22
    s.add(text_img("Figurenbeschreibung laut Rockstar", font("m", 26), MUTED), W / 2, y + 10, kw(c, rows[-1][1]) + 0.4, "fade")


def scene_lucia(s, c):
    scene_profile(s, c, "LUCIA", "CAMINOS", PINK, ORANGE,
                  [("Vom Vater das Kämpfen gelernt", "vater"), ("Für ihre Familie ins Gefängnis", "gefängnis"),
                   ("Ab jetzt: nur noch kluge Züge", "kluge")])


def scene_jason(s, c):
    scene_profile(s, c, "JASON", "DUVAL", CYAN, (90, 120, 255),
                  [("Unter Gaunern aufgewachsen", "gaunern"), ("War bei der Army", "army"),
                   ("Jobs für Drogenschmuggler in den Keys", "drogenschmuggler"),
                   ("Will nur ein einfaches Leben", "einfaches")])


def phone():
    w, h = 260, 400
    im = rrect(w, h, 44, (20, 22, 46, 255), outline=c4(WHITE), width=6)
    scr = grad((w - 34, h - 60), PINK, ORANGE, horizontal=False)
    m = rrect(w - 34, h - 60, 26, (255, 255, 255, 255))
    scr.putalpha(m.getchannel("A"))
    paste(im, scr, 17, 30)
    paste(im, pill("LIVE", RED, WHITE, size=24, padx=14, pady=6), 34, 48)
    tri = ss_shape((90, 100), lambda d, k: d.polygon([(0, 0), (90 * k - 1, 50 * k), (0, 100 * k - 1)],
                                                      fill=(255, 255, 255, 235)))
    paste(im, tri, w / 2 - 36, h / 2 - 50)
    paste_c(im, text_img("2,4 Mio. Views", font("b", 26), WHITE), w / 2, h - 82)
    return im


def scene_cast(s, c):
    s.add(text_img("WEITERE FIGUREN", font("sb", 36), MUTED), W / 2, 318, 0.1, "fade")
    for i, (name, col, word) in enumerate([("CAL HAMPTON", CYAN, "cal"), ("BOOBIE IKE", ORANGE, "boobie"),
                                           ("RAUL BAUTISTA", VIOLET, "raul")]):
        p = panel(660, 92, col)
        paste_c(p, text_img(name, font("xb", 50), col), SH + 330, SH + 22)
        s.add_panel(p, W / 2, 375 + i * 110, kw(c, word), "left" if i % 2 == 0 else "right")
    s.add(grad_text("VICE CITY IST ZURÜCK!", fit("VICE CITY IST ZURÜCK!", "black", 90, 940), (255, 205, 95), PINK),
          W / 2, 720, kw(c, "vice"), "pop")
    s.add(phone(), 120 + 130, 850, kw(c, "social"), "pop", glow=False)
    s.add(text_img("Social-Media-", font("xb", 52)), 430, 930, kw(c, "social") + 0.2, "right", center=False)
    s.add(text_img("Chaos", font("black", 72), PINK), 430, 995, kw(c, "social") + 0.35, "right", center=False)
    s.add(text_img("wie in den Trailern", font("m", 34), MUTED), 432, 1090, kw(c, "trailern"), "fade", center=False)


def scene_outro(s, c):
    bottom = add_logo(s, W / 2, 250, 0.0, max_w=700, max_h=300)
    s.add(text_img("ab 19.11.2026", font("black", 96)), W / 2, bottom + 6, kw(c, "19"), "pop")
    s.add(text_img("PS5 · Xbox Series X|S", font("b", 46), CYAN), W / 2, bottom + 128, kw(c, "ps5"))
    s.add(pill("FOLG MIR FÜR MEHR", PINK, DARK, size=46, padx=44, pady=24), W / 2, bottom + 220, kw(c, "folg"), "pop")
    s.add(text_img("Welche Region feierst du am meisten?", fit("Welche Region feierst du am meisten?", "xb", 52, 960)),
          W / 2, bottom + 370, kw(c, "region"))
    s.add(text_img("Schreib's in die Kommentare!", font("sb", 42), MUTED), W / 2, bottom + 440, kw(c, "region") + 0.4)
    note = ("Inoffizielles Fan-Video · GTA VI & Leonida-Karte © Rockstar Games" if _REAL
            else "Inoffizielles Fan-Video · Karte schematisch, keine offizielle Map")
    s.add(text_img(note, fit(note, "m", 25, 980), MUTED), W / 2, 1190, 0.6, "fade")
    note2 = "Stand: 14.11.2026" if _REAL else "GTA VI © Rockstar Games · Stand: 14.11.2026"
    s.add(text_img(note2, font("m", 25), MUTED), W / 2, 1226, 0.6, "fade")


SCENES = [scene_hook, scene_map_intro, scene_regions_a, scene_regions_b, scene_story_sting, scene_premise,
          scene_lucia, scene_jason, scene_cast, scene_outro]
TAGS = [None, ("#1 DIE MAP", CYAN), ("#2 DIE REGIONEN", CYAN), ("#2 DIE REGIONEN", CYAN), None,
        ("#3 DIE STORY", PINK), ("#4 LUCIA", PINK), ("#5 JASON", CYAN), ("#6 FIGUREN & FEATURES", ORANGE), None]
MAP_SCENES = {1, 2, 3}


# ---------------------------------------------------------------- Timeline / Rendering
def build_timeline():
    clips, t0 = [], 0.0
    n = len(CAPTIONS)
    for i in range(n):
        path = os.path.join(VO_DIR, f"s{i + 1:02d}.mp3")
        v = load_voice(path)
        dur = len(v) / SR
        sdur = LEAD + dur + TAIL + (END_HOLD if i == n - 1 else 0)
        chunks = chunk_text(CAPTIONS[i])
        times = caption_times(chunks, dur, silences(path, dur))
        clips.append(dict(voice=v, start=t0, dur=dur, sdur=sdur, chunks=chunks, ctimes=times + LEAD))
        t0 += sdur
    return clips, t0


_S = {}


def init_worker():
    clips, total = build_timeline()
    bg, _ = build_backgrounds()
    dim = bg.copy()
    dim.alpha_composite(Image.new("RGBA", (W, H), (5, 5, 16, 150)))
    mp = build_map()
    _REAL.clear()
    rp = real_map_path()
    if rp:
        _REAL.update(load_real_map(rp))
        _REAL["span"] = (clips[1]["start"], clips[3]["start"] + clips[3]["sdur"])
    scenes = []
    for i, fn in enumerate(SCENES):
        tag = TAGS[i]
        s = Scene2(i, clips[i]["sdur"], tag[0] if tag else None, tag[1] if tag else CYAN)
        if i in MAP_SCENES:
            fn(s, clips[i], mp)
        else:
            fn(s, clips[i])
        scenes.append(s)
    header = text_img("GTA 6 · MAP, STORY & FIGUREN", font("sb", 28), MUTED)
    _S.update(clips=clips, total=total, bg=bg, dim=dim, scenes=scenes, header=header)


def render_frame(t):
    clips, scenes = _S["clips"], _S["scenes"]
    n = len(clips)
    i = 0
    while i < n - 1 and t >= clips[i + 1]["start"]:
        i += 1
    c, sc = clips[i], scenes[i]
    st = t - c["start"]
    frame = (_S["dim"] if sc.bg_mode == "dim" else _S["bg"]).copy()
    draw_floor_lines(frame, t)
    sc.render(frame, st)

    ct = c["ctimes"]
    j = int(np.searchsorted(ct, st, side="right")) - 1
    if j >= 0:
        cap = caption_img(c["chunks"][j])
        lt = st - ct[j]
        if lt < 0.08:
            cap = with_alpha(cap, lt / 0.08)
        paste_c(frame, cap, W / 2, 1395)

    d = ImageDraw.Draw(frame)
    seg_w = (W - 120 - (n - 1) * 8) / n
    for k in range(n):
        x0 = 60 + k * (seg_w + 8)
        d.rounded_rectangle((x0, 52, x0 + seg_w, 60), 4, fill=(255, 255, 255, 255) if k < i else (70, 70, 96, 255))
        if k == i:
            f = min(1.0, st / c["sdur"])
            if f * seg_w > 8:
                d.rounded_rectangle((x0, 52, x0 + f * seg_w, 60), 4, fill=(255, 255, 255, 255))
    paste(frame, _S["header"], 56, 78)
    if i > 0 and st < 0.12:
        frame = Image.blend(frame, Image.new("RGBA", (W, H), (255, 255, 255, 255)), 0.22 * (1 - st / 0.12))
    return frame.convert("RGB")


def render_segment(args):
    f0, f1, path = args
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                          "-pix_fmt", "yuv420p", "-profile:v", "high", path], stdin=subprocess.PIPE)
    for k in range(f0, f1):
        p.stdin.write(render_frame(k / FPS).tobytes())
    p.stdin.close()
    p.wait()
    return path


def main():
    init_worker()
    if len(sys.argv) > 2 and sys.argv[1] == "--preview":
        outdir = os.path.join(HERE, "preview2")
        os.makedirs(outdir, exist_ok=True)
        for tok in sys.argv[2].split(","):
            render_frame(float(tok)).save(os.path.join(outdir, f"t{float(tok):06.2f}.png"))
        print("total", round(_S["total"], 2), "starts", [round(c["start"], 2) for c in _S["clips"]])
        return
    clips, total = _S["clips"], _S["total"]
    assert total <= 90.0, f"Video zu lang: {total:.2f}s"
    nframes = int(math.ceil(total * FPS))
    print(f"Dauer {total:.2f}s, {nframes} Frames, Logo-Datei: {'ja' if os.path.exists(LOGO) else 'nein (Platzhalter)'}, "
          f"echte Karte: {real_map_path() or 'nein (schematische Karte)'}")
    tmp = tempfile.mkdtemp(prefix="gta6b_")
    wav = os.path.join(tmp, "mix.wav")
    mv.build_audio(clips, total, wav, booms=(0, 4, 9))
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
