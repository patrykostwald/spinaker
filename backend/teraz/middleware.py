from django.conf import settings

PREFIKS_API = "/api/teraz/"


class PrywatneOdpowiedziPrzedStartem:
    """Przed publicznym startem (TERAZ_PUBLICZNE wyłączone) każda odpowiedź pod /api/teraz/ jest prywatna, także ta, która
    nie dochodzi do widoku: preflight CORS (pusta 200 z CorsMiddleware) i przekierowanie bez końcowego ukośnika (301 z
    CommonMiddleware). Stoi na zewnątrz tych middleware'ów, więc widzi ich odpowiedzi (recenzja PR #38, R38b P2-3).
    Widoki same ustawiają ten nagłówek w `PublicznyOdczyt.finalize_response`; tu tylko domykamy odpowiedzi poboczne."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        sciezka = request.path
        if (sciezka == PREFIKS_API.rstrip("/") or sciezka.startswith(PREFIKS_API)) and not settings.TERAZ_PUBLICZNE:
            response["Cache-Control"] = "private, no-store"
        return response
