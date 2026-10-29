"""Rechnungsautomat RRB – Aufruf:  python -m rechnungsautomat [eingang] [--final]

Liest alle PDFs im Eingangsordner (Bautagesberichte, Bestellungen), erstellt daraus
Rechnungs-PDFs mit Belegen als Anlage, eine Stundenliste (Excel) und einen Prüfbericht.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import pdfplumber

from . import bestellung as bestellung_parser
from . import btb as btb_parser
from .abrechnung import Abrechnung, d, de_zahl
from .export import SYMBOL, brutto, excel, pruefbericht
from .modell import FEHLER, Hinweis, INFO
from .rechnung_pdf import RechnungsPDF


def lade(pfad: Path) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


def erste_seite_text(datei: Path) -> str:
    with pdfplumber.open(datei) as pdf:
        return (pdf.pages[0].extract_text() or "") if pdf.pages else ""


def dateiname(r, entwurf: bool) -> str:
    ref = next((w for k, w in r.referenzen if k == "Ihre Bestellung"), "")
    ref = ("Best-" + ref.split(" ")[0]) if ref else f"{r.leistung_von:%Y-%m-%d}_bis_{r.leistung_bis:%Y-%m-%d}"
    kunde = re.sub(r"\W+", "", r.kunde_key.capitalize())
    return f"{'ENTWURF_' if entwurf else ''}{r.nummer}_{kunde}_{ref}.pdf"


def main(argv=None):
    basis = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(prog="rechnungsautomat", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("eingang", nargs="?", default=basis / "eingang", type=Path, help="Ordner mit den PDFs (Standard: eingang/)")
    ap.add_argument("--ausgang", default=basis / "ausgang", type=Path, help="Zielordner (Standard: ausgang/)")
    ap.add_argument("--config", default=basis / "config", type=Path, help="Ordner mit firma/kunden/preisliste.json")
    ap.add_argument("--datum", help="Rechnungsdatum TT.MM.JJJJ (Standard: heute)")
    ap.add_argument("--final", action="store_true",
                    help="Endgültige Rechnungsnummern vergeben (Zähler in firma.json wird erhöht). "
                         "Rechnungen mit FEHLER bleiben trotzdem Entwurf.")
    args = ap.parse_args(argv)

    firma_pfad = args.config / "firma.json"
    firma, kunden, preisliste = lade(firma_pfad), lade(args.config / "kunden.json"), lade(args.config / "preisliste.json")
    datum = datetime.strptime(args.datum, "%d.%m.%Y").date() if args.datum else date.today()

    btbs, bestellungen, sonstige = [], [], []
    for datei in sorted(args.eingang.glob("*.pdf")):
        text = erste_seite_text(datei)
        if btb_parser.ist_bautagesbericht(text):
            btbs += btb_parser.parse_datei(datei)
        elif bestellung_parser.ist_bestellung(text):
            bestellungen.append(bestellung_parser.parse_datei(datei))
        else:
            sonstige.append(datei.name)
    print(f"Eingang: {len(btbs)} Bautagesberichte, {len(bestellungen)} Bestellungen, {len(sonstige)} sonstige PDFs")

    ab = Abrechnung(firma, kunden, preisliste)
    for name in sonstige:
        ab.allgemein.append(Hinweis(INFO, name, "Weder Bautagesbericht noch Bestellung – übersprungen "
                                                "(Preise kommen aus config/preisliste.json)."))
    rechnungen = ab.erstellen(btbs, bestellungen)
    global_fehler = any(h.stufe == FEHLER for h in ab.allgemein)

    nr = firma.get("naechste_rechnungsnummer", 1)
    entwurf_nr = 1
    status = {}
    pdf = RechnungsPDF(firma, args.config)
    for r in rechnungen:
        r.datum = datum
        blockiert = global_fehler or any(h.stufe == FEHLER for h in r.hinweise)
        entwurf = blockiert or not args.final
        if args.final and blockiert:
            r.nummer = f"ENTWURF-{entwurf_nr}"   # keine echte Nummer verbrauchen (lückenlose Nummerierung)
            entwurf_nr += 1
        else:
            r.nummer = firma["rechnungsnummer_format"].format(jahr=datum.year, nr=nr)
            nr += 1
        status[r.nummer] = ("ENTWURF – Fehler klären" if blockiert else "ENTWURF" if entwurf else "versandfertig")
        r.dateiname = dateiname(r, entwurf)
        pdf.erzeugen(r, args.ausgang / r.dateiname, entwurf)

    if args.final:
        firma["naechste_rechnungsnummer"] = nr
        firma_pfad.write_text(json.dumps(firma, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stempel = datum.strftime("%Y-%m-%d")
    excel(rechnungen, ab.allgemein, status, args.ausgang / f"Stundenliste_{stempel}.xlsx")
    pruefbericht(rechnungen, ab.allgemein, status, args.ausgang / f"Pruefbericht_{stempel}.md", datum)

    print()
    for r in rechnungen:
        netto, _, br = brutto(r)
        print(f"  {r.nummer:<14} {r.kunde['name'][:42]:<42} netto {de_zahl(netto):>10} €  brutto {de_zahl(br):>10} €  [{status[r.nummer]}]")
    alle = ab.allgemein + [h for r in rechnungen for h in r.hinweise]
    zaehler = {s: sum(h.stufe == s for h in alle) for s in SYMBOL}
    print("\nHinweise: " + "  ".join(f"{SYMBOL[s]} {s}: {n}" for s, n in zaehler.items()))
    print(f"Ausgabe:  {args.ausgang}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
