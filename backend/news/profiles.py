"""Private aggregate activity unless the account owner explicitly opts in."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from news.accounts import AccountWriteThrottle, OpinionSerializer, OpinionReadThrottle
from news.account_models import ProfilePreference, ThreadFavorite, ArticleOpinion
from news.models import Thread


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
    public_activity = serializers.BooleanField()


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]
    def get(self, request):
        value = ProfilePreference.objects.filter(user=request.user).values_list('public_activity', flat=True).first()
        return Response({'username': request.user.username, 'public_activity': bool(value)})
    def patch(self, request):
        serializer = ProfileInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        ProfilePreference.objects.update_or_create(user=request.user, defaults=serializer.validated_data)
        return self.get(request)


class HistoryView(ProfileView):
    def get(self, request):
        return Response(history(request, request.user))
    def patch(self, request):
        return Response(status=405)


class PublicActivityView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OpinionReadThrottle, AccountWriteThrottle]
    def get(self, request, username):
        user = get_object_or_404(get_user_model(), username=username, is_active=True,
                                profile_preference__public_activity=True)
        return Response({'username': user.username, 'history': history(request, user)})


def favorite_data(row):
    return {'id': row.pk, 'thread': {'id': row.thread_id, 'slug': row.thread.slug, 'title': row.thread.title},
            'created_at': row.created_at.isoformat()}


class FavoriteInput(serializers.Serializer):
    thread_id = serializers.IntegerField(min_value=1)


class FavoritesView(APIView):
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


class FavoriteDetailView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]
    def delete(self, request, thread_id):
        ThreadFavorite.objects.filter(user=request.user, thread_id=thread_id).delete()
        return Response(status=204)
