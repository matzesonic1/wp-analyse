"""Demonstriert die Taktungsanalyse mit synthetischen Betriebsdaten."""

from .analyse.taktung import analysiere_taktung
from .config import Config
from .simulation import simuliere


def main() -> None:
    """Vergleicht die Analyseergebnisse für Normalbetrieb und häufiges Takten."""
    cfg = Config()
    for name, takten in [("Normalbetrieb", False), ("Taktender Betrieb", True)]:
        df = simuliere(tage=3, takten=takten)
        erg = analysiere_taktung(df, cfg)
        print(f"\n== {name} ==")
        print(f"Starts/Tag: {erg.starts_pro_tag}, mittlere Laufzeit: {erg.mittlere_laufzeit_min} min "
              f"-> {erg.bewertung.value}")
        for b in erg.befunde:
            print(f"  [{b.regel_id}] {b.text}")


if __name__ == "__main__":
    main()
