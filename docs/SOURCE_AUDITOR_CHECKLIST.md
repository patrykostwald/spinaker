# Kolejność audytu źródła

Audytor sprawdza kanały zawsze w tej kolejności:

1. Udokumentowane oficjalne API oraz jego warunki i limity.
2. Otwarty zbiór danych, katalog danych publicznych, eksport CSV/JSON/XML/ZIP.
3. Oficjalny webhook, newsletter lub kanał syndykacyjny.
4. RSS / Atom.
5. Oficjalna sitemap, w tym sitemap wiadomości i indeks archiwalny.
6. Jawnie dozwolony HTML pojedynczej strony.

Przy każdym kanale zapisuje: URL dokumentacji lub warunków, zakres danych,
atrybucję, limit, status robots, możliwość archiwum historycznego i decyzję.
Brak jednoznacznej podstawy kończy automatyczne pobieranie i tworzy kartę do
kontaktu z wydawcą. Audytor nie wykonuje masowego pobierania.
