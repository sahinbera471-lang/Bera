#!/usr/bin/env python3
"""Lohn ST – Zuschlagsstunden aus einer Excel-Monatsübersicht.

Liest eine Excel-Datei mit einer Monatsübersicht (eine Zeile pro Tag) und
schreibt eine neue Excel-Datei, die nur noch die Stunden je Zuschlagsart
enthält. Siehe ../SKILL.md und ../references/zuschlaege.md.
"""

import argparse
import datetime as dt
import json
import re
import sys
from collections import OrderedDict

try:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
except ImportError:  # pragma: no cover
    sys.exit("openpyxl fehlt – bitte 'pip install openpyxl' ausführen.")

HEADER_SCAN_ROWS = 40
EXCEL_EPOCH = dt.datetime(1899, 12, 30)

MONATE = {
    "januar": 1, "jan": 1, "februar": 2, "feb": 2, "märz": 3, "maerz": 3,
    "mrz": 3, "april": 4, "apr": 4, "mai": 5, "juni": 6, "jun": 6, "juli": 7,
    "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "november": 11, "nov": 11, "dezember": 12,
    "dez": 12,
}
MONATSNAMEN = ["", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
               "August", "September", "Oktober", "November", "Dezember"]

# Zuschlagsspalten: (Schlüsselwort, Standardsatz) – Reihenfolge = Priorität
ZUSCHLAG_KEYWORDS = [
    ("nacht", None), ("sonntag", "50 %"), ("sonn", "50 %"),
    ("feiertag", "125 %"), ("samstag", None), ("überstund", None),
    ("ueberstund", None), ("mehrarbeit", None), ("spät", None),
    ("spaet", None), ("heiligabend", None), ("silvester", None),
    ("zuschlag", None), ("%", None),
]
SUMMENZEILE = re.compile(r"\b(summe|gesamt|total|übertrag|uebertrag|jahr \d{4})\b", re.I)
GELD = re.compile(r"€|\b(eur|euro|betrag|lohn|grundlohn)\b|kosten(?! *\(std)|verpflegung", re.I)
# hübschere Bezeichnungen für typische Spaltenköpfe
LABELS = [("nacht", "Nachtarbeit"), ("sonntag", "Sonntagsarbeit"), ("feiertag", "Feiertagsarbeit"),
          ("samstag", "Samstagsarbeit"), ("überstund", "Überstunden"), ("mehrarbeit", "Mehrarbeit")]


# --------------------------------------------------------------------------
# Hilfsfunktionen: Werte lesen
# --------------------------------------------------------------------------

def norm(text):
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", str(text or ""))  # "Über-\nstunden"
    return re.sub(r"\s+", " ", text).strip().lower()


def to_hours(value, number_format=""):
    """Wandelt einen Zellwert in Dezimalstunden um (None, wenn kein Wert)."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.timedelta):
        return value.total_seconds() / 3600
    if isinstance(value, dt.datetime):
        # [h]:mm-Werte > 24 h kommen als Datum ab 1899-12-30 an
        return (value - EXCEL_EPOCH).total_seconds() / 3600
    if isinstance(value, dt.time):
        return value.hour + value.minute / 60 + value.second / 3600
    if isinstance(value, (int, float)):
        fmt = (number_format or "").lower()
        if "h" in fmt and ("mm" in fmt or ":" in fmt):
            return float(value) * 24
        return float(value)
    text = str(value).strip().lower().replace("std", "").replace("h", "").strip()
    m = re.fullmatch(r"(-?\d+):(\d{1,2})(?::\d{2})?", text)
    if m:
        sign = -1 if m.group(1).startswith("-") else 1
        return sign * (abs(int(m.group(1))) + int(m.group(2)) / 60)
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def to_time(value):
    """Uhrzeit (Beginn/Ende/Pause) -> Minuten seit 0 Uhr, oder None."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.hour * 60 + value.minute
    if isinstance(value, dt.time):
        return value.hour * 60 + value.minute
    if isinstance(value, dt.timedelta):
        return round(value.total_seconds() / 60)
    if isinstance(value, (int, float)):
        if 0 <= value < 1:  # Excel-Bruchteil eines Tages
            return round(value * 24 * 60)
        if 0 <= value <= 24:  # z. B. 22 oder 22.5
            return round(value * 60)
        return None
    m = re.search(r"(\d{1,2})[:.](\d{2})", str(value))
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


def to_date(value, year=None, month=None):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, (int, float)) and year and month:
        if 1 <= int(value) <= 31 and int(value) == value:
            try:
                return dt.date(year, month, int(value))
            except ValueError:
                return None
    if isinstance(value, str):
        m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})?", value)
        if m:
            d, mo = int(m.group(1)), int(m.group(2))
            y = m.group(3)
            y = (int(y) + 2000 if len(y) == 2 else int(y)) if y else year
            if y:
                try:
                    return dt.date(y, mo, d)
                except ValueError:
                    return None
        m = re.fullmatch(r"\s*(\d{1,2})\.?\s*", value)
        if m and year and month:
            try:
                return dt.date(year, month, int(m.group(1)))
            except ValueError:
                return None
    return None


# --------------------------------------------------------------------------
# Feiertage
# --------------------------------------------------------------------------

def ostersonntag(year):
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day)


def feiertage(year, land=None):
    """{datum: name} der gesetzlichen Feiertage."""
    o = ostersonntag(year)
    td = dt.timedelta
    f = {
        dt.date(year, 1, 1): "Neujahr",
        o - td(days=2): "Karfreitag",
        o + td(days=1): "Ostermontag",
        dt.date(year, 5, 1): "Tag der Arbeit",
        o + td(days=39): "Christi Himmelfahrt",
        o + td(days=50): "Pfingstmontag",
        dt.date(year, 10, 3): "Tag der Deutschen Einheit",
        dt.date(year, 12, 25): "1. Weihnachtstag",
        dt.date(year, 12, 26): "2. Weihnachtstag",
    }
    land = (land or "").upper()
    if land in ("BW", "BY", "ST"):
        f[dt.date(year, 1, 6)] = "Heilige Drei Könige"
    if land in ("BE", "MV"):
        f[dt.date(year, 3, 8)] = "Internationaler Frauentag"
    if land == "BB":
        f[o] = "Ostersonntag"
        f[o + td(days=49)] = "Pfingstsonntag"
    if land in ("BW", "BY", "HE", "NW", "RP", "SL"):
        f[o + td(days=60)] = "Fronleichnam"
    if land == "SL":
        f[dt.date(year, 8, 15)] = "Mariä Himmelfahrt"
    if land == "TH":
        f[dt.date(year, 9, 20)] = "Weltkindertag"
    if land in ("BB", "HB", "HH", "MV", "NI", "SN", "ST", "SH", "TH"):
        f[dt.date(year, 10, 31)] = "Reformationstag"
    if land in ("BW", "BY", "NW", "RP", "SL"):
        f[dt.date(year, 11, 1)] = "Allerheiligen"
    if land == "SN":
        nov22 = dt.date(year, 11, 22)
        f[nov22 - td(days=(nov22.weekday() - 2) % 7)] = "Buß- und Bettag"
    return f


# --------------------------------------------------------------------------
# Tabellenstruktur erkennen
# --------------------------------------------------------------------------

def classify_header(text):
    t = norm(text)
    if not t:
        return None
    if GELD.search(t):
        return "geld"
    if t in ("monat", "monate") or t.startswith("monat "):
        return "monat"
    for kw, _ in ZUSCHLAG_KEYWORDS:
        if kw in t:
            return "zuschlag"
    if t in ("datum", "date", "tag", "dat.") or t.startswith("datum"):
        return "datum"
    if re.search(r"\b(beginn|von|start|kommen|anfang|arbeitsbeginn)\b", t):
        return "beginn"
    if re.search(r"\b(ende|bis|gehen|arbeitsende|schluss)\b", t):
        return "ende"
    if "pause" in t:
        return "pause"
    if re.search(r"(arbeitszeit|stunden|std|ist|gesamt|summe|dauer)", t):
        return "gesamt"
    if t in ("wochentag", "wt"):
        return "wochentag"
    return None


def find_header(ws):
    best_row, best_score = None, 0
    for r, row in enumerate(ws.iter_rows(min_row=1, max_row=HEADER_SCAN_ROWS), 1):
        score = sum(1 for c in row if isinstance(c.value, str) and classify_header(c.value))
        if score > best_score:
            best_row, best_score = r, score
    return best_row if best_score >= 2 else None


def find_meta(ws, header_row):
    """Mitarbeitername und Monat/Jahr aus dem Bereich über der Tabelle."""
    name, year, month = None, None, None
    texts = [ws.title]
    for row in ws.iter_rows(min_row=1, max_row=max(header_row - 1, 1)):
        cells = list(row)
        for i, c in enumerate(cells):
            if c.value is None:
                continue
            if isinstance(c.value, (dt.date, dt.datetime)) and not year:
                year, month = c.value.year, c.value.month
            t = str(c.value)
            texts.append(t)
            if re.search(r"\b(name|mitarbeiter|arbeitnehmer)\b", t, re.I) and not name:
                rest = re.split(r"[:]", t, maxsplit=1)
                if len(rest) == 2 and rest[1].strip():
                    name = rest[1].strip()
                else:
                    for nxt in cells[i + 1:]:
                        if nxt.value not in (None, ""):
                            name = str(nxt.value).strip()
                            break
    if not month:
        for t in texts:
            tl = t.lower()
            month = next((n for m, n in MONATE.items() if re.search(rf"\b{m}\b", tl)), None)
            if month:
                break
        if not year:
            y = next((re.search(r"\b(20\d{2})\b", t) for t in texts
                      if re.search(r"\b(20\d{2})\b", t)), None)
            year = int(y.group(1)) if y else None
        if not month:
            for t in texts:
                m = re.search(r"\b(\d{1,2})[./-](20\d{2})\b", t)
                if m and 1 <= int(m.group(1)) <= 12:
                    month, year = int(m.group(1)), int(m.group(2))
                    break
    return name, year, month


def detect_rate(header, default=None):
    m = re.search(r"(\d{1,3})\s*%", str(header))
    return f"{m.group(1)} %" if m else (default or "")


# --------------------------------------------------------------------------
# Auswertung
# --------------------------------------------------------------------------

def label_fuer(header):
    t = norm(header)
    rate = re.search(r"\d{1,3}\s*%", t)
    for kw, label in LABELS:
        if kw in t:
            return f"{label} {rate.group(0)}" if rate else label
    return re.sub(r"\s+", " ", str(header)).strip()


def summe_spalten(rows, cols):
    """Spalten-Modus: Zuschlagsspalten über die Zeilen aufsummieren."""
    result = OrderedDict()
    for col, header in cols:
        default = next((d for kw, d in ZUSCHLAG_KEYWORDS if kw in norm(header)), None)
        result[label_fuer(header)] = {"satz": detect_rate(header, default), "stunden": 0.0}
    for row in rows:
        for col, header in cols:
            cell = row[col]
            h = to_hours(cell.value, cell.number_format)
            if h:
                result[label_fuer(header)]["stunden"] += h
    return result


def berechne(tage, land):
    """Berechnungs-Modus: Zuschlagsstunden minutengenau nach § 3b EStG."""
    keys = OrderedDict([
        ("nacht25", ("Nachtarbeit 20–24 / 4–6 Uhr (bzw. 0–4 Uhr bei Beginn nach 0 Uhr)", "25 %")),
        ("nacht40", ("Nachtarbeit 0–4 Uhr (Beginn vor 0 Uhr)", "40 %")),
        ("sonntag", ("Sonntagsarbeit", "50 %")),
        ("feiertag125", ("Feiertagsarbeit (inkl. 31.12. ab 14 Uhr)", "125 %")),
        ("feiertag150", ("Feiertagsarbeit 24.12. ab 14 Uhr, 25./26.12., 1.5.", "150 %")),
    ])
    minuten = {k: 0 for k in keys}
    gesamt = 0
    ft_cache = {}

    def ft(year):
        if year not in ft_cache:
            ft_cache[year] = feiertage(year, land)
        return ft_cache[year]

    for datum, beginn, ende, pause in tage:
        start = dt.datetime.combine(datum, dt.time()) + dt.timedelta(minutes=beginn)
        if ende <= beginn:
            ende += 24 * 60
        stop = dt.datetime.combine(datum, dt.time()) + dt.timedelta(minutes=ende)
        stop -= dt.timedelta(minutes=pause or 0)
        t = start
        while t < stop:
            gesamt += 1
            d, hhmm = t.date(), t.hour * 60 + t.minute
            # Nacht
            if hhmm >= 20 * 60 or hhmm < 6 * 60:
                if hhmm < 4 * 60 and start < dt.datetime.combine(d, dt.time()):
                    minuten["nacht40"] += 1
                else:
                    minuten["nacht25"] += 1
            # Feiertag / Sonntag
            md = (d.month, d.day)
            if md in ((12, 25), (12, 26), (5, 1)) or (md == (12, 24) and hhmm >= 14 * 60):
                minuten["feiertag150"] += 1
            elif d in ft(d.year) or (md == (12, 31) and hhmm >= 14 * 60):
                minuten["feiertag125"] += 1
            elif d.weekday() == 6:
                minuten["sonntag"] += 1
            t += dt.timedelta(minutes=1)

    result = OrderedDict()
    for k, (label, satz) in keys.items():
        result[label] = {"satz": satz, "stunden": minuten[k] / 60}
    return result, gesamt / 60


def auswerten_blatt(ws, land, immer_berechnen):
    header_row = find_header(ws)
    if not header_row:
        return None, "keine Kopfzeile mit Datum/Stunden/Zuschlägen gefunden"
    headers = [c.value for c in ws[header_row]]
    roles = {}
    zuschlag_cols = []
    for i, h in enumerate(headers):
        role = classify_header(h) if isinstance(h, str) else None
        if role == "zuschlag":
            zuschlag_cols.append((i, h))
        elif role and role != "geld" and role not in roles:
            roles[role] = i
    # Eine allgemeine Spalte "Zuschläge" ist neben Nacht/Sonntag/... meist ein Euro-Betrag
    if any(norm(h) not in ("zuschlag", "zuschläge", "zuschlaege") for _, h in zuschlag_cols):
        zuschlag_cols = [(i, h) for i, h in zuschlag_cols
                         if norm(h) not in ("zuschlag", "zuschläge", "zuschlaege")]

    name, year, month = find_meta(ws, header_row)

    # Tageszeilen sammeln (bis zur Summenzeile bzw. Tabellenende)
    rows = []
    for row in ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row):
        values = [c.value for c in row]
        if all(v in (None, "") for v in values):
            if rows:
                break  # Tabellenende
            continue
        if any(isinstance(v, str) and SUMMENZEILE.search(v) for v in values):
            break
        if "monat" in roles and "datum" not in roles:
            mv = norm(row[roles["monat"]].value)
            if mv not in MONATE:
                continue
        elif "datum" in roles:
            d = to_date(row[roles["datum"]].value, year, month)
            if not d:
                continue
            if not year:
                year, month = d.year, d.month
        rows.append(row)

    if not rows:
        return None, "keine Tageszeilen gefunden"

    # Jahresübersicht mit einer Zeile pro Monat: jeden Monat einzeln auswerten
    if "monat" in roles and "datum" not in roles and zuschlag_cols:
        ergebnisse = []
        for r in rows:
            mnum = MONATE[norm(r[roles["monat"]].value)]
            e = ergebnis(ws, name, f"{MONATSNAMEN[mnum]} {year}" if year else MONATSNAMEN[mnum],
                         "Spalten", summe_spalten([r], zuschlag_cols), gesamt_von([r], roles))
            if e["zuschlaege"] or e["gesamtstunden"]:
                ergebnisse.append(e)
        if not ergebnisse:
            return None, "alle Monate sind leer (keine Stunden eingetragen)"
        return ergebnisse, None

    gesamt = gesamt_von(rows, roles)

    kann_berechnen = all(k in roles for k in ("datum", "beginn", "ende"))
    if zuschlag_cols and not immer_berechnen:
        modus = "Spalten"
        result = summe_spalten(rows, zuschlag_cols)
    elif kann_berechnen:
        modus = "Berechnung"
        tage = []
        for r in rows:
            d = to_date(r[roles["datum"]].value, year, month)
            b = to_time(r[roles["beginn"]].value)
            e = to_time(r[roles["ende"]].value)
            if d is None or b is None or e is None:
                continue
            p = 0
            if "pause" in roles:
                ph = to_hours(r[roles["pause"]].value, r[roles["pause"]].number_format)
                if ph:
                    # Pause als Minutenangabe (z. B. 30) oder Stunden (0,5 / 0:30)
                    p = round(ph) if ph > 12 else round(ph * 60)
            tage.append((d, b, e, p))
        result, berechnet = berechne(tage, land)
        if gesamt is None:
            gesamt = berechnet
    else:
        return None, ("weder Zuschlagsspalten noch Datum + Beginn + Ende gefunden "
                      f"(erkannte Spalten: {', '.join(roles) or '-'})")

    monat = f"{MONATSNAMEN[month]} {year}" if month and year else None
    return [ergebnis(ws, name, monat, modus, result, gesamt)], None


def gesamt_von(rows, roles):
    if "gesamt" not in roles:
        return None
    werte = [to_hours(r[roles["gesamt"]].value, r[roles["gesamt"]].number_format) for r in rows]
    return sum(w for w in werte if w)


def ergebnis(ws, name, monat, modus, result, gesamt):
    zeilen = [(k, v["satz"], round(v["stunden"], 2)) for k, v in result.items()
              if round(v["stunden"], 2) != 0]
    return {
        "blatt": ws.title,
        "mitarbeiter": name,
        "monat": monat,
        "modus": modus,
        "gesamtstunden": round(gesamt, 2) if gesamt is not None else None,
        "zuschlaege": [{"art": a, "satz": s, "stunden": h} for a, s, h in zeilen],
    }


# --------------------------------------------------------------------------
# Ausgabe
# --------------------------------------------------------------------------

def schreibe_excel(ergebnisse, pfad):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lohn ST"
    bold = Font(bold=True)
    kopf = PatternFill("solid", fgColor="D9E1F2")
    r = 1
    ws.cell(r, 1, "Lohn ST – Zuschlagsstunden").font = Font(bold=True, size=14)
    r += 2
    for e in ergebnisse:
        titel = e["mitarbeiter"] or e["blatt"]
        ws.cell(r, 1, f"Mitarbeiter: {titel}").font = bold
        r += 1
        if e["monat"]:
            ws.cell(r, 1, f"Monat: {e['monat']}")
            r += 1
        if e["gesamtstunden"] is not None:
            ws.cell(r, 1, "Gesamtarbeitsstunden")
            c = ws.cell(r, 3, e["gesamtstunden"])
            c.number_format = "0.00"
            r += 1
        r += 1
        for col, text in enumerate(("Zuschlagsart", "Satz", "Stunden"), 1):
            c = ws.cell(r, col, text)
            c.font = bold
            c.fill = kopf
        r += 1
        if not e["zuschlaege"]:
            ws.cell(r, 1, "keine Zuschlagsstunden")
            r += 1
        for z in e["zuschlaege"]:
            ws.cell(r, 1, z["art"])
            ws.cell(r, 2, z["satz"]).alignment = Alignment(horizontal="center")
            c = ws.cell(r, 3, z["stunden"])
            c.number_format = "0.00"
            r += 1
        r += 2
    ws.column_dimensions["A"].width = 58
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 12
    wb.save(pfad)


def fmt(h):
    return f"{h:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    ap = argparse.ArgumentParser(description="Lohn ST – nur Zuschlagsstunden aus einer Monatsübersicht")
    ap.add_argument("eingabe", help="Excel-Datei (.xlsx/.xlsm)")
    ap.add_argument("-o", "--ausgabe", help="Ziel-Datei (Standard: <eingabe>_Lohn_ST.xlsx)")
    ap.add_argument("--land", help="Bundesland-Kürzel für Feiertage, z. B. BY, NW")
    ap.add_argument("--berechnen", action="store_true",
                    help="Zuschläge immer aus Datum/Beginn/Ende berechnen")
    ap.add_argument("--json", action="store_true", help="Ergebnis als JSON ausgeben")
    args = ap.parse_args()

    ausgabe = args.ausgabe or re.sub(r"\.xls[xm]?$", "", args.eingabe, flags=re.I) + "_Lohn_ST.xlsx"
    wb = openpyxl.load_workbook(args.eingabe, data_only=True)

    ergebnisse = []
    for ws in wb.worksheets:
        if ws.sheet_state != "visible":
            continue
        e, fehler = auswerten_blatt(ws, args.land, args.berechnen)
        if fehler:
            print(f"Blatt '{ws.title}' übersprungen: {fehler}", file=sys.stderr)
            continue
        ergebnisse.extend(e)

    if not ergebnisse:
        sys.exit("Keine auswertbare Monatsübersicht gefunden.")

    schreibe_excel(ergebnisse, ausgabe)

    for e in ergebnisse:
        print(f"\n== {e['mitarbeiter'] or e['blatt']}" + (f" – {e['monat']}" if e["monat"] else "")
              + f"  [Modus: {e['modus']}]")
        if e["gesamtstunden"] is not None:
            print(f"   Gesamtarbeitsstunden: {fmt(e['gesamtstunden'])}")
        for z in e["zuschlaege"] or [{"art": "keine Zuschlagsstunden", "satz": "", "stunden": 0}]:
            print(f"   {z['art']:<62} {z['satz']:>6}  {fmt(z['stunden']):>8}")
    print(f"\nGespeichert: {ausgabe}")
    if args.json:
        print(json.dumps(ergebnisse, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
