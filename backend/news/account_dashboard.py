"""Owner dashboard and public profiles. No remote services on reads."""
import re
from datetime import timedelta
from django.contrib.auth import get_user_model, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError as PasswordError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from news.account_models import MutedUser, ProfilePreference, PersonalContextThread
from news.account_security import AccountEnabled, require_verified
from news.accounts import AccountWriteThrottle, AccountIPThrottle
from news.community import public_threads, thread_summary, _counts
from news.community_models import CommunityThreadOpinion
from news.interview_vote_models import InterviewVote
from news.thread_social_models import ThreadComment, ThreadModerationReport


def muted_ids(user):
    return MutedUser.objects.filter(user=user).values('target_id') if user and user.is_authenticated else []


def profile_data(user, private=False):
    preference = ProfilePreference.objects.filter(user=user).first()
    visible = bool(preference and preference.public_activity)
    threads = PersonalContextThread.objects.filter(owner=user) if private else public_threads().filter(owner=user)
    comments = ThreadComment.objects.filter(author=user, deleted_at__isnull=True)
    ratings = CommunityThreadOpinion.objects.filter(user=user)
    if not private:
        comments = comments.filter(hidden_at__isnull=True, thread__in=public_threads())
        ratings = ratings.filter(thread__in=public_threads())
    result = {'id': user.pk, 'username': user.username, 'bio': preference.bio if preference else '',
        'date_joined': user.date_joined, 'public_activity': visible,
        'counts': {'threads': threads.count(), 'ratings': ratings.count(), 'comments': comments.count()}}
    if private:
        result.update(theme_preference=preference.theme_preference if preference else 'auto',
            nick_color=preference.nick_color if preference else '', nick_colors=ProfilePreference.NICK_COLORS,
            can_color_nick=hasattr(user, 'x_connection'),
            nick_change_available_at=preference.nick_changed_at + timedelta(days=30) if preference and preference.nick_changed_at else None)
    return result


def page(request, rows):
    number = serializers.IntegerField(min_value=1, max_value=10000).run_validation(request.query_params.get('page', 1))
    batch = list(rows[(number-1)*20:number*20+1])
    return batch[:20], number+1 if len(batch) > 20 else None


def activity(user, public=False, viewer=None):
    comments = ThreadComment.objects.filter(author=user, deleted_at__isnull=True).select_related('thread')
    ratings = CommunityThreadOpinion.objects.filter(user=user).select_related('thread')
    if public:
        comments = comments.filter(hidden_at__isnull=True, thread__in=public_threads(viewer))
    rows = []
    for row in comments:
        refs = [int(n) for n in re.findall(r'@(?:boks\s*|b)(\d{1,3})\b', row.body, re.I)]
        rows.append({'id': f'comment-{row.pk}', 'kind': 'comments', 'created_at': row.created_at,
            'body': row.body, 'title': row.thread.title, 'url': f'/spinki/{row.thread_id}#comment-{row.pk}',
            'thread_id': row.thread_id, 'box_references': refs, 'hidden': bool(row.hidden_at)})
    if not public:
        for row in ratings:
            rows.append({'id': f'rating-{row.pk}', 'kind': 'ratings', 'created_at': row.created_at,
                'polarity': row.polarity, 'title': row.thread.title, 'url': f'/spinki/{row.thread_id}'})
        from news.clinic_models import ClinicInterview
        winners = {row.day: row for row in ClinicInterview.objects.filter(
            day__in=InterviewVote.objects.filter(user=user).values('ballot__day'),
            selection_method__in=['votes', 'tie', 'views']).order_by('created_at', 'pk')}
        for row in InterviewVote.objects.filter(user=user).select_related('candidate', 'ballot'):
            selected = winners.get(row.ballot.day)
            rows.append({'id': f'vote-{row.pk}', 'kind': 'votes', 'created_at': row.updated_at,
                'title': row.candidate.title, 'day': row.ballot.day,
                'won': selected.video_id == row.candidate.video_id if selected else None,
                'url': f'/klinika/wywiady/glosowanie?day={row.ballot.day}'})
    return sorted(rows, key=lambda row: (row['created_at'], row['id']), reverse=True)


class DashboardView(APIView):
    permission_classes = [AccountEnabled, IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not isinstance(request.data, dict):
            raise serializers.ValidationError('Nieprawidłowy formularz.')

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response


class ActivityView(DashboardView):
    def get(self, request):
        kind = serializers.ChoiceField(choices=['all', 'ratings', 'comments', 'votes']).run_validation(request.query_params.get('kind', 'all'))
        rows = activity(request.user)
        batch, next_page = page(request, [row for row in rows if kind == 'all' or row['kind'] == kind])
        return Response({'results': batch, 'next_page': next_page})


class PublicProfileView(DashboardView):
    permission_classes = [AccountEnabled, AllowAny]

    def get(self, request, username):
        user = get_object_or_404(get_user_model(), username__iexact=username, is_active=True)
        if ProfilePreference.objects.filter(user=user, hidden_at__isnull=False).exists():
            from django.http import Http404
            raise Http404
        data = profile_data(user)
        from news.features import threads_enabled
        muted = MutedUser.objects.filter(user=request.user, target=user).exists() if request.user.is_authenticated else False
        rows = public_threads(request.user).filter(owner=user).select_related('owner').prefetch_related('items__article__source', 'items__link')
        if not threads_enabled():
            rows = rows.none()
            data['counts'] = {'threads': 0, 'ratings': 0, 'comments': 0}
        batch, next_page = page(request, rows.order_by('-published_at', '-pk'))
        comments, next_comments = page(request, activity(user, public=True, viewer=request.user) if threads_enabled() and data['public_activity'] and not muted else [])
        data.update(muted=muted, threads={'results': [thread_summary(row, _counts([row.pk])) for row in batch], 'next_page': next_page},
            comments={'results': comments, 'next_page': next_comments})
        return Response(data)


class MutesView(DashboardView):
    def get(self, request):
        return Response({'results': list(MutedUser.objects.filter(user=request.user).values('target_id', 'target__username'))})

    def post(self, request):
        pk = serializers.IntegerField(min_value=1).run_validation(request.data.get('user_id'))
        target = get_object_or_404(get_user_model(), pk=pk, is_active=True)
        if pk == request.user.pk:
            raise serializers.ValidationError('Wybierz inną osobę.')
        MutedUser.objects.get_or_create(user=request.user, target=target)
        return Response({'muted': True})


class MuteDetailView(DashboardView):
    def delete(self, request, user_id):
        MutedUser.objects.filter(user=request.user, target_id=user_id).delete()
        return Response(status=204)


def report_data(row, user):
    decisions = list(row.decisions.order_by('created_at', 'pk').values('action', 'rule', 'explanation', 'is_appeal', 'created_at'))
    last = decisions[-1] if decisions else None
    status = 'pending' if row.status in ('new', 'appeal') else (
        'removed' if last and last['action'] == 'hide' else 'restored' if last and last['is_appeal'] else 'rejected')
    return {'id': row.pk, 'thread_id': row.thread_id, 'target_kind': row.target_kind,
        'mine': row.reporter_id == user.pk, 'status': status, 'reason': row.reason,
        'created_at': row.created_at, 'decisions': decisions, 'appealed': bool(row.appealed_at),
        'can_appeal': row.status == 'resolved' and not row.appealed_at}


class ReportsView(DashboardView):
    def get(self, request):
        rows = ThreadModerationReport.objects.filter(Q(reporter=request.user) | Q(target_author=request.user)).prefetch_related('decisions').order_by('-created_at', '-pk')
        batch, next_page = page(request, rows)
        return Response({'results': [report_data(row, request.user) for row in batch], 'next_page': next_page})


class ProfileReportView(DashboardView):
    def post(self, request, username):
        from news.thread_social import ReportInput, locked_account
        from rest_framework.exceptions import Throttled
        require_verified(request.user)
        target = get_object_or_404(get_user_model(), username__iexact=username, is_active=True)
        data = ReportInput(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            locked_account(request.user)
            if ThreadModerationReport.objects.filter(reporter=request.user, created_at__gt=timezone.now()-timedelta(hours=1)).count() >= 20:
                raise Throttled(wait=3600)
            profile = profile_data(target)
            row, created = ThreadModerationReport.objects.get_or_create(reporter=request.user, target_author=target,
                target_kind='profile', defaults={**data.validated_data, 'snapshot': f"@{target.username}\n{profile['bio']}"})
        return Response({'id': row.pk}, status=201 if created else 200)


class PasswordChangeView(DashboardView):
    throttle_classes = [AccountIPThrottle]

    def post(self, request):
        current = serializers.CharField(max_length=256, trim_whitespace=False).run_validation(request.data.get('current_password'))
        password = serializers.CharField(max_length=256, trim_whitespace=False).run_validation(request.data.get('password'))
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not user.check_password(current):
                raise serializers.ValidationError({'current_password': 'Hasło jest nieprawidłowe.'})
            try:
                validate_password(password, user)
            except PasswordError as exc:
                raise serializers.ValidationError({'password': exc.messages})
            user.set_password(password)
            user.save(update_fields=['password'])
            update_session_auth_hash(request, user)
        return Response({'detail': 'Hasło zmienione.'})


class LogoutAllView(DashboardView):
    def post(self, request):
        # The project uses Django's database session backend; delete all active sessions,
        # including the current device, without modifying the password or Google identity.
        for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
            if str(session.get_decoded().get('_auth_user_id')) == str(request.user.pk):
                session.delete()
        logout(request)
        return Response({'detail': 'Wylogowano ze wszystkich urządzeń.'})
