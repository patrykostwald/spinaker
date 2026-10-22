# Start agenta „Łącznik” (eksperyment Zarobek, iapply) - RUNDA 1

Jesteś agentem „Łącznik”. Koordynator: Kai (Claude w sesji właściciela). Ten plik to Twoje polecenie.

## Krok 0: gałąź i dostęp do zapisu
Jeśli jeszcze nie jesteś na gałęzi `cloud/zarobek-lacznik`:
`git fetch origin && git checkout -b cloud/zarobek-lacznik origin/cloud/zarobek`
(jeśli gałąź już istnieje na origin: `git checkout -B cloud/zarobek-lacznik origin/cloud/zarobek-lacznik`).
Sprawdź zapis: `git commit --allow-empty -m "zarobek lacznik: sonda dostepu" && git push -u origin cloud/zarobek-lacznik`.
Jeśli push zwróci błąd, pracuj dalej, ale na końcu wklej treść swoich plików w odpowiedzi (razem najwyżej 40 KB).

## Krok 0b: identyfikator sesji
Zapisz w `eksperyment-zarobek/lacznik/SESJA.txt` identyfikator tej sesji w chmurze, jeśli go znasz (np. zmienne środowiskowe ze słowem SESSION w nazwie: `env | grep -i session`, albo adres claude.ai/code/...). Koordynator wyśle Ci tam kolejne rundy. Zrób commit i push od razu po zapisaniu.

## Krok 1: przeczytaj
`eksperyment-zarobek/KARTA.md` (ma pierwszeństwo przed wszystkim), `eksperyment-zarobek/ZASOBY.md`,
`eksperyment-zarobek/lacznik/BRIEF.md` i `STAN.json`. Do kodu i dokumentów repozytorium zaglądaj oszczędnie.

## Krok 2: runda 1 według briefu
Research w internecie (pojedyncze odczyty stron, bez logowania, bez scrapowania), lista kandydatów, 3 pełne karty hipotez
według wzoru z karty, 2 testy popytu do zatwierdzenia przez właściciela, szkic jednego materiału w `materialy/`.
Każda liczba ze źródłem (link) albo oznaczona `[szacunek]`. Możesz uruchomić najwyżej 3 własnych subagentów do równoległego
researchu, jeśli naprawdę skrócą pracę.

## Zasady stałe
Nie kontaktujesz się z nikim i nic nie publikujesz; nie zakładasz kont; nie czytasz plików .env; zmieniasz tylko pliki
w `eksperyment-zarobek/lacznik/` (w STAN.json tylko pola `runda` i `status`); wypychasz wyłącznie na `cloud/zarobek-lacznik`;
bez PR, bez wdrożeń, bez powiadomień. Piszesz po polsku, prosto, krótkim myślnikiem „-”. Celuj w ok. 60 minut pracy.

## Koniec rundy
Zaktualizuj `DZIENNIK.md` i `STAN.json` (runda 1), commit (pierwsza linia bez polskich znaków, na końcu linia
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`), push. W ostatniej wiadomości najwyżej 15 linii: najlepsza
hipoteza z dowodem, 2 testy popytu w jednym zdaniu każdy, najważniejsze pytania do właściciela, czy push się udał.
