# Współdzielona bramka hosta — decyzja wdrożeniowa

## Stan obecny

Lokalny limiter w pamięci chroni wyłącznie pojedynczy proces. Nie jest podstawą do uruchamiania równoległego transportu z wielu procesów lub maszyn.

## Kontrakt

Bramka hosta otrzymuje żądanie dopiero po zatwierdzeniu instrukcji dostępu dla danego kanału i URL. Potem kolejność jest stała:

1. instrukcja dostępu;
2. rezerwacja okna hosta;
3. `robots.txt` i warunki źródła;
4. request;
5. rozliczenie wyniku.

Minimalne API to `acquire(host, worker_id)`, `enforce_429(host, retry_after, worker_id)` i odczyt czasu następnej możliwej próby. Rezerwacja trwa co najmniej trzy sekundy niezależnie od tego, jak szybko kończy się request.

## Właściciel blokady

Każda rezerwacja ma losowy identyfikator właściciela. Przedłużenie po `429` musi wykonywać porównanie właściciela z bieżącą blokadą. Inny worker nie może zmienić ani usunąć jej czasu wygaśnięcia. To samo dotyczy zwolnienia blokady.

## Etapy

- Lokalny MVP: jeden proces transportowy. SQLite nie jest bazą współdzielonego limitera.
- Środowisko z PostgreSQL: można wdrożyć tabelę rezerwacji i krótkie transakcje bez trzymania transakcji podczas I/O.
- Wiele maszyn / większa skala: Redis z atomowym `SET NX` i TTL oraz operacjami właścicielskimi CAS/Lua.

## Testy przed aktywacją

Na mock transporcie muszą przejść: wyłączność przy burst, niezależność różnych hostów, pełny odstęp trzech sekund, odzyskanie po awarii workera, globalna przerwa po `429` oraz odmowa przejęcia blokady przez obcego workera.

Do czasu ich przejścia nie zwiększamy liczby aktywnych procesów transportowych.
