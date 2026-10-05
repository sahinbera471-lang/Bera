---
name: lohn-st
description: "Lohn ST" – wertet eine Excel-Monatsübersicht / einen Stundenzettel (Tagesbild eines Mitarbeiters) aus, entfernt die tageweise Monatsübersicht und gibt nur noch die zuschlagspflichtigen Stunden aus (Nacht, Sonntag, Feiertag, Samstag, Überstunden usw.). Verwenden, wenn der Nutzer "Lohn ST", "Zuschlagsstunden", "Zuschläge aus der Stundenliste", "nur die Zuschlagsstunden anzeigen" sagt oder eine Excel-Datei (.xlsx/.xlsm) mit Arbeitszeiten eines Monats hochlädt und die Stunden für Zuschläge sehen will.
---

# Lohn ST – Zuschlagsstunden aus der Monatsübersicht

Ziel: Aus einer Excel-Datei mit der Monatsübersicht (eine Zeile pro Tag) wird
eine neue, schlanke Excel-Datei erzeugt, die **nur noch die Stunden pro
Zuschlagsart** zeigt. Die tageweise Übersicht fliegt raus.

Ergebnis pro Mitarbeiter (pro Tabellenblatt):

| Zuschlagsart | Satz | Stunden |
|---|---|---|
| Nachtarbeit 20–24 / 4–6 Uhr | 25 % | 12,50 |
| Nachtarbeit 0–4 Uhr | 40 % | 8,00 |
| Sonntagsarbeit | 50 % | 16,00 |
| Feiertagsarbeit | 125 % | 8,00 |
| … | | |

## Ablauf

1. **Datei finden.** Die hochgeladene Excel-Datei des Nutzers verwenden. Ist
   keine da, kurz danach fragen. Kommt nur eine **PDF** (Ausdruck der
   Excel), um die Original-Excel (.xlsx/.xlsm) bitten – nur dort stehen die
   Werte zuverlässig drin. Ist die PDF lesbar und ausgefüllt, ersatzweise die
   Zuschlagsstunden direkt aus der PDF ablesen und im gleichen Format zeigen.

2. **Skript ausführen** (benötigt `openpyxl`, ggf. `pip install openpyxl`):

   ```bash
   python3 <skill-ordner>/scripts/lohn_st.py "<eingabe.xlsx>" -o "<ausgabe>_Lohn_ST.xlsx"
   ```

   Optionen:
   - `--land BY` – Bundesland-Kürzel für landesspezifische Feiertage
     (BW, BY, BE, BB, HB, HH, HE, MV, NI, NW, RP, SL, SN, ST, SH, TH).
     Ohne Angabe werden nur bundesweite Feiertage berücksichtigt.
   - `--berechnen` – Zuschläge immer selbst aus Datum/Beginn/Ende berechnen,
     auch wenn die Datei schon Zuschlagsspalten hat.
   - `--json` – Ergebnis zusätzlich als JSON auf stdout.

   Das Skript arbeitet in zwei Modi – automatisch pro Tabellenblatt:
   - **Spalten-Modus:** Hat die Tabelle bereits Spalten wie „Nacht“,
     „Sonntag“, „Feiertag“, „Zuschlag“, „Überstunden“, „Samstag“, „Spät“ …,
     werden diese Spalten über den Monat aufsummiert.
   - **Jahresübersicht:** Steht pro Zeile ein Monat (Spalte „Monat“, z. B.
     „AzF Monatsübersicht“ mit „Zuschl. Nacht/Sonntag/Feiertag (Std.)“),
     kommt pro Monat ein eigener Block heraus; leere Monate entfallen.
     Euro-Spalten (Grundlohn, Zuschläge €, Gesamt € …) werden ignoriert.
     Fragt der Nutzer nach einem bestimmten Monat, nur diesen Block zeigen.
   - **Berechnungs-Modus:** Gibt es keine Zuschlagsspalten, aber Datum +
     Beginn + Ende (+ optional Pause), werden die Zuschlagsstunden nach
     § 3b EStG berechnet (Details in `references/zuschlaege.md`).

3. **Ergebnis prüfen.** Die Konsolenausgabe des Skripts lesen. Wenn ein Blatt
   mit „übersprungen“ gemeldet wird oder die Werte unplausibel wirken
   (z. B. 0 Stunden überall, mehr Zuschlagsstunden als Arbeitsstunden), die
   Datei selbst mit openpyxl/pandas ansehen, die richtigen Spalten bestimmen
   und die Summen von Hand bilden – im gleichen Ausgabeformat.

4. **Antwort an den Nutzer** (auf Deutsch, kurz):
   - Pro Mitarbeiter/Blatt die Tabelle „Zuschlagsart | Satz | Stunden“.
   - Link/Pfad zur erzeugten Excel-Datei.
   - Falls im Berechnungs-Modus gerechnet wurde: in einem Satz erwähnen, nach
     welchen Regeln (Nacht 20–6 Uhr, Sonntag, Feiertage inkl. Bundesland).

## Regeln

- Die tageweise Monatsübersicht kommt **nicht** in die Ausgabe – nur die
  Summen je Zuschlagsart (plus Name/Monat, falls in der Datei erkennbar,
  und die Gesamtarbeitsstunden als Bezugsgröße).
- Zuschlagsarten mit 0 Stunden weglassen.
- Stunden immer als Dezimalstunden mit 2 Nachkommastellen (7:30 → 7,50).
- Die Originaldatei nie überschreiben – immer eine neue Datei erzeugen.
