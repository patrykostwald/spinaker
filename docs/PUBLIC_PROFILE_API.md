# API profili osób publicznych

Te endpointy są publiczne i gotowe do podłączenia przez frontend. Nie zwracają PESEL-i, dat urodzenia, danych prywatnych ani niepotwierdzonych relacji.

## Lista

`GET /api/public-figures/?q=&role_category=`

Zwraca maksymalnie 100 aktywnych osób. Opcjonalne filtry:

- `q` — fragment imienia, roli lub organizacji;
- `role_category` — `government`, `party`, `parliamentary`, `european`, `local` albo `political`.

## Szczegóły

`GET /api/public-figures/:id/`

Odpowiedź zawiera podstawowe dane roli i trzy pola istotne dla widoku profilu:

- `organisations` — wyłącznie relacje potwierdzone przez redakcję, z nazwą podmiotu, rolą lub udziałem wskazanym w dowodzie, statusem obecna/historyczna oraz linkami do rejestru i dowodu; publiczny widok nie musi pokazywać numeru KRS;
- `votes` — maksymalnie 30 głosowań z krótkim tematem, głosem i linkiem źródłowym; dostępne tylko po ręcznym połączeniu profilu z wpisem sejmowym;
- `votes.available=false` — brak bezpiecznego połączenia z mandatem. Interfejs powinien pokazać neutralny komunikat, nie pustą tabelę ani przypuszczenie.
- `x_account` — konto X pojawia się wyłącznie wtedy, gdy jawny link na oficjalnym profilu przeszedł przegląd, kandydatura została potwierdzona przez oficjalne API X, a konto ma aktywne potwierdzenie redakcyjne. W innym wypadku pole ma wartość `null`.

Przykładowe fragmenty odpowiedzi:

```json
{
  "name": "Anna Publiczna",
  "role_title": "Ministra",
  "organisations": [{
    "name": "Fundacja Jawna",
    "krs_number": "0000123456",
    "kind": "foundation",
    "public_role": "członkini zarządu",
    "relation_status": "current",
    "evidence_url": "https://…"
  }],
  "votes": {
    "available": true,
    "results": [{"topic": "Ustawa o jawności finansowania", "vote": "Za", "source": "Sejm RP"}]
  }
}
```

## Redakcja

Przed pojawieniem się głosowań redaktor w panelu łączy `PublicFigure` z właściwym `ParliamentaryRosterEntry`. To połączenie jest ręczne i oparte na oficjalnym profilu, nie na samym podobieństwie nazw.
