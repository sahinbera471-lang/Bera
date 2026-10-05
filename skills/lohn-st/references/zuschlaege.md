# Zuschlagsregeln (Berechnungs-Modus)

Gilt nur, wenn die Excel-Datei **keine** fertigen Zuschlagsspalten hat und das
Skript die Stunden aus Datum, Beginn, Ende und Pause selbst berechnet.
Grundlage sind die steuerfreien Sätze nach § 3b EStG.

| Zuschlagsart | Zeitraum | Satz |
|---|---|---|
| Nachtarbeit | 20:00–24:00 und 04:00–06:00 | 25 % |
| Nachtarbeit (erhöht) | 00:00–04:00, wenn die Schicht vor 0 Uhr begonnen hat | 40 % |
| Nachtarbeit | 00:00–04:00, wenn die Schicht erst nach 0 Uhr begonnen hat | 25 % |
| Sonntagsarbeit | Sonntag 0–24 Uhr | 50 % |
| Feiertagsarbeit | gesetzliche Feiertage 0–24 Uhr | 125 % |
| Silvester | 31.12. ab 14:00 | 125 % |
| Heiligabend, Weihnachten, 1. Mai | 24.12. ab 14:00, 25.12., 26.12., 01.05. | 150 % |

Hinweise:

- Sonn- und Feiertag sowie Nacht sind **unabhängig voneinander**: Eine Stunde
  Sonntag 22 Uhr zählt sowohl als Sonntags- als auch als Nachtstunde
  (so wird es auch in der Lohnabrechnung behandelt – die Sätze addieren sich).
- Feiertag hat Vorrang vor Sonntag: Fällt ein Feiertag auf einen Sonntag,
  zählt die Stunde nur als Feiertagsstunde.
- Arbeit nach Mitternacht wird dem Kalendertag zugerechnet, an dem sie
  tatsächlich stattfindet (Sonntag 23 Uhr bis Montag 6 Uhr → 1 h Sonntag).
- Pausen werden anteilig ans Schichtende gelegt (vereinfachend), d. h. sie
  werden von den letzten Stunden der Schicht abgezogen.
- Feiertage: bundesweite Feiertage immer; mit `--land` zusätzlich die des
  Bundeslandes. Der Betrieb kann tariflich andere Sätze/Zeiten haben – dann
  die Spalten in der Excel-Datei verwenden oder die Ausgabe anpassen.
