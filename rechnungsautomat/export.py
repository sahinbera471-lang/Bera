"""Stundenliste (Excel) und Prüfbericht (Markdown)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import tarife
from .abrechnung import d, de_zahl, schicht_betrag
from .modell import FEHLER, INFO, PRUEFEN, Hinweis, Rechnung

STUFEN = {FEHLER: 0, PRUEFEN: 1, INFO: 2}
SYMBOL = {FEHLER: "🔴", PRUEFEN: "🟡", INFO: "⚪"}
KOPF_FILL = PatternFill("solid", fgColor="1F3A6B")
FARBE = {FEHLER: "F8D7DA", PRUEFEN: "FFF3CD", INFO: "FFFFFF"}


def brutto(r: Rechnung) -> tuple[Decimal, Decimal, Decimal]:
    netto = r.netto
    mwst = (netto * r.mwst_satz / 100).quantize(Decimal("0.01"))
    return netto, mwst, netto + mwst


def _blatt(wb, titel, kopf, zeilen, breiten, faerben=None):
    ws = wb.create_sheet(titel)
    ws.append(kopf)
    for zelle in ws[1]:
        zelle.font = Font(bold=True, color="FFFFFF")
        zelle.fill = KOPF_FILL
        zelle.alignment = Alignment(vertical="center", wrap_text=True)
    for z in zeilen:
        ws.append(z)
        if faerben:
            farbe = faerben(z)
            if farbe:
                for zelle in ws[ws.max_row]:
                    zelle.fill = PatternFill("solid", fgColor=farbe)
    for i, b in enumerate(breiten, 1):
        ws.column_dimensions[get_column_letter(i)].width = b
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def excel(rechnungen: list[Rechnung], allgemein: list[Hinweis], status: dict[str, str], ziel: Path):
    wb = Workbook()
    wb.remove(wb.active)
    zeilen = []
    for r in rechnungen:
        netto, mwst, br = brutto(r)
        zeilen.append([r.nummer, r.kunde["name"], r.leistung_von, r.leistung_bis, float(netto), float(mwst), float(br),
                       r.datum + timedelta(days=r.zahlungsziel_tage), status[r.nummer], r.dateiname])
    ws = _blatt(wb, "Rechnungen", ["Rechnungs-Nr.", "Kunde", "Leistung von", "Leistung bis", "Netto €", "USt €", "Brutto €",
                                   "Fällig", "Status", "Datei"], zeilen, [16, 38, 13, 13, 12, 11, 12, 12, 30, 52])
    for zeile in ws.iter_rows(min_row=2):
        for i in (2, 3, 7):
            zeile[i].number_format = "DD.MM.YYYY"
        for i in (4, 5, 6):
            zeile[i].number_format = '#,##0.00 "€"'

    zeilen = []
    for r in rechnungen:
        for s in r.schichten:
            m = s.minuten
            betrag = schicht_betrag(s)
            quelle = f"{s.quelle.datei.name} S.{s.quelle.seite + 1}" if s.quelle else ""
            zeilen.append([r.nummer, r.kunde["name"], s.person, s.rolle, s.start.date(), s.start.strftime("%H:%M"),
                           s.ende.strftime("%H:%M"), s.pause_minuten, round(sum(m.values()) / 60, 2),
                           *(round(m.get(k, 0) / 60, 2) for k in tarife.KATEGORIEN), s.einsatzort, s.km, float(betrag), quelle])
    ws = _blatt(wb, "Stunden", ["Rechnung", "Kunde", "Person", "Rolle", "Datum", "von", "bis", "Pause min", "Std gesamt",
                                "Std normal", "Std Nacht", "Std Sonntag", "Std Feiertag", "Einsatzort", "km",
                                "Betrag netto € (Preisliste)", "Quelle"],
                zeilen, [16, 30, 18, 7, 12, 7, 7, 9, 10, 10, 10, 11, 11, 16, 6, 14, 48])
    for zeile in ws.iter_rows(min_row=2):
        zeile[4].number_format = "DD.MM.YYYY"
        zeile[15].number_format = '#,##0.00 "€"'

    zeilen = [["(alle)", h.stufe, h.quelle, h.text] for h in sorted(allgemein, key=lambda h: STUFEN[h.stufe])]
    for r in rechnungen:
        zeilen += [[r.nummer, h.stufe, h.quelle, h.text] for h in sorted(r.hinweise, key=lambda h: STUFEN[h.stufe])]
    ws = _blatt(wb, "Prüfhinweise", ["Rechnung", "Stufe", "Quelle", "Hinweis"], zeilen, [16, 10, 48, 120],
                faerben=lambda z: FARBE.get(z[1]))
    for zeile in ws.iter_rows(min_row=2):
        zeile[3].alignment = Alignment(wrap_text=True, vertical="top")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ziel)


def pruefbericht(rechnungen: list[Rechnung], allgemein: list[Hinweis], status: dict[str, str], ziel: Path, datum):
    z = [f"# Prüfbericht Rechnungslauf {d(datum)}", "",
         "🔴 FEHLER = vor Versand klären · 🟡 PRÜFEN = bitte ansehen · ⚪ INFO = zur Kenntnis", "",
         "| Rechnung | Kunde | Zeitraum | Netto | Brutto | Status |", "|---|---|---|---:|---:|---|"]
    summe_n = summe_b = Decimal("0")
    for r in rechnungen:
        netto, _, br = brutto(r)
        summe_n += netto
        summe_b += br
        zeitraum = d(r.leistung_von) if r.leistung_von == r.leistung_bis else f"{d(r.leistung_von)} – {d(r.leistung_bis)}"
        z.append(f"| {r.nummer} | {r.kunde['name']} | {zeitraum} | {de_zahl(netto)} € | {de_zahl(br)} € | {status[r.nummer]} |")
    z += [f"| **Summe** | | | **{de_zahl(summe_n)} €** | **{de_zahl(summe_b)} €** | |", ""]
    if allgemein:
        z += ["## Allgemein", ""] + [f"- {SYMBOL[h.stufe]} **{h.quelle}:** {h.text}" for h in sorted(allgemein, key=lambda h: STUFEN[h.stufe])] + [""]
    for r in rechnungen:
        z += [f"## {r.nummer} – {r.kunde['name']}", "", f"Datei: `{r.dateiname}`", ""]
        z += [f"- {SYMBOL[h.stufe]} **{h.quelle}:** {h.text}" for h in sorted(r.hinweise, key=lambda h: STUFEN[h.stufe])] or ["- keine Auffälligkeiten"]
        z.append("")
    ziel.write_text("\n".join(z), encoding="utf-8")
