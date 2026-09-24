"""Heal already-corrupted Article.title values for one RSS source by
re-fetching its live feed right now and copying the freshly parsed title
back onto the matching, already-imported Article (matched by exact URL).

This is the only kind of "restore a corrupted value" this project allows:
a genuine re-fetch from the same authorised source, never a guessed
substitution. It only ever overwrites a title that currently contains the
"?" mangling marker, and only when the freshly parsed title does not --
otherwise it leaves the row untouched (a still-mangled live fetch would
just reintroduce the same problem, and reports it as no-op instead of
regressing further).

Investigated once for scraper.rss_scraper.upsert_article: that path never
rewrites the title of an Article that already exists by URL, which is
correct for editorial fields, but means once bytes ever hit the database
wrong (this project confirmed, for source 52 in this session, that the
mangling was a one-time historical event and the current fetch_feed ->
feedparser pipeline is clean), a later, healthy re-fetch alone can never
self-heal it. This command is the explicit, reviewed alternative.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

import feedparser

from news.models import Article, Source, SourceAccessInstruction
from scraper.access_gate import approved_instruction
from scraper.utils import fetch_feed
from news.models import FetchAttempt


class Command(BaseCommand):
    help = ('Re-fetch one source\'s RSS feed now and repair already-corrupted '
            'Article.title values for entries matched by exact URL.')

    def add_arguments(self, parser):
        parser.add_argument('source_id', type=int)
        parser.add_argument('--apply', action='store_true',
            help='Write the corrected titles; default is a dry-run report.')

    def handle(self, *args, **options):
        source = Source.objects.filter(pk=options['source_id']).first()
        if source is None:
            raise CommandError(f'no Source with pk={options["source_id"]}')
        if not source.rss_url:
            raise CommandError('source has no rss_url')
        instruction = approved_instruction(source, SourceAccessInstruction.Channel.RSS, source.rss_url)
        if instruction is None:
            raise CommandError('no approved RSS access instruction for this source')

        raw = fetch_feed(source.rss_url, hostname_transport=True, audit_source=source,
            audit_instruction=instruction, requested_kind=FetchAttempt.RequestedKind.FEED)
        feed = feedparser.parse(raw)
        if feed.bozo and not feed.entries:
            raise CommandError('feed did not parse')

        healed, skipped_still_corrupt, no_match = 0, 0, 0
        for entry in feed.entries:
            url = entry.get('link')
            fresh_title = entry.get('title')
            if not url or not fresh_title:
                continue
            article = Article.objects.filter(source=source, url=url).first()
            if article is None:
                no_match += 1
                continue
            if '?' not in article.title:
                continue
            if '?' in fresh_title:
                skipped_still_corrupt += 1
                continue
            self.stdout.write(f'{"HEALED" if options["apply"] else "WOULD HEAL"} '
                f'pk={article.pk}: {article.title!r} -> {fresh_title!r}')
            if options['apply']:
                with transaction.atomic():
                    Article.objects.filter(pk=article.pk).update(title=fresh_title[:500])
            healed += 1
        self.stdout.write(f'{"applied" if options["apply"] else "dry_run"}: '
            f'healed={healed} skipped_still_corrupt_on_refetch={skipped_still_corrupt} no_url_match={no_match}')
