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
    return {'checked': checked, 'linked': linked, 'cleared': cleared,
            'unlinked': PublicRecordPerson.objects.filter(figure__isnull=True).count()}
