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


# ---------------------------------------------------------------- Video: Faktencheck
VERDICT = {"ok": (GREEN, "BESTÄTIGT"), "mid": (YELLOW, "BERICHTET"), "no": (RED, "GERÜCHT")}


def vicon(kind, size=70, bg=None):
    col = bg or VERDICT[kind][0]

    def fn(d, k):
        S = size * k
        d.ellipse((0, 0, S - 1, S - 1), fill=c4(col))
        lw = int(S * .12)
        if kind == "ok":
            d.line([(S * .27, S * .53), (S * .44, S * .70), (S * .75, S * .35)], fill=c4(DARK), width=lw, joint="curve")
        elif kind == "no":
            d.line([(S * .32, S * .32), (S * .68, S * .68)], fill=c4(DARK), width=lw)
            d.line([(S * .68, S * .32), (S * .32, S * .68)], fill=c4(DARK), width=lw)
        else:
            d.line([(S * .25, S * .5), (S * .75, S * .5)], fill=c4(DARK), width=lw)
    return ss_shape((size, size), fn)


def stamp(kind, label=None, size=52, rot=-6):
    col, default = VERDICT[kind]
    ic = vicon(kind, int(size * 1.25), bg=WHITE)
    t = text_img(label or default, font("black", size), DARK)
    pad = 24
    w, h = ic.width + t.width + 3 * pad, max(ic.height, t.height) + 30
    im = rrect(w, h, h // 2, c4(col), outline=c4(WHITE), width=5)
    paste(im, ic, pad, (h - ic.height) / 2)
    paste(im, t, 2 * pad + ic.width, (h - t.height) / 2)
    return im.rotate(rot, resample=Image.BICUBIC, expand=True) if rot else im


def picto(name, size=150, color=WHITE):
    """Einfache, eigene Piktogramme."""
    def fn(d, k):
        S = size * k
        lw = max(2, int(S * .07))
        C = c4(color)
        if name == "walk":
            d.ellipse((S * .42, S * .04, S * .6, S * .22), fill=C)
            d.line([(S * .5, S * .26), (S * .46, S * .58)], fill=C, width=lw)
            d.line([(S * .46, S * .58), (S * .32, S * .92)], fill=C, width=lw)
            d.line([(S * .46, S * .58), (S * .64, S * .9)], fill=C, width=lw)
            d.line([(S * .3, S * .44), (S * .5, S * .32), (S * .7, S * .48)], fill=C, width=lw)
        elif name == "car":
            d.rounded_rectangle((S * .06, S * .45, S * .94, S * .72), int(S * .08), fill=C)
            d.polygon([(S * .24, S * .46), (S * .34, S * .26), (S * .66, S * .26), (S * .78, S * .46)], fill=C)
            for cx in (S * .27, S * .73):
                d.ellipse((cx - S * .11, S * .62, cx + S * .11, S * .84), fill=c4(DARK), outline=C, width=lw)
        elif name == "plane":
            d.polygon([(S * .5, S * .04), (S * .56, S * .3), (S * .96, S * .55), (S * .96, S * .62), (S * .56, S * .52),
                       (S * .55, S * .8), (S * .68, S * .9), (S * .68, S * .96), (S * .5, S * .91), (S * .32, S * .96),
                       (S * .32, S * .9), (S * .45, S * .8), (S * .44, S * .52), (S * .04, S * .62), (S * .04, S * .55),
                       (S * .44, S * .3)], fill=C)
        elif name == "fish":
            d.ellipse((S * .12, S * .3, S * .72, S * .7), fill=C)
            d.polygon([(S * .66, S * .5), (S * .94, S * .28), (S * .94, S * .72)], fill=C)
            d.ellipse((S * .24, S * .42, S * .32, S * .5), fill=c4(DARK))
        elif name == "waves":
            for row in range(3):
                y0 = S * (.3 + row * .2)
                pts = [(S * (.06 + u * .88), y0 + math.sin(u * math.pi * 4) * S * .06) for u in np.linspace(0, 1, 30)]
                d.line(pts, fill=C, width=lw, joint="curve")
        elif name == "golf":
            d.line([(S * .4, S * .08), (S * .4, S * .86)], fill=C, width=lw)
            d.polygon([(S * .42, S * .08), (S * .82, S * .22), (S * .42, S * .36)], fill=c4(PINK))
            d.ellipse((S * .18, S * .8, S * .82, S * .96), fill=C)
            d.ellipse((S * .6, S * .66, S * .72, S * .78), fill=C)
        elif name == "dumbbell":
            d.rectangle((S * .2, S * .46, S * .8, S * .54), fill=C)
            for x0 in (S * .08, S * .76):
                d.rounded_rectangle((x0, S * .26, x0 + S * .16, S * .74), int(S * .03), fill=C)
        elif name == "ball":
            d.ellipse((S * .06, S * .06, S * .94, S * .94), fill=c4(ORANGE))
            d.line([(S * .5, S * .06), (S * .5, S * .94)], fill=c4(DARK), width=lw // 2 + 1)
            d.line([(S * .06, S * .5), (S * .94, S * .5)], fill=c4(DARK), width=lw // 2 + 1)
            d.arc((-S * .2, S * .1, S * .5, S * .9), -60, 60, fill=c4(DARK), width=lw // 2 + 1)
            d.arc((S * .5, S * .1, S * 1.2, S * .9), 120, 240, fill=c4(DARK), width=lw // 2 + 1)
        elif name == "eye":
            d.ellipse((S * .04, S * .26, S * .96, S * .74), outline=C, width=lw)
            d.ellipse((S * .36, S * .32, S * .64, S * .68), fill=C)
        elif name == "shirt":
            d.polygon([(S * .32, S * .12), (S * .68, S * .12), (S * .94, S * .3), (S * .82, S * .46), (S * .72, S * .4),
                       (S * .72, S * .9), (S * .28, S * .9), (S * .28, S * .4), (S * .18, S * .46), (S * .06, S * .3)], fill=C)
        elif name == "bubble":
            d.rounded_rectangle((S * .04, S * .1, S * .96, S * .7), int(S * .16), fill=C)
            d.polygon([(S * .22, S * .66), (S * .44, S * .66), (S * .2, S * .9)], fill=C)
        elif name == "pump":
            d.rounded_rectangle((S * .16, S * .1, S * .62, S * .92), int(S * .05), fill=C)
            d.rectangle((S * .24, S * .2, S * .54, S * .38), fill=c4(DARK))
            d.line([(S * .62, S * .3), (S * .8, S * .4), (S * .8, S * .74), (S * .88, S * .8)], fill=C, width=lw,
                   joint="curve")
            d.rectangle((S * .1, S * .88, S * .68, S * .96), fill=C)
        elif name == "magnifier":
            d.ellipse((S * .06, S * .06, S * .66, S * .66), outline=C, width=int(S * .09))
            d.line([(S * .58, S * .58), (S * .92, S * .92)], fill=C, width=int(S * .13))
        elif name == "bag":
            d.rounded_rectangle((S * .12, S * .3, S * .88, S * .92), int(S * .1), fill=C)
            d.arc((S * .3, S * .06, S * .7, S * .5), 180, 360, fill=C, width=lw)
    return ss_shape((size, size), fn)


_MAPCACHE = {}


def small_map(scale=0.6):
    if "img" not in _MAPCACHE:
        mp, _ = mv2.build_map()
        _MAPCACHE["img"] = mp.resize((int(mp.width * scale), int(mp.height * scale)), Image.LANCZOS)
    return _MAPCACHE["img"]


def claim_card(text, kind, sub=None, w=920):
    col = VERDICT[kind][0]
    lines = [(text, "b", 44, WHITE)]
    if sub:
        lines.append((sub, "xb", 32, col))
    return mk_card(lines, w=w, accent=col, icon=vicon(kind, 84), align="left")


def f1(s, c):
    s.add(picto("magnifier", 190, WHITE), W / 2, 270, 0.0, "pop", glow=False)
    add_title(s, "FAKTENCHECK", 500, 0.15, size=150, c1=CYAN, c2=PINK)
    add_text(s, "GTA 6: Was ist echt – was ist Gerücht?", 680, kw(c, "stimmt"), size=46, weight="xb")
    for i, kind in enumerate(("ok", "mid", "no")):
        s.add(stamp(kind, size=32, rot=0), 200 + i * 340, 800, kw(c, "faktencheck") + 0.2 * i, "pop", glow=False)


def f2(s, c):
    s.add(with_alpha(small_map(), 0.85), W / 2, 290, 0.0, "fade", glow=False)
    for i, (name, txt, word) in enumerate([("walk", "178 Min.", "178"), ("car", "35 Min.", "35"),
                                           ("plane", "7 Min.", "flugzeug")]):
        p = panel(320, 180, RED)
        paste_c(p, picto(name, 70), SH + 160, SH + 16)
        ti = text_img(txt, font("black", 56))
        tx, ty = SH + 160 - ti.width / 2, SH + 100
        paste(p, ti, tx, ty)
        ImageDraw.Draw(p).line([(tx - 6, ty + ti.height / 2), (tx + ti.width + 6, ty + ti.height / 2)],
                               fill=c4(RED, 235), width=6)
        s.add_panel(p, 190 + i * 350, 975, kw(c, word), "up")
    s.add(stamp("no", size=64), W / 2, 520, kw(c, "nie"), "pop", glow=False)
    add_text(s, "Keine offiziellen Zeiten · Karte: eigene Illustration", 1165, kw(c, "map"), size=30, weight="m",
             color=MUTED, anim="fade")


def f3(s, c):
    s.add(with_alpha(small_map(), 0.85), W / 2, 290, -5, "fade", glow=False)
    s.add_panel(mk_card([("≈ 2× GTA 5", "black", 84, [WARM, PINK]), ("laut Preview-Berichten", "b", 38, WHITE),
                         ("keine offizielle Zahl von Rockstar", "m", 32, MUTED)], accent=YELLOW), W / 2, 930,
                kw(c, "doppelt"))
    s.add(stamp("mid", size=64), W / 2, 520, kw(c, "berichtet"), "pop", glow=False)


def f4(s, c):
    add_title(s, "NEBENAKTIVITÄTEN", 300, 0.0, size=110, c1=GREEN, c2=CYAN)
    tiles = [("fish", "Angeln", "ok", "angeln"), ("waves", "Jetski", "ok", "jetski"), ("golf", "Minigolf", "ok", "minigolf"),
             ("dumbbell", "Fitnessstudio", "ok", "fitnessstudio"), ("ball", "Basketball", "mid", "basketball"),
             ("waves", "Tauchen · Airboat", "ok", "basketball")]
    for i, (pic, label, kind, word) in enumerate(tiles):
        col = VERDICT[kind][0]
        p = panel(300, 260, col)
        paste_c(p, picto(pic, 120, WHITE), SH + 150, SH + 26)
        lab = text_img(label, fit(label, "b", 38, 270))
        paste_c(p, lab, SH + 150, SH + 160)
        sub = "nur im Trailer" if kind == "mid" else "von Rockstar gezeigt"
        paste_c(p, text_img(sub, font("m", 24), col), SH + 150, SH + 212)
        paste(p, vicon(kind, 54), SH + 236, SH + 12)
        t = kw(c, word) + (0.35 if i == 5 else 0)
        s.add_panel(p, 200 + (i % 3) * 340, 450 + (i // 3) * 300, t, "pop")
    s.add(stamp("ok", size=52), W / 2, 1060, kw(c, "stimmt"), "pop", glow=False)


def f5(s, c):
    add_title(s, "DIE POLIZEI", 300, 0.0, size=130, c1=CYAN, c2=VIOLET)
    rows = [("Verbrechen braucht Zeugen oder Alarm", "ok", "laut Rockstar", "zeugen"),
            ("Cops merken sich dein Outfit", "ok", "laut Rockstar", "outfit"),
            ("4 Stufen bis „Psycho“", "no", "nicht bestätigt", "psycho")]
    for i, (txt, kind, sub, word) in enumerate(rows):
        s.add_panel(claim_card(txt, kind, sub), W / 2, 470 + i * 190, kw(c, word), "left")
    add_text(s, "Quelle: Rockstar North im IGN-Interview (Aug. 2026)", 1060, kw(c, "zeugen") + 0.6, size=30,
             weight="m", color=MUTED, anim="fade")


def f6(s, c):
    bub = picto("bubble", 230, WHITE)
    q = text_img("?", font("black", 120), DARK)
    paste_c(bub, q, 115, 18)
    s.add(bub, W / 2, 270, 0.0, "pop", glow=False)
    add_text(s, "Passanten erinnern sich an dich?", 560, 0.2, size=62, weight="black", maxw=980)
    s.add_panel(mk_card([("nur eine Deutung einer Trailer-Szene", "b", 44, WHITE)], accent=RED), W / 2, 690,
                kw(c, "deutung"))
    s.add(stamp("no", "NICHT BESTÄTIGT", size=56), W / 2, 880, kw(c, "bestätigt"), "pop", glow=False)


def f7(s, c):
    s.add(picto("bag", 170, YELLOW), W / 2, 270, 0.0, "pop", glow=False)
    add_title(s, "GELD & RAUB", 470, 0.1, size=120, c1=YELLOW, c2=ORANGE)
    s.add_panel(claim_card("Läden ausrauben & Beute beim Hehler", "mid", "BERICHTET"), W / 2, 640, kw(c, "ausrauben"),
                "left")
    s.add_panel(claim_card("Bank-, Bar- & Beutegeld-System", "no", "NICHTS OFFIZIELLES"), W / 2, 850,
                kw(c, "geldsystem"), "left")


def f8(s, c):
    s.add(picto("pump", 220, WHITE), W / 2, 270, 0.0, "pop", glow=False)
    add_title(s, "10 SEK. TANKEN?", 540, kw(c, "tanken"), size=120, c1=WARM, c2=PINK)
    s.add_panel(mk_card([("steht nur auf einer einzigen Fan-Seite", "b", 44, WHITE)], accent=RED), W / 2, 720,
                kw(c, "fan-seite"))
    s.add(stamp("no", size=70), W / 2, 900, kw(c, "gerücht"), "pop", glow=False)


def f9(s, c):
    add_title(s, "GLAUB NICHT ALLES!", 320, kw(c, "glaub"), size=110, c1=CYAN, c2=PINK)
    add_text(s, "Ab 19.11. wissen wir's genau", 500, kw(c, "19"), size=60, weight="black")
    s.add(pill("FOLG MIR FÜR ECHTE FAKTEN", PINK, DARK, size=44, padx=40, pady=22), W / 2, 630, kw(c, "folg"), "pop")
    for i, kind in enumerate(("ok", "mid", "no")):
        s.add(stamp(kind, size=30, rot=0), 200 + i * 340, 790, 0.3 + 0.15 * i, "fade", glow=False)
    add_logo(s, W / 2, 900, 0.5, max_w=420, max_h=150)
    disclaimer(s, "Stand: 14.11.2026 · Quellen: Rockstar/IGN, SVG, GTA-6-Tracker",
               "Inoffizielles Fan-Video · alle Grafiken selbst erstellt")


VIDEOS["faktencheck"] = dict(
    out="GTA6_Faktencheck.mp4", header="GTA 6 · FAKTENCHECK", booms=(0,),
    scenes=[f1, f2, f3, f4, f5, f6, f7, f8, f9],
    tags=[None, ("#1 DIE MAP-ZEITEN", RED), ("#2 MAP-GRÖSSE", YELLOW), ("#3 AKTIVITÄTEN", GREEN), ("#4 POLIZEI", CYAN),
          ("#5 NPCs", RED), ("#6 GELD", YELLOW), ("#7 TANKEN", RED), None],
    highlight={"gta-6-fakten", "faktencheck", "178", "35", "7", "rockstar", "map", "gta", "5", "doppelt", "angeln",
               "jetski", "minigolf", "fitnessstudio", "basketball", "zeugen", "alarm", "outfit", "psycho", "bestätigt",
               "gerücht", "berichtet", "hehler", "beutegeld", "10", "19", "fan-seite", "offizielles"},
    captions=[
        "Auf TikTok kursieren gerade jede Menge GTA-6-Fakten. Aber was davon stimmt wirklich? Zeit für den Faktencheck!",
        "Erstens: 178 Minuten zu Fuß, 35 mit dem Auto, 7 mit dem Flugzeug? Diese Zeiten hat Rockstar nie genannt – und die bunten Karten dazu sind keine echte Map.",
        "Was dagegen berichtet wird: Die Map soll etwa doppelt so groß sein wie in GTA 5. Eine offizielle Zahl gibt es aber nicht.",
        "Nebenaktivitäten? Das stimmt! Angeln, Jetski, Minigolf und Fitnessstudio hat Rockstar gezeigt. Basketball sieht man bisher nur im Trailer.",
        "Die Polizei: Laut Rockstar braucht ein Verbrechen Zeugen oder einen Alarm – und die Cops merken sich dein Outfit. 4 Stufen bis „Psycho“? Nicht bestätigt.",
        "Dass sich Passanten an dich erinnern, ist nur eine Deutung einer Trailer-Szene. Auch das ist nicht bestätigt.",
        "Läden ausrauben und Beute beim Hehler verkaufen wird berichtet. Aber ein Geldsystem mit Bank-, Bar- und Beutegeld? Dazu gibt es nichts Offizielles.",
        "Und „Tanken dauert 10 Sekunden“? Das steht nur auf einer einzigen Fan-Seite. Klares Gerücht!",
        "Also: Glaub nicht alles, was du siehst. Ab dem 19. November wissen wir es genau. Folg mir für echte GTA-6-Fakten!",
    ])


# ---------------------------------------------------------------- Video: Die krassesten Gerüchte
def picto2(name, size=150, color=WHITE):
    """Weitere eigene Piktogramme."""
    def fn(d, k):
        S = size * k
        lw = max(2, int(S * .07))
        C = c4(color)
        if name == "flame":
            d.polygon([(S * .5, S * .02), (S * .78, S * .38), (S * .86, S * .66), (S * .7, S * .9), (S * .5, S * .98),
                       (S * .3, S * .9), (S * .14, S * .66), (S * .24, S * .42), (S * .36, S * .52)], fill=c4(ORANGE))
            d.polygon([(S * .5, S * .4), (S * .66, S * .64), (S * .62, S * .86), (S * .5, S * .92), (S * .38, S * .86),
                       (S * .34, S * .68)], fill=c4(YELLOW))
        elif name == "skull":
            d.ellipse((S * .14, S * .06, S * .86, S * .7), fill=C)
            d.rounded_rectangle((S * .3, S * .56, S * .7, S * .9), int(S * .06), fill=C)
            for cx in (S * .36, S * .64):
                d.ellipse((cx - S * .1, S * .3, cx + S * .1, S * .5), fill=c4(DARK))
            d.polygon([(S * .5, S * .52), (S * .45, S * .62), (S * .55, S * .62)], fill=c4(DARK))
        elif name == "shield":
            d.polygon([(S * .5, S * .04), (S * .9, S * .18), (S * .84, S * .62), (S * .5, S * .96), (S * .16, S * .62),
                       (S * .1, S * .18)], fill=C)
            d.line([(S * .3, S * .5), (S * .45, S * .64), (S * .7, S * .36)], fill=c4(DARK), width=lw, joint="curve")
        elif name == "bank":
            d.polygon([(S * .5, S * .06), (S * .94, S * .3), (S * .06, S * .3)], fill=C)
            for x in (S * .18, S * .38, S * .58, S * .78):
                d.rectangle((x - S * .05, S * .36, x + S * .05, S * .78), fill=C)
            d.rectangle((S * .06, S * .82, S * .94, S * .94), fill=C)
        elif name == "wallet":
            d.rounded_rectangle((S * .06, S * .22, S * .94, S * .86), int(S * .1), fill=C)
            d.rounded_rectangle((S * .56, S * .42, S * .98, S * .66), int(S * .06), fill=c4(DARK))
            d.ellipse((S * .66, S * .5, S * .74, S * .58), fill=C)
        elif name == "bolt":
            d.polygon([(S * .58, S * .02), (S * .18, S * .56), (S * .46, S * .56), (S * .38, S * .98), (S * .82, S * .4),
                       (S * .54, S * .4)], fill=c4(YELLOW))
        elif name == "ring":
            d.rectangle((S * .08, S * .58, S * .92, S * .86), fill=C)
            for y in (S * .2, S * .32, S * .44):
                d.line([(S * .12, y), (S * .88, y)], fill=c4(PINK), width=lw // 2 + 1)
            for x in (S * .1, S * .9):
                d.line([(x, S * .12), (x, S * .6)], fill=C, width=lw)
        elif name == "disco":
            d.line([(S * .5, 0), (S * .5, S * .16)], fill=C, width=lw // 2 + 1)
            d.ellipse((S * .14, S * .16, S * .86, S * .88), fill=c4(VIOLET))
            for i in range(1, 4):
                y = S * (.16 + .18 * i)
                d.line([(S * .16, y), (S * .84, y)], fill=c4(WHITE, 160), width=2)
            for i in range(1, 4):
                x = S * (.14 + .18 * i)
                d.line([(x, S * .18), (x, S * .86)], fill=c4(WHITE, 160), width=2)
        elif name == "tv":
            d.rounded_rectangle((S * .06, S * .28, S * .94, S * .86), int(S * .08), fill=C)
            d.rounded_rectangle((S * .14, S * .36, S * .86, S * .78), int(S * .05), fill=c4(CYAN))
            d.line([(S * .5, S * .28), (S * .3, S * .06)], fill=C, width=lw // 2 + 1)
            d.line([(S * .5, S * .28), (S * .7, S * .06)], fill=C, width=lw // 2 + 1)
        elif name == "bed":
            d.rectangle((S * .06, S * .5, S * .94, S * .72), fill=C)
            d.rounded_rectangle((S * .1, S * .36, S * .36, S * .52), int(S * .05), fill=C)
            d.rectangle((S * .06, S * .3, S * .12, S * .9), fill=C)
            d.rectangle((S * .88, S * .5, S * .94, S * .9), fill=C)
    return ss_shape((size, size), fn)


def rumor_tile(pic_img, label, kind, w=230, h=230):
    col = VERDICT[kind][0]
    p = panel(w, h, col)
    paste_c(p, pic_img, SH + w / 2, SH + 22)
    paste_c(p, text_img(label, fit(label, "b", 34, w - 24)), SH + w / 2, SH + 140)
    sub = "gezeigt" if kind == "ok" else "unbestätigt"
    paste_c(p, text_img(sub, font("m", 24), col), SH + w / 2, SH + 188)
    paste(p, vicon(kind, 46), SH + w - 56, SH + 10)
    return p


def rumor_tag(s, n):
    s.add(pill(f"GERÜCHT #{n}", ORANGE, DARK, size=34, padx=28, pady=12), W / 2, 150, 0.0, "down", glow=False)


def q0(s, c):
    s.add(picto2("flame", 170), W / 2, 260, 0.0, "pop", glow=False)
    s.add(pill("VIRAL AUF TIKTOK", ORANGE, DARK, size=36, padx=30, pady=14), W / 2, 450, kw(c, "viral"), "pop")
    add_title(s, "DIE 7 KRASSESTEN", 560, 0.2, size=120, c1=YELLOW, c2=ORANGE)
    add_text(s, "GTA-6-GERÜCHTE", 700, 0.35, size=100, weight="black")
    add_text(s, "…und was wirklich dran ist", 840, kw(c, "dran"), size=48, weight="b", color=MUTED)
    for i in range(7):
        im = ss_shape((80, 80), lambda d, k, i=i: d.ellipse((0, 0, 80 * k - 1, 80 * k - 1), fill=c4(ORANGE)))
        paste_c(im, text_img(str(i + 1), font("black", 44), DARK), 40, 12)
        s.add(im, 140 + i * 133, 960, kw(c, "krassesten") + 0.08 * i, "pop", glow=False)


def q1(s, c):
    rumor_tag(s, 1)
    add_title(s, "MAP DURCHQUEREN", 290, 0.0, size=100, c1=WARM, c2=PINK)
    m = small_map(0.6)
    m = m.resize((int(m.width * 0.78), int(m.height * 0.78)), Image.LANCZOS)
    s.add(m, W / 2, 400, 0.1, "fade", glow=False)
    for i, (name, txt, word) in enumerate([("walk", "~178 Min.", "fuß"), ("car", "~35 Min.", "auto"),
                                           ("plane", "~7 Min.", "flugzeug")]):
        p = panel(320, 170, ORANGE)
        paste_c(p, picto(name, 64), SH + 160, SH + 14)
        paste_c(p, text_img(txt, font("black", 54)), SH + 160, SH + 96)
        s.add_panel(p, 190 + i * 350, 930, kw(c, word), "up")
    s.add(stamp("no", "UNBESTÄTIGT", size=46), W / 2, 1140, kw(c, "offiziell"), "pop", glow=False)


def q2(s, c):
    rumor_tag(s, 2)
    add_title(s, "KRIMINELLES PROFIL", 290, 0.0, size=100, c1=ORANGE, c2=RED)
    steps = [("PROFESSIONELL", GREEN, "shield", 150), ("AGGRESSIV", YELLOW, None, 210), ("GEWALTTÄTIG", ORANGE, "skull", 270),
             ("PSYCHO", RED, "skull", 330)]
    t0, t1 = kw(c, "stufen"), kw(c, "psycho")
    base = 900
    for i, (name, col, ic, hgt) in enumerate(steps):
        t = t0 + (t1 - t0) * i / 3
        x = 70 + i * 240
        bar = rrect(220, hgt, 22, c4(col))
        paste_c(bar, text_img(str(i + 1), font("black", 90), DARK), 110, 30)
        s.add(bar, x + 110, base - hgt, t, "up", glow=False)
        icon = picto2(ic, 90, col) if ic else bang_icon(col, 90)
        s.add(icon, x + 110, base - hgt - 106, t + 0.15, "pop", glow=False)
        s.add(text_img(name, fit(name, "xb", 30, 226), col), x + 110, base + 14, t + 0.1, "fade")
    s.add_panel(mk_card([("4 Stufen: unbestätigt", "xb", 42, RED),
                         ("Bestätigt: Polizei braucht Zeugen & merkt sich dein Outfit", "b", 32, GREEN)],
                        accent=YELLOW, icon=vicon("mid", 84), align="left"), W / 2, 1000, kw(c, "bestätigt"))


def q3(s, c):
    rumor_tag(s, 3)
    bub = picto("bubble", 240, WHITE)
    paste_c(bub, text_img("!", font("black", 130), DARK), 120, 14)
    s.add(bub, W / 2, 270, 0.0, "pop", glow=False)
    add_text(s, "Passanten erinnern sich an dich", 570, 0.2, size=62, weight="black", maxw=990)
    s.add_panel(mk_card([("…und reagieren auf frühere Begegnungen", "b", 44, WHITE)], accent=ORANGE), W / 2, 700,
                kw(c, "begegnungen"))
    s.add(stamp("no", "NUR EINE TRAILER-SZENE", size=46), W / 2, 900, kw(c, "trailer"), "pop", glow=False)


def q4(s, c):
    rumor_tag(s, 4)
    s.add(picto("bag", 180, YELLOW), W / 2, 270, 0.0, "pop", glow=False)
    add_text(s, "JEDEN LADEN AUSRAUBEN?", 480, kw(c, "jeden"), size=80, weight="black", color=YELLOW, maxw=990)
    s.add_panel(claim_card("Läden ausrauben & Beute beim Hehler", "mid", "WIRD BERICHTET"), W / 2, 640, kw(c, "hehler"),
                "left")
    s.add_panel(claim_card("Wirklich jeder einzelne Laden?", "no", "OFFEN"), W / 2, 850, kw(c, "offen"), "left")


def q5(s, c):
    rumor_tag(s, 5)
    add_title(s, "NEUES GELDSYSTEM?", 290, 0.0, size=110, c1=GREEN, c2=YELLOW)
    rows = [("bank", "BANKGELD", "sicher", VIOLET, "bankgeld"), ("wallet", "BARGELD", "kannst du verlieren", GREEN, "bargeld"),
            ("bag", "BEUTEGELD", "muss erst gewaschen werden", RED, "beutegeld")]
    for i, (ic, name, desc, col, word) in enumerate(rows):
        icon = picto2(ic, 100, col) if ic != "bag" else picto("bag", 100, col)
        p = mk_card([(name, "black", 56, col), (desc, "b", 38, WHITE)], accent=col, icon=icon, align="left")
        s.add_panel(p, W / 2, 440 + i * 190, kw(c, word), "left")
    s.add(stamp("no", "UNBESTÄTIGT", size=50), W / 2, 1020, kw(c, "unbestätigt"), "pop", glow=False)


def q6(s, c):
    rumor_tag(s, 6)
    s.add(picto("pump", 200, WHITE), W / 2 - 130, 270, 0.0, "pop", glow=False)
    s.add(picto2("bolt", 200), W / 2 + 130, 270, 0.2, "pop", glow=False)
    add_title(s, "TANKEN WIRD WICHTIG", 510, 0.1, size=96, c1=WARM, c2=PINK)
    s.add_panel(mk_card([("Verbrenner tanken · E-Autos laden", "b", 44, WHITE)], accent=ORANGE), W / 2, 650,
                kw(c, "verbrenner"))
    add_title(s, "~10 SEK.", 800, kw(c, "10"), size=130, c1=YELLOW, c2=ORANGE)
    s.add(stamp("no", "NUR 1 FAN-SEITE", size=48), W / 2, 980, kw(c, "fan-seite"), "pop", glow=False)


def q7(s, c):
    rumor_tag(s, 7)
    add_title(s, "16+ AKTIVITÄTEN?", 290, 0.0, size=110, c1=GREEN, c2=CYAN)
    tiles = [(picto2("ring", 100), "Wrestling", "mid", "wrestling"), (picto2("disco", 100), "Nachtclubs", "mid", "wrestling"),
             (picto2("tv", 100), "TV", "mid", "wrestling"), (picto2("bed", 100), "Schlafen", "mid", "wrestling"),
             (picto("fish", 100), "Angeln", "ok", "angeln"), (picto("waves", 100), "Jetski", "ok", "jetski"),
             (picto("golf", 100), "Minigolf", "ok", "minigolf"), (picto("dumbbell", 100), "Fitness", "ok", "fitnessstudio")]
    for i, (pic, label, kind, word) in enumerate(tiles):
        t = kw(c, word) + (0.15 * i if i < 4 else 0)
        s.add_panel(rumor_tile(pic, label, kind), 165 + (i % 4) * 250, 440 + (i // 4) * 290, t, "pop")
    s.add(stamp("mid", "TEILWEISE WAHR", size=50), W / 2, 1040, kw(c, "teilweise"), "pop", glow=False)


def q8(s, c):
    add_text(s, "Welches Gerücht soll stimmen?", 300, kw(c, "gerücht"), size=64, weight="black", maxw=990)
    names = ["Riesen-Map", "Krimi-Profil", "NPC-Gedächtnis", "Jeder Laden", "Geldsystem", "Tanken", "16+ Aktivitäten"]
    for i, n in enumerate(names):
        p = pill(f"{i + 1}  {n}", ORANGE if i % 2 == 0 else YELLOW, DARK, size=34, padx=26, pady=14)
        s.add(p, 290 + (i % 2) * 500, 420 + (i // 2) * 95, kw(c, "gerücht") + 0.1 * i, "pop", glow=False)
    add_text(s, "Schreib's in die Kommentare!", 820, kw(c, "kommentare"), size=48, weight="sb", color=MUTED)
    s.add(pill("FOLG MIR FÜR MEHR", PINK, DARK, size=44, padx=40, pady=22), W / 2, 920, kw(c, "folg"), "pop")
    disclaimer(s, "Gerüchte = unbestätigt · Stand: 14.11.2026", "Inoffizielles Fan-Video · alle Grafiken selbst erstellt")


VIDEOS["geruechte"] = dict(
    out="GTA6_Die_krassesten_Geruechte.mp4", header="GTA 6 · DIE KRASSESTEN GERÜCHTE", booms=(0,),
    scenes=[q0, q1, q2, q3, q4, q5, q6, q7, q8],
    tags=[None] * 9,
    highlight={"gta-6-gerüchte", "viral", "krassesten", "gerücht", "1", "2", "3", "4", "5", "6", "7", "map", "35",
               "psycho", "bestätigt", "zeugen", "outfit", "trailer", "laden", "hehler", "bankgeld", "bargeld",
               "beutegeld", "unbestätigt", "10", "fan-seite", "16", "wrestling", "fallschirmspringen", "angeln",
               "jetski", "minigolf", "fitnessstudio", "19"},
    captions=[
        "Diese GTA-6-Gerüchte gehen gerade auf TikTok viral! Ich zeig dir die krassesten – und was wirklich dran ist.",
        "Gerücht Nummer 1: Die Map ist so riesig, dass du zu Fuß fast 3 Stunden brauchst. Mit dem Auto etwa 35 Minuten, mit dem Flugzeug 7. Offiziell bestätigt ist davon aber nichts.",
        "Gerücht Nummer 2: Dein Verhalten bestimmt dein kriminelles Profil – in 4 Stufen, von professionell bis Psycho. Bestätigt ist nur: Die Polizei braucht Zeugen und merkt sich dein Outfit.",
        "Gerücht Nummer 3: Passanten sollen sich an dich erinnern und auf frühere Begegnungen reagieren. Das basiert aber nur auf einer Szene aus dem Trailer.",
        "Gerücht Nummer 4: Du kannst jeden einzelnen Laden ausrauben. Läden ausrauben und Beute beim Hehler verkaufen wird tatsächlich berichtet – ob wirklich jeder Laden geht, ist offen.",
        "Gerücht Nummer 5: ein neues Geldsystem. Bankgeld ist sicher, Bargeld kannst du verlieren, und Beutegeld musst du erst waschen. Klingt stark – ist aber unbestätigt.",
        "Gerücht Nummer 6: Tanken wird endlich wichtig. Verbrenner müssen tanken, E-Autos laden, ein Tankstopp dauert etwa 10 Sekunden. Quelle: nur eine Fan-Seite.",
        "Gerücht Nummer 7: über 16 Aktivitäten – vom Wrestling bis zum Fallschirmspringen. Teilweise stimmt's: Angeln, Jetski, Minigolf und Fitnessstudio hat Rockstar gezeigt.",
        "Welches Gerücht soll unbedingt stimmen? Schreib's in die Kommentare – am 19. November wissen wir es. Folg mir, damit du nichts verpasst!",
    ])


# ---------------------------------------------------------------- Video: GTA 6 Online & PC
def picto3(name, size=150, color=WHITE):
    def fn(d, k):
        S = size * k
        lw = max(2, int(S * .07))
        C = c4(color)
        if name == "pad":
            d.rounded_rectangle((S * .06, S * .3, S * .94, S * .74), int(S * .2), fill=C)
            d.rectangle((S * .2, S * .47, S * .36, S * .53), fill=c4(DARK))
            d.rectangle((S * .25, S * .42, S * .31, S * .58), fill=c4(DARK))
            for cx, cy in ((S * .68, S * .44), (S * .78, S * .54)):
                d.ellipse((cx - S * .05, cy - S * .05, cx + S * .05, cy + S * .05), fill=c4(DARK))
        elif name == "monitor":
            d.rounded_rectangle((S * .04, S * .1, S * .96, S * .7), int(S * .05), fill=C)
            d.rectangle((S * .1, S * .16, S * .9, S * .64), fill=c4(DARK))
            d.polygon([(S * .42, S * .7), (S * .58, S * .7), (S * .64, S * .86), (S * .36, S * .86)], fill=C)
            d.rounded_rectangle((S * .26, S * .86, S * .74, S * .93), int(S * .03), fill=C)
        elif name == "globe":
            d.ellipse((S * .06, S * .06, S * .94, S * .94), outline=C, width=lw)
            d.ellipse((S * .3, S * .06, S * .7, S * .94), outline=C, width=lw // 2 + 1)
            d.line([(S * .06, S * .5), (S * .94, S * .5)], fill=C, width=lw // 2 + 1)
            d.arc((S * .12, S * .1, S * .88, S * .5), 200, 340, fill=C, width=lw // 2 + 1)
            d.arc((S * .12, S * .5, S * .88, S * .9), 20, 160, fill=C, width=lw // 2 + 1)
        elif name == "group":
            for cx, s_ in ((S * .25, .8), (S * .75, .8), (S * .5, 1.0)):
                r = S * .12 * s_
                d.ellipse((cx - r, S * .3 - r, cx + r, S * .3 + r), fill=C)
                d.pieslice((cx - r * 2, S * .5, cx + r * 2, S * .5 + r * 4), 180, 360, fill=C)
    return ss_shape((size, size), fn)


def hbars(s, title, rows, y0, vmax, wmax=450, x0=360, unit_fmt=None):
    """rows: [(label, value|None, value_text, color, t)]"""
    add_text(s, title, y0, rows[0][4] - 0.2, size=40, weight="sb", color=MUTED, anim="fade")
    for i, (label, val, vtxt, col, t) in enumerate(rows):
        y = y0 + 90 + i * 140
        s.add(text_img(label, fit(label, "xb", 46, 290)), 60, y + 8, t, "left", center=False)
        if val is None:
            ghost = rrect(wmax, 70, 35, c4((90, 92, 130), 120), outline=c4(MUTED, 200), width=3)
            s.add(ghost, x0, y, t, "fade", center=False, glow=False)
            s.add(text_img("???", font("black", 52), YELLOW), x0 + wmax / 2 - 50, y + 4, t + 0.3, "pop", center=False)
        else:
            frac = max(0.02, val / vmax)
            s.dyn.append(bar_fn(x0, y, wmax, 70, frac, col, t))
            s.add(text_img(vtxt, font("black", 40), col), x0 + max(70, int(wmax * frac)) + 16, y + 10, t + 0.9,
                  "fade", center=False)


def o1(s, c):
    s.add(picto3("pad", 190), W / 2 - 150, 270, 0.0, "pop", glow=False)
    s.add(picto3("monitor", 190), W / 2 + 150, 270, 0.15, "pop", glow=False)
    add_title(s, "ONLINE & PC", 500, 0.2, size=160, c1=CYAN, c2=PINK)
    add_text(s, "Wann kommt was?", 690, kw(c, "beides"), size=64, weight="black")
    s.add(pill("19.11.2026 · nur PS5 & Xbox", CYAN, DARK, size=38, padx=30, pady=16), W / 2, 820, kw(c, "konsole"), "pop")
    s.add(stamp("no", "OHNE ONLINE-MODUS", size=40), W / 2, 940, kw(c, "online-modus"), "pop", glow=False)


def o2(s, c):
    s.add(picto3("globe", 180), W / 2, 310, 0.0, "pop", glow=False)
    add_title(s, "GTA 6 ONLINE", 520, 0.15, size=140, c1=CYAN, c2=GREEN)
    s.add(stamp("no", "NICHT ANGEKÜNDIGT", size=50), W / 2, 700, kw(c, "angekündigt"), "pop", glow=False)
    s.add_panel(claim_card("Zum Release: nur Singleplayer", "ok", "LAUT ROCKSTAR"), W / 2, 880,
                kw(c, "singleplayer-erlebnis"), "up")


def o3(s, c):
    add_title(s, "SO WAR'S BEI GTA 5", 300, 0.0, size=110, c1=GOLD, c2=ORANGE)
    t1, t2 = kw(c, "september"), kw(c, "wochen")
    x0, x1, y = 190, 890, 640
    s.add(rrect(x1 - x0, 16, 8, c4((80, 82, 120))), x0, y - 8, t1, "fade", center=False, glow=False)
    s.dyn.append(bar_fn(x0, y - 8, x1 - x0, 16, 1.0, GOLD, t1 + 0.3, dur=max(0.6, t2 - t1)))
    for x, date, name, t, col in ((x0, "17.09.2013", "GTA 5", t1, GOLD), (x1, "01.10.2013", "GTA Online", t2, CYAN)):
        dot = ss_shape((60, 60), lambda d, k, col=col: d.ellipse((0, 0, 60 * k - 1, 60 * k - 1), fill=c4(col)))
        s.add(dot, x, y - 30, t, "pop", glow=False)
        s.add(text_img(date, font("xb", 40), col), x, y + 50, t, "up")
        s.add(text_img(name, font("black", 52)), x, y - 130, t, "down")
    add_title(s, "NUR 14 TAGE", 780, t2 + 0.2, size=120, c1=CYAN, c2=GREEN)


def o4(s, c):
    add_title(s, "ONLINE NACH RELEASE", 300, 0.0, size=96, c1=CYAN, c2=PINK)
    hbars(s, "Tage bis zum Online-Modus", [
        ("GTA IV", 0.6, "zum Start", GREEN, kw(c, "multiplayer")),
        ("GTA V", 14, "14 Tage", GOLD, 0.3),
        ("RDR 2", 32, "~1 Monat", ORANGE, kw(c, "red dead")),
        ("GTA VI", None, "", PINK, kw(c, "multiplayer") + 0.8)], 430, vmax=32)


def o5(s, c):
    add_text(s, "GTA 6 ONLINE", 320, 0.0, size=56, weight="sb", color=MUTED, anim="fade")
    add_title(s, "2027?", 400, kw(c, "2027"), size=300, c1=CYAN, c2=PINK)
    s.add_panel(mk_card([("laut Berichten (u. a. Bloomberg)", "b", 44, WHITE)], accent=YELLOW), W / 2, 760,
                kw(c, "berichten"))
    s.add(stamp("mid", "NICHT BESTÄTIGT", size=50), W / 2, 950, kw(c, "bestätigt"), "pop", glow=False)


def o6(s, c):
    s.add(picto3("group", 180), W / 2, 310, 0.0, "pop", glow=False)
    add_title(s, "ROLEPLAY?", 510, kw(c, "aussehen"), size=150, c1=VIOLET, c2=PINK)
    s.add_panel(claim_card("2023: Rockstar übernimmt das FiveM-Team", "ok", "FAKT"), W / 2, 700, kw(c, "fivem"), "left")
    s.add_panel(claim_card("Roleplay in GTA 6 Online", "mid", "SPEKULATION"), W / 2, 890, kw(c, "spekulation"), "left")


def o7(s, c):
    add_title(s, "DAS ALTE GTA ONLINE", 300, 0.0, size=100, c1=GREEN, c2=CYAN)
    for i, (txt, word) in enumerate([("läuft weiter", "läuft"), ("bekommt weiter Updates", "updates"),
                                     ("kein Ende angekündigt", "ende")]):
        s.add_panel(claim_card(txt, "ok"), W / 2, 470 + i * 170, kw(c, word), "left")


def o8(s, c):
    s.add(picto3("monitor", 130), W / 2, 305, 0.0, "pop", glow=False)
    add_title(s, "PC-SPIELER, AUFGEPASST!", 460, kw(c, "pc-spielern"), size=90, c1=CYAN, c2=VIOLET)
    hbars(s, "Monate bis zur PC-Version", [
        ("GTA IV", 7, "7 Monate", GREEN, kw(c, "gta 4")),
        ("RDR 2", 12, "1 Jahr", ORANGE, kw(c, "red dead")),
        ("GTA V", 19, "19 Monate", RED, kw(c, "19"))], 590, vmax=19)


def o9(s, c):
    mon = picto3("monitor", 220)
    paste_c(mon, text_img("?", font("black", 110), YELLOW), 110, 30)
    s.add(mon, W / 2, 305, 0.0, "pop", glow=False)
    add_title(s, "GTA 6 AUF PC?", 545, 0.15, size=130, c1=CYAN, c2=PINK)
    s.add(stamp("no", "NICHT ANGEKÜNDIGT", size=48), W / 2, 715, kw(c, "angekündigt"), "pop", glow=False)
    s.add_panel(claim_card("Bericht: Anfang 2027", "mid", "VON ROCKSTAR UNBESTÄTIGT"), W / 2, 895, kw(c, "2027"),
                "left")


def o10(s, c):
    add_title(s, "MEIN FAZIT", 300, kw(c, "fazit"), size=130, c1=CYAN, c2=PINK)
    s.add_panel(claim_card("Online: wohl 2027", "mid", "PROGNOSE"), W / 2, 470, kw(c, "online"), "left")
    s.add_panel(claim_card("PC: nach der Konsolen-Version", "mid", "PROGNOSE"), W / 2, 640, kw(c, "release"), "left")
    add_text(s, "Wann rechnest du damit?", 830, kw(c, "rechnest"), size=58, weight="black")
    add_text(s, "Schreib's in die Kommentare!", 915, kw(c, "kommentare"), size=44, weight="sb", color=MUTED)
    s.add(pill("FOLG MIR FÜR UPDATES", PINK, DARK, size=44, padx=40, pady=22), W / 2, 1010, kw(c, "folg"), "pop")
    disclaimer(s, "Stand: 14.11.2026 · Quellen: Rockstar, Take-Two, Bloomberg, GamesBeat",
               "Inoffizielles Fan-Video · Prognosen ohne Gewähr")


VIDEOS["online"] = dict(
    out="GTA6_Online_und_PC.mp4", header="GTA 6 · ONLINE & PC", booms=(0, 7),
    scenes=[o1, o2, o3, o4, o5, o6, o7, o8, o9, o10],
    tags=[None, ("#1 STATUS ONLINE", CYAN), ("#2 RÜCKBLICK", GOLD), ("#3 VERGLEICH", PINK), ("#4 PROGNOSE", YELLOW),
          ("#5 ROLEPLAY", VIOLET), ("#6 GTA ONLINE", GREEN), ("#7 PC-HISTORIE", CYAN), ("#8 PC-STATUS", RED), None],
    highlight={"gta", "6", "5", "4", "online-modus", "online", "19", "konsole", "pc-version", "singleplayer-erlebnis",
               "2013", "2", "wochen", "1", "monat", "multiplayer", "2027", "fivem", "roleplay", "spekulation",
               "updates", "pc-spielern", "7", "monaten", "jahr", "fazit"},
    captions=[
        "GTA 6 kommt am 19. November – aber nur für Konsole und ohne Online-Modus. Wann kommt beides? Wir schauen in die Geschichte!",
        "Ein Online-Modus ist offiziell noch nicht angekündigt. Rockstar beschreibt GTA 6 zum Release als Singleplayer-Erlebnis.",
        "Ein Blick zurück: GTA 5 erschien im September 2013 – und GTA Online kam nur 2 Wochen später.",
        "Bei Red Dead Redemption 2 dauerte es rund 1 Monat bis zur Online-Beta. GTA 4 hatte den Multiplayer sogar direkt zum Start.",
        "Bei GTA 6 wird es wohl länger dauern: Berichten zufolge wird der Online-Modus erst 2027 erwartet. Bestätigt ist das aber nicht.",
        "Und wie könnte GTA 6 Online aussehen? Rockstar hat 2023 das Team hinter FiveM übernommen – viele hoffen deshalb auf Roleplay. Das ist aber noch Spekulation.",
        "Das alte GTA Online läuft übrigens weiter und bekommt weiter Updates. Ein Ende ist nicht angekündigt.",
        "Jetzt zu euch PC-Spielern! Die PC-Version kam bei Rockstar immer später: GTA 4 nach 7 Monaten, Red Dead 2 nach 1 Jahr, GTA 5 sogar erst nach 19 Monaten.",
        "Für GTA 6 ist noch keine PC-Version angekündigt. Ein Bericht spricht von Anfang 2027 – Rockstar hat das aber nicht bestätigt.",
        "Mein Fazit: Online und PC kommen sehr wahrscheinlich – nur nicht zum Release. Wann rechnest du damit? Schreib's in die Kommentare und folg mir für Updates!",
    ])


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
