# HaarScan

Haaranalyse im Browser: Foto von Stirn und Oberkopf machen, die App erkennt das Gesicht,
findet den Haaransatz, misst Geheimratsecken in Millimetern und gibt einen Plan mit Tipps,
die durch Studien und Leitlinien gedeckt sind.

## Was gemessen wird

- **Stirnhöhe**: Abstand Augenbrauen → Haaransatz in der Mitte (mm)
- **Geheimratsecken-Tiefe**: wie weit der Haaransatz an den Schläfen höher liegt als in der Mitte (mm, links/rechts)
- **Kopfhaut sichtbar**: Anteil sichtbarer Kopfhaut am Oberkopf/Scheitel (%)
- **Stadium**: geschätzte Norwood-Stufe (Männer) bzw. Ludwig-Stufe (Frauen)

Als Maßstab dient die Iris (bei Erwachsenen ca. 11,7 mm breit). Die Gesichtspunkte liefert
[MediaPipe Face Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker),
der Haaransatz wird per Farbabgleich mit der Stirnhaut gesucht. Die Punkte L, M, R lassen sich
im Bild verschieben, falls die Kante nicht genau getroffen ist. Alles läuft lokal im Browser,
Fotos werden nirgends hochgeladen.

Ein kurzer Fragebogen (Verlauf, Familie, Symptome) grenzt die Ursache ein: erblicher Haarausfall,
Schub-Haarausfall (telogenes Effluvium), kreisrunder Haarausfall, Kopfhautprobleme, Zug-Haarausfall.
Daraus wird eine priorisierte Liste mit Maßnahmen erstellt (Minoxidil, Finasterid, Microneedling,
Blutwerte, Hautarzt, PRP, Laser, Transplantation, Alltag) inklusive Anwendung und Nebenwirkungen.

## Starten

```bash
python3 -m http.server 8000
# dann http://localhost:8000 öffnen
```

Direkt per Doppelklick (`file://`) geht es nicht, weil der Browser dann das Modell nicht laden darf.
Für die Live-Kamera braucht es `localhost` oder HTTPS.

## Dateien

- `index.html` – die komplette App (HTML, CSS, JS)
- `vendor/` – MediaPipe Tasks Vision 0.10.21 (Apache-2.0)
- `models/face_landmarker.task` – Gesichtsmodell von Google MediaPipe (Apache-2.0)

## Hinweis

HaarScan ist keine Diagnose. Verschreibungspflichtige Mittel nur nach Rücksprache mit einer Hautärztin
oder einem Hautarzt.
