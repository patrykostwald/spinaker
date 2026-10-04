"""Staff decisions only; no experiment execution."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from news.agent_models import AgentNote

FIELDS = ('id', 'agent', 'kind', 'track', 'title', 'body', 'sources', 'scores', 'score', 'critiques',
          'status', 'cost_usd', 'decided_at', 'created_at')


@never_cache
@api_view(['GET'])
@permission_classes([IsAdminUser])
def daily_schedule(request):
    from news.daily_schedule import snapshot
    from news.schedule_health import snapshot as health
    return Response({**snapshot(), 'health': health()})


@never_cache
@api_view(['GET'])
@permission_classes([IsAdminUser])
def agent_map(request):
    from news.agent_registry import snapshot
    from news.admin_status import local_times
    reports = list(AgentNote.objects.filter(kind='report').order_by('-created_at', '-pk').values(*FIELDS)[:5])
    return Response(local_times({'results': snapshot(), 'reports': reports}))


@never_cache
@api_view(['GET'])
@permission_classes([IsAdminUser])
def notes(request):
    agent, kind = request.query_params.get('agent', 'strateg'), request.query_params.get('kind', '')
    if agent not in ('strateg', 'pielgrzym', 'ekspert', 'recenzent', 'projektant', 'kartograf', 'zwiadowca', 'prawnik', 'dziennikarz', 'kontroler', 'architekt', 'wynalazca') or kind not in ('', 'signal', 'idea', 'finding', 'experiment', 'request', 'report', 'review', 'audit'):
        return Response({'detail': 'Nieprawidłowy filtr.'}, status=400)
    try:
        offset = max(0, int(request.query_params.get('offset', 0)))
    except ValueError:
        return Response({'detail': 'Nieprawidłowa strona.'}, status=400)
    rows = AgentNote.objects.filter(agent=agent)
    if kind:
        rows = rows.filter(kind=kind)
    from news.seba import visible, enabled
    results = list(visible(rows).values(*FIELDS)[offset:offset + 51])
    rejected = list(rows.filter(seba_review__status='rejected').values(*FIELDS)[offset:offset + 51]) if enabled() else []
    return Response({'results': results[:50], 'has_more': len(results) > 50 or len(rejected) > 50,
                     'rejected': rejected[:50], 'seba_queued': rows.filter(seba_review__status='queued').count() if enabled() else 0})


@never_cache
@api_view(['POST'])
@permission_classes([IsAdminUser])
def decide(request, note_id):
    with transaction.atomic():
        note = get_object_or_404(AgentNote.objects.select_for_update(), pk=note_id)
        action = request.data.get('decision')
        allowed = ('approved', 'denied') if note.kind == 'request' else ('accepted', 'rejected') if note.kind in ('idea', 'experiment') else ()
        if action not in allowed:
            return Response({'detail': 'Nieprawidłowa decyzja.'}, status=400)
        if note.status not in ('pending', 'new'):
            return Response({'detail': 'Ten wpis ma już decyzję.'}, status=409)
        from news.seba import can_show
        if not can_show(note):
            return Response({'detail': 'Propozycja nie przeszła oceny Seby.'}, status=409)
        note.status, note.decided_by, note.decided_at = action, request.user, timezone.now()
        note.save(update_fields=['status', 'decided_by', 'decided_at'])
    return Response({'id': note.pk, 'status': note.status})
