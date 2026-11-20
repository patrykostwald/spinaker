# RAPORT: strony /social-media i /dostepnosc (22.10.2026)

Pliki do publikacji (wszystko w jednym pliku, CSS i JS w środku):
- `social-media/index.html` → zbudujmi.com/social-media/
- `dostepnosc/index.html` → zbudujmi.com/dostepnosc/

## Co zmieniłem

### Oba formularze
- Wysyłka `POST /api/kontakt` (ten sam origin, JSON): `{pkg, desc, who, contact, token, hp, page, lang:"pl"}`.
- Sprawdzenie w przeglądarce przed wysłaniem: `desc` co najmniej 3 znaki, `contact` = e-mail albo telefon (9-15 cyfr), błędne pola dostają `aria-invalid` i fokus.
- `hp` = ukryte pole-pułapka (poza ekranem, `tabindex=-1`, `aria-hidden`).
- Cloudflare Turnstile: skrypt `api.js?render=explicit&onload=tsReady`, sitekey `0x4AAAAAAFRyJ6A8ZcYfBLPP`, render jawny z callbackiem; token odświeżany po każdej próbie. Miejsce na widżet zarezerwowane (65 px), żeby nic nie skakało.
- Odpowiedzi: `{ok:true}` → podziękowanie i wyczyszczenie formularza; 503 / `{fallback:true}` → link „Wyślij to samo mailem” (`mailto:kontakt@iapply.pl` z gotowym tematem i treścią); 422 → komunikat i zaznaczenie pól z `errors`/`fields` (jeśli backend je zwraca); inny błąd lub brak sieci → ten sam link mailto. Gdy Turnstile się nie wczyta - też link mailto.
- Pod formularzem klauzula RODO: administrator iapply sp. z o.o., pl. Wolności 16, 61-739 Poznań; cel (art. 6 ust. 1 lit. b); okres do zakończenia rozmowy, max 12 miesięcy; prawa i skarga do Prezesa UODO; informacja o Turnstile; link `/polityka-prywatnosci/`.
- Usunięte stare zdanie „nie zapisujemy ich w bazie” (nie wiem, czy `/api/kontakt` zapisuje) i podstawa „lit. f”.

### /social-media
- `pkg`: `social-start`, `social-rozwoj`, `social-nie-wiem`; przyciski „Zapytaj o Start / Rozwój” ustawiają pakiet w formularzu. Adres profilu doklejany do `desc`.
- Ceny: Start 1190 zł netto/mies., pierwszy miesiąc 990 zł netto (cena po 1. miesiącu w tym samym zdaniu także w boksie u góry); Rozwój 1690 zł.
- Dodane: `noindex`, link „Przejdź do treści”, polityka prywatności w stopce, `summary` 44 px wysokości.

### /dostepnosc
- `pkg`: `dostepnosc-skan`. `desc` = adres strony + potwierdzenie uprawnienia + źródło `?z=` (np. `fb1`) + uwagi (nowe pole, nieobowiązkowe).
- Usunięty checkbox „zgoda” (podstawa to art. 6 ust. 1 lit. b, nie zgoda) i placeholder `[TREŚĆ KLAUZULI OD PRAWNIKA]`. Checkbox „zgłaszam stronę mojej instytucji” zostaje (wymagany).
- „Dlaczego teraz”: usunięte liczby 36% (źródło podaje 33,91%, niespójne) i „5 000 zł” oraz termin 31.03 (brak w ustawie). Zamiast nich 3 boksy bez liczb z linkiem do ustawy o dostępności cyfrowej (ISAP, Dz.U. 2019 poz. 848).
- Zdanie „audyt techniczny, nie porada prawna ani certyfikat zgodności” przy cenie i w stopce. Cena 1490 zł netto (1832,70 zł brutto).
- Boksy „Co dostajesz” dostały stopki (do 50 podstron / 10 podstron / w 5 dni roboczych) dla dociągnięcia do dołu.

## Lista kontrolna (zmierzone w Chromium, Playwright; Turnstile zablokowany w sesji, więc na zrzutach puste miejsce 65 px)

| Punkt | /social-media 1440 / 390 | /dostepnosc 1440 / 390 |
|---|---|---|
| 1. Dociąganie góra/dół (`auto 1fr auto`) | tak | tak |
| 2. Równe boksy w rzędzie (px) | karty 201 / 196, pakiety 428 / 448, kroki 227 / 196 | boksy 222 / 222, kroki 195 / 168 |
| 4. Tytuły w jednej linii (żaden nie ucięty) | tak | tak |
| 6. Pierwszy element pod paskiem | 40 / 28 px | 40 / 28 px |
| Poziome przewijanie | brak | brak |
| Cele dotyku ≥ 44 px (przyciski, pola, linki menu) | tak | tak |
| 7. Etykiety stanu małe, po prawej | tagi pakietów | - |
| 8. Kroje | 1 (systemowy) | 1 (systemowy) |
| 10. Odstępy na zmianie tła | sekcje 72 / 48 px góra i dół | jedno tło, sekcje 48 / 40 px |
| Tryb ciemny | nie (jasna strona ofertowa) | tak |
| `noindex` | tak | tak |
| Skrypty śledzące | brak | brak |

Testy formularza (podstawiony Turnstile i odpowiedzi API): pusty submit → komunikat walidacji; 200 → podziękowanie; 503 → link mailto; 422 → zaznaczone pole. Payloady zgodne z kontraktem.

## Do potwierdzenia przy publikacji (Kai)
1. Czy backend akceptuje wartości `pkg` (`social-start`, `social-rozwoj`, `social-nie-wiem`, `dostepnosc-skan`) - jeśli ma listę dozwolonych, podmienić w `<option value>` / `var PKG`.
2. Czy hostname zbudujmi.com jest dopisany do sitekey Turnstile.
3. Czy istnieje `/polityka-prywatnosci/` i czy wspomina Turnstile.
4. Jedno próbne zapytanie z każdej strony i sprawdzenie skrzynki.
5. Bez SRI na `api.js` Turnstile: Cloudflare nie wspiera `integrity` dla tego pliku (zmienia się bez wersji). Jeśli strona ma CSP, dopisać `challenges.cloudflare.com` do `script-src` i `frame-src`.
