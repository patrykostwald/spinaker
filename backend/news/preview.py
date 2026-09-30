"""Secret-link preview. The readable cookie is never backend authorization."""
import hashlib
import hmac
from django.conf import settings
from django.core import signing
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_GET
from rest_framework.throttling import SimpleRateThrottle
from news.features import preview_active

MAX_AGE = 30 * 24 * 60 * 60
SALT = 'news.phase2.preview.v1'


def key_digest():
    return hashlib.sha256(settings.PREVIEW_KEY.encode()).hexdigest()


def valid_preview(cookie):
    if not settings.PREVIEW_KEY or not cookie:
        return False
    try:
        digest = signing.loads(cookie, salt=SALT, max_age=MAX_AGE)
        return isinstance(digest, str) and hmac.compare_digest(digest, key_digest())
    except (signing.BadSignature, ValueError, TypeError):
        return False


def mail_preview_kwargs():
    # Transactional verification / recovery must survive the request boundary.
    # No request context is propagated to bulk mail or push workers.
    if preview_active.get():
        return {'kwargs': {'preview_grant': signing.dumps(key_digest(), salt=SALT)}}
    return {}


class PreviewMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Remove the secret before downstream exception reporting / request logging.
        if request.path.rstrip('/') == '/api/preview':
            request._preview_key_valid = bool(settings.PREVIEW_KEY) and hmac.compare_digest(
                request.GET.get('klucz', '').encode(), settings.PREVIEW_KEY.encode())
            request.META['QUERY_STRING'] = ''
            request.META.pop('RAW_URI', None)
            request.META.pop('REQUEST_URI', None)
            request.GET = request.GET.copy()
            request.GET.clear()
        active = valid_preview(request.COOKIES.get('sc_preview_sig'))
        token = preview_active.set(active)
        try:
            response = self.get_response(request)
            if active or request.path.rstrip('/') == '/api/preview' or request.path.startswith('/api/preview/'):
                response['Cache-Control'] = 'private, no-store'
                response['Referrer-Policy'] = 'no-referrer'
                response['X-Robots-Tag'] = 'noindex, nofollow'
            patch_vary_headers(response, ('Cookie',))
            if not active and (request.COOKIES.get('sc_preview') or request.COOKIES.get('sc_preview_sig')):
                # Do not remove the newly issued cookies on entry.
                if 'sc_preview_sig' not in response.cookies:
                    clear_cookies(response)
            return response
        finally:
            preview_active.reset(token)
            if hasattr(request, '_preview_key_valid'):
                del request._preview_key_valid


class PreviewThrottle(SimpleRateThrottle):
    scope = 'preview'
    rate = '10/hour'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


def clear_cookies(response):
    for name in ('sc_preview_sig', 'sc_preview'):
        response.delete_cookie(name, path='/', samesite='Lax')
        response.cookies[name]['secure'] = True
    response.cookies['sc_preview_sig']['httponly'] = True


@require_GET
def enter(request):
    if (not settings.PREVIEW_KEY or not PreviewThrottle().allow_request(request, None)
            or not getattr(request, '_preview_key_valid', False)):
        return HttpResponse(status=404)
    response = HttpResponseRedirect('/podglad')
    response.set_cookie('sc_preview_sig', signing.dumps(key_digest(), salt=SALT),
                        max_age=MAX_AGE, httponly=True, secure=True, samesite='Lax', path='/')
    response.set_cookie('sc_preview', '1', max_age=MAX_AGE, secure=True, samesite='Lax', path='/')
    return response


@require_GET
def leave(request):
    response = HttpResponseRedirect('/')
    clear_cookies(response)
    return response


@require_GET
def status(request):
    return JsonResponse({'active': preview_active.get()})
