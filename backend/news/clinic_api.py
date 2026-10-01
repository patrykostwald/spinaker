"""API Kliniki spinu: strona /klinika, diagnozy, reakcje, sugestie kont X i kolejka zatwierdzania."""
import os
import re
from datetime import date, datetime, time, timedelta

from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from news import clinic
from news.clinic_models import ClinicDailyMessage, SpinDiagnosis, XAccountSuggestion
from news.political_models import PublicFigure
from news.public_figures import verified_x_account_record
from news.schema import json_view
from news.techniques import CANONICAL_TECHNIQUES, normalized, technique_groups

X_PROFILE = re.compile(r'^https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})/?(?:[?#].*)?$')
RESERVED_PATHS = {'home', 'search', 'explore', 'i', 'intent', 'share', 'settings', 'messages', 'notifications', 'login', 'signup', 'tos', 'privacy'}


@extend_schema(summary='Skład Konsylium i przyjęcie Karty', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([AllowAny])
def clinic_council(request):
    from news.council_charter import council_data
    return Response(council_data())


@extend_schema(summary='Archiwum opublikowanych wywiadów', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([AllowAny])
def clinic_interviews(request):
    from news.clinic_interview import _published_interviews, interview_data
    try:
        page = max(1, int(request.query_params.get('page', '1')))
    except ValueError:
        return Response({'detail': 'Nieprawidłowy numer strony.'}, status=400)
    rows = _published_interviews().order_by('-day', '-diagnosed_at', '-pk')
    channels = list(rows.exclude(channel='').order_by('channel').values_list('channel', flat=True).distinct())
    channel, query = (request.query_params.get(key, '').strip() for key in ('channel', 'q'))
    if channel:
        rows = rows.filter(channel=channel)
    if query:
        rows = rows.filter(Q(guest_name__icontains=query) | Q(host_name__icontains=query) | Q(title__icontains=query))
    count = rows.count()
    batch = list(rows[(page - 1) * 20:page * 20 + 1])
    return Response({'results': [interview_data(row) for row in batch[:20]],
                     'next_page': page + 1 if len(batch) > 20 else None, 'count': count, 'channels': channels})


@extend_schema(summary='Pełna analiza opublikowanego wywiadu', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([AllowAny])
def clinic_interview_detail(request, interview_id):
    from news.clinic_interview import _published_interviews, interview_data
    return Response(interview_data(get_object_or_404(_published_interviews(), pk=interview_id)))


@extend_schema(summary='Przekazy obu stron według dni', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([AllowAny])
def clinic_messages(request):
    try:
        page = max(1, int(request.query_params.get('page', '1')))
    except ValueError:
        return Response({'detail': 'Nieprawidłowy numer strony.'}, status=400)
    rows = ClinicDailyMessage.objects.filter(status='approved', camp__in=clinic.CAMPS)
    days = rows.order_by('-day').values_list('day', flat=True).distinct()
    count = days.count()
    batch = list(days[(page - 1) * 14:page * 14 + 1])
    grouped = {day: {'day': day, 'government': None, 'opposition': None} for day in batch[:14]}
    for row in rows.filter(day__in=batch[:14]).prefetch_related('posts'):
        grouped[row.day][row.camp] = clinic._message_data(row)
    return Response({'results': list(grouped.values()), 'next_page': page + 1 if len(batch) > 14 else None,
                     'count': count})


@extend_schema(summary='Przekazy konkretnego dnia: obie strony, zakres i źródła', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([AllowAny])
def clinic_message_detail(request, day):
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
            raise ValueError
        selected_day = date.fromisoformat(day)
    except ValueError:
        raise Http404
    rows = list(ClinicDailyMessage.objects.filter(day=selected_day, status='approved', camp__in=clinic.CAMPS))
    if not rows:
        raise Http404
    result = {'day': selected_day, 'government': None, 'opposition': None}
    for row in rows:
        result[row.camp] = clinic._message_data(row, with_posts=True, all_posts=True)
    return Response(result)


@extend_schema(summary='Klinika spinu: waga, przekazy dnia, spin dnia i diagnozy obu stron', tags=['klinika'],
               responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def clinic_page(request):
    try:
        window = min(30, max(1, int(request.query_params.get('window', '7'))))
    except ValueError:
        return Response({'detail': 'Parametr window musi być liczbą dni (1–30).'}, status=400)
    return Response(clinic.clinic_page_data(window))


@extend_schema(summary='Lista zatwierdzonych diagnoz jednej strony', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def clinic_spins(request):
    camp = request.query_params.get('camp', '')
    try:
        page = max(1, int(request.query_params.get('page', '1')))
    except ValueError:
        return Response({'detail': 'Nieprawidłowy numer strony.'}, status=400)
    rows = clinic.published_diagnoses()
    if camp in clinic.CAMPS:
        rows = rows.filter(post__camp_at_collection=camp)
    verdict = request.query_params.get('verdict', '')
    if verdict in clinic.VERDICT_LABELS:
        rows = rows.filter(verdict=verdict)
    params = request.query_params
    account = params.get('account', '')
    if account:
        if not re.fullmatch(r'[0-9]{1,19}', account) or not 0 < int(account) <= 9223372036854775807:
            return Response({'detail': 'Nieprawidłowy identyfikator konta.'}, status=400)
        rows = rows.filter(post__account_id=int(account))
    try:
        minimum = int(params.get('intensity_min', '0'))
        maximum = int(params.get('intensity_max', '100'))
        if not 0 <= minimum <= maximum <= 100:
            raise ValueError
        dates = {key: date.fromisoformat(params[key]) for key in ('date_from', 'date_to') if params.get(key)}
        if len(dates) == 2 and dates['date_from'] > dates['date_to']:
            raise ValueError
        for key, day in dates.items():
            boundary = timezone.make_aware(datetime.combine(day, time.min))
            rows = rows.filter(**({'post__published_at__gte': boundary} if key == 'date_from'
                                  else {'post__published_at__lt': boundary + timedelta(days=1)}))
    except (ValueError, OverflowError):
        return Response({'detail': 'Nieprawidłowy zakres siły (0–100) lub dat (RRRR-MM-DD).'}, status=400)
    sort = params.get('sort', 'new')
    technique = params.get('technique', '')
    if sort not in ('new', 'strong') or (technique and technique not in CANONICAL_TECHNIQUES):
        return Response({'detail': 'Nieprawidłowe sortowanie lub kanoniczna technika.'}, status=400)
    if 'intensity_min' in params or 'intensity_max' in params:
        rows = rows.filter(intensity__gte=minimum, intensity__lte=maximum)
    rows = rows.order_by(*(['-intensity'] if sort == 'strong' else []), '-post__published_at', '-pk')
    query, party = normalized(params.get('q', '')), normalized(params.get('party', ''))
    if query or party or technique:
        candidates = list(rows)
        figures = clinic.figures_by_account({row.post.account_id for row in candidates}) if query or party else {}
        matched = []
        for row in candidates:
            author = clinic.author_data(row.post, figures.get(row.post.account_id)) if query or party else {}
            if query and not any(query in normalized(value) for value in (
                row.headline, row.summary, author['name'], author['handle'], row.post.account.display_name)):
                continue
            affiliation = author.get('party')
            if party and party not in ({normalized(value) for value in affiliation.values()} if affiliation else {'unknown'}):
                continue
            if technique and technique not in technique_groups(row.techniques):
                continue
            matched.append(row)
        rows = matched
    try:
        size = int(params.get('page_size', '20'))
        if not 1 <= size <= 20:
            raise ValueError
    except ValueError:
        return Response({'detail': 'Liczba wyników musi wynosić od 1 do 20.'}, status=400)
    count = len(rows) if isinstance(rows, list) else rows.count()
    batch = list(rows[(page - 1) * size:page * size + 1])
    return Response({'results': clinic.cards(batch[:size]), 'next_page': page + 1 if len(batch) > size else None,
                     'count': count})


@extend_schema(summary='Statystyki Kliniki z liczebnością próby', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([AllowAny])
def clinic_statistics(request):
    from news.clinic_stats import stats_data
    return Response(stats_data())


@extend_schema(summary='Pełna diagnoza spinu', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def clinic_spin_detail(request, diagnosis_id):
    diagnosis = get_object_or_404(clinic.published_diagnoses(), pk=diagnosis_id)
    return Response(clinic.detail_data(diagnosis))


class CardContentNegotiation(DefaultContentNegotiation):
    def filter_renderers(self, renderers, format):
        # W tym endpointcie parametr format wybiera układ PNG, nie renderer DRF.
        return renderers


class ClinicSpinCardView(APIView):
    permission_classes = [AllowAny]
    content_negotiation_class = CardContentNegotiation

    def get(self, request, diagnosis_id):
        from django.http import FileResponse
        from news.clinic_card import FORMATS, cached_card
        card_format = request.query_params.get('format', 'diagnoza')
        if card_format not in FORMATS:
            return Response({'detail': 'Nieznany format obrazu.'}, status=400)
        diagnosis = get_object_or_404(clinic.published_diagnoses(), pk=diagnosis_id)
        figures = clinic.figures_by_account([diagnosis.post.account_id])
        path = cached_card(clinic.card_data(diagnosis, figures), card_format)
        response = FileResponse(path.open('rb'), content_type='image/png')
        response['Cache-Control'] = 'public, max-age=3600'
        return response


clinic_spin_card = ClinicSpinCardView.as_view()


@extend_schema(summary='Konta X, z których czyta Klinika', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def clinic_accounts(request):
    return Response({'results': clinic.accounts_data()})


@extend_schema(summary='Raport tygodnia Dr. Spina (najnowszy albo z tygodnia kończącego się w danym dniu)', tags=['klinika'],
               responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def clinic_report(request, week_end=None):
    from news.clinic_models import WeeklyReport
    from news.weekly_report import report_data
    from datetime import date
    from django.http import Http404
    rows = WeeklyReport.objects.all()
    if week_end:
        try:
            week_end = date.fromisoformat(week_end)
        except ValueError:
            raise Http404
    report = get_object_or_404(rows, week_end=week_end) if week_end else rows.first()
    if report is None:
        return Response({'report': None, 'archive': []})
    archive = list(rows.values('week_start', 'week_end'))
    return Response({'report': report_data(report), 'archive': archive})


@extend_schema(summary='Usunięte posty polityków (bez treści)', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def clinic_deleted(request):
    from news.deleted_posts import deleted_data
    return Response(deleted_data())


class SuggestionThrottle(AnonRateThrottle):
    scope = 'x_suggestion'
    rate = '10/hour'


class SuggestionInput(serializers.Serializer):
    url = serializers.CharField(max_length=300)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default='')

    def validate_url(self, value):
        match = X_PROFILE.match(value.strip())
        if not match or match.group(1).lower() in RESERVED_PATHS:
            raise serializers.ValidationError('Podaj link do profilu na X, np. https://x.com/nazwa_konta.')
        return value.strip()


@extend_schema(summary='Zasugeruj konto X osoby publicznej (weryfikuje zespół)', tags=['osoby publiczne'],
               request=SuggestionInput, responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([SuggestionThrottle])
def suggest_x_account(request, figure_id):
    figure = get_object_or_404(PublicFigure, pk=figure_id, archived=False)
    if verified_x_account_record(figure):
        return Response({'detail': 'Ta osoba ma już potwierdzone konto X.'}, status=409)
    serializer = SuggestionInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    url = serializer.validated_data['url']
    handle = X_PROFILE.match(url).group(1)
    suggestion, created = XAccountSuggestion.objects.get_or_create(
        public_figure=figure, handle=handle,
        defaults={'url': f'https://x.com/{handle}', 'note': serializer.validated_data['note'],
                  'submitted_by': request.user if request.user.is_authenticated else None})
    return Response({'status': 'received' if created else 'already_suggested', 'handle': suggestion.handle},
                    status=201 if created else 200)


# --- kolejka zatwierdzania (tylko zespół) -----------------------------------------------------

def _queue_diagnosis(diagnosis):
    data = clinic.detail_data(diagnosis)
    data.update({'status': diagnosis.status, 'triage': diagnosis.triage, 'usage': diagnosis.usage})
    return data


@extend_schema(summary='Kolejka Kliniki: diagnozy i przekazy dnia czekające na decyzję', tags=['klinika'],
               responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def clinic_queue(request):
    diagnoses = (SpinDiagnosis.objects.filter(status='pending_review').select_related('post__account')
                 .order_by('post__published_at'))[:50]
    messages = ClinicDailyMessage.objects.filter(status='pending_review').order_by('day', 'camp')[:10]
    failed = SpinDiagnosis.objects.filter(status='failed').values('error').annotate(n=Count('id'))
    flagged = (SpinDiagnosis.objects.filter(status='flagged').select_related('post__account')
               .order_by('-screen_score', '-post__published_at'))[:50]
    flagged_figures = clinic.figures_by_account({row.post.account_id for row in flagged})
    return Response({
        'flagged': [{'id': row.pk, 'score': row.screen_score, 'reason': (row.triage or {}).get('reason', ''),
                     'screened_by': (row.triage or {}).get('provider', ''), 'camp_label': clinic.CAMP_LABELS.get(row.post.camp_at_collection, ''),
                     'author': clinic.author_data(row.post, flagged_figures.get(row.post.account_id)),
                     'post': {'url': row.post.url, 'text': row.post.text, 'published_at': row.post.published_at}}
                    for row in flagged],
        'diagnoses': [_queue_diagnosis(row) for row in diagnoses],
        'recent': clinic.cards(clinic.published_diagnoses().order_by('-diagnosed_at', '-pk')[:20]),
        'messages': [{'id': row.pk, 'day': row.day, 'camp': row.camp, 'camp_label': clinic.CAMP_LABELS[row.camp],
                      'message': row.message, 'themes': row.themes, 'posts_count': row.posts.count(),
                      'model': row.model_name} for row in messages],
        'counts': {
            'pending': SpinDiagnosis.objects.filter(status='pending_review').count(),
            'flagged': SpinDiagnosis.objects.filter(status='flagged').count(),
            'queued': SpinDiagnosis.objects.filter(status='queued').count(),
            'diagnosed_today': clinic.diagnoses_today(),
            'daily_limit': int(os.environ.get('CLINIC_DAILY_LIMIT', '20')),
            'approved': SpinDiagnosis.objects.filter(status='approved').count(),
            'rejected': SpinDiagnosis.objects.filter(status='rejected').count(),
            'not_applicable': SpinDiagnosis.objects.filter(status='not_applicable').count(),
            'failed': {row['error']: row['n'] for row in failed},
            'suggestions': XAccountSuggestion.objects.filter(status='new').count(),
        },
    })


class ReviewInput(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['approve', 'reject'])


def _review(request, obj):
    serializer = ReviewInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        clinic.review(obj, request.user, serializer.validated_data['decision'])
    except ValueError:
        return Response({'detail': 'Ta pozycja ma już decyzję.'}, status=409)
    return Response({'id': obj.pk, 'status': obj.status})


@extend_schema(summary='Zatwierdź albo odrzuć diagnozę (bez edycji treści)', tags=['klinika'], request=ReviewInput,
               responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def review_diagnosis(request, diagnosis_id):
    return _review(request, get_object_or_404(SpinDiagnosis, pk=diagnosis_id))


@extend_schema(summary='Zatwierdź albo odrzuć przekaz dnia (bez edycji treści)', tags=['klinika'], request=ReviewInput,
               responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def review_message(request, message_id):
    return _review(request, get_object_or_404(ClinicDailyMessage, pk=message_id))


class HideInput(serializers.Serializer):
    reason = serializers.CharField(max_length=240)


@extend_schema(summary='Ukryj opublikowaną diagnozę po zgłoszeniu prawnym (treść zostaje bez zmian)', tags=['klinika'],
               request=HideInput, responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def hide_diagnosis(request, diagnosis_id):
    diagnosis = get_object_or_404(SpinDiagnosis, pk=diagnosis_id, status='approved')
    serializer = HideInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    diagnosis.hidden_at, diagnosis.hidden_reason = timezone.now(), serializer.validated_data['reason']
    diagnosis.save(update_fields=['hidden_at', 'hidden_reason'])
    return Response({'id': diagnosis.pk, 'hidden_at': diagnosis.hidden_at})


class FlagInput(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['investigate', 'dismiss'])


@extend_schema(summary='Post oznaczony przez strażnika: zbadaj (płatna diagnoza) albo pomiń', tags=['klinika'],
               request=FlagInput, responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def decide_flag(request, diagnosis_id):
    row = get_object_or_404(SpinDiagnosis, pk=diagnosis_id)
    serializer = FlagInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        if serializer.validated_data['decision'] == 'investigate':
            clinic.queue_for_diagnosis(row)
            from news.tasks import clinic_diagnose_task
            try:
                clinic_diagnose_task.delay()
            except Exception:
                pass  # bez brokera diagnoza ruszy przy najbliższym cyklu harmonogramu
        else:
            clinic.dismiss_flag(row)
    except ValueError:
        return Response({'detail': 'Ten post ma już decyzję.'}, status=409)
    return Response({'id': row.pk, 'status': row.status})



@extend_schema(summary='Zespół: dodaj wywiad dnia (link do publicznego filmu z YouTube)', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def staff_interviews(request):
    from datetime import date
    from news import clinic_interview
    from news.clinic_models import ClinicInterview
    if request.method == 'POST':
        day = None
        if request.data.get('day'):
            try:
                day = date.fromisoformat(str(request.data['day']))
            except ValueError:
                return Response({'detail': 'Data w formacie RRRR-MM-DD.'}, status=400)
        try:
            interview = clinic_interview.queue_interview(str(request.data.get('url', '')), day, request.user)
        except ValueError:
            return Response({'detail': 'To nie jest link do filmu na YouTube.'}, status=400)
        return Response({'id': interview.pk, 'status': interview.status}, status=201)
    rows = ClinicInterview.objects.order_by('-created_at')[:20]
    return Response({'enabled': clinic_interview.enabled(), 'results': [
        {'id': row.pk, 'day': row.day, 'url': row.url, 'title': row.title, 'status': row.status, 'error': row.error}
        for row in rows]})
