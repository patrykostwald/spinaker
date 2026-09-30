"""Account notification endpoints; all queries are scoped to their owner."""
from news.features import accounts_enabled
from urllib.parse import quote
from django.contrib.auth import get_user_model
from django.http import Http404
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from news.accounts import AccountWriteThrottle
from news.notification_models import Follow, Notification, NotificationSettings
from news.political_models import PublicFigure
from news.schema import json_view


class AccountNotificationView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]

    def initial(self, request, *args, **kwargs):
        if not accounts_enabled():
            raise Http404
        return super().initial(request, *args, **kwargs)


def follow_data(row):
    if row.figure_id:
        label, url = row.figure.canonical_name, f'/osoby-publiczne/{row.figure_id}'
    elif row.target_user_id:
        label, url = row.target_user.username, f'/profile/{quote(row.target_user.username, safe="")}'
    else:
        label, url = row.thread.title, f'/nitki/{row.thread_id}'
    return {'id': row.pk, 'kind': row.kind, 'target_id': row.target_id, 'label': label, 'url': url}


class FollowInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=['figure', 'user', 'thread'])
    target_id = serializers.IntegerField(min_value=1)


@json_view('Obserwowani', tags=['konto'])
class FollowsView(AccountNotificationView):
    def get(self, request):
        from news.community import public_threads
        rows = Follow.objects.filter(user=request.user).filter(Q(thread__isnull=True) | Q(thread__in=public_threads()))
        return Response([follow_data(row) for row in rows.select_related('figure', 'target_user', 'thread')])

    def post(self, request):
        data = FollowInput(data=request.data)
        data.is_valid(raise_exception=True)
        kind, pk = data.validated_data['kind'], data.validated_data['target_id']
        if kind == 'figure':
            target = {'figure': get_object_or_404(PublicFigure, pk=pk, archived=False)}
        elif kind == 'user':
            target = {'target_user': get_object_or_404(get_user_model(), pk=pk, is_active=True)}
            if pk == request.user.pk:
                raise serializers.ValidationError({'target_id': 'Wybierz inną osobę.'})
        else:
            from news.community import public_threads, threads_enabled
            if not threads_enabled():
                raise Http404
            target = {'thread': get_object_or_404(public_threads(), pk=pk)}
        row, created = Follow.objects.get_or_create(user=request.user, **target)
        return Response(follow_data(row), status=201 if created else 200)


@json_view('Przestań obserwować', tags=['konto'])
class FollowDetailView(AccountNotificationView):
    def delete(self, request, follow_id):
        get_object_or_404(Follow, user=request.user, pk=follow_id).delete()
        return Response(status=204)


@json_view('Powiadomienia', tags=['konto'])
class NotificationsView(AccountNotificationView):
    def get(self, request):
        rows = Notification.objects.filter(user=request.user)
        return Response({'results': list(rows.values('id', 'kind', 'title', 'url', 'created_at', 'read_at')[:100]), 'unread': rows.filter(read_at__isnull=True).count()})


class ReadInput(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=100, required=False)
    all = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs.get('all') and not attrs.get('ids'):
            raise serializers.ValidationError('Wybierz powiadomienia do oznaczenia.')
        return attrs


@json_view('Oznacz przeczytane', tags=['konto'])
class NotificationReadView(AccountNotificationView):
    def post(self, request):
        data = ReadInput(data=request.data)
        data.is_valid(raise_exception=True)
        rows = Notification.objects.filter(user=request.user, read_at__isnull=True)
        if not data.validated_data.get('all'):
            rows = rows.filter(pk__in=data.validated_data['ids'])
        rows.update(read_at=timezone.now())
        return Response({'unread': Notification.objects.filter(user=request.user, read_at__isnull=True).count()})


class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = ['email_digest', 'push_spin_of_day', 'push_followed', 'push_thread_replies']


@json_view('Ustawienia powiadomień', tags=['konto'])
class NotificationSettingsView(AccountNotificationView):
    def get(self, request):
        row, _ = NotificationSettings.objects.get_or_create(user=request.user)
        return Response(SettingsSerializer(row).data)

    def patch(self, request):
        row, _ = NotificationSettings.objects.get_or_create(user=request.user)
        data = SettingsSerializer(row, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        if 'email_digest' in data.validated_data and data.validated_data['email_digest'] != row.email_digest:
            data.save(last_digest_at=timezone.now())
        else:
            data.save()
        return Response(data.data)
