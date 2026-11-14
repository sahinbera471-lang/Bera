#!/usr/bin/env python3
"""
GTA-6-Serie: fünf Kurzvideos (1080x1920, 30 fps) mit den Bausteinen aus make_video.py / make_video2.py.

    python3 make_series.py all                    # alle Videos rendern
    python3 make_series.py aktie                  # nur eins (aktie, gta5, geschichte, rekorde, vicecity)
    python3 make_series.py aktie --preview 3,12   # Vorschau-PNGs

Voiceover-Clips liegen in serie/<name>/voice/s01.mp3 … s07.mp3, die Videos landen in serie/<name>/.
"""
import math
import os
import subprocess
import sys
import tempfile
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw

import make_video as mv
import make_video2 as mv2
from make_video import (CYAN, DARK, FPS, GREEN, H, MUTED, ORANGE, PINK, RED, SH, SR, W, WHITE, YELLOW, c4,
                        caption_img, caption_times, chunk_text, draw_floor_lines, ease_out, fit, font, grad_text,
                        load_voice, panel, paste, paste_c, pill, rrect, silences, ss_shape, text_img, with_alpha)
from make_video2 import Scene2, add_logo, kw

HERE = os.path.dirname(os.path.abspath(__file__))
SERIE = os.path.join(HERE, "serie")
LEAD, TAIL, END_HOLD = 0.2, 0.35, 0.8
mv.LEAD = LEAD
GOLD = (255, 200, 60)
VIOLET = (165, 125, 255)
WARM = (255, 205, 95)


# ---------------------------------------------------------------- Bausteine
def add_text(s, text, y, t, size=48, weight="b", color=WHITE, anim="up", maxw=960, x=W / 2):
    return s.add(text_img(text, fit(text, weight, size, maxw), color), x, y, t, anim)


def add_title(s, text, y, t, size=160, c1=WARM, c2=PINK, maxw=960, anim="pop", x=W / 2):
    return s.add(grad_text(text, fit(text, "black", size, maxw), c1, c2), x, y, t, anim)


def _line_img(text, weight, size, col, maxw):
    f = fit(text, weight, size, maxw)
    if isinstance(col, list):
        return grad_text(text, f, col[0], col[1])
    return text_img(text, f, col)


def mk_card(lines, w=900, accent=None, pad=26, gap=12, fill=(20, 22, 46, 236), align="center", icon=None,
            min_h=0):
    """Karte mit Textzeilen [(text, weight, size, farbe | [c1, c2])], optional mit Icon links."""
    iw = icon.width + 30 if icon else 0
    imgs = [_line_img(t, wt, sz, col, w - 60 - iw) for t, wt, sz, col in lines]
    th = sum(i.height for i in imgs) + gap * (len(imgs) - 1)
    h = max(2 * pad + th, (icon.height + 2 * pad) if icon else 0, min_h)
    p = panel(w, h, accent, fill=fill)
    y = SH + (h - th) / 2
    if icon:
        paste(p, icon, SH + 30, SH + h / 2 - icon.height / 2)
    for im in imgs:
        if align == "center" and not icon:
            paste_c(p, im, SH + w / 2, y)
        else:
            paste(p, im, SH + 30 + iw, y)
        y += im.height + gap
    return p


def card_height(p):
    return p.height - 2 * SH


def arrow_icon(up=True, color=GREEN, size=110):
    def fn(d, k):
        S = size * k
        if up:
            pts = [(S / 2, 0), (S, S * .5), (S * .68, S * .5), (S * .68, S), (S * .32, S), (S * .32, S * .5), (0, S * .5)]
        else:
            pts = [(S / 2, S), (S, S * .5), (S * .68, S * .5), (S * .68, 0), (S * .32, 0), (S * .32, S * .5), (0, S * .5)]
        d.polygon(pts, fill=c4(color))
    return ss_shape((size, size), fn)


def bang_icon(color=ORANGE, size=84):
    im = ss_shape((size, size), lambda d, k: d.ellipse((0, 0, size * k - 1, size * k - 1), fill=c4(color)))
    t = text_img("!", font("black", int(size * .62)), DARK)
    paste_c(im, t, size / 2, size / 2 - t.height / 2)
    return im


def crown_icon(color=GOLD, size=230):
    h = int(size * .78)

    def fn(d, k):
        S, Hh = size * k, h * k
        d.polygon([(0, Hh * .25), (S * .25, Hh * .58), (S * .5, Hh * .12), (S * .75, Hh * .58), (S, Hh * .25),
                   (S * .9, Hh * .82), (S * .1, Hh * .82)], fill=c4(color))
        d.rounded_rectangle((S * .1, Hh * .84, S * .9, Hh), 8 * k, fill=c4(color))
        for cx, cy in [(0, Hh * .25), (S * .5, Hh * .12), (S, Hh * .25)]:
            r = S * .06
            d.ellipse((max(0, cx - r), max(0, cy - r), min(S - 1, cx + r), cy + r), fill=c4(color))
        for cx in (S * .3, S * .5, S * .7):
            d.ellipse((cx - S * .04, Hh * .62, cx + S * .04, Hh * .72), fill=c4(PINK))
    return ss_shape((size, h), fn)


def trophy_icon(color=GOLD, size=230):
    def fn(d, k):
        S = size * k
        d.ellipse((S * .02, S * .1, S * .3, S * .42), outline=c4(color), width=int(S * .05))
        d.ellipse((S * .7, S * .1, S * .98, S * .42), outline=c4(color), width=int(S * .05))
        d.pieslice((S * .18, -S * .3, S * .82, S * .62), 0, 180, fill=c4(color))
        d.rectangle((S * .18, S * .02, S * .82, S * .16), fill=c4(color))
        d.rectangle((S * .44, S * .6, S * .56, S * .8), fill=c4(color))
        d.rounded_rectangle((S * .26, S * .8, S * .74, S * .95), 6 * k, fill=c4(color))
        d.ellipse((S * .42, S * .2, S * .58, S * .36), fill=c4(WHITE, 200))
    return ss_shape((size, size), fn)


def play_icon(color=PINK, size=150):
    def fn(d, k):
        S = size * k
        d.ellipse((0, 0, S - 1, S - 1), fill=c4(color))
        d.polygon([(S * .4, S * .28), (S * .74, S * .5), (S * .4, S * .72)], fill=c4(WHITE))
    return ss_shape((size, size), fn)


def palm_icon(size=300):
    def fn(d, k):
        S = size * k
        pts = [(S * .5 + math.sin(u * 1.2) * S * .08, S * (.98 - .62 * u)) for u in np.linspace(0, 1, 12)]
        d.line(pts, fill=(150, 98, 60, 255), width=int(S * .06), joint="curve")
        tx, ty = pts[-1]
        for ang in (-160, -125, -90, -55, -20, 15, 200):
            a = math.radians(ang)
            ex, ey = tx + math.cos(a) * S * .36, ty + math.sin(a) * S * .22 + S * .08
            mx, my = (tx + ex) / 2 + math.sin(a) * S * .05, (ty + ey) / 2 - S * .06
            d.polygon([(tx, ty), (mx, my - S * .04), (ex, ey), (mx, my + S * .04)], fill=c4(GREEN))
        d.ellipse((tx - S * .04, ty - S * .01, tx + S * .04, ty + S * .07), fill=(120, 80, 50, 255))
    return ss_shape((size, size), fn)


def islands_icon(size=200, color=CYAN):
    def fn(d, k):
        S = size * k
        d.ellipse((S * .05, S * .25, S * .45, S * .8), fill=c4(color))
        d.ellipse((S * .55, S * .15, S * .95, S * .85), fill=c4(color))
        d.ellipse((S * .44, S * .45, S * .56, S * .55), fill=c4(color, 160))
    return ss_shape((size, size), fn)


def state_icon(size=200, color=PINK):
    xs = [p[0] for p in mv2.COAST]
    ys = [p[1] for p in mv2.COAST]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sc = 1 / max(x1 - x0, (y1 - y0) * 1.15)

    def fn(d, k):
        S = size * k
        pts = [((x - x0) * sc * S, (y1 - y) * sc * 1.15 * S) for x, y in mv2.COAST]
        d.polygon(pts, fill=c4(color))
    return ss_shape((size, size), fn)


def vs_cards(s, left, right, y, tl, tr, lcol=CYAN, rcol=PINK, w=470, icons=(None, None)):
    lp = mk_card(left, w=w, accent=lcol)
    rp = mk_card(right, w=w, accent=rcol)
    hh = max(card_height(lp), card_height(rp))
    lp = mk_card(left, w=w, accent=lcol, min_h=hh)
    rp = mk_card(right, w=w, accent=rcol, min_h=hh)
    s.add_panel(lp, 50 + w / 2, y, tl, "left")
    s.add_panel(rp, W - 50 - w / 2, y, tr, "right")
    s.add(pill("VS", YELLOW, DARK, size=40, padx=22, pady=12), W / 2, y + hh / 2 - 34, min(tl, tr) + 0.25, "pop",
          glow=False)
    if icons[0] is not None:
        s.add(icons[0], 50 + w / 2, y - icons[0].height - 16, tl, "pop", glow=False)
    if icons[1] is not None:
        s.add(icons[1], W - 50 - w / 2, y - icons[1].height - 16, tr, "pop", glow=False)
    return y + hh


def bar_fn(x0, y0, wmax, h, frac, color, t0, dur=1.1):
    def fn(frame, st):
        p = ease_out(min(1.0, max(0.0, (st - t0) / dur)))
        if p <= 0:
            return
        paste(frame, rrect(max(h, int(wmax * frac * p)), h, h // 2, c4(color)), x0, y0)
    return fn


def outro_tail(s, c, y, question, word):
    t = kw(c, word)
    add_text(s, question, y, t, size=56, weight="xb", maxw=980)
    add_text(s, "Schreib's in die Kommentare!", y + 82, t + 0.4, size=42, weight="sb", color=MUTED)
    s.add(pill("FOLG MIR FÜR MEHR", PINK, DARK, size=44, padx=40, pady=22), W / 2, y + 165, t + 0.8, "pop")


def disclaimer(s, l1, l2):
    for txt, y in ((l1, 1190), (l2, 1226)):
        s.add(text_img(txt, fit(txt, "m", 25, 990), MUTED), W / 2, y, 0.6, "fade")


# ---------------------------------------------------------------- Video: Take-Two-Aktie
def ak1(s, c):
    s.add(arrow_icon(True, GREEN, 120), 150, 330, 0.3, "pop", glow=False)
    s.add(arrow_icon(False, RED, 120), 930, 330, 0.5, "pop", glow=False)
    add_title(s, "TTWO", 300, 0.0, size=230, c1=GREEN, c2=CYAN, maxw=620)
    add_text(s, "Take-Two Interactive", 560, kw(c, "take-two"), size=56, weight="xb")
    add_text(s, "Mutterkonzern von Rockstar Games", 640, kw(c, "mutterkonzern"), size=40, weight="m", color=MUTED)
    s.add_panel(mk_card([("Bewegt GTA 6 die Aktie?", "xb", 56, WHITE)], accent=YELLOW), W / 2, 760, 0.6)
    s.add(pill("KEINE ANLAGEBERATUNG", (120, 24, 40), (255, 170, 170), size=30), W / 2, 960, 1.0, "fade")


def ak2(s, c):
    s.bg_mode = "red"
    for i, (when, what, word) in enumerate([("Mai 2025", "Verschiebung #1 → Mai 2026", "verschiebungen"),
                                             ("Nov. 2025", "Verschiebung #2 → 19.11.2026", "jedes")]):
        p = mk_card([(when, "xb", 58, WHITE), (what, "m", 34, MUTED), ("≈ −10 %", "black", 84, RED)],
                    accent=RED, icon=arrow_icon(False, RED, 120), align="left")
        s.add_panel(p, W / 2, 340 + i * 330, kw(c, word) + 0.2 * i, "left")
    add_text(s, "Kursrutsch direkt nach der Meldung (Berichte: ca. 8–11 %)", 1010, kw(c, "prozent"),
             size=32, weight="m", color=MUTED, anim="fade")


def ak3(s, c):
    s.add(arrow_icon(True, GREEN, 150), W / 2, 300, kw(c, "wende"), "pop", glow=False)
    add_title(s, "+8 %", 470, kw(c, "8"), size=250, c1=GREEN, c2=(190, 255, 120))
    s.add_panel(mk_card([("nach den Quartalszahlen", "b", 48, WHITE), ("vom 9. November 2026", "m", 34, MUTED)],
                        accent=GREEN), W / 2, 760, kw(c, "quartalszahlen"))
    s.add_panel(mk_card([("Kurs: rund 230 $", "xb", 54, WHITE), ("Schlusskurs am 11.11.2026", "m", 30, MUTED)]),
                W / 2, 990, kw(c, "oben"))


def ak4(s, c):
    add_text(s, "VORBESTELLUNGEN", 330, kw(c, "vorbestellungen"), size=42, weight="sb", color=MUTED, anim="fade")
    add_title(s, "~1 Mrd. $", 400, kw(c, "milliarde"), size=210, c1=GREEN, c2=YELLOW)
    s.add_panel(mk_card([("„weit über unseren Erwartungen“", "b", 46, WHITE),
                         ("Take-Two-Chef Strauss Zelnick (sinngemäß)", "m", 30, MUTED)], accent=GREEN),
                W / 2, 680, kw(c, "erwartungen"))
    add_text(s, "Schätzung: Sensor Tower · vor dem Release", 930, kw(c, "milliarde") + 0.4, size=32, weight="m",
             color=MUTED, anim="fade")


def ak5(s, c):
    s.add_panel(mk_card([("JAHRESPROGNOSE", "sb", 34, MUTED), ("7,98–8,18 Mrd. $", "black", 84, [CYAN, GREEN]),
                         ("Umsatz-Prognose erhöht", "b", 36, GREEN)], accent=CYAN,
                        icon=arrow_icon(True, GREEN, 110), align="left"), W / 2, 330, kw(c, "jahresprognose"))
    s.add_panel(mk_card([("28 von 29", "black", 110, [GREEN, (190, 255, 120)]),
                         ("Analysten: „Kaufen“", "b", 46, WHITE), ("Stand vor den Quartalszahlen", "m", 30, MUTED)],
                        accent=GREEN), W / 2, 690, kw(c, "analysten"))


def ak6(s, c):
    s.bg_mode = "red"
    add_title(s, "RISIKEN", 320, kw(c, "vorsicht"), size=150, c1=ORANGE, c2=RED)
    for i, (txt, word) in enumerate([("Hohe Bewertung (≈ 5,7× Umsatz)", "bewertet"),
                                     ("Viel Hype schon eingepreist", "hype"),
                                     ("Kurs kann nach dem Release fallen", "fallen")]):
        s.add_panel(mk_card([(txt, "b", 44, WHITE)], accent=ORANGE, icon=bang_icon(), align="left"),
                    W / 2, 540 + i * 160, kw(c, word), "left")


def ak7(s, c):
    s.add_panel(mk_card([("KEINE ANLAGEBERATUNG", "black", 64, RED), ("informier dich immer selbst", "b", 40, WHITE)],
                        accent=RED), W / 2, 320, 0.1, "pop")
    bottom = add_logo(s, W / 2, 600, 0.3, max_w=520, max_h=170)
    outro_tail(s, c, bottom + 20, "Schießt GTA 6 die Aktie nach oben?", "glaubst")
    disclaimer(s, "Stand: 14.11.2026 · Quellen: Take-Two, Sensor Tower, Analystenberichte",
               "Inoffizielles Fan-Video · keine Anlageberatung")


# ---------------------------------------------------------------- Video: GTA 5 Legende
def g1(s, c):
    s.add(crown_icon(GOLD, 240), W / 2, 290, 0.0, "pop", glow=False)
    add_title(s, "GTA 5", 500, 0.15, size=260, c1=GOLD, c2=ORANGE, maxw=800)
    add_text(s, "DIE LEGENDE", 760, kw(c, "legende"), size=86, weight="black")
    s.add(pill("Nr. 1 für viele", GOLD, DARK, size=46, padx=36, pady=18), W / 2, 890, kw(c, "nummer"), "pop")


def g2(s, c):
    s.add_panel(mk_card([("17.09.2013", "black", 76, [GOLD, ORANGE]), ("Release auf PS3 & Xbox 360", "m", 36, MUTED)],
                        accent=GOLD), W / 2, 320, kw(c, "september"))
    add_title(s, "815 Mio. $", 560, kw(c, "24"), size=180, c1=GREEN, c2=YELLOW)
    add_text(s, "Umsatz in 24 Stunden", 770, kw(c, "24") + 0.3, size=54, weight="xb")
    add_text(s, "11,2 Mio. verkaufte Spiele am ersten Tag (Guinness)", 860, kw(c, "umsatz"), size=32, weight="m",
             color=MUTED, anim="fade")


def g3(s, c):
    add_title(s, "1 MRD. $", 320, kw(c, "milliarde"), size=210, c1=GREEN, c2=YELLOW)
    add_text(s, "in nur 3 Tagen", 560, kw(c, "milliarde") + 0.3, size=70, weight="black")
    s.add_panel(mk_card([("GUINNESS-WELTREKORD", "black", 56, GOLD),
                         ("Schnellstes Entertainment-Produkt zur Milliarde", "b", 36, WHITE),
                         ("Rekord von 2013 · schneller als jeder Film", "m", 30, MUTED)],
                        accent=GOLD, icon=trophy_icon(GOLD, 130), align="left"), W / 2, 720, kw(c, "guinness"))


def g4(s, c):
    add_title(s, "~235 MIO.", 320, kw(c, "235"), size=210, c1=GOLD, c2=ORANGE)
    add_text(s, "verkaufte Exemplare", 550, kw(c, "235") + 0.3, size=56, weight="xb")
    add_text(s, "Stand: 30.09.2026 · Quelle: Take-Two", 635, kw(c, "235") + 0.5, size=30, weight="m", color=MUTED,
             anim="fade")
    s.add_panel(mk_card([("EINES DER MEISTVERKAUFTEN", "black", 54, GOLD), ("SPIELE ALLER ZEITEN", "black", 54, WHITE)],
                        accent=GOLD, icon=crown_icon(GOLD, 120), align="left"), W / 2, 760, kw(c, "meistverkauften"))


def g5(s, c):
    add_title(s, "3 GENERATIONEN", 310, kw(c, "konsolen-generationen"), size=110, c1=GOLD, c2=ORANGE)
    for i, (yr, plat, word) in enumerate([("2013", "PS3 · Xbox 360", "ps3"), ("2014/15", "PS4 · Xbox One · PC", "ps4"),
                                          ("2022", "PS5 · Xbox Series X|S", "ps5")]):
        p = mk_card([(yr, "black", 64, [GOLD, ORANGE]), (plat, "b", 46, WHITE)], accent=GOLD, align="left")
        s.add_panel(p, W / 2, 480 + i * 220, kw(c, word), "left")


def g6(s, c):
    add_title(s, "GTA ONLINE", 310, kw(c, "online"), size=150, c1=CYAN, c2=GREEN)
    add_text(s, "seit 2013 · ständig neue Updates", 500, kw(c, "updates"), size=48, weight="b")
    s.add_panel(mk_card([("~5 Mio.", "black", 120, [GREEN, YELLOW]), ("verkaufte Kopien pro Quartal", "b", 44, WHITE),
                         ("immer noch – 13 Jahre nach Release", "m", 32, MUTED)], accent=GREEN),
                W / 2, 640, kw(c, "millionen"))


def g7(s, c):
    s.add(crown_icon(GOLD, 200), W / 2, 280, 0.0, "pop", glow=False)
    add_title(s, "GTA 5", 455, 0.1, size=170, c1=GOLD, c2=ORANGE, maxw=700)
    add_text(s, "BLEIBT DIE LEGENDE", 640, kw(c, "legende"), size=72, weight="black")
    outro_tail(s, c, 780, "Für dich auch die Nummer 1?", "nummer")
    disclaimer(s, "Stand: 14.11.2026 · Quellen: Take-Two, Guinness World Records",
               "Inoffizielles Fan-Video · GTA V © Rockstar Games")


# ---------------------------------------------------------------- Video: Geschichte
YEARS = [1997, 1999, 2001, 2002, 2004, 2008, 2013, 2026]


def timeline_strip(active):
    w, h, ly = 980, 130, 65
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def x_of(yr):
        return 40 + (yr - 1997) / (2026 - 1997) * (w - 80)
    d.line([(40, ly), (w - 40, ly)], fill=(96, 98, 140, 255), width=5)
    for i, yr in enumerate(YEARS):
        on = yr in active
        r = 15 if on else 9
        x = x_of(yr)
        d.ellipse((x - r, ly - r, x + r, ly + r), fill=c4(YELLOW if on else (130, 132, 170)))
        if on:
            t = text_img(str(yr), font("xb", 28), YELLOW)
            paste_c(im, t, x, ly + 24 if i % 2 == 0 else ly - 24 - t.height)
    return im


def era_card(year, name, detail, accent):
    return mk_card([(year, "black", 104, [GOLD, ORANGE]), (name, "black", 62, WHITE), (detail, "m", 36, MUTED)],
                   accent=accent)


def hist_strip(s, active, t=-5, anim="fade"):
    s.add(timeline_strip(active), W / 2, 285, t, anim, glow=False)


def h1(s, c):
    hist_strip(s, YEARS, 0.2)
    add_title(s, "29 JAHRE GTA", 470, 0.0, size=150, c1=WARM, c2=PINK)
    add_text(s, "1997 → 2026", 660, kw(c, "1997"), size=92, weight="black")
    add_text(s, "in einer Minute", 790, kw(c, "minute"), size=52, weight="b", color=MUTED)


def h2(s, c):
    hist_strip(s, {1997, 1999})
    s.add_panel(era_card("1997", "Grand Theft Auto", "Ansicht von oben · 2D", CYAN), W / 2, 440, kw(c, "1997"))
    s.add_panel(era_card("1999", "GTA 2", "Der Nachfolger", CYAN), W / 2, 780, kw(c, "1999"))


def h3(s, c):
    hist_strip(s, {2001, 2002})
    s.add_panel(era_card("2001", "GTA III", "Erstmals in 3D · Liberty City", ORANGE), W / 2, 440, kw(c, "2001"))
    s.add_panel(era_card("2002", "Vice City", "80er-Jahre-Feeling", PINK), W / 2, 780, kw(c, "vice"))


def h4(s, c):
    hist_strip(s, {2004})
    s.add_panel(era_card("2004", "San Andreas", "3 Städte · CJ als Hauptfigur", GREEN), W / 2, 470, kw(c, "2004"))
    s.add(pill("NEUE MASSSTÄBE", GREEN, DARK, size=44, padx=36, pady=18), W / 2, 830, kw(c, "maßstäbe"), "pop")


def h5(s, c):
    hist_strip(s, {2008, 2013})
    s.add_panel(era_card("2008", "GTA IV", "Niko Bellic · düster & realistisch", VIOLET), W / 2, 440, kw(c, "2008"))
    s.add_panel(era_card("2013", "GTA V", "Gleich 3 Hauptfiguren", GOLD), W / 2, 780, kw(c, "2013"))


def h6(s, c):
    hist_strip(s, {2026})
    bottom = add_logo(s, W / 2, 420, kw(c, "gta 6"), max_w=640, max_h=230)
    add_text(s, "2026", bottom + 10, kw(c, "gta 6") + 0.2, size=110, weight="black", color=YELLOW)
    add_text(s, "Lucia & Jason · zurück in Vice City", bottom + 150, kw(c, "lucia"), size=46, weight="b")
    s.add(pill("13 JAHRE NACH GTA V", PINK, DARK, size=40, padx=32, pady=16), W / 2, bottom + 240, kw(c, "13"), "pop")


def h7(s, c):
    add_title(s, "~480 MIO.", 320, kw(c, "480"), size=200, c1=WARM, c2=PINK)
    add_text(s, "verkaufte Spiele der ganzen Reihe", 545, kw(c, "480") + 0.3, size=46, weight="b")
    outro_tail(s, c, 700, "Welches GTA ist dein Favorit?", "favorit")
    disclaimer(s, "Stand: 14.11.2026 · Quelle: Take-Two", "Inoffizielles Fan-Video · GTA © Rockstar Games")


# ---------------------------------------------------------------- Video: Rekorde
def r1(s, c):
    s.add(trophy_icon(GOLD, 260), W / 2, 290, 0.0, "pop", glow=False)
    add_title(s, "REKORDE", 590, 0.2, size=190, c1=GOLD, c2=PINK)
    add_text(s, "schon vor dem Release", 800, kw(c, "rekorde"), size=56, weight="xb")


def r2(s, c):
    s.add(play_icon(PINK, 130), 180, 320, 0.0, "pop", glow=False)
    s.add(text_img("TRAILER 1", font("black", 70)), 280, 322, 0.1, "left", center=False)
    s.add(text_img("Dezember 2023", font("m", 38), MUTED), 284, 405, 0.2, "left", center=False)
    add_title(s, "90,4 MIO.", 500, kw(c, "90"), size=190, c1=PINK, c2=ORANGE)
    add_text(s, "Aufrufe auf YouTube in 24 Stunden", 720, kw(c, "youtube"), size=46, weight="b")
    stamp = pill("WELTREKORD", RED, WHITE, size=60, padx=40, pady=20).rotate(-6, resample=Image.BICUBIC, expand=True)
    s.add(stamp, W / 2, 840, kw(c, "weltrekord"), "pop", glow=False)


def r3(s, c):
    add_title(s, "3× GUINNESS", 310, kw(c, "guinness"), size=150, c1=GOLD, c2=ORANGE)
    rows = [("Meistgesehenes Nicht-Musik-Video in 24 h – vor MrBeast", "mrbeast"),
            ("Meistgesehener Spiele-Reveal auf YouTube in 24 h", "guinness"),
            ("Meistgelikter Spiele-Trailer in 24 h: 8,9 Mio. Likes", "likes")]
    for i, (txt, word) in enumerate(rows):
        s.add_panel(mk_card([(txt, "b", 38, WHITE)], accent=GOLD, icon=trophy_icon(GOLD, 70), align="left"),
                    W / 2, 520 + i * 165, kw(c, word), "left")


def r4(s, c):
    s.add(play_icon(CYAN, 130), 180, 320, 0.0, "pop", glow=False)
    s.add(text_img("TRAILER 2", font("black", 70)), 280, 322, 0.1, "left", center=False)
    s.add(text_img("Mai 2025", font("m", 38), MUTED), 284, 405, 0.2, "left", center=False)
    add_title(s, "475 MIO.", 500, kw(c, "475"), size=200, c1=CYAN, c2=PINK)
    add_text(s, "Aufrufe in 24 Stunden", 725, kw(c, "475") + 0.3, size=52, weight="xb")
    add_text(s, "auf allen Plattformen zusammen (laut Rockstar)", 810, kw(c, "plattformen"), size=36, weight="m",
             color=MUTED)


def r5(s, c):
    add_text(s, "GRÖSSTER VIDEO-LAUNCH ALLER ZEITEN", 320, kw(c, "größte"), size=54, weight="black", color=YELLOW)
    add_text(s, "laut Rockstar · Aufrufe in 24 Stunden", 395, kw(c, "größte") + 0.2, size=34, weight="m", color=MUTED)
    rows = [("GTA 6 – Trailer 2", 475, "475 Mio.", PINK, kw(c, "größte") + 0.4),
            ("Deadpool & Wolverine – Trailer", 365, "365 Mio.", (140, 142, 180), kw(c, "deadpool"))]
    for i, (name, val, lab, col, t) in enumerate(rows):
        y = 520 + i * 230
        s.add(text_img(name, font("b", 44)), 80, y, t, "fade", center=False)
        s.dyn.append(bar_fn(80, y + 70, 760, 70, val / 475, col, t))
        s.add(text_img(lab, font("black", 52), col), 80 + int(760 * val / 475) + 20, y + 72, t + 1.0, "fade",
              center=False)


def r6(s, c):
    add_text(s, "VORBESTELLUNGEN", 330, kw(c, "vorbestellungen"), size=44, weight="sb", color=MUTED, anim="fade")
    add_title(s, "~1 MRD. $", 400, kw(c, "milliarde"), size=210, c1=GREEN, c2=YELLOW)
    add_text(s, "bevor das Spiel überhaupt erscheint", 640, kw(c, "bevor"), size=48, weight="b")
    add_text(s, "Schätzung: Sensor Tower", 720, kw(c, "bevor") + 0.3, size=32, weight="m", color=MUTED, anim="fade")


def r7(s, c):
    end = vs_cards(s, [("GTA 5 · Tag 1", "xb", 40, MUTED), ("815 Mio. $", "black", 70, [GOLD, ORANGE])],
                   [("GTA 6 · Tag 1", "xb", 40, MUTED), ("???", "black", 70, [PINK, CYAN])],
                   320, kw(c, "815"), kw(c, "knackt"), lcol=GOLD, rcol=PINK)
    outro_tail(s, c, end + 60, "Knackt GTA 6 den Rekord?", "knackt")
    disclaimer(s, "Quellen: Guinness World Records, Rockstar, Sensor Tower · Stand: 14.11.2026",
               "Inoffizielles Fan-Video · GTA © Rockstar Games")


# ---------------------------------------------------------------- Video: Vice City damals vs. heute
OLD = (64, 224, 255)
NEW = PINK


def v1(s, c):
    add_title(s, "VICE CITY", 330, kw(c, "vice"), size=180, c1=OLD, c2=PINK)
    add_text(s, "ist zurück!", 540, kw(c, "zurück"), size=64, weight="black")
    vs_cards(s, [("2002", "black", 110, [OLD, VIOLET]), ("Das Original", "b", 40, MUTED)],
             [("2026", "black", 110, [WARM, PINK]), ("GTA 6", "b", 40, MUTED)], 680, kw(c, "2002"),
             kw(c, "vergleich"), lcol=OLD, rcol=NEW)


def v2(s, c):
    add_title(s, "DIE ZEIT", 320, 0.0, size=130, c1=OLD, c2=PINK)
    vs_cards(s, [("1986", "black", 110, [OLD, VIOLET]), ("Neon · Synthpop", "b", 38, WHITE), ("80er-Mode", "b", 38, WHITE)],
             [("HEUTE", "black", 110, [WARM, PINK]), ("Gegenwart", "b", 38, WHITE), ("Social-Media-Zeit", "b", 38, WHITE)],
             520, kw(c, "1986"), kw(c, "gegenwart"), lcol=OLD, rcol=NEW)


def v3(s, c):
    add_title(s, "DIE HELDEN", 320, 0.0, size=130, c1=OLD, c2=PINK)
    vs_cards(s, [("1", "black", 120, [OLD, VIOLET]), ("Tommy Vercetti", "xb", 40, WHITE), ("allein unterwegs", "m", 34, MUTED)],
             [("2", "black", 120, [WARM, PINK]), ("Lucia & Jason", "xb", 40, WHITE), ("zu zweit", "m", 34, MUTED)],
             520, kw(c, "tommy"), kw(c, "lucia"), lcol=OLD, rcol=NEW)
    add_text(s, "Hauptfiguren", 930, kw(c, "lucia") + 0.4, size=44, weight="b", color=MUTED, anim="fade")


def v4(s, c):
    add_title(s, "DIE MAP", 320, 0.0, size=130, c1=OLD, c2=PINK)
    vs_cards(s, [("2 Inseln", "black", 66, [OLD, VIOLET]), ("nur die Stadt", "b", 38, WHITE)],
             [("Ganz Leonida", "black", 60, [WARM, PINK]), ("Vice City ist nur", "b", 38, WHITE),
              ("ein Teil davon", "b", 38, WHITE)],
             740, kw(c, "inseln"), kw(c, "leonida"), lcol=OLD, rcol=NEW,
             icons=(islands_icon(190, OLD), state_icon(190, NEW)))


def v5(s, c):
    add_title(s, "DIE TECHNIK", 320, 0.0, size=130, c1=OLD, c2=PINK)
    vs_cards(s, [("PS2", "black", 120, [OLD, VIOLET]), ("PlayStation 2", "b", 38, WHITE), ("2002", "m", 34, MUTED)],
             [("PS5 · XBOX", "black", 74, [WARM, PINK]), ("Social Media", "b", 36, WHITE), ("volle Strände", "b", 36, WHITE),
              ("krasse Details", "b", 36, WHITE)],
             520, kw(c, "playstation"), kw(c, "ps5"), lcol=OLD, rcol=NEW)


def v6(s, c):
    s.add(palm_icon(320), W / 2, 280, 0.0, "pop", glow=False)
    add_text(s, "WAS GLEICH BLEIBT", 630, 0.2, size=48, weight="sb", color=MUTED, anim="fade")
    add_title(s, "SONNE · STRÄNDE · PALMEN", 700, kw(c, "sonne"), size=80, c1=WARM, c2=PINK)
    add_text(s, "+ dieses Miami-Gefühl", 820, kw(c, "miami"), size=56, weight="xb")
    s.add(pill("24 JAHRE SPÄTER", OLD, DARK, size=44, padx=36, pady=18), W / 2, 930, kw(c, "24"), "pop")


def v7(s, c):
    add_text(s, "Welches Vice City feierst du mehr?", 330, 0.1, size=60, weight="black", maxw=990)
    s.add(pill("ORIGINAL 2002", OLD, DARK, size=48, padx=40, pady=22), 290, 470, kw(c, "original"), "pop")
    s.add(pill("NEU 2026", NEW, DARK, size=48, padx=40, pady=22), 800, 470, kw(c, "neue"), "pop")
    add_text(s, "Schreib's in die Kommentare!", 640, kw(c, "kommentare"), size=48, weight="sb", color=MUTED)
    s.add(pill("FOLG MIR FÜR MEHR", PINK, DARK, size=44, padx=40, pady=22), W / 2, 740, kw(c, "folg"), "pop")
    bottom = add_logo(s, W / 2, 880, 0.4, max_w=420, max_h=150)
    disclaimer(s, "Stand: 14.11.2026 · Inoffizielles Fan-Video",
               "GTA Vice City & GTA VI © Rockstar Games")


# ---------------------------------------------------------------- Konfiguration
VIDEOS = {
    "aktie": dict(
        out="GTA6_TakeTwo_Aktie.mp4", header="GTA 6 · DIE AKTIE", booms=(0, 2),
        scenes=[ak1, ak2, ak3, ak4, ak5, ak6, ak7],
        tags=[None, ("#1 VERSCHIEBUNGEN", RED), ("#2 DIE WENDE", GREEN), ("#3 VORBESTELLUNGEN", GREEN),
              ("#4 PROGNOSE", CYAN), ("#5 RISIKEN", ORANGE), None],
        highlight={"gta", "6", "take-two", "rockstar", "aktie", "10", "8", "prozent", "1", "milliarde", "milliarden",
                   "kaufen", "analysten", "anlageberatung", "hype", "vorsicht", "jahresprognose"},
        captions=[
            "Kann GTA 6 eine ganze Aktie bewegen? Bei Take-Two, dem Mutterkonzern von Rockstar, auf jeden Fall!",
            "Das zeigen die Verschiebungen: Jedes Mal, wenn GTA 6 verschoben wurde, fiel die Aktie um rund 10 Prozent.",
            "Jetzt, kurz vor dem Release, die Wende: Nach den neuen Quartalszahlen sprang die Aktie um rund 8 Prozent nach oben.",
            "Der Grund: Die Vorbestellungen laufen laut Take-Two weit über den Erwartungen. Schätzungen sprechen von rund 1 Milliarde Dollar.",
            "Take-Two hat deshalb die Jahresprognose erhöht – auf rund 8 Milliarden Dollar Umsatz. Und fast alle Analysten stufen die Aktie mit Kaufen ein.",
            "Aber Vorsicht: Die Aktie ist hoch bewertet, und viel Hype ist schon eingepreist. Nach dem Release kann der Kurs auch fallen.",
            "Das hier ist keine Anlageberatung – informier dich immer selbst. Was glaubst du: Schießt GTA 6 die Aktie nach oben? Schreib's in die Kommentare!",
        ]),
    "gta5": dict(
        out="GTA5_Die_Legende.mp4", header="GTA 5 · DIE LEGENDE", booms=(0, 2),
        scenes=[g1, g2, g3, g4, g5, g6, g7],
        tags=[None, ("#1 DER START", GOLD), ("#2 WELTREKORD", GOLD), ("#3 VERKÄUFE", GOLD), ("#4 3 GENERATIONEN", GOLD),
              ("#5 GTA ONLINE", CYAN), None],
        highlight={"gta", "5", "6", "legende", "nummer", "1", "2013", "24", "800", "milliarde", "guinness-weltrekord",
                   "235", "ps3", "ps4", "ps5", "online", "quartal", "3"},
        captions=[
            "GTA 6 kommt – aber eins ist klar: GTA 5 ist eine Legende. Und für viele bleibt es die Nummer 1. Hier ist der Beweis!",
            "Am 17. September 2013 erschien GTA 5 und machte in nur 24 Stunden über 800 Millionen Dollar Umsatz.",
            "Nach 3 Tagen war die Milliarde geknackt. Damals war kein Film und kein anderes Entertainment-Produkt schneller – Guinness-Weltrekord!",
            "Heute steht GTA 5 bei fast 235 Millionen verkauften Exemplaren – eines der meistverkauften Spiele aller Zeiten.",
            "Und es hat 3 Konsolen-Generationen überlebt: von PS3 und Xbox 360 über PS4 und Xbox One bis zu PS5 und Xbox Series.",
            "GTA Online läuft seit 2013 mit ständig neuen Updates. Und selbst jetzt verkauft sich GTA 5 noch rund 5 Millionen Mal pro Quartal.",
            "GTA 6 wird vielleicht größer. Aber GTA 5 hat Geschichte geschrieben und bleibt die Legende. Für dich auch die Nummer 1? Schreib's in die Kommentare!",
        ]),
    "geschichte": dict(
        out="GTA_Geschichte_1997-2026.mp4", header="GTA · DIE GESCHICHTE", booms=(0, 5),
        scenes=[h1, h2, h3, h4, h5, h6, h7],
        tags=[None, ("1997 – 1999", CYAN), ("2001 – 2002", ORANGE), ("2004", GREEN), ("2008 – 2013", VIOLET),
              ("2026", PINK), None],
        highlight={"gta", "29", "1997", "1999", "2001", "2004", "2008", "2013", "6", "2", "iii", "iv", "v", "3d",
                   "vice", "city", "liberty", "san", "andreas", "cj", "niko", "bellic", "lucia", "jason", "480", "13"},
        captions=[
            "29 Jahre GTA in einer Minute! Von 1997 bis GTA 6 – los geht's!",
            "1997 startete alles mit Grand Theft Auto – noch von oben und in 2D. 1999 folgte GTA 2.",
            "2001 kam die Revolution: GTA III, zum ersten Mal in 3D, in Liberty City. Ein Jahr später folgte Vice City mit Achtziger-Feeling.",
            "2004 setzte San Andreas neue Maßstäbe – mit 3 Städten und CJ als Hauptfigur.",
            "2008 wurde es mit GTA IV und Niko Bellic düster und realistisch. 2013 kam GTA V – mit gleich 3 Hauptfiguren.",
            "Und jetzt, nach 13 Jahren Warten: GTA 6 – mit Lucia und Jason, zurück in Vice City.",
            "Insgesamt hat sich die Reihe fast 480 Millionen Mal verkauft. Welches GTA ist dein Favorit? Schreib's in die Kommentare!",
        ]),
    "rekorde": dict(
        out="GTA6_Rekorde.mp4", header="GTA 6 · DIE REKORDE", booms=(0, 6),
        scenes=[r1, r2, r3, r4, r5, r6, r7],
        tags=[None, ("#1 TRAILER 1", PINK), ("#2 GUINNESS", GOLD), ("#3 TRAILER 2", CYAN), ("#4 VERGLEICH", PINK),
              ("#5 VORBESTELLUNGEN", GREEN), None],
        highlight={"gta", "6", "5", "rekorde", "rekord", "24", "90", "youtube", "weltrekord", "mrbeast", "3",
                   "guinness-weltrekorde", "likes", "475", "365", "1", "milliarde", "815", "2"},
        captions=[
            "GTA 6 ist noch nicht mal draußen – und hat schon Rekorde gebrochen. Hier sind die krassesten!",
            "Dezember 2023: Der erste Trailer holt in 24 Stunden über 90 Millionen Aufrufe auf YouTube – Weltrekord!",
            "Damit schlug er sogar MrBeast und holte 3 Guinness-Weltrekorde – unter anderem für die meisten Likes.",
            "Mai 2025: Trailer 2 kommt in 24 Stunden auf 475 Millionen Aufrufe – auf allen Plattformen zusammen.",
            "Laut Rockstar der größte Video-Launch aller Zeiten. Zum Vergleich: Der Trailer zu Deadpool und Wolverine schaffte 365 Millionen.",
            "Und die Vorbestellungen? Laut Schätzungen schon rund 1 Milliarde Dollar – bevor das Spiel überhaupt erscheint.",
            "GTA 5 machte am ersten Tag rund 815 Millionen Dollar. Knackt GTA 6 diesen Rekord? Schreib deine Prognose in die Kommentare!",
        ]),
    "vicecity": dict(
        out="Vice_City_2002_vs_2026.mp4", header="VICE CITY · 2002 VS. 2026", booms=(0,),
        scenes=[v1, v2, v3, v4, v5, v6, v7],
        tags=[None, ("#1 DIE ZEIT", OLD), ("#2 DIE HELDEN", OLD), ("#3 DIE MAP", OLD), ("#4 DIE TECHNIK", OLD),
              ("#5 WAS BLEIBT", PINK), None],
        highlight={"vice", "city", "2002", "1986", "gta", "6", "tommy", "vercetti", "lucia", "jason", "2", "leonida",
                   "playstation", "ps5", "xbox", "24", "original", "neue", "sonne", "palmen", "miami-gefühl"},
        captions=[
            "Vice City ist zurück! Aber was hat sich seit dem Original von 2002 verändert? Der große Vergleich!",
            "Die Zeit: Das Original spielte 1986 – mit Neon, Synthpop und Achtziger-Mode. GTA 6 spielt in der Gegenwart.",
            "Die Helden: Damals war Tommy Vercetti allein unterwegs. Heute spielst du zu zweit – als Lucia und Jason.",
            "Die Map: 2002 bestand Vice City aus 2 großen Inseln. In GTA 6 ist die Stadt nur ein Teil des ganzen Bundesstaats Leonida.",
            "Die Technik: Damals PlayStation 2. Heute PS5 und Xbox Series – mit Social Media, vollen Stränden und unglaublich vielen Details.",
            "Was gleich bleibt: Sonne, Strände, Palmen und dieses Miami-Gefühl – nur 24 Jahre später.",
            "Welches Vice City feierst du mehr – das Original oder das neue? Schreib's in die Kommentare und folg für mehr!",
        ]),
}


# ---------------------------------------------------------------- Rendering
_S = {}


def build_timeline(slug):
    cfg = VIDEOS[slug]
    clips, t0, n = [], 0.0, len(cfg["captions"])
    for i in range(n):
        path = os.path.join(SERIE, slug, "voice", f"s{i + 1:02d}.mp3")
        v = load_voice(path)
        dur = len(v) / SR
        sdur = LEAD + dur + TAIL + (END_HOLD if i == n - 1 else 0)
        chunks = chunk_text(cfg["captions"][i])
        times = caption_times(chunks, dur, silences(path, dur))
        clips.append(dict(voice=v, start=t0, dur=dur, sdur=sdur, chunks=chunks, ctimes=times + LEAD))
        t0 += sdur
    return clips, t0


def init_worker(slug):
    cfg = VIDEOS[slug]
    mv.HIGHLIGHT = cfg["highlight"]
    clips, total = build_timeline(slug)
    bg, red = mv.build_backgrounds()
    scenes = []
    for i, fn in enumerate(cfg["scenes"]):
        tag = cfg["tags"][i]
        s = Scene2(i, clips[i]["sdur"], tag[0] if tag else None, tag[1] if tag else CYAN)
        fn(s, clips[i])
        scenes.append(s)
    header = text_img(cfg["header"], font("sb", 28), MUTED)
    _S.update(clips=clips, total=total, bg=bg, red=red, scenes=scenes, header=header)


def render_frame(t):
    clips, scenes = _S["clips"], _S["scenes"]
    n = len(clips)
    i = 0
    while i < n - 1 and t >= clips[i + 1]["start"]:
        i += 1
    c, sc = clips[i], scenes[i]
    st = t - c["start"]
    if sc.bg_mode == "red":
        frame = Image.blend(_S["bg"], _S["red"], 0.55 + 0.45 * math.sin(st * 2 * math.pi * 1.0))
    else:
        frame = _S["bg"].copy()
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


def render_video(slug):
    cfg = VIDEOS[slug]
    init_worker(slug)
    clips, total = _S["clips"], _S["total"]
    nframes = int(math.ceil(total * FPS))
    out = os.path.join(SERIE, slug, cfg["out"])
    print(f"[{slug}] Dauer {total:.2f}s, {nframes} Frames")
    tmp = tempfile.mkdtemp(prefix=f"gta_{slug}_")
    wav = os.path.join(tmp, "mix.wav")
    mv.build_audio(clips, total, wav, booms=cfg["booms"])
    workers = max(1, os.cpu_count() or 1)
    bounds = np.linspace(0, nframes, workers + 1).astype(int)
    jobs = [(int(a), int(b), os.path.join(tmp, f"seg{k}.mp4")) for k, (a, b) in enumerate(zip(bounds, bounds[1:]))]
    with Pool(workers, initializer=init_worker, initargs=(slug,)) as pool:
        parts = pool.map(render_segment, jobs)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{p}'\n" for p in parts)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100", "-c:a", "aac", "-b:a", "192k",
                    "-t", f"{total:.3f}", "-movflags", "+faststart", out], check=True)
    print(f"[{slug}] fertig: {out}")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    slugs = list(VIDEOS) if args[0] == "all" else [args[0]]
    if len(args) > 2 and args[1] == "--preview":
        for slug in slugs:
            init_worker(slug)
            outdir = os.path.join(SERIE, slug, "preview")
            os.makedirs(outdir, exist_ok=True)
            for tok in args[2].split(","):
                render_frame(float(tok)).save(os.path.join(outdir, f"t{float(tok):06.2f}.png"))
            print(slug, "total", round(_S["total"], 2), "starts", [round(c["start"], 2) for c in _S["clips"]])
        return
    for slug in slugs:
        render_video(slug)


if __name__ == "__main__":
    main()
