import json
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from news.editorial_roles import can_author_threads

@require_GET
@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({'csrfToken': get_token(request)})

@require_POST
@csrf_protect
def sign_in(request):
    key = 'login-attempts:' + request.META.get('REMOTE_ADDR', '')
    cache.add(key, 0, timeout=300)
    if cache.incr(key) > 10:
        return JsonResponse({'detail': 'Zbyt wiele prób. Spróbuj ponownie za 5 minut.'}, status=429)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError()
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'detail': 'Nieprawidłowe dane.'}, status=400)
    username, password = data.get('username', ''), data.get('password', '')
    if not isinstance(username, str) or not isinstance(password, str):
        return JsonResponse({'detail': 'Nieprawidłowe dane.'}, status=400)
    user = authenticate(request, username=username[:150], password=password)
    if not user or not can_author_threads(user):
        return JsonResponse({'detail': 'Nieprawidłowe dane logowania lub brak dostępu redakcyjnego.'}, status=403)
    login(request, user)
    return JsonResponse({'authenticated': True, 'csrfToken': get_token(request)})

@require_POST
@csrf_protect
def sign_out(request):
    logout(request)
    return JsonResponse({'authenticated': False})
