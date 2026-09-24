# Official parliamentary roster staging

`sync_parliamentary_roster` imports only official roster data into a staff-only review list. It never calls X, creates `PoliticalAccountCandidate`, enables polling, or removes records.

## Commands

```powershell
docker compose exec backend python manage.py sync_parliamentary_roster --source sejm --dry-run
docker compose exec backend python manage.py sync_parliamentary_roster --source sejm
docker compose exec backend python manage.py sync_parliamentary_roster --source senat --dry-run
docker compose exec backend python manage.py sync_parliamentary_roster --source senat
docker compose exec backend python manage.py sync_parliamentary_roster --source ep --dry-run
docker compose exec backend python manage.py sync_parliamentary_roster --source ep
```

The Sejm adapter reads the official current-term endpoint:
`https://api.sejm.gov.pl/sejm/term10/MP`

Only rows marked `active: true` are staged. A successful non-empty, unique source response may mark previously seen entries absent from that response as inactive; it never deletes them.

The Senate adapter reads the official current roster page:
`https://www.senat.gov.pl/sklad/senatorowie/`

It uses only official profile links from the current list and excludes list items explicitly marked `mandat wygasł` or `zmarł`. It fails without writing if the HTML is empty, ambiguous between terms, contains conflicting profile data, or returns fewer than 50 active profiles. It does not visit individual profile pages.

The European Parliament adapter reads the official current-members JSON-LD endpoint:
`https://data.europarl.europa.eu/api/v2/meps/show-current?format=application%2Fld%2Bjson`

It stages only entries whose official `api:country-of-representation` is `PL`. The endpoint supplies the EU political group (`api:political-group`) and that value is stored verbatim in **club**. It does not supply a national-party field, so the importer does not infer one. The review link is the stable official EP person URI.

No migration performs web requests.

Review imported entries in Django admin under **Parliamentary roster entries**. The roster is evidence for editorial review, not proof of an X identity.
