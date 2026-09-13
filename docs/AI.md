# Przyszły asystent oparty na źródłach

## Decyzja dla obecnego MVP

Najpierw niezawodna baza i ręczne nitki administratora. Nie uruchamiamy publicznego automatycznego fact-checkera ani trenowania modelu na zebranych publikacjach. Obecna aplikacja nie wysyła materiałów do modelu AI i nie ponosi kosztów modelu.

## Następny etap

Istniejące `Article`, `OfficialRecord`, `OfficialRevision`, `EvidenceLink` i komentarze redakcji tworzą podstawę wyszukiwania z dowodami. Proponowany asystent najpierw pobierze pasujące fragmenty źródeł, następnie przygotuje szkic odpowiedzi lub nitki z odwołaniami do konkretnych rekordów. Takie podejście (RAG) umożliwia używanie aktualnej bazy bez ponownego trenowania modelu po każdym imporcie.

Przebieg: URL lub treść twierdzenia → rozbicie na sprawdzalne tezy → wyszukanie źródeł → chronologia → szkic z cytowaniami → zatwierdzenie administratora. Oryginalna wypowiedź, dowód i interpretacja muszą pozostać rozdzielone. Brak dowodu ma prowadzić do „nie da się ustalić z dostępnych materiałów”, nie do uzupełniania luk.

## Warunki rzetelności

- Każde ustalenie musi prowadzić do źródła i konkretnego fragmentu; same tagi nie wystarczą do potwierdzenia tezy.
- Źródło pierwotne może zawierać twierdzenia autora, które wymagają osobnego sprawdzenia. Urzędowa domena nie zmienia opinii ministra w niezależny werdykt.
- Weryfikacja cytatu wymaga jego dosłownego pokrycia z zapisanym tekstem. Model nie może tworzyć cytatów ani zgadywać dat.
- Głos posła odnosi się do dokładnego wniosku; nie daje podstaw do wnioskowania o intencjach.
- Źródła są niezaufaną treścią dla modelu. Polecenia ukryte w artykule nie mogą sterować agentem ani narzędziami.
- Testy jakości muszą obejmować różne strony polityczne, zmianę stanowiska w czasie, pomyłki nazwisk, sprzeczne źródła i pytania bez odpowiedzi.

Neutralność jest celem procedury i testów, nie gwarantowaną cechą dowolnego modelu. W pierwszej wersji AI tworzyłoby szkice dla redakcji; publikacja pozostaje decyzją człowieka. Kolejny etap można ograniczyć do „zadaj pytanie tej nitce”, co zawęża materiał i koszty.

## Co trzeba dołożyć

Pozyskanie pełnych tekstów na ustalonych zasadach, przechowywanie fragmentów i ich wersji, indeks wyszukiwania, identyfikatory cytowań, kolejka szkiców, limity kosztów i ewaluacja. Dopiero na danych z prawdziwych redakcyjnych ocen warto rozważyć dostrajanie modelu do formatu i stylu. Nie zastępuje ono aktualnego wyszukiwania źródeł.
