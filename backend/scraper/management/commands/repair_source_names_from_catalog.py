"""Restore corrupted Polish diacritics in justice-candidate Source rows,
from the same reviewed literal list that originally created them.

This never guesses replacement letters for a "?" character. Every value it
writes comes from prepare_justice_candidates' own already-reviewed,
committed constants -- the authorised source for these specific rows:

- catalog_notes: all affected rows share one identical literal
  (CANDIDATE_NOTE), so any row whose catalog_notes currently matches the
  known-corrupted form of that exact sentence is repaired to the literal.
- name for NATIONAL_JUSTICE / REGIONAL_PROSECUTORS (16 rows): matched by
  each row's exact, uncorrupted URL, which is unique per institution.
- name for DISTRICT_PROSECUTORS (41 rows, created with url=None so URL
  cannot be used as a key): these were bulk-created in one command run in
  the exact order of the DISTRICT_PROSECUTORS tuple, landing on 41
  consecutive primary keys with no gap. This command only performs that
  positional match when it can first confirm, from the *current* database
  state, that there are exactly 41 such consecutive candidate rows
  immediately following the 16 URL-addressable ones -- if that shape does
  not hold, it refuses and changes nothing rather than mismatch a name.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from news.models import Source
from scraper.management.commands.prepare_justice_candidates import (
    CANDIDATE_NOTE, DISTRICT_PROSECUTORS, NATIONAL_JUSTICE, REGIONAL_PROSECUTORS)

CORRUPTED_NOTE_MARKER = 'Kandydat wymiaru sprawiedliwo'


class Command(BaseCommand):
    help = ('Repair Source.name / catalog_notes corruption for the justice '
            'candidates, restoring only from the already-reviewed catalog literals.')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
            help='Write the corrections; default is a dry-run report.')

    def handle(self, *args, **options):
        apply_changes = options['apply']
        name_fixes = self._plan_name_fixes()
        note_fixes = self._plan_note_fixes()

        for pk, url, old, new in name_fixes:
            action = 'FIXED NAME' if apply_changes else 'WOULD FIX NAME'
            self.stdout.write(f'{action} pk={pk} url={url}: {old!r} -> {new!r}')
        self.stdout.write(f'names: changed={len(name_fixes)}')

        self.stdout.write(f'notes: changed={len(note_fixes)}')

        if apply_changes:
            for pk, _url, _old, new in name_fixes:
                Source.objects.filter(pk=pk).update(name=new)
            Source.objects.filter(pk__in=note_fixes).update(catalog_notes=CANDIDATE_NOTE)

        self.stdout.write('applied' if apply_changes else 'dry_run')

    def _plan_name_fixes(self):
        fixes = []
        for name, url in list(NATIONAL_JUSTICE) + list(REGIONAL_PROSECUTORS):
            source = Source.objects.filter(url=url).first()
            if source is not None and source.name != name:
                fixes.append((source.pk, url, source.name, name))
        fixes.extend(self._plan_district_name_fixes())
        return fixes

    def _plan_district_name_fixes(self):
        national_and_regional_urls = [url for _name, url in
            list(NATIONAL_JUSTICE) + list(REGIONAL_PROSECUTORS)]
        anchor_pks = list(Source.objects.filter(url__in=national_and_regional_urls)
            .order_by('pk').values_list('pk', flat=True))
        if len(anchor_pks) != len(national_and_regional_urls):
            return []  # anchors incomplete; refuse to guess where the district block starts

        expected = len(DISTRICT_PROSECUTORS)
        found = list(Source.objects.filter(
            pk__gt=anchor_pks[-1], catalog_notes__startswith=CORRUPTED_NOTE_MARKER,
        ).order_by('pk').values_list('pk', 'name')[:expected + 1])
        if len(found) != expected:
            return []  # not exactly one candidate row per district prosecutor; refuse
        candidates = found
        pks = [pk for pk, _name in candidates]
        if pks[-1] - pks[0] != expected - 1:
            return []  # candidate rows are not contiguous; refuse rather than mismatch

        fixes = []
        for (pk, current_name), correct_name in zip(candidates, DISTRICT_PROSECUTORS):
            if current_name != correct_name:
                fixes.append((pk, None, current_name, correct_name))
        return fixes

    def _plan_note_fixes(self):
        return list(Source.objects.filter(
            Q(catalog_notes__startswith=CORRUPTED_NOTE_MARKER) & ~Q(catalog_notes=CANDIDATE_NOTE),
        ).values_list('pk', flat=True))
