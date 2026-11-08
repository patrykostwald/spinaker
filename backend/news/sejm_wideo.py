"""Wystąpienia posłów z nagrań Sejmu -> Dr. Spin (raport źródeł 6.10, punkt 1).

Dane: zbieracz scraper.nowe_zrodla ('videos': lista transmisji i zapisy przebiegu posiedzeń komisji) oraz istniejący
zbieracz wystąpień z sali ('statements'). Nagrań nie pobieramy; tekst wystąpienia jest urzędowy (API Sejmu).

Wybór (ta sama miara dla wszystkich): codziennie najwyżej SEJM_VIDEO_SPIN_DAILY wystąpień (domyślnie 3) z dnia, które mają
osobę w rejestrze i co najmniej SEJM_VIDEO_SPIN_MIN_WORDS słów; kolejność tylko po długości wystąpienia, jedno na osobę
dziennie, bez przewodniczących i sekretarzy. Partia, obóz ani nazwisko nie wpływają na wybór.

Diagnoza: ta sama ścieżka co wpisy z X (clinic_ai.diagnose -> Konsylium, kworum, rezerwa limitów na treść); bez kworum
wpis czeka w kolejce. Osobny dzienny budżet SEJM_VIDEO_SPIN_BUDGET_USD (domyślnie 1 USD).
Miejsce w nagraniu: sala - sekunda z czasu wystąpienia w API Sejmu (dokładna); komisja - szacunek z położenia
wystąpienia w zapisie przebiegu (oznaczony „ok.”).
"""
from datetime import datetime, timedelta
import logging
import os

from django.db.models import Q
from django.utils import timezone

from news.repairer import flag

logger = logging.getLogger(__name__)
CHAIR = ('marszałek', 'wicemarszałek', 'przewodnicząc', 'sekretarz')


def enabled():
    from news import clinic_ai
    return flag('SEJM_VIDEO_SPIN_ENABLED', False) and clinic_ai.enabled()


def _env_int(name, default, low=1, high=50):
    try:
        return min(high, max(low, int(os.environ.get(name, default))))
    except ValueError:
        return default


def _dt(value):
    try:
        moment = datetime.fromisoformat(str(value)[:19])
    except (TypeError, ValueError):
        return None
    return moment


def timecode(seconds):
    if seconds is None:
        return ''
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def video_link(player, seconds):
    """Odtwarzacz Sejmu z sekundą (fragment #t= - odtwarzacz, który go nie obsługuje, i tak otwiera nagranie)."""
    return f'{player}#t={int(seconds)}' if player and seconds is not None else player or ''


def plenary_video(day, moment):
    """Transmisja z sali obejmująca chwilę wystąpienia (nie komisja); (nagranie, sekunda) albo (None, None)."""
    from news.public_records_models import PublicRecord
    if moment is None:
        return None, None
    for video in PublicRecord.objects.filter(source='videos', kind='video', date=day).order_by('pk'):
        data = video.data or {}
        if data.get('type') in ('komisja', 'podkomisja') or data.get('committee'):
            continue
        start, end = _dt(data.get('start')), _dt(data.get('end'))
        if start and end and start <= moment <= end:
            return video, int((moment - start).total_seconds())
    return None, None


def _figure(record):
    person = next((p for p in record.people.all() if p.figure_id and not p.figure.archived), None)
    return person.figure if person else None


def candidates(day):
    """Wystąpienia z dnia gotowe do diagnozy (bez już wybranych), posortowane tym samym kryterium dla wszystkich."""
    from news.public_records_models import PublicRecord
    min_words = _env_int('SEJM_VIDEO_SPIN_MIN_WORDS', 150, 20, 2000)
    rows = []
    taken = Q(video_spin__isnull=False)
    plenary = (PublicRecord.objects.filter(source='statements', kind='statement', date=day).exclude(taken)
               .prefetch_related('people__figure'))
    for record in plenary:
        data = record.data or {}
        function = str(data.get('function') or data.get('name') or '').casefold()
        words = len((record.text or '').split())
        figure = _figure(record)
        if (not figure or data.get('secretary') or data.get('unspoken') or words < min_words
                or any(word in function for word in CHAIR)):
            continue
        video, offset = plenary_video(day, _dt(data.get('startDateTime')))
        if video is None:
            continue
        rows.append({'record': record, 'figure': figure, 'place': 'sala', 'words': words, 'video': video.data['unid'],
                     'player': video.data.get('player', ''), 'offset': offset, 'exact': True})
    committees = (PublicRecord.objects.filter(source='videos', kind='committee_speech', date=day).exclude(taken)
                  .prefetch_related('people__figure'))
    for record in committees:
        data = record.data or {}
        words = len((record.text or '').split())
        figure = _figure(record)
        if not figure or words < min_words:
            continue
        start, end = _dt(data.get('video_start')), _dt(data.get('video_end'))
        offset = int((end - start).total_seconds() * float(data.get('position') or 0)) if start and end else None
        rows.append({'record': record, 'figure': figure, 'place': 'komisja', 'words': words, 'video': data.get('unid', ''),
                     'player': data.get('player', ''), 'offset': offset, 'exact': False})
    rows.sort(key=lambda r: (-r['words'], r['record'].pk))
    seen, out = set(), []
    for row in rows:
        if row['figure'].pk in seen:
            continue
        seen.add(row['figure'].pk)
        out.append(row)
    return out


def select(day):
    """Dzienny wybór: dopełnia do SEJM_VIDEO_SPIN_DAILY wystąpień z dnia (osoby już wybrane tego dnia pomija)."""
    from news.zrodla_models import SejmVideoSpin
    daily = _env_int('SEJM_VIDEO_SPIN_DAILY', 3, 0, 20)
    chosen = SejmVideoSpin.objects.filter(day=day)
    free = daily - chosen.count()
    if free <= 0:
        return []
    people = set(chosen.values_list('figure_id', flat=True))
    created = []
    for row in candidates(day):
        if row['figure'].pk in people:
            continue
        created.append(SejmVideoSpin.objects.create(
            record=row['record'], figure=row['figure'], day=day, place=row['place'], video_unid=row['video'][:32],
            video_url=video_link(row['player'], row['offset'])[:1024], offset_seconds=row['offset'],
            offset_exact=row['exact'], rank_score=row['words']))
        people.add(row['figure'].pk)
        if len(created) >= free:
            break
    return created


def spent_today():
    from news import clinic, clinic_ai
    from news.zrodla_models import SejmVideoSpin
    start = clinic.local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    return round(sum(clinic_ai.cost_usd(u or {}) for u in
                     SejmVideoSpin.objects.filter(diagnosed_at__gte=start).values_list('usage', flat=True)), 4)


def budget_left():
    try:
        budget = float(os.environ.get('SEJM_VIDEO_SPIN_BUDGET_USD', '') or 1.0)
    except ValueError:
        budget = 1.0
    return round(budget - spent_today(), 4)


def context(row):
    from news import clinic
    from news.przeszlosc_osoba import x_accounts
    figure, record = row.figure, row.record
    party = clinic.party_data(figure)
    accounts = x_accounts(figure) if figure else []
    camp = accounts[0][0].camp if accounts else 'unassigned'
    place = 'na sali posiedzeń Sejmu' if row.place == 'sala' else f"w komisji: {record.data.get('committee', '')}"
    when = (record.data or {}).get('startDateTime') or row.day.isoformat()
    agenda = (record.data or {}).get('agenda', '')
    text = record.text or ''
    limit = _env_int('SEJM_VIDEO_SPIN_MAX_CHARS', 9000, 1000, 30000)
    return {
        'author': figure.canonical_name if figure else record.title, 'role': figure.role_title if figure else 'Poseł na Sejm RP',
        'club': (party or {}).get('name') or (record.data or {}).get('club', ''),
        'camp_label': clinic.CAMP_PROMPT_LABELS.get(camp, 'bez przypisania do obozu'), 'camp_at_collection': camp,
        'published_at': str(when).replace('T', ' ')[:16], 'url': row.video_url or record.source_url,
        'text': (f'Wystąpienie {place} (zapis urzędowy Kancelarii Sejmu'
                 + (f', punkt: {agenda[:300]}' if agenda else '') + '):\n' + text[:limit]),
        'media_notes': '', 'media': [],
    }


def diagnose(row):
    from news import clinic, clinic_ai
    try:
        result = dict(clinic_ai.diagnose(context(row)))
    except clinic_ai.ClinicAIError as error:
        code = str(error.code)[:240]
        if code.startswith('council_quorum'):
            from news import council_quorum
            council_quorum.block((getattr(error, 'council', None) or {}).get('members') or [], code, timezone.now())
            row.status, row.error = 'queued', code
            row.usage = {**(row.usage or {}), 'quorum': getattr(error, 'quorum', None) or {}}
        else:
            row.status, row.error = 'failed', code
            row.diagnosed_at = timezone.now()
        row.save()
        return row
    usage = result.pop('usage', {}) or {}
    usage['loaded_words'] = result.pop('loaded_words', [])
    for field in ('verdict', 'intensity', 'headline', 'summary', 'plain', 'analysis', 'techniques', 'claims', 'lab',
                  'limitations'):
        if field in result:
            setattr(row, field, result[field])
    row.usage, row.error = usage, ''
    row.model_name = (usage.get('model') or clinic_ai.model_name())[:64]
    row.status = 'approved' if clinic.auto_publish() else 'pending_review'
    row.diagnosed_at = timezone.now()
    row.save()
    return row


def run(limit=1, now=None):
    """Jedno przejście: wybór dnia (wczoraj i dwa dni wcześniej - zapisy komisji ukazują się później) i diagnozy."""
    from news import clinic, clinic_ai
    from news.zrodla_models import SejmVideoSpin
    if not enabled():
        return {'status': 'disabled'}
    today = timezone.localdate(now) if now else timezone.localdate()
    selected = sum(len(select(today - timedelta(days=back))) for back in (1, 2, 3))
    if budget_left() < clinic.diagnosis_reserve():
        return {'status': 'budget', 'selected': selected}
    if clinic_ai.provider() == 'council':
        from news import council_quorum
        wait = council_quorum.waiting()
        state = None if wait else council_quorum.possible()
        if wait or not state['met']:
            return {'status': 'quorum', 'selected': selected, 'reason': (wait or {}).get('reason') or state['reason']}
    done = {}
    for row in SejmVideoSpin.objects.filter(status='queued').select_related('record', 'figure').order_by('day', '-rank_score')[:limit]:
        diagnose(row)
        done[row.status] = done.get(row.status, 0) + 1
        if row.status == 'queued':
            break  # bez kworum kolejne też by czekały
    return {'status': 'ok', 'selected': selected, 'diagnosed': done, 'usd_left_today': budget_left()}


def item(row):
    from news.przeszlosc_osoba import slug
    figure = row.figure
    return {'id': row.pk, 'day': row.day.isoformat(), 'place': row.place, 'place_label': row.get_place_display(),
            'person': {'id': figure.pk, 'name': figure.canonical_name, 'slug': slug(figure)} if figure else None,
            'title': row.record.title[:300], 'headline': row.headline, 'summary': row.summary, 'verdict': row.verdict,
            'intensity': row.intensity, 'techniques': [t.get('name', '') for t in row.techniques or []][:6],
            'video_url': row.video_url, 'timecode': timecode(row.offset_seconds), 'exact': row.offset_exact,
            'source_url': row.record.source_url, 'committee': (row.record.data or {}).get('committee', '')}


def published():
    from news.zrodla_models import SejmVideoSpin
    return (SejmVideoSpin.objects.filter(status='approved', hidden_at__isnull=True, withdrawn_at__isnull=True)
            .select_related('record', 'figure'))


from rest_framework.decorators import api_view, permission_classes  # noqa: E402
from rest_framework.permissions import AllowAny  # noqa: E402
from rest_framework.response import Response  # noqa: E402


@api_view(['GET'])
@permission_classes([AllowAny])
def sejm_video_view(request):
    """GET /api/clinic/sejm-wideo/?osoba=<id> - opublikowane diagnozy wystąpień z nagrań Sejmu."""
    rows = published()
    figure = request.query_params.get('osoba', '')
    if figure.isdigit():
        rows = rows.filter(figure_id=int(figure))
    return Response({'results': [item(r) for r in rows[:30]],
                     'source': {'label': 'Kancelaria Sejmu: zapisy wystąpień i transmisje', 'url': 'https://api.sejm.gov.pl/videos.html'}})
