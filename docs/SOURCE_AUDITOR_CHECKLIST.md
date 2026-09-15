# Checklista audytu źródła

Audytor bada kanały zawsze w tej kolejności:

1. Udokumentowane oficjalne API oraz jego warunki i limity.
2. Otwarty zbiór danych, katalog danych publicznych lub eksport CSV/JSON/XML/ZIP.
3. Oficjalny webhook, newsletter lub kanał syndykacyjny.
4. RSS / Atom.
5. Oficjalną sitemapę, w tym sitemapę wiadomości i indeks archiwalny.
6. Jawnie dozwolony HTML pojedynczej strony.

Audytor nie wykonuje masowego pobierania. Techniczna dostępność nie jest samodzielną podstawą decyzji.

## Dziewięć pytań przed utworzeniem instrukcji

Dla każdego kanału odpowiedź i dowód trafiają do karty źródła:

1. Kto jest właścicielem źródła i jaki jest kanoniczny host?
2. Jaki konkretny endpoint albo ograniczony wzorzec URL ma być używany?
3. Czy istnieje pierwotny dowód warunków, licencji, API albo ponownego wykorzystywania informacji?
4. Co dokładnie dowód pozwala pobrać: metadane, snapshot techniczny czy treść?
5. Czy robots.txt, `X-Robots-Tag`, regulamin albo warunki endpointu ograniczają ten kanał lub automatyczny dostęp?
6. Jaki minimalny odstęp, limit, sposób identyfikacji klienta i reguła `Retry-After` obowiązują?
7. Czy metoda prowadzi wyłącznie do zatwierdzonego endpointu, bez swobodnego podążania za linkami?
8. Czy zakres może zawierać dane niepotrzebne, prywatne, komentarze lub materiały osób trzecich? Jeżeli tak, czy należy go zawęzić?
9. Kiedy decyzja wygasa i co będzie sygnałem do ponownego audytu?

Brak jednoznacznej odpowiedzi na pytania 3–7 kończy automatyczne pobieranie. Audytor tworzy kartę do kontaktu z wydawcą albo odkłada źródło do ponownej oceny.

## Wersjonowanie i drugi przegląd

Jedna karta opisuje jeden kanał, endpoint i zakres. RSS nie uprawnia do HTML; sitemap nie uprawnia do API. Nowsza wersja karty jest nadrzędna wobec starszej, także gdy jest wstrzymana.

Drugi audytor przegląda przed zatwierdzeniem:

- źródła o dużym przewidywanym wolumenie;
- źródła, których warunki są niejednoznaczne;
- źródła z pełnym tekstem, OCR, RAG albo materiałami wrażliwymi;
- każdy wyjątek od standardowego kanału i limitu.

Różnica między decyzją pierwszego i drugiego przeglądu jest zapisana jako wynik kontroli jakości, nie jako powód do obchodzenia bramki.

## Dalsza obsługa

Zmiana warunków, robots.txt, endpointu, struktury odpowiedzi, wzrost 403/429/5xx lub wygaśnięcie karty wstrzymuje host do ponownego audytu. „Lekarz źródła” tylko diagnozuje i proponuje ścieżkę; nie uruchamia harvestera ani nie kontaktuje wydawcy samodzielnie.

Przed utworzeniem instrukcji audytor sprawdza, czy ten sam host nie jest już obsługiwany przez inne źródło lub drugi mechanizm. Dla jednego wydawcy aktywna jest jedna udokumentowana metoda, chyba że redakcja zatwierdzi wyjątek wraz z uzasadnieniem.
