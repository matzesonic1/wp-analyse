"""Tests für Zeitfilter, Zustandskonvertierung und Konfiguration des Novelan-Adapters."""

import json
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from wpanalyse.adapters.novelan_ladv9 import NovelanLadv9Adapter


def _antwort(daten):
    """Erzeugt einen dateiähnlichen JSON-Response für den API-Mock."""
    return BytesIO(json.dumps(daten).encode())


def _adapter():
    """Erstellt einen Adapter mit Testzugangsdaten und Beispielentitäten."""
    return NovelanLadv9Adapter(
        ha_url="http://homeassistant.local:8123",
        token="test-token",
        sensoren={
            "aussen_c": "sensor.aussen",
            "verdichter_an": "binary_sensor.verdichter",
        },
    )


def test_lese_ordnet_verlauf_zu_und_filtert_zeitraum():
    """Der Verlauf wird nach Entität zugeordnet und auf [von, bis) begrenzt."""
    verlauf = [
        [
            {"entity_id": "sensor.aussen", "state": "4.5", "last_changed": "2026-01-01T00:00:00+00:00"},
            {"entity_id": "sensor.aussen", "state": "unavailable", "last_changed": "2026-01-01T01:00:00+00:00"},
            {"entity_id": "sensor.aussen", "state": "5.0", "last_changed": "2026-01-01T02:00:00+00:00"},
        ],
        [
            {"entity_id": "binary_sensor.verdichter", "state": "on", "last_changed": "2026-01-01T00:00:00+00:00"},
            {"entity_id": "binary_sensor.verdichter", "state": "off", "last_changed": "2026-01-01T01:00:00+00:00"},
        ],
    ]
    with patch(
        "wpanalyse.adapters.novelan_ladv9.urlopen", return_value=_antwort(verlauf)
    ) as urlopen_mock:
        df = _adapter().lese(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 1, 2, tzinfo=UTC),
        )

    assert list(df.columns) == ["aussen_c", "verdichter_an"]
    assert df.index.tolist() == list(pd.date_range("2026-01-01", periods=2, freq="h", tz="UTC"))
    assert df.loc["2026-01-01T00:00:00Z", "aussen_c"] == 4.5
    assert df.loc["2026-01-01T00:00:00Z", "verdichter_an"]
    assert pd.isna(df.loc["2026-01-01T01:00:00Z", "aussen_c"])
    assert not df.loc["2026-01-01T01:00:00Z", "verdichter_an"]

    request = urlopen_mock.call_args.args[0]
    assert request.get_header("Authorization") == "Bearer " + "test-token"
    query = parse_qs(urlparse(request.full_url).query)
    assert query["filter_entity_id"] == ["sensor.aussen,binary_sensor.verdichter"]
    assert query["end_time"] == ["2026-01-01T02:00:00Z"]


def test_aktuell_liefert_aktuelle_zustaende_und_ignoriert_andere_entitaeten():
    """Aktuelle Werte konfigurierter Entitäten werden aus der API-Antwort gelesen."""
    zustaende = [
        {
            "entity_id": "sensor.aussen",
            "state": "3.2",
            "last_changed": "2026-01-01T00:00:00+00:00",
        },
        {
            "entity_id": "binary_sensor.verdichter",
            "state": "off",
            "last_changed": "2026-01-01T00:01:00+00:00",
        },
        {
            "entity_id": "sensor.andere",
            "state": "99",
            "last_changed": "2026-01-01T00:01:00+00:00",
        },
    ]
    with patch("wpanalyse.adapters.novelan_ladv9.urlopen", return_value=_antwort(zustaende)):
        df = _adapter().aktuell()

    assert len(df) == 2
    assert df.iloc[0]["aussen_c"] == 3.2
    assert df.iloc[1]["verdichter_an"] is False


def test_adapter_benoetigt_ha_zugangsdaten(monkeypatch):
    """Ohne Home-Assistant-URL oder Token schlägt die Initialisierung fehl."""
    monkeypatch.delenv("HA_URL", raising=False)
    monkeypatch.delenv("HA_TOKEN", raising=False)
    with pytest.raises(ValueError, match="HA_URL und HA_TOKEN"):
        NovelanLadv9Adapter(sensoren={"aussen_c": "sensor.aussen"})
