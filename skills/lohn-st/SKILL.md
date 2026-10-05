---
name: lohn-st
description: "Lohn ST" – macht aus der Excel-Monatsübersicht (AzF Monatsübersicht / Arbeitszeit-Datei) die Ansicht für den Steuerberater. Der obere Teil mit der Übersicht der einzelnen Monate bzw. Tage wird ausgeblendet. Sichtbar bleibt nur der untere Teil mit Urlaub/Konten (Zeitkonto), „Monatsabrechnung für den Steuerberater (Lohnabrechnung)“ und „Weitere Angaben“ (Arbeitsstunden, Zuschläge, Montage, Verpflegung …). Nichts wird gelöscht oder umgerechnet. Verwenden, wenn der Nutzer „Lohn ST“, „für den Steuerberater“, „Steuerberater-Ansicht“, „Lohnabrechnung vorbereiten“ sagt oder die Monatsübersicht so haben will, dass nur der Teil für den Steuerberater zu sehen ist.
---

# Lohn ST – Monatsübersicht für den Steuerberater

**Was der Skill macht:** In der Excel-Monatsübersicht wird alles **oberhalb**
des Steuerberater-Teils **ausgeblendet**. Übrig bleibt nur, was der
Steuerberater für die Lohnabrechnung braucht:

| bleibt sichtbar | wird ausgeblendet |
|---|---|
| Urlaub / Konten (Urlaub, Ansparstunden = Zeitkonto) | Kopfzeile mit Mitarbeiter-Auswahl |
| Monatsabrechnung für den Steuerberater (Arbeitsstunden, Zuschläge Nacht/Sonntag/Feiertag, Urlaub, Krank, Fahrtkosten, Verpflegung/Montage, Summe) | Übersicht aller Monate bzw. Tage (Januar–Dezember, Jahressumme) |
| Weitere Angaben (Urlaubstage, Krankheitstage, Überstunden, Bereitschaft, Montagetage, Resturlaub, Bemerkung) | |

## Wichtig

- **Nichts ändern.** Keine Werte, Formeln, Formatierungen, Auswahllisten
  oder Makros anfassen, nichts löschen, nichts neu berechnen. Nur Zeilen
  ausblenden und den Druckbereich auf den sichtbaren Teil setzen.
- Die Originaldatei bleibt unverändert. Es entsteht eine Kopie
  `<Name>_Steuerberater.xlsx` (bzw. `.xlsm`).
- Die Datei **nicht** mit openpyxl/pandas speichern. Das würde Formeln,
  Auswahllisten oder Makros beschädigen können. Immer das Skript verwenden: Es
  ändert nur die XML-Attribute für „ausgeblendet“ und den Druckbereich.

## Ablauf

1. **Datei nehmen.** Die hochgeladene Excel-Datei (.xlsx/.xlsm) verwenden.
   Kommt nur ein PDF, um die Excel-Datei bitten, denn in einem PDF kann man
   nichts ausblenden.

2. **Skript ausführen** (benötigt `openpyxl`, ggf. `pip install openpyxl`):

   ```bash
   python3 <skill-ordner>/scripts/lohn_st.py "<datei.xlsx>"
   ```

   Optionen:
   - `--ohne-konten`: auch den Block „Urlaub / Konten“ ausblenden, sodass nur
     ab „Monatsabrechnung für den Steuerberater“ sichtbar ist.
   - `--blatt "Name"`: nur dieses Tabellenblatt bearbeiten (mehrfach möglich).
     Ohne Angabe wird jedes Blatt bearbeitet, das den Abschnitt
     „Monatsabrechnung …“ enthält.
   - `--kein-druckbereich`: Druckbereich nicht setzen.
   - `-o <ziel.xlsx>`: anderer Name für die Kopie.

   Das Skript sucht die Überschrift „Urlaub / Konten“ (bzw. „Monatsabrechnung“)
   und blendet alle Zeilen darüber aus. Der Druckbereich wird auf den
   sichtbaren Teil gesetzt, damit ein Ausdruck oder PDF für den Steuerberater
   nur diesen Teil zeigt.

3. **Antwort an den Nutzer** (Deutsch, kurz):
   - Welche Zeilen ausgeblendet wurden und ab wo alles sichtbar bleibt
     (steht in der Ausgabe des Skripts).
   - Die neue Datei zum Herunterladen geben.
   - Hinweis: Zum Wiederherstellen in Excel alles markieren, dann Rechtsklick
     auf die Zeilennummern und „Einblenden“ wählen. Für ein PDF an den
     Steuerberater: Datei → Drucken → „Als PDF speichern“.

Findet das Skript die Überschrift nicht, weil die Datei anders aufgebaut ist,
den Nutzer fragen, ab welcher Überschrift oder Zeile alles sichtbar bleiben
soll. Dann `--blatt` benutzen bzw. das Skript entsprechend aufrufen. Nicht
raten und nichts löschen.
