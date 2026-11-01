"""Tests für Arbeitszahlbewertung und Heizstabregel."""

import pandas as pd

from wpanalyse.analyse.effizienz import analysiere_effizienz
from wpanalyse.config import Config
from wpanalyse.models import Bewertung


def _tagesdaten(az: float, aussen_c: float = 0.0, heizstab_an: bool = False) -> pd.DataFrame:
    """Erzeugt einen Tag synthetischer Energie-, Temperatur- und Heizstabwerte."""
    index = pd.date_range("2026-01-10", periods=24, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "waerme_kwh": [az] * 24,
            "strom_kwh": [1.0] * 24,
            "aussen_c": [aussen_c] * 24,
            "heizstab_an": [heizstab_an] * 24,
        },
        index=index,
    )


def test_tages_az_wird_bei_passender_aussentemperatur_berechnet():
    """Eine unauffällige Arbeitszahl wird ohne Befund zurückgegeben."""
    erg = analysiere_effizienz(_tagesdaten(3.3), Config())

    assert erg.tages_az == {"2026-01-10": 3.3}
    assert erg.bewertung == Bewertung.OK
    assert erg.befunde == []


def test_niedrige_az_wird_abhaengig_von_aussentemperatur_bewertet():
    """Die gleiche Arbeitszahl wird bei milderem Wetter strenger bewertet."""
    kalter_tag = analysiere_effizienz(_tagesdaten(2.3, aussen_c=-10.0), Config())
    milder_tag = analysiere_effizienz(_tagesdaten(2.3, aussen_c=10.0), Config())

    assert kalter_tag.bewertung == Bewertung.OK
    assert milder_tag.bewertung == Bewertung.WARNUNG
    assert milder_tag.befunde[0].regel_id == "A2"


def test_heizstab_bei_milden_temperaturen_wird_gemeldet():
    """Heizstabeinsatz oberhalb des Außentemperaturgrenzwerts wird gemeldet."""
    erg = analysiere_effizienz(_tagesdaten(3.3, aussen_c=0.0, heizstab_an=True), Config())

    assert erg.bewertung == Bewertung.WARNUNG
    assert erg.befunde[0].regel_id == "A4"


def test_heizstab_am_grenzwert_loest_keine_warnung_aus():
    """Der Heizstab löst genau am konfigurierten Grenzwert keinen Befund aus."""
    erg = analysiere_effizienz(_tagesdaten(3.3, aussen_c=-5.0, heizstab_an=True), Config())

    assert erg.bewertung == Bewertung.OK
    assert erg.befunde == []


def test_ohne_waermeenergie_nur_heizstabregel_und_hinweis():
    """Fehlende Wärmeenergie verhindert die AZ, nicht aber die Heizstabprüfung."""
    df = _tagesdaten(3.3, aussen_c=0.0, heizstab_an=True).drop(columns="waerme_kwh")
    df["waerme_w"] = 1200.0

    erg = analysiere_effizienz(df, Config())

    assert erg.tages_az == {}
    assert erg.bewertung == Bewertung.WARNUNG
    assert {befund.regel_id for befund in erg.befunde} == {"A2", "A4"}
    assert any("AZ nicht berechenbar" in befund.text for befund in erg.befunde)
