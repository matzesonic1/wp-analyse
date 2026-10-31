from wpanalyse.analyse.taktung import analysiere_taktung
from wpanalyse.config import Config
from wpanalyse.models import Bewertung
from wpanalyse.simulation import simuliere


def test_normalbetrieb_ohne_fehlalarm():
    erg = analysiere_taktung(simuliere(tage=3, takten=False), Config())
    assert erg.bewertung == Bewertung.OK
    assert erg.befunde == []


def test_takten_wird_erkannt():
    erg = analysiere_taktung(simuliere(tage=3, takten=True), Config())
    assert erg.bewertung == Bewertung.WARNUNG
    assert erg.starts_pro_tag > 20
    assert erg.befunde[0].regel_id == "A1"
