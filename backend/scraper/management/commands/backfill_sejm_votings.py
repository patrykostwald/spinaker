"""Incrementally import a reviewed range of Sejm term-10 voting records."""

from time import sleep

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from news.models import ImportState, SourceAccessInstruction
from scraper.access_gate import approved_instruction
from scraper.official import API, fetch_json, import_voting, official_source
from scraper.utils import HostRateLimited


STATE_NAME = "sejm-term10-voting-backfill"


class Command(BaseCommand):
    help = (
        "Wznawialny import głosowań Sejmu z podanego zakresu posiedzeń. "
        "Bez --apply nie wykonuje żądań."
    )

    def add_arguments(self, parser):
        parser.add_argument("--from-sitting", type=int, required=True)
        parser.add_argument("--to-sitting", type=int, required=True)
        parser.add_argument("--max-requests", type=int, default=12,
                            help="Najwyżej tyle żądań w jednym uruchomieniu (domyślnie 12).")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        first, last = options["from_sitting"], options["to_sitting"]
        maximum = options["max_requests"]
        if first < 1 or last < first:
            raise CommandError("Zakres posiedzeń jest nieprawidłowy.")
        if not 1 <= maximum <= 24:
            raise CommandError("--max-requests musi być w zakresie 1–24.")
        if connection.vendor != "postgresql":
            raise CommandError("Import wymaga PostgreSQL; SQLite nie jest bazą pilota.")

        source = official_source("sejm")
        first_list_url = f"{API}/sejm/term10/votings/{first}"
        first_detail_url = f"{first_list_url}/1"
        card = approved_instruction(source, SourceAccessInstruction.Channel.API, first_list_url)
        if not card or not approved_instruction(source, SourceAccessInstruction.Channel.API, first_detail_url):
            raise CommandError("Brak aktywnej karty API dla list i szczegółów głosowań kadencji 10.")

        if not options["apply"]:
            self.stdout.write(self.style.SUCCESS(
                f"GOTOWY: posiedzenia {first}–{last}, maks. {maximum} żądań; użyj --apply."))
            return

        state, _ = ImportState.objects.get_or_create(name=STATE_NAME)
        cursor = state.cursor or {}
        sitting = max(first, int(cursor.get("sitting", first)))
        next_vote = max(1, int(cursor.get("next_vote", 1))) if sitting == int(cursor.get("sitting", sitting)) else 1
        requests = imported = 0
        interval = float(card.minimum_interval_seconds) + 0.05

        def pause_before_request():
            nonlocal requests
            if requests:
                sleep(interval)
            requests += 1

        def defer_for_error(error):
            state.cursor = {"sitting": sitting, "next_vote": next_vote}
            state.last_error = f"Odroczono po błędzie transportu: {type(error).__name__}"[:200]
            state.save(update_fields=["cursor", "last_error"])
            self.stdout.write(self.style.WARNING(
                "ODROCZONO: błąd połączenia zapisany w audycie; kolejne uruchomienie wznowi import."))

        while sitting <= last and requests < maximum:
            try:
                pause_before_request()
                rows = fetch_json(f"/sejm/term10/votings/{sitting}")
            except HostRateLimited as exc:
                state.cursor = {"sitting": sitting, "next_vote": next_vote}
                state.last_error = f"Odroczono przez bramkę: {exc.retry_after_seconds:.1f}s"
                state.save(update_fields=["cursor", "last_error"])
                self.stdout.write(self.style.WARNING("ODROCZONO: bramka lub limit dzienny."))
                return
            except Exception as exc:
                defer_for_error(exc)
                return

            if not isinstance(rows, list):
                raise CommandError(f"Posiedzenie {sitting}: API nie zwróciło listy głosowań.")
            votes = sorted(
                row.get("votingNumber") for row in rows
                if isinstance(row, dict) and row.get("term") == 10
                and row.get("sitting") == sitting and isinstance(row.get("votingNumber"), int)
            )
            for vote in votes:
                if vote < next_vote:
                    continue
                if requests >= maximum:
                    state.cursor = {"sitting": sitting, "next_vote": vote}
                    state.save(update_fields=["cursor"])
                    self.stdout.write(self.style.SUCCESS(f"PAUZA: {imported} rekordów, limit uruchomienia."))
                    return
                try:
                    pause_before_request()
                    imported += int(bool(import_voting(10, sitting, vote)))
                except HostRateLimited as exc:
                    state.cursor = {"sitting": sitting, "next_vote": vote}
                    state.last_error = f"Odroczono przez bramkę: {exc.retry_after_seconds:.1f}s"
                    state.save(update_fields=["cursor", "last_error"])
                    self.stdout.write(self.style.WARNING("ODROCZONO: bramka lub limit dzienny."))
                    return
                except Exception as exc:
                    defer_for_error(exc)
                    return
                next_vote = vote + 1
                state.cursor = {"sitting": sitting, "next_vote": next_vote}
                state.imported += 1
                state.last_error = ""
                state.save(update_fields=["cursor", "imported", "last_error"])

            sitting += 1
            next_vote = 1
            state.cursor = {"sitting": sitting, "next_vote": next_vote}
            state.save(update_fields=["cursor"])

        self.stdout.write(self.style.SUCCESS(f"ZAKOŃCZONO: nowych rekordów={imported}, żądań={requests}."))
