"""Staff-only evidence and audited owner decisions; no API/model calls in HTTP views."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from news.political_models import PoliticalAccount, WardenReview


@never_cache
@api_view(['GET'])
@permission_classes([IsAdminUser])
def reviews(request):
    try:
        offset = max(0, int(request.query_params.get('offset', 0)))
    except ValueError:
        return Response({'detail': 'Nieprawidłowa strona.'}, status=400)
    rows = WardenReview.objects.filter(status__in=['pending', 'owner']).select_related('account', 'seba_review').order_by('created_at')
    result = []
    for row in rows[offset:offset + 51]:
        seba = getattr(row, 'seba_review', None)
        result.append({'id': row.pk, 'handle': row.account.handle, 'status': row.status, 'reason': row.reason,
            'first_decision': row.first_decision, 'second_decision': row.second_decision,
            'evidence': row.evidence, 'second_evidence': row.second_evidence,
            'created_at': row.created_at, 'due_at': row.due_at, 'last_error': row.last_error,
            'seba': seba.critiques if seba else [], 'seba_waiting': bool(seba and seba.status == 'queued')})
    return Response({'results': result[:50], 'has_more': len(result) > 50})


@never_cache
@api_view(['POST'])
@permission_classes([IsAdminUser])
def decide(request, review_id):
    action = request.data.get('decision')
    if action not in ('disable', 'keep'):
        return Response({'detail': 'Nieprawidłowa decyzja.'}, status=400)
    with transaction.atomic():
        review = get_object_or_404(WardenReview.objects.select_for_update(), pk=review_id)
        account = PoliticalAccount.objects.select_for_update().get(pk=review.account_id)
        if review.status != 'owner':
            return Response({'detail': 'Wniosek nie czeka na decyzję właściciela.'}, status=409)
        if review.fingerprint != account.identity_fingerprint():
            review.status = 'superseded'
            review.save(update_fields=['status'])
            return Response({'detail': 'Dane konta się zmieniły. Potrzebny nowy wniosek.'}, status=409)
        account.enabled = action == 'keep'
        account.last_error = '' if account.enabled else ('warden-owner: ' + review.reason)[:120]
        account.save(update_fields=['enabled', 'last_error'])
        review.status = 'kept' if action == 'keep' else 'disabled'
        review.decided_by, review.decided_at = request.user, timezone.now()
        review.save(update_fields=['status', 'decided_by', 'decided_at'])
    return Response({'id': review.pk, 'status': review.status})
