"""Wspólne logowanie trzech domen (spin.clinic, przeszlosc.today, spina3.pl): projekt i implementacja tokenów.

Problem: trzy różne eTLD+1, ciasteczko sesji nie przechodzi. Rozwiązanie (RF sekcja 5, poprawka 4):
JEDNA usługa logowania na osobnej domenie (np. konto.iapply.pl; to istniejące konta e-mail i X z `news.accounts`),
logowanie w spina3 przez przekierowanie i powrót, tokeny krótkie.

Przepływ (flaga `auth_mode='token'`):
1. Front spina3.pl kieruje na `{SPINA3_SSO_ISSUER}/logowanie?aud=spina3&powrot=<url>`.
2. Usługa kont (ten sam backend Django, inna domena) po zalogowaniu wystawia jednorazowy KOD (`issue_code`, 120 s,
   podpisany TimestampSigner z solą 'spina3-sso-code') i przekierowuje z powrotem z `?kod=...`.
3. Front woła `POST /api/spina3/auth/exchange {code}`; backend weryfikuje kod (`redeem_code`) i wystawia TOKEN SESJI
   (`issue_token`, 15 min; odświeżany `POST /api/spina3/auth/refresh` dopóki konto aktywne). Token idzie w nagłówku
   `Authorization: Bearer <token>`; klasa `SsoBearerAuthentication` uwierzytelnia żądania DRF.
4. Wylogowanie wszędzie: `Spina3Profile.pseudonym` jest w tokenie; rotacja pseudonimu unieważnia wszystkie tokeny
   (jedno kliknięcie "wyloguj wszędzie"), bez tabeli sesji.

Czego tu NIE ma: konfiguracji produkcji (domeny, CORS, ciasteczka), kluczy; klucz podpisu to SECRET_KEY Django
(osobny `SPINA3_SSO_SECRET` do rozważenia przy rozdzieleniu usług). Tryb domyślny 'session' zostawia dzisiejsze
logowanie sesyjne (ta sama domena API).
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from rest_framework import authentication, exceptions

CODE_SALT = 'spina3-sso-code'
TOKEN_SALT = 'spina3-sso-token'


def _audience() -> str:
    return getattr(settings, 'SPINA3_SSO_AUDIENCE', 'spina3')


def issue_code(user, audience: str | None = None) -> str:
    """Jednorazowy kod przekazywany w przekierowaniu (ważny `SPINA3_SSO_CODE_MAX_AGE` s)."""
    from .models import Spina3Profile
    profile = Spina3Profile.for_user(user)
    return signing.TimestampSigner(salt=CODE_SALT).sign_object(
        {'uid': user.pk, 'aud': audience or _audience(), 'p': profile.pseudonym})


def redeem_code(code: str, audience: str | None = None):
    """Zwraca użytkownika albo None (kod przeterminowany, zły podpis, zła domena, konto nieaktywne)."""
    try:
        data = signing.TimestampSigner(salt=CODE_SALT).unsign_object(
            code, max_age=getattr(settings, 'SPINA3_SSO_CODE_MAX_AGE', 120))
    except (signing.BadSignature, signing.SignatureExpired):
        return None
    if data.get('aud') != (audience or _audience()):
        return None
    return _user_for(data)


def issue_token(user) -> str:
    """Token sesji (krótki, `SPINA3_SSO_TOKEN_MAX_AGE` s), zawiera pseudonim: rotacja pseudonimu = wylogowanie wszędzie."""
    from .models import Spina3Profile
    profile = Spina3Profile.for_user(user)
    return signing.TimestampSigner(salt=TOKEN_SALT).sign_object({'uid': user.pk, 'p': profile.pseudonym, 'aud': _audience()})


def verify_token(token: str):
    try:
        data = signing.TimestampSigner(salt=TOKEN_SALT).unsign_object(
            token, max_age=getattr(settings, 'SPINA3_SSO_TOKEN_MAX_AGE', 900))
    except (signing.BadSignature, signing.SignatureExpired):
        return None
    if data.get('aud') != _audience():
        return None
    return _user_for(data)


def _user_for(data: dict):
    from .models import Spina3Profile
    user = get_user_model().objects.filter(pk=data.get('uid'), is_active=True).first()
    if user is None:
        return None
    profile = Spina3Profile.for_user(user)
    if profile.pseudonym != data.get('p'):
        return None  # wylogowano wszędzie (rotacja pseudonimu) albo token z innego konta
    return user


def logout_everywhere(user) -> None:
    """Rotacja pseudonimu: unieważnia wszystkie tokeny; dziennik zdarzeń traci powiązanie ze starym pseudonimem."""
    import secrets
    from .models import Spina3Profile
    profile = Spina3Profile.for_user(user)
    profile.pseudonym = secrets.token_hex(16)
    profile.save(update_fields=['pseudonym'])


class SsoBearerAuthentication(authentication.BaseAuthentication):
    """`Authorization: Bearer <token>`; aktywna tylko przy `auth_mode='token'` (inaczej przezroczysta)."""
    keyword = 'Bearer'

    def authenticate(self, request):
        from .config import flags
        if flags().auth_mode != 'token':
            return None
        header = authentication.get_authorization_header(request).decode('latin-1')
        if not header or not header.lower().startswith('bearer '):
            return None
        user = verify_token(header.split(' ', 1)[1].strip())
        if user is None:
            raise exceptions.AuthenticationFailed('Token nieważny albo przeterminowany.')
        return (user, None)

    def authenticate_header(self, request):
        return self.keyword
