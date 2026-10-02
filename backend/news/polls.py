"""Szybkie głosowania (np. wybór formatu wpisu na X). Bez kont, bez maili, bez imion.

Jeden głos na przeglądarkę w każdym pytaniu (można zmienić). Z jednej sieci najwyżej
MAX_PER_NETWORK różnych głosujących, żeby czyszczenie przeglądarki nie mnożyło głosów.
"""
import hashlib
import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from news.poll_models import PollVote

POLLS = {
    'udostepnianie-x': {
        'x': [f'p{n:02d}' for n in range(1, 11)],
        'card': ['now', 'big'],
        'hook': ['score', 'brand', 'name'],
        'score': ['number', 'word'],
    },
}
MAX_PER_NETWORK = 6
VOTER = re.compile(r'^[0-9a-f]{32}$')


class PollThrottle(AnonRateThrottle):
    scope = 'poll'
    rate = '60/hour'


def network(request, poll):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
    ip = forwarded or request.META.get('REMOTE_ADDR', '')
    return hashlib.sha256(f'{settings.SECRET_KEY}:{poll}:{ip}'.encode()).hexdigest()[:32]


def results(poll, voter=''):
    questions = POLLS[poll]
    counts = {q: {o: 0 for o in options} for q, options in questions.items()}
    rows = PollVote.objects.filter(poll=poll).values_list('voter', 'answers')
    mine, total = {}, 0
    for who, answers in rows:
        total += 1
        for q, o in (answers or {}).items():
            if o in counts.get(q, {}):
                counts[q][o] += 1
        if who == voter:
            mine = answers
    return {'counts': counts, 'voters': total, 'mine': mine}


@api_view(['GET'])
@permission_classes([AllowAny])
def poll_results(request, slug):
    if slug not in POLLS:
        return Response({'detail': 'Nie ma takiego głosowania.'}, status=404)
    voter = str(request.query_params.get('voter', ''))
    return Response(results(slug, voter if VOTER.match(voter) else ''))


@api_view(['POST'])
@authentication_classes([])  # anonimowy głos: bez sesji, więc bez CSRF dla zalogowanych
@permission_classes([AllowAny])
@throttle_classes([PollThrottle])
def poll_vote(request, slug):
    if slug not in POLLS:
        return Response({'detail': 'Nie ma takiego głosowania.'}, status=404)
    voter, question, option = (str(request.data.get(k, '')) for k in ('voter', 'question', 'option'))
    if not VOTER.match(voter) or option not in POLLS[slug].get(question, []):
        return Response({'detail': 'Nieprawidłowy głos.'}, status=400)
    net = network(request, slug)
    now = timezone.now()
    with transaction.atomic():
        row = PollVote.objects.select_for_update().filter(poll=slug, voter=voter).first()
        if row is None:
            if PollVote.objects.filter(poll=slug, network=net).count() >= MAX_PER_NETWORK:
                return Response({'detail': 'Z tej sieci oddano już kilka głosów.'}, status=429)
            try:
                with transaction.atomic():
                    row = PollVote.objects.create(poll=slug, voter=voter, network=net, answers={})
            except IntegrityError:
                row = PollVote.objects.select_for_update().get(poll=slug, voter=voter)
        row.answers = {**row.answers, question: option}
        row.updated_at = now
        row.save(update_fields=['answers', 'updated_at'])
    return Response(results(slug, voter))
