# Kierunek MVP frontendu spin.clinic

## Tożsamość
spin.clinic nie tworzy własnych reportaży ani nie rozstrzyga, co jest prawdą. Porządkuje, promuje i łączy materiały już opublikowane przez źródła, do których ma właściwy dostęp. Zawsze widoczne są źródło, czas i odnośnik do oryginału.

## Strona główna
1. Nagłówek: wyszukiwarka, Tematy, Źródła, Moje nitki, Jak działamy.
2. Szeroki pas ilustracyjny: cztery autorskie warianty dla pory dnia; wybór jasny, ciemny lub auto; stała etykieta „Ilustracja autorska”.
3. „Najnowsze materiały w bazie”: poziomy strumień realnych materiałów.
4. „TOP 10 tematów”: liczba nowych materiałów i źródeł z ostatnich 24 godzin.
5. „Wątek dnia”: tylko gdy wystarcza danych; materiał, wyjaśnialna oś czasu, źródła i wejście do pełnego kontekstu. W przeciwnym razie „Najczęściej rozwijający się temat”.
6. „Nitki Dr Spina”: kontekstowe zestawienia z jasno podanymi kryteriami; Dr Spin jest przewodnikiem po kontekście, nie reporterem.
7. „Najaktywniejsze źródła dziś”: liczba materiałów i czas ostatniej aktualizacji, bez sugerowania rankingu jakości.
8. „Moje nitki”: prywatne nitki użytkownika.
9. Wejście do bazy i kategorii: Polska, Świat, Gospodarka, Prawo i instytucje, Nauka i zdrowie, Kultura, Sport, Technologie, Lokalne.

## Moje nitki - MVP
Użytkownik tworzy 1-5 prywatnych nitek jako pełnoszerokie, poziome paski materiałów na stronie głównej. Każdy pasek wygląda i działa jak „Najnowsze materiały w bazie”, lecz ma własną nazwę i regułę: słowa kluczowe, źródła, kategorie oraz opcjonalny okres czasu. Przykłady: „Sport”, „Zondacrypto”, „Tylko Onet”. Nitka pokazuje wyłącznie materiały już w bazie i nie uruchamia pobierania. Każdy wpis ma „Dlaczego tu jest?” z jawnym dopasowaniem. Przy braku wyników pokazujemy użyteczny pusty stan. Do czasu obsługi kont przez backend ustawienia można przechowywać lokalnie w przeglądarce, bez deklarowania, że są synchronizowane.

## Granice MVP
Nie ma materiałów sponsorowanych ani nitek partnerskich. Nie ma fikcyjnych newsów, obrazów wydarzeń ani udawanych danych. Grafiki dekoracyjne są własne i oznaczone. Nie zmieniamy backendu, kart dostępu, harvesterów ani wspólnych komponentów bez osobnego zadania.

## Konta MVP i udział źródeł
Są dwa typy kont. Zwykły użytkownik personalizuje prywatne paski na stronie głównej, zapisuje ulubione publiczne nitki, dodaje jednorazowe oceny oraz ręcznie udostępnia materiał do X. Konto autoryzowane (semiredakcyjne) może tworzyć własne publiczne nitki podpisane nazwą zweryfikowanego konta; publikacja na stronie głównej wymaga jasnego oznaczenia autora i kryteriów doboru. Nie ma automatycznego publikowania do X. W MVP nie ma materiałów sponsorowanych ani nitek partnerskich. Zaproszenia e-mail do źródeł są wstrzymane do czasu publicznego MVP z linkiem testowym.
