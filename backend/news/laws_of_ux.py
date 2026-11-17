"""Laws of UX (lawsofux.com, Jon Yablonski) - „biblia” Projektanta i pętli designu (właściciel 5.10).

LAWS: wszystkie 30 praw z opisem po polsku i tym, jak stosujemy je w spin.clinic, przeszłość.today i zbudujmi.
check(): raz w tygodniu czyta stronę główną i stronę każdego prawa (sekcja „Key Takeaways”), zapisuje wnioski,
a gdy pojawi się nowe prawo albo zmieni się treść - zwraca różnice (Projektant wysyła wtedy wiadomość właścicielowi)."""
import hashlib
import re

import requests

SITE = 'https://lawsofux.com/'
UA = {'User-Agent': 'spin.clinic Projektant (+https://spin.clinic)'}
STATE = 'laws-of-ux'

LAWS = [
    ('Aesthetic-Usability Effect', 'Ładne wydaje się łatwiejsze w użyciu.', 'Dopracowany wygląd daje kredyt zaufania, ale nie maskuje błędów: testujemy na ludziach, nie tylko na zrzutach.'),
    ('Choice Overload', 'Za dużo opcji paraliżuje.', 'Jedna główna akcja na ekranie; filtry i cenniki z małą liczbą pozycji, reszta po rozwinięciu.'),
    ('Chunking', 'Informację dzielimy na sensowne grupy.', 'Boksy, sekcje z nagłówkiem, liczby po trzy; długie listy w porcjach.'),
    ('Cognitive Bias', 'Systematyczne błędy myślenia wpływają na decyzje.', 'Nie wykorzystujemy ich przeciw użytkownikowi; w spin.clinic je pokazujemy i nazywamy (spin, chwyty).'),
    ('Cognitive Load', 'Każdy element zużywa zasoby umysłu.', 'Usuwamy zbędne słowa i elementy; jeden pomysł na boks; bez żargonu.'),
    ('Doherty Threshold', 'Odpowiedź poniżej 400 ms utrzymuje skupienie.', 'Szybkie strony (LCP poniżej 1,5 s), natychmiastowa reakcja na klik, wskaźnik ładowania dopiero po 0,6 s.'),
    ("Fitts's Law", 'Czas trafienia zależy od odległości i wielkości celu.', 'Przyciski co najmniej 44 px, ważne cele duże i blisko, na telefonie w zasięgu kciuka.'),
    ('Flow', 'Pełne zanurzenie w zadaniu.', 'Bez przeszkadzaczy w trakcie czytania; płynne przejścia, natychmiastowa informacja zwrotna.'),
    ('Goal-Gradient Effect', 'Im bliżej celu, tym większa motywacja.', 'Paski postępu (przejście spinki, formularz wyceny), widoczny następny krok.'),
    ("Hick's Law", 'Czas decyzji rośnie z liczbą i złożonością wyborów.', 'Mniej pozycji w menu, podział złożonych zadań na kroki, wyróżniona rekomendacja.'),
    ("Jakob's Law", 'Ludzie oczekują, że strona działa jak inne, które znają.', 'Konwencje zamiast wynalazków: logo w lewym górnym rogu, menu, link „→”, koszyk po prawej.'),
    ('Law of Common Region', 'Elementy we wspólnym obszarze tworzą grupę.', 'Boksy i karty z wyraźną granicą dla rzeczy, które należą do siebie.'),
    ('Law of Proximity', 'Bliskie elementy postrzegamy jako grupę.', 'Odstęp wewnątrz grupy mniejszy niż między grupami; stała skala odstępów.'),
    ('Law of Prägnanz', 'Złożone kształty odczytujemy jak najprościej.', 'Proste ikony i kształty; minimalizm zamiast ozdobników.'),
    ('Law of Similarity', 'Podobne elementy odbieramy jako całość.', 'Ten sam styl dla tej samej funkcji (jeden styl linków „→”, jedna skala kolorów siły spinu).'),
    ('Law of Uniform Connectedness', 'Połączone wizualnie elementy wydają się bardziej powiązane.', 'Linie i spinki między boksami pokazują związek; łańcuch spinki, strumienie w mechanizmie.'),
    ('Mental Model', 'Ludzie mają w głowie uproszczony obraz działania systemu.', 'Nazywamy rzeczy słowami użytkownika (słownik właściciela), pokazujemy drogę zadania.'),
    ("Miller's Law", 'W pamięci roboczej mieści się około 7 elementów.', 'Grupujemy treść; nie zmuszamy do pamiętania informacji między ekranami.'),
    ("Occam's Razor", 'Z równie dobrych rozwiązań wybieramy najprostsze.', 'Usuwamy, zanim dodamy; każdy element musi mieć powód.'),
    ('Paradox of the Active User', 'Ludzie nie czytają instrukcji, od razu działają.', 'Podpowiedzi w miejscu użycia, przykłady i stan wypełniony przykładem zamiast pustego ekranu.'),
    ('Pareto Principle', '80% efektów pochodzi z 20% przyczyn.', 'Najpierw dopracowujemy najczęstsze ścieżki (ścieżki czytelników, Dyrygent ustala kolejność).'),
    ("Parkinson's Law", 'Zadanie rozrasta się do dostępnego czasu.', 'Krótkie, jasne formularze; automatyczne wypełnianie; terminy w pętlach (prototyp 24 h).'),
    ('Peak-End Rule', 'Oceniamy doświadczenie po szczycie i końcu.', 'Dopracowany moment „wow” i dobre zakończenie (potwierdzenie, dziękujemy, dostarczone).'),
    ("Postel's Law", 'Bądź liberalny w tym, co przyjmujesz, a ostrożny w tym, co wysyłasz.', 'Formularze akceptują różne formaty (telefon, NIP, daty), wynik zawsze w jednym, czystym formacie.'),
    ('Selective Attention', 'Skupiamy się na bodźcach związanych z celem.', 'Nie ukrywamy ważnego w miejscach wyglądających jak reklama; jeden wyraźny akcent na ekranie.'),
    ('Serial Position Effect', 'Najlepiej pamiętamy pierwsze i ostatnie pozycje.', 'Najważniejsze na początku i końcu list oraz menu; kluczowa akcja na końcu ścieżki.'),
    ("Tesler's Law", 'Każdy system ma złożoność, której nie da się usunąć.', 'Złożoność bierze na siebie system (agenci, automatyzacja), nie użytkownik.'),
    ('Von Restorff Effect', 'Zapamiętujemy element, który się wyróżnia.', 'Wyróżniamy tylko jedną rzecz (główny przycisk, rekomendowany pakiet); nie tylko kolorem (dostępność).'),
    ('Working Memory', 'Pamięć robocza na chwilę przechowuje informacje do zadania.', 'Pokazujemy kontekst na ekranie (co wybrano, gdzie jesteś), zamiast wymagać pamiętania.'),
    ('Zeigarnik Effect', 'Niedokończone zadania pamiętamy lepiej.', 'Widoczny postęp i „dokończ” (przejście spinki, szkic wyceny), żeby ludzie wracali.'),
]


def guide_lines():
    return [f'Laws of UX · {name}: {pl} U nas: {use}' for name, pl, use in LAWS]


def _takeaways(html):
    m = re.search(r'Key Takeaways(.*?)(?:</ul>|</ol>)', html, re.S | re.I)
    return [' '.join(re.sub(r'<[^>]+>', ' ', li).split()) for li in re.findall(r'<li[^>]*>(.*?)</li>', m.group(1), re.S)] if m else []


def check():
    """Raz w tygodniu: lista praw i ich kluczowe wnioski; zwraca (zmiany, dane). Zmiany = nowe prawa albo inne wnioski."""
    from news.models import ImportState
    html = requests.get(SITE, timeout=20, headers=UA).text
    links = sorted(set(re.findall(r'href="(https://lawsofux\.com/[a-z0-9%-]+/)"', html)) - {SITE})
    data = {}
    for url in links:
        try:
            page = requests.get(url, timeout=20, headers=UA).text
        except requests.RequestException:
            continue
        title = re.search(r'<h1[^>]*>(.*?)</h1>', page, re.S)
        name = ' '.join(re.sub(r'<[^>]+>', ' ', title.group(1)).split()) if title else url.rstrip('/').rsplit('/', 1)[-1]
        points = _takeaways(page)
        data[name] = {'url': url, 'takeaways': points, 'hash': hashlib.sha1(' '.join(points).encode()).hexdigest()[:12]}
    state, _ = ImportState.objects.get_or_create(name=STATE)
    before = (state.cursor or {}).get('laws', {})
    changes = [f'Nowe prawo: {n}' for n in data if n not in before] + [f'Zmienione wnioski: {n}' for n in data if n in before and before[n]['hash'] != data[n]['hash']]
    if data:
        state.cursor = {'laws': data}
        state.save(update_fields=['cursor'])
    return (changes if before else []), data


def takeaways():
    """Wnioski zapisane przy ostatnim sprawdzeniu (do audytu Projektanta)."""
    from news.models import ImportState
    state = ImportState.objects.filter(name=STATE).first()
    return {n: d['takeaways'] for n, d in ((state.cursor or {}).get('laws', {}) if state else {}).items()}
