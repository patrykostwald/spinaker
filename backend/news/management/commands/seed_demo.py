"""Dane demonstracyjne do lokalnego audytu interfejsu: komenda idempotentna, bez potoku AI.

Wstawia gotowe, wymyślone treści prosto do modeli (źródła, materiały, nitki, diagnozy, przekazy dnia, wywiady,
Konsylium, raporty tygodnia, osoby publiczne, głosowania Sejmu, newsletter). Uruchamia się wyłącznie na SQLite.
Ponowne uruchomienie nie duplikuje rekordów (stałe klucze: adresy URL, uchwyty, identyfikatory wpisów, slugi).
"""
import hashlib
import json
import random
from datetime import date, timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from news import newsletter, weekly_report
from news.clinic_models import (
    ClinicDailyMessage, ClinicInterview, CouncilCall, CouncilCharterAcceptance, CouncilRecruitment, CouncilSeat,
    InquisitorReview, SpinDiagnosis, SpinOpinion, WeeklyReport,
)
from news.council_charter import charter
from news.council_registry import metadata as council_metadata
from news.management.commands import _seed_demo_content as content
from news.models import (
    Article, Ballot, OfficialRecord, ParliamentaryVoting, Source, SourceAccessInstruction, SourceUsageDecision, Thread,
    ThreadItem,
)
from news.account_models import PersonalContextThread, PersonalContextThreadItem
from news.newsletter_models import NewsletterSubscriber
from news.political_models import (
    ParliamentaryRosterEntry, PoliticalAccount, PoliticalAccountCandidate, PoliticalPost, PublicFigure,
    PublicFigureArticleReference, PublicFigureOrganisationRelation, PublicFigureRole, PublicOffice,
    RegisteredOrganisation, SocialHandleEvidence,
)

NOTE = 'Dane demonstracyjne (seed_demo): treść wymyślona na potrzeby lokalnego audytu interfejsu.'
NEIGHBOUR = {'spin': 'partial', 'partial': 'spin', 'no_spin': 'partial', 'unclear': 'no_spin'}
ROSTER_SOURCES = {'Sejm RP': 'sejm', 'Senat RP': 'senat', 'Parlament Europejski': 'ep'}
ROSTER_PROFILES = {'sejm': 'https://www.sejm.gov.pl/sejm10.nsf/posel.xsp?id=', 'senat': 'https://www.senat.gov.pl/sklad/senatorowie/', 'ep': 'https://www.europarl.europa.eu/meps/pl/'}
STATEMENTS = {
    'OpenAI': 'Przyjmuję zasady Karty; oceniam wpisy tą samą miarą dla obu stron.',
    'Alibaba': 'Przyjmuję Kartę i zobowiązuję się do jawności ocen oraz niezgadywania intencji.',
    'NVIDIA': 'Przyjmuję wszystkie zasady Karty, w tym ujawnianie braków analizy.',
    'Google': 'Przyjmuję Kartę; ocena faktu wymaga źródła, a brak dowodu oznacza „niezweryfikowane”.',
    'Mistral AI': 'Przyjmuję zasady Karty i zasadę równej miary wobec rządzących i opozycji.',
    'SpeakLeash / Cyfronet': 'Przyjmuję Kartę; dbam też o poprawność języka polskiego diagnoz.',
    'Meta': 'Przyjmuję zasady Karty bez zastrzeżeń.',
    'DeepSeek': 'Przyjmuję Kartę i wierne cytowanie wpisów.',
    'Moonshot AI': 'Przyjmuję zasady Karty, w tym prawo do zgłoszenia błędu.',
}


class Command(BaseCommand):
    help = 'Wstawia spójne dane demonstracyjne do lokalnej bazy SQLite (idempotentnie, bez potoku AI).'

    def handle(self, *args, **options):
        if not settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
            raise CommandError('Dane demonstracyjne wolno wstawić tylko do lokalnej bazy SQLite (USE_SQLITE=true).')
        self.now = timezone.now()
        self.stdout.write('Wstawiam dane demonstracyjne…')
        with transaction.atomic():
            self.editor = self.get_editor()
            self.readers = self.get_readers()
            sources = self.seed_sources()
            articles = self.seed_articles(sources)
            self.seed_votings(sources)
            self.seed_threads(articles)
            self.seed_personal_threads(articles)
            self.figures = self.seed_people(articles)
            posts = self.seed_diagnoses(self.figures)
            self.seed_messages(posts)
            self.seed_deleted()
            self.seed_interviews(self.figures)
            self.seed_council()
            self.seed_opinions()
            self.seed_reports()
            self.seed_newsletter()
        self.report()

    # --- pomocnicze ------------------------------------------------------------------------

    def ago(self, hours=0, days=0):
        return self.now - timedelta(hours=hours, days=days)

    def get_editor(self):
        users = get_user_model()
        editor = users.objects.filter(is_staff=True, is_active=True).order_by('pk').first()
        if editor is None:
            editor = users(username='demo_redakcja', is_staff=True, is_active=True)
            editor.set_unusable_password()
            editor.save()
        return editor

    def get_readers(self):
        users = get_user_model()
        result = {}
        for index in range(1, 4):
            user, created = users.objects.get_or_create(username=f'demo_czytelnik{index}', defaults={'is_active': True})
            if created:
                user.set_unusable_password()
                user.save()
            result[user.username] = user
        return result

    # --- źródła i materiały ----------------------------------------------------------------

    def seed_sources(self):
        sources = {}
        for name, url, kind, rss, x_handle, youtube, stage, active, access in content.SOURCES:
            source, _ = Source.objects.update_or_create(url=url, defaults={
                'name': name, 'source_type': kind, 'rss_url': rss, 'x_handle': x_handle, 'youtube_url': youtube,
                'catalog_stage': stage, 'is_active': active, 'scrape_enabled': active, 'catalog_notes': NOTE,
                'last_scraped': self.ago(hours=1) if active else None})
            sources[name] = source
            if access:
                SourceAccessInstruction.objects.get_or_create(source=source, version=1, defaults={
                    'status': 'approved', 'channel': 'api' if kind == 'institution' else 'rss', 'allowed_scope': 'metadata',
                    'endpoint': url, 'terms_url': url, 'evidence': {'note': NOTE}, 'daily_request_cap': 1000,
                    'reviewed_at': self.now, 'reviewed_by': 'seed_demo', 'valid_until': self.now + timedelta(days=365)})
            if name in content.USAGE_CONSENT:
                SourceUsageDecision.objects.get_or_create(source=source, version=1, defaults={
                    'status': 'approved', 'allowed_uses': ['public_card'], 'applies_until_acquired_at': self.now + timedelta(days=365),
                    'frozen_host': urlsplit(url).hostname or '', 'terms_url': url, 'evidence': {'note': NOTE},
                    'reviewed_at': self.now, 'reviewed_by': 'seed_demo'})
        return sources

    def article_url(self, source, slug):
        if 'youtube.com' in source.url:
            return f'https://www.youtube.com/watch?v=demo-{slug}'[:1024]
        return f'{source.url.rstrip("/")}/demo/{slug}'

    def seed_articles(self, sources):
        articles = {}
        for slug, name, category, title, description, hours, author, tags in content.ARTICLES:
            source = sources[name]
            method = {'Sejm Rzeczypospolitej Polskiej': 'sejm', 'ELI — Dziennik Ustaw i Monitor Polski': 'eli'}.get(
                name, 'youtube' if 'youtube.com' in source.url else 'rss' if source.rss_url else 'manual')
            article, _ = Article.objects.update_or_create(url=self.article_url(source, slug), defaults={
                'source': source, 'title': title, 'description': description, 'author': author, 'category': category,
                'tags': tags, 'published_date': self.ago(hours=hours), 'discovered_at': self.ago(hours=max(0, hours - 1)),
                'ingestion_method': method, 'category_reviewed': True, 'evidence_note': NOTE})
            articles[slug] = article
            if method in ('sejm', 'eli'):
                self.official_record(article, method, f'demo/{slug}', category)
        for source in sources.values():
            source.total_articles = source.articles.count()
            source.save(update_fields=['total_articles'])
        return articles

    def official_record(self, article, provider, external_id, category):
        if category == 'parliamentary_print':
            number = article.title.split(':')[0].replace('Druk nr ', '')
            raw = {'number': number, 'title': article.title, 'deliveryDate': article.published_date.date().isoformat(),
                   'attachments': [f'{number}.pdf', f'{number}-uzasadnienie.pdf'], 'status': 'skierowany do komisji'}
        else:
            raw = {'title': article.title, 'status': 'obowiązujący', 'type': 'Ustawa' if 'Ustawa' in article.title else 'Rozporządzenie',
                   'promulgation': article.published_date.date().isoformat()}
        OfficialRecord.objects.update_or_create(provider=provider, external_id=external_id, defaults={
            'article': article, 'api_url': article.url, 'raw_data': raw, 'fetched_at': self.now})

    # --- głosowania Sejmu ------------------------------------------------------------------

    def seed_votings(self, sources):
        source = sources['Sejm Rzeczypospolitej Polskiej']
        mps = [(name, club, mp) for _, name, _, club, _, _, org, mp, _, _ in content.PERSONS
               if mp and ROSTER_SOURCES.get(org) == 'sejm']
        mps += [(f'{first} {last}', club, 91000 + index) for index, (first, last, club) in enumerate(content.EXTRA_MPS)]
        for sitting, number, title, motion, days, yes_clubs in content.VOTINGS:
            rng = random.Random(f'{sitting}-{number}')
            ballots = []
            for name, club, mp_id in mps:
                roll = rng.random()
                if roll < 0.05:
                    vote = 'ABSENT'
                elif club in yes_clubs:
                    vote = 'YES' if roll < 0.94 else 'ABSTAIN'
                else:
                    vote = 'NO' if roll < 0.92 else 'ABSTAIN'
                ballots.append((mp_id, name, club, vote))
            tally = {code: sum(1 for ballot in ballots if ballot[3] == code) for code in ('YES', 'NO', 'ABSTAIN', 'ABSENT')}
            voted = tally['YES'] + tally['NO'] + tally['ABSTAIN']
            counts = {'yes': tally['YES'], 'no': tally['NO'], 'abstain': tally['ABSTAIN'], 'notParticipating': tally['ABSENT'],
                      'present': voted, 'totalVoted': voted, 'majorityType': 'SIMPLE_MAJORITY', 'majorityVotes': (tally['YES'] + tally['NO']) // 2 + 1}
            url = f'https://api.sejm.gov.pl/sejm/term10/votings/{sitting}/{number}'
            published = self.ago(days=days)
            article, _ = Article.objects.update_or_create(url=url, defaults={
                'source': source, 'title': title, 'description': motion, 'category': 'voting', 'published_date': published,
                'discovered_at': published, 'ingestion_method': 'sejm', 'category_reviewed': True, 'tags': ['polityka'],
                'evidence_note': NOTE})
            OfficialRecord.objects.update_or_create(provider='sejm', external_id=f'vote/10/{sitting}/{number}', defaults={
                'article': article, 'api_url': url, 'fetched_at': self.now,
                'raw_data': {'term': 10, 'sitting': sitting, 'votingNumber': number, 'title': title, 'description': motion, **counts}})
            voting, _ = ParliamentaryVoting.objects.update_or_create(term=10, sitting=sitting, number=number, defaults={
                'article': article, 'motion': motion, 'kind': 'ELECTRONIC', 'counts': counts, 'options': []})
            voting.ballots.all().delete()
            Ballot.objects.bulk_create([Ballot(voting=voting, mp_id=mp_id, name=name, club=club, vote=vote)
                                        for mp_id, name, club, vote in ballots])

    # --- nitki -----------------------------------------------------------------------------

    def seed_threads(self, articles):
        for slug, title, kind, slot, featured, description, hours, items in content.THREADS:
            thread, _ = Thread.objects.update_or_create(slug=slug, defaults={
                'title': title, 'thread_type': kind, 'editorial_slot': slot, 'is_featured': featured, 'description': description,
                'published': True, 'views_count': 120 + 37 * len(items)})
            Thread.objects.filter(pk=thread.pk).update(updated_at=self.ago(hours=hours))
            for position, (article_slug, note) in enumerate(items, start=1):
                ThreadItem.objects.update_or_create(thread=thread, article=articles[article_slug],
                                                    defaults={'position': position, 'editorial_note': note})

    def seed_personal_threads(self, articles):
        for username, title, description, items in content.PERSONAL_THREADS:
            thread, _ = PersonalContextThread.objects.get_or_create(owner=self.readers[username], title=title, defaults={
                'description': description, 'is_public': True, 'published_at': self.ago(hours=30)})
            for position, (article_slug, note) in enumerate(items, start=1):
                PersonalContextThreadItem.objects.get_or_create(thread=thread, article=articles[article_slug],
                                                                defaults={'note': note, 'position': position})

    # --- osoby publiczne i konta X ----------------------------------------------------------

    def seed_people(self, articles):
        figure_type = ContentType.objects.get_for_model(PublicFigure)
        figures = {}
        for index, (key, name, camp, club, category, title, organisation, mp_id, handle, followers) in enumerate(content.PERSONS):
            source = ROSTER_SOURCES.get(organisation)
            roster = None
            if mp_id and source:
                national = {'sejm': club, 'senat': club, 'ep': content.EP_GROUPS.get(key, club)}[source]
                roster, _ = ParliamentaryRosterEntry.objects.update_or_create(source=source, external_id=str(mp_id), defaults={
                    'full_name': name, 'club': national, 'profile_url': ROSTER_PROFILES[source] + str(mp_id),
                    'source_url': ROSTER_PROFILES[source], 'term': 10 if source == 'sejm' else None, 'active': True})
            profile = f'https://www.sejm.gov.pl/sejm10.nsf/posel.xsp?id={mp_id}' if source == 'sejm' else (
                ROSTER_PROFILES[source] + str(mp_id) if source else '')
            figure, _ = PublicFigure.objects.update_or_create(import_key=f'demo:{key}', defaults={
                'canonical_name': name, 'role_category': category, 'role_title': title, 'organisation': organisation,
                'status': 'current', 'official_profile_url': profile,
                'evidence_url': profile or 'https://www.gov.pl/web/gmina-przykladowo', 'evidence_note': NOTE,
                'political_alignment': club if source == 'ep' else '', 'source_checked_at': self.ago(days=1 + index % 6),
                'parliamentary_roster_entry': roster})
            figures[key] = figure
            party = content.EP_GROUPS.get(key, club) if source else ''
            PublicFigureRole.objects.update_or_create(import_key=f'demo:{key}:mandat', defaults={
                'public_figure': figure, 'role_category': category, 'role_title': title, 'organisation': organisation,
                'status': 'current', 'official_profile_url': profile, 'evidence_url': figure.evidence_url,
                'evidence_note': NOTE, 'since': date_of('2024-07-16' if source == 'ep' else '2023-11-13'),
                'party': party, 'source_checked_at': self.ago(days=1 + index % 6)})
            if camp:
                self.seed_account(figure, figure_type, camp, name, handle, followers, index)
        for office_title, category, organisation, holder in content.OFFICES:
            key = office_title.lower().replace(' ', '-')
            office, _ = PublicOffice.objects.update_or_create(import_key=f'demo:office:{key}', defaults={
                'title': office_title, 'role_category': category, 'organisation': organisation,
                'official_roster_url': 'https://www.gov.pl/web/premier', 'evidence_note': NOTE, 'current_holder': figures[holder]})
            PublicFigureRole.objects.update_or_create(import_key=f'demo:{holder}:urzad:{key}', defaults={
                'public_figure': figures[holder], 'public_office': office, 'role_category': category, 'role_title': office_title,
                'organisation': organisation, 'status': 'current', 'evidence_url': office.official_roster_url, 'evidence_note': NOTE,
                'since': date_of('2024-01-15'), 'source_checked_at': self.ago(days=2)})
        organisations = {}
        for org_name, krs, kind, sector, legal_form, register in content.ORGANISATIONS:
            organisations[org_name], _ = RegisteredOrganisation.objects.update_or_create(krs_number=krs, defaults={
                'name': org_name, 'kind': kind, 'sector': sector, 'legal_form': legal_form, 'register': register,
                'official_register_url': f'https://prs.ms.gov.pl/krs/demo/{krs}', 'sector_note': NOTE})
        for key, org_name, role, organ, since, until, status in content.RELATIONS:
            PublicFigureOrganisationRelation.objects.update_or_create(
                public_figure=figures[key], organisation=organisations[org_name], public_role=role, relation_status=status,
                defaults={'evidence_url': organisations[org_name].official_register_url, 'evidence_note': NOTE,
                          'verification_status': 'confirmed', 'verification_method': 'public_sources', 'verified_at': self.now,
                          'organ': organ, 'since': date_of(since), 'until': date_of(until) if until else None,
                          'sources': [{'url': organisations[org_name].official_register_url, 'title': f'KRS {organisations[org_name].krs_number} (demo)'}]})
        references = [('kwolinska', 'mention-wolinska', 'speaker'), ('kwolinska', 'tvn24-budzet-deficyt', 'mentioned'),
                      ('pzalewicz', 'mf-komunikat-vat', 'subject'), ('pzalewicz', 'bi-vat', 'mentioned'),
                      ('rkalinowicz', 'zet-wywiad-kalinowicz', 'interviewee'), ('rkalinowicz', 'yt-tvn24-senat', 'subject'),
                      ('bzarzecka', 'republika-ceny-pradu', 'speaker'), ('awrzosek', 'republika-sejm-migracja', 'mentioned'),
                      ('msadowicz', 'wp-migracja-pakt', 'mentioned'), ('jbrzozowicz', 'druk-asystencja', 'subject')]
        for key, slug, kind in references:
            PublicFigureArticleReference.objects.get_or_create(public_figure=figures[key], article=articles[slug], reference_kind=kind, defaults={
                'evidence_note': NOTE, 'verification_status': 'confirmed', 'verified_by': self.editor, 'verified_at': self.now})
        return figures

    def seed_account(self, figure, figure_type, camp, name, handle, followers, index):
        account, _ = PoliticalAccount.objects.update_or_create(handle=handle, defaults={
            'user_id': f'9100000000000{index + 1:04d}', 'display_name': name, 'camp': camp,
            'confirmation_url': figure.evidence_url, 'confirmation_note': NOTE, 'enabled': True,
            'last_polled_at': self.ago(hours=0.3), 'poll_interval_minutes': 15})
        if not account.is_confirmed():
            account.confirm(self.editor)
        candidate, _ = PoliticalAccountCandidate.objects.update_or_create(handle=handle, defaults={
            'display_name': name, 'classification': camp, 'proposed_camp': camp, 'confirmation_url': figure.evidence_url,
            'confirmation_note': NOTE, 'resolved_at': self.now, 'resolved_account': account})
        SocialHandleEvidence.objects.get_or_create(
            subject_content_type=figure_type, subject_object_id=figure.pk, platform='x', handle=handle, defaults={
                'evidence_url': figure.evidence_url, 'extracted_url': f'https://x.com/{handle}',
                'status': 'candidate_created', 'candidate': candidate, 'reviewed_by': self.editor, 'reviewed_at': self.now})
        figure.demo_account, figure.demo_followers = account, followers

    # --- wpisy X i diagnozy ----------------------------------------------------------------

    def make_post(self, post_id, figure, text, published, likes=0, reposts=0, available=True, unavailable_after=None):
        account = figure.demo_account
        defaults = {
            'account': account, 'url': f'https://x.com/{account.handle}/status/{post_id}', 'text': text, 'published_at': published,
            'fetched_at': published + timedelta(minutes=3), 'camp_at_collection': account.camp, 'available': available,
            'response_sha256': hashlib.sha256(text.encode()).hexdigest(), 'media': [],
            'source_data': {'public_metrics': {'like_count': likes, 'retweet_count': reposts, 'reply_count': likes // 12, 'quote_count': reposts // 8}},
            'author_data': {'name': figure.canonical_name, 'profile_image_url': '',
                            'public_metrics': {'followers_count': figure.demo_followers}}}
        if unavailable_after is not None:
            defaults.update(unavailable_at=published + timedelta(hours=unavailable_after),
                            availability_checked_at=published + timedelta(hours=unavailable_after + 1))
        post, _ = PoliticalPost.objects.update_or_create(post_id=str(post_id), defaults=defaults)
        return post

    def council_record(self, index, verdict, intensity):
        rng = random.Random(index)
        members = []
        for step in range(6):
            provider, model, company = content.COUNCIL[(index + step) % len(content.COUNCIL)]
            if step == 5 and index % 4 == 0:
                members.append({'model': model, 'company': company, 'provider': provider, 'role': 'członek',
                                'status': 'brak odpowiedzi', 'note': 'timeout', 'seconds': 60.0})
                continue
            vote = NEIGHBOUR[verdict] if step == 2 and index % 3 == 0 else verdict
            value = max(0, min(100, intensity + rng.randint(-9, 9)))
            members.append({'model': model, 'company': company, 'provider': provider, 'role': 'członek', 'status': 'odpowiedział',
                            'verdict': vote, 'intensity': min(value, 20) if vote == 'no_spin' else value,
                            'seconds': round(rng.uniform(1.2, 9.5), 3)})
        answered = [member for member in members if member['status'] == 'odpowiedział']
        agree = sum(member['verdict'] == verdict for member in answered)
        companies = {member['company'] for member in answered}
        return {'agreement': f'{agree}/{len(answered)}', 'chair': 'gemini-3.8-flash',
                'linguist': 'speakleash/Bielik-11B-v3.0-Instruct:publicai',
                'review': {'ok': True, 'issues': [], 'model': 'nvidia/nemotron-3-super-120b-a12b'},
                'escalated': verdict == 'spin' and intensity >= 70,
                'diversity': {'members': len(answered), 'companies': len(companies), 'polish': any('Bielik' in m['model'] for m in answered),
                              'sufficient': len(answered) >= 4 and len(companies) >= 3, 'polish_required': True, 'degraded': False},
                'members': members}

    def seed_diagnoses(self, figures):
        posts = []
        for index, row in enumerate(content.DIAGNOSES):
            (key, hours, likes, reposts, text, verdict, intensity, headline, summary, analysis, techniques, claims, limitations) = row
            for name, quote, _ in techniques:
                if quote not in text:
                    raise CommandError(f'Cytat techniki „{name}” nie występuje w treści wpisu {index}: {quote}')
            published = self.ago(hours=hours)
            post = self.make_post(1900000000000000100 + index, figures[key], text, published, likes, reposts)
            posts.append(post)
            council = self.council_record(index, verdict, intensity)
            names = ', '.join(member['model'].split('/')[-1] for member in council['members'] if member['status'] == 'odpowiedział')
            SpinDiagnosis.objects.update_or_create(post=post, defaults={
                'status': 'approved', 'verdict': verdict, 'intensity': intensity, 'headline': headline, 'summary': summary,
                'analysis': analysis, 'limitations': limitations,
                'techniques': [{'name': name, 'category': name, 'quote': quote, 'explanation': explanation, 'votes': 2 + index % 3}
                               for name, quote, explanation in techniques],
                'claims': [{'claim': claim, 'assessment': assessment, 'explanation': explanation,
                            'sources': [{'url': source[0], 'title': source[1]}] if source else []}
                           for claim, assessment, explanation, source in claims],
                'lab': {'sentiment': {'status': 'pominięto'}, 'hate_speech': {'status': 'pominięto'}},
                'triage': {'score': min(100, intensity + 20), 'reason': 'Wpis zawiera sprawdzalne twierdzenia i nacechowane sformułowania.',
                           'provider': 'groq', 'model': 'openai/gpt-oss-20b'},
                'screen_score': min(100, intensity + 20), 'provider': 'anthropic', 'model_name': 'konsylium', 'prompt_version': 'v7',
                'usage': {'council': council, 'model': f'konsylium: {names}', 'check_model': 'gemini-3.8-flash'},
                'created_at': published + timedelta(minutes=8), 'diagnosed_at': published + timedelta(minutes=40),
                'reviewed_at': published + timedelta(minutes=41)})
        return posts

    # --- przekazy dnia ---------------------------------------------------------------------

    def seed_messages(self, diagnosed_posts):
        for index, (days, camp, message, analysis, themes, sources) in enumerate(content.MESSAGES):
            moment = self.ago(days=days)
            day = timezone.localtime(moment).date()
            row, _ = ClinicDailyMessage.objects.update_or_create(day=day, camp=camp, defaults={
                'message': message, 'analysis': analysis, 'themes': themes, 'status': 'approved',
                'model_name': 'llama-3.3-70b', 'prompt_version': 'v7', 'usage': {'model': 'llama-3.3-70b'},
                'reviewed_at': moment, 'created_at': moment})
            posts = [post for post in diagnosed_posts if post.camp_at_collection == camp
                     and timezone.localtime(post.published_at).date() == day]
            for offset, (key, text) in enumerate(sources):
                figure = self.figures[key]
                published = timezone.localtime(moment).replace(hour=9 + 3 * offset, minute=10 + index, second=0, microsecond=0)
                post = self.make_post(1900000000000001000 + 2 * index + offset, figure, text, published,
                                      40 + 17 * (index + offset), 6 + index + offset)
                posts.append(post)
                if (index + offset) % 2 == 0 and not SpinDiagnosis.objects.filter(post=post).exists():
                    SpinDiagnosis.objects.create(post=post, status='not_applicable', screen_score=12 + (index * 3) % 20,
                                                 provider='groq', model_name='openai/gpt-oss-20b', prompt_version='v7',
                                                 triage={'score': 12, 'reason': 'Komunikat informacyjny, bez twierdzeń do oceny.',
                                                         'provider': 'groq', 'model': 'openai/gpt-oss-20b'}, created_at=published + timedelta(minutes=6))
            row.posts.set(posts)
        flagged = [('pzalewicz', 'Rząd po raz kolejny udowadnia, że potrafi więcej niż obiecał. Dane mówią same za siebie.', 6),
                   ('awrzosek', 'Każdy rachunek, każda podwyżka, każdy dzień — to koszt rządów koalicji. Dosyć!', 9)]
        for offset, (key, text, hours) in enumerate(flagged):
            post = self.make_post(1900000000000001900 + offset, self.figures[key], text, self.ago(hours=hours), 800, 140)
            SpinDiagnosis.objects.get_or_create(post=post, defaults={
                'status': 'flagged', 'screen_score': 55 + 8 * offset, 'provider': 'groq', 'model_name': 'openai/gpt-oss-20b',
                'prompt_version': 'v7', 'triage': {'score': 55, 'reason': 'Silne sformułowania bez wskazania danych.', 'provider': 'groq'}})

    def seed_deleted(self):
        for index, (key, hours, after) in enumerate(content.DELETED_POSTS):
            self.make_post(1900000000000002000 + index, self.figures[key], '', self.ago(hours=hours), 300, 40,
                           available=False, unavailable_after=after)

    # --- wywiady ---------------------------------------------------------------------------

    def seed_interviews(self, figures):
        for index, row in enumerate(content.INTERVIEWS):
            (days, video, channel, title, key, host, headline, summary, overall, guest, host_row) = row
            person = figures[key]
            moment = self.ago(days=days)
            guest_verdict, guest_intensity, guest_summary, guest_techniques, guest_claims = guest
            host_verdict, host_intensity, host_summary, host_notes = host_row
            ClinicInterview.objects.update_or_create(video_id=video, defaults={
                'day': timezone.localtime(moment).date(), 'url': f'https://www.youtube.com/watch?v={video}', 'title': title,
                'channel': channel, 'thumbnail_url': '', 'guest_name': person.canonical_name, 'guest_role': person.role_title,
                'host_name': host, 'status': 'approved', 'headline': headline, 'summary': summary, 'overall': overall,
                'guest_analysis': {
                    'verdict': guest_verdict, 'intensity': guest_intensity, 'summary': guest_summary,
                    'techniques': [{'name': name, 'category': name, 'quote': quote, 'time': at, 'explanation': explanation}
                                   for name, quote, at, explanation in guest_techniques],
                    'claims': [{'claim': claim, 'time': f'{4 + 5 * number:02d}:{(7 * number) % 60:02d}', 'seconds': (4 + 5 * number) * 60 + (7 * number) % 60,
                                'assessment': assessment, 'explanation': explanation,
                                'sources': [{'url': source[0], 'title': source[1]}] if source else []}
                               for number, (claim, assessment, explanation, source) in enumerate(guest_claims)]},
                'host_analysis': {
                    'verdict': host_verdict, 'intensity': host_intensity, 'summary': host_summary,
                    'notes': [{'name': name, 'category': name, 'quote': quote, 'time': at, 'explanation': explanation}
                              for name, quote, at, explanation in host_notes]},
                'limitations': 'Analiza obejmuje wyłącznie ścieżkę dźwiękową rozmowy; nie oceniono obrazu ani montażu.',
                'transcript': '', 'model_name': 'gemini-3.8-flash + konsylium', 'usage': {}, 'created_at': moment,
                'diagnosed_at': moment + timedelta(hours=2)})

    # --- Konsylium -------------------------------------------------------------------------

    def seed_council(self):
        for provider, model, company in content.COUNCIL:
            CouncilSeat.objects.update_or_create(provider=provider, model=model, defaults={
                'company': company, 'origin': 'config', 'status': 'active', 'last_ok_at': self.ago(hours=0.5)})
        for provider, model, company, roles in content.RECRUITER_SEATS:
            CouncilSeat.objects.update_or_create(provider=provider, model=model, defaults={
                'company': company, 'origin': 'recruiter', 'roles': roles, 'status': 'active',
                'admitted_at': self.ago(days=6), 'last_ok_at': self.ago(hours=1)})
        provider, model, company, error = content.SUSPENDED_SEAT
        CouncilSeat.objects.update_or_create(provider=provider, model=model, defaults={
            'company': company, 'origin': 'config', 'status': 'suspended', 'suspended_at': self.ago(days=2),
            'first_fail_at': self.ago(days=2, hours=3), 'last_error': error})
        for number, (kind, provider, model, company, decision, mode, roles, exam, reason) in enumerate(content.RECRUITMENTS):
            row, created = CouncilRecruitment.objects.get_or_create(kind=kind, provider=provider, model=model, decision=decision, defaults={
                'company': company, 'exam': exam or {}, 'mode': mode, 'roles': roles, 'reason': reason,
                'source': {'context': 128000, 'polish': False, 'new_company': company in ('DeepSeek', 'Moonshot AI'), 'billions': 70},
                'votes': [{'model': member[1], 'admit': decision != 'rejected', 'reason': 'Odpowiedzi egzaminacyjne zgodne z Kartą.'}
                          for member in content.COUNCIL[:4]] if kind == 'candidate' else []})
            if created:
                CouncilRecruitment.objects.filter(pk=row.pk).update(created_at=self.ago(days=1 + 2 * number))
        _, version, digest = charter()
        everyone = [(p, m, c) for p, m, c in content.COUNCIL] + [(p, m, c) for p, m, c, _ in content.RECRUITER_SEATS]
        for provider, model, company in everyone:
            CouncilCharterAcceptance.objects.get_or_create(provider=provider, model=model, charter_version=version, charter_hash=digest, defaults={
                'company': company, 'response': {'accepts': True, 'statement': STATEMENTS.get(company, 'Przyjmuję zasady Karty.')}})
        if not CouncilCall.objects.exists():
            rng = random.Random('council-calls')
            outcomes = ['ok'] * 17 + ['429', 'timeout', 'ok']
            for provider, model, _ in content.COUNCIL:
                for number in range(10):
                    call = CouncilCall.objects.create(provider=provider, model=model, outcome=rng.choice(outcomes),
                                                      seconds=round(rng.uniform(1.0, 14.0), 2))
                    CouncilCall.objects.filter(pk=call.pk).update(created_at=self.ago(hours=rng.uniform(0.2, 70)))
        for index, diagnosis in enumerate(SpinDiagnosis.objects.filter(status='approved').order_by('pk')[:6]):
            members = [council_metadata((provider, model)) for provider, model, _ in content.COUNCIL[index % 4:index % 4 + 2]]
            answers = [content.INQUISITOR_ANSWERS[(index + shift) % 3] if shift == 0 else content.INQUISITOR_ANSWERS[0]
                       for shift in range(2)]
            review, created = InquisitorReview.objects.get_or_create(diagnosis=diagnosis, defaults={
                'camp': diagnosis.post.camp_at_collection, 'reviewers': members, 'answers': answers,
                'verdict': 'ok' if all(all(a.values()) for a in answers) else 'doubt'})
            if created:
                InquisitorReview.objects.filter(pk=review.pk).update(created_at=diagnosis.diagnosed_at + timedelta(hours=6))

    # --- reakcje, raporty, newsletter ------------------------------------------------------

    def seed_opinions(self):
        readers = list(self.readers.values())
        remarks = ['Zgadzam się, wpis podaje liczbę bez punktu odniesienia.', 'Trafna ocena, pomogły źródła pod diagnozą.',
                   'Moim zdaniem zbyt surowo; autor zaznaczył, że to szacunek.', '']
        for index, diagnosis in enumerate(SpinDiagnosis.objects.filter(status='approved').order_by('pk')[:12]):
            for offset, reader in enumerate(readers):
                if (index + offset) % 3 == 2:
                    continue
                polarity = 'negative' if (index + offset) % 5 == 0 else 'positive'
                SpinOpinion.objects.get_or_create(user=reader, diagnosis=diagnosis, defaults={
                    'polarity': polarity, 'body': remarks[(index + offset) % len(remarks)] if polarity == 'positive' or offset == 0 else remarks[2]})

    def seed_reports(self):
        today = timezone.localdate()
        for number, summary in enumerate(content.REPORT_SUMMARIES):
            end = today - timedelta(days=7 * number)
            data = json.loads(json.dumps(weekly_report.build(end), cls=DjangoJSONEncoder))
            WeeklyReport.objects.update_or_create(week_end=end, defaults={
                'week_start': end - timedelta(days=6), 'data': data, 'summary': summary})

    def seed_newsletter(self):
        for number, (email, status, source, days) in enumerate(content.NEWSLETTER, start=1):
            moment = self.ago(days=days)
            NewsletterSubscriber.objects.get_or_create(email=email, defaults={
                'status': status, 'token': f'demo-newsletter-token-{number:02d}-' + 'x' * 24,
                'consent_version': newsletter.CONSENT_VERSION, 'source': source, 'created_at': moment,
                'confirmation_sent_at': moment, 'confirmed_at': moment if status in ('confirmed', 'unsubscribed') else None,
                'unsubscribed_at': self.ago(days=max(0, days - 3)) if status == 'unsubscribed' else None})

    def report(self):
        rows = [('Źródła', Source), ('Materiały', Article), ('Nitki redakcyjne', Thread), ('Pozycje nitek', ThreadItem),
                ('Nitki czytelników', PersonalContextThread), ('Głosowania Sejmu', ParliamentaryVoting), ('Karty głosów', Ballot),
                ('Rekordy urzędowe', OfficialRecord), ('Osoby publiczne', PublicFigure), ('Funkcje (role)', PublicFigureRole),
                ('Konta X', PoliticalAccount), ('Wpisy X', PoliticalPost), ('Diagnozy (wszystkie)', SpinDiagnosis),
                ('Przekazy dnia', ClinicDailyMessage), ('Wywiady', ClinicInterview), ('Miejsca w Konsylium', CouncilSeat),
                ('Rekrutacje', CouncilRecruitment), ('Wywołania Konsylium', CouncilCall), ('Przyjęcia Karty', CouncilCharterAcceptance),
                ('Przeglądy inkwizytora', InquisitorReview), ('Raporty tygodnia', WeeklyReport), ('Reakcje na diagnozy', SpinOpinion),
                ('Subskrybenci newslettera', NewsletterSubscriber)]
        for label, model in rows:
            self.stdout.write(f'  {label}: {model.objects.count()}')
        self.stdout.write(self.style.SUCCESS('Gotowe. Dane są wymyślone i służą tylko do lokalnego audytu.'))


def date_of(value):
    return date.fromisoformat(value)

