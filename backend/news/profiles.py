from news.features import ThreadsEnabledMixin
"""Private aggregate activity unless the account owner explicitly opts in."""
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from news.accounts import AccountWriteThrottle, OpinionSerializer, OpinionReadThrottle
from news.account_models import ProfilePreference, ThreadFavorite, ArticleOpinion
from news.models import Thread
from news.schema import json_view


def paginate(request, rows, serialize):
    try:
        page = int(request.query_params.get('page', '1'))
        if not 1 <= page <= 10000:
            raise ValueError()
    except (ValueError, TypeError):
        raise serializers.ValidationError('Nieprawidłowy numer strony.')
    batch = list(rows[(page - 1) * 20:page * 20 + 1])
    return {'results': [serialize(row) for row in batch[:20]], 'next_page': page + 1 if len(batch) > 20 else None}


def history(request, user):
    rows = ArticleOpinion.objects.filter(user=user, article__source__is_active=True).exclude(
        article__source__catalog_stage='excluded').select_related('user')
    return paginate(request, rows, lambda row: {**OpinionSerializer(row).data, 'article_id': row.article_id})


class ProfileInput(serializers.Serializer):
    username = serializers.RegexField(r'^[A-Za-z0-9_]{3,30}$', max_length=30, required=False)
    bio = serializers.CharField(max_length=160, allow_blank=True, required=False)
    public_activity = serializers.BooleanField(required=False)
    theme_preference = serializers.ChoiceField(choices=ProfilePreference.THEME_CHOICES, required=False)
    nick_color = serializers.ChoiceField(choices=[''] + ProfilePreference.NICK_COLORS, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Podaj ustawienie do zmiany.')
        return attrs


@json_view("Profil użytkownika", tags=["konto"])
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response
    def get(self, request):
        from news.account_dashboard import profile_data
        return Response(profile_data(request.user, private=True))
    def patch(self, request):
        serializer = ProfileInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
                preference, _ = ProfilePreference.objects.get_or_create(user=user)
                values = dict(serializer.validated_data)
                if values.get('nick_color') and not hasattr(user, 'x_connection'):
                    raise serializers.ValidationError({'nick_color': 'Kolor nicka jest dostępny po połączeniu konta z X.'})
                nick = values.pop('username', user.username).lower()
                if nick != user.username:
                    if preference.nick_changed_at and timezone.now() < preference.nick_changed_at + timedelta(days=30):
                        raise serializers.ValidationError({'username': 'Nick możesz zmienić raz na 30 dni.'})
                    if get_user_model().objects.filter(username__iexact=nick).exclude(pk=user.pk).exists():
                        raise serializers.ValidationError({'username': 'Ten nick jest niedostępny.'})
                    user.username = nick
                    user.save(update_fields=['username'])
                    preference.nick_changed_at = timezone.now()
                for field, value in values.items():
                    setattr(preference, field, value)
                preference.save()
                request.user.username = user.username
        except IntegrityError:
            raise serializers.ValidationError({'username': 'Ten nick jest niedostępny.'})
        return self.get(request)


@json_view("Historia przeglądania", tags=["konto"])
class HistoryView(ProfileView):
    def get(self, request):
        return Response(history(request, request.user))
    def patch(self, request):
        return Response(status=405)


@json_view("Publiczna aktywność profilu", tags=["konto"])
class PublicActivityView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OpinionReadThrottle, AccountWriteThrottle]
    def get(self, request, username):
        from news.x_accounts import public_identity
        user = get_object_or_404(get_user_model(), username=username, is_active=True,
                                profile_preference__public_activity=True)
        return Response({'id': user.pk, 'username': user.username, **public_identity(user), 'history': history(request, user)})


def favorite_data(row):
    return {'id': row.pk, 'thread': {'id': row.thread_id, 'slug': row.thread.slug, 'title': row.thread.title},
            'created_at': row.created_at.isoformat()}


class FavoriteInput(serializers.Serializer):
    thread_id = serializers.IntegerField(min_value=1)


@json_view("Ulubione spinki", tags=["konto"])
class FavoritesView(ThreadsEnabledMixin, APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]
    def get(self, request):
        rows = ThreadFavorite.objects.filter(user=request.user, thread__published=True).select_related('thread')
        if 'thread_id' in request.query_params:
            serializer = FavoriteInput(data={'thread_id': request.query_params['thread_id']})
            serializer.is_valid(raise_exception=True)
            rows = rows.filter(thread_id=serializer.validated_data['thread_id'])
        return Response(paginate(request, rows, favorite_data))
    def post(self, request):
        serializer = FavoriteInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            thread = get_object_or_404(Thread.objects.select_for_update(), pk=serializer.validated_data['thread_id'], published=True)
            row, created = ThreadFavorite.objects.get_or_create(user=request.user, thread=thread)
        return Response(favorite_data(row), status=201 if created else 200)


@json_view("Ulubiona spinka", tags=["konto"])
class FavoriteDetailView(ThreadsEnabledMixin, APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]
    def delete(self, request, thread_id):
        ThreadFavorite.objects.filter(user=request.user, thread_id=thread_id).delete()
        return Response(status=204)
