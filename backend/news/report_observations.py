"""Strict adapter for reviewed analysis. No network, inference, or raw source text."""
from collections import Counter

from django.core.exceptions import ValidationError

from news.report_models import ReportObservation


def rows(start, end, *, topic=None, figure_id=None):
    selected = ReportObservation.objects.filter(approved=True, verified_by__isnull=False,
        verified_at__isnull=False, day__gte=start, day__lt=end).select_related(
            'figure__parliamentary_roster_entry', 'diagnosis__post', 'ballot__voting__article')
    if topic:
        selected = selected.filter(topic=topic)
    if figure_id:
        selected = selected.filter(figure_id=figure_id)
    result = []
    for obj in selected.order_by('day', 'pk'):
        try:
            obj.full_clean()
        except ValidationError:
            continue
        if obj.diagnosis and (obj.diagnosis.status != 'approved' or obj.diagnosis.hidden_at
                              or obj.diagnosis.withdrawn_at or not obj.diagnosis.post.available):
            continue
        result.append({'id': f'observation:{obj.pk}', 'kind': obj.kind, 'date': str(obj.day),
            'topic': obj.topic, 'analysis': obj.analysis, 'url': obj.source_url,
            'corroborating_url': obj.corroborating_url, 'confidence': obj.confidence,
            'confidence_reason': obj.confidence_reason, 'figure_id': obj.figure_id,
            'diagnosis_id': obj.diagnosis_id, 'stance': obj.stance,
            'ballot_id': obj.ballot_id, 'vote': obj.ballot.vote if obj.ballot else '',
            'vote_url': obj.ballot.voting.article.url if obj.ballot else '',
            'supporting_vote': obj.supporting_vote})
    return result


def comparisons(observations):
    changes, alignment, last = [], [], {}
    for row in sorted((r for r in observations if r['kind'] == 'stance'), key=lambda r: (r['date'], r['id'])):
        key = (row['figure_id'], row['topic'])
        previous = last.get(key)
        if previous and previous['stance'] != row['stance'] and previous['date'] != row['date']:
            changes.append({'from_id': previous['id'], 'to_id': row['id'], 'topic': row['topic'],
                            'from': previous['stance'], 'to': row['stance'], 'date': row['date']})
        last[key] = row
        if row['ballot_id']:
            comparable = row['stance'] in ('support', 'oppose') and row['vote'] in ('YES', 'NO')
            matches = (row['vote'] == row['supporting_vote']) == (row['stance'] == 'support')
            alignment.append({'observation': row['id'], 'ballot': f"ballot:{row['ballot_id']}",
                              'result': ('consistent' if matches else 'different') if comparable else 'unassessed'})
    return {'position_changes': changes, 'vote_alignment': alignment,
            'alignment_counts': dict(Counter(r['result'] for r in alignment))}


def current(snapshot):
    from datetime import date, timedelta
    recorded = [r for r in snapshot['rows'] if r['id'].startswith('observation:')]
    if not recorded:
        return True
    first, last = min(r['date'] for r in recorded), max(r['date'] for r in recorded)
    fresh = {r['id']: r for r in rows(date.fromisoformat(first), date.fromisoformat(last) + timedelta(days=1))}
    return all(fresh.get(r['id']) == r for r in recorded)
