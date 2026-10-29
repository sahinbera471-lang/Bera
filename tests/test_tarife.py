import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from rechnungsautomat import tarife
from rechnungsautomat.abrechnung import Abrechnung, schicht_betrag
from rechnungsautomat.modell import Bautagesbericht

CONFIG = Path(__file__).resolve().parent.parent / "config"
PREISE = json.loads((CONFIG / "preisliste.json").read_text(encoding="utf-8"))


def abrechnung():
    firma = json.loads((CONFIG / "firma.json").read_text(encoding="utf-8"))
    kunden = json.loads((CONFIG / "kunden.json").read_text(encoding="utf-8"))
    return Abrechnung(firma, kunden, PREISE)


def btb(datum, von, bis, pause=0, ort="Plettenberg"):
    return Bautagesbericht(datei=Path("x.pdf"), seite=0, baufirma="Eiffage Infra Rail", tf_name="Test", tf_firma="RRB",
                           datum=datum, ist_von=von, ist_bis=bis, pause_minuten=pause, bauvorhaben=ort)


def test_ostern_und_feiertage_nrw():
    assert tarife.ostersonntag(2026) == date(2026, 4, 5)
    ft = tarife.feiertage(2026, "NW")
    assert ft[date(2026, 11, 1)] == "Allerheiligen"
    assert ft[date(2026, 6, 4)] == "Fronleichnam"
    assert date(2026, 10, 31) not in ft          # Reformationstag nicht in NRW


def test_nachtschicht_samstag_auf_sonntag():
    teile = tarife.segmente(datetime(2026, 10, 24, 22), datetime(2026, 10, 25, 6, 30), PREISE, "NW")
    assert [(k, m) for k, _, _, m in teile] == [("nacht", 120), ("sonntag", 390)]


def test_sonntag_auf_montag_mit_tagstunden():
    teile = tarife.segmente(datetime(2026, 10, 25, 22), datetime(2026, 10, 26, 6, 30), PREISE, "NW")
    assert [(k, m) for k, _, _, m in teile] == [("sonntag", 120), ("nacht", 360), ("normal", 30)]


def test_feiertag_schlaegt_sonntag_und_nacht():
    # 31.10.2026 (Sa) 22:00 -> 01.11.2026 (So, Allerheiligen) 06:00
    teile = tarife.segmente(datetime(2026, 10, 31, 22), datetime(2026, 11, 1, 6), PREISE, "NW")
    assert [(k, m) for k, _, _, m in teile] == [("nacht", 120), ("feiertag", 360)]


def test_pause_wird_anteilig_abgezogen():
    teile = tarife.segmente(datetime(2026, 10, 21, 18), datetime(2026, 10, 22, 2), PREISE, "NW")  # 2h normal, 6h nacht
    netto = tarife.pause_abziehen(teile, 40)
    assert sum(t[3] for t in netto) == 440
    assert tarife.summen(netto) == {"normal": 110, "nacht": 330}


def test_mindestschicht_wird_aufgefuellt():
    s = abrechnung().schicht(btb(date(2026, 10, 21), "08:00", "12:00"), "TF", "Test", [])
    assert s.auffuellung == ("normal", 240)
    assert schicht_betrag(s) == Decimal("656.00")    # 8 Std x 82,00 €


def test_ab_100_km_hoeherer_satz_und_anfahrt():
    ab = abrechnung()
    ab.kunden["_einsatzorte_km"]["Fernort"] = 250
    s = ab.schicht(btb(date(2026, 10, 21), "07:00", "15:00", ort="Fernort"), "TF", "Test", [])
    assert s.saetze["normal"] == Decimal("93.00")
    assert tarife.anfahrt(PREISE, s.km) == Decimal("150.00")


def test_beispielwoche_eiffage():
    """Die 7 Nachtschichten aus den Mustern: 48 Std Nacht, 3 Std Tag, 8,5 Std Sonntag = 5.274,75 € netto."""
    ab = abrechnung()
    summe = sum(schicht_betrag(ab.schicht(btb(date(2026, 10, t), "22:00", "06:30"), "TF", "Test", []))
                for t in range(20, 27))
    assert summe == Decimal("5274.75")


def test_bestellung_uebernimmt_ist_stunden_aus_btb():
    import pytest
    from rechnungsautomat import bestellung
    pdf = CONFIG.parent / "eingang" / "Beauftragung_RRB_TF_Transport_2_DE18_2026-10-Bo-0034.pdf"
    if not pdf.exists():
        pytest.skip("Muster-Bestellung nicht im Eingang")
    b = bestellung.parse_datei(pdf)
    bericht = btb(date(2026, 10, 22), "06:00", "14:30")
    bericht.baufirma = "J. Hubert"
    r = abrechnung().rechnung_aus_bestellung(b, "hubert", [bericht])
    assert r.anlagen == [(Path("x.pdf"), 0)]
    assert r.zeilen[1].menge == Decimal("8.50") and r.netto == Decimal("722.50")   # 8,5 Std x 85,00 €
    texte = " ".join(h.text for h in r.hinweise)
    assert "kein Bautagesbericht" not in texte
    assert "Zeitaufwand: 8 Stunden" in texte                                       # Bestellfehler bleibt gemeldet
