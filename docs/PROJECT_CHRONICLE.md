# Kronika powstawania spin.clinic

Ten dokument jest trwałym dziennikiem projektu przygotowywanym z myślą o przyszłej książce. Zapisuje decyzje, przełomy, błędy, wyniki eksperymentów i podział pracy między człowieka oraz narzędzia AI. Nie przechowuje kluczy, haseł, prywatnych danych ani pełnych treści źródeł.

## Początek idei

spin.clinic powstało z potrzeby pokazania kontekstu przed oceną treści — `CONTEXT BEFORE CONTENT`. Podstawową jednostką został box: jedno źródło, niezależnie od tego, czy jest artykułem, dokumentem, filmem, wypowiedzią, postem, reklamą czy wzmianką. Boxy łączą się w chronologiczne nitki, dzięki którym użytkownik może zobaczyć rozwój wydarzenia zamiast pojedynczego nagłówka.

Nazwa i język produktu świadomie nawiązują do kliniki: Dr Spin analizuje twierdzenia, Izba przyjęć przyjmuje materiały społeczności, a role redakcyjne mogą używać nazw Ordynator i Doktor. Ustalono jednak, że marka ma pozostać profesjonalna i powściągliwa, bez rozbudowanego znaku medycznego — podstawowym logo jest napis `spin.clinic`.

## Najważniejsze decyzje produktowe

- MVP zaczyna się od bogatego archiwum legalnie dostępnych źródeł, strony głównej z paskami wiadomości, TOP 10, tematu dnia, Dr Spina i nitek zatwierdzonych autorów.
- Zwykli użytkownicy w MVP mogą personalizować źródła i hasła, zapisywać nitki, komentować oraz reagować. Publiczne nitki społeczności należą do etapu drugiego.
- Wklejenie publicznego URL najpierw uruchamia wyszukiwanie kontekstu w bazie i dozwolonych źródłach. Osobny przycisk Dr Spin analizuje sprawdzalne twierdzenia według jawnych kategorii metodologicznych.
- Wynik Dr Spina jest analizą z dowodami, zakresem pokrycia, niepewnością i historią korekt. Nie jest certyfikatem prawdy.
- W MVP publiczne analizy zatwierdza redakcja. Automatyzacja może rosnąć dopiero po pomiarze jakości i odsetka korekt.
- Oficjalne API X ma objąć bieżące posty ręcznie zweryfikowanej listy polityków oraz instytucji. Obóz polityczny jest informacją redakcyjną, a nie inferencją modelu.
- Płatne modele AI są wymienne. Ich wejścia, wyniki, wersje promptów, koszty i korekty budują audytowalny zbiór ewaluacyjny dla przyszłego własnego modelu.
- Trzy motywy produktu to: ciemny główny, jasny oraz pastelowy „Polska droga”. Typografia łączy IBM Plex Sans, Serif i Mono.

## 14 września 2026 — pierwsza noc skalowania

- Lokalne archiwum osiągnęło ponad 155 tysięcy boxów, a kolejka kandydackich URL przekroczyła 3,8 miliona pozycji.
- Uruchomiono ograniczony czasowo backfill: konfiguracja do 32 workerów, najwyżej jedno aktywne pobranie na domenę i minimum trzy sekundy odstępu, zwiększane przez reguły wydawcy.
- Audyt map OKO.press wykrył, że indeks obejmował także tagi, osoby i instytucje. Pobieranie zatrzymano, błędne zadania poddano kwarantannie, a importer ograniczono do map postów. Ten incydent potwierdził, że liczba URL nie może zastępować kontroli jakości boxów.
- Audyt praw i dostępu rozdzielono od audytu technicznego. Publiczna mapa strony nie jest automatycznie zgodą na masowe pobieranie. Źródła blokujące odpowiednie klasy botów trafiają na listę próśb o dostęp lub współpracę.
- Claude Code połączono z projektem przez lokalną kolejkę tekstową i osobny worktree. Pierwsze zbyt szerokie zadania wyczerpały limit kroków; po uproszczeniu procesu Claude ukończył opt-in mechanizm prywatnych snapshotów dowodowych.
- Snapshoty przechowują prywatny artefakt poza bazą, a w bazie jedynie metadane, hash, podstawę zgody, wersję parsera i retencję. Funkcja pozostaje domyślnie wyłączona i odmawia zapisu bez jawnego statusu prawnego.
- Mistral EU został podłączony przez adapter, lecz pierwsza minimalna próba API zwróciła HTTP 429. Dalsze próby zatrzymano, aby nie generować kosztów ani szumu.
- Powstał lokalny monitor pokazujący tempo tworzenia boxów, stan kolejki, błędy, źródła, pracę Claude’a i najważniejsze zdarzenia AI. Komputer zabezpieczono przed uśpieniem na dziesięć godzin.
- Trzy warianty wizualne wyeksportowano w rozdzielczości 1600 × 1050. Zachowano tekstowe logo i osadzone lokalnie fonty.
- Podczas przygotowania materiałów przed snem okazało się, że wcześniejsze, zaakceptowane wizualizacje z ilustracyjną „polską drogą” nie zostały zachowane jako trwałe pliki. Zamiast nich powstała techniczna rekonstrukcja, która nie odpowiadała wspólnym ustaleniom. Błąd wykrył właściciel projektu; serię odtworzono, a samo zdarzenie stało się argumentem za zapisywaniem nie tylko decyzji, lecz również ich wizualnych artefaktów, wersji i pochodzenia.
- Ustalono, że Codex i Claude mają prowadzić krótkie, zrozumiałe dla człowieka zapisy ważnych decyzji, przełomów, nieudanych prób oraz napraw. Dziennik ma pokazywać rzeczywisty proces współpracy człowieka z różnymi systemami AI, bez upiększania historii i bez sekretów.
- Po ponownym obejrzeniu rekonstrukcji właściciel wstrzymał dalsze prace nad widokami, aby priorytetem pozostała baza. Zachowane korekty do następnego podejścia: w nagłówku wyłącznie `spin.clinic`, kropka w kolorze akcentu, na środku stonowane pole wyszukiwania z przyciskiem „Szukaj”, a nitki mają zachować wcześniej uzgodniony sposób prezentacji. Hasło „Czas na lepszą rozmowę” zostało odrzucone.
- Kolejka archiwalna przekroczyła 158 tysięcy zapisanych boxów przy tempie około 5,6 tysiąca na godzinę. Równolegle oddzielono błędy trwałe od ponawialnych: techniczne ślepe uliczki trafiają do kwarantanny, a przejściowe awarie zachowują kontrolowane próby. Dzięki temu licznik pracy coraz lepiej opisuje faktyczne materiały zamiast wielokrotnie liczonych nieudanych adresów.
- Wspólny audyt Codexa i Claude wykrył rzadki wyścig przy przejmowaniu wygasłej dzierżawy zadania. Dane artykułu pozostawały bezpieczne, lecz postęp mógł zostać policzony podwójnie. Poprawkę przyjęto dopiero po lokalnym teście regresyjnym; 30 testów ścieżki archiwalnej przeszło.
- Cel 32 równoległych źródeł pozostał limitem pojemności, nie powodem do omijania zasad dostępu. W tej chwili dziewięć archiwów ma jednocześnie potwierdzony mechanizm i zgodę operacyjną. Następne źródła są dopuszczane dopiero po osobnym audycie technicznym i prawnym.
- Trzy równoległe audyty kandydatów — źródeł oficjalnych, publicznych interfejsów danych oraz mediów regionalnych — nie dopisały automatycznie żadnej domeny do puli. Wynik był celowy: publiczny adres, RSS albo mapa strony nie zastępują jasnych warunków ponownego użycia. Raporty zostawiają ślad dowodowy i wskazują, co musi zostać zweryfikowane ręcznie przed kolejną falą.
- Po zatrzymaniu nieskutecznego transportu bezpośrednio do adresów IP wykonano dwa kontrolowane testy nowej ścieżki po nazwie domeny: jeden feed i sześć, a następnie dwadzieścia pięć pojedynczych zadań z różnych źródeł. Każdy test zakończył się bez błędu. Nie był to jednak dowód prawa do masowego archiwum — audyt wykazał między innymi, że regulamin Infor.pl nie pozwala na automatyczne wtórne użycie. Szeroka seria została zatem zatrzymana.
- Wprowadzono wersjonowaną instrukcję dostępu do źródła. Od tej chwili harvester wymaga jednocześnie: wskazanego kanału, zakresu, linku do warunków, dowodu, autora i daty przeglądu oraz minimum trzech sekund przerwy. „Mapa techniczna” bez instrukcji nie uruchamia już kolejki. To zmienia miarę postępu z liczby prób na liczbę legalnie i odtwarzalnie pobranych materiałów.
- Niezależny przegląd Claude Code potwierdził naprawę transportu, a także wykrył zbyt szeroką granicę zaufania. Po jego uwadze połączenie po nazwie domeny ograniczono wyłącznie do zadań mających zatwierdzoną instrukcję dostępu; niezweryfikowane i arbitralne URL-e zachowują ścieżkę z przypiętym adresem IP. Dodany test chroni także przekierowanie do adresu prywatnego. Wspólny test regresyjny przeszedł dla 58 przypadków.
- Zewnętrzny, niezależny audyt architektury zwrócił uwagę na głębszą zasadę: mały pilot nie może sam z siebie usprawiedliwiać pierwszego pobrania. Od tej chwili projekt rozdziela wąskie dopuszczenie testowe od zgody na pracę ciągłą, a sukces testu oznacza zgodną z instrukcją odpowiedź, nie tylko nowy box. Audyt ujawnił też, że starsze ścieżki RSS i oficjalnego API nie korzystają jeszcze z tej samej bramki dostępu co archiwum sitemap. Harvestery pozostają zatrzymane do czasu napisania testów odmowy oraz połączenia wszystkich kanałów we wspólną politykę.
- Drugi przegląd niezależnego modelu wykazał, że sama zgoda na odczyt mapy strony nie może dawać prawa do pobrania artykułów z HTML. Poprawkę zaprojektowano najpierw jako test odmowy, a następnie przeniesiono kontrolę do samego punktu transportu. Mapa wymaga odtąd instrukcji `sitemap`, a artykuł niezależnej instrukcji `html`. To zamknęło furtkę, w której nowy adapter mógłby przekazać sam tekstowy zakres i ominąć decyzję o dostępie.
- Kolejny przegląd domknął dwa pozornie nieaktywne moduły WordPress REST. Wcześniej katalogowa flaga techniczna mogła sama utworzyć zadanie archiwalne. Od tej chwili jest wyłącznie dowodem pomocniczym: przed zapisem kolejki system ponownie blokuje aktualne źródło i wymaga wersjonowanej instrukcji `api` dla konkretnego endpointu. Test odmowy najpierw potwierdził lukę, a po naprawie cała ścieżka WordPress przeszła 81 testów.
- Audyt egressu rozdzielił dwa pytania, które wcześniej łatwo było pomylić: czy wolno pobrać materiał oraz czy wolno użyć go później. Wprowadzono osobną, wersjonowaną decyzję użycia źródła. Pierwsze zastosowanie jest wąskie: bez jawnej decyzji historyczny box nie może wysłać nawet metadanych do zewnętrznego AI przy tworzeniu szkicu redakcyjnego. Nie zmieniono przy tym publicznego feedu ani nie usunięto żadnego boxa.

## Zasada dalszego zapisu

Kronika opisuje wydarzenia językiem zrozumiałym dla przyszłego czytelnika: co się wydarzyło, dlaczego miało znaczenie, kto lub które narzędzie uczestniczyło oraz jaki był wynik. Szczegółowe telemetrie pozostają w logach operacyjnych. Każdy wpis pomija sekrety i dane prywatne.

## 15 września 2026 — od liczby URL do dowodu pobrania

- Właściciel projektu zatrzymał pytanie „ile workerów uruchomić?” i przesunął środek ciężkości na pytanie „czy każdy pobrany materiał potrafimy obronić, wyjaśnić i ponownie odtworzyć?”. Ta zmiana uporządkowała kolejne prace: legalny kanał i jakość dowodu są ważniejsze niż maksymalna liczba równoległych procesów.
- Niezależne modele — Claude, Gemini, Qwen, GLM, MiniMax i Grok — otrzymały rozdzielone zadania: projekt widoków Dr Spina, kontrakt limitera hostów, decyzje użycia danych oraz adwersarialny przegląd pętli pobierania. Ich propozycje nie były wdrażane automatycznie. Porównanie ujawniło wspólny rdzeń: wersjonowana instrukcja dostępu, osobna decyzja użycia danych, ślad każdego requestu, limit całego hosta i jawne braki dowodowe.
- Wprowadzono datę ważności instrukcji dostępu. Wygasła albo niekompletna instrukcja jest odrzucana przez bramkę przed wyjściem do sieci. Kontrola migracji i 22 testy bramki zakończyły się powodzeniem.
- Audytor źródeł otrzymał stałą checklistę dziewięciu pytań: właściciel i host, endpoint, dowód warunków, zakres danych, robots i ograniczenia, tempo, granica URL, dane zbędne lub wrażliwe oraz data ponownej oceny. Istotniejsze i niejednoznaczne źródła wymagają drugiego przeglądu.
- Dr Spin otrzymał kierunek produktowy „Diagnoza kontekstu”. Pierwsze widoki nie będą udawały pełnego rozumienia artykułów: pokażą puls wydarzeń, kontekst zewnętrzny, ścieżkę dowodów i sieć połączeń. Odpowiedź ma rozdzielać „Ustalenia”, „Niewiadome” i „Co mogłoby zmienić diagnozę”. Ustalono, że liczba wspólnych wzmianek nie jest miarą prawdziwości ani siły relacji.
- Odrzucono pozornie precyzyjne procenty pewności oraz założenie, że sam tytuł, publiczny URL albo dokument instytucjonalny zawsze daje pełną zgodę na dowolne użycie. W interfejsie mają pozostać zrozumiałe typy dowodu: dokument urzędowy, zatwierdzona relacja, pojedyncze źródło, współwystępowanie, konflikt i niewiadoma.

## 15 września 2026 — bramka jako pojedyncze przejście

- Zespół niezależnych modeli skonfrontował pierwszą wersję trwałego limitera hostów. Gemini wskazał ważną lukę: sama trzysekundowa dzierżawa nie chroni wydawcy, kiedy odpowiedź trwa dłużej niż trzy sekundy. Drugi worker mógłby wtedy rozpocząć nakładające się pobranie.
- Poprawka zmieniła regułę z „co najmniej trzy sekundy od startu” na „najwyżej jedno aktywne pobranie, a następne dopiero trzy sekundy po zakończeniu”. Po awarii workera rezerwacja wygasa po ograniczonym czasie awaryjnym. Test symuluje wolną odpowiedź i potwierdza, że kolejny worker nie może jej wyprzedzić.
- Przekierowanie do innego hosta zostało zatrzymane na granicy transportu. Taki adres nie dziedziczy karty dostępu pierwotnego źródła; wymaga odrębnej, udokumentowanej decyzji.
- Kolejka archiwum rozróżnia odroczenie od awarii. Kiedy bramka odmawia z powodu tempa, zadanie wraca po wskazanym czasie bez naliczania błędu i bez fałszywego uruchamiania „lekarza źródła”.
- Claude Code przeprowadził ograniczony rekonesans jawnych API. Wynik nie stał się automatyczną zgodą: Sejm pozostaje jedynym przygotowywanym pilotem, a NBP, GUS/SDG, ELI i wybrane europejskie interfejsy trafiają najpierw do kolejki osobnego audytu kanału, warunków i zakresu.

## 15 września 2026 — dwa rodzaje prawdy o pobraniu

- Niezależne porównanie analiz C1, C2 i C3 domknęło mechanizm nieukończonych pobrań. Reaper oraz worker blokują ten sam rekord sterujący, dlatego tylko jeden z nich może zapisać końcowy fakt: wynik transportu albo uczciwe „nieukończona próba”.
- Doprecyzowano znaczenie dziennika: udany `FetchAttempt` potwierdza odbiór odpowiedzi od źródła, lecz nie udaje, że parser oraz zapis publicznego boxa zawsze już się udały. Błąd dalszego przetwarzania zatrzymuje publikację i trafia do diagnozy, zachowując prawdziwy ślad transportu.
- Lokalne testy potwierdziły rezerwację przed siecią, atomowy zapis dziennika, próg zawieszenia po trzech nieukończonych próbach oraz brak drugiego końca po wygranej reapera. Przed uruchomieniem realnego pilota pozostają dwa testy wyścigów na osobnych połączeniach PostgreSQL: worker kontra worker oraz dwa reapery na tym samym zestawie starych rezerwacji.
