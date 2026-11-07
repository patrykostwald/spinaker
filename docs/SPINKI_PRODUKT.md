# Spinki: produkt społecznościowy (specyfikacja robocza, 9.10.2026)

Stan: plan, nic nie zbudowane. Zasady podane przez właściciela 9.10.2026. Spinki stają się osobnym produktem (domena spina3.pl po zakupie), a z spin.clinic znika cała sekcja spinek (patrz PLAN_AKTUALNY.md). Produkt ma być czysto społecznościowy, nie narzędziem dla dziennikarzy.

## Idea
Ściana kafelków. Każdy kafelek to box z naszej bazy (materiał: artykuł, wpis, film, diagnoza, dokument). Działa w pełni po podpięciu mediów. W prawym rogu boxa jest miejsce na spinkę; jej kolor zależy od reakcji użytkowników. Spinka pokazuje, co użytkownicy zrobili z boxem: reakcje i, przede wszystkim, przypięcia z komentarzem.

## Zasady (decyzje właściciela)
1. **Jedno przypięcie na użytkownika i box.** Użytkownik może do danego boxa przypiąć tylko jedną rzecz, jeden raz (unikalność w bazie: użytkownik + box; zmiana lub usunięcie przypięcia jest dozwolone, ale w danym momencie obowiązuje jedno).
2. **Dwa rodzaje przypięcia:**
   - **A. Materiał z naszej bazy:** użytkownik przypina inny box. To przypięcie ma komentarz użytkownika i reakcję (określa „jak ten materiał ma się do tego boxa”).
   - **B. Treść dodana przez użytkownika:** użytkownik dodaje coś własnego (to jest hosting, patrz niżej). Zakres typów treści do ustalenia (np. tylko odnośnik i tekst na start; zdjęcia lub pliki później).
3. **Ciąg.** Z własnych przypięć użytkownik może ułożyć ciąg (uporządkowaną listę) z tytułem i opisem. W ciągu każdy box występuje najwyżej raz, z jednym przypięciem. Ciąg jest publiczny (opcjonalnie szkic).
4. **Spinka = suma tego, co użytkownicy zrobili z boxem:** liczba przypięć, rozkład reakcji i komentarze. Kolor spinki wynika z rozkładu reakcji (skala kolorów zgodna z zasadą „siła spinu: zielony > niebieski > czerwony” z design-system albo nowa skala, do decyzji).
5. **Reakcje:** jedna reakcja dodatnia lub ujemna na obiekt na użytkownika (jak dziś dla boxów), zmiana zastępuje poprzednią. Komentarz do przypięcia najwyżej jeden na użytkownika.

## Model danych (szkic, do uzgodnienia przed budową)
- `Pin(id, user, box, kind: 'internal'|'user_content', target_box|null, content_id|null, comment, created_at, updated_at, status)`; unikalność (user, box).
- `UserContent(id, user, type: 'link'|'text'|'image', payload, moderation_status, reported_count)`; relacja jeden do jednego z Pin typu B.
- `PinReaction(pin, user, value: -1|+1, comment|null)`; unikalność (pin, user).
- `Chain(id, user, title, description, is_public)` i `ChainItem(chain, pin, position)`; unikalność (chain, pin).
- `BoxSpinka` (zmaterializowany widok lub pole w cache): agregat do koloru i liczników, przeliczany przy zmianie reakcji.
- Migracja z istniejących spinek: eksport i archiwum (spinki, oceny połączeń, przepięcia), bez automatycznego importu do nowego modelu.

## Hosting i prawo (przed startem)
Treści użytkowników (typ B, komentarze, ciągi) oznaczają, że jesteśmy usługą hostingową. Potrzebne: regulamin i polityka prywatności, zasady dla małoletnich, mechanizm zgłaszania i usuwania treści (powiadomienie i działanie, uzasadnienie decyzji), moderacja (narzędzia i procedura, w tym szybkie ukrycie), ograniczenia typu treści (bez zdjęć osób prywatnych, bez danych osobowych osób niepublicznych), blokady kont i limity, odpowiedzialność za treści o osobach publicznych (dobra osobiste, sprostowania). Przy treści typu B z plikami dochodzi prawo autorskie. Pytania zapisane w `Desktop\projekty\spin-clinic-maile\licencje\pytania-do-prawnika.md` (G.15); dodatkowe pytania poniżej.
- Czy na start dopuszczamy tylko odnośniki i tekst (bez plików i zdjęć), żeby ograniczyć ryzyko?
- Czy konieczna jest weryfikacja konta (adres e-mail, wiek) przed pierwszym przypięciem typu B?
- Jak oznaczać, że treść pochodzi od użytkownika, a nie od Dr. Spina i nie z naszej bazy (żeby nie przypisywać nam cudzych twierdzeń)?

## Zależności
- Podpięcie mediów (ściana kafelków wymaga materiałów z bazy).
- Konta użytkowników (jest w repo: konta, komentarze, reakcje, ThreadOpinion, ThreadFavorite, PersonalContextThread).
- Domena spina3.pl (zakup po stronie właściciela) i osobna aplikacja frontendowa lub wspólny kod z `packages/ui`.

## Etapy (przyszłość, po aplikacji spin.clinic i raportach)
1. Zamrożenie i eksport obecnych spinek (zadanie 2 planu).
2. Model danych i API: przypięcie typu A (z bazy), komentarz, reakcja, kolor spinki.
3. Ściana kafelków i widok boxa ze spinkami.
4. Ciągi.
5. Przypięcia typu B (treści użytkowników) razem z moderacją i regulaminem.

## Decyzje właściciela z 9.10.2026 (odpowiedzi na pytania)
1. **Skala kolorów:** może zostać zielony-niebieski-czerwony; właściciel jest otwarty na inne opcje (do rozważenia przy projekcie).
2. **Autor ciągu:** jeden autor (rekomendacja Claude: jeden autor na start, bo współtworzenie dokłada uprawnienia, spory i moderację; później można dodać „rozwidlenie” cudzego ciągu jako własnej kopii).
3. **Przypięcie typu A z linku:** wolno wskazać link spoza bazy; my go badamy i dodajemy do bazy jako nowy box (kolejka weryfikacji linków, ta sama klasyfikacja i kontrola co dla innych materiałów, z zachowaniem praw autorskich: tytuł, data, redakcja, odnośnik).
4. **Ściana główna:** ściana kafelków jest stroną główną spina3.pl. W kafelkach zmieniają się cyklicznie: miniaturka, post, autor posta i wskaźniki reakcji (spinki). Realizacja później.

## Otwarte pytania do właściciela
- Z jakich pól składa się kafelek na ścianie i co jest w nim domyślne (miniaturka czy post)?
- Kolejka weryfikacji linków dodawanych przez użytkowników: automatyczna kontrola (typ materiału, źródło, język) i kiedy człowiek?
