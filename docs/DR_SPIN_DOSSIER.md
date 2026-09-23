# Dr Spin — karta badawcza

Przycisk **„Dr Spin: zbadaj kontekst”** dla profilu osoby publicznej odczytuje:

`GET /api/public-figures/<id>/dossier/`

Endpoint nie uruchamia modelu ani wyszukiwania internetu. Zwraca bezkosztowy,
ograniczony pakiet dowodów z Bazy: funkcje, potwierdzone relacje z podmiotami,
głosowania, ręcznie potwierdzone materiały, potwierdzone konto X, oś czasu,
mapę i jawne luki.

## Jedno wywołanie AI

Gdy pilotaż AI zostanie włączony, interfejs może przesłać wyłącznie ten pakiet
do jednego wywołania modelu. Model zwraca pięć sekcji:

1. krótki opis dostępnego kontekstu;
2. zalecaną kolejność lektury;
3. pytania badawcze;
4. znane braki;
5. informacje, które mogłyby zmienić obraz sprawy.

Każdy punkt musi wskazać URL obecny w pakiecie. Model nie może dopisywać faktów,
relacji, motywów, ocen osób ani danych spoza pakietu. Brak rekordu nie stanowi
dowodu braku relacji.

## Prezentacja

Interfejs pokazuje osobno: streszczenie, oś czasu, funkcje, podmioty,
głosowania, materiały, mapę i luki. Ciągła krawędź mapy oznacza potwierdzoną
relację z dowodem; linia przerywana może oznaczać wyłącznie wspólny temat lub
wzmiankę i nie jest relacją.

Karta nie wydaje werdyktu i nie publikuje materiału. Publikacja nitki Dr Spina
pozostaje decyzją redakcji.
