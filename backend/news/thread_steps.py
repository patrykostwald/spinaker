"""Ocena tropu krok po kroku (właściciel 3.10).

Czytelnik nie ocenia tropu w całości: przechodzi go i każdemu boksowi oraz każdemu powiązaniu (kontekstowi między
boksami) daje jedną z trzech reakcji ✓ ? ✕. Wynik tropu na głównej to średnia wszystkich reakcji jego kroków
(✓ = 1, ? = 0,5, ✕ = 0). Kto ocenił wszystkie kroki, ma też jedną ocenę całego tropu (z własnej średniej): z niej
korzystają dotychczasowe liczniki, sortowanie i izba przyjęć.
"""
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response

from news.community import item_data, public_threads
from news.community_models import CommunityThreadOpinion
from news.thread_social import SocialView, locked_account
from news.thread_social_models import ThreadStepReaction

WEIGHT = {'positive': 1.0, 'doubt': 0.5, 'negative': 0.0}


def steps_of(thread):
    """Kroki tropu w kolejności: boks, potem powiązanie prowadzące do następnego boksu."""
    out = []
    for item in thread.items.all():
        if item.link_id and item.link.hidden_at:
            continue
        if item.position and item.link_note:
            out.append((item.pk, 'context'))
        out.append((item.pk, 'box'))
    return out


def verdict(values):
    """Średnia reakcji -> jedna ocena: ✓ od 2/3, ✕ do 1/3, pomiędzy ?."""
    score = sum(WEIGHT[value] for value in values) / len(values)
    return 'positive' if score >= 2 / 3 else 'negative' if score <= 1 / 3 else 'doubt'


def score_of(thread_ids):
    """{thread_id: {'percent': 0-100, 'reactions': n}} ze wszystkich reakcji na kroki."""
    result = {}
    rows = (ThreadStepReaction.objects.filter(thread_id__in=thread_ids).values('thread_id')
            .annotate(n=Count('id'), p=Count('id', filter=Q(polarity='positive')), d=Count('id', filter=Q(polarity='doubt'))))
    for row in rows:
        result[row['thread_id']] = {'percent': round(100 * (row['p'] + 0.5 * row['d']) / row['n']) if row['n'] else 0,
                                    'reactions': row['n']}
    return result


def sync_opinion(thread, user):
    """Pełne przejście tropu daje jedną ocenę całości; niepełne jej nie daje."""
    steps = steps_of(thread)
    mine = dict(((r.item_id, r.part), r.polarity) for r in ThreadStepReaction.objects.filter(thread=thread, user=user))
    values = [mine[step] for step in steps if step in mine]
    if steps and len(values) == len(steps):
        CommunityThreadOpinion.objects.update_or_create(user=user, thread=thread, defaults={'polarity': verdict(values)})
    else:
        CommunityThreadOpinion.objects.filter(user=user, thread=thread).delete()


class StepInput(serializers.Serializer):
    item_id = serializers.IntegerField()
    part = serializers.ChoiceField(choices=['box', 'context'])
    polarity = serializers.ChoiceField(choices=['positive', 'doubt', 'negative'])


class ThreadStepsView(SocialView):
    def get(self, request, thread_id):
        thread = get_object_or_404(public_threads(request.user), pk=thread_id)
        steps = steps_of(thread)
        counts = {}
        for row in ThreadStepReaction.objects.filter(thread=thread).values('item_id', 'part', 'polarity').annotate(n=Count('id')):
            counts.setdefault((row['item_id'], row['part']), {'positive': 0, 'doubt': 0, 'negative': 0})[row['polarity']] = row['n']
        mine = {}
        if request.user.is_authenticated:
            mine = dict(((r.item_id, r.part), r.polarity) for r in ThreadStepReaction.objects.filter(thread=thread, user=request.user))
        return Response({
            'steps': [{'item_id': item_id, 'part': part, 'counts': counts.get((item_id, part), {'positive': 0, 'doubt': 0, 'negative': 0}),
                       'mine': mine.get((item_id, part))} for item_id, part in steps],
            'progress': {'done': sum(1 for step in steps if step in mine), 'total': len(steps)},
            'score': score_of([thread.pk]).get(thread.pk, {'percent': 0, 'reactions': 0}),
        })

    def post(self, request, thread_id):
        """Ponowne kliknięcie tej samej reakcji cofa ją."""
        thread = get_object_or_404(public_threads(request.user), pk=thread_id)
        data = StepInput(data=request.data)
        data.is_valid(raise_exception=True)
        item_id, part, polarity = (data.validated_data[key] for key in ('item_id', 'part', 'polarity'))
        if (item_id, part) not in steps_of(thread):
            raise serializers.ValidationError('Tego kroku nie ma w tym tropie.')
        with transaction.atomic():
            locked_account(request.user, 'rating')
            current = ThreadStepReaction.objects.filter(thread=thread, item_id=item_id, part=part, user=request.user).first()
            if current and current.polarity == polarity:
                current.delete()
            else:
                ThreadStepReaction.objects.update_or_create(thread=thread, item_id=item_id, part=part, user=request.user,
                                                            defaults={'polarity': polarity})
            sync_opinion(thread, request.user)
            from news.admission import check_admission
            check_admission(thread)
        return self.get(request, thread_id)


class ThreadBoxView(SocialView):
    """Boks z Bazy: źródło, reakcje w tym tropie, powiązania obok i te same materiały w innych tropach (sieć kontekstów)."""
    def get(self, request, thread_id, item_id):
        thread = get_object_or_404(public_threads(request.user), pk=thread_id)
        item = get_object_or_404(thread.items.all(), pk=item_id)
        items = [i for i in thread.items.all() if not (i.link_id and i.link.hidden_at)]
        index = next(n for n, i in enumerate(items) if i.pk == item.pk)
        after = items[index + 1] if index + 1 < len(items) else None
        same = Q()
        if item.article_id:
            same = Q(items__article_id=item.article_id)
        elif item.link_id:
            same = Q(items__link_id=item.link_id)
        elif (item.box_data or {}).get('diagnosis_id'):
            same = Q(items__box_data__diagnosis_id=item.box_data['diagnosis_id'])
        elif (item.box_data or {}).get('political_post_id'):
            same = Q(items__box_data__political_post_id=item.box_data['political_post_id'])
        others = list(public_threads(request.user).filter(same).exclude(pk=thread.pk).distinct()
                      .values('pk', 'title')[:6]) if same else []
        counts = {'positive': 0, 'doubt': 0, 'negative': 0}
        for row in ThreadStepReaction.objects.filter(thread=thread, item=item, part='box').values('polarity').annotate(n=Count('id')):
            counts[row['polarity']] = row['n']
        return Response({
            'item': item_data(item), 'position': index + 1, 'counts': counts,
            'context_before': item.link_note if item.position else '',
            'context_after': after.link_note if after else '',
            'other_threads': [{'id': row['pk'], 'title': row['title']} for row in others],
        })
