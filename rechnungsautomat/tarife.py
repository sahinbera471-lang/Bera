"""Preisliste, Feiertage und Aufteilung einer Schicht in Tarif-Kategorien."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

KATEGORIEN = ("normal", "nacht", "sonntag", "feiertag")
KATEGORIE_TEXT = {
    "normal": "Stundensatz",
    "nacht": "Nachttarif",
    "sonntag": "Sonntagstarif",
    "feiertag": "Feiertagstarif",
}

CENT = Decimal("0.01")


def geld(wert) -> Decimal:
    return Decimal(wert).quantize(CENT, rounding=ROUND_HALF_UP)


def ostersonntag(jahr: int) -> date:
    # Anonymer Gregorianischer Algorithmus (Meeus/Jones/Butcher)
    a = jahr % 19
    b, c = divmod(jahr, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    monat, tag = divmod(h + l - 7 * m + 114, 31)
    return date(jahr, monat, tag + 1)


def feiertage(jahr: int, land: str = "NW") -> dict[date, str]:
    ostern = ostersonntag(jahr)
    tage = {
        date(jahr, 1, 1): "Neujahr",
        ostern - timedelta(days=2): "Karfreitag",
        ostern + timedelta(days=1): "Ostermontag",
        date(jahr, 5, 1): "Tag der Arbeit",
        ostern + timedelta(days=39): "Christi Himmelfahrt",
        ostern + timedelta(days=50): "Pfingstmontag",
        date(jahr, 10, 3): "Tag der Deutschen Einheit",
        date(jahr, 12, 25): "1. Weihnachtstag",
        date(jahr, 12, 26): "2. Weihnachtstag",
    }
    if land in ("NW", "BW", "BY", "HE", "RP", "SL"):
        tage[ostern + timedelta(days=60)] = "Fronleichnam"
    if land in ("NW", "BW", "BY", "RP", "SL"):
        tage[date(jahr, 11, 1)] = "Allerheiligen"
    if land in ("BB", "MV", "SN", "ST", "TH", "HB", "HH", "NI", "SH"):
        tage[date(jahr, 10, 31)] = "Reformationstag"
    return tage


def _uhrzeit(text: str) -> time:
    h, m = text.split(":")
    return time(int(h), int(m))


def kategorie(ts: datetime, nacht_von: time, nacht_bis: time, ft: dict[date, str]) -> str:
    if ts.date() in ft:
        return "feiertag"
    if ts.weekday() == 6:
        return "sonntag"
    t = ts.time()
    if t >= nacht_von or t < nacht_bis:
        return "nacht"
    return "normal"


def segmente(start: datetime, ende: datetime, preisliste: dict, land: str) -> list[list]:
    """Zerlegt die Schicht in Zeitfenster gleicher Kategorie: [kategorie, von, bis, minuten].
    Vorrang: Feiertag > Sonntag > Nacht > Normal."""
    nacht_von = _uhrzeit(preisliste["nachtfenster"]["von"])
    nacht_bis = _uhrzeit(preisliste["nachtfenster"]["bis"])
    ft = {}
    for jahr in range(start.year, ende.year + 1):
        ft.update(feiertage(jahr, land))
    teile: list[list] = []
    ts = start
    while ts < ende:
        kat = kategorie(ts, nacht_von, nacht_bis, ft)
        if teile and teile[-1][0] == kat:
            teile[-1][2] = ts + timedelta(minutes=1)
            teile[-1][3] += 1
        else:
            teile.append([kat, ts, ts + timedelta(minutes=1), 1])
        ts += timedelta(minutes=1)
    return teile


def pause_abziehen(teile: list[list], pause: int) -> list[list]:
    """Pause anteilig auf die Zeitfenster verteilen (Lage der Pause steht nicht im Bericht)."""
    gesamt = sum(t[3] for t in teile)
    ergebnis = [list(t) for t in teile]
    if pause <= 0 or gesamt == 0:
        return ergebnis
    pause = min(pause, gesamt)
    anteile = [t[3] * pause / gesamt for t in teile]
    abzug = [int(a) for a in anteile]
    rest = pause - sum(abzug)
    for i in sorted(range(len(teile)), key=lambda i: anteile[i] - abzug[i], reverse=True)[:rest]:
        abzug[i] += 1
    for t, a in zip(ergebnis, abzug):
        t[3] -= a
    return ergebnis


def summen(teile: list[list]) -> dict[str, int]:
    """Minuten je Kategorie in der Reihenfolge des ersten Auftretens."""
    ergebnis: dict[str, int] = {}
    for kat, _, _, minuten in teile:
        ergebnis[kat] = ergebnis.get(kat, 0) + minuten
    return ergebnis


def uhr(ts: datetime, ist_ende: bool = False) -> str:
    return "24:00" if ist_ende and ts.hour == 0 and ts.minute == 0 else ts.strftime("%H:%M")


def satz(preisliste: dict, rolle: str, kat: str, km: int | None) -> Decimal:
    spalte = "ab_100km" if km is not None and km >= 100 else "bis_100km"
    return Decimal(str(preisliste["rollen"][rolle][kat][spalte]))


def anfahrt(preisliste: dict, km: int | None) -> Decimal:
    if km is None:
        return Decimal("0")
    for stufe in preisliste["anfahrt"]:
        if km >= stufe["ab_km"] and (stufe["bis_km"] is None or km < stufe["bis_km"]):
            return Decimal(str(stufe["preis"]))
    return Decimal("0")
