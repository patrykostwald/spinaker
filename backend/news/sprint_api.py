"""Sprint tygodnia w panelu personelu: lista biletów budowy i decyzja jednym kliknięciem (bez wywołań modeli)."""
from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from news import sprint
from news.agent_models import BuildTicket

ORDER = {'proposed': 0, 'approved': 1, 'in_progress': 2, 'done': 3, 'dropped': 4}


@never_cache
@api_view(['GET'])
@permission_classes([IsAdminUser])
def tickets(request):
    since = timezone.now() - timedelta(days=7)
    rows = list(BuildTicket.objects.select_related('note').filter(status__in=BuildTicket.OPEN)) + list(
        BuildTicket.objects.select_related('note').filter(status='done', done_at__gte=since)[:10])
    rows.sort(key=lambda t: (ORDER[t.status], -t.rank, -t.pk))
    from news.dyrygent import CODEX_BACK
    return Response({'results': [sprint.row(t) for t in rows], 'codex_from': CODEX_BACK,
                     'open': sum(t.status in BuildTicket.OPEN for t in rows)})


@never_cache
@api_view(['POST'])
@permission_classes([IsAdminUser])
def decide(request, ticket_id):
    decision = request.data.get('decision')
    if decision not in ('approved', 'dropped'):
        return Response({'detail': 'Nieprawidłowa decyzja.'}, status=400)
    with transaction.atomic():
        ticket = get_object_or_404(BuildTicket.objects.select_for_update(), pk=ticket_id)
        allowed = ('proposed',) if decision == 'approved' else ('proposed', 'approved')
        if ticket.status not in allowed:
            return Response({'detail': 'Ten bilet ma już decyzję.'}, status=409)
        sprint.decide(ticket, decision, request.user)
    return Response(sprint.row(ticket))
