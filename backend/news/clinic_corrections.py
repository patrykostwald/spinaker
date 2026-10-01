"""Publiczny rejestr: paginacja zdarzeń w bazie, autorzy pobierani jedną partią."""
from django.db.models import CharField, Count, F, Q, Value
from django.db.models.functions import Substr
from django.utils import timezone

from news import clinic
from news.clinic_models import ClinicAuthorReply, SpinDiagnosis


def withdrawn_data(diagnosis):
    post = diagnosis.post
    figures = clinic.figures_by_account([post.account_id])
    return {
        'id': diagnosis.pk, 'status': 'withdrawn', 'withdrawn_at': diagnosis.withdrawn_at,
        'withdrawn_reason': diagnosis.withdrawn_reason,
        'author': clinic.author_data(post, figures.get(post.account_id)),
        'camp': post.camp_at_collection, 'camp_label': clinic.CAMP_LABELS.get(post.camp_at_collection, ''),
        'post': {'url': post.url, 'published_at': post.published_at},
        'author_replies': list(diagnosis.author_replies.filter(published_at__lte=timezone.now()).values(
            'id', 'body', 'source_url', 'received_at', 'published_at')),
    }


def corrections_data(page=1):
    diagnoses = SpinDiagnosis.objects.all()
    replies = ClinicAuthorReply.objects.filter(published_at__lte=timezone.now()).filter(
        Q(diagnosis__status='approved') | Q(diagnosis__withdrawn_at__isnull=False))
    counts = diagnoses.aggregate(
        published=Count('pk', filter=Q(status='approved') | Q(withdrawn_at__isnull=False) | Q(hidden_at__isnull=False)),
        withdrawn=Count('pk', filter=Q(withdrawn_at__isnull=False)),
        hidden=Count('pk', filter=Q(hidden_at__isnull=False)),
    )
    counts['replies'] = replies.count()
    # Wszystkie kolumny są aliasami: Django 5.1 ustawia pola modelu przed adnotacjami w UNION.
    fields = ('event_id', 'target_id', 'type', 'date', 'reason', 'reply_excerpt')
    empty = Value('', output_field=CharField())
    withdrawals = diagnoses.filter(withdrawn_at__isnull=False).order_by().annotate(
        event_id=F('pk'), target_id=F('pk'), type=Value('withdrawal'), date=F('withdrawn_at'),
        reason=F('withdrawn_reason'), reply_excerpt=empty).values(*fields)
    hidden = diagnoses.filter(hidden_at__isnull=False).order_by().annotate(
        event_id=F('pk'), target_id=F('pk'), type=Value('hiding'), date=F('hidden_at'),
        reason=empty, reply_excerpt=empty).values(*fields)
    answers = replies.order_by().annotate(event_id=F('pk'), target_id=F('diagnosis_id'), type=Value('author_reply'), date=F('published_at'),
                                         reason=empty, reply_excerpt=Substr('body', 1, 280)).values(*fields)
    events = withdrawals.union(hidden, answers, all=True).order_by('-date', '-type', '-event_id')
    batch = list(events[(page - 1) * 20:page * 20 + 1])
    rows = diagnoses.select_related('post__account').in_bulk({item['target_id'] for item in batch[:20]})
    figures = clinic.figures_by_account({row.post.account_id for row in rows.values() if not row.hidden_at})
    result = []
    for item in batch[:20]:
        diagnosis = rows[item.pop('target_id')]
        item['id'] = f"{item['type']}:{item.pop('event_id')}"
        if diagnosis.hidden_at:
            # Dotyczy także wcześniejszego wycofania/odpowiedzi: bez danych osobowych ani fragmentów treści.
            item.update(author=None, camp=None, camp_label=None, post_date=None, diagnosis_url=None,
                        reason='', reply_excerpt='', notice='Ukryto po zgłoszeniu prawnym')
        else:
            post = diagnosis.post
            item.update(author=clinic.author_data(post, figures.get(post.account_id)), camp=post.camp_at_collection,
                        camp_label=clinic.CAMP_LABELS.get(post.camp_at_collection, ''), post_date=post.published_at,
                        diagnosis_url=f'/klinika/{diagnosis.pk}')
        result.append(item)
    return {'results': result, 'counts': counts, 'count': counts['withdrawn'] + counts['hidden'] + counts['replies'],
            'next_page': page + 1 if len(batch) > 20 else None}
