"""Archiwum spinek: wyłącznie SELECT, zero zapisów w bazie i wywołań sieci.

Eksport jest pseudonimizacją, nie pełną anonimizacją treści publicznych.
Manifest powstaje na końcu; jego brak oznacza niedokończone archiwum.
"""
import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, models
from django.utils import timezone


VERSION = 1
BATCH = 500
EMAIL = re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w.-]+", re.UNICODE)
# Jawna lista tekstów technicznych. Pozostałe teksty/JSON nie trafiają do archiwum.
TECH = set('kind signal_kind polarity role link_kind part status result action rule '
           'target_kind reason mode consent_version'.split()) - {'reason'}
CONTENT = {
    'PersonalContextThread': ('title', 'description'),
    'PersonalContextThreadItem': ('note', 'link_note', 'box_data'),
    'Thread': ('title', 'description'),
    'ThreadItem': ('editorial_note',),
    'ThreadOpinion': ('body',),
    'CommunityThreadOpinion': ('body',),
    'ThreadComment': ('body',),
    'CommunityLink': ('title',),
}


def model(name):
    return apps.get_model('news', name)


def scopes():
    names = ('PersonalContextThread PersonalContextThreadItem Thread ThreadItem '
             'ThreadOpinion ThreadFavorite CommunityThreadOpinion CommunityThreadReport '
             'ThreadComment ThreadCommentReaction ThreadRateEvent ThreadStepReaction '
             'ThreadReview ThreadReviewRound ThreadModerationReport '
             'ThreadModerationDecision ThreadModerationMail').split()
    rows = {name: model(name).objects.all() for name in names}
    rows['PersonalContextThread_sources'] = model('PersonalContextThread').sources.through.objects.all()
    rows['CommunityLink'] = model('CommunityLink').objects.filter(
        pk__in=model('PersonalContextThreadItem').objects.values('link_id'))
    rows['CommentReport'] = model('CommentReport').objects.filter(thread_opinion__isnull=False)
    rows['Follow'] = model('Follow').objects.filter(thread__isnull=False)
    rows['NotificationSettings'] = model('NotificationSettings').objects.filter(push_thread_replies=True)
    rows['Notification'] = model('Notification').objects.filter(
        kind__in=['followed_thread', 'thread_reply', 'report_status'])
    rows['NotificationPost'] = model('NotificationPost').objects.filter(
        notification__in=rows['Notification'])
    rows['NotificationEvent'] = model('NotificationEvent').objects.filter(
        kind__in=['thread', 'thread_comment', 'reply', 'moderation'])
    rows['PushSubscription'] = model('PushSubscription').objects.all()
    rows['PushEvent'] = model('PushEvent').objects.filter(key__startswith='dr-spin:')
    return rows


def fields_for(queryset):
    name = queryset.model.__name__
    return [f for f in queryset.model._meta.concrete_fields
            if f.is_relation or isinstance(f, (models.IntegerField, models.BooleanField,
                                               models.DateTimeField, models.DateField))
            or f.name in TECH or f.name in CONTENT.get(name, ())
            or (name == 'PushSubscription' and f.name == 'topics')]


def records(queryset):
    fields = fields_for(queryset)
    for row in queryset.order_by('pk').values(*[f.attname for f in fields]).iterator(chunk_size=BATCH):
        if queryset.model.__name__ == 'PushSubscription':
            if 'nitki-dr-spina' not in (row.get('topics') or []):
                continue
            row['topics'] = ['nitki-dr-spina']
        yield row


def counts(rows):
    result = {name: (sum(1 for _ in records(qs)) if name == 'PushSubscription' else qs.count())
              for name, qs in rows.items()}
    result['PersonalContextThread.publiczne'] = rows['PersonalContextThread'].filter(is_public=True).count()
    result['PersonalContextThread.prywatne'] = rows['PersonalContextThread'].filter(is_public=False).count()
    result['Thread.publiczne'] = rows['Thread'].filter(published=True).count()
    result['Thread.prywatne'] = rows['Thread'].filter(published=False).count()
    return result


def public_content(name, row):
    public = model('PersonalContextThread').objects.filter(is_public=True, hidden_at__isnull=True)
    editorial = model('Thread').objects.filter(published=True)
    if name == 'PersonalContextThread':
        return row['is_public'] and row['hidden_at'] is None
    if name == 'Thread':
        return row['published']
    if name in ('PersonalContextThreadItem', 'CommunityThreadOpinion', 'ThreadComment'):
        return (not row.get('hidden_at') and not row.get('deleted_at')
                and public.filter(pk=row['thread_id']).exists())
    if name in ('ThreadItem', 'ThreadOpinion'):
        return editorial.filter(pk=row['thread_id']).exists()
    if name == 'CommunityLink':
        return not row['hidden_at'] and model('PersonalContextThreadItem').objects.filter(
            link_id=row['id'], thread__in=public).exists()
    return False


def pseudonym(salt, value):
    return hmac.new(salt.encode('utf-8'), f'user:{value}'.encode('utf-8'), hashlib.sha256).hexdigest()


def scrub(value):
    if isinstance(value, str):
        return EMAIL.sub('[email ukryty]', value)
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, dict):
        return {scrub(k): scrub(v) for k, v in value.items()}
    return value


def export_row(name, qs, row, salt):
    if not public_content(name, row):
        for key in CONTENT.get(name, ()):
            row.pop(key, None)
    # Nie pobieramy haseł ani tokenów. Pamięć ograniczona do paczki użytkowników.
    # Nazwy kont w publicznych tekstach zastępujemy tym samym pseudonimem.
    content_keys = [key for key in CONTENT.get(name, ()) if key in row]
    if content_keys:
        for key in content_keys:
            row[key] = scrub(row[key])
        user_model = get_user_model()
        identity_fields = [key for key in ('username', 'first_name', 'last_name')
                           if key in {f.name for f in user_model._meta.fields}]
        for user in user_model.objects.values('pk', *identity_fields).iterator(chunk_size=BATCH):
            replacement = '[user:' + pseudonym(salt, user['pk']) + ']'
            for key in content_keys:
                row[key] = mask_names(row[key], [user[f] for f in identity_fields], replacement)
    for field in fields_for(qs):
        if field.is_relation and field.related_model._meta.label_lower == settings.AUTH_USER_MODEL.lower():
            value = row.pop(field.attname)
            row[field.name + '_hash'] = pseudonym(salt, value) if value is not None else None
    return scrub(row)


def mask_names(value, names, replacement):
    if isinstance(value, str):
        for name in sorted((n for n in names if n), key=len, reverse=True):
            value = re.sub(r'(?<!\w)' + re.escape(name) + r'(?!\w)', lambda _: replacement,
                           value, flags=re.IGNORECASE)
        return value
    if isinstance(value, list):
        return [mask_names(v, names, replacement) for v in value]
    if isinstance(value, dict):
        return {mask_names(k, names, replacement): mask_names(v, names, replacement)
                for k, v in value.items()}
    return value


class Command(BaseCommand):
    help = 'Liczby lub pseudonimizowane archiwum spinek. Baza tylko do odczytu.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--tylko-liczby', action='store_true')
        group.add_argument('--eksport', metavar='KATALOG')
        parser.add_argument('--sol', help='Sól pseudonimów; domyślnie losowa, zapisana w manifeście.')

    def handle(self, *args, **options):
        try:
            rows = scopes()
            if not options['eksport']:
                self.stdout.write(json.dumps(counts(rows), ensure_ascii=False, indent=2))
                return
            destination = Path(options['eksport'])
            # Nigdy nie nadpisujemy ani nie usuwamy poprzedniego archiwum.
            destination.mkdir(parents=True, exist_ok=False)
            salt = options['sol'] or secrets.token_hex(32)
            manifest = {'version': VERSION, 'started_at': timezone.now().isoformat(),
                        'salt': salt, 'algorithm': 'HMAC-SHA256(user:<id>)', 'files': {}}
            descriptions = []
            for name, qs in rows.items():
                filename = name + '.jsonl'
                digest = hashlib.sha256()
                total = 0
                with (destination / filename).open('xb') as output:
                    for row in records(qs):
                        data = export_row(name, qs, row, salt)
                        line = (json.dumps(data, cls=DjangoJSONEncoder, ensure_ascii=False) + '\n').encode('utf-8')
                        output.write(line)
                        digest.update(line)
                        total += 1
                manifest['files'][filename] = {'count': total, 'sha256': digest.hexdigest()}
                descriptions.append(name + ': ' + ', '.join(
                    f.name + '_hash' if f.is_relation and f.related_model._meta.label_lower == settings.AUTH_USER_MODEL.lower()
                    else f.attname for f in fields_for(qs)))
            readme = ('Archiwum spinek, wersja 1. UTF-8, jeden rekord JSON na linię.\n'
                      'Baza: wyłącznie odczyt. Identyfikatory *_id wskazują modele źródłowe; '
                      'Article, Source i diagnozy pozostają referencjami zewnętrznymi.\n'
                      '*_hash: HMAC-SHA256 identyfikatora użytkownika z solą manifestu; null oznacza brak użytkownika.\n'
                      'Treści tylko publiczne i nieukryte; prywatne rekordy zawierają metadane i powiązania.\n'
                      'Pominięto profile, adresatów maili, endpointy i klucze push, URL, '
                      'teksty moderacji, payloady recenzji, zapytania oraz dane sygnałów.\n'
                      'Adresy e-mail oraz nazwy i imiona z kont użytkowników w treściach zamaskowano. '
                      'Maskowanie nazw skanuje konta paczkami dla każdego rekordu treści (koszt O(treści * konta)). '
                      'Treści mogą zawierać inne nazwiska '
                      'i inne dane osobowe; archiwum nie jest anonimowe ani przeznaczone do publikacji.\n'
                      'ThreadOpinion i ThreadFavorite dotyczą starszego Thread. ThreadReport nie jest modelem; '
                      'zgłoszenia obejmują CommunityThreadReport, ThreadModerationReport i CommentReport opinii wątków.\n'
                      'PushSubscription: tylko temat nitki-dr-spina, bez pozostałych tematów. '
                      'NotificationSettings: tylko push_thread_replies=True.\n'
                      'Eksport nie zapewnia wspólnego snapshotu przy równoległych zmianach bazy; '
                      'uruchom przy wstrzymanych zapisach. Manifest powstaje dopiero po ukończeniu.\n\n'
                      'Pola (daty ISO 8601, pozostałe typy jak w modelach; treści mogą być pominięte):\n'
                      + '\n'.join(descriptions) + '\n')
            readme_bytes = readme.encode('utf-8')
            (destination / 'README.txt').write_bytes(readme_bytes)
            manifest['readme_sha256'] = hashlib.sha256(readme_bytes).hexdigest()
            manifest['finished_at'] = timezone.now().isoformat()
            (destination / 'manifest.json.tmp').write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            (destination / 'manifest.json.tmp').rename(destination / 'manifest.json')
            self.stdout.write('Archiwum ukończone: ' + str(destination))
        except (OSError, DatabaseError, ValueError, TypeError) as exc:
            raise CommandError('Nie ukończono archiwum spinek (' + type(exc).__name__
                               + '). Sprawdź schemat bazy, uprawnienia i wolne miejsce; '
                               'użyj nowego katalogu. Brak manifestu oznacza niepełny eksport.') from None
