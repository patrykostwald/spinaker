# Rejestr osób publicznych — zakres i stan

`PublicFigure` jest redakcyjnym rejestrem osób z publicznym głosem politycznym, także bez bieżącego mandatu. `ParliamentaryRosterEntry` jest odrębnym, technicznym rejestrem mandatów. Oba rejestry są dowodem roli, a nie dowodem tożsamości konta X.

## Działa obecnie

| Zakres | Oficjalne źródło | Zasada importu |
| --- | --- | --- |
| Aktywni posłowie | `https://api.sejm.gov.pl/sejm/term10/MP` | tylko rekordy `active: true` |
| Aktywni senatorowie | `https://www.senat.gov.pl/sklad/senatorowie/` | tylko profile z aktualnej listy Senatu |
| Polscy europosłowie | `https://data.europarl.europa.eu/api/v2/meps/show-current?format=application%2Fld%2Bjson` | tylko reprezentanci Polski (`PL`) |
| Premier, wicepremierzy i ministrowie | `https://www.gov.pl/web/premier/czlonkowie-rady-ministrow2` | tylko jednoznaczne pozycje z aktualnego składu Rady Ministrów |
| Oficjalnie podlinkowane konta X | oficjalne profile z powyższych rejestrów | tylko jawne linki `x.com` lub `twitter.com` znalezione na zatwierdzonym profilu |

Importer Rady Ministrów zatrzymuje się bez zapisu, gdy strona KPRM jest niejednoznaczna, zbyt krótka lub sprzeczna. Zmiana składu archiwizuje poprzedni wpis zamiast usuwać historię.

## Odkrywanie kont społecznościowych

Odkrywanie działa wyłącznie dla stron z zatwierdzonych domen:

- Sejm: `sejm.gov.pl`, `www.sejm.gov.pl`;
- Senat: `senat.gov.pl`, `www.senat.gov.pl`;
- Parlament Europejski: `europarl.europa.eu`, `www.europarl.europa.eu`, `data.europarl.europa.eu`.

System nie zgaduje handle'i z nazwiska, nie przeszukuje X po osobie i nie traktuje widocznego tekstu `@konto` jako dowodu. Zapisuje wyłącznie bezpośredni link z oficjalnej strony jako `SocialHandleEvidence` do późniejszego przeglądu redakcyjnego.

## Następne źródła rejestru

Kolejne adaptery będą dodawane pojedynczo, dopiero po sprawdzeniu oficjalnej strony, struktury danych i zasad archiwizacji:

1. Prezydent RP oraz kierownictwo KPRM;
2. marszałkowie i wicemarszałkowie Sejmu oraz Senatu;
3. marszałkowie województw, prezydenci miast i burmistrzowie największych miast;
4. strony kierownictwa ministerstw — sekretarze i podsekretarze stanu, których nie obejmuje skład Rady Ministrów;
5. oficjalne strony władz partii — liderzy, wiceliderzy, rzecznicy i inne osoby wskazane przez daną partię;
6. oficjalne strony klubów parlamentarnych — przewodniczący, rzecznicy i prezydia klubów;
7. szefowie najważniejszych organów państwa.

Każdy przyszły wpis wymaga: kanonicznego imienia i nazwiska, kategorii roli, organizacji, statusu, URL-a potwierdzającego oraz daty sprawdzenia. Przynależność polityczna pozostaje decyzją redakcyjną, nigdy automatycznym wnioskiem systemu.

Pełna kolejność pokrycia i wymagane oficjalne rostery są w
[PUBLIC_FIGURE_COVERAGE.md](PUBLIC_FIGURE_COVERAGE.md).

## Granice automatyzacji

- Rejestr nie tworzy automatycznie `PoliticalAccountCandidate` ani `PoliticalAccount`.
- Rejestr nie wykonuje zapytań do `api.x.com` i nie pobiera postów.
- Monitoring konta wymaga kolejno: dowodu, zatwierdzenia redaktora, weryfikacji prawdziwego ID w X i osobnego włączenia `Enabled`.
- Wpis zakończonej funkcji archiwizujemy; nie usuwamy go.
- Rejestr nie jest rankingiem, listą „wszystkich wpływowych osób” ani automatyczną klasyfikacją poglądów.

## Operacja redakcyjna

Aktualny skład Rady Ministrów można najpierw sprawdzić, a później zaimportować:

```powershell
docker compose exec backend python manage.py sync_public_figures --source cabinet --dry-run
docker compose exec backend python manage.py sync_public_figures --source cabinet
```

Listy mandatów i oficjalne dowody kont X obsługują osobne procedury opisane w [PARLIAMENTARY_ROSTER_IMPORT.md](PARLIAMENTARY_ROSTER_IMPORT.md) i [OFFICIAL_SOCIAL_DISCOVERY.md](OFFICIAL_SOCIAL_DISCOVERY.md).
