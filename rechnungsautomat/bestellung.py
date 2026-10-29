"""Parser für Kunden-Bestellungen (Format J. Hubert / DocuWare, inkl. angehängter Bestell-Mail)."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pdfplumber

from .modell import Bestellposition, Bestellung, MailAngabe

DATUM = r"(\d{2}\.\d{2}\.\d{4})"
BETRAG = r"(\d{1,3}(?:\.\d{3})*,\d{2})"
POS_RE = re.compile(
    rf"^(\d+(?:\.\d{{3}})*,\d+)\s*(Std|Stk|Stück|h|km|Psch\.?|Pauschale)\s+(?:{DATUM}\s*)?(.*?)\s*{BETRAG}\s+{BETRAG}$"
)


def ist_bestellung(text: str) -> bool:
    return bool(re.search(r"Bestellung\s*-\s*Nr\.", text))


def zahl(text: str) -> Decimal:
    return Decimal(text.replace(".", "").replace(",", "."))


def datum(text: str):
    return datetime.strptime(text, "%d.%m.%Y").date()


def _detail(ziel, zeile: str) -> bool:
    """Übernimmt Leistung/KST/Funktion/Zeitaufwand. True, wenn die Zeile erkannt wurde."""
    if m := re.match(r"Leistung:\s*(.*)", zeile):
        ziel.leistung = m.group(1).strip()
    elif m := re.match(r"KST:\s*(\S+)", zeile):
        ziel.kst = m.group(1)
    elif m := re.match(r"Funktion:\s*(.*)", zeile):
        ziel.funktion = m.group(1).strip()
    elif m := re.match(r"Zeitaufwand:\s*(\d+(?:[.,]\d+)?)\s*(?:Std|Stunden|h)", zeile):
        ziel.zeitaufwand_std = zahl(m.group(1))
    else:
        return False
    return True


def _parse_positionen(zeilen: list[str], b: Bestellung):
    aktuell = None
    in_leistung = False
    for zeile in zeilen:
        if zeile.startswith("Summe"):
            if m := re.search(BETRAG + r"\s*$", zeile):
                b.summe_netto = zahl(m.group(1))
            aktuell = None
            continue
        if m := POS_RE.match(zeile):
            aktuell = Bestellposition(
                menge=zahl(m.group(1)), einheit=m.group(2),
                datum=datum(m.group(3)) if m.group(3) else None,
                einzelpreis=zahl(m.group(5)), gesamtpreis=zahl(m.group(6)),
                leistung=m.group(4).strip(),
            )
            b.positionen.append(aktuell)
            in_leistung = False
            continue
        if aktuell is None or re.match(r"pro \d", zeile):
            continue
        if _detail(aktuell, zeile):
            in_leistung = zeile.startswith("Leistung:")
        elif in_leistung:
            aktuell.leistung += " " + zeile


def _parse_mail(zeilen: list[str], b: Bestellung):
    aktuell = None
    in_leistung = False
    for zeile in zeilen:
        if re.fullmatch(DATUM, zeile):
            aktuell = MailAngabe(datum=datum(zeile))
            b.mail_angaben.append(aktuell)
            in_leistung = False
        elif aktuell is not None:
            if _detail(aktuell, zeile):
                in_leistung = zeile.startswith("Leistung:")
            elif in_leistung and not re.match(r"(Vielen|Viele|Mit freundlichen|Gruß|Grüße)", zeile):
                aktuell.leistung += " " + zeile
            else:
                in_leistung = False


def parse_datei(datei: Path) -> Bestellung:
    with pdfplumber.open(datei) as pdf:
        seiten = [(p.extract_text() or "") for p in pdf.pages]
    b = Bestellung(datei=datei)
    bestell_zeilen: list[str] = []
    mail_zeilen: list[str] = []
    for text in seiten:
        # \uf0b7, \u2022, \u00b7 = Aufzählungszeichen aus Outlook-Mails
        zeilen = [z.strip(" \t\uf0b7\u2022\u00b7") for z in text.splitlines()]
        zeilen = [z for z in zeilen if z]
        ist_mail = any(z.startswith("Von:") for z in zeilen) and any(z.startswith("Betreff:") for z in zeilen)
        (mail_zeilen if ist_mail else bestell_zeilen).extend(zeilen)

    if bestell_zeilen:
        b.besteller = bestell_zeilen[0]
    voll = "\n".join(bestell_zeilen)
    if m := re.search(r"Bestellung\s*-\s*Nr\.\s*(\S+)", voll):
        b.nummer = m.group(1)
    if m := re.search(r"Datum:\s*" + DATUM, voll):
        b.datum = datum(m.group(1))
    if m := re.search(r"Kostenstelle:\s*(\S+)\s*-\s*(.*?)\s+Anspr\.partner:\s*(.*)\n(.*?)\s*Mobil:\s*(.*)", voll):
        b.kostenstelle = m.group(1)
        b.kostenstelle_text = " ".join(t for t in (m.group(2).strip(), m.group(4).strip()) if t)
        b.ansprechpartner = m.group(3).strip()
        b.ansprechpartner_mobil = m.group(5).strip()
    if m := re.search(r"Zahlungsbedingung:\s*(\d+)\s*Tage", voll):
        b.zahlungsziel_tage = int(m.group(1))
    if m := re.search(r"an\s+(\S+@\S+)\s+vermerken", voll):
        b.rechnung_email = m.group(1)
    b.belege_erforderlich = "Rechnungsbegründende Unterlagen" in voll

    # Empfängerblock (unsere Adresse, wie der Kunde sie führt)
    for i, z in enumerate(bestell_zeilen):
        if z.startswith("Firma"):
            for folge in bestell_zeilen[i + 1:]:
                if ist_bestellung(folge):
                    break
                b.empfaenger.append(folge)
            break
    # Rechnungsadresse
    for i, z in enumerate(bestell_zeilen):
        if z.startswith("Rechnungsadresse"):
            for folge in bestell_zeilen[i + 1:]:
                if folge.startswith("Rechnungsbegründende") or folge.startswith("Zahlungsbedingung"):
                    break
                b.rechnungsadresse.append(folge)
            break

    _parse_positionen(bestell_zeilen, b)
    _parse_mail(mail_zeilen, b)
    return b
