# Gdzie AI i matematyka mogą legalnie dać przewagę: przegląd dla Polski (październik 2026)

Prywatny przegląd, nie porada prawna ani inwestycyjna. Źródła: desk research trzech niezależnych agentów i moje wyliczenia.
Części stron (lotto.pl, sejm.gov.pl) nie udało się otworzyć bezpośrednio, dlatego część liczb pochodzi ze źródeł wtórnych.
Takie miejsca oznaczam [DP] (do potwierdzenia).

## Najkrótsza odpowiedź
- W grach losowych (Lotto, zdrapki, ruletka, automaty, loterie promocyjne) przewagi nie ma i AI tego nie zmieni.
- Zakłady sportowe w Polsce zjada podatek 12% od stawki. Model musiałby być o ok. 14-20% lepszy od rynku, a najlepsze opisane
  w badaniach strategie dają kilka procent.
- Dodatni wynik jest realny tylko tam, gdzie liczy się umiejętność, a AI jest dozwolone: turnieje prognoz, konkursy analityczne,
  w mniejszym stopniu konkursy kreatywne i poker na żywo (po długiej nauce).
- Pewny punkt odniesienia: obligacje skarbowe dają ok. 4,4-5,6% rocznie bez ryzyka
  ([SII](https://www.sii.org.pl/19368/analizy/newsroom/obligacje-skarbowe-oprocentowanie-w-pazdzierniku-bez-zmian-pol-roku-stabilizacji.html)) [DP].
  Każdy pomysł poniżej trzeba z tym porównać.

## Tabela

| # | Pozycja | Legalne w PL | Wartość oczekiwana (EV) | Kapitał | Czas | Ocena 1-10 |
|---|---|---|---|---|---|---|
| 1 | Turnieje prognoz i botów (Metaculus) | tak, AI wprost dozwolone | dodatnia dla dobrych, wpisowe 0 zł | 0 zł | 5-20 h/mies. | **8** |
| 2 | Konkursy analityczne (Kaggle, AIMO) | tak, zasady per konkurs | dodatnia tylko dla czołówki | 0 zł (+ komputer) | 50-300 h/konkurs | **6** |
| 3 | Konkursy kreatywne firm (hasło, zdjęcie, przepis) | tak, poza ustawą hazardową | lekko dodatnia, ok. 10 zł/h [model] | 0 zł - koszt zakupu | 0,5 h/zgłoszenie | **5** |
| 4 | Bonusy i kupony „bez podatku” u legalnych bukmacherów | tak, u operatorów z listy MF | dodatnia, ale jednorazowa: setki zł łącznie [DP] | 500-2000 zł | 10-20 h | **4** |
| 5 | Poker na żywo w kasynie lub legalnym turnieju | tak, tylko na żywo | dodatnia dla nielicznych po latach nauki | 5-20 tys. zł | setki-tysiące h | **3** |
| 6 | Blackjack: liczenie kart w pamięci | tak, ale kasyno może zakazać wstępu | +0,5-1,5% przy grze z buta | 20-50 tys. zł | setki h | **3** |
| 7 | Zakłady sportowe na modelu (value betting) | tak, u legalnych | ujemna po podatku 12% | 5-20 tys. zł | dużo | **2** |
| 8 | Loterie promocyjne (losowanie nagród) | tak | zależy od nagród i liczby zgłoszeń, AI nic nie daje | koszt zakupu | mały | **2** |
| 9 | Lotto, Eurojackpot, Mini Lotto, Multi Multi, Keno, Ekstra Pensja | tak | ujemna zawsze, także przy kumulacjach | - | - | **1** |
| 10 | Zdrapki | tak | ujemna | - | - | **1** |
| 11 | Ruletka, automaty, kasyno online z RNG (Total Casino) | tak | ujemna (ruletka -2,7%) | - | - | **1** |
| 12 | Strony zagraniczne, Polymarket, Betfair, poker online | **NIE** | nieistotna: przestępstwo skarbowe | - | - | **0** |

## Szczegóły według pozycji

**1. Gry liczbowe Totalizatora.**
- Na nagrody idzie stały procent wpłat (Lotto co najmniej 51%, Eurojackpot 50%), więc EV jest ograniczone z góry
  ([regulamin Lotto](https://www.lotto.pl/storage/files/2020/4/17/68c4a918-14e7-45ba-b7ac-554b70fc138b/Regulamin%20gry%20liczbowej%20Lotto%20oraz%20Plus.pdf), [podział Eurojackpot](https://www.euro-jackpot.net/de/gewinnverteilung)).
- Szanse: Lotto 1 : 13 983 816 (C(49,6)), Eurojackpot 1 : 139 838 160 (C(50,5)·C(12,2)) - wyliczone.
- Moje wyliczenie (podatek 10%, dzielenie wygranej z innymi trafieniami, model Poissona, liczba sprzedanych zakładów [DP]):
  - Lotto przy kumulacji 50 mln zł i 20 mln zakładów: część za „szóstkę” daje 1,71 zł z 3 zł; z niższymi stopniami ok. 2,4 zł.
  - Rekord 57,8 mln zł (2016) podzieliło trzech zwycięzców
    ([se.pl](https://superbiz.se.pl/wiadomosci/wyniki-lotto-sa-zwyciezcy-do-podzialu-maja-60-mln-zlotych-aa-5LNW-4kBw-Dm8f.html)).
  - Eurojackpot przy maksimum 120 mln euro: część za główną wygraną daje ok. 2,5-3,1 zł z 12,50 zł, razem z niższymi stopniami
    ok. 5-6 zł.
- Wniosek: EV jest ujemne zawsze. Wybór rzadko typowanych liczb zmniejsza tylko ryzyko dzielenia się wygraną.
- Podatek: wygrana do 2280 zł jest zwolniona, wyższa płaci 10% od całości (art. 21 ust. 1 pkt 6a i art. 30 ust. 1 pkt 2 ustawy o PIT;
  [bezprawnik](https://bezprawnik.pl/ododatkowanie-wygranej/)).

**2. Zakłady bukmacherskie.**
- Legalni są tylko bukmacherzy z zezwoleniem MF; zakazane domeny są w rejestrze [hazard.mf.gov.pl](https://hazard.mf.gov.pl).
- Podatek 12% od stawki: ze 100 zł w grze jest 88 zł ([pit.pl](https://www.pit.pl/?p=12288)).
- Próg opłacalności przy kursie 2,00: p > 1/(0,88·2) = 56,8%, a przy uczciwych 50/50 i marży ok. 6% potrzeba 60,2% [marża DP].
- Kaunitz i in. (2017) zarobili ok. 5,5% na wirtualnych zakładach, po czym bukmacherzy ograniczyli im konta
  ([arXiv](https://arxiv.org/abs/1710.02824), [MIT Tech Review](https://www.technologyreview.com/2017/10/19/67760/the-secret-betting-strategy-that-beats-online-bookmakers/)).
- W Wielkiej Brytanii ograniczenia dostało 4,31% kont, częściej wygrywający
  ([iGB](https://igamingbusiness.com/sports-betting/operators-in-great-britain-player-account-restrictions-2024/)).
  Polscy bukmacherzy też limitują ([meczyki](https://meczyki.pl/bukmacherzy/limity-bukmacherskie/12)).
- Surebety po podatku wymagają sumy 1/kurs < 0,88, co praktycznie się nie zdarza.
- Dodatnie EV dają tylko bonusy powitalne i kupony bez podatku (np. Betclic, LVBET), jednorazowo
  ([meczyki](https://www.meczyki.pl/bukmacherzy/bonusy-bukmacherskie-i-promocjesprawdz-bukmacher-bonus-2020/81)) [DP].
- Betfair i inne giełdy zakładów nie mają polskiego zezwolenia.

**3. Poker.**
- Legalnego pokera online przeciwko innym graczom w Polsce nie ma; Total Casino oferuje tylko gry przeciw krupierowi
  ([prawo.pl](https://www.prawo.pl/biznes/poker-ma-wiele-ograniczen,534245.html)).
- Legalnie: turnieje w kasynach oraz turnieje poza kasynem z art. 6a ustawy o grach hazardowych - z nagrodami rzeczowymi do 50%
  kwoty bazowej, po zgłoszeniu dyrektorowi izby administracji skarbowej
  ([ifirma](https://www.ifirma.pl/blog/koncesje-zezwolenia-i-zgloszenia-na-gry-hazardowe-legalne-dzialania-hazardowe-2025/)).
- Nauka z solverami (GTO Wizard, PioSolver) poza grą jest legalna. Podpowiedzi w trakcie gry (RTA) są zakazane: w 2020 r.
  GGPoker zablokował za nie 40 kont i skonfiskował 1,18 mln USD
  ([PokerNews](https://www.pokernews.com/news/2020/09/ggpoker-responds-cheating-scandal-38050.htm)).
- Dobry wynik przy niskich stawkach to 3-6 dużych ciemnych na 100 rozdań; ok. 70% graczy jest na zero lub na minusie, a
  wiarygodna ocena wymaga ponad 100 tys. rozdań ([vip-grinders](https://vip-grinders.com/can-you-make-money-playing-poker)) [DP].
  Na żywo to 25-35 rozdań na godzinę, czyli tysiące godzin.

**4. Blackjack i gry kasynowe.**
- Strategia podstawowa: przewaga kasyna ok. 0,5%. Liczenie kart: przewaga gracza +0,5-1,5%
  ([Wizard of Odds](https://wizardofodds.com/games/blackjack/card-counting/introduction/)).
- Sąd Najwyższy stwierdził, że liczenie kart w pamięci nie jest zabronione
  ([II CSKP 1988/22](https://www.sn.pl/sites/orzecznictwo/orzeczenia3/ii%20cskp%201988-22.pdf)).
  Kasyno może jednak zgodnie z prawem zakazać wstępu ([prawo.pl, V ACa 576/22](https://www.prawo.pl/prawo/zakaz-wejscia-do-kasyna-nie-naruszyl-dobra-osobistego,523714.html)).
- Urządzenia przy stole są zakazane. Maszyny ciągłego tasowania całkowicie neutralizują liczenie; czy są w polskich kasynach [DP].
- Moje szacunki: przy 1% przewagi i średnim zakładzie 100 zł zysk to ok. 100 zł/h, a odchylenie ok. 1150 zł/h - wynik widać
  dopiero po setkach godzin.
- Ruletka z jednym zerem: -2,70% (1/37). Automaty i kasyno online z generatorem losowym (RNG) mają stałą ujemną EV, której
  żaden system ani AI nie zmieni. Wygrane u legalnych operatorów są zwolnione z PIT
  ([infor](https://ksiegowosc.infor.pl/podatki/inne-podatki-oplaty/5622440,podatek-od-gier.html)).

**5. Konkursy, loterie promocyjne, quizy, turnieje.**
- Loteria promocyjna (zwycięzców losuje się) wymaga zezwolenia izby administracji skarbowej
  ([prawo.pl](https://www.prawo.pl/biznes/konkurs-a-loteria-promocyjna-roznice-i-przepisy,533760.html)).
  Jest losowa, więc umiejętności nic w niej nie dają.
- Konkurs (zwycięzców wybiera się według kryteriów) nie podlega ustawie hazardowej; tu AI może pomóc w jakości zgłoszenia.
- Regulaminy coraz częściej zakazują AI albo wymagają ujawnienia:
  - [Konkurs Darwinowski 2026](https://www.psr.org.pl/regulamin-konkursu-darwinowskiego-2026/): całkowity zakaz,
  - [Sieć Obywatelska 2026](https://siecobywatelska.pl/wp-content/uploads/2026/09/Regulamin-konkursu-25-lat-2.pdf):
    AI tylko w osobnej kategorii,
  - [Politechnika Poznańska](https://architektura.put.poznan.pl/sites/default/files/2025-04/2.%20REGULAMIN_konkursu_kabina%20tramwaju.pdf):
    deklaracja użycia AI.
- Typowe zapisy: jedno zgłoszenie na osobę i przeniesienie praw autorskich.
- Podatek: nagrody ze sprzedaży premiowej do 2000 zł są zwolnione (art. 21 ust. 1 pkt 68 ustawy o PIT;
  [podatki.biz](https://www.podatki.biz/artykuly/sprzedaz-premiowa-i-zwolnienie-z-pit-dla-nagrod-o-niskiej-wartosci_60_59412.htm)),
  powyżej płaci się 10%.
- Model zarobku [DP]: nagroda 500 zł, 200 zgłoszeń, podwojona szansa dzięki jakości - ok. 5 zł na zgłoszenie, ok. 10 zł/h.
- Turnieje prognoz i botów na Metaculus: ok. 175 tys. USD rocznie w pulach, AI jest tu wprost celem
  ([LessWrong](https://www.lesswrong.com/posts/E7wxQnBvYxgB3rTTk/announcing-metaculus-summer-2026-futureeval-bot-tournament),
  [EA Forum](https://forum.effectivealtruism.org/posts/hrJrsgMCwsdBuAqgQ/announcing-fall-2026-futureeval-bot-tournament)).
- Kaggle i AIMO (fundusz 10 mln USD): nagroda wymaga publikacji kodu, konkurencja jest bardzo silna
  ([AIMO](https://aimo.xtxmarkets.com/participate)).
- Podatek od nagród od zagranicznych organizatorów [DP].

**6. Inne.**
- Bug bounty: rynek zalany słabymi zgłoszeniami z AI; curl zamknął płatny program w 2026 r.
  ([BleepingComputer](https://bleepingcomputer.com/news/security/curl-ending-bug-bounty-program-after-flood-of-ai-slop-reports/)).
  Wartość ma tylko dla kogoś, kto sam zna bezpieczeństwo.
- Polymarket jest w rejestrze zakazanych domen od stycznia 2025 r. [DP data], więc gra przez VPN to przestępstwo skarbowe.

## Ranking
1. Turnieje prognoz i botów (Metaculus)
2. Konkursy analityczne (Kaggle)
3. Konkursy kreatywne bez zakazu AI
4. Jednorazowe bonusy u legalnych bukmacherów
5. Poker na żywo
6. Liczenie kart
7. i dalej: wszystko z ujemną EV

## Rekomendacje i plany małych testów (bez ryzyka)
1. **Turniej prognoz na Metaculus (4 tygodnie, 0 zł).**
   - Znajomy rejestruje się sam i co tydzień prognozuje 10 pytań; AI pomaga zbierać źródła i liczyć prawdopodobieństwa.
   - Miara: wynik Brier lub punkty względem mediany społeczności.
   - Dalej tylko wtedy, gdy wynik jest powyżej mediany; następny krok to prosty bot w turnieju FutureEval.
2. **Trzy konkursy kreatywne bez zakazu AI (2 tygodnie, 0 zł).**
   - Przed każdym zgłoszeniem czyta się cały regulamin: czy AI jest dozwolone, czy trzeba je ujawnić, ile zgłoszeń na osobę.
   - Zapis: czas, nagroda, wynik. Po 10 zgłoszeniach liczy się złote na godzinę.
3. **Value betting na papierze (8 tygodni, 0 zł).**
   - Model AI wskazuje zakłady, ale zapisuje się je tylko w arkuszu, z kursem w chwili typowania i kursem zamknięcia.
   - Test zaliczony dopiero wtedy, gdy wynik po odjęciu 12% podatku jest dodatni na co najmniej 300 zakładach. Według tego
     przeglądu to mało prawdopodobne, więc test głównie oszczędza pieniądze.

## Nie warto (i dlaczego)
- **Lotto, Eurojackpot, Keno, zdrapki:** stały odsetek wpłat na nagrody, więc EV jest ujemne także przy kumulacjach
  (wyliczenie wyżej). „Systemy” i analiza historii losowań nic nie dają, bo losowania są niezależne.
- **Ruletka, automaty, kasyno online:** stała przewaga kasyna, a progresje typu Martingale nie zmieniają sumy EV.
- **Loterie promocyjne:** czysty los, a AI nic nie daje.
- **Zakłady sportowe na modelu:** podatek 12% od stawki wymaga nierealnej przewagi, a wygrywającym bukmacherzy limitują konta.
- **Liczenie kart:** mała przewaga, duży kapitał, setki godzin i zakaz wstępu do kasyna po wykryciu.
- **Bug bounty z AI bez własnej wiedzy:** zgłoszenia są odrzucane, a za spam grozi ban.

## Czego NIE wolno (twarde granice)
- **Gra u nielegalnych operatorów:** zagraniczne kasyna, bukmacherzy, poker online, Polymarket, Betfair. Grozi za to grzywna do
  120 stawek dziennych, teoretycznie od ok. 1,6 tys. do 7,7 mln zł, i przepadek wygranej (art. 107 § 2 i art. 30 § 5 k.k.s.;
  [lexlege](https://lexlege.pl/kks/art-107/)). Także przez VPN.
- **Urządzenia, aplikacje i podpowiedzi AI przy stole lub w trakcie rozdania** (RTA, liczniki kart, kamery).
- **Boty grające za człowieka** tam, gdzie regulamin tego nie przewiduje.
- **Wiele kont,** konta na rodzinę lub znajomych, „bonus abuse” wbrew regulaminowi.
- **Łamanie regulaminów konkursów:** zgłaszanie treści AI tam, gdzie są zakazane, ukrywanie użycia AI, cudze utwory,
  więcej zgłoszeń niż wolno.
- Gra jest dozwolona od 18 lat.

## Do potwierdzenia (dla Prawnika)
Aktualny podział puli w Lotto (49% czy 43-44%), ceny Keno i Ekstra Pensji, odsetek wygranych w zdrapkach, minimalne RTP automatów,
data wpisu Polymarketu do rejestru, maszyny ciągłego tasowania w polskich kasynach, marża polskich bukmacherów, podatek od nagród
od zagranicznych organizatorów konkursów.
