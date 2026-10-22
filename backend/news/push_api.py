import base64
import uuid
from urllib.parse import urlsplit
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from news.push import TOPICS, CONSENT_VERSION
from news.features import push_enabled
from news.push_models import PushSubscription
from django.conf import settings


def enabled():
    return bool(push_enabled() and settings.VAPID_PUBLIC_KEY
                and settings.VAPID_PRIVATE_KEY and settings.VAPID_SUBJECT)


class SubscriptionInput(serializers.Serializer):
    endpoint = serializers.URLField(max_length=2048)
    keys = serializers.DictField(child=serializers.CharField(max_length=128))
    topics = serializers.ListField(child=serializers.ChoiceField(choices=TOPICS), max_length=len(TOPICS), allow_empty=False)
    consent_version = serializers.ChoiceField(choices=[CONSENT_VERSION])

    def validate_endpoint(self, value):
        url = urlsplit(value)
        # Only browser push services; arbitrary endpoints would allow server-side requests.
        host = url.hostname or ''
        allowed = (host == 'fcm.googleapis.com' or host == 'updates.push.services.mozilla.com'
                   or host.endswith('.push.services.mozilla.com')
                   or host == 'web.push.apple.com' or host.endswith('.push.apple.com'))
        try:
            valid_port = url.port in (None, 443)
        except ValueError:
            valid_port = False
        if url.scheme != 'https' or not allowed or not valid_port or url.username or url.password or url.fragment:
            raise serializers.ValidationError('Nieobsługiwana usługa push.')
        return value

    def validate_keys(self, value):
        try:
            for key, size in [('p256dh', 65), ('auth', 16)]:
                raw = base64.b64decode(value[key] + '=' * (-len(value[key]) % 4), altchars=b'-_', validate=True)
                if len(raw) != size or (key == 'p256dh' and raw[0] != 4):
                    raise ValueError()
        except (KeyError, ValueError):
            raise serializers.ValidationError('Nieprawidłowe klucze subskrypcji.')
        return {key: value[key] for key in ('p256dh', 'auth')}


@method_decorator(csrf_protect, name='dispatch')
class SubscriptionsView(APIView):
    permission_classes = [AllowAny]

    def _device(self, request):
        value = request.session.get('push_device')
        if not value:
            value = str(uuid.uuid4())
            request.session['push_device'] = value
        return value

    def get(self, request):
        active = enabled()
        rows = PushSubscription.objects.filter(device=self._device(request)) if active else []
        response = Response({'enabled': active, 'public_key': settings.VAPID_PUBLIC_KEY if active else '',
                             'consent_version': CONSENT_VERSION, 'csrfToken': get_token(request),
                             'results': [{'endpoint': r.endpoint, 'topics': r.topics} for r in rows]})
        response['Cache-Control'] = 'no-store'
        return response

    def post(self, request):
        if not enabled():
            return Response({'detail': 'Powiadomienia są wyłączone.'}, status=503)
        serializer = SubscriptionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # Alerty o obserwowanych osobach są przypisane do konta; anonimowa subskrypcja nigdy by ich nie dostała (zlecenie 116).
        if 'obserwowani' in data['topics'] and not request.user.is_authenticated:
            return Response({'detail': 'Alerty o obserwowanych osobach wymagają konta.'}, status=401)
        device = self._device(request)
        defaults = {**data, 'device': device,
                    'user': request.user if request.user.is_authenticated else None,
                    'consent_at': timezone.now()}
        with transaction.atomic():
            row, created = PushSubscription.objects.get_or_create(endpoint=data['endpoint'], defaults=defaults)
            row = PushSubscription.objects.select_for_update().get(pk=row.pk)
            if str(row.device) != device:
                return Response({'detail': 'Subskrypcja należy do innej sesji. Wyłącz ją i włącz ponownie.'}, status=409)
            if not created:
                for key, value in defaults.items():
                    setattr(row, key, value)
                row.save()
        return Response({'topics': data['topics']}, status=201)

    def delete(self, request):
        # Withdrawal remains available after the feature has been disabled.
        PushSubscription.objects.filter(device=self._device(request)).delete()
        return Response(status=204)
