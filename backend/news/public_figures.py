"""Public, evidence-only profile API for the future politician view."""
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from news.models import ArticleCategory, Ballot
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
        'office': ({
            'id': role.public_office_id,
            'title': role.public_office.title,
            'official_roster_url': role.public_office.official_roster_url,
            'source_checked_at': role.public_office.source_checked_at,
        } if role.public_office_id else None),
        'role_category': role.role_category,
        'role_title': role.role_title,
        'organisation': role.organisation,
        'status': role.status,
        'official_profile_url': role.official_profile_url,
        'evidence_url': role.evidence_url,
        'source_checked_at': role.source_checked_at,
    } for role in figure.public_roles.filter(archived=False).select_related('public_office').order_by(
        'role_category', 'organisation', 'role_title')]
    data['votes'] = votes_data(figure)
    data['x_account'] = verified_x_account_data(figure)
    data['x_posts'] = verified_x_posts_data(figure)
    data['materials'] = materials_data(figure)
    return data


def confirmed_material_references(figure):
    return figure.article_references.filter(
        verification_status='confirmed', article__source__is_active=True,
    ).select_related('article__source').order_by('-article__published_date', '-pk')


def materials_data(figure):
    """Expose reviewed material links only; never infer a link from a name."""
    references = confirmed_material_references(figure)
    by_category = {key: 0 for key, _ in ArticleCategory.choices}
    by_reference_kind = {}
    results = []
    for reference in references[:100]:
        article = reference.article
        by_category[article.category] = by_category.get(article.category, 0) + 1
        by_reference_kind[reference.reference_kind] = by_reference_kind.get(reference.reference_kind, 0) + 1
        results.append({
            'id': article.pk,
            'title': article.title,
            'url': article.url,
            'source': article.source.name,
            'published_date': article.published_date,
            'category': article.category,
            'reference_kind': reference.reference_kind,
            'evidence_note': reference.evidence_note,
        })
    return {
        'available': bool(results),
        'count': references.count(),
        'by_category': {key: count for key, count in by_category.items() if count},
        'by_reference_kind': by_reference_kind,
        'results': results,
    }


def context_graph_data(figure):
    """A compact, evidence-first graph for the person-context view."""
    figure_node = f'person:{figure.pk}'
    nodes = [{'id': figure_node, 'type': 'public_figure', 'label': figure.canonical_name}]
    edges = []
    for role in figure.public_roles.filter(archived=False).select_related('public_office').order_by('role_title', 'pk'):
        node_id = f"office:{role.public_office_id}" if role.public_office_id else f'role:{role.pk}'
        if role.public_office_id:
            nodes.append({'id': node_id, 'type': 'public_office', 'label': role.public_office.title,
                          'organisation': role.public_office.organisation,
                          'url': role.public_office.official_roster_url})
        else:
            nodes.append({'id': node_id, 'type': 'role', 'label': role.role_title,
                          'organisation': role.organisation, 'status': role.status})
        edges.append({'from': figure_node, 'to': node_id, 'type': 'holds_public_office' if role.public_office_id else 'holds_role',
                      'evidence_url': role.evidence_url, 'source_checked_at': role.source_checked_at})
    for relation in figure.organisation_relations.filter(
        verification_status='confirmed', organisation__archived=False,
    ).select_related('organisation').order_by('organisation__name', 'pk'):
        node_id = f'organisation:{relation.organisation_id}'
        nodes.append({'id': node_id, 'type': 'organisation', 'label': relation.organisation.name,
                      'kind': relation.organisation.kind, 'url': relation.organisation.official_register_url})
        edges.append({'from': figure_node, 'to': node_id, 'type': 'confirmed_organisation_relation',
                      'label': relation.public_role, 'status': relation.relation_status,
                      'evidence_url': relation.evidence_url, 'verified_at': relation.verified_at})
    for reference in confirmed_material_references(figure)[:100]:
        article = reference.article
        node_id = f'article:{article.pk}'
        nodes.append({'id': node_id, 'type': 'article', 'label': article.title,
                      'category': article.category, 'source': article.source.name, 'url': article.url,
                      'published_date': article.published_date})
        edges.append({'from': figure_node, 'to': node_id, 'type': 'confirmed_material_reference',
                      'label': reference.reference_kind, 'evidence_note': reference.evidence_note})
    votes = votes_data(figure)
    for vote in votes['results']:
        node_id = f"vote:{vote['article_url']}"
        nodes.append({'id': node_id, 'type': 'vote', 'label': vote['topic'], 'date': vote['date'],
                      'vote': vote['vote'], 'url': vote['article_url']})
        edges.append({'from': figure_node, 'to': node_id, 'type': 'official_vote',
                      'evidence_url': vote['article_url']})
    account = verified_x_account_data(figure)
    if account:
        node_id = f"x:{account['handle'].lower()}"
        nodes.append({'id': node_id, 'type': 'x_account', 'label': '@' + account['handle'], 'url': account['url']})
        edges.append({'from': figure_node, 'to': node_id, 'type': 'confirmed_x_account',
                      'evidence_url': account['evidence_url']})
    gaps = []
    if not figure.organisation_relations.filter(verification_status='confirmed').exists():
        gaps.append('Brak potwierdzonych relacji z podmiotami w Bazie.')
    if not votes['available']:
        gaps.append('Brak potwierdzonego połączenia z mandatem poselskim i głosowaniami.')
    if not confirmed_material_references(figure).exists():
        gaps.append('Brak ręcznie potwierdzonych relacji z materiałami w Bazie.')
    if not account:
        gaps.append('Brak potwierdzonego konta X.')
    return {'nodes': nodes, 'edges': edges, 'gaps': gaps}


def dossier_data(figure):
    """Build the evidence-only input and display structure for Dr Spin.

    This remains useful with AI disabled.  A future single model call receives
    this bounded pack, not unrestricted database content, and may only explain
    or order the cited records.
    """
    details = figure_data(figure, include_detail=True)
    graph = context_graph_data(figure)
    materials = details['materials']
    timeline = [
        {
            'kind': 'material', 'date': row['published_date'], 'label': row['title'],
            'url': row['url'], 'evidence_url': row['url'],
        }
        for row in materials['results']
    ] + [
        {
            'kind': 'official_vote', 'date': row['date'], 'label': row['topic'],
            'vote': row['vote'], 'url': row['article_url'], 'evidence_url': row['article_url'],
        }
        for row in details['votes']['results']
    ]
    timeline.sort(key=lambda row: (row['date'] is None, row['date'] or ''), reverse=True)
    questions = []
    if details['organisations']:
        questions.append('Która udokumentowana rola przy podmiocie jest istotna dla badanego tematu i z jakiego okresu pochodzi?')
    if details['votes']['available']:
        questions.append('Które oficjalne głosowania dotyczą badanego zagadnienia, a które są tylko zbieżne tematycznie?')
    if materials['results']:
        questions.append('Które materiały są źródłami pierwotnymi, a które relacjami lub komentarzem?')
    if not questions:
        questions.append('Jakie urzędowe źródło lub materiał pierwotny byłby potrzebny, aby poszerzyć kontekst?')
    return {
        'status': 'evidence_pack_ready',
        'figure': figure_data(figure),
        'summary': {
            'current_role': figure.role_title,
            'public_offices': [role['office'] for role in details['roles'] if role['office']],
            'confirmed_organisations': len(details['organisations']),
            'confirmed_materials': materials['count'],
            'official_votes': len(details['votes']['results']),
            'confirmed_x_account': bool(details['x_account']),
        },
        'timeline': timeline[:30],
        'materials': materials,
        'organisations': details['organisations'],
        'roles': details['roles'],
        'votes': details['votes'],
        'graph': graph,
        'research_questions': questions,
        'gaps': graph['gaps'],
        'ai_output_contract': {
            'one_call': True,
            'sections': ['brief', 'reading_order', 'research_questions', 'known_gaps', 'what_could_change_the_picture'],
            'rule': 'Każdy punkt musi wskazać element tego pakietu przez URL; model nie może dodawać nowych faktów ani relacji.',
        },
        'notice': ('To jest pakiet dowodów z Bazy, nie ocena osoby ani potwierdzenie tezy. '
                   'AI może pomóc w kolejności lektury, ale nie może tworzyć faktów poza tym pakietem.'),
    }


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


@api_view(['GET'])
def public_figure_context(request, figure_id):
    figure = get_object_or_404(PublicFigure, pk=figure_id, archived=False)
    return Response({
        'figure': figure_data(figure),
        'materials': materials_data(figure),
        'graph': context_graph_data(figure),
        'notice': ('Krawędzie pokazują wyłącznie potwierdzone relacje i materiały. '
                   'Wspólny temat lub wystąpienie nazwiska nie tworzy relacji.'),
    })


@api_view(['GET'])
def public_figure_dossier(request, figure_id):
    figure = get_object_or_404(PublicFigure, pk=figure_id, archived=False)
    return Response(dossier_data(figure))
