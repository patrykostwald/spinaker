from news.features import ThreadsEnabledMixin
"""Public session accounts. Editorial authentication and permissions stay separate."""
import base64
import hashlib
import hmac
import secrets
import unicodedata
from urllib.parse import urlencode

import requests
from django.conf import settings
from news.features import accounts_enabled
from django.http import HttpResponseRedirect
from hashlib import sha256

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from news.account_models import ArticleOpinion, ThreadOpinion, SavedTopic, UserXConnection, AccountIdentity
from news.account_security import AccountEnabled, require_verified
from django.utils import timezone
from news.models import Article, ArticleCategory, Source, Thread
from news.topics import TOPICS
from news.editorial_roles import role_data
from news.schema import json_view
from drf_spectacular.utils import extend_schema, extend_schema_view


def user_data(user):
    identity = getattr(user, 'account_identity', None)
    return {'id': user.pk, 'username': user.username, **public_identity(user), 'is_staff': user.is_staff,
            'is_social': user.groups.filter(name='social').exists(),
            'email': user.email, 'email_verified': bool(identity and identity.email_verified),
            'accepted_terms_version': identity.accepted_terms_version if identity else '', **role_data(user)}


class AccountIPThrottle(SimpleRateThrottle):
    scope = 'public_account_ip'
    rate = '20/hour'
    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class AccountNameThrottle(SimpleRateThrottle):
    scope = 'public_account_name'
    rate = '10/hour'
    def get_cache_key(self, request, view):
        name = request.data.get('username', '') if isinstance(request.data, dict) else ''
        digest = sha256(str(name).strip().casefold().encode()).hexdigest()
        return self.cache_format % {'scope': self.scope, 'ident': digest}


class RegistrationInput(serializers.Serializer):
    username = serializers.RegexField(r'^[A-Za-z0-9_]{3,30}$', max_length=30)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)
    email = serializers.EmailField(max_length=254)
    accepted_terms = serializers.BooleanField()
    accepted_privacy = serializers.BooleanField(required=False)
    adult = serializers.BooleanField()
    newsletter = serializers.BooleanField(default=False)

    def validate(self, attrs):
        for field in ('accepted_terms', 'adult'):
            if not attrs.get(field):
                raise serializers.ValidationError({field: 'Potwierdź ukończenie 18 lat.' if field == 'adult' else 'Zaakceptuj zasady korzystania.'})
        attrs['email'] = attrs['email'].strip().lower()
        # Canonical public handles prevent case-only impersonation/races.
        attrs['username'] = attrs['username'].lower()
        if get_user_model().objects.filter(username__iexact=attrs['username']).exists():
            raise serializers.ValidationError({'username': 'Ta nazwa jest niedostępna.'})
        user = get_user_model()(username=attrs['username'], email=attrs.get('email', ''))
        try:
            validate_password(attrs['password'], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages})
        return attrs


@method_decorator(csrf_protect, name='dispatch')
@json_view("Rejestracja konta", tags=["konto"])
class RegisterView(APIView):
    permission_classes = [AccountEnabled, AllowAny]
    throttle_classes = [AccountIPThrottle, AccountNameThrottle]

    def post(self, request):
        serializer = RegistrationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop('accepted_terms')
        data.pop('accepted_privacy', None)
        user = get_user_model()(username=data['username'], email=data['email'],
                                is_staff=False, is_superuser=False, is_active=True)
        user.set_password(data['password'])
        # Identical response for an occupied email; never log in based on registration.
        if not get_user_model().objects.filter(email__iexact=data['email']).exists():
            try:
                with transaction.atomic():
                    user.save()
                    AccountIdentity.objects.create(user=user, email=data['email'],
                        adult_declared_at=timezone.now(),
                        newsletter_consent_at=timezone.now() if data['newsletter'] else None,
                        accepted_terms_version=settings.ACCOUNT_TERMS_VERSION,
                        accepted_privacy_version=settings.ACCOUNT_PRIVACY_VERSION, accepted_at=timezone.now())
            except IntegrityError:
                pass
        from news.account_lifecycle import queue_verification
        queue_verification(data['email'])
        return Response({'authenticated': False, 'user': None, 'csrfToken': get_token(request),
                         'detail': 'Sprawdź pocztę, aby potwierdzić e-mail. Jeśli masz już konto, zaloguj się lub ustaw nowe hasło.'}, status=201)



class LoginInput(serializers.Serializer):
    username = serializers.CharField(max_length=254)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


@method_decorator(csrf_protect, name='dispatch')
@json_view("Logowanie", tags=["konto"])
class LoginView(APIView):
    # Logowanie działa zawsze (zespół, dziennikarze); flaga ACCOUNTS_ENABLED zamyka tylko rejestrację czytelników.
    permission_classes = [AllowAny]
    throttle_classes = [AccountIPThrottle, AccountNameThrottle]
    def post(self, request):
        serializer = LoginInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        identifier = data['username'].strip().lower()
        if '@' in identifier:
            matches = list(get_user_model().objects.filter(email__iexact=identifier).values_list('username', flat=True)[:2])
            if len(matches) == 1:
                user = authenticate(request, username=matches[0], password=data['password'])
            else:
                # Match the password-hash work without using a reservable username.
                get_user_model()().set_password(data['password'])
                user = None
        else:
            user = authenticate(request, username=identifier, password=data['password'])
        if user is None:
            return Response({'detail': 'Nieprawidłowa nazwa lub hasło.'}, status=403)
        login(request, user)
        return Response({'authenticated': True, 'user': user_data(user), 'csrfToken': get_token(request)})


@method_decorator(csrf_protect, name='dispatch')
@json_view("Wylogowanie", tags=["konto"])
class LogoutView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        logout(request)
        return Response({'authenticated': False, 'user': None, 'csrfToken': get_token(request)})


@method_decorator(ensure_csrf_cookie, name='dispatch')
@json_view("Bieżące konto", tags=["konto"])
class AccountMeView(APIView):
    permission_classes = [AllowAny]
    def get_throttles(self):
        return [AccountIPThrottle()] if self.request.method == 'PATCH' else []

    def get(self, request):
        return Response({'authenticated': request.user.is_authenticated,
                         'user': user_data(request.user) if request.user.is_authenticated else None,
                         'csrfToken': get_token(request),
                         'accounts_enabled': accounts_enabled(), 'x_enabled': bool(accounts_enabled() and x_enabled()),
                         'google_enabled': bool(accounts_enabled() and settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)})

    def patch(self, request):
        AccountEnabled().has_permission(request, self)
        if not request.user.is_authenticated:
            from rest_framework.exceptions import NotAuthenticated
            raise NotAuthenticated()
        from news.account_lifecycle import update_account
        return update_account(request)


from news.x_accounts import XConnectionView, XConnectionStartView, XConnectionCallbackView, x_enabled, public_identity


class TopicSerializer(serializers.ModelSerializer):
    query = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    topics = serializers.ListField(child=serializers.ChoiceField(choices=list(TOPICS)), max_length=13, required=False)
    categories = serializers.ListField(child=serializers.ChoiceField(choices=ArticleCategory.choices), max_length=40, required=False)
    source_ids = serializers.PrimaryKeyRelatedField(source='sources', many=True,
        queryset=Source.objects.filter(is_active=True).exclude(catalog_stage='excluded'), required=False)
    position = serializers.IntegerField(min_value=0, max_value=9, required=False)
    class Meta:
        model = SavedTopic
        fields = ['id', 'label', 'query', 'categories', 'topics', 'source_ids', 'position']
        read_only_fields = ['id']
    def validate_categories(self, value):
        return list(dict.fromkeys(value))
    def validate_source_ids(self, value):
        if len(value) > 200:
            raise serializers.ValidationError('Wybierz najwyżej 200 źródeł.')
        return list({source.pk: source for source in value}.values())


class AccountWriteThrottle(UserRateThrottle):
    scope = 'account_write'
    rate = '120/hour'


@json_view("Paski tematów użytkownika", tags=["konto"])
class TopicsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]
    def get(self, request):
        rows = SavedTopic.objects.filter(owner=request.user).prefetch_related('sources')
        return Response({'topics': TopicSerializer(rows, many=True).data, 'max_topics': 10})
    def post(self, request):
        serializer = TopicSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                used = set(SavedTopic.objects.filter(owner=request.user).values_list('slot', flat=True))
                free = next((slot for slot in range(10) if slot not in used), None)
                if free is None:
                    return Response({'detail': 'Możesz zapisać najwyżej 10 pasków.'}, status=409)
                serializer.save(owner=request.user, slot=free)
        except IntegrityError:
            return Response({'detail': 'Równoczesny zapis. Odśwież listę pasków.'}, status=409)
        return Response(serializer.data, status=201)


@json_view("Pasek tematu użytkownika", tags=["konto"])
@extend_schema_view(get=extend_schema(operation_id="account_topics_detail_retrieve"), post=extend_schema(operation_id="account_topics_detail_create"))
class TopicDetailView(TopicsView):
    def get(self, request, topic_id):
        return Response(TopicSerializer(get_object_or_404(SavedTopic, pk=topic_id, owner=request.user)).data)
    def post(self, request, topic_id):
        return Response(status=405)
    def patch(self, request, topic_id):
        topic = get_object_or_404(SavedTopic, pk=topic_id, owner=request.user)
        serializer = TopicSerializer(topic, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    def delete(self, request, topic_id):
        get_object_or_404(SavedTopic, pk=topic_id, owner=request.user).delete()
        return Response(status=204)


def conservative_x_weight(text):
    """Conservative codepoint budget using twitter-text v3 ranges, not X parsing.

    Reference: https://raw.githubusercontent.com/twitter/twitter-text/master/config/v3.json
    No URL extraction/shortening or emoji-sequence discount. This is an additional
    server text limit, not certification of an exported post; frontend must use
    official twitter-text on the complete comment plus appended source link.
    """
    ranges = ((0, 0x10FF), (0x2000, 0x200D), (0x2010, 0x201F), (0x2032, 0x2037))
    return sum(1 if any(start <= ord(c) <= end for start, end in ranges) else 2 for c in text)


class OpinionInput(serializers.Serializer):
    polarity = serializers.ChoiceField(choices=['positive', 'negative'])
    body = serializers.CharField(max_length=240, required=False, allow_blank=True, default='')
    def validate_body(self, value):
        value = unicodedata.normalize('NFC', value)
        if any(unicodedata.category(c) in {'Cs', 'Cc'} and c not in '\n\t' for c in value):
            raise serializers.ValidationError('Komentarz zawiera niedozwolone znaki.')
        if conservative_x_weight(value) > 240:
            raise serializers.ValidationError('Skróć komentarz do budżetu 240 znaków ważonych; emoji mogą zajmować więcej miejsca.')
        return value


class OpinionSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    class Meta:
        model = ArticleOpinion
        fields = ['id', 'author', 'polarity', 'body', 'created_at']
    def get_author(self, opinion):
        return {'id': opinion.user_id, 'username': opinion.user.username}


class OpinionReadThrottle(AnonRateThrottle):
    scope = 'opinion_read'
    rate = '300/hour'


@json_view("Reakcje i komentarze do materiału (przydatne / nieprzydatne)", tags=["reakcje"])
class OpinionsView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OpinionReadThrottle, AccountWriteThrottle]
    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method in ('POST', 'PATCH') else super().get_permissions()
    def get(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        try:
            size = min(20, max(1, int(request.query_params.get('page_size', 20))))
            pages = {p: max(1, int(request.query_params.get(p + '_page', 1))) for p in ['positive', 'negative']}
            if max(pages.values()) > 10000:
                raise ValueError()
        except (ValueError, TypeError):
            raise serializers.ValidationError('Nieprawidłowy numer strony.')
        rows = article.opinions.select_related('user')
        counts = {'positive': 0, 'negative': 0}
        counts.update({row['polarity']: row['n'] for row in rows.values('polarity').annotate(n=Count('id'))})
        result = {'counts': counts, 'mine': None}
        if request.user.is_authenticated:
            mine = rows.filter(user=request.user).first()
            result['mine'] = OpinionSerializer(mine).data if mine else None
        for polarity, page in pages.items():
            offset = (page - 1) * size
            batch = list(rows.filter(polarity=polarity).exclude(body='')[offset:offset + size + 1])
            result[polarity] = {'results': OpinionSerializer(batch[:size], many=True).data,
                                'next_page': page + 1 if len(batch) > size else None}
        return Response(result)
    def post(self, request, article_id):
        require_verified(request.user)
        article = get_object_or_404(Article, pk=article_id)
        serializer = OpinionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                opinion = ArticleOpinion.objects.create(user=request.user, article=article, **serializer.validated_data)
        except IntegrityError:
            return Response({'detail': 'Twój komentarz do tego materiału jest już zapisany i nie można go zmienić.'}, status=409)
        return Response(OpinionSerializer(opinion).data, status=201)

    def patch(self, request, article_id):
        require_verified(request.user)
        if not isinstance(request.data, dict) or set(request.data) - {'body'}:
            raise serializers.ValidationError('Możesz jedynie dopisać komentarz; reakcja pozostaje bez zmian.')
        serializer = OpinionInput(data={'polarity': 'positive', **request.data})
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data['body']
        if not body:
            raise serializers.ValidationError({'body': 'Podaj treść komentarza.'})
        with transaction.atomic():
            opinion = get_object_or_404(ArticleOpinion.objects.select_for_update(of=('self',)).select_related('user'),
                                       article_id=article_id, user=request.user)
            if opinion.body or not ArticleOpinion.objects.filter(pk=opinion.pk, body='').update(body=body):
                return Response({'detail': 'Komentarz został już zapisany i nie można go zastąpić.'}, status=409)
            opinion.body = body
        return Response(OpinionSerializer(opinion).data)


class ThreadOpinionSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    class Meta:
        model = ThreadOpinion
        fields = ['id', 'author', 'polarity', 'body', 'created_at']
    def get_author(self, opinion):
        return {'id': opinion.user_id, 'username': opinion.user.username}


@json_view("Reakcje i komentarze do spinki kontekstowej", tags=["reakcje"])
class ThreadOpinionsView(ThreadsEnabledMixin, APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OpinionReadThrottle, AccountWriteThrottle]
    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method in ('POST', 'PATCH') else super().get_permissions()
    def _thread(self, slug):
        return get_object_or_404(Thread, slug=slug, published=True)
    def get(self, request, slug):
        rows = self._thread(slug).opinions.select_related('user')
        counts = {'positive': 0, 'negative': 0}
        counts.update({row['polarity']: row['n'] for row in rows.values('polarity').annotate(n=Count('id'))})
        mine = rows.filter(user=request.user).first() if request.user.is_authenticated else None
        return Response({
            'counts': counts,
            'mine': ThreadOpinionSerializer(mine).data if mine else None,
            'positive': ThreadOpinionSerializer(rows.filter(polarity='positive').exclude(body='')[:20], many=True).data,
            'negative': ThreadOpinionSerializer(rows.filter(polarity='negative').exclude(body='')[:20], many=True).data,
        })
    def post(self, request, slug):
        require_verified(request.user)
        thread = self._thread(slug)
        serializer = OpinionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                opinion = ThreadOpinion.objects.create(user=request.user, thread=thread, **serializer.validated_data)
        except IntegrityError:
            return Response({'detail': 'Twoja opinia o tej spince jest już zapisana.'}, status=409)
        return Response(ThreadOpinionSerializer(opinion).data, status=201)
    def patch(self, request, slug):
        require_verified(request.user)
        if not isinstance(request.data, dict) or set(request.data) - {'body'}:
            raise serializers.ValidationError('Możesz jedynie dopisać komentarz; reakcja pozostaje bez zmian.')
        serializer = OpinionInput(data={'polarity': 'positive', **request.data})
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data['body']
        if not body:
            raise serializers.ValidationError({'body': 'Podaj treść komentarza.'})
        with transaction.atomic():
            opinion = get_object_or_404(ThreadOpinion.objects.select_for_update(of=('self',)).select_related('user'), thread__slug=slug,
                                        thread__published=True, user=request.user)
            if opinion.body or not ThreadOpinion.objects.filter(pk=opinion.pk, body='').update(body=body):
                return Response({'detail': 'Komentarz został już zapisany i nie można go zastąpić.'}, status=409)
            opinion.body = body
        return Response(ThreadOpinionSerializer(opinion).data)
