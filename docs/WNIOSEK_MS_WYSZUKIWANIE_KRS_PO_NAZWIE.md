# Wniosek do Ministerstwa Sprawiedliwości o udostępnienie wyszukiwania w KRS po nazwie (PROJEKT, 6.11.2026)

Status: **projekt do akceptacji właściciela; nic nie wysłano** (reguła 6: działania zewnętrzne tylko za zgodą właściciela).

## Po co
przeszłość.today łączy dane publiczne (dotacje UE, zamówienia, KRS). Część źródeł (np. lista projektów UE 2021-2027) podaje beneficjenta wyłącznie nazwą, bez NIP i KRS. Otwarte API KRS (`api-krs.ms.gov.pl`, usługi OdpisAktualny, OdpisPelny, Biuletyn) wyszukuje tylko po numerze KRS. Wyszukiwarka KRS dla użytkowników (strona wyszukiwarka-krs.ms.gov.pl) wyszukuje także po nazwie, województwie, powiecie, gminie i miejscowości, ale jej interfejs nie jest udokumentowany dla zewnętrznych aplikacji i wymaga klucza wbudowanego w stronę. **Nie używamy tego klucza ani nie podszywamy się pod aplikację urzędu.**

## Treść (do wysłania po akceptacji)
Szanowni Państwo,
prowadzimy serwis przeszłość.today (iapply sp. z o.o.), który łączy publiczne dane o podmiotach i dotacjach w celu zwiększenia przejrzystości wydatkowania środków publicznych. Korzystamy z otwartego API KRS (tylko dane podmiotów, bez danych osób, z limitem zapytań i pamięcią podręczną).
Prosimy o informację, czy Ministerstwo udostępnia (lub może udostępnić) **uprawniony, udokumentowany sposób wyszukiwania podmiotów w KRS po nazwie** (z możliwością zawężenia województwem, powiatem, gminą lub miejscowością), np. jako rozszerzenie otwartego API albo klucz dostępowy do usługi wyszukiwania. Zobowiązujemy się do: limitu najwyżej 1 zapytania na sekundę, identyfikowalnego User-Agenta z adresem kontaktowym, buforowania wyników, przetwarzania wyłącznie danych podmiotów (bez danych osób fizycznych) i zastosowania się do regulaminu oraz wskazanych limitów.
Z poważaniem, [imię i nazwisko właściciela], iapply sp. z o.o., [adres e-mail kontaktowy]

## Adresat i uwagi
- Ministerstwo Sprawiedliwości, Departament Informatyzacji i Rejestrów Sądowych (kontakt przez Portal Rejestrów Sądowych, prs.ms.gov.pl, zakładka Pomoc, albo ePUAP/e-mail instytucji); podstawa: art. 4b ust. 2 ustawy o KRS w zw. z ustawą o otwartych danych.
- Alternatywa komercyjna (wydatek, wymaga zgody właściciela): dostawcy własnej kopii rejestru (np. MGBI) z wyszukiwaniem po nazwie.
- Do oceny Prawnika: czy regulamin serwisu wyszukiwarki dopuszcza zautomatyzowane zapytania; do czasu odpowiedzi klient wyszukiwania po nazwie pozostaje wyłączony.
