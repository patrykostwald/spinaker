"""Publiczne API danych z Rządowego Procesu Legislacyjnego (legislacja.rcl.gov.pl), tylko do odczytu.

Każdy rekord niesie blok ``source``: "Źródło: Rządowe Centrum Legislacji, legislacja.rcl.gov.pl", link do strony w RCL,
datę pobrania i informację o przetworzeniu (warunki RCL z pisma RCL.DPK.053.168.2026).  Do czasu włączenia
RCL_API_ENABLED=true (po ocenie Prawnika) interfejs odpowiada 404.
"""
import os

from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from news.models import LegislativeChange, LegislativeDocument, LegislativeProject
from scraper.rcl_guard import PROCESSING_NOTE, RCL_BASE_URL, SOURCE_LINE

CHANGE_LIMIT = 100


def api_enabled():
    return os.environ.get('RCL_API_ENABLED', '').strip().lower() in ('1', 'true', 'yes', 'on')


def _iso(value):
    return value.isoformat() if value else None


def source_block(url, fetched_at):
    return {'attribution': SOURCE_LINE, 'url': url, 'fetched_at': _iso(fetched_at), 'processing': PROCESSING_NOTE}


def project_card(project):
    return {
        'id': project.rcl_id,
        'title': project.title,
        'act_type': project.act_type,
        'act_type_id': project.act_type_id,
        'applicant': project.applicant,
        'wykaz_number': project.wykaz_number,
        'status': project.status,
        'created_on': _iso(project.created_on),
        'modified_on': _iso(project.list_modified_on),
        'source': source_block(project.source_url or LegislativeProject.url_for(project.rcl_id),
                               project.fetched_at or project.list_fetched_at),
    }


def document_card(doc):
    return {
        'id': doc.rcl_doc_id,
        'name': doc.name,
        'category': doc.category,
        'category_note': 'Kategoria wynika z nazwy folderu i pliku (heurystyka), nie z oceny treści.',
        'author': doc.author,
        'created_on': _iso(doc.created_on),
        'folder': doc.folder_name,
        'file_url': doc.file_url,
        'removed_from_source_at': _iso(doc.removed_at),
        'source': source_block(doc.source_page_url, doc.fetched_at),
    }


def _disabled():
    return Response({'detail': 'Dane z Rządowego Procesu Legislacyjnego nie są jeszcze udostępniane.'}, status=404)


@extend_schema(summary='Projekty z Rządowego Procesu Legislacyjnego', tags=['legislacja'], responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def project_list(request):
    if not api_enabled():
        return _disabled()
    try:
        page = max(1, int(request.query_params.get('page', '1')))
        page_size = min(100, max(1, int(request.query_params.get('page_size', '50'))))
        type_id = request.query_params.get('typ', '').strip()
        type_id = int(type_id) if type_id else None
    except ValueError:
        return Response({'detail': 'Parametry page, page_size i typ muszą być liczbami całkowitymi.'}, status=400)
    rows = LegislativeProject.objects.all()
    query = request.query_params.get('q', '').strip()
    if query:
        rows = rows.filter(Q(title__icontains=query) | Q(wykaz_number__iexact=query.replace(' ', '')))
    applicant = request.query_params.get('organ', '').strip()
    if applicant:
        rows = rows.filter(applicant__icontains=applicant)
    if type_id is not None:
        rows = rows.filter(act_type_id=type_id)
    count = rows.count()
    start = (page - 1) * page_size
    return Response({
        'count': count, 'page': page, 'page_size': page_size,
        'source': {'attribution': SOURCE_LINE, 'url': RCL_BASE_URL + '/lista', 'processing': PROCESSING_NOTE},
        'results': [project_card(p) for p in rows.order_by('-list_modified_on', '-rcl_id')[start:start + page_size]],
    })


@extend_schema(summary='Projekt z etapami, dokumentami, uwagami i zgłoszeniami lobbingowymi', tags=['legislacja'],
               responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
def project_detail(request, rcl_id):
    if not api_enabled():
        return _disabled()
    project = LegislativeProject.objects.filter(rcl_id=rcl_id).first()
    if project is None:
        return Response({'detail': 'Brak w naszych danych (projekt nie został jeszcze pobrany z RCL).'}, status=404)
    docs = list(LegislativeDocument.objects.filter(project=project).order_by('-created_on', '-rcl_doc_id'))
    Category = LegislativeDocument.Category
    by = lambda *cats: [document_card(d) for d in docs if d.category in cats]  # noqa: E731
    card = project_card(project)
    card.update({
        'departments': project.departments, 'keywords': project.keywords, 'term': project.term,
        'wykaz_name': project.wykaz_name, 'wykaz_url': project.wykaz_url,
        'rm_number': project.rm_number, 'sejm_url': project.sejm_url, 'notes': project.notes,
        'stages': [{
            'id': s.rcl_id, 'number': s.number, 'name': s.name, 'kind': s.kind, 'state': s.state,
            'modified_on': _iso(s.modified_on), 'catalog_url': s.catalog_url,
            'catalog_fetched_at': _iso(s.catalog_fetched_at)} for s in project.stages.order_by('number', 'rcl_id')],
        'documents': by(Category.PROJECT, Category.JUSTIFICATION, Category.OSR, Category.COVER_LETTER, Category.OTHER),
        'consultation_positions': by(Category.POSITION),
        'comment_tables': by(Category.COMMENT_TABLE),
        'lobbying_notifications': by(Category.LOBBYING),
        'changes': [{
            'entity': c.entity, 'key': c.entity_key, 'kind': c.kind, 'changes': c.changes,
            'detected_at': _iso(c.detected_at), 'fetched_at': _iso(c.fetched_at)
        } for c in LegislativeChange.objects.filter(project=project)[:CHANGE_LIMIT]],
        'completeness': {
            'details_fetched_at': _iso(project.fetched_at),
            'waiting_for_refresh': project.needs_refresh,
            'note': 'Zakres: dane pobrane z RCL do daty fetched_at; brak pozycji oznacza brak w naszych danych na ten dzień, nie brak w RCL.'},
    })
    return Response(card)
