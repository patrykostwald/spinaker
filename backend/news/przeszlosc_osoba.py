"""przeszłość.today, sprint 1: profil osoby publicznej bez tematu i „Wspólne mianowniki”.

Wszystko, co mamy o jednej osobie z rejestru osób publicznych, w jednym miejscu: funkcje, konta X (tylko potwierdzone),
wpisy z diagnozami Dr. Spina, funkcje w KRS (kontekst, nie dowód), głosowania imienne, interpelacje i zapytania,
potwierdzone materiały medialne, wykres aktywności i eksport.

Zasady (pracownia_osint.LEGAL): tylko osoby publiczne z rejestru (PublicFigure), żadnych osób prywatnych; posłowie łączeni
z dokumentami i głosowaniami wyłącznie przez oficjalny identyfikator Sejmu (nigdy po nazwisku); materiały medialne tylko
z potwierdzonych powiązań; ta sama miara dla wszystkich.
"""
import csv
import difflib
import io
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import timedelta
from urllib.parse import quote

from django.db.models import Count, F, OuterRef, Q, Subquery
from django.utils import timezone

KRS_NOTE = 'Funkcje w KRS to kontekst osoby, nie dowód związku z tematem ani winy.'
DECISIVE = ('YES', 'NO', 'ABSTAIN')
VOTE_LABEL = {'YES': 'za', 'NO': 'przeciw', 'ABSTAIN': 'wstrzymał się', 'ABSENT': 'nieobecny', 'NO_VOTE': 'nieobecny',
              'PRESENT': 'obecny, bez głosu', 'VOTE_VALID': 'głos na liście', 'VOTE_INVALID': 'głos nieważny'}
RECORD_LABEL = {'interpellations': 'Interpelacja', 'questions': 'Zapytanie poselskie', 'statement': 'Wystąpienie w Sejmie',
                'print': 'Druk sejmowy', 'consultation': 'Konsultacje', 'amendment': 'Poprawka', 'position': 'Stanowisko',
                'lobby_activity': 'Lobbing', 'financial_document': 'Finanse', 'asset_declaration': 'Oświadczenie majątkowe',
                'committee_speech': 'Wystąpienie w komisji', 'asset_document': 'Oświadczenie majątkowe',
                'osr_document': 'Ocena skutków regulacji', 'process': 'Proces legislacyjny',
                'committee_sitting': 'Posiedzenie komisji', 'video': 'Transmisja Sejmu'}
DOCUMENT_LABEL = 'Dokument Sejmu'  # nigdy surowy klucz rodzaju na stronie (właściciel 7.10: „committee: 3”)
# Członkostwo w komisji to funkcja, nie dokument: osobny blok „Komisje sejmowe”, bez liczenia w dokumentach i mianownikach.
MEMBERSHIP_KINDS = ('committee',)
COMMITTEE_URL = 'https://www.sejm.gov.pl/Sejm10.nsf/agent.xsp?symbol=KOMISJAST&NrKadencji={term}&KodKom={code}'
ROLE_ORDER = ('przewodnicząc', 'zastępca', 'sekretarz')
# Dane z otwartych zbiorów mają własne bloki profilu (news.zrodla_profil), nie listę dokumentów Sejmu.
OPEN_DATA_KINDS = ('ballot', 'ep_vote', 'mep', 'mep_income', 'mep_meeting', 'person', 'mileage', 'office_report')
TOPIC_PEOPLE = 'przeszlosc-topic-people'
_PL = str.maketrans({'ł': 'l', 'Ł': 'L'})


def fold(text):
    """„Łukasz Śliwiński” → „lukasz sliwinski” (wyszukiwanie bez polskich znaków i wielkości liter)."""
    text = (text or '').translate(_PL)
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).lower()


def words(text):
    return [w for w in re.split(r'[^a-z0-9]+', fold(text)) if w]


def slug(figure):
    return f"{figure.pk}-{'-'.join(words(figure.canonical_name))}".strip('-')


def resolve(ident):
    """„123-jan-kowalski” albo „123” → osoba; połączony profil prowadzi do docelowego, archiwalny nie istnieje."""
    from news.political_models import PublicFigure
    match = re.match(r'^(?:figure:)?(\d{1,10})(?:-|$)', str(ident or ''))
    if not match:
        return None
    figure = PublicFigure.objects.filter(pk=int(match.group(1))).first()
    for _ in range(5):
        if figure is None or not figure.merged_into_id:
            break
        figure = figure.merged_into
    return figure if figure and not figure.archived else None


def _rows():
    from django.core.cache import cache
    from django.db import connection
    from news.political_models import PublicFigure
    cached = cache.get('przeszlosc:people-index') if connection.vendor == 'postgresql' else None
    if cached is None:
        cached = [(pk, name, role, words(name)) for pk, name, role in
                  PublicFigure.objects.filter(archived=False).values_list('pk', 'canonical_name', 'role_title')]
        if connection.vendor == 'postgresql':
            cache.set('przeszlosc:people-index', cached, 600)
    return cached


def search(query, limit=10):
    """Rozmyte wyszukiwanie osób: każde słowo zapytania musi pasować do jednego słowa nazwiska (początek albo literówka)."""
    from news.political_models import PublicFigure
    from news.public_figures import figures_with_verified_x
    asked = words(query)[:4]
    if not asked or len(''.join(asked)) < 3:
        return []
    scored = []
    for pk, name, role, tokens in _rows():
        total = 0.0
        for w in asked:
            best = 0.0
            for t in tokens:
                if t == w:
                    best = 1.0
                    break
                if t.startswith(w):
                    best = max(best, .95)
                elif len(w) >= 4:
                    matcher = difflib.SequenceMatcher(None, w, t)
                    if matcher.real_quick_ratio() >= .78 and matcher.quick_ratio() >= .78:
                        ratio = matcher.ratio()
                        if ratio >= .78:
                            best = max(best, ratio * .9)
            if not best:
                break
            total += best
        else:
            scored.append((-total / len(asked), name, pk, role))
    scored.sort()
    top = scored[:limit]
    figures = {f.pk: f for f in PublicFigure.objects.filter(pk__in=[row[2] for row in top]).select_related('parliamentary_roster_entry')}
    with_x = figures_with_verified_x(figures.values())
    return [{'id': pk, 'slug': slug(figures[pk]), 'name': name, 'role': role, 'organisation': figures[pk].organisation,
             'has_x': pk in with_x, 'score': round(-score, 3)} for score, name, pk, role in top if pk in figures]


# --- tożsamości posła: tylko oficjalne identyfikatory Sejmu ---
def deviation_summary(identities):
    """Odstępstwa od klubu z nocnego wyniku (news.voting_anomalies), najnowsza kadencja posła, cała kadencja."""
    from news import voting_anomalies
    for term, mp_id in sorted(identities, reverse=True):
        found = voting_anomalies.member(mp_id, term, 'term')
        if found:
            m = found['clubs'][0]
            return {'term': term, 'club': m['club'], 'share': m['share'], 'club_median': m['club_median'], 'flagged': m['flagged'],
                    'counted': m['counted'], 'rebellions_total': m['rebellions_total'], 'latest': m['latest']}
    return None


def mp_identities(figure):
    """[(kadencja, id posła)] z ręcznie sprawdzonego mandatu albo z ról importowanych z API Sejmu."""
    found = set()
    entry = figure.parliamentary_roster_entry
    if entry and entry.source == 'sejm' and str(entry.external_id).isdigit() and entry.term:
        found.add((int(entry.term), int(entry.external_id)))
    for key in figure.public_roles.filter(import_key__startswith='sejm-term:').values_list('import_key', flat=True):
        parts = key.split(':')
        if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            found.add((int(parts[1]), int(parts[2])))
    return sorted(found, reverse=True)


def figures_for_mps(pairs):
    """{(kadencja, id posła): osoba} - ta sama reguła co zbieracz dokumentów (scraper.public_records.figure_for)."""
    from news.political_models import PublicFigure, PublicFigureRole
    pairs = set(pairs)
    if not pairs:
        return {}
    result = {}
    for f in PublicFigure.objects.filter(archived=False, parliamentary_roster_entry__source='sejm',
                                         parliamentary_roster_entry__term__in={t for t, _ in pairs}).select_related('parliamentary_roster_entry'):
        e = f.parliamentary_roster_entry
        if str(e.external_id).isdigit() and (e.term, int(e.external_id)) in pairs:
            result[(e.term, int(e.external_id))] = f
    keys = [f'sejm-term:{t}:{m}' for t, m in pairs]
    for role in PublicFigureRole.objects.filter(import_key__in=keys, public_figure__archived=False).select_related('public_figure'):
        _, t, m = role.import_key.split(':')
        result.setdefault((int(t), int(m)), role.public_figure)
    return result


def vote_url(v):
    return (f'https://www.sejm.gov.pl/sejm{v.term}.nsf/agent.xsp?symbol=glosowania&NrKadencji={v.term}'
            f'&NrPosiedzenia={v.sitting}&NrGlosowania={v.number}')


def _ballots(identities):
    from news.models import Ballot
    q = Q(pk__in=[])
    for term, mp_id in identities:
        q |= Q(mp_id=mp_id, voting__term=term)
    return Ballot.objects.filter(q)


def _records(figure, identities):
    from news.public_records_models import PublicRecordPerson
    q = Q(figure=figure)
    for term, mp_id in identities:
        q |= Q(term=term, mp_id=mp_id)
    return PublicRecordPerson.objects.filter(q).exclude(record__kind__in=OPEN_DATA_KINDS + MEMBERSHIP_KINDS)


def committees(figure, identities):
    """Komisje sejmowe posła w bieżącej kadencji: z zbieracza committees (skład komisji z API Sejmu), po oficjalnym
    identyfikatorze posła, nigdy po nazwisku. Funkcja z API (przewodniczący, zastępca...), domyślnie „członek”."""
    from news.public_records_models import PublicRecordPerson
    from scraper.public_records import TERM
    pairs = [(t, i) for t, i in identities if t == TERM]
    q = Q(figure=figure, term=TERM)
    for term, mp_id in pairs:
        q |= Q(term=term, mp_id=mp_id)
    rows = PublicRecordPerson.objects.filter(q, record__source='committees', record__kind='committee').select_related('record')
    out = {}
    for person in rows:
        data = person.record.data if isinstance(person.record.data, dict) else {}
        code = str(data.get('code') or person.record.external_id.rsplit('/', 1)[-1])
        member = next((m for m in data.get('members') or [] if isinstance(m, dict) and str(m.get('id')) == str(person.mp_id)), {})
        if member.get('leaveDate'):
            continue  # tylko obecny skład
        role = str(member.get('function') or 'członek').strip().lower()
        out[code] = {'code': code, 'name': str(data.get('name') or person.record.title or code), 'role': role,
                     'since': member.get('joinDate') or None,
                     'url': COMMITTEE_URL.format(term=person.record.term or TERM, code=code)}
    rank = lambda c: next((i for i, r in enumerate(ROLE_ORDER) if c['role'].startswith(r)), len(ROLE_ORDER))  # noqa: E731
    return sorted(out.values(), key=lambda c: (rank(c), c['name']))


def x_accounts(figure):
    """Wszystkie konta X osoby potwierdzone podwójnie (dowód + potwierdzenie konta przez redaktora)."""
    from django.contrib.contenttypes.models import ContentType
    from news.political_models import PublicFigure, SocialHandleEvidence
    q = Q(subject_content_type=ContentType.objects.get_for_model(PublicFigure), subject_object_id=figure.pk)
    if figure.parliamentary_roster_entry_id:
        q |= Q(roster_entry_id=figure.parliamentary_roster_entry_id)
    out = {}
    for ev in (SocialHandleEvidence.objects.filter(q, platform='x', status='candidate_created', candidate__resolved_account__isnull=False)
               .select_related('candidate__resolved_account__confirmed_by')):
        account = ev.candidate.resolved_account
        if account.is_confirmed() and account.pk not in out:
            out[account.pk] = (account, ev.evidence_url)
    return list(out.values())


def _month(value):
    return value.strftime('%Y-%m') if value else None


def activity(posts, documents, votes, media, months=12):
    """Miesiące (ostatnie 12) × rodzaj aktywności; zera też, żeby wykres miał stałą oś."""
    today = timezone.localdate()
    keys = []
    y, m = today.year, today.month
    for _ in range(months):
        keys.append(f'{y:04d}-{m:02d}')
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    keys.reverse()
    table = {k: {'month': k, 'posts': 0, 'documents': 0, 'votes': 0, 'media': 0} for k in keys}
    for kind, dates in (('posts', posts), ('documents', documents), ('votes', votes), ('media', media)):
        for d in dates:
            k = _month(d)
            if k in table:
                table[k][kind] += 1
    return list(table.values())


def profile(figure):
    from news.clinic import published_diagnoses
    from news.political_models import PoliticalPost
    from news.public_figures import figure_data
    data = figure_data(figure, include_detail=True)
    data.pop('x_posts', None)
    data.pop('votes', None)
    data['slug'] = slug(figure)
    data['krs_note'] = KRS_NOTE
    identities = mp_identities(figure)
    since = timezone.now() - timedelta(days=400)

    # Konta X i wpisy z diagnozami
    accounts = x_accounts(figure)
    data['x_accounts'] = [{'handle': a.handle, 'url': f'https://x.com/{a.handle}', 'evidence_url': ev, 'camp': a.camp} for a, ev in accounts]
    post_rows = PoliticalPost.objects.filter(account__in=[a for a, _ in accounts], available=True)
    posts = list(post_rows.select_related('account').order_by('-published_at', '-pk')[:200])
    diagnoses = {d.post_id: d for d in published_diagnoses().filter(post__in=posts)}
    spins = [d.intensity for d in diagnoses.values()]
    data['posts'] = {
        'count': post_rows.count(), 'diagnoses': len(diagnoses), 'avg_spin': round(sum(spins) / len(spins)) if spins else None,
        'results': [{'id': p.pk, 'url': p.url, 'text': p.text[:700], 'date': p.published_at.date().isoformat(), 'handle': p.account.handle,
                     'diagnosis': ({'id': diagnoses[p.pk].pk, 'intensity': diagnoses[p.pk].intensity, 'headline': diagnoses[p.pk].headline,
                                    'url': f'https://spin.clinic/klinika/{diagnoses[p.pk].pk}'} if p.pk in diagnoses else None)}
                    for p in posts],
    }

    # Interpelacje, zapytania, wystąpienia i inne dokumenty Sejmu (oficjalny identyfikator posła)
    record_rows = _records(figure, identities)
    by_kind = Counter(record_rows.values_list('record__kind', flat=True))
    data['committees'] = committees(figure, identities)
    records = [p.record for p in record_rows.select_related('record').order_by(F('record__date').desc(nulls_last=True), '-record__pk')[:120]]
    seen, docs = set(), []
    for r in records:
        if r.pk in seen:
            continue
        seen.add(r.pk)
        replies = r.data.get('replies') if isinstance(r.data, dict) else None
        docs.append({'id': r.pk, 'kind': r.kind, 'label': RECORD_LABEL.get(r.kind, DOCUMENT_LABEL), 'title': (r.title or '')[:300],
                     'date': r.date.isoformat() if r.date else None, 'url': r.source_url,
                     'replies': len(replies) if isinstance(replies, list) else None})
    labels = Counter()
    for k, n in by_kind.items():
        labels[RECORD_LABEL.get(k, DOCUMENT_LABEL)] += n
    data['documents'] = {'available': bool(identities) or bool(docs), 'by_kind': dict(labels),
                         'count': sum(by_kind.values()), 'results': docs}

    # Głosowania imienne
    ballots = _ballots(identities)
    tally = Counter(VOTE_LABEL.get(v, 'inne') for v in ballots.values_list('vote', flat=True))
    recent = list(ballots.select_related('voting__article').order_by('-voting__article__published_date', '-pk')[:40])
    data['votes'] = {'available': bool(identities), 'count': sum(tally.values()), 'summary': dict(tally),
                     'reason': '' if identities else 'Brak potwierdzonego mandatu poselskiego (oficjalny identyfikator Sejmu).',
                     'results': [{'date': b.voting.article.published_date.date().isoformat() if b.voting.article.published_date else None,
                                  'title': b.voting.article.title[:300], 'motion': (b.voting.motion or '')[:300],
                                  'vote': VOTE_LABEL.get(b.vote, 'inne'), 'club': b.club, 'url': vote_url(b.voting)} for b in recent]}
    data['votes']['deviation'] = deviation_summary(identities)

    # Aktywność w czasie
    media_dates = [m['published_date'] for m in data.get('materials', {}).get('results', []) if m.get('published_date')]
    data['activity'] = activity(
        post_rows.filter(published_at__gte=since).values_list('published_at', flat=True),
        [d for d in record_rows.filter(record__date__isnull=False, record__date__gte=since.date()).values_list('record__date', flat=True)],
        [d for d in ballots.filter(voting__article__published_date__gte=since).values_list('voting__article__published_date', flat=True)],
        media_dates)
    # Raport źródeł 6.10: wystąpienia z nagrań Sejmu z diagnozą i dane z otwartych zbiorów (europosłowie, Wikidata, biura)
    from news import sejm_wideo
    from news.zrodla_profil import open_data
    data['sejm_video'] = [sejm_wideo.item(r) for r in sejm_wideo.published().filter(figure=figure)[:10]]
    data['open_data'] = open_data(figure, identities)
    data['topics'] = [t for t in topic_history() if figure.pk in t['people']][:12]
    for t in data['topics']:
        t.pop('people', None)
    data['generated_at'] = timezone.now().isoformat(timespec='minutes')
    return data


# --- spin.clinic: bezpłatny „Ślad w dokumentach” (wycinek profilu przeszłość.today) ---
FREE_KINDS = ('interpellations', 'questions')
PRO_FEATURES = ['Funkcje w KRS', 'Wspólne mianowniki', 'Alerty e-mail', 'Eksport CSV i JSON']


def club_line(ballots):
    """{voting_id: {klub: większościowy głos}} - tylko głosy za/przeciw/wstrzymał się; remis = brak większości."""
    from news.models import Ballot
    counts = defaultdict(Counter)
    rows = (Ballot.objects.filter(voting_id__in={b.voting_id for b in ballots}, club__in={b.club for b in ballots if b.club}, vote__in=DECISIVE)
            .values('voting_id', 'club', 'vote').annotate(n=Count('id')))
    for r in rows:
        counts[(r['voting_id'], r['club'])][r['vote']] = r['n']
    out = {}
    for key, c in counts.items():
        top = c.most_common(2)
        out[key] = top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else None
    return out


def free_trace(figure):
    """Ślad w dokumentach dla czytelników spin.clinic: 5 ostatnich głosowań (głos wobec większości klubu), 3 ostatnie
    interpelacje lub zapytania i liczby z 12 miesięcy. Ta sama miara dla każdej osoby i partii; posła łączymy z Sejmem
    wyłącznie przez oficjalny identyfikator (mp_identities), nigdy po nazwisku. KRS, Wspólne mianowniki, alerty
    i eksport zostają w pełnym profilu przeszłość.today."""
    from news.przeszlosc import enabled
    from news.przeszlosc_alerts import site
    identities = mp_identities(figure)
    since = timezone.now() - timedelta(days=365)
    ballots = _ballots(identities)
    recent = list(ballots.select_related('voting__article').order_by('-voting__article__published_date', '-pk')[:5])
    line = club_line(recent)
    votes = []
    for b in recent:
        majority = line.get((b.voting_id, b.club)) if b.club else None
        if b.vote not in DECISIVE:
            relation = ''
        elif not b.club or majority is None:
            relation = 'brak większości w klubie' if b.club else ''
        else:
            relation = 'zgodnie z klubem' if b.vote == majority else 'inaczej niż klub'
        votes.append({'date': b.voting.article.published_date.date().isoformat() if b.voting.article.published_date else None,
                      'title': (b.voting.motion or b.voting.article.title or '')[:200], 'vote': VOTE_LABEL.get(b.vote, 'inne'),
                      'club': _club(b.club), 'club_vote': VOTE_LABEL.get(majority, '') if majority else '', 'relation': relation,
                      'url': vote_url(b.voting)})
    records = _records(figure, identities)
    docs, seen = [], set()
    for p in records.filter(record__kind__in=FREE_KINDS).select_related('record').order_by(F('record__date').desc(nulls_last=True), '-record__pk')[:12]:
        r = p.record
        if r.pk in seen:
            continue
        seen.add(r.pk)
        replies = r.data.get('replies') if isinstance(r.data, dict) else None
        docs.append({'kind': r.kind, 'label': RECORD_LABEL.get(r.kind, 'Dokument Sejmu'), 'title': (r.title or '')[:200],
                     'date': r.date.isoformat() if r.date else None, 'url': r.source_url,
                     'answered': bool(replies) if isinstance(replies, list) else None})
        if len(docs) == 3:
            break
    return {
        'available': bool(identities),
        'reason': '' if identities else 'Brak potwierdzonego mandatu poselskiego (oficjalny identyfikator Sejmu) - głosowań i interpelacji tu nie łączymy.',
        'votes': votes,
        'documents': docs,
        'year': {'votes': ballots.filter(voting__article__published_date__gte=since).count(),
                 'documents': records.filter(record__date__gte=since.date()).values('record_id').distinct().count()},
        'full_profile': {'url': f'{site()}/przeszlosc/osoba/{slug(figure)}', 'features': PRO_FEATURES} if enabled() else None,
    }


def _club(code):
    from news.public_figures import _club_short
    return _club_short(code)


# --- historia tematów dnia: kto występował w jakim temacie (dowód współwystępowania) ---
def remember_topics(rows):
    """Zapis osób z tematów dnia (pick_topics). Trzymamy 200 ostatnich tematów; nic z zapytań użytkowników."""
    from news.models import ImportState
    state, _ = ImportState.objects.get_or_create(name=TOPIC_PEOPLE)
    history = {t['topic'].lower(): t for t in (state.cursor or {}).get('topics', [])}
    today = timezone.localdate().isoformat()
    for row in rows:
        if row.get('people'):
            history[row['topic'].lower()] = {'topic': row['topic'], 'at': today, 'people': sorted(set(row['people']))}
    ordered = sorted(history.values(), key=lambda t: t['at'], reverse=True)[:200]
    state.cursor = {'topics': ordered}
    state.save(update_fields=['cursor'])


def topic_history():
    from news.models import ImportState
    state = ImportState.objects.filter(name=TOPIC_PEOPLE).first()
    return [dict(t) for t in (state.cursor or {}).get('topics', [])] if state else []


def _person(f):
    return {'id': f.pk, 'slug': slug(f), 'name': f.canonical_name, 'role': f.role_title}


def co_occurrence(figure, identities, limit=10):
    """Osoby, które występują razem z tą osobą: wspólne dokumenty Sejmu (np. współautorzy interpelacji),
    wspólne tematy dnia i wspólne przekazy dnia Kliniki. Każda pozycja z dowodami (link)."""
    from news.clinic import figures_by_account
    from news.clinic_models import ClinicDailyMessage
    from news.political_models import PoliticalPost, PublicFigure
    from news.public_records_models import PublicRecordPerson
    score, evidence = Counter(), defaultdict(list)
    record_ids = list(_records(figure, identities).values_list('record_id', flat=True)[:2000])
    others = (PublicRecordPerson.objects.filter(record_id__in=record_ids, figure__isnull=False, figure__archived=False)
              .exclude(figure=figure).select_related('record').order_by(F('record__date').desc(nulls_last=True)))
    seen = set()
    for p in others[:3000]:
        if (p.figure_id, p.record_id) in seen:
            continue
        seen.add((p.figure_id, p.record_id))
        score[p.figure_id] += 3
        evidence[p.figure_id].append({'kind': 'dokument', 'label': (p.record.title or RECORD_LABEL.get(p.record.kind, 'Dokument'))[:140], 'url': p.record.source_url})
    for t in topic_history():
        if figure.pk in t['people']:
            for other in t['people']:
                if other != figure.pk:
                    score[other] += 2
                    evidence[other].append({'kind': 'temat', 'label': t['topic'], 'url': '/przeszlosc?q=' + quote(t['topic'])})
    accounts = [a for a, _ in x_accounts(figure)]
    if accounts:
        messages = ClinicDailyMessage.objects.filter(status='approved', posts__account__in=accounts).distinct().order_by('-day')[:60]
        for msg in messages:
            other_accounts = set(PoliticalPost.objects.filter(clinic_daily_messages=msg).exclude(account__in=accounts).values_list('account_id', flat=True))
            for f in {f.pk for f in figures_by_account(other_accounts).values()} - {figure.pk}:
                score[f] += 1
                evidence[f].append({'kind': 'przekaz dnia', 'label': f'Przekaz dnia {msg.day.isoformat()}', 'url': f'https://spin.clinic/klinika/przekazy/{msg.day.isoformat()}'})
    people = {f.pk: f for f in PublicFigure.objects.filter(pk__in=list(score), archived=False)}
    rows = [(s, pk) for pk, s in score.items() if pk in people]
    rows.sort(key=lambda r: (-r[0], people[r[1]].canonical_name))
    return [{**_person(people[pk]), 'score': s, 'shared': Counter(e['kind'] for e in evidence[pk]), 'evidence': evidence[pk][:3]}
            for s, pk in rows[:limit]]


def shared_krs(figure, limit=10):
    """Inne osoby publiczne z potwierdzonymi funkcjami w tych samych podmiotach KRS."""
    from news.political_models import PublicFigureOrganisationRelation
    mine = list(PublicFigureOrganisationRelation.objects.filter(public_figure=figure, verification_status='confirmed',
                                                                organisation__archived=False).select_related('organisation'))
    my_role = {r.organisation_id: r.organ or r.public_role for r in mine}
    rows = (PublicFigureOrganisationRelation.objects.filter(organisation_id__in=my_role, verification_status='confirmed', public_figure__archived=False)
            .exclude(public_figure=figure).select_related('organisation', 'public_figure'))
    grouped = defaultdict(list)
    for r in rows:
        grouped[r.public_figure_id].append(r)
    out = []
    for pk, rels in grouped.items():
        f = rels[0].public_figure
        orgs = {r.organisation_id: r for r in rels}
        out.append({**_person(f), 'count': len(orgs), 'evidence': [
            {'kind': 'KRS', 'label': f'{r.organisation.name} (KRS {r.organisation.krs_number}): {r.organ or r.public_role} / {my_role[r.organisation_id]}',
             'url': r.organisation.official_register_url} for r in list(orgs.values())[:3]]})
    out.sort(key=lambda r: (-r['count'], r['name']))
    return out[:limit]


def vote_alignment(identities, limit=10, window=400, minimum=10):
    """Zgodność głosów z innymi posłami (za/przeciw/wstrzymał się) w ostatnich głosowaniach tej osoby.
    Dwa zestawienia: najbardziej zgodni ogółem i najbardziej zgodni spoza własnego klubu. Dowód: wspólne głosowania."""
    from news.models import Ballot
    if not identities:
        return {'available': False, 'window': 0, 'aligned': [], 'cross_club': []}
    term, me = identities[0]
    mine = Ballot.objects.filter(mp_id=me, voting__term=term, vote__in=DECISIVE)
    voting_ids = list(mine.order_by('-voting_id').values_list('voting_id', flat=True)[:window])
    if not voting_ids:
        return {'available': False, 'window': 0, 'aligned': [], 'cross_club': []}
    my_club = mine.order_by('-voting_id').values_list('club', flat=True).first() or ''
    my_vote = Ballot.objects.filter(voting_id=OuterRef('voting_id'), mp_id=me).values('vote')[:1]
    stats = (Ballot.objects.filter(voting_id__in=voting_ids, vote__in=DECISIVE).exclude(mp_id=me)
             .annotate(mine=Subquery(my_vote)).values('mp_id')
             .annotate(total=Count('id'), same=Count('id', filter=Q(vote=F('mine')))))
    rows = [r for r in stats if r['total'] >= min(minimum, len(voting_ids))]
    info = {}
    for mp_id, name, club in (Ballot.objects.filter(voting_id__in=voting_ids[:50], mp_id__in=[r['mp_id'] for r in rows])
                              .order_by('mp_id', '-voting_id').values_list('mp_id', 'name', 'club')):
        info.setdefault(mp_id, (name, club))
    for r in rows:
        r['pct'] = round(100 * r['same'] / r['total'])
        r['name'], r['club'] = info.get(r['mp_id'], (f"Poseł {r['mp_id']}", ''))
    rows.sort(key=lambda r: (-r['pct'], -r['total'], r['name']))
    aligned = rows[:limit]
    cross = [r for r in rows if r['club'] and r['club'] != my_club][:limit]
    chosen = {r['mp_id'] for r in aligned + cross}
    figures = figures_for_mps({(term, m) for m in chosen})
    mine_map = dict(Ballot.objects.filter(mp_id=me, voting_id__in=voting_ids).values_list('voting_id', 'vote'))
    agree = defaultdict(list)
    for b in (Ballot.objects.filter(mp_id__in=chosen, voting_id__in=voting_ids).select_related('voting__article').order_by('-voting_id')):
        if mine_map.get(b.voting_id) == b.vote and len(agree[b.mp_id]) < 3:
            agree[b.mp_id].append({'kind': 'głosowanie', 'label': f"{b.voting.article.title[:120]} ({VOTE_LABEL.get(b.vote, b.vote)})", 'url': vote_url(b.voting)})

    def item(r):
        f = figures.get((term, r['mp_id']))
        return {**(_person(f) if f else {'id': None, 'slug': None, 'name': r['name'], 'role': 'Poseł na Sejm RP'}),
                'club': r['club'], 'pct': r['pct'], 'shared': r['total'], 'agreed': r['same'], 'evidence': agree[r['mp_id']]}
    return {'available': True, 'window': len(voting_ids), 'club': my_club, 'term': term,
            'aligned': [item(r) for r in aligned], 'cross_club': [item(r) for r in cross]}


def denominators(figure):
    identities = mp_identities(figure)
    return {'people': co_occurrence(figure, identities), 'krs': shared_krs(figure), 'votes': vote_alignment(identities),
            'note': 'Współwystępowanie to wskazówka do sprawdzenia, nie dowód współpracy. Każda pozycja prowadzi do źródła.'}


def export_csv(data):
    out = io.StringIO()
    out.write('﻿')
    w = csv.writer(out, delimiter=';')
    w.writerow(['data', 'rodzaj', 'treść', 'spin', 'link'])
    for p in data['posts']['results']:
        w.writerow([p['date'], 'wpis na X', p['text'], p['diagnosis']['intensity'] if p['diagnosis'] else '', p['url']])
    for d in data['documents']['results']:
        w.writerow([d['date'] or '', d['label'], d['title'], '', d['url']])
    for v in data['votes']['results']:
        w.writerow([v['date'] or '', f"głosowanie: {v['vote']}", v['title'], '', v['url']])
    for o in data.get('organisations', []):
        w.writerow([o.get('since') or '', 'funkcja w KRS (kontekst, nie dowód)', f"{o['name']}: {o.get('organ') or o.get('public_role')}", '', o['official_register_url']])
    for m in data.get('materials', {}).get('results', []):
        w.writerow([str(m.get('published_date') or '')[:10], 'artykuł', m['title'], '', m['url']])
    w.writerow([])
    w.writerow([f"Źródło: przeszłość.today, profil {data['name']}, pobrano {timezone.localdate().isoformat()}. Każdy wiersz prowadzi do oryginału."])
    return out.getvalue()


from rest_framework.decorators import api_view, permission_classes  # noqa: E402
from rest_framework.permissions import AllowAny  # noqa: E402
from rest_framework.response import Response  # noqa: E402


@api_view(['GET'])
@permission_classes([AllowAny])
def people_view(request):
    """GET /api/przeszlosc/osoby/?q=kosiniak - osoby publiczne z rejestru (bez polskich znaków, z literówkami)."""
    from news.przeszlosc import enabled
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    query = request.query_params.get('q', '')[:80]
    if len(''.join(words(query))) < 3:
        return Response({'detail': 'Podaj co najmniej 3 litery nazwiska.'}, status=400)
    return Response({'query': query, 'results': search(query)})


@api_view(['GET'])
@permission_classes([AllowAny])
def person_view(request, ident):
    """GET /api/przeszlosc/osoba/<id albo slug>/ ; ?eksport=csv|json pobiera plik."""
    from django.core.cache import cache
    from django.db import connection
    from django.http import HttpResponse
    from news.przeszlosc import enabled
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    figure = resolve(ident)
    if figure is None:
        return Response({'detail': 'Nie ma takiej osoby publicznej w rejestrze.'}, status=404)
    key = f'przeszlosc:osoba:{figure.pk}'
    data = cache.get(key) if connection.vendor == 'postgresql' else None
    if data is None:
        data = profile(figure)
        data['denominators'] = denominators(figure)
        if connection.vendor == 'postgresql':
            cache.set(key, data, 900)
    from news.przeszlosc_dostep import access, has, locked
    fmt = request.query_params.get('eksport', '')
    if fmt in ('csv', 'json') and not has('export', request):
        return locked('export')
    data = {**data, 'access': access(request)}
    if not has('denominators', request):
        data['denominators'] = None
    if not has('krs', request):
        data['organisations'] = []
    stamp = timezone.localdate().isoformat()
    if fmt == 'csv':
        response = HttpResponse(export_csv(data), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="przeszlosc-{data["slug"]}-{stamp}.csv"'
        return response
    response = Response(data)
    if fmt == 'json':
        response['Content-Disposition'] = f'attachment; filename="przeszlosc-{data["slug"]}-{stamp}.json"'
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
def spin_trace_view(request, figure_id):
    """GET /api/public-figures/<id>/slad/ - bezpłatny „Ślad w dokumentach” na profilu spin.clinic."""
    from django.core.cache import cache
    from django.db import connection
    from news.political_models import PublicFigure
    figure = PublicFigure.objects.filter(pk=figure_id, archived=False).select_related('parliamentary_roster_entry').first()
    if figure is None:
        return Response({'detail': 'Nie ma takiej osoby publicznej w rejestrze.'}, status=404)
    key = f'spin:slad:{figure.pk}'
    data = cache.get(key) if connection.vendor == 'postgresql' else None
    if data is None:
        data = free_trace(figure)
        if connection.vendor == 'postgresql':
            cache.set(key, data, 900)
    return Response(data)
