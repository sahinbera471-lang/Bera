"""Gemeinsame Datenstrukturen."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

FEHLER = "FEHLER"    # blockiert den Versand
PRUEFEN = "PRÜFEN"   # bitte ansehen, Rechnung trotzdem erstellt
INFO = "INFO"        # nur zur Kenntnis


@dataclass
class Hinweis:
    stufe: str
    quelle: str
    text: str


@dataclass
class Zugfahrt:
    zug_nr: str
    von_bf: str
    nach_bf: str
    fertigmeldung: str
    abfahrt: str
    ankunft: str


@dataclass
class Taetigkeit:
    von: str
    bis: str
    text: str


@dataclass
class Bautagesbericht:
    datei: Path
    seite: int                      # 0-basiert
    baufirma: str = ""
    logistiker: str = ""
    kostenstelle: str = ""
    bauvorhaben: str = ""
    lok_nr: str = ""
    tf_name: str = ""
    tf_firma: str = ""
    azf_name: str = ""
    azf_firma: str = ""
    tfz_br: str = ""
    tfz_firma: str = ""
    datum: date | None = None
    bestellt_von: str = ""
    bestellt_bis: str = ""
    ist_von: str = ""
    ist_bis: str = ""
    pause_minuten: int = 0
    pause_angekreuzt: str = ""      # "nein", "ja" oder ""
    stunden_angegeben: Decimal | None = None
    betra: list[str] = field(default_factory=list)
    zugfahrten: list[Zugfahrt] = field(default_factory=list)
    taetigkeiten: list[Taetigkeit] = field(default_factory=list)
    vorkommnisse: list[str] = field(default_factory=list)
    ort_datum: str = ""
    unterschrift: str = ""
    ag_gezeichnet: str = ""

    @property
    def bezeichnung(self) -> str:
        d = self.datum.strftime("%d.%m.%Y") if self.datum else "?"
        return f"BTB {d} {self.tf_name} ({self.datei.name} S.{self.seite + 1})"


@dataclass
class Bestellposition:
    menge: Decimal
    einheit: str
    datum: date | None
    einzelpreis: Decimal
    gesamtpreis: Decimal
    leistung: str = ""
    kst: str = ""
    funktion: str = ""
    zeitaufwand_std: Decimal | None = None


@dataclass
class MailAngabe:
    datum: date
    leistung: str = ""
    kst: str = ""
    funktion: str = ""
    zeitaufwand_std: Decimal | None = None


@dataclass
class Bestellung:
    datei: Path
    besteller: str = ""
    nummer: str = ""
    datum: date | None = None
    empfaenger: list[str] = field(default_factory=list)
    kostenstelle: str = ""
    kostenstelle_text: str = ""
    ansprechpartner: str = ""
    ansprechpartner_mobil: str = ""
    positionen: list[Bestellposition] = field(default_factory=list)
    summe_netto: Decimal | None = None
    rechnungsadresse: list[str] = field(default_factory=list)
    zahlungsziel_tage: int | None = None
    rechnung_email: str = ""
    belege_erforderlich: bool = False
    mail_angaben: list[MailAngabe] = field(default_factory=list)


@dataclass
class Schicht:
    """Eine abgerechnete Schicht einer Person (Basis für Rechnung und Stundenliste)."""
    person: str
    rolle: str                       # "TF" oder "AZF"
    start: datetime
    ende: datetime
    pause_minuten: int
    segmente: list[list]             # [kategorie, von, bis, minuten] – nach Pausenabzug
    auffuellung: tuple[str, int] | None   # (kategorie, minuten) bis zur Mindestschichtlänge
    minuten: dict[str, int]          # Kategorie -> Minuten gesamt (inkl. Auffüllung)
    saetze: dict[str, Decimal]       # Kategorie -> €/Std
    einsatzort: str
    km: int | None
    quelle: Bautagesbericht | None = None


@dataclass
class Rechnungszeile:
    text: str
    menge: Decimal | None = None
    einheit: str = ""
    einzelpreis: Decimal | None = None
    betrag: Decimal | None = None
    ist_kopf: bool = False           # Überschriftzeile ohne Betrag


@dataclass
class Rechnung:
    kunde_key: str
    kunde: dict
    nummer: str = ""
    datum: date | None = None
    leistung_von: date | None = None
    leistung_bis: date | None = None
    referenzen: list[tuple[str, str]] = field(default_factory=list)
    zeilen: list[Rechnungszeile] = field(default_factory=list)
    tarif_summen: dict[str, Decimal] = field(default_factory=dict)   # Kategorie -> Stunden
    mwst_satz: Decimal = Decimal("19")
    zahlungsziel_tage: int = 10
    anlagen: list[tuple[Path, int]] = field(default_factory=list)  # (PDF, Seite)
    schichten: list[Schicht] = field(default_factory=list)
    hinweise: list[Hinweis] = field(default_factory=list)
    dateiname: str = ""

    @property
    def netto(self) -> Decimal:
        return sum((z.betrag for z in self.zeilen if z.betrag is not None), Decimal("0"))
