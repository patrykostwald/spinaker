"""Dokumenty Sejmu → osoby publiczne (sprint 1 przeszłość.today, punkt D).

Zbieracz (scraper.public_records) zapisuje autorów interpelacji, zapytań i wystąpień po oficjalnym identyfikatorze posła
i od razu szuka osoby w rejestrze. Gdy mandat połączono z osobą później (sync rosterów, scalenie profili), stare wiersze
zostają bez osoby. To zadanie bez sieci dopina je tą samą regułą (scraper.public_records.figure_for): wyłącznie kadencja
i identyfikator Sejmu, nigdy nazwisko. Idempotentne: drugi przebieg nic nie zmienia.
"""
from news.public_records_models import PublicRecordPerson


def link_people(batch=5000):
    from scraper.public_records import figure_for
    linked = cleared = checked = 0
    # posłów jest kilkuset: rozstrzygamy każdą parę (kadencja, id) raz i aktualizujemy wszystkie jej wiersze naraz
    pairs = PublicRecordPerson.objects.filter(figure__isnull=True).values_list('term', 'mp_id').distinct()
    for term, mp_id in pairs[:batch]:
        checked += 1
        figure_id = figure_for(term, mp_id)
        if figure_id:
            linked += PublicRecordPerson.objects.filter(term=term, mp_id=mp_id, figure__isnull=True).update(figure_id=figure_id)
    # osoba zarchiwizowana albo scalona: przepinamy na profil docelowy (tylko gdy jednoznaczny)
    for person in PublicRecordPerson.objects.filter(figure__archived=True).select_related('figure')[:batch]:
        checked += 1
        target = person.figure.merged_into if person.figure.merged_into_id and not person.figure.merged_into.archived else None
        new = target.pk if target else figure_for(person.term, person.mp_id)
        if new != person.figure_id:
            PublicRecordPerson.objects.filter(pk=person.pk).update(figure_id=new)
            if new:
                linked += 1
            else:
                cleared += 1
    # unlinked = stan (wiersze, które nadal nie mają osoby), nie liczba odpiętych w tym przebiegu (te są w cleared)
    return {'checked': checked, 'linked': linked, 'cleared': cleared,
            'unlinked': PublicRecordPerson.objects.filter(figure__isnull=True).count(), 'why_unlinked': why_unlinked()}


def why_unlinked(batch=5000):
    """Dlaczego pary (kadencja, id) zostają bez osoby, zliczone po parach (bez sieci). Reguła łączenia się nie zmienia:
    - not_in_roster: mandatu nie ma na liście (lista Sejmu ma tylko aktywnych posłów: wygasłe mandaty, np. wybrani
      do PE w 2024, albo europoseł spoza listy PE),
    - roster_without_profile: mandat jest, ale nikt nie połączył go z profilem osoby (połączenie sprawdzane ręcznie),
    - ambiguous: mandat pasuje do więcej niż jednego profilu (do scalenia w panelu)."""
    from news.political_models import ParliamentaryRosterEntry
    from scraper.public_records import EP_TERM
    out = {'not_in_roster': 0, 'roster_without_profile': 0, 'ambiguous': 0}
    pairs = PublicRecordPerson.objects.filter(figure__isnull=True).values_list('term', 'mp_id').distinct()
    for term, mp_id in pairs[:batch]:
        if term == EP_TERM:
            entries = ParliamentaryRosterEntry.objects.filter(source='ep', external_id=str(mp_id))
        else:
            entries = ParliamentaryRosterEntry.objects.filter(source='sejm', term=term,
                                                              external_id__in=[str(mp_id), f'{mp_id:03d}'])
        profiles = entries.values_list('public_figure_profiles', flat=True).exclude(public_figure_profiles=None).distinct()
        key = 'not_in_roster' if not entries.exists() else 'roster_without_profile' if not profiles else 'ambiguous'
        out[key] += 1
    return out
