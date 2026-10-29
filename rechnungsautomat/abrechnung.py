"""Baut Rechnungen aus Bautagesberichten (BTB) und Bestellungen und prüft sie auf Plausibilität."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from . import tarife
from .modell import (FEHLER, INFO, PRUEFEN, Bautagesbericht, Bestellung, Hinweis,
                     Rechnung, Rechnungszeile, Schicht)

WOCHENTAG = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
ROLLE_TEXT = {"TF": "Tf", "AZF": "Azf"}
PFLICHT_FIRMA = ["steuernummer", "ust_id", "iban", "bic", "bank", "handelsregister", "geschaeftsfuehrer"]
PFLICHT_KUNDE = ["name", "strasse", "plz_ort"]


def d(dt) -> str:
    return dt.strftime("%d.%m.%Y")


def std(minuten: int) -> Decimal:
    return (Decimal(minuten) / 60).quantize(Decimal("0.01"))


def de_zahl(wert: Decimal, stellen=2) -> str:
    return f"{wert:,.{stellen}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def schicht_betrag(s: Schicht) -> Decimal:
    """Netto-Betrag einer Schicht nach Preisliste, gerundet wie auf der Rechnung (je Zeitfenster)."""
    teile = [(k, m) for k, _, _, m in s.segmente] + ([s.auffuellung] if s.auffuellung else [])
    return sum((tarife.geld(std(m) * s.saetze[k]) for k, m in teile if m), Decimal("0"))


def ist_platzhalter(wert) -> bool:
    return wert is None or str(wert).strip() == "" or bool(re.fullmatch(r"\[.*\]", str(wert).strip()))


def kunde_finden(text: str, kunden: dict) -> str | None:
    """Längster Alias-Treffer gewinnt ('Eiffage Infra Rail' vor 'Eiffage')."""
    t = (text or "").lower()
    bester, laenge = None, 0
    for key, k in kunden.items():
        if key.startswith("_"):
            continue
        for alias in [k["name"], *k.get("aliase", [])]:
            a = alias.lower()
            if a and a in t and len(a) > laenge:
                bester, laenge = key, len(a)
    return bester


def ist_eigene_firma(text: str, firma: dict) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in firma.get("eigene_kuerzel", []))


def einsatzort_und_km(btb: Bautagesbericht, kunden: dict) -> tuple[str, int | None]:
    ort = btb.bauvorhaben
    if not ort or "siehe" in ort.lower():
        ort = btb.ort_datum.split(",")[0].strip() if "," in btb.ort_datum else ""
    tabelle = {k.lower().replace("-", " "): v for k, v in kunden.get("_einsatzorte_km", {}).items()}
    return ort, tabelle.get(ort.lower().replace("-", " "))


class Abrechnung:
    def __init__(self, firma: dict, kunden: dict, preisliste: dict):
        self.firma = firma
        self.kunden = kunden
        self.preisliste = preisliste
        self.land = firma.get("bundesland", "NW")
        self.allgemein: list[Hinweis] = []

    # ------------------------------------------------------------------ Schichten
    def schicht(self, btb: Bautagesbericht, rolle: str, person: str, hinweise: list[Hinweis]) -> Schicht | None:
        von, bis = btb.ist_von, btb.ist_bis
        if not (von and bis):
            von, bis = btb.bestellt_von, btb.bestellt_bis
            if not (von and bis):
                hinweise.append(Hinweis(FEHLER, btb.bezeichnung, "Weder Ist- noch bestellte Zeit lesbar – Schicht nicht abgerechnet."))
                return None
            hinweise.append(Hinweis(PRUEFEN, btb.bezeichnung,
                                    f"Ist-Zeit nicht eingetragen – bestellte Zeit {von}–{bis} abgerechnet."))
        if btb.datum is None:
            hinweise.append(Hinweis(FEHLER, btb.bezeichnung, "Datum nicht lesbar – Schicht nicht abgerechnet."))
            return None
        start = datetime.combine(btb.datum, time(*map(int, von.split(":"))))
        ende = datetime.combine(btb.datum, time(*map(int, bis.split(":"))))
        if ende <= start:
            ende += timedelta(days=1)

        teile = tarife.pause_abziehen(tarife.segmente(start, ende, self.preisliste, self.land), btb.pause_minuten)
        minuten = tarife.summen(teile)
        gearbeitet_min = sum(minuten.values())
        mindest = self.preisliste["mindeststunden_pro_schicht"]
        auffuellung = None
        if gearbeitet_min < mindest * 60:
            haupt = max(minuten, key=minuten.get) if minuten else "normal"
            auffuellung = (haupt, mindest * 60 - gearbeitet_min)
            minuten[haupt] = minuten.get(haupt, 0) + auffuellung[1]
            hinweise.append(Hinweis(INFO, btb.bezeichnung,
                                    f"Schicht kürzer als {mindest} Std – laut Preisliste auf {mindest} Std aufgefüllt (+{auffuellung[1]} min)."))
        gearbeitet = std(gearbeitet_min)
        if btb.stunden_angegeben is not None and abs(gearbeitet - btb.stunden_angegeben) > Decimal("0.01"):
            hinweise.append(Hinweis(PRUEFEN, btb.bezeichnung,
                                    f"Im Bericht stehen {de_zahl(btb.stunden_angegeben)} Std, aus den Zeiten ergeben sich {de_zahl(gearbeitet)} Std "
                                    "– abgerechnet wird nach Uhrzeiten."))
        ort, km = einsatzort_und_km(btb, self.kunden)
        saetze = {k: tarife.satz(self.preisliste, rolle, k, km) for k, m in minuten.items() if m}
        return Schicht(person, rolle, start, ende, btb.pause_minuten, teile, auffuellung, minuten, saetze, ort, km, btb)

    # ------------------------------------------------------------------ BTB-Rechnung
    def rechnung_aus_btbs(self, kunde_key: str, btbs: list[Bautagesbericht]) -> Rechnung:
        kunde = self.kunden[kunde_key]
        r = Rechnung(kunde_key, kunde,
                     mwst_satz=Decimal(str(self.preisliste["mwst_satz"])),
                     zahlungsziel_tage=kunde.get("zahlungsziel_tage") or self.preisliste["zahlungsziel_tage"])
        fremd: dict[str, set[str]] = defaultdict(set)
        orte: dict[str, int | None] = {}
        for btb in sorted(btbs, key=lambda b: (b.datum, b.tf_name)):
            self._pruefe_btb(btb, kunde_key, r.hinweise)
            for rolle, name, firma in (("TF", btb.tf_name, btb.tf_firma), ("AZF", btb.azf_name, btb.azf_firma)):
                if not name:
                    continue
                if not ist_eigene_firma(firma, self.firma):
                    fremd[firma or "unbekannt"].add(f"{ROLLE_TEXT[rolle]} {name}")
                    continue
                s = self.schicht(btb, rolle, name, r.hinweise)
                if not s:
                    continue
                r.schichten.append(s)
                orte[s.einsatzort or "?"] = s.km
                self._zeilen_fuer_schicht(r, s, btb)
            r.anlagen.append((btb.datei, btb.seite))

        if r.schichten:
            r.leistung_von = min(s.start for s in r.schichten).date()
            r.leistung_bis = max(s.ende for s in r.schichten).date()
        r.referenzen = self._btb_referenzen(btbs)
        for firma, personen in fremd.items():
            r.hinweise.append(Hinweis(INFO, "Personal", f"{', '.join(sorted(personen))} ({firma}) – nicht über uns abgerechnet."))
        for ort, km in orte.items():
            if km is None:
                r.hinweise.append(Hinweis(PRUEFEN, "Entfernung",
                                          f"Entfernung für Einsatzort „{ort}“ unbekannt – Sätze „bis 100 km“ angenommen. "
                                          "In config/kunden.json unter _einsatzorte_km eintragen."))
            else:
                spalte = "ab 100 km" if km >= 100 else "bis 100 km"
                r.hinweise.append(Hinweis(INFO, "Entfernung", f"Einsatzort {ort}: {km} km laut kunden.json → Sätze „{spalte}“. Bitte Wert bestätigen."))
        ohne_ag = [b for b in btbs if not b.ag_gezeichnet]
        if ohne_ag:
            r.hinweise.append(Hinweis(PRUEFEN, "Belege",
                                      f"Auf {len(ohne_ag)} von {len(btbs)} Bautagesberichten fehlt die Gegenzeichnung des Auftraggebers (Feld „AG / 4.2 gezeichnet“)."))
        zuschlag = defaultdict(int)
        for s in r.schichten:
            for k in ("sonntag", "feiertag"):
                zuschlag[k] += s.minuten.get(k, 0)
        for k, m in zuschlag.items():
            if m:
                r.hinweise.append(Hinweis(INFO, "Tarif", f"{tarife.KATEGORIE_TEXT[k]} für {de_zahl(std(m))} Std angewendet."))
        self._kunde_pruefen(r)
        return r

    def _zeilen_fuer_schicht(self, r: Rechnung, s: Schicht, btb: Bautagesbericht):
        kopf = (f"{WOCHENTAG[s.start.weekday()]} {s.start:%d.%m.} {s.start:%H:%M} – "
                f"{WOCHENTAG[s.ende.weekday()]} {s.ende:%d.%m.%Y} {s.ende:%H:%M}  ·  "
                f"{ROLLE_TEXT[s.rolle]} {s.person}")
        lok = btb.lok_nr or btb.tfz_br
        if lok:
            lok = f"Lok {lok}" + (f" ({btb.tfz_br})" if btb.tfz_br and btb.tfz_br != lok else "")
        # Ort nur zeigen, wenn er als Bauvorhaben im Bericht steht (Ort/Datum ist nur der Unterschriftsort)
        ort = btb.bauvorhaben if btb.bauvorhaben and "siehe" not in btb.bauvorhaben.lower() else ""
        details = [x for x in (lok, ort) if x]
        if details:
            kopf += "  ·  " + " · ".join(details)
        if s.pause_minuten:
            kopf += f"  ·  abzgl. {s.pause_minuten} min Pause"
        r.zeilen.append(Rechnungszeile(kopf, ist_kopf=True))
        bezeichnung = self.preisliste["rollen"][s.rolle]["bezeichnung"]
        weit = " – Satz ab 100 km" if s.km is not None and s.km >= 100 else ""
        for kat, von, bis, m in s.segmente:
            if not m:
                continue
            menge = std(m)
            text = f"{bezeichnung} – {tarife.KATEGORIE_TEXT[kat]} {tarife.uhr(von)}–{tarife.uhr(bis, True)} Uhr{weit}"
            r.zeilen.append(Rechnungszeile(text, menge, "Std", s.saetze[kat], tarife.geld(menge * s.saetze[kat])))
        if s.auffuellung:
            kat, m = s.auffuellung
            menge = std(m)
            text = (f"{bezeichnung} – Auffüllung auf Mindestschicht {self.preisliste['mindeststunden_pro_schicht']} Std "
                    f"({tarife.KATEGORIE_TEXT[kat]}){weit}")
            r.zeilen.append(Rechnungszeile(text, menge, "Std", s.saetze[kat], tarife.geld(menge * s.saetze[kat])))
        for kat, m in s.minuten.items():
            schluessel = f"{ROLLE_TEXT[s.rolle]} – {tarife.KATEGORIE_TEXT[kat]}"
            r.tarif_summen[schluessel] = r.tarif_summen.get(schluessel, Decimal("0")) + std(m)
        an = tarife.anfahrt(self.preisliste, s.km)
        if an:
            r.zeilen.append(Rechnungszeile(f"An- und Abfahrt ({s.km} km)", Decimal("1"), "psch.", an, an))

    def _btb_referenzen(self, btbs: list[Bautagesbericht]) -> list[tuple[str, str]]:
        def eindeutig(werte):
            return list(dict.fromkeys(w for w in werte if w and "siehe" not in w.lower()))
        refs = []
        if bv := eindeutig(b.bauvorhaben for b in btbs):
            refs.append(("Bauvorhaben", ", ".join(bv)))
        if betra := eindeutig(x for b in btbs for x in b.betra):
            refs.append(("BETRA-Nr.", ", ".join(betra)))
        if kst := eindeutig(b.kostenstelle for b in btbs):
            refs.append(("Kostenstelle", ", ".join(kst)))
        if log := eindeutig(b.logistiker for b in btbs):
            refs.append(("Logistiker", ", ".join(log)))
        return refs

    def _pruefe_btb(self, btb: Bautagesbericht, kunde_key: str, hinweise: list[Hinweis]):
        if not btb.kostenstelle:
            hinweise.append(Hinweis(PRUEFEN, btb.bezeichnung, "Kostenstelle leer (andere Berichte: „siehe Betra“) – Zuordnung klären."))
        lok_kunde = kunde_finden(btb.tfz_firma, self.kunden)
        if lok_kunde and lok_kunde != kunde_key:
            hinweise.append(Hinweis(PRUEFEN, btb.bezeichnung,
                                    f"Baufirma ist „{btb.baufirma}“, das Tfz gehört aber „{btb.tfz_firma}“ "
                                    f"({self.kunden[lok_kunde]['name']}). Wer ist Auftraggeber? Vorerst bei {self.kunden[kunde_key]['name']} abgerechnet."))
        for v in btb.vorkommnisse:
            hinweise.append(Hinweis(INFO, btb.bezeichnung, f"Vorkommnis: {v}"))
        # Lücken/Überschneidungen im Tätigkeitsprotokoll
        zeiten = [(t.von, t.bis) for t in btb.taetigkeiten if t.von and t.bis]
        for (v1, b1), (v2, _) in zip(zeiten, zeiten[1:]):
            if b1 != v2:
                hinweise.append(Hinweis(INFO, btb.bezeichnung, f"Tätigkeitsprotokoll: Lücke/Sprung zwischen {b1} und {v2}."))

    # ------------------------------------------------------------------ Bestellungs-Rechnung
    def rechnung_aus_bestellung(self, b: Bestellung, kunde_key: str, btb_pool: list[Bautagesbericht]) -> Rechnung:
        kunde = self.kunden[kunde_key]
        r = Rechnung(kunde_key, kunde,
                     mwst_satz=Decimal(str(self.preisliste["mwst_satz"])),
                     zahlungsziel_tage=b.zahlungsziel_tage or kunde.get("zahlungsziel_tage") or self.preisliste["zahlungsziel_tage"])
        quelle = f"Bestellung {b.nummer}"
        r.referenzen = [("Ihre Bestellung", f"{b.nummer} vom {d(b.datum)}" if b.datum else b.nummer)]
        if b.kostenstelle:
            r.referenzen.append(("Kostenstelle", f"{b.kostenstelle} – {b.kostenstelle_text}".strip(" –")))
        if b.ansprechpartner:
            r.referenzen.append(("Ihr Ansprechpartner", b.ansprechpartner))

        tf_satz = self.preisliste["rollen"]["TF"]
        for pos in b.positionen:
            passend = [x for x in btb_pool
                       if x.datum == pos.datum and kunde_finden(x.baufirma, self.kunden) == kunde_key]
            menge = pos.menge
            personen = []
            if passend:
                minuten = 0
                for x in passend:
                    btb_pool.remove(x)
                    r.anlagen.append((x.datei, x.seite))
                    s = self.schicht(x, "TF", x.tf_name, r.hinweise) if ist_eigene_firma(x.tf_firma, self.firma) else None
                    if s:
                        r.schichten.append(s)
                        minuten += sum(s.minuten.values())
                        personen.append(s.person)
                menge = std(minuten)
                if menge > pos.menge:
                    r.hinweise.append(Hinweis(PRUEFEN, quelle,
                                              f"Laut Bautagesbericht {de_zahl(menge)} Std, bestellt waren {de_zahl(pos.menge)} Std – Mehrstunden mit Kunde abstimmen (Nachtrag)."))
            elif b.belege_erforderlich:
                r.hinweise.append(Hinweis(FEHLER, quelle,
                                          f"Kunde verlangt rechnungsbegründende Belege, aber es liegt kein Bautagesbericht vom "
                                          f"{d(pos.datum) if pos.datum else '?'} vor. Bericht in den Eingang legen – dann wird er angehängt "
                                          "und die Ist-Stunden werden übernommen. Bis dahin: Bestellmenge abgerechnet."))

            r.zeilen.append(Rechnungszeile(f"Beauftragung als {pos.funktion or 'TF'}: {pos.leistung}", ist_kopf=True))
            text = f"Leistungsdatum {d(pos.datum)}" if pos.datum else "Leistung"
            if pos.kst:
                text += f"  ·  KST {pos.kst}"
            if personen:
                text += f"  ·  Tf {', '.join(personen)}"
            r.zeilen.append(Rechnungszeile(text, menge, pos.einheit, pos.einzelpreis, tarife.geld(menge * pos.einzelpreis)))
            if pos.datum:
                r.leistung_von = min(filter(None, [r.leistung_von, pos.datum]))
                r.leistung_bis = max(filter(None, [r.leistung_bis, pos.datum]))

            # --- Prüfungen je Position
            mail = next((m for m in b.mail_angaben if m.datum == pos.datum), None)
            if pos.zeitaufwand_std is not None and pos.einheit == "Std" and pos.zeitaufwand_std != pos.menge:
                zusatz = f" und in der Bestell-Mail" if mail and mail.zeitaufwand_std == pos.zeitaufwand_std else ""
                r.hinweise.append(Hinweis(FEHLER, quelle,
                                          f"Bestellmenge {de_zahl(pos.menge)} Std, aber im Positionstext{zusatz} steht „Zeitaufwand: "
                                          f"{de_zahl(pos.zeitaufwand_std, 0)} Stunden“. Vor dem Versand klären (Bautagesbericht / {b.ansprechpartner or 'Kunde'}) "
                                          f"– sonst wird die Rechnung womöglich gekürzt."))
            elif mail and mail.zeitaufwand_std is not None and mail.zeitaufwand_std != pos.menge:
                r.hinweise.append(Hinweis(FEHLER, quelle,
                                          f"Bestellmenge {de_zahl(pos.menge)} Std, in der Bestell-Mail stehen {de_zahl(mail.zeitaufwand_std, 0)} Std."))
            if mail and mail.kst and pos.kst and mail.kst != pos.kst:
                r.hinweise.append(Hinweis(FEHLER, quelle, f"KST in Bestellung {pos.kst}, in der Mail {mail.kst}."))
            if pos.kst and b.kostenstelle and pos.kst != b.kostenstelle:
                r.hinweise.append(Hinweis(PRUEFEN, quelle, f"KST der Position ({pos.kst}) weicht vom Bestellkopf ({b.kostenstelle}) ab."))
            if "azf" in pos.funktion.lower() and not any("azf" in (p.leistung + p.funktion).lower() and p is not pos for p in b.positionen):
                azf = self.preisliste["rollen"]["AZF"]
                r.hinweise.append(Hinweis(PRUEFEN, quelle,
                                          f"Funktion „{pos.funktion}“ bestellt, aber nur ein Stundensatz ({de_zahl(pos.einzelpreis)} €) bepreist. "
                                          f"Falls wir auch den Azf stellen, fehlt eine Position (Preisliste Azf: {de_zahl(Decimal(str(azf['normal']['bis_100km'])))} €/Std, "
                                          f"nachts {de_zahl(Decimal(str(azf['nacht']['bis_100km'])))} €/Std) – Nachtrag beim Kunden anfordern."))
            liste = Decimal(str(tf_satz["normal"]["bis_100km"]))
            liste_weit = Decimal(str(tf_satz["normal"]["ab_100km"]))
            if pos.einzelpreis not in (liste, liste_weit):
                r.hinweise.append(Hinweis(INFO, quelle,
                                          f"Bestellpreis {de_zahl(pos.einzelpreis)} €/Std weicht von der Preisliste ab (Tf {de_zahl(liste)} €, "
                                          f"ab 100 km {de_zahl(liste_weit)} € + Anfahrt). Abgerechnet wird der Bestellpreis."))

        if b.summe_netto is not None and sum(p.gesamtpreis for p in b.positionen) != b.summe_netto:
            r.hinweise.append(Hinweis(PRUEFEN, quelle, "Positionssumme der Bestellung stimmt nicht mit der Bestell-Summe überein."))
        if b.empfaenger and not any(self.firma["strasse"].lower() in z.lower() for z in b.empfaenger):
            r.hinweise.append(Hinweis(PRUEFEN, quelle,
                                      f"Kunde führt uns als „{' / '.join(b.empfaenger[1:4])}“ – unsere Stammdaten: "
                                      f"{self.firma['name']}, {self.firma['strasse']}, {self.firma['plz_ort']}. Adresse beim Kunden aktualisieren lassen?"))
        if b.rechnungsadresse and b.rechnungsadresse[0] != kunde["name"]:
            r.hinweise.append(Hinweis(INFO, quelle,
                                      f"Rechnungsadresse in der Bestellung: „{b.rechnungsadresse[0]}“ – verwendet: „{kunde['name']}“ (kunden.json)."))
        if b.rechnungsadresse and not ist_platzhalter(kunde.get("strasse")) and not any(kunde["strasse"] in z for z in b.rechnungsadresse):
            r.hinweise.append(Hinweis(PRUEFEN, quelle, f"Rechnungsadresse der Bestellung ({', '.join(b.rechnungsadresse)}) ≠ Stammdaten."))
        if b.zahlungsziel_tage and b.zahlungsziel_tage != self.preisliste["zahlungsziel_tage"]:
            r.hinweise.append(Hinweis(INFO, quelle,
                                      f"Kunde gibt {b.zahlungsziel_tage} Tage netto vor (Preisliste: {self.preisliste['zahlungsziel_tage']} Tage) – Bestellbedingung übernommen."))
        if b.rechnung_email:
            r.hinweise.append(Hinweis(INFO, quelle, f"Rechnung mit Bestell-Nr. an {b.rechnung_email} senden."))
        r.anlagen = list(dict.fromkeys(r.anlagen))
        self._kunde_pruefen(r)
        return r

    # ------------------------------------------------------------------ gemeinsame Prüfungen
    def _kunde_pruefen(self, r: Rechnung):
        fehlend = [f for f in PFLICHT_KUNDE if ist_platzhalter(r.kunde.get(f))]
        if fehlend:
            r.hinweise.append(Hinweis(FEHLER, "Stammdaten",
                                      f"Kundenadresse unvollständig ({', '.join(fehlend)}) – in config/kunden.json ergänzen."))

    def firma_pruefen(self):
        fehlend = [f for f in PFLICHT_FIRMA if ist_platzhalter(self.firma.get(f))]
        if fehlend:
            self.allgemein.append(Hinweis(FEHLER, "config/firma.json",
                                          f"Pflichtangaben für Rechnungen fehlen: {', '.join(fehlend)}. Ohne Steuernummer bzw. USt-IdNr. "
                                          "ist die Rechnung nicht ordnungsgemäß (§ 14 UStG) – alle Rechnungen bleiben ENTWURF."))

    def ueberschneidungen(self, rechnungen: list[Rechnung]):
        nach_person = defaultdict(list)
        for r in rechnungen:
            for s in r.schichten:
                nach_person[s.person].append(s)
        for person, schichten in nach_person.items():
            schichten.sort(key=lambda s: s.start)
            for a, b in zip(schichten, schichten[1:]):
                if b.start < a.ende:
                    self.allgemein.append(Hinweis(FEHLER, person,
                                                  f"Doppelt verplant: {a.start:%d.%m. %H:%M}–{a.ende:%H:%M} und {b.start:%d.%m. %H:%M}–{b.ende:%H:%M}."))

    def mail_abdeckung(self, bestellungen: list[Bestellung]):
        bestellt = {(p.datum) for b in bestellungen for p in b.positionen}
        for b in bestellungen:
            for m in b.mail_angaben:
                if m.datum not in bestellt:
                    self.allgemein.append(Hinweis(PRUEFEN, f"Bestell-Mail zu {b.nummer}",
                                                  f"Leistung am {d(m.datum)} ({m.leistung[:60]}…) angefragt, aber keine Bestellung dazu im Eingang."))

    # ------------------------------------------------------------------ Gesamtlauf
    def erstellen(self, btbs: list[Bautagesbericht], bestellungen: list[Bestellung]) -> list[Rechnung]:
        self.firma_pruefen()
        pool = list(btbs)
        rechnungen = []
        for b in sorted(bestellungen, key=lambda b: b.nummer):
            key = kunde_finden(b.besteller, self.kunden) or kunde_finden(" ".join(b.rechnungsadresse), self.kunden)
            if not key:
                self.allgemein.append(Hinweis(FEHLER, b.datei.name, f"Kunde „{b.besteller}“ nicht in config/kunden.json."))
                continue
            rechnungen.append(self.rechnung_aus_bestellung(b, key, pool))
        gruppen = defaultdict(list)
        for btb in pool:
            key = kunde_finden(btb.baufirma, self.kunden)
            if not key:
                self.allgemein.append(Hinweis(FEHLER, btb.bezeichnung, f"Baufirma „{btb.baufirma}“ nicht in config/kunden.json – nicht abgerechnet."))
                continue
            gruppen[key].append(btb)
        for key, liste in gruppen.items():
            rechnungen.append(self.rechnung_aus_btbs(key, liste))
        self.ueberschneidungen(rechnungen)
        self.mail_abdeckung(bestellungen)
        rechnungen.sort(key=lambda r: (r.leistung_von or datetime.max.date(), r.kunde["name"]))
        return rechnungen
