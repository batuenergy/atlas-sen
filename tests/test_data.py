"""Data-invariant tests for the committed atlas bundle.

Run from the repo root: `pytest tests/ -q` (or `make test`).
These guard both correctness and the licensing separation — if point coordinates
ever leak into the committed public/data/atlas.json, `test_no_coordinate_leak` fails.
"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ATLAS = ROOT / "public" / "data" / "atlas.json"
DEMAND = ROOT / "public" / "data" / "demand" / "today.json"


@pytest.fixture(scope="module")
def atlas():
    assert ATLAS.exists(), f"missing {ATLAS} — run `make build` first"
    return json.loads(ATLAS.read_text())


def test_bundle_has_expected_keys(atlas):
    for k in ("P", "H", "R", "T", "REG", "Z", "TZ", "OL", "RP"):
        assert k in atlas, f"atlas.json missing key {k}"


def test_no_coordinate_leak(atlas):
    """Point coordinates must NOT be committed (they are proprietary-geocoded).
    They are spliced in at runtime from coordinates.json. See DATA-LICENSE.md."""
    for p in atlas["P"]:
        assert p[1] is None and p[2] is None, "plant lat/lng leaked into atlas.json"
        assert p[12] is None and p[13] is None, "connection lat/lng leaked into atlas.json"
    for h in atlas["H"]:
        assert h[1] is None and h[2] is None, "substation lat/lng leaked into atlas.json"


def test_regions(atlas):
    assert len(atlas["REG"]) == 10
    # control-region polygons cover the same 10 regions
    assert set(atlas["RP"].keys()) <= set(atlas["REG"])
    assert len(atlas["RP"]) == 10


def test_plants_well_formed(atlas):
    types = set(atlas["T"].keys())
    for p in atlas["P"]:
        assert isinstance(p[0], str) and p[0]
        assert p[4] in types, f"unknown source type {p[4]!r}"
        assert isinstance(p[3], int) and p[3] >= 0   # MW
        assert isinstance(p[-1], str)                # tariff-division tag


def test_transmission_lines(atlas):
    assert len(atlas["OL"]) > 1000
    kvs = set()
    for kv, geom in atlas["OL"]:
        assert isinstance(kv, int) and kv >= 115
        assert len(geom) >= 2 and len(geom[0]) == 2
        kvs.add(kv)
    assert {400, 230, 115} <= kvs


def test_tariff_divisions(atlas):
    assert len(atlas["TZ"]) == 17


def test_demand_snapshot_shape():
    if not DEMAND.exists():
        pytest.skip("no demand snapshot committed")
    d = json.loads(DEMAND.read_text())
    assert "regions" in d and d.get("source") == "CENACE"
    sin = d["regions"].get("Sistema Interconectado Nacional")
    assert sin and isinstance(sin["hourly"], list) and sin["hourly"]
    row = sin["hourly"][0]
    for k in ("hora", "demandaMW", "generacionMW", "pronosticoMW"):
        assert k in row
