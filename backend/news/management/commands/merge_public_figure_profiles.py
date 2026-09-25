"""Merge editorially confirmed profiles of the same person (never by name alone).

The registry imports one person from several official rosters: a minister from
KPRM (``kprm-cabinet:*``), the same person as an MP from the Sejm
(``parliamentary:sejm:*``), a party leader from the priority list.  Each pair
below was confirmed by the editor (2026-09-25) as one person.  The MP profile
is kept (it carries the mandate and the official votes); the other profile:

* hands over its roles, the office it currently holds, confirmed material
  references and confirmed entity relations,
* gets its own title recorded as a role when it had no role record,
* is archived with ``merged_into`` set, so roster syncs keep it archived
  (``sync_public_figures`` and ``seed_priority_public_figures`` respect it).

Without ``--apply`` the command only plans; ``--restore --apply`` reverts.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from news.political_models import (PublicFigure, PublicFigureArticleReference, PublicFigureOrganisationRelation,
                                   PublicFigureRole, PublicOffice)

# (profil do połączenia, profil docelowy) — potwierdzone przez redakcję 25.09.2026.
CONFIRMED_PAIRS = (
    ('kprm-cabinet:agnieszka-dziemianowicz-bak', 'parliamentary:sejm:76'),
    ('kprm-cabinet:andrzej-domanski', 'parliamentary:sejm:68'),
    ('kprm-cabinet:barbara-nowacka', 'parliamentary:sejm:263'),
    ('kprm-cabinet:dariusz-klimczak', 'parliamentary:sejm:162'),
    ('kprm-cabinet:jakub-rutnicki', 'parliamentary:sejm:317'),
    ('editorial-priority:jaroslaw-kaczynski', 'parliamentary:sejm:148'),
    ('kprm-cabinet:krzysztof-gawkowski', 'parliamentary:sejm:90'),
    ('kprm-cabinet:marcin-kulasek', 'parliamentary:sejm:201'),
    ('kprm-cabinet:paulina-hennig-kloska', 'parliamentary:sejm:128'),
    ('kprm-cabinet:stefan-krajewski', 'parliamentary:sejm:183'),
    ('kprm-cabinet:w-adys-aw-kosiniak-kamysz', 'parliamentary:sejm:174'),
)


def own_role_key(profile):
    return f'profile-role:{profile.import_key}'


def merge(source, target):
    """Przenosi powiązania `source` do `target` i archiwizuje `source`. Zwraca liczniki."""
    moved = {'roles': 0, 'offices': 0, 'references': 0, 'relations': 0}
    office_roles = source.public_roles.filter(public_office__isnull=False).exists()
    moved['roles'] = source.public_roles.update(public_figure=target)
    moved['offices'] = PublicOffice.objects.filter(current_holder=source).update(current_holder=target)
    # Potwierdzone powiązania: jeśli profil docelowy ma już identyczne, zostaje ono przy profilu archiwalnym
    # (nic nie usuwamy; ograniczenia unikalności obejmują osobę).
    unique_fields = {
        PublicFigureArticleReference: ('article_id', 'reference_kind'),
        PublicFigureOrganisationRelation: ('organisation_id', 'public_role', 'relation_status'),
    }
    for model, key in ((PublicFigureArticleReference, 'references'), (PublicFigureOrganisationRelation, 'relations')):
        for row in model.objects.filter(public_figure=source):
            same = {field: getattr(row, field) for field in unique_fields[model]}
            if model.objects.filter(public_figure=target, **same).exists():
                continue
            row.public_figure = target
            row.save(update_fields=['public_figure'])
            moved[key] += 1
    if office_roles:
        # Rola z urzędem już opisuje tę funkcję — kopia tytułu z wcześniejszej normalizacji byłaby dublem.
        PublicFigureRole.objects.filter(import_key=own_role_key(source)).update(archived=True)
    else:
        PublicFigureRole.objects.update_or_create(import_key=own_role_key(source), defaults={
            'public_figure': target,
            'role_category': source.role_category,
            'role_title': source.role_title,
            'organisation': source.organisation,
            'status': source.status,
            'official_profile_url': source.official_profile_url,
            'evidence_url': source.evidence_url,
            'evidence_note': source.evidence_note,
            'source_checked_at': source.source_checked_at,
            'archived': False,
        })
    source.merged_into = target
    source.archived = True
    source.save(update_fields=['merged_into', 'archived', 'updated_at'])
    return moved


class Command(BaseCommand):
    help = 'Łączy potwierdzone przez redakcję profile tej samej osoby (jawna lista par, nie po nazwisku).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Zapisz zmiany (domyślnie tylko plan).')
        parser.add_argument('--restore', action='store_true', help='Cofnij połączenia z tej listy.')

    def handle(self, *args, **options):
        if options['restore']:
            return self._restore(options['apply'])
        todo = []
        for source_key, target_key in CONFIRMED_PAIRS:
            source = PublicFigure.objects.filter(import_key=source_key).first()
            target = PublicFigure.objects.filter(import_key=target_key, archived=False).first()
            if not source or not target:
                self.stdout.write(f'POMIŃ    {source_key} -> {target_key}: brak profilu źródłowego lub docelowego')
                continue
            if source.merged_into_id == target.pk:
                self.stdout.write(f'GOTOWE   {source.canonical_name}: już połączony z #{target.pk}')
                continue
            if source.canonical_name != target.canonical_name:
                self.stdout.write(f'POMIŃ    {source_key} -> {target_key}: różne nazwy ({source.canonical_name} / {target.canonical_name})')
                continue
            todo.append((source, target))
            self.stdout.write(f'POŁĄCZ   #{source.pk} {source.canonical_name} ({source.role_title}) -> #{target.pk} ({target.role_title})')
        if not options['apply']:
            self.stdout.write(f'PLAN: do połączenia={len(todo)}; bez --apply nie zmieniam bazy.')
            return
        totals = {'roles': 0, 'offices': 0, 'references': 0, 'relations': 0}
        with transaction.atomic():
            for source, target in todo:
                for key, value in merge(source, target).items():
                    totals[key] += value
        self.stdout.write(self.style.SUCCESS(
            f'POŁĄCZONO: {len(todo)}; przeniesione role={totals["roles"]}, urzędy={totals["offices"]}, '
            f'materiały={totals["references"]}, relacje={totals["relations"]}.'))

    def _restore(self, apply):
        keys = [source for source, _ in CONFIRMED_PAIRS]
        rows = list(PublicFigure.objects.filter(import_key__in=keys, merged_into__isnull=False).select_related('merged_into'))
        for source in rows:
            self.stdout.write(f'ROZDZIEL #{source.pk} {source.canonical_name} od #{source.merged_into_id}')
        if not apply:
            self.stdout.write(f'PLAN: do rozdzielenia={len(rows)}; bez --apply nie zmieniam bazy.')
            return
        with transaction.atomic():
            for source in rows:
                target = source.merged_into
                # Role i urzędy z kluczem importu tego profilu wracają do niego; reszta zostaje u docelowego.
                PublicFigureRole.objects.filter(public_figure=target, import_key__contains=f':holder:{source.import_key}').update(public_figure=source)
                for office in PublicOffice.objects.filter(current_holder=target, holder_roles__import_key__contains=f':holder:{source.import_key}').distinct():
                    office.current_holder = source
                    office.save(update_fields=['current_holder'])
                PublicFigureRole.objects.filter(import_key=own_role_key(source), public_figure=target).delete()
                source.merged_into = None
                source.archived = False
                source.save(update_fields=['merged_into', 'archived', 'updated_at'])
        self.stdout.write(self.style.SUCCESS(f'ROZDZIELONO: {len(rows)}.'))
