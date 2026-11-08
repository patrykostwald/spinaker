from news import doniesienia_badacz as db
from news import krs


def odpis(names):
    return {'odpis': {'naglowekP': {}, 'dane': {'dzial1': {'danePodmiotu': {
        'nazwa': [{'nazwa': n, 'nrWpisuWprow': str(i + 1)} for i, n in enumerate(names)],
        'formaPrawna': [{'formaPrawna': 'STOWARZYSZENIE', 'nrWpisuWprow': '1'}]},
        'siedzibaIAdres': {'siedziba': {'miejscowosc': 'SZCZECIN'}}}, 'dzial2': {}}}}


def test_parse_collects_former_names_from_full_extract():
    e = krs.parse('0000422794', 'S', odpis(['STOWARZYSZENIE PRZYJACIÓŁ ZDROWIA', 'STOWARZYSZENIE PRZYJACIÓŁ MEDIÓW']))
    assert e.name == 'STOWARZYSZENIE PRZYJACIÓŁ MEDIÓW' and e.former_names == ['STOWARZYSZENIE PRZYJACIÓŁ ZDROWIA']
    assert krs.parse('0000000001', 'S', {'odpis': {'dane': {'dzial1': {'danePodmiotu': {'nazwa': 'X'}}}}}).former_names == []


def test_verify_accepts_a_former_name_with_matching_city_but_not_a_stranger(monkeypatch):
    extract = krs.parse('0000422794', 'S', odpis(['STOWARZYSZENIE PRZYJACIÓŁ ZDROWIA', 'STOWARZYSZENIE PRZYJACIÓŁ MEDIÓW']))
    monkeypatch.setattr(krs, 'fetch_status', lambda number, full=True, timeout=30: (extract, 'ok'))
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)
    ok, why = db.verify_candidate('0000422794', {'organisation_name': 'Stowarzyszenie Przyjaciół Zdrowia', 'city': 'Szczecin'})
    assert ok is extract and why == 'ok'
    ok, why = db.verify_candidate('0000422794', {'organisation_name': 'Stowarzyszenie Przyjaciół Sportu', 'city': 'Szczecin'})
    assert ok is None and 'nazwa niezgodna' in why
