# Harmonogram dnia

Wszystkie godziny są podane dla Warszawy, z uwzględnieniem zmiany czasu.
Plan jest zapisany w `backend/news/daily_schedule.py`. Celery beat w
`backend/config/celery.py` pobiera z tego modułu godziny zadań.
Dyżurny sprawdza wyniki co 15 minut. Nie powstał żaden nowy agent AI.

| Co | Kiedy pracuje automat | Gdzie trafia wynik | Termin | Co robi Ratownik |
| --- | --- | --- | --- | --- |
| Zbieranie X | Co minutę, pobiera tylko konta gotowe do odczytu | Baza wpisów | Udany puls do 10 min między 7:00 a 23:00, do 2 h nocą | Uruchamia zbieranie teraz |
| Strażnik wpisów | Co 5 min | Ocena w Klinice | Do 30 min od pobrania wpisu | Ponawia ocenę, także po awarii darmowego modelu |
| Diagnozy | Co 10 min w godzinach 7-22 | Klinika albo kolejka do decyzji | Pierwsza diagnoza do 10:00, jeśli są kandydaci | Uruchamia diagnozy z zachowaniem obecnych limitów |
| Wywiad dnia | Wybór 7:05, potem 10:05, 13:05, 16:05 i 19:05; opracowanie co 10 min | Klinika albo kolejka do decyzji | Wybrany do 8:00; gotowy do 18:00 | Uwalnia osieroconą pracę i ponawia; następnie ponawia wybór; na końcu bierze kolejnego kandydata |
| Przekaz dnia każdej strony | 9:00, 12:00, 15:00, 18:00, 21:30 | Klinika albo kolejka do decyzji | Do 12:30; końcowa kontrola 22:15 | Groq, potem NVIDIA NIM, na końcu ograniczony Gemini Flash |
| Publikacja | X o :15 i :45, social o :25 i :55, w godzinach 8-21 | X oraz włączone kanały social | Przynajmniej jeden wpis na X do 21:30 | Uruchamia zadania publikacji X i social |
| Nitka Dr. Spina | 19:30 | Nitki w portalu | 20:30 | Ponawia budowę nitki z kontekstem |
| Raport tygodnia | Niedziela 20:00 | Raporty w portalu | Niedziela 21:00 | Ponawia przygotowanie raportu |
| Kontrole dostępności | 00:05, 06:05, 12:05, 18:05 | Panel dowodzenia | Co 6 h | Alarm dla kluczy X, Gemini, Anthropic i Groq, dysku oraz pulsów zadań |

Brak materiału nie zawsze oznacza awarię. Przy mniej niż trzech kontach danej strony
przekaz ma status „nie dotyczy”. Podobnie jest z brakiem kandydatów do diagnozy,
brakiem diagnozy nadającej się do publikacji i brakiem materiałów do nitki.
Raport tygodnia obowiązuje tylko w niedzielę. Wyłączone zbieranie, wywiady lub nitki
są opisane jako „nie dotyczy”. Brak klucza przy włączonej funkcji pozostaje problemem.

Wywiad dotyczy materiału z poprzedniego dnia. Brak znalezionego wywiadu przy włączonej
funkcji nie jest uznawany za sukces. „Czeka na decyzję” oznacza gotowy materiał,
który wymaga zatwierdzenia zespołu. Brak budżetu diagnoz daje osobny status
„wstrzymane: budżet” i nie uruchamia Ratownika.

## Jak działa Ratownik

Po terminie Dyżurny otwiera jeden alarm dla kamienia. Sprawdza rzeczywisty wynik,
nie samo przyjęcie zadania przez kolejkę. Gdy wynik powstanie, alarm zamyka się sam.
Przekaz rządzących i opozycji ma osobne kamienie, alarmy i limity prób.

Ratownik to kod. Ma najwyżej trzy próby na kamień i dzień warszawski, z odstępem
co najmniej 15 min. Zapisuje próbę przed wysłaniem do kolejki. Gdy worker zniknie,
czeka do 40 min, żeby nie rozpocząć równoległej pracy. Zlecenie z poprzedniego dnia
nie może wykonać naprawy dla dzisiejszego materiału.

Po trzech nieudanych próbach alarm staje się krytyczny. System podejmuje jedną próbę
wysłania pilnego maila do właściciela na kamień i dzień, również gdy
`STAFF_MAIL_ENABLED=false`. Wysyła też powiadomienie do zespołu, jeśli push jest
włączony. Błąd SMTP jest widoczny w szczegółach; system nie powiela maili.
Naprawiacz zapisuje opis problemu, ostatnie wyniki i propozycję działania.
Jego zwykły przebieg co 15 min również tylko analizuje i proponuje.
Nie zmienia produkcji samodzielnie.

## Płatny zapas przekazu

Stała lista w `clinic_ai.DAILY_MESSAGE_MODELS`:

1. `groq:openai/gpt-oss-120b`
2. `nim:deepseek-ai/deepseek-v4.1-flash`
3. `gemini:gemini-2.5-flash`

Zwykłe przebiegi korzystają wyłącznie z dwóch pierwszych modeli.
Ratownik może użyć Gemini dopiero w trzeciej próbie, tylko dla brakującego przekazu.
Nie nadpisuje gotowego lub ręcznie zatwierdzonego materiału.

Ustawienie do `.env.production`:

```ini
DAILY_MESSAGE_PAID_FALLBACK_USD=0.05
```

To wspólny dzienny limit obu stron, niezależny od cache. Wartość `0` wyłącza płatny zapas.
Nieprawidłowa lub ujemna wartość też blokuje płatne generowanie.
Używany jest istniejący `GEMINI_API_KEY`. Przed generowaniem system liczy tokeny
i rezerwuje maksymalny koszt całej odpowiedzi, do 2500 tokenów, bez wyszukiwania
i bez myślenia modelu. Stawki rezerwy są celowo wyższe od
[opublikowanej taryfy Gemini Flash](https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash).
Rezerwa zostaje zajęta także po błędzie lub timeoutcie. Nie ma automatycznej pętli
płatnych wywołań. Zmiana modelu lub taryfy wymaga przeglądu limitu w kodzie.

## Co widać w panelu

W panelu dowodzenia jest sekcja „Harmonogram dnia”. Wiersz pokazuje planowaną godzinę,
nazwę, status i krótki szczegół. Problemy są na górze. Po rozwinięciu widać termin,
historię prób, propozycję Naprawiacza i wynik wysyłki pilnego maila.
Panel odświeża dane co minutę. Nic nie zostało dodane do strony publicznej.
Odczyt `/api/staff/daily-schedule/` wymaga konta personelu i nie wywołuje dostawców.

Kontrole dostawców używają list modeli, a dla X informacji o własnym koncie oraz
[statystyk użycia API](https://docs.x.com/x-api/usage/get-usage), osobno dla klucza publikacji i zbierania.
Nie uruchamiają analiz AI. Dysk zgłasza alarm przy wolnym miejscu równym lub mniejszym niż 10%.
Kontrola beat jest pośrednia: potrzebuje aktualnych pulsów co najmniej dwóch z trzech
niezależnych zadań. Awarii całego workera i beat naraz sam Dyżurny nie zgłosi;
pozostaje istniejący zewnętrzny watchdog serwera.

Nie ma nowej migracji. Próby, rezerwy i pulsy korzystają z `RepairerState`,
alarmy z `DutyAlarm`, propozycje z `RepairAction`. Po wdrożeniu trzeba uruchomić
ponownie workery i beat. Pierwszy puls pojawi się po przebiegu zadania.
