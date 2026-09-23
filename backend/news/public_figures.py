"""Public, evidence-only profile API for the future politician view."""
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from news.models import Ballot
from news.political_models import PoliticalPost, PublicFigure, SocialHandleEvidence


def figure_data(figure, include_detail=False):
    data = {
        'id': figure.pk,
        'name': figure.canonical_name,
        'role_category': figure.role_category,
        'role_title': figure.role_title,
        'organisation': figure.organisation,
        'status': figure.status,
        'official_profile_url': figure.official_profile_url,
        'evidence_url': figure.evidence_url,
        'source_checked_at': figure.source_checked_at,
    }
    if not include_detail:
        return data
    relations = figure.organisation_relations.filter(
        verification_status='confirmed', organisation__archived=False,
    ).select_related('organisation').order_by('organisation__kind', 'organisation__name')
    data['organisations'] = [{
        'id': relation.organisation_id,
        'name': relation.organisation.name,
        'krs_number': relation.organisation.krs_number,
        'kind': relation.organisation.kind,
        'official_register_url': relation.organisation.official_register_url,
        'public_role': relation.public_role,
        'relation_status': relation.relation_status,
        'evidence_url': relation.evidence_url,
        'verified_at': relation.verified_at,
    } for relation in relations]
    data['roles'] = [{
        'role_category': role.role_category,
        'role_title': role.role_title,
        'organisation': role.organisation,
        'status': role.status,
        'official_profile_url': role.official_profile_url,
        'evidence_url': role.evidence_url,
        'source_checked_at': role.source_checked_at,
    } for role in figure.public_roles.filter(archived=False).order_by(
        'role_category', 'organisation', 'role_title')]
    data['votes'] = votes_data(figure)
    data['x_account'] = verified_x_account_data(figure)
    data['x_posts'] = verified_x_posts_data(figure)
    return data


def verified_x_account_record(figure):
    """Return the account and its public evidence only after two confirmations.

    A public link on an official roster page alone remains editorial evidence.
    The record is intentionally internal: public serializers expose only the
    minimal account/post fields below.
    """
    evidence_filters = Q(
        subject_content_type=ContentType.objects.get_for_model(PublicFigure),
        subject_object_id=figure.pk,
    )
    if figure.parliamentary_roster_entry_id:
        evidence_filters |= Q(roster_entry_id=figure.parliamentary_roster_entry_id)
    evidence = SocialHandleEvidence.objects.filter(
        evidence_filters,
        platform='x',
        status='candidate_created',
        candidate__resolved_account__isnull=False,
    ).select_related('candidate__resolved_account__confirmed_by').order_by('-reviewed_at', '-pk').first()
    if not evidence or not evidence.candidate.resolved_account.is_confirmed():
        return None
    return evidence.candidate.resolved_account, evidence


def verified_x_account_data(figure):
    """Public account details, never guessed from a name or handle."""
    record = verified_x_account_record(figure)
    if record is None:
        return None
    account, evidence = record
    return {
        'handle': account.handle,
        'url': f'https://x.com/{account.handle}',
        'evidence_url': evidence.evidence_url,
        'posts_collected': PoliticalPost.objects.filter(account=account, available=True).count(),
    }


def verified_x_posts_data(figure):
    """Stored posts from the same confirmed X account; no keyword matching."""
    record = verified_x_account_record(figure)
    if record is None:
        return {'available': False, 'results': []}
    account, _ = record
    posts = PoliticalPost.objects.filter(account=account, available=True).order_by('-published_at', '-pk')[:100]
    return {'available': True, 'results': [{
        'id': post.pk,
        'post_id': post.post_id,
        'url': post.url,
        'text': post.text,
        'published_at': post.published_at,
        'likes_count': post.source_data.get('public_metrics', {}).get('like_count', 0),
        'reposts_count': post.source_data.get('public_metrics', {}).get('retweet_count', 0),
    } for post in posts]}


def votes_data(figure):
    entry = figure.parliamentary_roster_entry
    if not entry or entry.source != 'sejm' or not str(entry.external_id).isdigit() or not entry.term:
        return {'available': False, 'reason': 'Brak ręcznie potwierdzonego połączenia z mandatem poselskim.', 'results': []}
    ballots = Ballot.objects.filter(
        mp_id=int(entry.external_id), voting__term=entry.term,
    ).select_related('voting__article').order_by(
        '-voting__article__published_date', '-pk')[:30]
    return {'available': True, 'source_url': entry.profile_url, 'results': [{
        'date': ballot.voting.article.published_date,
        'topic': ballot.voting.motion,
        'vote': ballot.vote,
        'article_url': ballot.voting.article.url,
        'source': 'Sejm RP',
    } for ballot in ballots]}


@api_view(['GET'])
def public_figure_list(request):
    query = request.query_params.get('q', '').strip()
    role_category = request.query_params.get('role_category', '').strip()
    status = request.query_params.get('status', '').strip()
    try:
        page = max(1, int(request.query_params.get('page', '1')))
        page_size = min(100, max(1, int(request.query_params.get('page_size', '50'))))
    except ValueError:
        return Response({'detail': 'Parametry page i page_size muszą być liczbami całkowitymi.'}, status=400)
    rows = PublicFigure.objects.filter(archived=False)
    if query:
        rows = rows.filter(Q(canonical_name__icontains=query) | Q(role_title__icontains=query) |
                           Q(organisation__icontains=query))
    if role_category:
        rows = rows.filter(role_category=role_category)
    if status:
        rows = rows.filter(status=status)
    rows = rows.order_by('canonical_name', 'pk')
    count = rows.count()
    start = (page - 1) * page_size
    return Response({
        'count': count,
        'page': page,
        'page_size': page_size,
        'results': [figure_data(row) for row in rows[start:start + page_size]],
    })


@api_view(['GET'])
def public_figure_detail(request, figure_id):
    figure = get_object_or_404(PublicFigure, pk=figure_id, archived=False)
    return Response(figure_data(figure, include_detail=True))
