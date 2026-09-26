"""API Kliniki spinu: strona /klinika, diagnozy, reakcje, sugestie kont X i kolejka zatwierdzania."""
import os
import re

from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from news import clinic
from news.accounts import AccountWriteThrottle, OpinionInput, OpinionReadThrottle
from news.clinic_models import ClinicDailyMessage, SpinDiagnosis, SpinOpinion, XAccountSuggestion
from news.political_models import PublicFigure
from news.public_figures import verified_x_account_record
from news.schema import json_view

X_PROFILE = re.compile(r'^https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})/?(?:[?#].*)?$')
RESERVED_PATHS = {'home', 'search', 'explore', 'i', 'intent', 'share', 'settings', 'messages', 'notifications', 'login', 'signup', 'tos', 'privacy'}


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
    size = 20
    batch = list(rows.order_by('-post__published_at', '-pk')[(page - 1) * size:page * size + 1])
    return Response({'results': clinic.cards(batch[:size]), 'next_page': page + 1 if len(batch) > size else None})


@extend_schema(summary='Pełna diagnoza spinu', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def clinic_spin_detail(request, diagnosis_id):
    diagnosis = get_object_or_404(clinic.published_diagnoses(), pk=diagnosis_id)
    return Response(clinic.detail_data(diagnosis))


@extend_schema(summary='Konta X, z których czyta Klinika', tags=['klinika'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def clinic_accounts(request):
    return Response({'results': clinic.accounts_data()})


class SpinOpinionSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = SpinOpinion
        fields = ['id', 'author', 'polarity', 'body', 'created_at']

    def get_author(self, opinion):
        return {'id': opinion.user_id, 'username': opinion.user.username}


@json_view('Reakcje i komentarze do diagnozy spinu (trafna / nietrafna)', tags=['klinika'])
class SpinOpinionsView(APIView):
    """Najpierw reakcja, komentarz opcjonalnie. Sam komentarz bez reakcji nie jest możliwy."""
    permission_classes = [AllowAny]
    throttle_classes = [OpinionReadThrottle, AccountWriteThrottle]

    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method in ('POST', 'PATCH') else super().get_permissions()

    def _diagnosis(self, diagnosis_id):
        return get_object_or_404(clinic.published_diagnoses(), pk=diagnosis_id)

    def get(self, request, diagnosis_id):
        rows = self._diagnosis(diagnosis_id).opinions.select_related('user')
        counts = {'positive': 0, 'negative': 0}
        counts.update({row['polarity']: row['n'] for row in rows.values('polarity').annotate(n=Count('id'))})
        mine = rows.filter(user=request.user).first() if request.user.is_authenticated else None
        return Response({
            'counts': counts,
            'mine': SpinOpinionSerializer(mine).data if mine else None,
            'positive': SpinOpinionSerializer(rows.filter(polarity='positive').exclude(body='')[:50], many=True).data,
            'negative': SpinOpinionSerializer(rows.filter(polarity='negative').exclude(body='')[:50], many=True).data,
        })

    def post(self, request, diagnosis_id):
        diagnosis = self._diagnosis(diagnosis_id)
        serializer = OpinionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                opinion = SpinOpinion.objects.create(user=request.user, diagnosis=diagnosis, **serializer.validated_data)
        except IntegrityError:
            return Response({'detail': 'Twoja reakcja na tę diagnozę jest już zapisana.'}, status=409)
        return Response(SpinOpinionSerializer(opinion).data, status=201)

    def patch(self, request, diagnosis_id):
        if not isinstance(request.data, dict) or set(request.data) - {'body'}:
            raise serializers.ValidationError('Możesz jedynie dopisać komentarz; reakcja pozostaje bez zmian.')
        serializer = OpinionInput(data={'polarity': 'positive', **request.data})
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data['body']
        if not body:
            raise serializers.ValidationError({'body': 'Podaj treść komentarza.'})
        self._diagnosis(diagnosis_id)
        with transaction.atomic():
            opinion = get_object_or_404(SpinOpinion.objects.select_for_update().select_related('user'),
                                        diagnosis_id=diagnosis_id, user=request.user)
            if opinion.body or not SpinOpinion.objects.filter(pk=opinion.pk, body='').update(body=body):
                return Response({'detail': 'Komentarz został już zapisany i nie można go zastąpić.'}, status=409)
            opinion.body = body
        return Response(SpinOpinionSerializer(opinion).data)


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
