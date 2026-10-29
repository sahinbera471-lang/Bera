"""Parser für RRB-Bautagesberichte (Formular "Bautagesbericht – Lok und Az Personal").

Das Formular ist digital ausgefüllt, die Werte stehen also als Text im PDF. Felder werden
über die Position der Formular-Beschriftungen gefunden, nicht über feste Koordinaten.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pdfplumber

from .modell import Bautagesbericht, Taetigkeit, Zugfahrt

KOPF_LABELS = {
    "Baufirma:": "baufirma",
    "Logistiker:": "logistiker",
    "Kostenstelle:": "kostenstelle",
    "Bauvorhaben:": "bauvorhaben",
    "Lok Nr:": "lok_label",
    "Name TfzF:": "tf_name",
    "Name Azf:": "azf_name",
    "Tfz/ BR:": "tfz_br",
    "Firma": "firma",
}
FIRMA_ZU = {"tf_name": "tf_firma", "azf_name": "azf_firma", "tfz_br": "tfz_firma"}

DATUM_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
ZEIT_RE = re.compile(r"^(\d{1,2})[:/.](\d{2})$")


def ist_bautagesbericht(text: str) -> bool:
    return "Bautagesbericht" in text and "Lok und Az Personal" in text


def zeit_normal(text: str) -> str:
    """'23/30' -> '23:30', '3:40' -> '03:40'. Leer, wenn keine Uhrzeit."""
    m = ZEIT_RE.match(text.strip())
    if not m:
        return ""
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _mitte(w) -> float:
    return (w["x0"] + w["x1"]) / 2


def _zeilen(words, toleranz=4.0):
    zeilen = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if zeilen and abs(w["top"] - zeilen[-1][0]["top"]) <= toleranz:
            zeilen[-1].append(w)
        else:
            zeilen.append([w])
    return [sorted(z, key=lambda w: w["x0"]) for z in zeilen]


def _finde(words, text, x_max=None):
    for w in words:
        if w["text"].strip() == text and (x_max is None or w["x0"] < x_max):
            return w
    return None


def _naechste_spalte(wort, spalten: dict[str, dict]) -> str:
    return min(spalten, key=lambda k: abs(_mitte(spalten[k]) - _mitte(wort)))


def _parse_kopf(words, datum_top, btb: Bautagesbericht):
    lok_top = _finde(words, "Lok Nr:")
    werte: dict[str, list[str]] = {}
    for zeile in _zeilen([w for w in words if 70 < w["top"] < datum_top - 5]):
        feld = None
        letzter_name = None
        for w in zeile:
            t = w["text"].strip()
            if t in KOPF_LABELS:
                feld = KOPF_LABELS[t]
                if feld == "firma":
                    feld = FIRMA_ZU.get(letzter_name)
                elif feld in FIRMA_ZU:
                    letzter_name = feld
                continue
            if lok_top and w["top"] > lok_top["top"] + 5 and w["x1"] < 150 and feld is None:
                werte.setdefault("lok_nr", []).append(t)
            elif feld and feld != "lok_label":
                werte.setdefault(feld, []).append(t)
    for feld, teile in werte.items():
        setattr(btb, feld, " ".join(teile).strip())


def _parse_zeiten(page, words, datum_label, btb: Bautagesbericht):
    band = [w for w in words if datum_label["top"] + 5 < w["top"] < datum_label["top"] + 25]
    von = sorted([w for w in band if w["text"].strip() == "von"], key=lambda w: w["x0"])
    bis = sorted([w for w in band if w["text"].strip() == "bis"], key=lambda w: w["x0"])
    nein = _finde(band, "nein")
    ja = _finde(band, "ja")
    minuten = _finde(band, "Minuten")
    stunden = _finde(words, "Stunden")
    if len(von) < 2 or len(bis) < 2:
        return
    spalten = {
        "bestellt_von": von[0], "bestellt_bis": bis[0],
        "ist_von": von[1], "ist_bis": bis[1],
    }
    zahl_spalten = {k: v for k, v in (("pause", minuten), ("stunden", stunden)) if v}
    kopf_top = von[0]["top"]
    for w in words:
        if not (kopf_top + 5 < w["top"] < kopf_top + 32):
            continue
        t = w["text"].strip()
        m = DATUM_RE.search(t)
        if m and btb.datum is None:
            btb.datum = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date()
            continue
        z = zeit_normal(t)
        if z:
            setattr(btb, _naechste_spalte(w, spalten), z)
            continue
        if re.fullmatch(r"\d+([.,]\d+)?", t) and zahl_spalten:
            ziel = _naechste_spalte(w, zahl_spalten)
            if ziel == "stunden":
                btb.stunden_angegeben = Decimal(t.replace(",", "."))
            else:
                btb.pause_minuten = int(Decimal(t.replace(",", ".")))
    # Kreuz im Feld Pause nein/ja (als zwei schräge Linien gezeichnet)
    if nein and ja and minuten:
        felder = {"nein": (nein["x0"] - 6, ja["x0"] - 4), "ja": (ja["x0"] - 4, minuten["x0"] - 2)}
        for linie in page.lines + page.curves:
            schraeg = abs(linie["x1"] - linie["x0"]) > 3 and abs(linie["bottom"] - linie["top"]) > 3
            if not schraeg or not (kopf_top < linie["top"] < kopf_top + 40):
                continue
            for name, (links, rechts) in felder.items():
                if links <= linie["x0"] and linie["x1"] <= rechts + 2:
                    btb.pause_angekreuzt = name


def _parse_betra(words, btb: Bautagesbericht):
    label = _finde(words, "BETRA Nr:")
    wetter = _finde(words, "Wetter")
    if not label:
        return
    rechts = wetter["x0"] - 5 if wetter else 360
    treffer = [w for w in words
               if label["top"] - 15 < w["top"] < label["top"] + 13
               and label["x1"] + 5 < w["x0"] < rechts]
    btb.betra = [w["text"].strip() for w in sorted(treffer, key=lambda w: w["top"]) if w["text"].strip()]


def _parse_zugfahrten(words, btb: Bautagesbericht):
    kopf = _finde(words, "Zug-Nr.:")
    ende = _finde(words, "Ausgeführte Arbeiten [ von - bis ]")
    if not kopf:
        return
    kopfzeile = [w for w in words if abs(w["top"] - kopf["top"]) < 4]
    namen = ["zug_nr", "von_bf", "nach_bf", "fertigmeldung", "abfahrt", "ankunft"]
    spalten = dict(zip(namen, sorted(kopfzeile, key=lambda w: w["x0"])))
    unten = ende["top"] if ende else kopf["top"] + 80
    for zeile in _zeilen([w for w in words if kopf["top"] + 6 < w["top"] < unten - 4]):
        werte = dict.fromkeys(namen, "")
        for w in zeile:
            t = w["text"].strip()
            if t in ("*", ""):
                continue
            werte[_naechste_spalte(w, spalten)] = t
        if any(werte.values()):
            btb.zugfahrten.append(Zugfahrt(**werte))


def _parse_taetigkeiten(words, btb: Bautagesbericht):
    kopf = _finde(words, "Warte")
    grund = [w for w in words if w["text"].strip() == "Grund zu:" and w["x0"] < 120]
    if not kopf or not grund:
        return
    for zeile in _zeilen([w for w in words if kopf["top"] + 6 < w["top"] < grund[0]["top"] - 3]):
        von = bis = ""
        text = []
        for w in zeile:
            t = w["text"].strip()
            if w["x1"] < 92 and zeit_normal(t):
                von = zeit_normal(t)
            elif 95 < w["x0"] < 140 and zeit_normal(t):
                bis = zeit_normal(t)
            elif w["x0"] > 230 and t != "-":
                text.append(t)
        if von or bis or text:
            btb.taetigkeiten.append(Taetigkeit(von, bis, " ".join(text)))


def _parse_fuss(words, btb: Bautagesbericht):
    grund = [w for w in words if w["text"].strip() == "Grund zu:" and w["x0"] < 120]
    ort = _finde(words, "Ort/Datum")
    unt = _finde(words, "Azf/Tf Unterschrift")
    ag = _finde(words, "AG / 4.2 gezeichnet")
    if grund and ort:
        band = [w for w in words if grund[0]["top"] + 8 < w["top"] < ort["top"] - 30
                and w["x0"] > 85 and not re.fullmatch(r"\*\d\.", w["text"].strip())]
        for zeile in _zeilen(band):
            text = " ".join(w["text"].strip() for w in zeile).strip()
            if text:
                btb.vorkommnisse.append(text)
    if ort and unt and ag:
        spalten = {"ort_datum": ort, "unterschrift": unt, "ag_gezeichnet": ag}
        werte: dict[str, list[str]] = {}
        for w in words:
            if ort["top"] - 28 < w["top"] < ort["top"] - 4:
                werte.setdefault(_naechste_spalte(w, spalten), []).append(w["text"].strip())
        for feld, teile in werte.items():
            setattr(btb, feld, " ".join(teile).strip())


def parse_seite(page, datei: Path, nr: int) -> Bautagesbericht | None:
    words = page.extract_words(keep_blank_chars=True, x_tolerance=1.5)
    for w in words:
        # manche Formulare liefern 'ß' als 'û' ("Baumaûnahme")
        w["text"] = re.sub(r"(?<=[a-zäöü])û(?=[a-zäöü])", "ß", w["text"])
    datum_label = _finde(words, "Datum:")
    if not datum_label:
        return None
    btb = Bautagesbericht(datei=datei, seite=nr)
    _parse_kopf(words, datum_label["top"], btb)
    _parse_zeiten(page, words, datum_label, btb)
    _parse_betra(words, btb)
    _parse_zugfahrten(words, btb)
    _parse_taetigkeiten(words, btb)
    _parse_fuss(words, btb)
    return btb


def parse_datei(datei: Path) -> list[Bautagesbericht]:
    berichte = []
    with pdfplumber.open(datei) as pdf:
        for nr, page in enumerate(pdf.pages):
            if not ist_bautagesbericht(page.extract_text() or ""):
                continue
            btb = parse_seite(page, datei, nr)
            if btb:
                berichte.append(btb)
    return berichte
