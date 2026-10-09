"""Publiczny odczyt; oceny i komentarze wyłącznie z potwierdzonego konta."""
from datetime import timedelta
import unicodedata

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, Throttled
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from news.account_models import AccountIdentity, CommentReport
from news.account_security import AccountEnabled, require_verified
from news.accounts import AccountWriteThrottle, OpinionReadThrottle
from news.clinic_models import SpinOpinion
from news.clinic_discussion_models import ClinicComment, ClinicCommentReport, InterviewOpinion, DailyMessageOpinion, ClinicCommentAppeal
from news.clinic_moderation import body_hash, screen_comment, finish_screening, notify_moderators


def target(kind, target_id):
    if kind == 'spins':
        from news.clinic import published_diagnoses
        return 'diagnosis', get_object_or_404(published_diagnoses(), pk=target_id)
    if kind == 'daily-messages':
        from news.clinic import published_messages
        return 'daily_message', get_object_or_404(published_messages(), pk=target_id)
    from news.clinic_interview import _published_interviews
    return 'interview', get_object_or_404(_published_interviews(), pk=target_id)


def counts(rows):
    result = {'positive': 0, 'negative': 0}
    result.update({row['polarity']: row['n'] for row in rows.filter(polarity__isnull=False).values('polarity').annotate(n=Count('id'))})
    return result


def locked_identity(user):
    identity = AccountIdentity.objects.select_for_update().filter(user=user).first()
    if not identity or not identity.email_verified:
        raise PermissionDenied('Potwierdź e-mail, aby ocenić i komentować.')
    return identity


class DiscussionView(APIView):
    permission_classes = [AccountEnabled]

    def get_permissions(self):
        return [AccountEnabled()] + ([IsAuthenticated()] if self.request.method != 'GET' else [])

    def get_throttles(self):
        return [OpinionReadThrottle()] if self.request.method == 'GET' else [AccountWriteThrottle()]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response


class RatingInput(serializers.Serializer):
    polarity = serializers.ChoiceField(choices=['positive', 'negative'])

    def validate(self, attrs):
        if self.initial_data.get('body'):
            raise serializers.ValidationError('Komentarz dodaj osobno w sekcji Dyskusja. Odśwież stronę.')
        return attrs


class ClinicOpinionsView(DiscussionView):
    def get(self, request, kind, target_id):
        field, obj = target(kind, target_id)
        rows = obj.opinions.all()
        mine = rows.filter(user=request.user, polarity__isnull=False).first() if request.user.is_authenticated else None
        return Response({'counts': counts(rows), 'mine': {'polarity': mine.polarity} if mine else None})

    def post(self, request, kind, target_id):
        require_verified(request.user)
        field, obj = target(kind, target_id)
        data = RatingInput(data=request.data)
        data.is_valid(raise_exception=True)
        model = {'diagnosis': SpinOpinion, 'interview': InterviewOpinion, 'daily_message': DailyMessageOpinion}[field]
        with transaction.atomic():
            locked_identity(request.user)
            model.objects.update_or_create(user=request.user, **{field: obj}, defaults=data.validated_data)
        return self.get(request, kind, target_id)

    patch = post

    def delete(self, request, kind, target_id):
        require_verified(request.user)
        field, obj = target(kind, target_id)
        with transaction.atomic():
            locked_identity(request.user)
            rows = obj.opinions.filter(user=request.user)
            if field == 'diagnosis':
                rows.update(polarity=None)  # Zachowujemy stare komentarze i daty.
            else:
                rows.delete()
        return self.get(request, kind, target_id)


class CommentInput(serializers.Serializer):
    body = serializers.CharField(max_length=1000)
    parent = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate_body(self, value):
        value = unicodedata.normalize('NFC', value).strip()
        if not value or len(value) > 1000:
            raise serializers.ValidationError('Komentarz musi mieć od 1 do 1000 znaków.')
        return value


def comment_data(row, user):
    mine = user.is_authenticated and row.author_id == user.pk
    data = {'id': row.pk, 'author': {'id': row.author_id, 'username': row.author.username},
            'body': row.body if not row.hidden_at or mine else None,
            'hidden': bool(row.hidden_at), 'hidden_reason': row.hidden_reason if mine else '',
            'parent': row.parent_id, 'created_at': row.created_at,
            'reply_count': getattr(row, 'reply_count', 0)}
    if mine:
        appeal = getattr(row, 'appeal', None)
        data['appeal'] = {'status': appeal.status} if appeal else None
    return data


class ClinicCommentsView(DiscussionView):
    def get(self, request, kind, target_id):
        field, obj = target(kind, target_id)
        try:
            page = int(request.query_params.get('page', 1))
            parent_id = int(request.query_params['parent']) if 'parent' in request.query_params else None
            if page < 1 or (parent_id is not None and parent_id < 1):
                raise ValueError
        except (ValueError, TypeError):
            raise serializers.ValidationError('Nieprawidłowy numer strony lub komentarza.')
        rows = obj.comments.all()
        if parent_id:
            get_object_or_404(rows, pk=parent_id, parent__isnull=True)
        roots = rows.filter(parent_id=parent_id).select_related('author', 'appeal').annotate(reply_count=Count('replies')).order_by('-created_at', '-id')
        batch = list(roots[(page - 1) * 20:page * 20 + 1])
        return Response({'results': [comment_data(row, request.user) for row in batch[:20]],
                         'next_page': page + 1 if len(batch) > 20 else None,
                         'count': rows.count()})

    def post(self, request, kind, target_id):
        require_verified(request.user)
        field, obj = target(kind, target_id)
        data = CommentInput(data=request.data)
        data.is_valid(raise_exception=True)
        body = data.validated_data['body']
        parent_id = data.validated_data.get('parent')
        if parent_id:
            get_object_or_404(obj.comments, pk=parent_id, parent__isnull=True)
        # Jedna blokada konta serializuje limity również między różnymi dyskusjami.
        with transaction.atomic():
            identity = locked_identity(request.user)
            now = timezone.now()
            if identity.comments_blocked_until and identity.comments_blocked_until > now:
                raise PermissionDenied('Możliwość komentowania została czasowo zablokowana przez moderację.')
            rows = ClinicComment.objects.filter(author=request.user)
            if rows.filter(created_at__gt=now - timedelta(seconds=30)).exists():
                raise Throttled(wait=30, detail='Odczekaj 30 sekund między komentarzami.')
            if rows.filter(created_at__gte=now - timedelta(hours=1)).count() >= 10:
                raise Throttled(detail='Limit 10 komentarzy na godzinę.')
            if rows.filter(created_at__gte=now - timedelta(days=1)).count() >= 50:
                raise Throttled(detail='Limit 50 komentarzy na dobę.')
            digest = body_hash(body)
            if rows.filter(body_hash=digest).exists():
                raise serializers.ValidationError('Ten komentarz został już opublikowany.')
            row = ClinicComment.objects.create(author=request.user, **{field: obj}, body=body, body_hash=digest,
                parent_id=parent_id, hidden_at=now, hidden_reason='Komentarz czeka na sprawdzenie.')
        # Brak blokady konta w trakcie połączenia z modelem. Do wyniku treść jest ukryta.
        row = finish_screening(row.pk, screen_comment(body))
        return Response(comment_data(row, request.user), status=201)


class ReportInput(serializers.Serializer):
    reason = serializers.ChoiceField(choices=CommentReport.REASONS)
    details = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')


class ClinicCommentReportView(DiscussionView):
    def post(self, request, kind, target_id, comment_id):
        require_verified(request.user)
        field, obj = target(kind, target_id)
        data = ReportInput(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            locked_identity(request.user)
            row = get_object_or_404(obj.comments.select_for_update(), pk=comment_id)
            if row.author_id == request.user.pk:
                raise serializers.ValidationError('Nie możesz zgłosić własnego komentarza.')
            report, created = ClinicCommentReport.objects.get_or_create(comment=row, reporter=request.user,
                defaults=data.validated_data)
            if created:
                row.needs_review = True
                # Rozpatrzone zgłoszenia nie ukrywają ponownie przywróconego komentarza.
                if row.reports.filter(reviewed_at__isnull=True).count() >= 3:
                    row.hidden_at = row.hidden_at or timezone.now()
                    row.hidden_reason = 'Trzy niezależne zgłoszenia — oczekuje na decyzję moderatora.'
                    if row.screening == 'pending':
                        row.screening = 'unavailable'
                row.save(update_fields=['needs_review', 'hidden_at', 'hidden_reason', 'screening', 'updated_at'])
                transaction.on_commit(lambda: notify_moderators('report', report.pk))
        return Response({'reported': True}, status=201 if created else 200)


class AppealInput(serializers.Serializer):
    details = serializers.CharField(max_length=1000, required=False, allow_blank=True, default='')


class ClinicCommentAppealView(DiscussionView):
    def post(self, request, kind, target_id, comment_id):
        require_verified(request.user)
        field, obj = target(kind, target_id)
        data = AppealInput(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            locked_identity(request.user)
            row = get_object_or_404(obj.comments.select_for_update(), pk=comment_id, author=request.user)
            existing = getattr(row, 'appeal', None)
            if existing:
                return Response({'status': existing.status})
            if not row.hidden_at or row.screening == 'pending':
                raise serializers.ValidationError('Odwołanie dotyczy wyłącznie ukrytego komentarza.')
            appeal = ClinicCommentAppeal.objects.create(comment=row, author=request.user, **data.validated_data)
            row.needs_review = True
            row.save(update_fields=['needs_review', 'updated_at'])
            transaction.on_commit(lambda: notify_moderators('appeal', appeal.pk))
        return Response({'status': appeal.status}, status=201)
