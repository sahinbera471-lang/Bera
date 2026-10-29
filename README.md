# Rechnungsautomat RRB Ruhrrail

Macht aus **Bautagesberichten** und **Kunden-Bestellungen** (PDF) automatisch:

- **Rechnungs-PDFs** mit Logo, Pflichtangaben und den Bautagesberichten als Anlage (gestempelt „Anlage x zu Rechnung …“)
- eine **Stundenliste** (Excel) mit Rechnungen, Schichten je Mitarbeiter und allen Prüfhinweisen
- einen **Prüfbericht** mit allem, was vor dem Versand geklärt werden muss

## So geht's

```bash
pip install -r requirements.txt
# PDFs in den Ordner eingang/ legen, dann:
python -m rechnungsautomat                 # Entwurfslauf (verbraucht keine Rechnungsnummern)
python -m rechnungsautomat --final         # endgültige Nummern vergeben (Zähler in config/firma.json)
python -m rechnungsautomat --datum 31.10.2026
```

Die Ergebnisse landen in `ausgang/`.

## Was das Programm erkennt und rechnet

| Eingang | Ergebnis |
|---|---|
| Bautagesbericht (RRB-Formular, auch mehrere Seiten pro PDF) | Eine Rechnung je Baufirma, abgerechnet nach Preisliste |
| Bestellung mit Bestell-Nr. (z. B. J. Hubert) | Eine Rechnung je Bestellung zum **Bestellpreis**. Liegt ein passender Bautagesbericht vor (gleicher Tag, gleiche Baufirma), werden dessen Ist-Stunden übernommen und der Bericht angehängt. |

**Preislogik** (`config/preisliste.json`):

- Jede Schicht wird minutengenau in Zeitfenster zerlegt. Vorrang: Feiertag (NRW) vor Sonntag vor Nacht (20–06 Uhr) vor normalem Stundensatz.
- Mindestens 8 Stunden pro Schicht.
- Ab 100 km gelten die höheren Sätze plus An- und Abfahrtspauschale. Die Entfernung kommt aus `config/kunden.json` → `_einsatzorte_km`.
- Abgerechnet wird nur eigenes Personal (Firma „RRB“). Fremdpersonal wie der Azf von BDK erscheint nur als Hinweis.
- Fehlt die Ist-Zeit, wird die bestellte Zeit genommen (mit Hinweis). Eine Pause wird anteilig abgezogen.

**Prüfungen**: Die Ampel im Prüfbericht zeigt:

- 🔴 **FEHLER:** blockiert den Versand. Die Rechnung bleibt ENTWURF und bekommt im `--final`-Lauf keine Nummer.
- 🟡 **PRÜFEN:** bitte ansehen.
- ⚪ **INFO:** nur zur Kenntnis.

Geprüft werden unter anderem:

- Bestellmenge ≠ Zeitaufwand im Text bzw. in der Bestell-Mail
- „TF + Azf“ bestellt, aber nur ein Satz bepreist
- fehlende Belege, obwohl der Kunde sie verlangt
- fehlende AG-Gegenzeichnung
- leere Kostenstelle
- Lok gehört einem anderen Kunden als die Baufirma
- veraltete Adresse von uns beim Kunden
- Abweichungen vom Listenpreis
- doppelt verplante Mitarbeiter
- Lücken im Tätigkeitsprotokoll
- fehlende Pflichtangaben nach § 14 UStG

## Einrichten (einmalig)

- `config/firma.json`: Steuernummer, USt-IdNr., Bankverbindung, HRB und Geschäftsführung eintragen. Alles in `[eckigen Klammern]` ist Platzhalter.
- `config/kunden.json`: Kundenadressen (Eiffage fehlt noch), Aliase (Schreibweisen in den Berichten) und Entfernungen zu den Einsatzorten.
- `config/preisliste.json`: Stundensätze. Bei neuer Preisliste hier anpassen.

`eingang/` und `ausgang/` sind per `.gitignore` vom Repo ausgeschlossen, weil sie Personen- und Kundendaten enthalten.

## Tests

```bash
python -m pytest -q
```
