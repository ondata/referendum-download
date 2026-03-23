"""Test per referendum_download.py."""

import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest
import requests

from referendum_download import (
    api_get,
    decode_cod,
    export_flat,
    flatten_record,
    get_scrutini_provincia,
    get_scrutini_regione,
    parse_url,
)


# ---------------------------------------------------------------------------
# parse_url
# ---------------------------------------------------------------------------

def test_parse_url_date_only():
    assert parse_url("20250608") == "20250608"


def test_parse_url_full_url():
    url = "https://elezioni.interno.gov.it/risultati/20250608/referendum/scheda1"
    assert parse_url(url) == "20250608"


def test_parse_url_invalid():
    with pytest.raises(ValueError):
        parse_url("non-una-data")


# ---------------------------------------------------------------------------
# decode_cod
# ---------------------------------------------------------------------------

def test_decode_cod():
    reg, prov, com = decode_cod("010020034")
    assert reg == "01"
    assert prov == "002"
    assert com == "0034"


# ---------------------------------------------------------------------------
# flatten_record
# ---------------------------------------------------------------------------

SCRUTINI_RECORD = {
    "livello": "comune",
    "area": "italia",
    "cod": "010020034",
    "cod_reg": "01",
    "cod_prov": "002",
    "cod_com": "0034",
    "data": {
        "int": {
            "desc_com": "Comune Test",
            "desc_prov": "Provincia Test",
            "desc_reg": "Regione Test",
            "ele_m": 1000,
            "ele_f": 1100,
            "ele_t": 2100,
            "sz_tot": 5,
        },
        "scheda": [
            {
                "cod": "1",
                "sz_perv": 5,
                "vot_m": 700,
                "vot_f": 750,
                "vot_t": 1450,
                "perc_vot": "69.05",
                "sk_bianche": 10,
                "sk_nulle": 5,
                "sk_contestate": 0,
                "voti_si": 900,
                "voti_no": 535,
                "perc_si": "62.72",
                "perc_no": "37.28",
            },
            {"cod": "2", "sz_perv": 5, "vot_t": 1400},
        ],
    },
}


def test_flatten_record_returns_one_row_per_scheda():
    rows = flatten_record(SCRUTINI_RECORD)
    assert len(rows) == 2


def test_flatten_record_fields():
    rows = flatten_record(SCRUTINI_RECORD)
    r = rows[0]
    assert r["cod"] == "010020034"
    assert r["area"] == "italia"
    assert r["livello"] == "comune"
    assert r["cod_reg"] == "01"
    assert r["quesito_cod"] == "1"
    assert r["elettori_t"] == 2100
    assert r["voti_si"] == 900
    assert r["perc_si"] == "62.72"


def test_flatten_record_missing_optional_fields():
    rows = flatten_record(SCRUTINI_RECORD)
    r = rows[1]
    assert r["quesito_cod"] == "2"
    assert r["voti_si"] == ""


def test_flatten_record_estero():
    record = {
        "livello": "nazionale",
        "area": "estero",
        "cod": "estero",
        "data": {
            "int": {"ele_t": 500000, "sz_tot": 100},
            "scheda": [{"cod": "1", "vot_t": 200000}],
        },
    }
    rows = flatten_record(record)
    assert len(rows) == 1
    assert rows[0]["area"] == "estero"
    assert rows[0]["cod_reg"] == ""
    assert rows[0]["cod_com"] == ""


# ---------------------------------------------------------------------------
# api_get
# ---------------------------------------------------------------------------

def test_api_get_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"enti": []}
    mock_resp.raise_for_status = MagicMock()
    session = MagicMock()
    session.get.return_value = mock_resp

    result = api_get("test/endpoint", session)
    assert result == {"enti": []}


def test_api_get_http_error():
    session = MagicMock()
    session.get.return_value.raise_for_status.side_effect = requests.HTTPError("404")

    with pytest.raises(requests.HTTPError):
        api_get("test/endpoint", session)


def test_api_get_network_error():
    session = MagicMock()
    session.get.side_effect = requests.ConnectionError("timeout")

    with pytest.raises(requests.ConnectionError):
        api_get("test/endpoint", session)


def test_api_get_api_error_in_response():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"Error": "Dati non disponibili"}
    mock_resp.raise_for_status = MagicMock()
    session = MagicMock()
    session.get.return_value = mock_resp

    with pytest.raises(RuntimeError, match="API error"):
        api_get("test/endpoint", session)


def test_api_get_invalid_json():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.side_effect = ValueError("No JSON")
    session = MagicMock()
    session.get.return_value = mock_resp

    with pytest.raises(ValueError):
        api_get("test/endpoint", session)


# ---------------------------------------------------------------------------
# export_flat
# ---------------------------------------------------------------------------

def test_export_flat_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        scrutini_file = os.path.join(tmpdir, "scrutini.jsonl")
        flat_file = os.path.join(tmpdir, "scrutini_flat.jsonl")

        with open(scrutini_file, "w") as f:
            f.write(json.dumps(SCRUTINI_RECORD, ensure_ascii=False) + "\n")

        count = export_flat(scrutini_file, flat_file)
        assert count == 2

        with open(flat_file) as f:
            rows = [json.loads(line) for line in f]

        assert len(rows) == 2
        assert rows[0]["quesito_cod"] == "1"
        assert rows[1]["quesito_cod"] == "2"


def test_flatten_record_regione():
    record = {
        "livello": "regione",
        "area": "italia",
        "cod": "010000000",
        "cod_reg": "01",
        "cod_prov": "",
        "cod_com": "",
        "data": {
            "int": {"desc_reg": "PIEMONTE", "ele_t": 3300000, "sz_tot": 4790},
            "scheda": [{"cod": 1, "voti_si": 700000, "voti_no": 800000}],
        },
    }
    rows = flatten_record(record)
    assert len(rows) == 1
    assert rows[0]["livello"] == "regione"
    assert rows[0]["cod_reg"] == "01"
    assert rows[0]["cod_prov"] == ""
    assert rows[0]["cod_com"] == ""
    assert rows[0]["desc_reg"] == "PIEMONTE"
    assert rows[0]["desc_prov"] == ""
    assert rows[0]["desc_com"] == ""


def test_flatten_record_provincia():
    record = {
        "livello": "provincia",
        "area": "italia",
        "cod": "010020000",
        "cod_reg": "01",
        "cod_prov": "002",
        "cod_com": "",
        "data": {
            "int": {"desc_prov": "ALESSANDRIA", "desc_reg": "PIEMONTE", "ele_t": 313000, "sz_tot": 535},
            "scheda": [{"cod": 1, "voti_si": 82000, "voti_no": 75000}],
        },
    }
    rows = flatten_record(record)
    assert len(rows) == 1
    assert rows[0]["livello"] == "provincia"
    assert rows[0]["cod_prov"] == "002"
    assert rows[0]["cod_com"] == ""
    assert rows[0]["desc_prov"] == "ALESSANDRIA"
    assert rows[0]["desc_com"] == ""


def test_get_scrutini_regione():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"int": {"cod_reg": 1}, "scheda": []}
    mock_resp.raise_for_status = MagicMock()
    session = MagicMock()
    session.get.return_value = mock_resp

    result = get_scrutini_regione("20260322", "01", session)
    assert result == {"int": {"cod_reg": 1}, "scheda": []}
    called_url = session.get.call_args[0][0]
    assert "RE/01" in called_url
    assert "PR/" not in called_url


def test_get_scrutini_provincia():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"int": {"cod_prov": 2}, "scheda": []}
    mock_resp.raise_for_status = MagicMock()
    session = MagicMock()
    session.get.return_value = mock_resp

    result = get_scrutini_provincia("20260322", "01", "002", session)
    assert result == {"int": {"cod_prov": 2}, "scheda": []}
    called_url = session.get.call_args[0][0]
    assert "RE/01/PR/002" in called_url
    assert "CM/" not in called_url


def test_export_flat_empty_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        scrutini_file = os.path.join(tmpdir, "scrutini.jsonl")
        flat_file = os.path.join(tmpdir, "scrutini_flat.jsonl")
        open(scrutini_file, "w").close()

        count = export_flat(scrutini_file, flat_file)
        assert count == 0
