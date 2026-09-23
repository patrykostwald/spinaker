# Zlecenie dla Claude Code — trzy narzędzia redakcyjne X

Pracujesz w `C:\Users\User\spin-clinic\.local\spinaker-mvp-frontend`.
Nie zmieniaj frontendowego układu strony głównej, infrastruktury Docker,
plików `.env` ani istniejącego procesu pobierania `news.political_polling`.
Nie commituj i nie pushuj.

Zaimplementuj wyłącznie panel redakcyjny dla już zapisanych `PoliticalPost`:

1. trzy widoki: „Przekaz obozu rządzącego”, „Przekaz opozycji”, „Kandydaci Dr
   Spina”;
2. pierwszy i drugi filtrują posty według `camp_at_collection`; trzeci pozwala
   redaktorowi wskazać posty z dowolnego obozu;
3. wynik ma być wyłącznie propozycją do przeglądu: cytat, link do posta,
   konto, data, materiały za i przeciw, pole niepewności oraz status;
4. nie wolno automatycznie publikować nitek, pisać oskarżeń ani przypisywać
   prawdziwości. Zatwierdzenie szkicu nie publikuje niczego;
5. użyj istniejących modeli `PoliticalAccount`, `PoliticalPost`,
   `PoliticalDraft` i zasad z `news.political_api.DRAFT_RULES`;
6. interfejs ma być dostępny tylko dla administratora/redaktora; nie wywołuj
   płatnego API X;
7. dodaj sensowne testy API i uruchom testy dotyczące zmienionych plików.

Na końcu podaj listę plików, wynik testów oraz niewdrożone zależności. Nie
usuwaj istniejącego kodu bez uzasadnienia.
