"""Public session accounts. Editorial authentication and permissions stay separate."""
import unicodedata
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

from news.account_models import ArticleOpinion, SavedTopic
from news.models import Article, ArticleCategory, Source
from news.topics import TOPICS
from news.editorial_roles import role_data


def user_data(user):
    return {'id': user.pk, 'username': user.username, 'is_staff': user.is_staff, **role_data(user)}


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
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs):
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
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AccountIPThrottle, AccountNameThrottle]

    def post(self, request):
        serializer = RegistrationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(**serializer.validated_data,
                    is_staff=False, is_superuser=False, is_active=True)
        except IntegrityError:
            return Response({'username': ['Ta nazwa jest niedostępna.']}, status=400)
        login(request, user)
        return Response({'authenticated': True, 'user': user_data(user), 'csrfToken': get_token(request)}, status=201)


class LoginInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AccountIPThrottle, AccountNameThrottle]
    def post(self, request):
        serializer = LoginInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = authenticate(request, username=data['username'].lower(), password=data['password'])
        if user is None:
            return Response({'detail': 'Nieprawidłowa nazwa lub hasło.'}, status=403)
        login(request, user)
        return Response({'authenticated': True, 'user': user_data(user), 'csrfToken': get_token(request)})


@method_decorator(csrf_protect, name='dispatch')
class LogoutView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        logout(request)
        return Response({'authenticated': False, 'user': None, 'csrfToken': get_token(request)})


@method_decorator(ensure_csrf_cookie, name='dispatch')
class AccountMeView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({'authenticated': request.user.is_authenticated,
                         'user': user_data(request.user) if request.user.is_authenticated else None,
                         'csrfToken': get_token(request)})


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
        if not isinstance(request.data, dict) or set(request.data) - {'body'}:
            raise serializers.ValidationError('Możesz jedynie dopisać komentarz; reakcja pozostaje bez zmian.')
        serializer = OpinionInput(data={'polarity': 'positive', **request.data})
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data['body']
        if not body:
            raise serializers.ValidationError({'body': 'Podaj treść komentarza.'})
        with transaction.atomic():
            opinion = get_object_or_404(ArticleOpinion.objects.select_for_update().select_related('user'),
                                       article_id=article_id, user=request.user)
            if opinion.body or not ArticleOpinion.objects.filter(pk=opinion.pk, body='').update(body=body):
                return Response({'detail': 'Komentarz został już zapisany i nie można go zastąpić.'}, status=409)
            opinion.body = body
        return Response(OpinionSerializer(opinion).data)
