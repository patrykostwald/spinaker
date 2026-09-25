# Brief strony „O nas”

Stan decyzji: 25 września 2026 (aktualizacja struktury; zasady z 23.09 poniżej nadal obowiązują). To źródło prawdy dla treści strony `/o-nas`.

## Struktura (25.09)

Strona jest adresowana do nowych czytelników i do redakcji, którym wysyłamy prośbę o zgodę — link w wiadomości prowadzi do `/o-nas` (albo `/o-nas#dla-redakcji`). Kolejność sekcji (każda ma kotwicę):

1. `#spin-doctor` — definicja ze Słownika języka polskiego PWN (cytat dosłowny, z linkiem) i jedno zdanie o tym, czym jest spin.clinic.
2. `#o-nas` — „Kontekst zamiast werdyktu”: czym jest serwis, czego nie robi, stan projektu; opis do skopiowania.
3. `#fazy` — trzy fazy z technologią każdej fazy.
4. `#box` — box; notka: dziś powiązania po słowach, kategoriach i dacie, w przyszłości własny otwartoźródłowy silnik AI (plan, nie stan).
5. `#po-kliknieciu` — oś czasu 15 powiązanych, reakcje, baza powiązanych (kategorie × daty).
6. `#nitki-newsowe` — do 5 własnych pasków po haśle, kategorii i źródle.
7. `#nitki-kontekstowe` — box otwierający + oś kontekstu z komentarzami; dziś tylko redakcja jako Dr. Spin.
8. `#dr-spin` — programy i modele AI szukają przekazów dnia i powtarzanych spinów, podsuwają materiały potwierdzające, podważające lub wyjaśniające; redakcja zatwierdza. Później: osie powiązań z rejestrem osób publicznych. Nie jest narzędziem „prawdy”.
9. `#dla-redakcji` — zakres dostępu (metadane, tempo, bez pełnych tekstów i zdjęć, brak odpowiedzi ≠ zgoda, rezygnacja na wiadomość, kontakt).
10. `#zasady` — co robimy / czego nie robimy.

Forma: schematy rysowane znakami w okienkach „do skopiowania”; prosty, ludzki język bez marketingu.

## Cel

W minutę czytelnik ma zrozumieć, że spin.clinic pomaga czytać materiały w kontekście źródeł i czasu. Każdy materiał jest boxem ze źródłem, datą i odnośnikiem do oryginału. Powiązanie oznacza wspólny element, a nie dowód ani werdykt.

## Działające MVP

- Baza materiałów z legalnie dostępnych i możliwych do sprawdzenia źródeł.
- Powiązania po haśle, kategorii, źródle i czasie oraz chronologiczny widok kontekstu.
- Temat dnia: automatycznie ułożone chronologicznie materiały powiązane tematycznie.
- Dr Spin: nitki układane i zatwierdzane przez człowieka. Nie publikuje ich automatycznie żaden model.
- Oficjalne API instytucji, RSS, BIP, Sejm, ELI, opisy filmów YouTube oraz wpisy X wyłącznie z ręcznie potwierdzonych kont i przez oficjalne płatne API.

## Kolejny etap

Konta użytkowników pozwolą zachować ulubione materiały i prywatne nitki kontekstowe. Komentarze, reakcje i zgłoszenia będą udostępniane razem z moderacją. Funkcje istniejące technicznie, lecz niewłączone jeszcze w interfejsie, opisujemy jako „w trakcie udostępniania”, nie jako działające publicznie.

## Asystent redakcyjny

Publiczna nazwa: **„Dr Spin — asystent redakcyjny oparty na modelach open-weight”**.

- NVIDIA NIM: późniejszy pilotaż grupowania i porządkowania już pobranych, potwierdzonych wpisów X.
- Groq: późniejszy pilotaż szkiców redakcyjnych w ścisłym formacie, wyłącznie na tych wpisach X.
- Dostawcy są domyślnie wyłączeni. Do modelu trafiają wyłącznie dopuszczone, krótkie fragmenty publicznych materiałów ze źródłem i datą.
- Model może zaproponować szkic; redaktor sprawdza go i decyduje o publikacji. Model nie ocenia osób, nie rozstrzyga prawdy i nie publikuje sam.
- Docelowo rozważamy własną infrastrukturę dla modeli open-weight po ewaluacji jakości, licencji i kosztów. Nie nazywamy tego dziś „własnym AI”.

Zakres pierwszego pilotażu AI jest celowo wąski: przygotowuje trzy niepublikowane szkice dla redaktora — przekaz dnia kont rządzących, przekaz dnia kont opozycyjnych oraz kandydat Dr Spina wskazujący najczęściej powtarzany albo najbardziej angażujący przekaz. Nie nazywa automatycznie osoby ani wpisu „głupim”, „kłamstwem” czy „spinem”; redaktor wybiera opis, sprawdza źródła i decyduje o publikacji.

## Granice, które muszą być widoczne

- Portal nie oznacza treści jako „prawda” lub „fałsz” i nie ocenia osób.
- Portal nie zastępuje wydawcy, materiału źródłowego ani niezależnej weryfikacji.
- Portal nie omija blokad, limitów, płatnych dostępów ani zasad źródeł.
- Materiał reklamowy lub sponsorowany musi mieć jawną etykietę.
- Braki danych pokazujemy jako braki, bez zgadywania.

## Styl

Minimalistyczny: box → oś czasu → nitka Dr Spina. Bez ściany logotypów, pozorowanych liczników i agresywnych animacji. Ruch jest opcjonalny i wyłączony przy `prefers-reduced-motion`.
