"""Schemat OpenAPI (drf-spectacular) zawiera wszystkie trasy spina3 bez błędów generowania."""
from __future__ import annotations

import pytest
from drf_spectacular.generators import SchemaGenerator

pytestmark = pytest.mark.django_db

EXPECTED = ['/api/spina3/wall/', '/api/spina3/facets/', '/api/spina3/boxes/search/', '/api/spina3/box/{box_id}/',
            '/api/spina3/box/{box_id}/related/', '/api/spina3/boxes/', '/api/spina3/pin/{pin_id}/',
            '/api/spina3/pin/{pin_id}/rating/', '/api/spina3/box/{box_id}/comments/', '/api/spina3/comment/{comment_id}/',
            '/api/spina3/comment/{comment_id}/helpful/', '/api/spina3/me/boxes/', '/api/spina3/me/ratings/', '/api/spina3/me/profile/', '/api/spina3/report/', '/api/spina3/config/', '/api/spina3/moderation/queue/',
            '/api/spina3/auth/exchange/']


def test_schema_contains_spina3_paths():
    schema = SchemaGenerator(urlconf='config.urls').get_schema(request=None, public=True)
    paths = schema['paths']
    for path in EXPECTED:
        assert path in paths, path
    assert '/api/spina3/box/{box_id}/pin/' not in paths and '/api/spina3/me/pins/' not in paths   # v1 usunięte
    assert 'post' in paths['/api/spina3/boxes/']
    assert 'put' in paths['/api/spina3/pin/{pin_id}/rating/'] and 'delete' in paths['/api/spina3/pin/{pin_id}/rating/']
    assert 'get' in paths['/api/spina3/box/{box_id}/comments/'] and 'post' in paths['/api/spina3/box/{box_id}/comments/']
    assert 'patch' in paths['/api/spina3/pin/{pin_id}/'] and 'delete' in paths['/api/spina3/pin/{pin_id}/']
    body = paths['/api/spina3/boxes/']['post']['requestBody']['content']['application/json']['schema']
    assert 'BoxWithPinIn' in body.get('$ref', '')
    components = schema['components']['schemas']
    kind = components['PinSpecInRequest']['properties']['kind']
    ref = (kind.get('$ref') or kind.get('allOf', [{}])[0].get('$ref', '')).rsplit('/', 1)[-1]
    assert 'image' in components[ref]['enum']   # typ "image" zarezerwowany w kontrakcie, wyłączony flagą
    assert 'spin' not in components['NickColorEnum']['enum']   # kolor Dr. Spina poza listą użytkownika


def test_schema_endpoint_served(api):
    response = api.get('/api/schema/?format=json')
    assert response.status_code == 200
    assert '/api/spina3/wall/' in response.content.decode()
