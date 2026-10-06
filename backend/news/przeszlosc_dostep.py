"""Dostęp do funkcji przeszłość.today (właściciel 7.10: „na razie nie publikujmy cen, dajmy wszystkie funkcjonalności,
żeby pokazać, co możemy oferować”).

PRZESZLOSC_BETA_ALL_FEATURES (domyślnie True): każda funkcja Pro jest otwarta dla każdego odwiedzającego i konta, a strony
pokazują małą etykietę „Beta - wszystkie funkcje bezpłatnie”. Wyłączenie flagi przywraca podział darmowe / Pro bez zmian
w kodzie: Pro mają piloci (news.sales.is_pilot_pro) i personel. Cen nie publikujemy nigdzie: ani na stronach, ani w API,
ani w materiałach - wycena indywidualna, te same warunki dla wszystkich.

FEATURES to jedno źródło listy „Co potrafi przeszłość.today” (strona /przeszlosc/funkcje i API /api/przeszlosc/funkcje/).
"""
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

BETA_LABEL = 'Beta - wszystkie funkcje bezpłatnie'
PRO = {'alerts', 'export', 'denominators', 'krs', 'money_trail', 'deviations'}
LOCKED_DETAIL = 'To funkcja Pro. W pilotażu dostęp jest bezpłatny: przeszlosc.today/przeszlosc/pilot.'

# (id, ikona, tytuł - jedna linia, opis - do 3 linii, przykład, odnośnik, rodzaj). Bez cen i bez obietnic przyszłych funkcji.
FEATURES = [
    ('temat', 'search', 'Kto, co i kiedy w temacie', 'Wypowiedzi polityków, druki i głosowania Sejmu, spółki z KRS i media na jednej osi czasu.',
     'Wpisz „CPK” albo „KPO”', '/przeszlosc?q=CPK', 'darmowe'),
    ('drzewo', 'people', 'Drzewo powiązań', 'Osoba, jej wypowiedź i diagnoza Dr. Spina połączone liniami. Każda krawędź ma źródło.',
     'Kliknij osobę w drzewie tematu', '/przeszlosc?q=KPO', 'darmowe'),
    ('glosowania', 'vote', 'Głosowania Sejmu w temacie', 'Wynik każdego klubu i głos każdego posła w głosowaniach związanych z tematem.',
     'Temat „Turów”: kto był za, kto przeciw', '/przeszlosc?q=Tur%C3%B3w', 'darmowe'),
    ('profil', 'person', 'Profil osoby publicznej', 'Wpisy na X, interpelacje, wystąpienia, głosowania i artykuły jednej osoby w jednym miejscu.',
     'Szukaj po nazwisku, np. „Kosiniak”', '/przeszlosc?tryb=osoba', 'darmowe'),
    ('diagnozy', 'diagnosis', 'Diagnozy Dr. Spina', 'Ocena manipulacji od 0 do 100 przy wpisach polityków, liczona tą samą miarą dla wszystkich.',
     '„Średni spin” w profilu osoby', 'https://spin.clinic/klinika', 'darmowe'),
    ('odstepstwa', 'vote', 'Odstępstwa od klubu', 'Kto głosuje inaczej niż większość swojego klubu i jak często, z linkiem do każdego głosu.',
     '„Głosy wbrew klubowi” na stronie', '/przeszlosc#odstepstwa', 'Pro'),
    ('mianowniki', 'people', 'Wspólne mianowniki', 'Z kim osoba występuje w tych samych tematach, w tych samych spółkach i jak zgodnie głosuje.',
     'Dół profilu każdej osoby', '/przeszlosc?tryb=osoba', 'Pro'),
    ('krs', 'organisation', 'Funkcje w KRS', 'Zarządy i rady nadzorcze spółek i fundacji z datami od i do, prosto z urzędowego odpisu.',
     '„Funkcje w KRS” w profilu', '/przeszlosc?tryb=osoba', 'Pro'),
    ('pieniadze', 'institution', 'Ślad pieniędzy z UE', 'Dotacje i projekty z funduszy UE (Kohesio, FTS) przy spółkach i organizacjach z tematu.',
     '„Fundusze UE w temacie” przy KPO', '/przeszlosc?q=KPO', 'Pro'),
    ('alerty', 'bell', 'Alerty e-mail', 'Codziennie o 7:00 jeden list o nowych wpisach, dokumentach i głosowaniach w obserwowanym temacie.',
     'Przycisk „Obserwuj” przy temacie', '/przeszlosc/alerty', 'Pro'),
    ('eksport', 'down', 'Eksport CSV i JSON', 'Cały temat albo profil do arkusza lub własnej bazy, każdy wiersz z linkiem do oryginału.',
     'Przyciski CSV i JSON w profilu', '/przeszlosc?tryb=osoba', 'Pro'),
    ('przypis', 'record', 'Gotowy przypis', 'Jednym kliknięciem cytat z autorem, datą i źródłem do wklejenia w tekst lub przypis.',
     'Przycisk przypisu przy wpisie', '/przeszlosc?q=CPK', 'darmowe'),
    ('archiwum', 'media', 'Kopia źródła w archiwum', 'Kopia cytowanego materiału w Internet Archive i ostrzeżenie, gdy tekst zmienił się po cytowaniu.',
     'Panel wpisu: „Zapisz kopię teraz”', '/przeszlosc?q=CPK', 'darmowe'),
    ('wideo', 'statement', 'Wystąpienia z nagrań Sejmu', 'Wystąpienia posłów z sali i komisji z sekundą nagrania i diagnozą Dr. Spina.',
     '„Wystąpienia w Sejmie” w profilu', '/przeszlosc?tryb=osoba', 'darmowe'),
    ('europoslowie', 'institution', 'Europosłowie z Polski', 'Głosowania w Parlamencie Europejskim, deklaracje dochodów i spotkania z lobbystami.',
     '„Głosowania w PE” w profilu', '/przeszlosc?tryb=osoba', 'darmowe'),
    ('kilometrowki', 'record', 'Kilometrówki i biura posłów', 'Rozliczenia przejazdów i biur poselskich, sprawdzone z listą posłów Sejmu.',
     '„Wydatki posła” w profilu', '/przeszlosc?tryb=osoba', 'darmowe'),
    ('rss', 'rss', 'Kanał RSS tematu', 'Nowości w temacie w czytniku RSS albo w narzędziu redakcji, bez zakładania konta.',
     'Okno „Obserwuj”: kanał RSS', '/przeszlosc?q=CPK', 'darmowe'),
    ('tematy-dnia', 'statement', 'Tematy dnia', 'Tematy, o których dziś mówi najwięcej polityków, wybierane automatycznie z danych.',
     'Przyciski pod wyszukiwarką', '/przeszlosc', 'darmowe'),
]


def beta():
    return bool(getattr(settings, 'PRZESZLOSC_BETA_ALL_FEATURES', True))


def has(feature, request=None, email=''):
    """Czy ta funkcja jest otwarta dla tego odwiedzającego. W becie: zawsze. Potem: darmowe dla wszystkich, Pro dla
    personelu i pilotów (adres e-mail z przyznanym pilotem)."""
    if feature not in PRO or beta():
        return True
    from news.sales import is_pilot_pro
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        if user.is_staff or (user.email and is_pilot_pro(user.email)):
            return True
    return bool(email) and is_pilot_pro(email)


def access(request=None):
    """Mały blok do odpowiedzi API: etykieta bety i lista zamkniętych funkcji (pusta w becie)."""
    on = beta()
    return {'beta': on, 'label': BETA_LABEL if on else '', 'locked': sorted(f for f in PRO if not has(f, request))}


def locked(feature):
    return Response({'detail': LOCKED_DETAIL, 'feature': feature, 'locked': True}, status=403)


def features(request=None):
    open_ = access(request)
    return [{'id': i, 'icon': icon, 'title': title, 'text': text, 'example': example, 'href': href, 'tier': tier,
             'open': i not in FEATURE_GATES or FEATURE_GATES[i] not in open_['locked']}
            for i, icon, title, text, example, href, tier in FEATURES]


# Funkcja na stronie -> bramka w API (has / locked).
FEATURE_GATES = {'odstepstwa': 'deviations', 'mianowniki': 'denominators', 'krs': 'krs', 'pieniadze': 'money_trail',
                 'alerty': 'alerts', 'eksport': 'export'}


@api_view(['GET'])
@permission_classes([AllowAny])
def features_view(request):
    """GET /api/przeszlosc/funkcje/ - lista funkcji i etykieta bety (bez cen). Działa także przy wyłączonym podglądzie."""
    return Response({**access(request), 'features': features(request)})
