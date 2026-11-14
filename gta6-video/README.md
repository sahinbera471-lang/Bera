# GTA 6 – Das musst du wissen (Kurzvideo)

Hochkant-Video (1080×1920, 30 fps, ca. 93 s) für TikTok / Reels / Shorts.

- `GTA6_Das_musst_du_wissen.mp4` – fertiges Video
- `voiceover/s01.mp3 … s10.mp3` – Sprecheraufnahmen (ElevenLabs, Stimme „Timon“)
- `make_video.py` – rendert Grafiken, Untertitel, Musik und Mix neu: `python3 make_video.py`
  (braucht Python 3 mit Pillow + NumPy, ffmpeg und die Schrift Inter)

## Inhalt
1. GTA 6 erscheint in 6 Tagen
2. Release: Donnerstag, 19.11.2026 (zweimal verschoben)
3. Plattformen: PS5 und Xbox Series X|S, PC noch nicht angekündigt
4. Preis: Standard 79,99 €, Ultimate 99,99 €
5. Story: Leonida / Vice City, Lucia und Jason
6. Tipp: Speicher frei machen, Pre-Load checken
7. Achtung: Krankfeiern kann zur fristlosen Kündigung führen (§ 626 BGB)
8. Schon die Ankündigung „dann bin ich halt krank“ kann reichen, Clips in der Story können als Beweis dienen
9. Besser: Urlaub beantragen, mit dem Chef reden, nach Feierabend zocken
10. Outro mit Call-to-Action

Stand der Infos: 13.11.2026. Inoffizielles Fan-Video, keine Rechtsberatung.

---

# Video 2: GTA 6 – Map, Story & Figuren

Hochkant-Video (1080×1920, 30 fps, ca. 1:23 Min.).

- `GTA6_Map_Story_Figuren.mp4` – fertiges Video
- `voiceover2/s01.mp3 … s10.mp3` – Sprecheraufnahmen (ElevenLabs, Stimme „Timon“)
- `make_video2.py` – rendert das Video neu: `python3 make_video2.py`

Inhalt: Leonida und die Map-Größe (laut Preview-Berichten etwa doppelt so groß wie GTA 5),
die sechs Regionen auf einer **eigenen, illustrierten Luftbild-Karte** (Berge, Sumpf, Felder, Stadt,
Hafen, Inselkette, Straßen, ziehende Wolken, leicht geneigt). Eine offizielle Map gibt es vor dem Release nicht, die Story mit Lucia und Jason, weitere Figuren und das Outro.

**Logo:** An drei Stellen (Intro, „Die Story“, Outro) ist ein Logo-Platz mit Lichteffekt eingebaut.
Lege das offizielle Logo als `assets/logo.png` ab (am besten mit transparentem Hintergrund) und
starte `python3 make_video2.py` neu, dann wird es dort automatisch eingesetzt. Ohne Datei erscheint
ein eigener „GTA 6“-Schriftzug als Platzhalter.

**Echte Karte:** Rockstar stellt die offizielle Leonida-Karte laut eigener Ankündigung am Release-Tag
(19.11.2026) als kostenlosen Download auf rockstargames.com bereit. Lege sie als `assets/map.png`
(oder `.jpg`) ab und starte `python3 make_video2.py` neu: Die Karte ersetzt dann in den Map-Szenen
die eigene Karte, mit langsamem Zoom, und die sechs Regionen erscheinen als Chips darunter.

---

# Serie: 5 weitere Kurzvideos (`serie/`)

Je ca. 1 Minute, hochkant, mit Sprecherstimme und Untertiteln. Rendern mit `python3 make_series.py all`
(oder einzeln: `aktie`, `gta5`, `geschichte`, `rekorde`, `vicecity`).

| Ordner | Video | Thema |
|---|---|---|
| `serie/aktie/` | `GTA6_TakeTwo_Aktie.mp4` | Take-Two-Aktie & GTA 6 (Kursrutsch bei Verschiebungen, +8 % nach Quartalszahlen, Vorbestellungen, Prognose, Risiken – keine Anlageberatung) |
| `serie/gta5/` | `GTA5_Die_Legende.mp4` | GTA 5 bleibt die Legende: 815 Mio. $ in 24 h, 1 Mrd. $ in 3 Tagen, ~235 Mio. verkauft, 3 Konsolen-Generationen, GTA Online |
| `serie/geschichte/` | `GTA_Geschichte_1997-2026.mp4` | Von GTA (1997) bis GTA 6 (2026) mit Zeitstrahl |
| `serie/rekorde/` | `GTA6_Rekorde.mp4` | Trailer-Rekorde (90,4 Mio. / 475 Mio.), 3 Guinness-Rekorde, Vorbestellungen, Vergleich mit GTA 5 |
| `serie/vicecity/` | `Vice_City_2002_vs_2026.mp4` | Vice City damals vs. heute: Zeit, Helden, Map, Technik |

Stand der Infos: 14.11.2026. Inoffizielle Fan-Videos.
