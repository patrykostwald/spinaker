"""Wspólne dopasowanie słowa do materiałów lokalnej Bazy."""
from django.db.models import Q

from news.models import Ballot, EvidenceLink


def article_token_query(token):
    """Tekst, nazwisko głosującego lub udokumentowane powiązanie redakcyjne."""
    return (Q(title__icontains=token) | Q(description__icontains=token)
            | Q(content__text__icontains=token)
            | Q(pk__in=Ballot.objects.filter(name__icontains=token).values('voting__article_id'))
            | Q(pk__in=EvidenceLink.objects.filter(phrase__icontains=token).values('article_id')))
