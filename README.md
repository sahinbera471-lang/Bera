# AUSLÄNDERSTADT – AI Follower City

Eine fortlaufend wachsende 3D-Stadt für eine TikTok-Serie. Die Stadt beginnt als kleines Dorf und
wächst mit jedem Follower: **1 neuer Follower = 1.000 € virtuelles Bau-Budget** (reine Spielmechanik,
kein echtes Geld).

Jede Episode ist ein 60-Sekunden-Video im Hochformat (1080 × 1920, 30 FPS), in dem die neuen Gebäude
sichtbar *gebaut* werden: Grundstück vermessen → Straßen → Fundamente → Wände → Dächer → Bäume →
Straßenbeleuchtung → Luftaufnahme bei Sonnenuntergang mit der Frage „WIE GROSS WIRD AUSLÄNDERSTADT?“.

## Schnellstart

```bash
npm install
npm start            # Dashboard: http://localhost:5173
```

Zum Rendern werden `ffmpeg` und ein Chromium für Playwright gebraucht
(`npm i -D playwright && npx playwright install chromium`, falls noch nicht vorhanden).

```bash
npm run render -- 1            # Episode 001 final rendern  -> output/episode_001.mp4
npm run render -- 2 --draft    # schneller Entwurf (540×960, 15 FPS)
npm run still -- bild.jpg --pos=120,90,170 --look=0,0,0     # Standbild des aktuellen Stands
```

## Das Dashboard

| Bereich | Funktion |
|---|---|
| Follower & Bau-Budget | Followerstand manuell eingeben, Budget wird berechnet (gesamt / verbaut / verfügbar) |
| Das kann jetzt gebaut werden | automatische Bauplanung aus dem verfügbaren Budget in der Reihenfolge des Masterplans |
| Stadtteile & Meilensteine | ganze Stadtteile (1.000 / 2.000 / 3.000 / 5.000 / 10.000 / 25.000 Follower) auf einmal bauen |
| Eigenes Gebäude | Typ wählen und per Klick in der 3D-Ansicht auf eine freie Fläche setzen (Kollisions- und Budgetprüfung) |
| Geplant für Episode N | alles, was in der nächsten Episode entsteht; einzeln entfernbar; „Letzten Baufortschritt laden“ |
| TikTok-Episode rendern | Entwurf oder finales MP4 rendern, ansehen und exportieren |

Die 3D-Ansicht links zeigt die echte Stadt (frei drehbar, Tageszeit einstellbar) oder spielt die
Bauanimation der nächsten Episode als Vorschau ab.

## Kontinuität – dieselbe Stadt in jeder Episode

Die Stadt wird nie neu erzeugt. Alles liegt dauerhaft im Repository:

| Datei | Inhalt |
|---|---|
| `city/state.json` | **der** Stadtzustand: Gelände-Seed, Beleuchtung, jede Straße, jedes Gebäude, jeder Baum und jede Laterne mit exakter Position, Ausrichtung, Farben und der Episode, in der es gebaut wurde |
| `city/masterplan.json` | geplante Stadtentwicklung mit festen Positionen für alle Meilensteine |
| `city/history/state_after_ep_NNN.json` | Sicherung des Stands nach jeder fertig gerenderten Episode |
| `episodes/NNN/episode.json` | Timeline der Episode: Bauzeiten, alle Kamerapositionen, Einblendungen |
| `episodes/NNN/voiceover.json` | Voice-over-Datei + Wort-Zeitstempel (optional) |

Eine Episode N zeigt alles mit `episode < N` von Anfang an fertig und animiert nur, was `episode == N`
hat. Die Gebäudemodelle sind prozedural und deterministisch – aus denselben Daten entsteht immer
exakt dieselbe Stadt.

## Ablauf für eine neue Episode

1. `npm start`, aktuellen Followerstand eintragen.
2. „Alles einplanen“ (oder Stadtteil / eigenes Gebäude wählen).
3. „Episoden-Vorschau“ ansehen.
4. Optional Voice-over einbinden (siehe unten).
5. „Episode rendern (MP4)“ – danach ist der Stand festgeschrieben und die nächste Episode baut darauf auf.
6. `city/`, `episodes/` und `output/` committen.

## Voice-over (ElevenLabs)

Das Skript wird unverändert vertont. Aus der Audiodatei und den Wort-Zeitstempeln entstehen
automatisch Untertitel (wichtige Wörter gelb, das gerade gesprochene Wort hervorgehoben), die Musik
weicht der Stimme aus, und die Szenenwechsel werden auf die nächstgelegenen Satzanfänge gelegt:

```bash
npm run voiceover -- 1 --audio pfad/zur/stimme.mp3 --words pfad/zum/timing.json --highlights "AUSLÄNDERSTADT,Follower"
npm run render -- 1
```

`timing.json` darf ein ElevenLabs-Transkript (`{words:[{text,start,end}]}`), ein Alignment
(`characters` + Start-/Endzeiten) oder ein einfaches Array `[{text,start,end}]` sein.

## Technik

- **3D:** Three.js. Gelände, Himmel, Texturen und alle Gebäude werden prozedural erzeugt
  (`web/engine/`). Blender wurde bewusst nicht verwendet: ohne GPU wären 1.800 Bilder pro Episode
  nicht in vertretbarer Zeit renderbar, und so nutzen Dashboard-Vorschau und Video dieselbe Szene.
- **Rendern:** Headless-Chromium zeichnet Bild für Bild deterministisch (`server/render.js`),
  ffmpeg kodiert H.264/AAC. Ohne Grafikkarte (Software-Rendering) dauert eine Episode rund 30 Minuten,
  mit GPU deutlich kürzer.
- **Ton:** Hintergrundmusik und Soundeffekte werden passend zur Timeline synthetisiert
  (`server/audio.js`) – keine fremden Audiodateien, keine Lizenzfragen.

```
city/        dauerhafter Stadtzustand + Masterplan
episodes/    Timeline (und Voice-over) je Episode
output/      fertige MP4s + Titelbilder
server/      Dashboard-Server, Renderer, Tonerzeugung
tools/       Standbild, Benchmark, Voice-over-Import, einmaliger Seed
web/         Dashboard und 3D-Engine
```

`tools/seed.mjs` hat den Grundzustand einmalig erzeugt. Es setzt die Stadt zurück und darf nur mit
`--force` für einen kompletten Neustart benutzt werden.
