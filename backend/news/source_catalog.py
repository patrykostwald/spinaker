"""Editorial source configuration. This catalog never mutates collected publications."""
import csv
import io
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Min
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from news.models import Source, SourceType, ArchiveJob, ImportState


def domain_key(value):
    return (urlsplit(value or '').hostname or '').lower().removeprefix('www.')


def public_catalog_url(value, *, resolve=True):
    """Validate a public HTTP address without fetching content or trusting its metadata."""
    value = (value or '').strip()
    if not value:
        return ''
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or '').encode('idna').decode('ascii').lower()
        port = parsed.port
    except (ValueError, UnicodeError):
        raise serializers.ValidationError('Nieprawidłowy adres URL.')
    if (parsed.scheme not in ('http', 'https') or not host or parsed.username is not None
            or parsed.password is not None or len(value) > 4096 or any(c.isspace() for c in value)):
        raise serializers.ValidationError('Podaj publiczny adres http lub https bez danych logowania.')
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal', '.invalid', '.test', '.onion')):
        raise serializers.ValidationError('Adres lokalny lub prywatny nie jest źródłem publicznym.')
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        if '.' not in host:
            raise serializers.ValidationError('Podaj pełną publiczną domenę.')
    else:
        if not literal.is_global:
            raise serializers.ValidationError('Adres lokalny lub prywatny nie jest źródłem publicznym.')
    if resolve:
        try:
            addresses = socket.getaddrinfo(host, port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
        except (OSError, UnicodeError):
            raise serializers.ValidationError('Nie potwierdzono publicznego adresu domeny. Sprawdź adres lub zachowaj kandydata bez URL.')
        if not addresses or any(not ipaddress.ip_address(entry[4][0]).is_global for entry in addresses):
            raise serializers.ValidationError('Domena wskazuje na adres prywatny lub niedostępny publicznie.')
    netloc = f'[{host}]' if ':' in host else host
    if port is not None:
        netloc += f':{port}'
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, ''))


class SourceCatalogSerializer(serializers.ModelSerializer):
    url = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=4096)
    rss_url = serializers.CharField(required=False, allow_blank=True, max_length=4096)
    scrape_frequency_minutes = serializers.IntegerField(min_value=1, max_value=2147483647, required=False)
    catalog_notes = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    article_count = serializers.IntegerField(read_only=True)
    oldest_publication = serializers.DateTimeField(read_only=True)
    newest_publication = serializers.DateTimeField(read_only=True)
    archive_status = serializers.SerializerMethodField()
    access_check = serializers.SerializerMethodField()

    class Meta:
        model = Source
        fields = ('id', 'name', 'url', 'source_type', 'rss_url', 'is_active', 'scrape_enabled',
                  'scrape_frequency_minutes', 'catalog_notes', 'catalog_stage', 'article_count',
                  'last_scraped', 'last_attempted', 'last_error', 'archive_status',
                  'oldest_publication', 'newest_publication', 'access_check')
        read_only_fields = ('id', 'last_scraped', 'last_attempted', 'last_error')

    def get_archive_status(self, obj):
        return self.context.get('archive_statuses', {}).get(obj.pk, {
            'pending': 0, 'running': 0, 'error': 0, 'done': 0, 'last_checked': None})

    def get_access_check(self, obj):
        check = self.context.get('access_checks', {}).get(obj.pk)
        if not check:
            return None
        return {**check, 'configuration_changed':
            (check.get('source_url') or '') != (obj.url or '') or
            (check.get('configured_rss_url') or '') != (obj.rss_url or '')}

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['url'] = data['url'] or ''
        return data

    def validate(self, attrs):
        if self.instance is None:
            attrs.setdefault('catalog_stage', 'candidate')
            attrs.setdefault('is_active', False)
            attrs.setdefault('scrape_enabled', False)
            attrs.setdefault('url', None)
        activating = (attrs.get('is_active') is True or attrs.get('scrape_enabled') is True
                      or (attrs.get('catalog_stage') == 'configured'
                          and self.instance is not None and self.instance.catalog_stage != 'configured'))
        if activating and self.instance:
            for field in ('url', 'rss_url'):
                attrs.setdefault(field, getattr(self.instance, field))
        for field in ('url', 'rss_url'):
            if field in attrs:
                previous = getattr(self.instance, field, None) if self.instance else None
                if activating or (attrs[field] or '') != (previous or ''):
                    try:
                        attrs[field] = public_catalog_url(attrs[field])
                    except serializers.ValidationError as exc:
                        raise serializers.ValidationError({field: exc.detail})
                if field == 'url' and not attrs[field]:
                    attrs[field] = None
        if attrs.get('url'):
            duplicates = Source.objects.filter(url=attrs['url'])
            if self.instance:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError({'url': 'Ten adres jest już w katalogu.'})
        values = {field.name: getattr(self.instance, field.name) for field in Source._meta.fields} if self.instance else {}
        values.update(attrs)
        candidate = Source(**values)
        try:
            candidate.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs


def catalog_queryset():
    return Source.objects.annotate(article_count=Count('articles'),
        oldest_publication=Min('articles__published_date'), newest_publication=Max('articles__published_date')).order_by('name', 'pk')


def access_checks():
    result = {}
    for state in ImportState.objects.filter(name__startswith='source-check:').only('name', 'cursor'):
        suffix = state.name.removeprefix('source-check:')
        if suffix.isdecimal() and isinstance(state.cursor, dict):
            result[int(suffix)] = state.cursor
    return result


def archive_statuses(source_ids=None):
    jobs = ArchiveJob.objects.all()
    if source_ids is not None:
        jobs = jobs.filter(source_id__in=source_ids)
    statuses = {}
    for row in jobs.values('source_id', 'status').annotate(count=Count('id'), last_checked=Max('checked_at')):
        item = statuses.setdefault(row['source_id'], {'pending': 0, 'running': 0, 'error': 0, 'done': 0, 'last_checked': None})
        item[row['status']] = row['count']
        if row['last_checked'] and (item['last_checked'] is None or row['last_checked'] > item['last_checked']):
            item['last_checked'] = row['last_checked']
    return statuses


def serialize_source(source_id):
    return SourceCatalogSerializer(catalog_queryset().get(pk=source_id),
        context={'archive_statuses': archive_statuses([source_id]), 'access_checks': access_checks()}).data


class CatalogAccess(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = [SessionAuthentication]


class SourceCatalogList(CatalogAccess):
    def get(self, request):
        data = SourceCatalogSerializer(catalog_queryset(), many=True,
            context={'archive_statuses': archive_statuses(), 'access_checks': access_checks()}).data
        return Response({'sources': data,
            'source_types': [{'value': value, 'label': label} for value, label in SourceType.choices]})

    def post(self, request):
        serializer = SourceCatalogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                source = serializer.save()
        except IntegrityError:
            return Response({'url': ['Ten adres jest już w katalogu.']}, status=400)
        return Response(serialize_source(source.pk), status=201)


class SourceCatalogDetail(CatalogAccess):
    def patch(self, request, source_id):
        source = get_object_or_404(Source, pk=source_id)
        serializer = SourceCatalogSerializer(source, data=request.data, partial=True)
        # DNS checks happen before the write transaction so network latency never holds SQLite's writer lock.
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                source = get_object_or_404(Source.objects.select_for_update(), pk=source_id)
                for field, value in serializer.validated_data.items():
                    setattr(source, field, value)
                try:
                    source.clean()
                except DjangoValidationError as exc:
                    raise serializers.ValidationError(exc.message_dict)
                serializer.instance = source
                serializer.save()
        except IntegrityError:
            return Response({'url': ['Ten adres jest już w katalogu.']}, status=400)
        return Response(serialize_source(source_id))


def csv_cell(value):
    value = '' if value is None else str(value)
    # Prevent a spreadsheet from evaluating editor-supplied cells as formulas.
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r')) else value


class SourceCatalogExport(CatalogAccess):
    def get(self, request):
        buffer = io.StringIO(newline='')
        fields = ['id', 'name', 'url', 'source_type', 'rss_url', 'is_active', 'scrape_enabled',
                  'scrape_frequency_minutes', 'catalog_stage', 'catalog_notes', 'article_count',
                  'last_scraped', 'last_attempted', 'last_error', 'archive_pending', 'archive_running',
                  'archive_error', 'archive_done', 'archive_last_checked', 'oldest_publication', 'newest_publication',
                  'access_checked_at', 'rss_check_status', 'rss_found_url', 'archive_method',
                  'sitemap_urls', 'listing_urls', 'access_recommendation', 'check_configuration_changed']
        writer = csv.DictWriter(buffer, fieldnames=fields, delimiter=';')
        writer.writeheader()
        rows = SourceCatalogSerializer(catalog_queryset(), many=True,
            context={'archive_statuses': archive_statuses(), 'access_checks': access_checks()}).data
        for data in rows:
            status = data.pop('archive_status')
            data.update({'archive_' + key: status.get(key) for key in ('pending', 'running', 'error', 'done', 'last_checked')})
            check = data.pop('access_check') or {}
            rss, archive = check.get('rss', {}), check.get('archive', {})
            data.update(access_checked_at=check.get('checked_at'), rss_check_status=rss.get('status'),
                rss_found_url=rss.get('url'), archive_method=archive.get('status'),
                sitemap_urls='\n'.join(archive.get('sitemap_urls', [])),
                listing_urls='\n'.join(archive.get('listing_urls', [])),
                access_recommendation=check.get('recommendation'), check_configuration_changed=check.get('configuration_changed'))
            writer.writerow({field: csv_cell(data.get(field)) for field in fields})
        response = HttpResponse(buffer.getvalue().encode('utf-8-sig'), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="katalog-zrodel.csv"'
        response['Cache-Control'] = 'private, no-store'
        return response
