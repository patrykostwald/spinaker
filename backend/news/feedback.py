"""„Zgłoś błąd” i zbiorcza mapa ścieżek. Opis zasad w feedback_models."""
import re

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from news.feedback_models import BugReport, JourneyStep

ENTRY, EXIT = '(wejście)', '(wyjście)'
ACTION = re.compile(r'^(nav|exit|click|rage):?[a-z0-9_-]{0,50}$')


def clean_path(value):
    """Adres bez zapytania i fragmentu; liczby i nazwy użytkowników zamienione na znacznik, żeby nic nie wskazywało osoby."""
    value = str(value or '').split('?')[0].split('#')[0][:200]
    if value in (ENTRY, EXIT):
        return value
    if not value.startswith('/'):
        return ''
    value = re.sub(r'^/(profile|profil|u)/[^/]+', r'/\1/:nick', value)
    value = re.sub(r'/\d+(?=/|$)', '/:id', value)
    value = re.sub(r'/[0-9a-f]{16,}(?=/|$)', '/:id', value)
    return value[:120]


class BugThrottle(AnonRateThrottle):
    rate = '5/hour'


class BugUserThrottle(UserRateThrottle):
    rate = '10/hour'


class BugInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=['bug', 'idea'], default='bug')
    text = serializers.CharField(min_length=5, max_length=1000)
    path = serializers.CharField(max_length=200)
    viewport = serializers.RegexField(r'^\d{2,5}x\d{2,5}$', required=False, allow_blank=True)
    theme = serializers.ChoiceField(choices=['light', 'dark', ''], required=False, default='')
    trail = serializers.ListField(child=serializers.CharField(max_length=200), max_length=12, required=False, default=list)
    contact = serializers.EmailField(required=False, allow_blank=True)


class BugReportView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [BugThrottle, BugUserThrottle]

    def post(self, request):
        data = BugInput(data=request.data)
        data.is_valid(raise_exception=True)
        row = data.validated_data
        report = BugReport.objects.create(
            kind=row['kind'], text=row['text'].strip(), path=clean_path(row['path']) or '/',
            viewport=row.get('viewport', ''), theme=row.get('theme', ''),
            trail=[p for p in (clean_path(item) for item in row.get('trail', [])) if p],
            contact=row.get('contact', ''), user=request.user if request.user.is_authenticated else None)
        transaction.on_commit(lambda: notify(report))
        return Response({'ok': True}, status=status.HTTP_201_CREATED)


def notify(report):
    """Mail do właściciela; poczta nie blokuje zgłoszenia."""
    try:
        from news.council_recruiter import _owner_email
        from news.social_publish import _mail
        trail = ' → '.join(report.trail) or '-'
        body = (f'{report.get_kind_display()} na {report.path}\n\n{report.text}\n\n'
                f'Ekran: {report.viewport or "-"} · motyw: {report.theme or "-"}\nOstatnie strony: {trail}\n'
                f'Kontakt: {report.contact or "-"}\nPanel: /admin/news/bugreport/{report.pk}/change/')
        _mail(_owner_email(), f'spin.clinic · zgłoszenie: {report.text[:60]}', body, important=True)
    except Exception:  # noqa: BLE001
        pass


class JourneyThrottle(AnonRateThrottle):
    rate = '120/hour'


class JourneyInput(serializers.Serializer):
    steps = serializers.ListField(child=serializers.ListField(child=serializers.CharField(max_length=200), min_length=3, max_length=3),
                                  max_length=40)
    device = serializers.ChoiceField(choices=['phone', 'desktop'])


def record(steps, device, now=None):
    hour = (now or timezone.now()).replace(minute=0, second=0, microsecond=0)
    saved = 0
    for source, target, action in steps:
        source, target = clean_path(source), clean_path(target)
        if not source or not target or not ACTION.match(action):
            continue
        key = {'hour': hour, 'source': source, 'target': target, 'action': action, 'device': device}
        if not JourneyStep.objects.filter(**key).update(count=F('count') + 1):
            try:
                with transaction.atomic():
                    JourneyStep.objects.create(**key, count=1)
            except IntegrityError:
                JourneyStep.objects.filter(**key).update(count=F('count') + 1)
        saved += 1
    return saved


class JourneyView(APIView):
    """Przyjmuje paczkę kroków (sendBeacon przy wyjściu). Nie zapisuje nic poza licznikami."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [JourneyThrottle]

    def post(self, request):
        data = JourneyInput(data=request.data)
        if not data.is_valid():
            return Response(status=status.HTTP_204_NO_CONTENT)
        record(data.validated_data['steps'], data.validated_data['device'])
        return Response(status=status.HTTP_204_NO_CONTENT)
