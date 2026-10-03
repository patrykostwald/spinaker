"""Whole-thread ratings and flat comments. All mutations are account-gated."""
import re
import unicodedata
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, Throttled
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from news.account_models import AccountIdentity
from news.account_security import require_verified
from news.community import public_threads, _counts
from news.community_models import CommunityThreadOpinion, CommunityThreadReport
from news.features import accounts_enabled, threads_enabled
from news.thread_social_models import ThreadComment, ThreadRateEvent, ThreadModerationReport


def locked_account(user, kind=None):
    identity = AccountIdentity.objects.select_for_update().get(user=user)
    if not identity.email_verified:
        raise PermissionDenied('Potwierdź e-mail, aby publikować.')
    if kind == 'comment' and identity.comments_blocked_until and identity.comments_blocked_until > timezone.now():
        raise PermissionDenied('Komentowanie jest czasowo zablokowane przez zespół.')
    if kind:
        limit = 20 if kind == 'comment' else 50
        if ThreadRateEvent.objects.filter(user=user, kind=kind, created_at__gt=timezone.now() - timedelta(hours=1)).count() >= limit:
            raise Throttled(wait=3600, detail=f'Limit {limit} zapisów na godzinę.')
        ThreadRateEvent.objects.create(user=user, kind=kind)


class SocialView(APIView):
    def get_permissions(self):
        return [] if self.request.method == 'GET' else [IsAuthenticated()]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not threads_enabled() or (request.method != 'GET' and not accounts_enabled()):
            raise Http404
        if request.method not in ('GET', 'DELETE'):
            require_verified(request.user)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response


class RatingInput(serializers.Serializer):
    polarity = serializers.ChoiceField(choices=['positive', 'doubt', 'negative'])


class ThreadRatingsView(SocialView):
    def get(self, request, thread_id):
        thread = get_object_or_404(public_threads(), pk=thread_id)
        mine = thread.opinions.filter(user=request.user).first() if request.user.is_authenticated else None
        counts = _counts([thread_id])[thread_id]
        total = sum(counts.values())
        return Response({'counts': counts, 'mine': {'polarity': mine.polarity} if mine else None,
                         'total': total, 'highlight': total >= 3,
                         'distribution': {key: value / total if total else 0 for key, value in counts.items()}})

    def post(self, request, thread_id):
        thread = get_object_or_404(public_threads(), pk=thread_id)
        data = RatingInput(data=request.data)
        data.is_valid(raise_exception=True)
        if set(request.data) != {'polarity'}:
            raise serializers.ValidationError('Komentarz dodaj osobno pod nitką.')
        with transaction.atomic():
            locked_account(request.user, 'rating')
            CommunityThreadOpinion.objects.update_or_create(user=request.user, thread=thread, defaults=data.validated_data)
        return self.get(request, thread_id)

    patch = post


class CommentInput(serializers.Serializer):
    body = serializers.CharField(max_length=600)

    def validate_body(self, body):
        body = unicodedata.normalize('NFC', body).strip()
        if not body or len(body) > 600:
            raise serializers.ValidationError('Komentarz musi mieć od 1 do 600 znaków.')
        return body


def comment_data(row, user):
    mine = user.is_authenticated and row.author_id == user.pk
    return {'id': row.pk, 'body': row.body, 'author': row.author.username if row.author_id else 'Usunięte konto',
            'created_at': row.created_at, 'edited_at': row.edited_at, 'is_owner': mine,
            'hidden': bool(row.hidden_at),
            'can_edit': mine and not row.hidden_at and timezone.now() < row.created_at + timedelta(minutes=5),
            'box_references': [int(n) for n in re.findall(r'@boks\s+(\d{1,3})\b', row.body, re.I)]}


class ThreadCommentsView(SocialView):
    def get(self, request, thread_id):
        get_object_or_404(public_threads(), pk=thread_id)
        try:
            after = int(request.query_params.get('after', 0))
            if after < 0:
                raise ValueError
        except ValueError:
            raise serializers.ValidationError('Nieprawidłowy kursor komentarzy.')
        rows = ThreadComment.objects.filter(thread_id=thread_id, deleted_at__isnull=True)
        visible = Q(hidden_at__isnull=True)
        if request.user.is_authenticated:
            visible |= Q(author=request.user)
        rows = rows.filter(visible)
        # An ID cursor stays stable when earlier comments are removed.
        batch = list(rows.filter(pk__gt=after).select_related('author').order_by('pk')[:21])
        return Response({'results': [comment_data(row, request.user) for row in batch[:20]],
                         'next_cursor': batch[19].pk if len(batch) > 20 else None, 'count': rows.filter(hidden_at__isnull=True).count()})

    def post(self, request, thread_id):
        thread = get_object_or_404(public_threads(), pk=thread_id)
        data = CommentInput(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            locked_account(request.user, 'comment')
            row = ThreadComment.objects.create(thread=thread, author=request.user, **data.validated_data)
        return Response(comment_data(row, request.user), status=201)


class ThreadCommentDetailView(SocialView):
    def patch(self, request, thread_id, comment_id):
        get_object_or_404(public_threads(), pk=thread_id)
        data = CommentInput(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            locked_account(request.user, 'comment')
            row = get_object_or_404(ThreadComment.objects.select_for_update(), pk=comment_id,
                thread_id=thread_id, author=request.user, deleted_at__isnull=True)
            if timezone.now() >= row.created_at + timedelta(minutes=5):
                raise PermissionDenied('Komentarz można edytować przez 5 minut od publikacji.')
            if row.hidden_at:
                raise PermissionDenied('Ukryty komentarz czeka na decyzję zespołu.')
            row.body, row.edited_at = data.validated_data['body'], timezone.now()
            row.save(update_fields=['body', 'edited_at'])
        return Response(comment_data(row, request.user))

    def delete(self, request, thread_id, comment_id):
        # Owners may delete even when the parent thread is hidden or unpublished.
        row = get_object_or_404(ThreadComment, pk=comment_id, thread_id=thread_id, author=request.user)
        row.body, row.deleted_at = '', timezone.now()
        row.save(update_fields=['body', 'deleted_at'])
        return Response(status=204)


class ReportInput(serializers.Serializer):
    reason = serializers.ChoiceField(choices=CommunityThreadReport.REASONS)
    details = serializers.CharField(max_length=1000, required=False, allow_blank=True, default='')


class ThreadReportView(SocialView):
    def post(self, request, thread_id, comment_id=None):
        from news.thread_moderation import assess_report, target_snapshot
        thread = get_object_or_404(public_threads(), pk=thread_id)
        comment = get_object_or_404(ThreadComment, pk=comment_id, thread=thread,
            hidden_at__isnull=True, deleted_at__isnull=True) if comment_id else None
        data = ReportInput(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            locked_account(request.user)
            existing = ThreadModerationReport.objects.filter(thread=thread, comment=comment, reporter=request.user).first()
            if existing:
                return Response({'status': 'already_reported', 'id': existing.pk})
            if ThreadModerationReport.objects.filter(reporter=request.user, created_at__gt=timezone.now()-timedelta(hours=1)).count() >= 20:
                raise Throttled(wait=3600)
            snapshot = target_snapshot(thread, comment)
            report = ThreadModerationReport.objects.create(thread=thread, comment=comment, reporter=request.user,
                target_author_id=comment.author_id if comment else thread.owner_id,
                target_kind='comment' if comment else 'thread',
                snapshot=snapshot, **data.validated_data)
        assess_report(report.pk)
        return Response({'status': 'received', 'id': report.pk}, status=201)


class ThreadAppealView(SocialView):
    def get(self, request, report_id):
        if not request.user.is_authenticated:
            raise PermissionDenied('Zaloguj się, aby odczytać decyzję.')
        report = get_object_or_404(ThreadModerationReport.objects.select_related('thread', 'comment'), pk=report_id)
        author_id = report.target_author_id
        if request.user.pk not in (author_id, report.reporter_id):
            raise PermissionDenied()
        return Response({'id': report.pk, 'status': report.status, 'appealed': bool(report.appealed_at),
            'decisions': list(report.decisions.values('action', 'rule', 'explanation', 'is_appeal', 'created_at'))})

    def post(self, request, report_id):
        if not isinstance(request.data, dict):
            raise serializers.ValidationError('Nieprawidłowy formularz odwołania.')
        body = serializers.CharField(max_length=2000).run_validation(request.data.get('body'))
        with transaction.atomic():
            report = get_object_or_404(ThreadModerationReport.objects.select_for_update(of=('self',)).select_related('thread', 'comment'), pk=report_id)
            author_id = report.target_author_id
            if request.user.pk not in (author_id, report.reporter_id):
                raise PermissionDenied()
            if report.status != 'resolved' or report.appealed_at:
                raise serializers.ValidationError('Od decyzji można odwołać się jeden raz.')
            report.appeal, report.appealed_at, report.appealed_by, report.status = body, timezone.now(), request.user, 'appeal'
            report.save(update_fields=['appeal', 'appealed_at', 'appealed_by', 'status'])
        return Response({'status': 'appeal'})


class ThreadModerationQueueView(APIView):
    permission_classes = [IsAdminUser]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.has_perm('news.change_threadmoderationreport'):
            raise PermissionDenied()

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response

    def get(self, request):
        from news.thread_moderation import RULES
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            raise serializers.ValidationError('Nieprawidłowa strona.')
        rows = ThreadModerationReport.objects.filter(status__in=['new', 'appeal']).select_related('thread').prefetch_related('decisions')
        batch = list(rows[(page-1)*20:page*20+1])
        return Response({'rules': RULES, 'next_page': page+1 if len(batch)>20 else None, 'results': [
            {'id': row.pk, 'thread_id': row.thread_id, 'target_kind': row.target_kind,
             'reason': row.reason, 'details': row.details, 'snapshot': row.snapshot,
             'status': row.status, 'ai': row.ai_assessment, 'appeal': row.appeal,
             'decisions': [{'action': d.action, 'rule': d.rule, 'explanation': d.explanation} for d in row.decisions.all()]}
            for row in batch[:20]]})

    def post(self, request):
        from news.thread_moderation import decide, RULES
        if not isinstance(request.data, dict):
            raise serializers.ValidationError('Nieprawidłowy formularz decyzji.')
        report_id = serializers.IntegerField(min_value=1).run_validation(request.data.get('report_id'))
        action = serializers.ChoiceField(choices=['hide', 'restore']).run_validation(request.data.get('action'))
        rule = serializers.ChoiceField(choices=list(RULES)).run_validation(request.data.get('rule'))
        explanation = serializers.CharField(max_length=2000).run_validation(request.data.get('explanation'))
        get_object_or_404(ThreadModerationReport, pk=report_id)
        decision = decide(report_id, request.user, action, rule, explanation)
        return Response({'id': decision.pk, 'status': 'resolved'})
