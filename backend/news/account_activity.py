"""Panel konta: wszystkie reakcje i komentarze użytkownika w jednym miejscu (materiały, Dr. Spin, Klinika, Nitki)."""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from news.account_models import ArticleOpinion, ThreadOpinion
from news.accounts import AccountWriteThrottle
from news.clinic_models import SpinOpinion
from news.community_models import CommunityThreadOpinion
from news.schema import json_view

LIMIT = 100


def _row(kind, opinion, title, href):
    return {'kind': kind, 'id': opinion.pk, 'polarity': opinion.polarity, 'body': opinion.body,
            'created_at': opinion.created_at, 'target': {'title': title, 'href': href}}


@json_view('Moje reakcje i komentarze ze wszystkich części serwisu', tags=['konto'])
class MyReactionsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountWriteThrottle]

    def get(self, request):
        user = request.user
        rows = [
            *[_row('material', row, row.article.title, f'/material/{row.article_id}')
              for row in ArticleOpinion.objects.filter(user=user).select_related('article')[:LIMIT]],
            *[_row('drspin', row, row.thread.title, f'/thread/{row.thread.slug}')
              for row in ThreadOpinion.objects.filter(user=user).select_related('thread')[:LIMIT]],
            *[_row('clinic', row, row.diagnosis.headline or 'Diagnoza spinu', f'/klinika/{row.diagnosis_id}')
              for row in SpinOpinion.objects.filter(user=user).select_related('diagnosis')[:LIMIT]],
            *[_row('community', row, row.thread.title, f'/nitki/{row.thread_id}')
              for row in CommunityThreadOpinion.objects.filter(user=user).select_related('thread')[:LIMIT]],
        ]
        rows.sort(key=lambda row: row['created_at'], reverse=True)
        counts = {kind: sum(1 for row in rows if row['kind'] == kind) for kind in ('material', 'drspin', 'clinic', 'community')}
        return Response({'results': rows[:LIMIT], 'counts': counts,
                         'comments': sum(1 for row in rows if row['body'])})
