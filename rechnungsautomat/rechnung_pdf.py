"""Erzeugt das Rechnungs-PDF (reportlab) und hängt die Belege als Anlage an (pypdf)."""
from __future__ import annotations

import io
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

from .abrechnung import d, de_zahl, ist_platzhalter
from .modell import Rechnung

BREITE, HOEHE = A4
LINKS, RECHTS = 25 * mm, 20 * mm
INHALT = BREITE - LINKS - RECHTS

BLAU = colors.HexColor("#1F3A6B")
ROT = colors.HexColor("#B3202A")
GRAU = colors.HexColor("#5A6270")
HELL = colors.HexColor("#EEF1F6")
LINIE = colors.HexColor("#C9CFD9")

S_NORMAL = ParagraphStyle("n", fontName="Helvetica", fontSize=9, leading=12)
S_KLEIN = ParagraphStyle("k", parent=S_NORMAL, fontSize=8, leading=10)
S_KOPF = ParagraphStyle("h", parent=S_NORMAL, fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=BLAU)
S_ZAHL = ParagraphStyle("z", parent=S_KLEIN, alignment=TA_RIGHT)
S_TITEL = ParagraphStyle("t", parent=S_NORMAL, fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=BLAU)
S_TH = ParagraphStyle("th", parent=S_KLEIN, fontName="Helvetica-Bold", textColor=colors.white)
S_TH_R = ParagraphStyle("thr", parent=S_TH, alignment=TA_RIGHT)


def euro(wert: Decimal) -> str:
    return f"{de_zahl(wert)} €"


class _NummerierteSeiten(rl_canvas.Canvas):
    """Canvas, der am Ende 'Seite x von y' schreiben kann."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seiten = []

    def showPage(self):
        self._seiten.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        gesamt = len(self._seiten)
        for zustand in self._seiten:
            self.__dict__.update(zustand)
            self.setFont("Helvetica", 7)
            self.setFillColor(GRAU)
            self.drawRightString(BREITE - RECHTS, 10 * mm, f"Seite {self._pageNumber} von {gesamt}")
            super().showPage()
        super().save()


class RechnungsPDF:
    def __init__(self, firma: dict, config_dir: Path):
        self.firma = firma
        logo = firma.get("logo")
        self.logo = (config_dir / logo) if logo and (config_dir / logo).exists() else None

    # ------------------------------------------------------------ Seitenelemente
    def _text(self, c, x, y, text, font="Helvetica", size=8, farbe=colors.black):
        c.setFont(font, size)
        c.setFillColor(ROT if ist_platzhalter(text) or "[" in str(text) else farbe)
        c.drawString(x, y, str(text))

    def _fuss(self, c):
        f = self.firma
        c.setStrokeColor(LINIE)
        c.line(LINKS, 24 * mm, BREITE - RECHTS, 24 * mm)
        spalten = [
            [f["name"], f["strasse"], f["plz_ort"], f"Tel. {f.get('telefon', '')}  ·  {f.get('email', '')}"],
            [f"Steuernummer: {f.get('steuernummer', '')}", f"USt-IdNr.: {f.get('ust_id', '')}",
             f"{f.get('handelsregister', '')}", f"Geschäftsführung: {f.get('geschaeftsfuehrer', '')}"],
            [f"{f.get('bank', '')}", f"IBAN: {f.get('iban', '')}", f"BIC: {f.get('bic', '')}"],
        ]
        for i, zeilen in enumerate(spalten):
            x = LINKS + i * INHALT / 3
            for j, z in enumerate(zeilen):
                self._text(c, x, 20 * mm - j * 3.3 * mm, z, size=6.8, farbe=GRAU)

    def _wasserzeichen(self, c):
        c.saveState()
        c.setFillColor(ROT)
        c.setFillAlpha(0.10)
        c.setFont("Helvetica-Bold", 96)
        c.translate(BREITE / 2, HOEHE / 2)
        c.rotate(35)
        c.drawCentredString(0, -30, "ENTWURF")
        c.restoreState()

    def _erste_seite(self, c, doc):
        r: Rechnung = doc.rechnung
        f = self.firma
        if self.logo:
            c.drawImage(str(self.logo), BREITE - RECHTS - 62 * mm, HOEHE - 30 * mm, 62 * mm, 17.3 * mm,
                        preserveAspectRatio=True, mask="auto")
        else:
            self._text(c, BREITE - RECHTS - 62 * mm, HOEHE - 22 * mm, f["name"], "Helvetica-Bold", 12, BLAU)
        # Absenderzeile + Empfänger (Fensterbereich DIN 5008)
        self._text(c, LINKS, HOEHE - 47 * mm, f"{f['name']} · {f['strasse']} · {f['plz_ort']}", size=6.5, farbe=GRAU)
        c.setStrokeColor(GRAU)
        c.line(LINKS, HOEHE - 48 * mm, LINKS + 85 * mm, HOEHE - 48 * mm)
        k = r.kunde
        for i, z in enumerate([k.get("name", ""), k.get("strasse", ""), k.get("plz_ort", "")]):
            self._text(c, LINKS, HOEHE - 54 * mm - i * 4.6 * mm, z, "Helvetica-Bold" if i == 0 else "Helvetica", 10)
        # Infoblock rechts
        faellig = r.datum + timedelta(days=r.zahlungsziel_tage)
        zeitraum = d(r.leistung_von) if r.leistung_von == r.leistung_bis else f"{d(r.leistung_von)} – {d(r.leistung_bis)}"
        info = [("Rechnungs-Nr.", r.nummer), ("Rechnungsdatum", d(r.datum)),
                ("Leistungszeitraum", zeitraum), ("Fällig am", d(faellig))] + r.referenzen
        x_l, x_w = 118 * mm, 146 * mm
        y = HOEHE - 47 * mm
        for label, wert in info:
            self._text(c, x_l, y, label, size=7.5, farbe=GRAU)
            zeilen = self._umbrechen(str(wert), BREITE - RECHTS - x_w, "Helvetica", 7.5)
            for z in zeilen:
                self._text(c, x_w, y, z, "Helvetica-Bold" if label == "Rechnungs-Nr." else "Helvetica", 7.5)
                y -= 3.6 * mm
            y -= 0.6 * mm
        self._fuss(c)
        if doc.entwurf:
            self._wasserzeichen(c)

    def _folgeseite(self, c, doc):
        r: Rechnung = doc.rechnung
        self._text(c, LINKS, HOEHE - 15 * mm, f"Rechnung {r.nummer} vom {d(r.datum)}", "Helvetica-Bold", 9, BLAU)
        self._text(c, LINKS, HOEHE - 19 * mm, r.kunde.get("name", ""), size=8, farbe=GRAU)
        self._fuss(c)
        if doc.entwurf:
            self._wasserzeichen(c)

    @staticmethod
    def _umbrechen(text, breite, font, size):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        woerter, zeilen, aktuell = text.split(), [], ""
        for w in woerter:
            probe = f"{aktuell} {w}".strip()
            if stringWidth(probe, font, size) <= breite or not aktuell:
                aktuell = probe
            else:
                zeilen.append(aktuell)
                aktuell = w
        return zeilen + [aktuell] if aktuell else zeilen or [""]

    # ------------------------------------------------------------ Inhalt
    def _positionen(self, r: Rechnung):
        breiten = [10 * mm, 83 * mm, 16 * mm, 12 * mm, 21 * mm, 23 * mm]
        daten = [[Paragraph(t, S_TH) for t in ("Pos.", "Leistung")] +
                 [Paragraph(t, S_TH_R) for t in ("Menge", "Einh.", "Einzelpreis", "Gesamt")]]
        stil = [
            ("BACKGROUND", (0, 0), (-1, 0), BLAU),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]
        pos = 0
        for z in r.zeilen:
            zeile = len(daten)
            if z.ist_kopf:
                daten.append(["", Paragraph(z.text, S_KOPF), "", "", "", ""])
                stil += [("SPAN", (1, zeile), (-1, zeile)), ("BACKGROUND", (0, zeile), (-1, zeile), HELL),
                         ("TOPPADDING", (0, zeile), (-1, zeile), 4)]
            else:
                pos += 1
                daten.append([Paragraph(str(pos), S_KLEIN), Paragraph(z.text, S_KLEIN),
                              Paragraph(de_zahl(z.menge), S_ZAHL), Paragraph(z.einheit, S_ZAHL),
                              Paragraph(euro(z.einzelpreis), S_ZAHL), Paragraph(euro(z.betrag), S_ZAHL)])
                stil.append(("LINEBELOW", (0, zeile), (-1, zeile), 0.3, LINIE))
        t = Table(daten, colWidths=breiten, repeatRows=1)
        t.setStyle(TableStyle(stil))
        return t

    def _summen(self, r: Rechnung):
        netto = r.netto
        mwst = (netto * r.mwst_satz / 100).quantize(Decimal("0.01"))
        brutto = netto + mwst
        daten = [["Nettobetrag", euro(netto)],
                 [f"zzgl. {de_zahl(r.mwst_satz, 0)} % USt.", euro(mwst)],
                 ["Rechnungsbetrag", euro(brutto)]]
        t = Table(daten, colWidths=[45 * mm, 28 * mm], hAlign="RIGHT")
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
            ("FONT", (0, 2), (-1, 2), "Helvetica-Bold", 10.5),
            ("TEXTCOLOR", (0, 2), (-1, 2), BLAU),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEABOVE", (0, 2), (-1, 2), 0.8, BLAU),
            ("TOPPADDING", (0, 2), (-1, 2), 4),
        ]))
        return t, brutto

    def _tarifuebersicht(self, r: Rechnung):
        daten = [["Stundenübersicht nach Tarif", "Std"]]
        daten += [[k, de_zahl(v)] for k, v in r.tarif_summen.items()]
        daten.append(["Gesamt", de_zahl(sum(r.tarif_summen.values()))])
        t = Table(daten, colWidths=[60 * mm, 18 * mm], hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5),
            ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 7.5),
            ("TEXTCOLOR", (0, 0), (-1, -1), GRAU),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.4, LINIE),
            ("LINEABOVE", (0, -1), (-1, -1), 0.4, LINIE),
            ("TOPPADDING", (0, 0), (-1, -1), 1.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
        ]))
        return t

    def erzeugen(self, r: Rechnung, ziel: Path, entwurf: bool):
        puffer = io.BytesIO()
        doc = BaseDocTemplate(puffer, pagesize=A4, leftMargin=LINKS, rightMargin=RECHTS,
                              title=f"Rechnung {r.nummer}", author=self.firma["name"])
        doc.rechnung, doc.entwurf = r, entwurf
        unten = 28 * mm
        erste = Frame(LINKS, unten, INHALT, HOEHE - 97 * mm - unten, id="erste", leftPadding=0, rightPadding=0)
        folge = Frame(LINKS, unten, INHALT, HOEHE - 26 * mm - unten, id="folge", leftPadding=0, rightPadding=0)
        doc.addPageTemplates([PageTemplate("erste", [erste], onPage=self._erste_seite),
                              PageTemplate("folge", [folge], onPage=self._folgeseite)])

        story = [NextPageTemplate("folge"),
                 Paragraph(f"Rechnung {r.nummer}", S_TITEL), Spacer(1, 3 * mm),
                 Paragraph("Sehr geehrte Damen und Herren,", S_NORMAL), Spacer(1, 1.5 * mm),
                 Paragraph("für die erbrachten Leistungen berechnen wir Ihnen wie folgt:", S_NORMAL), Spacer(1, 4 * mm),
                 self._positionen(r), Spacer(1, 4 * mm)]
        summen, brutto = self._summen(r)
        story.append(KeepTogether([summen]))
        if r.tarif_summen:
            story += [Spacer(1, 5 * mm), KeepTogether([self._tarifuebersicht(r)])]
        faellig = r.datum + timedelta(days=r.zahlungsziel_tage)
        schluss = [Spacer(1, 6 * mm),
                   Paragraph(f"Bitte überweisen Sie den Rechnungsbetrag von <b>{euro(brutto)}</b> ohne Abzug bis zum "
                             f"<b>{d(faellig)}</b> ({r.zahlungsziel_tage} Tage netto) unter Angabe der Rechnungsnummer "
                             f"<b>{r.nummer}</b> auf das unten genannte Konto.", S_NORMAL)]
        if r.anlagen:
            anzahl = len(r.anlagen)
            schluss += [Spacer(1, 3 * mm),
                        Paragraph(f"Anlage: {anzahl} Bautagesbericht{'e' if anzahl > 1 else ''} (Leistungsnachweis)", S_KLEIN)]
        schluss += [Spacer(1, 6 * mm), Paragraph("Mit freundlichen Grüßen", S_NORMAL), Spacer(1, 1.5 * mm),
                    Paragraph(self.firma["name"], S_NORMAL)]
        story.append(KeepTogether(schluss))
        doc.build(story, canvasmaker=_NummerierteSeiten)

        schreiber = PdfWriter()
        for seite in PdfReader(puffer).pages:
            schreiber.add_page(seite)
        leser: dict[Path, PdfReader] = {}
        for i, (datei, nr) in enumerate(r.anlagen, 1):
            leser.setdefault(datei, PdfReader(datei))
            seite = leser[datei].pages[nr]
            seite.merge_page(self._anlagenstempel(seite, f"Anlage {i}/{len(r.anlagen)} zu Rechnung {r.nummer}"))
            schreiber.add_page(seite)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        with open(ziel, "wb") as f:
            schreiber.write(f)

    @staticmethod
    def _anlagenstempel(seite, text):
        b, h = float(seite.mediabox.width), float(seite.mediabox.height)
        puffer = io.BytesIO()
        c = rl_canvas.Canvas(puffer, pagesize=(b, h))
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(ROT)
        c.drawString(48, h - 10, text)
        c.save()
        return PdfReader(puffer).pages[0]
