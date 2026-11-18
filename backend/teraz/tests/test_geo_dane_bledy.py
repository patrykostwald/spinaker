"""Błędy w treści plików danych geokodera zawsze jako `BladDanych` (trzecia recenzja, P3), nie surowe TypeError itp."""

import json
import shutil

import pytest

pytest.importorskip("shapely")

from teraz import geo  # noqa: E402
from teraz.geo import granice, slownik as sl  # noqa: E402


@pytest.fixture
def kopia_danych(tmp_path):
    katalog = tmp_path / "dane"
    shutil.copytree(sl.DANE, katalog)
    return katalog


def test_sprawdz_dane_niehashowalny_kod_w_granicach_to_blad_danych(kopia_danych):
    plik = kopia_danych / "granice_powiaty.geojson"
    dane = json.loads(plik.read_text(encoding="utf-8"))
    dane["features"][0]["properties"]["kod"] = [1, 2]  # lista nie jest hashowalna: surowy TypeError przy zbiorze kodów
    plik.write_text(json.dumps(dane), encoding="utf-8")
    with pytest.raises(geo.BladDanych, match=r"granice_powiaty\.geojson"):
        geo.sprawdz_dane(kopia_danych)


@pytest.mark.parametrize("zmiana", [
    lambda s: s.__setitem__("wojewodztwa", 5),  # nie da się iterować
    lambda s: s["gminy"].__setitem__(0, [1, 2]),  # za krótki wiersz
    lambda s: s["gminy"][0].__setitem__(0, ["0201011"]),  # kod jako lista (niehashowalny)
])
def test_slownik_zly_typ_lub_uklad_to_blad_danych(kopia_danych, zmiana):
    surowe = json.loads((kopia_danych / "teryt.json").read_text(encoding="utf-8"))
    zmiana(surowe)
    (kopia_danych / "teryt.json").write_text(json.dumps(surowe), encoding="utf-8")
    with pytest.raises(geo.BladDanych, match=r"teryt\.json"):
        geo.sprawdz_dane(kopia_danych)


@pytest.mark.parametrize("geometria", [
    {"type": "Polygon", "coordinates": [[[0, 0]]]},  # za mało punktów: błąd shapely
    {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 1], [0, 0]], "x"]},
    {"type": "Nieznany", "coordinates": []},
])
def test_warstwa_granic_blad_shapely_to_blad_danych(kopia_danych, monkeypatch, geometria):
    plik = kopia_danych / "granice_powiaty.geojson"
    dane = json.loads(plik.read_text(encoding="utf-8"))
    dane["features"][0]["geometry"] = geometria
    plik.write_text(json.dumps(dane), encoding="utf-8")
    monkeypatch.setattr(granice, "DANE", kopia_danych)
    with pytest.raises(geo.BladDanych, match=r"granice_powiaty\.geojson: zły układ danych"):
        granice._Warstwa("granice_powiaty.geojson")


def test_zbuduj_dane_wymaga_daty_stanu(tmp_path, capsys):
    from teraz.geo import zbuduj_dane

    with pytest.raises(SystemExit) as wyjscie:
        zbuduj_dane.main([str(tmp_path)])  # bez --stan atrybucja dostałaby starą datę
    assert wyjscie.value.code == 2
    assert "--stan" in capsys.readouterr().err
