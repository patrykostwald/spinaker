"""„Wcześniej i teraz” (v3): dwie wypowiedzi albo głosy tej samej osoby o tym samym temacie, obok siebie, bez oceny.

Kontrakt: docs/SPINA_V3_API.md. Flaga POSITION_PAIRS_ENABLED (domyślnie wyłączona); cisza wyborcza (ELECTION_SILENCE) ukrywa.

Zasady (ta sama miara dla każdej strony, ZAWSZE):
- algorytm nie zna partii ani obozu: te same progi, ta sama reguła podobieństwa (zmiana_zdania.stems/similarity), to samo
  polecenie modelu (zmiana_zdania.SYSTEM), ten sam walidator; brak gałęzi zależnych od strony politycznej;
- kandydaci (AI albo człowiek) są niepubliczni; publicznie tylko pary zatwierdzone przez człowieka;
- bez etykiet oceniających, bez liczników i rankingów; kontekst tylko opisowy;
- ta sama osoba wyłącznie po identyfikatorze (konta X potwierdzone przy osobie, oficjalny identyfikator posła w Sejmie);
- cytaty dosłowne z materiałów w bazie (<= 280 znaków), głos = wynik z imiennego głosowania;
- zgłoszenie błędu zawsze trafia do kolejki moderacji; parę z API zdejmuje tylko zgłoszenie zweryfikowanej osoby albo
  przedstawiciela albo próg niezależnych zgłoszeń z kont, inaczej para ma oznaczenie review_pending (procedura sprostowania);
- dziennik PositionPairEvent (AI Act art. 50).
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

PROMPT_VERSION = 'pary-1'
# Recenzja Fable 13.10 (poprawka 3): jawne kryterium doboru zamiast „bez oceny”; tekst do przeglądu prawnika.
NOTICE = ('Dwie wypowiedzi tej samej osoby o tym samym temacie z różnych dat. Zestawiamy je, bo według naszej metody '
          'stanowiska się różnią. Nie oceniamy powodów. Sprawdź oba źródła w całości.')
ALERT_TITLE = 'Nowe zestawienie wypowiedzi: {topic}'
KIND_LABEL = {'wpis': 'Wpis na X', 'wystapienie': 'Wystąpienie w Sejmie', 'glos': 'Głosowanie w Sejmie', 'wypowiedz': 'Wypowiedź'}
MAX_QUOTE, MAX_CONTEXT, MAX_TOPIC = 280, 200, 120
PUBLIC_LIMIT = 20
MAX_ASKS = 6
# Słowa oceniające - zakaz w kontekście i temacie (lista do przeglądu prawnika; rdzenie, bez wielkości liter).
EVALUATIVE = re.compile(
    r'hipokry|obłud|kłam|zdrad|kompromit|wolt[aąyę]|przewrot|flip|oszuk|cynicz|skandal|wstyd|żenu|bezczel|manipul|'
    r'dwulic|chorąg|niekonsekwen|sprzeczn|zaprzecz|zmieni\w* zdani|zmian\w* front|nagle|wreszcie|znowu|kolejny raz|'
    r'populi|farbowan|kameleon|bezwstyd|perfid|absurd|kuriozal',
    re.IGNORECASE)
CONDITIONAL = re.compile(r'\b(jeśli|jeżeli|gdyby|gdybyśmy|o ile|chyba że|pod warunkiem)\b', re.IGNORECASE)
IRONY = re.compile(r'\(sic\)|;\)|:\)|:-\)|:D|xD|/s\b|[\U0001F602\U0001F609\U0001F643\U0001F644\U0001F923]', re.IGNORECASE)


class PairError(Exception):
    """Błąd z kodem i listą powodów (walidator, decyzja)."""

    def __init__(self, code, issues=()):
        self.code, self.issues = code, list(issues)
        super().__init__('; '.join(self.issues) or code)


def enabled() -> bool:
    from news.v3_flags import flag
    return flag('POSITION_PAIRS_ENABLED')


def silence() -> bool:
    from news.v3_flags import silence as _silence
    return _silence()


# --- materiały (ta sama osoba po identyfikatorze) ------------------------------------------------------------------------

def _day(value):
    if value is None:
        return None
    return timezone.localtime(value).date() if hasattr(value, 'hour') else value


REPOST_TEXT = re.compile(r'^\s*(rt|retweet|repost)\s*:?\s*@\w+|^\s*["„“]\s*@\w+\s*:|\bvia\s+@\w+', re.IGNORECASE)


def is_repost(post) -> bool:
    """Podanie dalej albo cytat cudzego wpisu (recenzja Codex 2): metadane X (referenced_tweets/referenced_posts:
    retweeted, quoted) i wzorce tekstu (RT @, rt @ ze spacjami, „@konto: ...”, via @konto). Konserwatywnie: w razie
    wątpliwości to nie jest własna wypowiedź."""
    data = post.source_data or {}
    refs = data.get('referenced_tweets', data.get('referenced_posts', [])) or []
    types = {ref.get('type') for ref in refs if isinstance(ref, dict)}
    return bool(types & {'retweeted', 'quoted'}) or bool(REPOST_TEXT.search(post.text or ''))


def vote_target(motion, title='') -> str:
    """Przedmiot głosowania (recenzja Fable, poprawka 2): głos „za” wnioskiem o odrzucenie to sprzeciw wobec projektu.
    Kolejność: wniosek o odrzucenie, poprawka, całość; inaczej „inne” (wymaga potwierdzenia człowieka)."""
    from news.przeszlosc_osoba import fold
    text = fold(f'{motion or ""} {title or ""}')
    if 'odrzuc' in text:
        return 'wniosek o odrzucenie'
    if 'poprawk' in text:
        return 'poprawka'
    if 'calosc' in text or re.search(r'trzeci\w* czytan', text):
        return 'całość'
    return 'inne'


VOTE_PHRASES = {
    'całość': {'za': 'za całością projektu', 'przeciw': 'przeciw całości projektu',
               'wstrzymał się': 'wstrzymał(a) się w głosowaniu nad całością projektu'},
    'wniosek o odrzucenie': {'za': 'za wnioskiem o odrzucenie projektu', 'przeciw': 'przeciw wnioskowi o odrzucenie projektu',
                             'wstrzymał się': 'wstrzymał(a) się w głosowaniu nad wnioskiem o odrzucenie projektu'},
    'poprawka': {'za': 'za poprawką', 'przeciw': 'przeciw poprawce', 'wstrzymał się': 'wstrzymał(a) się w głosowaniu nad poprawką'},
    'inne': {'za': 'za (przedmiot głosowania w opisie)', 'przeciw': 'przeciw (przedmiot głosowania w opisie)',
             'wstrzymał się': 'wstrzymał(a) się (przedmiot głosowania w opisie)'},
}


def vote_phrase(vote, target) -> str:
    return VOTE_PHRASES.get(target, VOTE_PHRASES['inne']).get(vote or '', vote or '')


def _sentence_around(text, quote) -> str:
    """Zdanie (albo zdania) materiału, w którym stoi cytat - po normalizacji jak zmiana_zdania.quoted."""
    from news.zmiana_zdania import _norm
    norm_text, norm_quote = _norm(text), _norm(quote)
    start = norm_text.find(norm_quote)
    if start < 0:
        return norm_quote
    end = start + len(norm_quote)
    left = max(norm_text.rfind(mark, 0, start) for mark in '.!?;')
    right = [i for i in (norm_text.find(mark, end) for mark in '.!?;') if i >= 0]
    return norm_text[left + 1:(min(right) + 1) if right else len(norm_text)]


def material(figure, key):
    """Materiał osoby po kluczu: post:<id> (konto X potwierdzone przy osobie), record:<id> (wystąpienie w Sejmie po
    identyfikatorze posła), ballot:<id> (głos imienny po identyfikatorze posła). None, gdy nie należy do tej osoby."""
    from news.political_models import PoliticalPost
    from news.przeszlosc_osoba import DECISIVE, VOTE_LABEL, _ballots, _records, mp_identities, vote_url, x_accounts
    kind, _, raw = str(key or '').partition(':')
    if not raw.isdigit():
        return None
    pk = int(raw)
    if kind == 'post':
        accounts = [a.pk for a, _ in x_accounts(figure)]
        p = PoliticalPost.objects.filter(pk=pk, account_id__in=accounts).select_related('account').first()
        if p is None:
            return None
        return {'key': f'post:{p.pk}', 'kind': 'wpis', 'date': _day(p.published_at), 'text': p.text or '', 'vote': None,
                'retweet': is_repost(p), 'available': p.available, 'post': p,
                'source': {'name': f'@{p.account.handle} na X', 'url': p.url, 'fetched_at': _day(p.fetched_at)}}
    identities = mp_identities(figure)
    if kind == 'record':
        link = (_records(figure, identities).filter(record_id=pk, record__kind='statement').select_related('record').first())
        if link is None:
            return None
        r = link.record
        return {'key': f'record:{r.pk}', 'kind': 'wystapienie', 'date': r.date, 'text': f'{r.title}\n{r.text}'.strip(),
                'vote': None, 'retweet': False, 'available': True,
                'source': {'name': f'Sejm RP: {(r.title or "wystąpienie")[:80]}', 'url': r.source_url, 'fetched_at': _day(r.fetched_at)}}
    if kind == 'ballot' and identities:
        b = _ballots(identities).filter(pk=pk, vote__in=DECISIVE).select_related('voting__article').first()
        if b is None:
            return None
        v = b.voting
        subject = ' - '.join(part for part in (v.article.title, v.motion) if part)[:300]
        target = vote_target(v.motion, v.article.title)
        vote = VOTE_LABEL.get(b.vote)
        return {'key': f'ballot:{b.pk}', 'kind': 'glos', 'date': _day(v.article.published_date), 'text': subject,
                'vote': vote, 'vote_target': target, 'vote_label': vote_phrase(vote, target),
                'vote_subject': f'{target[0].upper()}{target[1:]}: {subject}'[:320], 'retweet': False, 'available': True,
                'source': {'name': f'Sejm RP, głosowanie {v.sitting}/{v.number} (kadencja {v.term})', 'url': vote_url(v),
                           'fetched_at': _day(getattr(v.article, 'created_at', None) or v.article.published_date)}}
    return None


# --- walidator ---------------------------------------------------------------------------------------------------------

def _clean(text) -> str:
    return ' '.join(re.sub(r'\s*[—–]\s*', ' - ', str(text or '')).split())


def check_text(text, limit, label) -> list[str]:
    """Kontekst i temat: opisowe, krótkie, bez słów oceniających, bez wykrzykników i pytań."""
    issues = []
    if len(text) > limit:
        issues.append(f'{label}: dłuższy niż {limit} znaków')
    if EVALUATIVE.search(text):
        issues.append(f'{label}: słowo oceniające ({EVALUATIVE.search(text).group(0)})')
    if re.search(r'[!?]', text):
        issues.append(f'{label}: wykrzyknik albo pytanie')
    if label == 'kontekst' and len(re.findall(r'[.!?](\s|$)', text)) > 1:
        issues.append('kontekst: więcej niż jedno zdanie')
    return issues


def _side(mat, quote, label) -> tuple[dict, list[str]]:
    from news.zmiana_zdania import quoted
    issues = []
    if mat is None:
        return {}, [f'{label}: brak materiału tej osoby (po identyfikatorze)']
    if not mat['source'].get('name') or not mat['source'].get('url') or not mat['date']:
        issues.append(f'{label}: brak źródła albo daty')
    if mat.get('retweet'):
        issues.append(f'{label}: podanie dalej cudzego wpisu, nie własna wypowiedź')
    side = {'key': mat['key'], 'kind': mat['kind'], 'kind_label': KIND_LABEL[mat['kind']],
            'date': mat['date'].isoformat() if mat['date'] else None, 'quote': None, 'vote': None, 'source': {
                'name': mat['source'].get('name'), 'url': mat['source'].get('url'),
                'fetched_at': mat['source']['fetched_at'].isoformat() if mat['source'].get('fetched_at') else None}}
    if mat['kind'] == 'glos':
        if not mat.get('vote'):
            issues.append(f'{label}: brak wyniku głosowania')
        side.update({key: mat.get(key) for key in ('vote', 'vote_target', 'vote_label', 'vote_subject')})
        return side, issues
    quote = _clean(quote)
    if not quote:
        issues.append(f'{label}: brak cytatu')
    elif len(quote) > MAX_QUOTE:
        issues.append(f'{label}: cytat dłuższy niż {MAX_QUOTE} znaków')
    elif not quoted(mat['text'], quote):
        issues.append(f'{label}: cytat nie jest dosłownym fragmentem materiału')
    elif CONDITIONAL.search(_sentence_around(mat['text'], quote)):
        issues.append(f'{label}: wypowiedź warunkowa (całe zdanie materiału)')
    elif IRONY.search(re.sub(r'https?://\S+', ' ', mat['text'])):  # znacznik w całym materiale (bez adresów t.co)
        issues.append(f'{label}: znacznik ironii')
    side['quote'] = quote or None
    return side, issues


def validate(figure, a_key, b_key, quote_a=None, quote_b=None, context='', topic='') -> dict:
    """Czysta reguła (te same progi dla każdej osoby). Zwraca dane pary albo PairError('invalid', powody)."""
    from news.zmiana_zdania import MIN_GAP_DAYS
    mat_a, mat_b = material(figure, a_key), material(figure, b_key)
    if mat_a and mat_b and mat_a['date'] and mat_b['date'] and mat_a['date'] > mat_b['date']:
        mat_a, mat_b, quote_a, quote_b = mat_b, mat_a, quote_b, quote_a  # zawsze A starszy, B nowszy
    a, issues_a = _side(mat_a, quote_a, 'A')
    b, issues_b = _side(mat_b, quote_b, 'B')
    issues = issues_a + issues_b
    if mat_a and mat_b:
        if mat_a['key'] == mat_b['key']:
            issues.append('A i B to ten sam materiał')
        elif mat_a['date'] and mat_b['date'] and (mat_b['date'] - mat_a['date']).days < MIN_GAP_DAYS:
            issues.append(f'różnica czasu mniejsza niż {MIN_GAP_DAYS} dni')
        if mat_a['kind'] == 'glos' and mat_b['kind'] == 'glos' and mat_a.get('vote') == mat_b.get('vote'):
            issues.append('dwa takie same głosy')
    topic, context = _clean(topic), _clean(context)
    # Temat i kontekst mogą być puste u kandydata; zatwierdzenie wymaga obu (approve).
    issues += check_text(topic, MAX_TOPIC, 'temat') + check_text(context, MAX_CONTEXT, 'kontekst')
    if issues:
        raise PairError('invalid', issues)
    return {'a': a, 'b': b, 'a_date': mat_a['date'], 'b_date': mat_b['date'], 'topic': topic, 'context': context,
            'posts': [m['post'] for m in (mat_a, mat_b) if m.get('post')]}


# --- zapis kandydata ---------------------------------------------------------------------------------------------------

def _log(pair, event, actor=None, **details):
    from news.clinic_models import PositionPairEvent
    PositionPairEvent.objects.create(pair=pair, event=event, actor=actor, details=details)


def _diagnosis_for(posts):
    from news.clinic import published_diagnoses
    for post in reversed(posts):  # najpierw B (nowsza)
        found = published_diagnoses().filter(post=post).first()
        if found:
            return found
    return None


def suggest(figure, topic, a_key, b_key, quote_a=None, quote_b=None, context='', *, ai_suggested=False, user=None,
            model='', prompt_version=PROMPT_VERSION, source_check=None, usage=None):
    """Kandydat (status „zgłoszona”, niepubliczny). Ta sama para drugi raz nie powstaje (także po odrzuceniu)."""
    from news.clinic_models import PositionPair
    data = validate(figure, a_key, b_key, quote_a, quote_b, context, topic)
    try:
        with transaction.atomic():
            pair = PositionPair.objects.create(
                figure=figure, topic=data['topic'], a=data['a'], b=data['b'], a_key=data['a']['key'], b_key=data['b']['key'],
                a_date=data['a_date'], b_date=data['b_date'], context=data['context'], ai_suggested=ai_suggested,
                context_source=('ai' if ai_suggested else 'human') if data['context'] else '',
                suggested_by=user, model_name=str(model)[:200], prompt_version=prompt_version if ai_suggested else '',
                source_check=source_check, diagnosis=_diagnosis_for(data['posts']), usage=usage or {})
    except IntegrityError:
        return PositionPair.objects.get(figure=figure, a_key=data['a']['key'], b_key=data['b']['key'])
    _log(pair, 'suggested', actor=user, ai_suggested=ai_suggested, model=str(model)[:200])
    return pair


def from_checks(limit=50) -> dict:
    """Kandydaci z istniejącej pętli „Zmiana zdania” (PositionCheck: zmiana stanowiska od progu, cytaty sprawdzone).
    Ta sama reguła dla każdej osoby; wynik to tylko kandydaci do decyzji człowieka."""
    from news.clinic_models import PositionCheck, PositionPair
    from news.zmiana_zdania import MIN_CONFIDENCE, person
    rows = (PositionCheck.objects.filter(relation='change', confidence__gte=MIN_CONFIDENCE, diagnosis__status='approved',
                                         diagnosis__withdrawn_at__isnull=True, diagnosis__hidden_at__isnull=True)
            .select_related('diagnosis__post').order_by('-checked_at', '-pk')[:limit])
    created = skipped = 0
    reasons = []
    for check in rows:
        figure, _ = person(check.diagnosis)
        if figure is None:
            skipped += 1
            continue
        b_key = f'post:{check.diagnosis.post_id}'
        if PositionPair.objects.filter(figure=figure, a_key=check.source_key, b_key=b_key).exists():
            continue
        # Temat tylko z tytułu źródła (głosowanie, wystąpienie); dla dwóch wpisów temat wpisuje człowiek przy zatwierdzeniu.
        topic = check.source_title[:MAX_TOPIC] if check.source_kind != 'post' else ''
        context = check.explanation if not check_text(_clean(check.explanation), MAX_CONTEXT, 'kontekst') else ''
        try:
            suggest(figure, topic, check.source_key, b_key, check.quote_then, check.quote_now, context, ai_suggested=True,
                    model=check.model_name, source_check=check, usage={'from': 'zmiana_zdania', 'confidence': check.confidence})
            created += 1
        except PairError as error:
            skipped += 1
            reasons.append(f'check {check.pk}: {error}')
    return {'created': created, 'skipped': skipped, 'reasons': reasons[:20]}


def topic_items(figure, topic, limit=400) -> list[dict]:
    """Materiały osoby, w których pada temat (bez polskich znaków i wielkości liter), od najnowszych."""
    from news.political_models import PoliticalPost
    from news.przeszlosc import terms
    from news.przeszlosc_osoba import DECISIVE, _ballots, _records, fold, mp_identities, words, x_accounts
    from news.zmiana_zdania import STOP
    # Każdy wariant tematu (oddzielony przecinkiem) jako zestaw 5-literowych początków słów: odmiana nie rozbija dopasowania
    # („podatek” i „podatku”); materiał pasuje, gdy zawiera wszystkie początki jednego wariantu.
    variants = [{w[:5] for w in words(t) if len(w) >= 4 and w not in STOP} for t in (terms(topic) or [topic])]
    variants = [v for v in variants if v]

    def hit(text):
        present = {w[:5] for w in words(text)}
        return any(v <= present for v in variants)

    keys = []
    accounts = [a for a, _ in x_accounts(figure)]
    for p in PoliticalPost.objects.filter(account__in=accounts, available=True).order_by('-published_at')[:2000]:
        if hit(p.text) and not p.text.startswith('RT @'):
            keys.append(f'post:{p.pk}')
    identities = mp_identities(figure)
    if identities:
        for link in _records(figure, identities).filter(record__kind='statement').select_related('record').order_by('-record__date')[:1000]:
            if hit(f'{link.record.title} {link.record.text}'):
                keys.append(f'record:{link.record_id}')
        for b in (_ballots(identities).filter(vote__in=DECISIVE).select_related('voting__article')
                  .order_by('-voting__article__published_date')[:2000]):
            if hit(f'{b.voting.article.title} {b.voting.motion}'):
                keys.append(f'ballot:{b.pk}')
    items = [m for m in (material(figure, k) for k in keys[:limit]) if m and m['date']]
    items.sort(key=lambda m: m['date'], reverse=True)
    return items


def from_topic(figure, topic, *, ask=None, max_asks=MAX_ASKS) -> dict:
    """Kandydaci dla jednej osoby i tematu: nowsza wypowiedź albo głos (B) i najbliższe tematycznie wcześniejsze (A),
    co najmniej MIN_GAP_DAYS wcześniej; ocenę „zmiana stanowiska” daje model z tym samym poleceniem co pętla Zmiana zdania.
    Głosy porównujemy z deklaracjami (wpisy, wystąpienia) w obie strony. Tylko kandydaci."""
    from news import zmiana_zdania as zz
    ask = ask or zz.ask
    items = topic_items(figure, topic)
    asked = created = 0
    reasons = []
    for b in items[:5]:
        b_stems = zz.stems(b['text'])
        older = []
        for a in items:
            if a['date'] and (b['date'] - a['date']).days >= zz.MIN_GAP_DAYS and not (a['kind'] == b['kind'] == 'glos'):
                shared, score = zz.similarity(b_stems, zz.stems(a['text']))
                if shared >= 1:  # temat już wspólny (topic_items); kolejność po podobieństwie
                    older.append((score, a))
        older.sort(key=lambda row: (-row[0], -row[1]['date'].toordinal()))
        for _, a in older[:2]:
            if asked >= max_asks:
                break
            payload = {'obecna_wypowiedz': {'rodzaj': KIND_LABEL[b['kind']], 'data': b['date'].isoformat(), 'tekst': b['text'][:3000]},
                       'wczesniejsza_wypowiedz': {'rodzaj': KIND_LABEL[a['kind']], 'data': a['date'].isoformat(), 'tekst': a['text'][:3000]}}
            try:
                answer, model = ask(payload)
            except Exception as error:  # noqa: BLE001 - brak modelu = brak kandydata, nie błąd
                reasons.append(f'model: {str(error)[:120]}')
                return {'asked': asked, 'created': created, 'reasons': reasons}
            asked += 1
            relation = zz.RELATIONS.get(str(answer.get('relation', '')).strip().lower())
            try:
                confidence = int(answer.get('confidence') or 0)
            except (TypeError, ValueError):
                confidence = 0
            if relation != 'change' or confidence < zz.MIN_CONFIDENCE:
                continue
            explanation = _clean(answer.get('explanation'))
            context = explanation if not check_text(explanation, MAX_CONTEXT, 'kontekst') else ''
            try:
                suggest(figure, topic, a['key'], b['key'], answer.get('quote_then'), answer.get('quote_now'), context,
                        ai_suggested=True, model=model, usage={'from': 'temat', 'confidence': confidence})
                created += 1
            except PairError as error:
                reasons.append(f"{a['key']}/{b['key']}: {error}")
    return {'asked': asked, 'created': created, 'reasons': reasons[:20]}


# --- decyzje człowieka -------------------------------------------------------------------------------------------------

def _decide(pair, user, to, allowed, event, note='', **details):
    from news.clinic_models import PositionPair
    with transaction.atomic():
        pair = PositionPair.objects.select_for_update().get(pk=pair.pk)
        if pair.status not in allowed:
            raise PairError('decided', [f'Para ma status {pair.status}.'])
        pair.status, pair.decided_at, pair.review_note = to, timezone.now(), note[:400]
        fields = ['status', 'decided_at', 'review_note']
        if to == 'approved':
            pair.approved_at, pair.approved_by = pair.decided_at, user
            fields += ['approved_at', 'approved_by']
        pair.save(update_fields=fields)
        open_reports = list(pair.reports.filter(resolved_at__isnull=True))
        pair.reports.filter(resolved_at__isnull=True).update(resolved_at=pair.decided_at)
        _log(pair, event, actor=user, note=note[:400], **details)
    send_decisions(pair, open_reports, event, note)
    return pair


def approve(pair, user, note='', *, confirm_subject=False, context=None, topic=None):
    """Zatwierdzenie (recenzja Fable, poprawki 2, 4, 7): cztery oczy (inna osoba niż zgłaszający kandydata), temat
    i kontekst obowiązkowe (kontekst od człowieka nadpisuje kontekst AI), przedmiot głosowania innego niż całość projektu
    wymaga jawnego potwierdzenia (confirm_subject)."""
    if silence():
        raise PairError('silence', ['Cisza wyborcza: zatwierdzanie wstrzymane.'])
    if user is not None and pair.suggested_by_id and pair.suggested_by_id == getattr(user, 'pk', None):
        raise PairError('four_eyes', ['Parę zatwierdza inna osoba niż ta, która ją zgłosiła (zasada czterech oczu).'])
    materials = [material(pair.figure, pair.a_key), material(pair.figure, pair.b_key)]
    if any(m is None for m in materials):
        raise PairError('invalid', ['Materiał nie należy już do tej osoby albo został usunięty.'])
    if any(not m.get('available', True) for m in materials):
        raise PairError('unavailable', ['Wpis z tej pary jest już niedostępny na X; para nie może być zatwierdzona.'])
    changed = []
    if topic is not None and _clean(topic) != pair.topic:
        issues = check_text(_clean(topic), MAX_TOPIC, 'temat')
        if issues:
            raise PairError('invalid', issues)
        pair.topic = _clean(topic)
        changed.append('topic')
    if context is not None and _clean(context):
        issues = check_text(_clean(context), MAX_CONTEXT, 'kontekst')
        if issues:
            raise PairError('invalid', issues)
        pair.context, pair.context_source = _clean(context), 'human'
        changed += ['context', 'context_source']
    if not pair.topic:
        raise PairError('topic', ['Para wymaga tematu (opisowo, od człowieka albo z tytułu źródła).'])
    if not pair.context:
        raise PairError('context', ['Para wymaga kontekstu: jedno opisowe zdanie, co łączy obie wypowiedzi.'])
    targets = [side.get('vote_target') for side in (pair.a, pair.b) if side.get('kind') == 'glos']
    if any(t != 'całość' for t in targets) and not confirm_subject:
        raise PairError('subject', ['Głos nie dotyczy całości projektu (' + ', '.join(t for t in targets if t != 'całość')
                                    + '): potwierdź przedmiot głosowania (--potwierdzam-przedmiot) i opisz go w kontekście.'])
    if changed:
        pair.save(update_fields=changed)
    pair = _decide(pair, user, 'approved', ('suggested',), 'approved', note, confirm_subject=bool(confirm_subject),
                   context_source=pair.context_source, vote_targets=targets)
    notify_followers(pair)
    return pair


def reject(pair, user, note=''):
    return _decide(pair, user, 'rejected', ('suggested',), 'rejected', note)


def withdraw(pair, user, note):
    """Wycofanie zatwierdzonej pary z publicznym powodem (rejestr korekt przeszłości: /api/przeszlosc/poprawki/)."""
    if not note.strip():
        raise PairError('note', ['Wycofanie wymaga publicznego powodu.'])
    pair = _decide(pair, user, 'withdrawn', ('approved',), 'withdrawn', note)
    notify_withdrawn(pair, note)
    return pair


def notify_withdrawn(pair, note) -> int:
    """Decyzja właściciela 13.10: kto dostał powiadomienie o parze, dostaje powiadomienie o jej wycofaniu z publicznym powodem."""
    from news.notification_models import Notification
    from news.przeszlosc_osoba import slug
    title = f'Zestawienie wycofane: {pair.topic}. Powód: {note.strip()}'[:240]
    sent = 0
    for user_id in (Notification.objects.filter(group_key__startswith=f'pair:{pair.pk}:', kind='position_pair')
                    .values_list('user_id', flat=True).distinct()):
        _, created = Notification.objects.get_or_create(
            group_key=f'pair-withdrawn:{pair.pk}:{user_id}',
            defaults={'user_id': user_id, 'figure': pair.figure, 'kind': 'position_pair_withdrawn', 'title': title,
                      'url': f'/przeszlosc/osoba/{slug(pair.figure)}#poprawki'})
        sent += int(created)
    return sent


# --- odpowiedź osoby obok pary (decyzja właściciela 13.10) ---------------------------------------------------------------

RESPONSE_LABEL = 'Odpowiedź osoby'


def submit_response(pair, text, *, user=None, token=None):
    """Odpowiedź osoby (do 600 znaków): tylko od zweryfikowanego zgłaszającego (VerifiedReporter tej osoby) albo z
    potwierdzonego adresu urzędowego (token zgłoszenia z official_domain). Publiczna dopiero po decyzji personelu."""
    from news.clinic_models import PositionPairReport, SubjectResponse
    text = ' '.join(str(text or '').split())
    if not 10 <= len(text) <= 600:
        raise PairError('text', ['Odpowiedź: od 10 do 600 znaków.'])
    if pair.status != 'approved' or pair.approved_at is None:  # recenzja Codex 3: tylko para opublikowana
        raise PairError('pair', ['Odpowiedź można dodać tylko do opublikowanej pary.'])
    from news import v3_tokens
    now = timezone.now()
    report = None
    if verified_reporter(user, pair.figure):
        via = 'verified_reporter'
    else:
        report = v3_tokens.find(PositionPairReport.objects.filter(pair=pair, official_domain=True, email_confirmed_at__isnull=False),
                                'response_token', token)
        if report is None or report.response_token_used_at or (report.response_token_expires_at and now > report.response_token_expires_at):
            raise PairError('not_allowed', ['Odpowiedź dodaje osoba zweryfikowana albo z potwierdzonego adresu urzędowego.'])
        via = 'official_email'
    row = SubjectResponse.objects.create(pair=pair, text=text, via=via, report=report,
                                         user=user if getattr(user, 'is_authenticated', False) else None)
    if report is not None:  # token jednorazowy
        report.response_token_used_at = now
        report.save(update_fields=['response_token_used_at'])
    _log(pair, 'response_submitted', response=row.pk, via=via)
    return row


def decide_response(row, user, publish, note=''):
    if row.status != 'zgloszona':
        raise PairError('decided', [f'Odpowiedź ma status {row.status}.'])
    if not publish and not note.strip():
        raise PairError('note', ['Odrzucenie odpowiedzi wymaga uzasadnienia.'])
    row.status = 'opublikowana' if publish else 'odrzucona'
    row.decided_by, row.decided_at, row.decision_note = user, timezone.now(), note[:400]
    row.save(update_fields=['status', 'decided_by', 'decided_at', 'decision_note'])
    _log(row.pair, 'response_published' if publish else 'response_rejected', actor=user, response=row.pk, note=note[:400])
    return row


# --- zgłoszenia błędów (procedura sprostowania) ------------------------------------------------------------------------

def ip_hash(ip) -> str:
    """Skrót adresu IP z solą serwisu (do liczenia niezależnych zgłoszeń); sam adres nie jest zapisywany (RODO)."""
    import hashlib
    return hashlib.sha256(f'{settings.SECRET_KEY}:pary:{ip or ""}'.encode('utf-8')).hexdigest() if ip else ''


def verified_reporter(user, figure) -> bool:
    """Konto potwierdzone przez personel jako osoba z pary albo jej przedstawiciel (VerifiedReporter)."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    from news.clinic_models import VerifiedReporter
    return VerifiedReporter.objects.filter(user=user, figure=figure, revoked_at__isnull=True).exists()


def independent_reports(pair, now=None) -> int:
    """Niezależne zgłoszenia z okna (domyślnie 24 h): tylko z kont starszych niż POSITION_PAIR_ACCOUNT_MIN_AGE_DAYS
    (domyślnie 7 dni), każde z innego konta i innego skrótu IP."""
    from news.clinic_models import PositionPairReport
    now = now or timezone.now()
    window = timedelta(hours=int(getattr(settings, 'POSITION_PAIR_REPORT_WINDOW_HOURS', 24)))
    min_age = timedelta(days=int(getattr(settings, 'POSITION_PAIR_ACCOUNT_MIN_AGE_DAYS', 7)))
    users, ips, count = set(), set(), 0
    for user_id, digest in (PositionPairReport.objects.filter(pair=pair, resolved_at__isnull=True, created_at__gte=now - window,
                                                              user__isnull=False, user__date_joined__lte=now - min_age)
                            .order_by('created_at').values_list('user_id', 'ip_hash')):
        if user_id in users or not digest or digest in ips:
            continue
        users.add(user_id)
        ips.add(digest)
        count += 1
    return count


EMAIL = re.compile(r'^[^@\s]+@([^@\s]+\.[^@\s]+)$')


def official_domain(email) -> bool:
    """Adres z domeny urzędowej albo partyjnej z listy (news/official_domains.py: plik, env, dziennik zmian)."""
    if not EMAIL.match((email or '').strip().lower()):
        return False
    from news.official_domains import match
    return match(email) is not None


def _site() -> str:
    return getattr(settings, 'PUBLIC_SITE_URL', '') or 'https://przeszlosc.today'


def _mail(to, subject, body) -> bool:
    """Wiadomość do zgłaszającego (szablon bez ocen); błąd poczty nie zatrzymuje procedury (zapis w dzienniku)."""
    from django.core.mail import send_mail
    try:
        send_mail(subject, body, getattr(settings, 'DEFAULT_FROM_EMAIL', None), [to], fail_silently=False)
        return True
    except Exception as error:  # noqa: BLE001
        logger.warning('pary: poczta do zgłaszającego nie wyszła: %s', type(error).__name__)
        return False


def _hide(pair, why):
    pair.status, pair.review_note = 'suggested', why[:400]
    pair.save(update_fields=['status', 'review_note'])


def report(pair, reason, contact='', is_subject=False, *, user=None, ip=None):
    """Zgłoszenie błędu (procedura sprostowania; recenzje Codex 2 i Fable). Zawsze trafia do kolejki moderacji.
    Para znika z API automatycznie tylko, gdy: (a) zgłasza konto potwierdzone jako osoba z pary albo jej przedstawiciel,
    (b) jest co najmniej POSITION_PAIR_REPORT_THRESHOLD niezależnych zgłoszeń z kont (wiek >= 7 dni) w oknie 24 h,
    (c) później: osoba potwierdzi e-mail z domeny urzędowej z listy (confirm_report).
    Zgłoszenie „dotyczy mnie” z adresem e-mail dostaje link potwierdzający (48 h); bez potwierdzenia priorytet zwykły."""
    from news import v3_tokens
    from news.clinic_models import PositionPair, PositionPairReport
    user = user if getattr(user, 'is_authenticated', False) else None
    verified = verified_reporter(user, pair.figure)
    contact = (contact or '').strip()[:200]
    token, token_hash = v3_tokens.new() if (is_subject and EMAIL.match(contact.lower())) else ('', '')
    hours = int(getattr(settings, 'POSITION_PAIR_CONFIRM_HOURS', 48))
    with transaction.atomic():
        pair = PositionPair.objects.select_for_update().get(pk=pair.pk)
        row = PositionPairReport.objects.create(
            pair=pair, reason=reason[:1000], contact=contact, is_subject=is_subject, user=user, ip_hash=ip_hash(ip),
            verified=verified, priority='wysoki' if verified else 'zwykly', confirm_token=token_hash,
            token_expires_at=timezone.now() + timedelta(hours=hours) if token else None)
        threshold = int(getattr(settings, 'POSITION_PAIR_REPORT_THRESHOLD', 3))
        independent = independent_reports(pair)
        hide = pair.status == 'approved' and (verified or independent >= threshold)
        if hide:
            _hide(pair, f'zgłoszenie osoby zweryfikowanej #{row.pk}' if verified
                  else f'{independent} niezależne zgłoszenia, ostatnie #{row.pk}')
        _log(pair, 'reported', report=row.pk, is_subject=is_subject, verified=verified, independent=independent, hidden=hide,
             confirm_sent=bool(token))
    if token:
        _mail(contact, 'Potwierdź zgłoszenie dotyczące zestawienia wypowiedzi',
              f'Otrzymaliśmy zgłoszenie dotyczące zestawienia „{pair.topic}”. Jeśli to Ty je wysłałeś(-aś), potwierdź adres '
              f'w ciągu {hours} godzin: {_site()}/api/stanowiska/zgloszenie/potwierdz/{token}/\n\n'
              'Po potwierdzeniu zgłoszenie rozpatrzy człowiek i odpowie na ten adres. Jeśli to nie Ty, zignoruj tę wiadomość.\n'
              'Kontakt: kontakt@iapply.pl')
    return row, hide


def confirm_report(token, now=None):
    """Potwierdzenie adresu e-mail osoby (link 48 h). Domena z listy urzędowej/partyjnej = zdjęcie pary jak VerifiedReporter;
    inna = priorytet wysoki i oznaczenie review_pending. Zwraca (zgłoszenie, ukryto) albo PairError."""
    from news import v3_tokens
    from news.clinic_models import PositionPair, PositionPairReport
    now = now or timezone.now()
    row = v3_tokens.find(PositionPairReport.objects.exclude(confirm_token='').select_related('pair'), 'confirm_token', token)
    if row is None:
        raise PairError('token', ['Nieznany link potwierdzający.'])
    if row.token_used_at or row.email_confirmed_at:
        raise PairError('used', ['Ten link został już użyty.'])  # jednorazowy: powtórka nie działa
    expires = row.token_expires_at or row.created_at + timedelta(hours=int(getattr(settings, 'POSITION_PAIR_CONFIRM_HOURS', 48)))
    if now > expires:
        raise PairError('expired', ['Link wygasł. Wyślij zgłoszenie ponownie.'])
    official = official_domain(row.contact)
    response_token = ''
    with transaction.atomic():
        pair = PositionPair.objects.select_for_update().get(pk=row.pair_id)
        row.email_confirmed_at, row.token_used_at, row.official_domain, row.priority = now, now, official, 'wysoki'
        fields = ['email_confirmed_at', 'token_used_at', 'official_domain', 'priority']
        if official:  # osobny, jednorazowy token do odpowiedzi osoby (14 dni)
            response_token, row.response_token = v3_tokens.new()
            row.response_token_expires_at = now + timedelta(days=14)
            fields += ['response_token', 'response_token_expires_at']
        row.save(update_fields=fields)
        hide = official and pair.status == 'approved' and row.resolved_at is None
        if hide:
            _hide(pair, f'zgłoszenie z potwierdzonego adresu urzędowego #{row.pk}')
        _log(pair, 'report_confirmed', report=row.pk, official_domain=official, hidden=hide)
    if response_token:
        _mail(row.contact, 'Zgłoszenie potwierdzone: możesz dodać odpowiedź',
              f'Zgłoszenie dotyczące zestawienia „{pair.topic}” zostało potwierdzone i trafiło do przeglądu.\n'
              f'Jeśli chcesz, by obok zestawienia ukazała się Twoja odpowiedź (do 600 znaków), wyślij ją z tym kodem w ciągu 14 dni '
              f'(POST {_site()}/api/stanowiska/{pair.pk}/odpowiedz/, pole token): {response_token}\nKontakt: kontakt@iapply.pl')
    return row, hide


DECISION_TEXT = {
    'approved': 'Zestawienie zostało ponownie sprawdzone i pozostaje opublikowane.',
    'rejected': 'Zestawienie nie zostanie opublikowane.',
    'withdrawn': 'Zestawienie zostało wycofane; wpis znajduje się w publicznym rejestrze korekt.',
    'reports_resolved': 'Zestawienie zostało sprawdzone i pozostaje bez zmian.',
}


def send_decisions(pair, reports, event, note) -> int:
    """Odpowiedź do zgłaszających z potwierdzonym adresem: decyzja i powód z szablonu (bez danych innych osób)."""
    sent = 0
    for row in reports:
        if not row.email_confirmed_at or not row.contact or row.decision_sent_at or event not in DECISION_TEXT:
            continue
        body = (f'Dziękujemy za zgłoszenie dotyczące zestawienia „{pair.topic}”.\n\n{DECISION_TEXT[event]}\n'
                + (f'Uzasadnienie: {note.strip()}\n' if note.strip() else '') +
                '\nJeśli chcesz, by obok zestawienia ukazało się Twoje stanowisko (do 280 znaków), odpowiedz na tę wiadomość.\n'
                'Kontakt: kontakt@iapply.pl')
        if _mail(row.contact, 'Decyzja w sprawie zgłoszenia', body):
            row.decision_sent_at = timezone.now()
            row.save(update_fields=['decision_sent_at'])
            sent += 1
    return sent


def resolve_reports(pair, user, note):
    """Człowiek rozpatrzył zgłoszenia i zostawia zatwierdzoną parę bez zmian (uzasadnienie w dzienniku i do zgłaszających)."""
    if not note.strip():
        raise PairError('note', ['Rozpatrzenie zgłoszeń wymaga uzasadnienia.'])
    now = timezone.now()
    open_reports = list(pair.reports.filter(resolved_at__isnull=True))
    done = pair.reports.filter(resolved_at__isnull=True).update(resolved_at=now)
    _log(pair, 'reports_resolved', actor=user, note=note[:400], reports=done)
    send_decisions(pair, open_reports, 'reports_resolved', note)
    return done


def clean_contacts(days=None, now=None) -> int:
    """Retencja danych zgłaszających: po `days` (domyślnie POSITION_PAIR_CONTACT_RETENTION_DAYS) od rozstrzygnięcia
    czyścimy adres kontaktowy i token (pary i ciągi przyczyn). Treść zgłoszenia i skrót IP zostają w rejestrze decyzji."""
    from news.clinic_models import CausalChainReport, PositionPairReport
    now = now or timezone.now()
    days = int(days if days is not None else getattr(settings, 'POSITION_PAIR_CONTACT_RETENTION_DAYS', 90))
    cutoff = now - timedelta(days=days)
    cleaned = (PositionPairReport.objects.filter(resolved_at__lte=cutoff).exclude(contact='', confirm_token='', response_token='')
               .update(contact='', confirm_token='', response_token=''))
    from news.clinic_models import DataObjection  # recenzja Codex 3: także sprzeciwy RODO po decyzji
    cleaned += (DataObjection.objects.filter(decided_at__lte=cutoff).exclude(contact='', confirm_token='')
                .update(contact='', confirm_token=''))
    cleaned += CausalChainReport.objects.filter(resolved_at__lte=cutoff).exclude(contact='').update(contact='')
    return cleaned


def notify_followers(pair) -> int:
    """Powiadomienie obserwujących osobę: neutralny tekst z tematem, tylko po zatwierdzeniu, przy fladze i poza ciszą."""
    if not enabled() or silence() or pair.status != 'approved':
        return 0
    from news.notification_models import Follow, Notification
    from news.przeszlosc_osoba import slug
    url = f'/przeszlosc/osoba/{slug(pair.figure)}#stanowiska-{pair.pk}'
    title = ALERT_TITLE.format(topic=pair.topic)[:240]
    sent = 0
    for user_id in Follow.objects.filter(figure=pair.figure).values_list('user_id', flat=True):
        _, created = Notification.objects.get_or_create(
            group_key=f'pair:{pair.pk}:{user_id}',
            defaults={'user_id': user_id, 'figure': pair.figure, 'kind': 'position_pair', 'title': title, 'url': url})
        sent += int(created)
    return sent


# --- dane publiczne ----------------------------------------------------------------------------------------------------

REVIEW_PENDING_NOTE = 'Do tej pary wpłynęło zgłoszenie. Czeka na przegląd.'
CONTEXT_NOTE = {'ai': 'Kontekst napisała AI, człowiek go zatwierdził.', 'human': 'Kontekst napisał człowiek.'}


def public_item(pair, review_pending=False, response=None) -> dict:
    def side(data):
        out = {key: data.get(key) for key in ('kind', 'kind_label', 'date', 'quote', 'vote', 'source')}
        if data.get('kind') == 'glos':
            out.update({key: data.get(key) for key in ('vote_target', 'vote_label', 'vote_subject')})
        return out
    return {'id': pair.pk, 'topic': pair.topic, 'a': side(pair.a), 'b': side(pair.b), 'context': pair.context,
            'context_source': pair.context_source, 'context_note': CONTEXT_NOTE.get(pair.context_source, ''),
            'approved_at': pair.approved_at, 'ai_suggested': pair.ai_suggested, 'notice': NOTICE,
            'review_pending': bool(review_pending), 'review_note': REVIEW_PENDING_NOTE if review_pending else '',
            'subject_response': ({'label': RESPONSE_LABEL, 'text': response.text, 'date': response.submitted_at.date().isoformat()}
                                 if response else None),
            'report_url': f'/api/stanowiska/{pair.pk}/zgloszenie/'}


def public_queryset():
    from news.clinic_models import PositionPair
    return PositionPair.objects.filter(status='approved', approved_at__isnull=False)


def _visible(pairs) -> list:
    """Bez par, których wpis zniknął z X (tak jak diagnozy)."""
    from news.political_models import PoliticalPost
    keys = {int(k.split(':')[1]) for p in pairs for k in (p.a_key, p.b_key) if k.startswith('post:')}
    gone = set(PoliticalPost.objects.filter(pk__in=keys, available=False).values_list('pk', flat=True)) if keys else set()
    return [p for p in pairs if not any(k.startswith('post:') and int(k.split(':')[1]) in gone for k in (p.a_key, p.b_key))]


def block(queryset) -> dict:
    if silence():
        return {'items': [], 'notice': NOTICE, 'paused': True}
    from django.db.models import Q
    from news.clinic_models import PositionPairReport
    pairs = _visible(list(queryset.order_by('-b_date', '-pk')[:PUBLIC_LIMIT]))
    # Recenzja Fable: oznaczenie tylko po zgłoszeniu zweryfikowanym (konto albo potwierdzony e-mail), nie po anonimowym.
    pending = set(PositionPairReport.objects.filter(pair__in=pairs, resolved_at__isnull=True)
                  .filter(Q(verified=True) | Q(email_confirmed_at__isnull=False))
                  .values_list('pair_id', flat=True)) if pairs else set()
    from news.clinic_models import SubjectResponse
    responses = {}
    for r in SubjectResponse.objects.filter(pair__in=pairs, status='opublikowana').order_by('submitted_at') if pairs else []:
        responses[r.pair_id] = r  # najnowsza opublikowana
    return {'items': [public_item(p, p.pk in pending, responses.get(p.pk)) for p in pairs], 'notice': NOTICE, 'paused': False}


def cache_header(response):
    """Pary zależą od ciszy wyborczej i zgłoszeń: bez cache pośredników (recenzja Codex 2)."""
    response['Cache-Control'] = 'no-store'
    return response


def extend_profile(data: dict, figure) -> dict:
    if enabled():
        data['position_pairs'] = block(public_queryset().filter(figure=figure))
    return data


def extend_diagnosis(data: dict, diagnosis) -> dict:
    if enabled():
        key = f'post:{diagnosis.post_id}'
        from django.db.models import Q
        data['position_pairs'] = block(public_queryset().filter(Q(diagnosis=diagnosis) | Q(a_key=key) | Q(b_key=key)))
    return data


def corrections_rows(limit=200) -> list:
    """Wycofane pary do rejestru korekt przeszłości (/api/przeszlosc/poprawki/): typ, data, publiczny powód, odnośnik;
    bez danych zgłaszającego."""
    from news.clinic_models import PositionPair
    from news.przeszlosc_osoba import slug
    rows = []
    for pair in PositionPair.objects.filter(status='withdrawn').select_related('figure').order_by('-decided_at')[:limit]:
        rows.append({'id': f'pair_withdrawal:{pair.pk}', 'type': 'pair_withdrawal',
                     'date': (pair.decided_at or pair.created_at).date().isoformat(), 'record': f'para:{pair.pk}',
                     'label': f'Wycofano zestawienie „{pair.topic}”. Powód: {pair.review_note}'[:240],
                     'href': f'/przeszlosc/osoba/{slug(pair.figure)}'})
    return rows


# --- API ---------------------------------------------------------------------------------------------------------------

from rest_framework import serializers  # noqa: E402
from rest_framework.decorators import api_view, permission_classes, throttle_classes  # noqa: E402
from rest_framework.permissions import AllowAny  # noqa: E402
from rest_framework.response import Response  # noqa: E402
from rest_framework.throttling import SimpleRateThrottle  # noqa: E402

DISABLED = {'detail': 'Funkcja jeszcze wyłączona.'}
REPORT_PRIVACY = ('Adres e-mail służy tylko do potwierdzenia zgłoszenia i odpowiedzi; usuwamy go '
                  'po rozstrzygnięciu (okres przechowywania w polityce prywatności). Administrator: iapply sp. z o.o.')


@api_view(['GET'])
@permission_classes([AllowAny])
def pairs_view(request, ident):
    """GET /api/przeszlosc/osoba/<id albo slug>/stanowiska/ - zatwierdzone pary „Wcześniej i teraz”."""
    from news.przeszlosc import enabled as przeszlosc_enabled
    if not enabled() or not przeszlosc_enabled():
        return Response(DISABLED, status=404)
    from news.przeszlosc_osoba import _person, resolve
    figure = resolve(ident)
    if figure is None:
        return Response({'detail': 'Nie ma takiej osoby publicznej w rejestrze.'}, status=404)
    person = _person(figure)
    return cache_header(Response({'person': {k: person[k] for k in ('id', 'slug', 'name')},
                                  **block(public_queryset().filter(figure=figure))}))


class ReportThrottle(SimpleRateThrottle):
    """5 zgłoszeń na godzinę z jednego adresu IP - także dla zalogowanych."""
    scope = 'position_pair_report'
    rate = '5/hour'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class ReportInput(serializers.Serializer):
    reason = serializers.CharField(min_length=20, max_length=1000)
    contact = serializers.CharField(required=False, allow_blank=True, max_length=200, default='')
    is_subject = serializers.BooleanField(required=False, default=False)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ReportThrottle])
def report_view(request, pair_id):
    """POST /api/stanowiska/<id>/zgloszenie/ - zgłoszenie błędu przy zatwierdzonej parze (procedura sprostowania)."""
    if not enabled():
        return Response(DISABLED, status=404)
    pair = public_queryset().filter(pk=pair_id).first()
    if pair is None:
        return Response({'detail': 'Nie ma takiej pary.'}, status=404)
    serializer = ReportInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    row, hidden = report(pair, data['reason'], data['contact'], data['is_subject'], user=request.user,
                         ip=ReportThrottle().get_ident(request))
    return cache_header(Response({'status': 'received', 'hidden': hidden, 'confirm_email_sent': bool(row.confirm_token),
                                  'privacy': REPORT_PRIVACY}, status=202))


@api_view(['GET'])
@permission_classes([AllowAny])
def confirm_view(request, token):
    """GET /api/stanowiska/zgloszenie/potwierdz/<token>/ - potwierdzenie adresu e-mail zgłaszającego (link 48 h)."""
    if not enabled():
        return Response(DISABLED, status=404)
    try:
        _, hidden = confirm_report(token)
    except PairError as error:
        return cache_header(Response({'detail': str(error), 'code': error.code}, status=410 if error.code in ('expired', 'used') else 404))
    return cache_header(Response({'status': 'confirmed', 'hidden': hidden}))


class ResponseInput(serializers.Serializer):
    text = serializers.CharField(min_length=10, max_length=600)
    token = serializers.CharField(required=False, allow_blank=True, max_length=64, default='')


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ReportThrottle])
def response_view(request, pair_id):
    """POST /api/stanowiska/<id>/odpowiedz/ - odpowiedź osoby (zweryfikowane konto albo token potwierdzonego zgłoszenia
    z adresu urzędowego); publiczna po zatwierdzeniu przez personel."""
    from news.clinic_models import PositionPair
    if not enabled():
        return Response(DISABLED, status=404)
    pair = public_queryset().filter(pk=pair_id).first()  # niepubliczna para = jak nieistniejąca (bez enumeracji)
    if pair is None:
        return cache_header(Response({'detail': 'Nie ma takiej pary.'}, status=404))
    serializer = ResponseInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        submit_response(pair, serializer.validated_data['text'], user=request.user, token=serializer.validated_data['token'])
    except PairError as error:
        return cache_header(Response({'detail': str(error), 'code': error.code}, status=403 if error.code == 'not_allowed' else 400))
    return cache_header(Response({'status': 'received', 'detail': 'Odpowiedź ukaże się po sprawdzeniu przez zespół.'}, status=202))
