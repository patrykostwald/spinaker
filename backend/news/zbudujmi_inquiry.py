"""Zapytania ze strony zbudujmi.com (właściciel 6.10: „podpinaj wysyłkę”). Strona jest statyczna na Cloudflare,
więc formularz wysyła POST tutaj, a my przekazujemy go e-mailem przez istniejący SMTP serwisu.

Bez zapisywania w bazie: wiadomość trafia tylko do skrzynki firmy. Ochrona: pole-pułapka dla botów, limity długości,
limit 5 zapytań na godzinę z jednego adresu, odpowiedź CORS tylko dla domen zbudujmi."""
import json
import re

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from news.account_mail import send_account_mail

TO = 'kontakt@iapply.pl'
ORIGINS = {'https://zbudujmi.com', 'https://www.zbudujmi.com', 'http://localhost:8790'}
LIMITS = {'what': 120, 'm': 4000, 'n': 200, 'e': 200}


def _cors(response, request):
    origin = request.headers.get('Origin', '')
    if origin in ORIGINS:
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'content-type'
        response['Vary'] = 'Origin'
    return response


@csrf_exempt
def inquiry(request):
    if request.method == 'OPTIONS':
        return _cors(HttpResponse(status=204), request)
    if request.method != 'POST':
        return _cors(JsonResponse({'detail': 'Tylko POST.'}, status=405), request)
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        return _cors(JsonResponse({'detail': 'Niepoprawne dane.'}, status=400), request)
    if data.get('website'):  # pole-pułapka: człowiek go nie widzi
        return _cors(JsonResponse({'ok': True}), request)
    fields = {k: str(data.get(k, '')).strip()[:limit] for k, limit in LIMITS.items()}
    if not fields['m'] or not fields['e']:
        return _cors(JsonResponse({'detail': 'Uzupełnij opis i kontakt.'}, status=400), request)
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
    key = 'zbudujmi-inquiry:' + re.sub(r'[^0-9a-f.:]', '', ip.lower())
    count = cache.get(key, 0)
    if count >= 5:
        return _cors(JsonResponse({'detail': 'Za dużo zapytań. Napisz na ' + TO + '.'}, status=429), request)
    cache.set(key, count + 1, 3600)
    body = (f"Nowe zapytanie ze strony zbudujmi.com\n\nCo: {fields['what'] or '-'}\nOpis: {fields['m']}\n"
            f"Imię i firma: {fields['n'] or '-'}\nKontakt: {fields['e']}\n")
    sent = send_account_mail(TO, 'Zapytanie zbudujmi: ' + (fields['what'] or 'projekt'), body)
    if not sent:
        return _cors(JsonResponse({'detail': 'Nie udało się wysłać. Napisz na ' + TO + '.'}, status=503), request)
    return _cors(JsonResponse({'ok': True}), request)
