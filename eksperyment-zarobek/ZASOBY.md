# Zasoby iapply (stan 21.10.2026, spisał koordynator)

Oznaczenia: [P] potwierdzone, [DP] do potwierdzenia. Szczegóły techniczne są w repozytorium (backend/, docs/, frontend-*).

## Firma i ludzie
- iapply sp. z o.o., Poznań, KRS 0001133291, kapitał 50 000 zł [P]. Faktury VAT wystawia spółka.
- Ludzie: właściciel (współzałożyciel, produkt i decyzje), prezes zarządu (podpisuje umowy i oferty), wsparcie przy mediach
  społecznościowych. Czasu właściciela jest mało, gotówki mało. Najcenniejsze są pomysły, które nie zjadają jego dni.

## Produkty i usługi, które już działają
1. **zbudujmi.com: studio stron** [P]. Cennik z 6.10: 1490, 2990, 4990, 9990, 14990, 2490 i 149 zł netto [DP: przypisanie do pakietów
   sprawdź na zbudujmi.com]. Podglądy dla klientów pod zbudujmi.com/podglad z możliwością zgłaszania uwag. Portfolio tylko za zgodą klienta.
2. **Automatyzacja mediów społecznościowych** [P]. Pierwszy klient (sklep z odzieżą motocyklową): strona ze sklepem 3500 zł netto
   płatne z góry i pakiet „Rozwój” 1690 zł netto miesięcznie; automatycznie robione rolki wideo, kalendarz publikacji z subskrypcją
   w iPhone i Google oraz formularzem zmian. Dowód, że ktoś za to zapłacił.
3. **Konsylium AI (konsylium.ai)** [P]: metoda, w której kilka niezależnych modeli różnych firm ocenia osobno, wynik łączy stała reguła,
   a niepewność daje „nie wiem” zamiast zgadywania. Spisane zasady (Kodeks, Metoda v1.0). Kierunek: wdrożenia u klientów i wersje
   online w trzech rozmiarach [DP: ceny].
4. **spin.clinic** [P]: automatyczne diagnozy technik perswazji we wpisach polityków z X (oficjalne API), rada modeli, wywiady.
   Zasady sprzedaży (3.10): zwykli użytkownicy za darmo, raporty B2B dla instytucji i redakcji, jedna oferta dla wszystkich, bez cen
   na stronie.
5. **przeszłość.today** [P]: narzędzie do researchu przeszłości (firmy, zamówienia, osoby publiczne w zakresie prawnie dozwolonym)
   z danych publicznych: KRS, BZP, TED, a od 21.10 **pisemna zgoda Rządowego Centrum Legislacji na ponowne wykorzystanie danych
   o projektach aktów prawnych, także komercyjnie**, z podaniem źródła (pobieranie tylko nocą, limit 1 zapytanie na 5 s; zbieracz
   gotowy, start po wyjaśnieniu robots.txt). Księgi wieczyste tylko przez oficjalną licencję.
6. **Narzędzie rekrutacyjne iapply i generator dokumentów** [P], ceny z 1.10: 0, 390, 290 i 590 zł [DP: co jest czym].
7. **Filmy i grafiki reklamowe robione automatycznie** [P] (np. 3 filmy kampanii iapply: strony, social media, AI).
8. **Łowca zleceń** [P]: codzienne alerty z przetargów BZP w 6 obszarach (strony i dostępność, oprogramowanie, AI i dane,
   automatyzacja, marketing i filmy, szkolenia). Mniejsze zapytania (Baza Konkurencyjności) czekają na zgodę administratora.

## Technologia i dostęp
- Serwer VPS z Django, Postgres, Celery i Caddy; repozytorium z wieloma gotowymi modułami (zbieracze danych publicznych, rada modeli,
  poczta, raporty). Kod możesz czytać do woli.
- **PCSS (Poznańskie Centrum Superkomputerowo-Sieciowe)** [P]: darmowy dostęp testowy do modeli AI przez API (10 mln tokenów,
  obiecane kolejne 10 mln), m.in. gpt-oss 120B, Qwen3.5 397B, DeepSeek V4, Bielik 11B, Whisper; ceny po testach bardzo niskie
  (np. gpt-oss 120B 0,61 zł za 1 mln tokenów wejścia). Rozmowy o karcie GPU A100 na testy w toku.
- **BASAL** [P]: lokalny model decyzji tak/nie z prawdopodobieństwem (Apache 2.0), działa na laptopie właściciela; test 21.10 na
  546 wpisach polityków: lepiej od obecnego sita oddziela spin od zwykłych wpisów.
- „Warsztat”: Codex (budowa prototypów), Gemini CLI, lokalne modele w Ollama.

## Kanały, które mamy
- Profil na Useme (limit ofert do czasu weryfikacji profilu) [P].
- Strona firmowa na Facebooku i gotowe materiały kampanii [P]; strony zbudujmi.com i konsylium.ai [P].
- Kontakty instytucjonalne w toku (PCSS, instytucje publiczne). Agenci nie kontaktują się z nimi sami.

## Granty i programy w toku (nie dubluj)
- Program SECURE (cyberbezpieczeństwo, CRA): rekomendacja „tak”, mały projekt ok. 10-12 tys. EUR, czeka na decyzję właściciela.
- Fundusze EOG przez partnera z sektora organizacji pozarządowych: najwcześniej 2027.

## Czego nie ruszać
- Projekt „Radar” (niepubliczny), oferta wdrożeniowa w toku dla jednej kancelarii, prywatne gry właściciela.
- Wycena firmy, dane klientów, klucze i hasła (nie czytasz plików .env).
