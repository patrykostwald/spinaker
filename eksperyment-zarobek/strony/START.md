# Strony zbudujmi.com: /social-media i /dostepnosc - wersje do publikacji (22.10.2026)

Pracujesz na gałęzi `cloud/zarobek-strony`, folder `eksperyment-zarobek/strony/`. Właściciel zatwierdził publikację obu stron;
publikuje koordynator (Kai) z Twoich plików. Ty niczego nie publikujesz i nigdzie nie wysyłasz.

## Wejście
- Strona social media: `git show origin/cloud/zarobek-rzemieslnik:eksperyment-zarobek/rzemieslnik/materialy/zbudujmi-social-media.html`
  (+ pakiet `.../DZIALANIA/P1.md`, cennik `.../materialy/cennik-social-start-rozwoj.md`).
- Strona dostępności: `git show origin/cloud/zarobek-audytor:eksperyment-zarobek/audytor/materialy/strona-dostepnosc.html`
  (+ `.../DZIALANIA/P3.md`, przykładowy raport `.../materialy/przyklad-raportu.html`).

## Do zrobienia
1. **Formularz:** adres `/api/zbudujmi/zapytanie/` nie istnieje. Podłącz oba formularze do istniejącego `POST /api/kontakt`
   (ten sam origin, JSON): `{pkg, desc, who, contact, token, hp, page, lang:"pl"}`, gdzie `desc` co najmniej 3 znaki,
   `contact` to e-mail albo telefon, `hp` to ukryte pole-pułapka (puste), `token` z Cloudflare Turnstile
   (skrypt `https://challenges.cloudflare.com/turnstile/v0/api.js`, sitekey `0x4AAAAAAFRyJ6A8ZcYfBLPP`, render jawny z callbackiem).
   Odpowiedzi: `{ok:true}`; 503 `{fallback:true}` = pokaż link `mailto:kontakt@iapply.pl` z gotową treścią; 422 = popraw pola.
2. **RODO pod formularzem** (krótko): administrator iapply sp. z o.o., pl. Wolności 16, 61-739 Poznań; cel: odpowiedź na zapytanie
   i przygotowanie oferty (art. 6 ust. 1 lit. b RODO); dane do czasu zakończenia rozmowy, nie dłużej niż 12 miesięcy; prawa:
   dostęp, sprostowanie, usunięcie, ograniczenie, sprzeciw, skarga do Prezesa UODO; link do `/polityka-prywatnosci/`;
   informacja o Cloudflare Turnstile jako zabezpieczeniu przed botami.
3. **Treść:** ceny zgodne z decyzjami (social media „Start” 1190 zł netto mies., pierwszy miesiąc 990 zł; „Rozwój” 1690 zł;
   przegląd dostępności 1490 zł netto). Bez nazw klientów (obecny klient tylko jako „sklep z odzieżą motocyklową”), bez obietnic
   zgodności prawnej (audyt techniczny, nie porada prawna), bez nazw konkurentów, bez liczb bez źródła.
4. **Design** (zasady z CLAUDE.md repo, sekcja Design): boksy z dociągnięciem góra/dół i równymi wysokościami, tytuły w jednej linii,
   najwyżej 2 kroje, cele dotyku 44 px, `noindex` na razie zostaw (właściciel zdecyduje o indeksowaniu), bez skryptów śledzących.
   Zrzuty 1440 i 390 px nie są tu możliwe, więc sprawdź układ w CSS na obie szerokości i opisz to w RAPORT.md.
5. Wynik: `eksperyment-zarobek/strony/social-media/index.html` i `eksperyment-zarobek/strony/dostepnosc/index.html`
   (wszystko w jednym pliku: CSS i JS w środku, bez zewnętrznych fontów poza tym, co już ma zbudujmi), plus `RAPORT.md`
   (co zmieniłeś, lista kontrolna).

Nie czytasz .env, nie zmieniasz niczego poza swoim folderem. Commit i push na `cloud/zarobek-strony` (pierwsza linia bez polskich
znaków, na końcu `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Celuj w ok. 45 minut. W ostatniej wiadomości najwyżej 10 linii.
