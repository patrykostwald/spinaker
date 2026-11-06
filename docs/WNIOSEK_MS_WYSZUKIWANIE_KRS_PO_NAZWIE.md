# Wniosek do Ministerstwa Sprawiedliwości o udostępnienie wyszukiwania w KRS po nazwie (PROJEKT, 6.11.2026)

Status: **tekst gotowy z danymi właściciela (Patryk Ostwald, patryk@iapply.pl); wysyła właściciel sam, nic nie wysłano** (reguła 6: działania zewnętrzne tylko za zgodą właściciela).

## Po co
przeszłość.today łączy dane publiczne (dotacje UE, zamówienia, KRS). Część źródeł (np. lista projektów UE 2021-2027) podaje beneficjenta wyłącznie nazwą, bez NIP i KRS. Otwarte API KRS (`api-krs.ms.gov.pl`, usługi OdpisAktualny, OdpisPelny, Biuletyn) wyszukuje tylko po numerze KRS. Wyszukiwarka KRS dla użytkowników (strona wyszukiwarka-krs.ms.gov.pl) wyszukuje także po nazwie, województwie, powiecie, gminie i miejscowości, ale jej interfejs nie jest udokumentowany dla zewnętrznych aplikacji i wymaga klucza wbudowanego w stronę. **Nie używamy tego klucza ani nie podszywamy się pod aplikację urzędu.**

## Treść (gotowa do wysłania przez właściciela; stan 6.11.2026)
**Temat:** Zapytanie o uprawniony sposób wyszukiwania podmiotów w KRS po nazwie oraz o zakres dozwolonego korzystania z otwartego API KRS

Szanowni Państwo,

prowadzimy serwis przeszłość.today (iapply sp. z o.o.), który łączy publiczne dane o podmiotach, zamówieniach i dotacjach w celu zwiększenia przejrzystości wydatkowania środków publicznych. Korzystamy z otwartego API KRS (usługi OdpisAktualny, OdpisPelny, Biuletyn; zapytania o numery KRS, z limitem zapytań i pamięcią podręczną; dane podmiotów).

Prosimy o odpowiedź na dwa pytania:

1. Czy Ministerstwo udostępnia lub może udostępnić uprawniony, udokumentowany sposób **wyszukiwania podmiotów w KRS po nazwie** (z możliwością zawężenia województwem, powiatem, gminą lub miejscowością), np. jako rozszerzenie otwartego API albo klucz dostępowy do usługi wyszukiwania? Na jakich warunkach (wniosek, decyzja, opłaty)?

2. Czy dotychczasowy sposób korzystania z otwartego API KRS, opisany powyżej, mieści się w dozwolonym zakresie po zmianach ustawy o KRS dotyczących dostępu przez usługi sieciowe? Jeśli nie, prosimy o wskazanie, co należy zmienić.

Zobowiązujemy się do: limitu najwyżej 1 zapytania na sekundę, identyfikowalnego nagłówka User-Agent z adresem kontaktowym, buforowania wyników, przetwarzania wyłącznie danych podmiotów (bez danych osób fizycznych z tego trybu), stosowania się do regulaminu i wskazanych limitów.

Z poważaniem,
Patryk Ostwald
iapply sp. z o.o.
patryk@iapply.pl

## Adresat i uwagi
- Ministerstwo Sprawiedliwości, Departament Informatyzacji i Rejestrów Sądowych (kontakt przez Portal Rejestrów Sądowych, prs.ms.gov.pl, zakładka Pomoc, albo ePUAP/e-mail instytucji); podstawa: art. 4b ust. 2 ustawy o KRS w zw. z ustawą o otwartych danych.
- Alternatywa komercyjna (wydatek, wymaga zgody właściciela): dostawcy własnej kopii rejestru (np. MGBI) z wyszukiwaniem po nazwie.
- Do oceny Prawnika: czy regulamin serwisu wyszukiwarki dopuszcza zautomatyzowane zapytania; do czasu odpowiedzi klient wyszukiwania po nazwie pozostaje wyłączony.
