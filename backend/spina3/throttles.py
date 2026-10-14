"""Limity odczytu i zapisu (PETLA 2.2 wiersz 18 i lista zbiorcza): 120/min ściana, 30/min szukaj, related i komentarze (odczyt),
10/min boxy z przypięciem, 30/min oceny, 10/min komentarze (zapis) na konto. Klucz na SKRÓCONYM IP (hash z solą dobową),
nigdy pełny IP w bazie ani w cache."""
from __future__ import annotations

from hashlib import sha256

from django.conf import settings
from django.utils import timezone
from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class HashedIpThrottle(SimpleRateThrottle):
    scope = 'spina3_read'
    rate = '120/min'

    def get_cache_key(self, request, view):
        salt = f"{settings.SECRET_KEY}:{timezone.localdate()}"
        digest = sha256(f'{salt}:{self.get_ident(request)}'.encode()).hexdigest()[:24]
        return self.cache_format % {'scope': self.scope, 'ident': digest}


class WallThrottle(HashedIpThrottle):
    scope = 'spina3_wall'
    rate = '120/min'


class SearchThrottle(HashedIpThrottle):
    scope = 'spina3_search'
    rate = '30/min'


class RelatedThrottle(HashedIpThrottle):
    scope = 'spina3_related'
    rate = '30/min'


class CommentsReadThrottle(HashedIpThrottle):
    scope = 'spina3_comments_read'
    rate = '60/min'


class PinWriteThrottle(UserRateThrottle):
    scope = 'spina3_pin_write'
    rate = '10/min'


class RatingWriteThrottle(UserRateThrottle):
    scope = 'spina3_rating_write'
    rate = '30/min'


class CommentWriteThrottle(UserRateThrottle):
    scope = 'spina3_comment_write'
    rate = '10/min'


class ReportThrottle(UserRateThrottle):
    scope = 'spina3_report'
    rate = '10/hour'


class AuthExchangeThrottle(HashedIpThrottle):
    scope = 'spina3_auth'
    rate = '20/min'


class CorrectionThrottle(HashedIpThrottle):
    """Sprostowania składa także osoba bez konta: limit po skrócie adresu IP."""
    scope = 'spina3_correction'
    rate = '5/hour'
