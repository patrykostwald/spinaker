"""Reviewed agent identities. Scheduling and telemetry come from Celery and cache."""
from copy import copy
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.utils import timezone

from news.repairer import flag, stamp
from news.task_heartbeat import cadence

WARSAW = ZoneInfo('Europe/Warsaw')


def agent(name, description, task, env='', default=False, collector=False, cost=''):
    return dict(name=name, description=description, task=task, flag=env,
                default=default, collector=collector, cost=cost)


REGISTRY = {
    'raportysta': agent('Raportysta', 'Przygotowuje analizy dla instytucji, recenzje i pliki do zatwierdzenia.', 'news.tasks.institutional_reports_task', 'REPORTS_ENABLED'),
    'schedule-health': agent('Kontrola dostępności', 'Sprawdza klucze, wolny dysk i pulsy zadań co 6 godzin.', 'news.tasks.schedule_health_task', default=True),
    'video-stats': agent('Koszt filmów', 'Sprawdza dzienny koszt opracowania filmów.', 'news.tasks.clinic_video_stats_task', default=True),
    'social-assistant': agent('Asystent social media', 'Odpowiada na pytania osoby od publikacji. Tylko darmowe modele, domyślnie do 30 prób dziennie.', 'news.social_assistant.answer_question', default=True),
    'plain-editor': agent('Redaktor prostoty', 'Pisze krótki pierwszy ekran po korekcie języka diagnozy.', 'news.tasks.clinic_diagnose_task', 'CLINIC_AI_ENABLED'),
    'plain-meter': agent('Miernik', 'Bez AI sprawdza długość, powtórzenia i proste słowa.', 'news.tasks.clinic_diagnose_task', 'CLINIC_AI_ENABLED'),
    'plain-guard': agent('Strażnik rzetelności', 'Bez AI sprawdza cytaty, techniki i słownik zarzutów.', 'news.tasks.clinic_diagnose_task', 'CLINIC_AI_ENABLED'),
    'plain-reader': agent('Czytelnik testowy', 'Co tydzień czyta do 20 losowych prostych diagnoz i zapisuje raporty w panelu.', 'news.tasks.plain_reader_task', 'PLAIN_READER_ENABLED'),
    'dr-spin': agent('Dr. Spin', 'Diagnozuje wpisy polityków z pomocą Konsylium.', 'news.tasks.clinic_diagnose_task', 'CLINIC_AI_ENABLED', cost='diagnoses'),
    'council': agent('Konsylium', 'Uzupełnia deklaracje Karty członków Konsylium.', 'news.tasks.council_charter_missing_task'),
    'screen': agent('Strażnik wpisów', 'Wybiera wpisy warte diagnozy.', 'news.tasks.clinic_screen_task', 'CLINIC_AI_ENABLED'),
    'warden': agent('Strażnik kont', 'Sprawdza tożsamość i aktywność obserwowanych kont.', 'news.tasks.account_warden_task', cost='warden'),
    'repairer': agent('Naprawiacz', 'Analizuje błędy i proponuje działania właścicielowi. Nie zmienia produkcji.', 'news.tasks.repairer_task', 'REPAIRER_ENABLED', True),
    'auditor': agent('Audytor', 'Sprawdza kondycję i wyniki Konsylium.', 'news.tasks.council_audit_task'),
    'inquisitor': agent('Inkwizytor', 'Niezależnie kontroluje jakość diagnoz.', 'news.tasks.inquisitor_task'),
    'konsylium-powtorz': agent('Kworum Konsylium', 'Co noc o 2:40 powtarza diagnozy wystawione bez kworum (za mało modeli albo stałego rdzenia); stary wynik zostaje w historii.', 'news.tasks.konsylium_powtorz_task', 'CLINIC_AI_ENABLED'),
    'recruiter': agent('Rekruter', 'Sprawdza kandydatów do Konsylium.', 'news.tasks.council_recruiter_task'),
    'strateg': agent('Strateg', 'Proponuje rozwój serwisu w wolnym oknie modeli.', 'news.tasks.agents_window_task', 'AGENTS_ENABLED'),
    'pilgrim': agent('Pielgrzym', 'Szuka usprawnień Konsylium na zmianę ze Strategiem.', 'news.tasks.agents_window_task', 'AGENTS_ENABLED'),
    'reports': agent('Raporty Stratega i Pielgrzyma', 'Podsumowuje propozycje tygodnia lub miesiąca.', 'news.tasks.agents_report_task', 'AGENTS_ENABLED'),
    'duty': agent('Dyżurny', 'Co 5 minut sprawdza wszystko: zbieracz X, dostawców modeli, diagnozy, wywiady, przekazy, spinki, budżet i zadania; o problemach pisze mailem.', 'news.tasks.duty_task', 'DUTY_ENABLED', True),
    'interview-candidates': agent('Kandydaci na wywiad dnia', 'Zbiera kandydatów do głosowania na wywiad dnia.', 'news.tasks.clinic_interview_candidates_task', default=True),
    'moderation-mail': agent('Poczta moderacji', 'Ponawia wysyłkę e-maili z decyzjami moderacji spinek.', 'news.notification_tasks.retry_thread_moderation_mail', 'THREADS_ENABLED'),
    'narrative-threads': agent('Spinka narracji dnia', 'Układa spinkę narracji dnia dla każdej strony według jawnego kryterium.', 'news.tasks.narrative_thread_task', 'THREADS_ENABLED'),
    'signal-threads': agent('Sygnały i narracje', 'Bez AI wykrywa sygnały lobbingu przy drukach i nowe narracje; układa szkice spinek.', 'news.tasks.signal_threads_task', 'THREADS_ENABLED'),
    'thread-review': agent('Kontrola spinek', 'Miernik, recenzent merytoryczny, redaktor tytułów i językoznawca poprawiają każdą spinkę Dr. Spina; zdejmują ją tylko przy odrzuceniu.', 'news.tasks.thread_reviews_task', 'THREADS_ENABLED'),
    'recenzent': agent('Recenzent', 'Co 2 godziny czyta nowe treści (spinki, przekazy, raporty, diagnozy), raz w tygodniu wszystkie stałe teksty stron; cztery perspektywy: językoznawca, dziennikarz, rzetelność, czytelnik; raporty i spinki odsyła do poprawki, diagnozy tylko zgłasza.', 'news.tasks.recenzent_task', 'AGENTS_ENABLED'),
    'projektant': agent('Projektant UX/UI', 'Co tydzień uczy się całej branży (dla spin.clinic i zbudujmi.com) (Nielsen Norman, Smashing, web.dev, Awwwards i inne), aktualizuje przewodnik i przegląda wszystkie strony serwisu; proponuje poprawki.', 'news.tasks.projektant_task', 'AGENTS_ENABLED'),
    'przeszlosc-topics': agent('Tematy dnia przeszłość.today', 'Codziennie wybiera najbogatsze tematy z druków Sejmu i wpisów polityków (ta sama reguła dla wszystkich).', 'news.tasks.przeszlosc_topics_task', 'PRZESZLOSC_ENABLED'),
    'przeszlosc-alerts': agent('Alerty przeszłość.today', 'Codziennie o 7:00 jeden list na adres z nowościami w obserwowanych tematach i osobach (podwójne potwierdzenie, wypisanie jednym kliknięciem, bez śledzenia).', 'news.tasks.przeszlosc_alerts_task', 'PRZESZLOSC_ENABLED'),
    'odstepstwa': agent('Odstępstwa od klubu', 'Co noc bez AI i bez sieci liczy, kto głosuje inaczej niż większość swojego klubu (cała kadencja i 90 dni); te same progi dla każdego klubu.', 'news.tasks.voting_deviations_task', 'PRZESZLOSC_ENABLED'),
    'wspolny-przekaz': agent('Wspólny przekaz', 'Co 2 godziny bez AI szuka prawie identycznych wpisów z co najmniej 3 kont X w 6 godzin (ostatnie 48 h); strona publiczna dopiero po WSPOLNY_PRZEKAZ_PUBLIC, wcześniej podgląd dla redakcji.', 'news.tasks.coordinated_narratives_task', default=True),
    'wspolny-przekaz-noc': agent('Wspólny przekaz (noc)', 'Co noc to samo dla całego tygodnia: wpisy dosłane później przez zbieranie X.', 'news.tasks.coordinated_narratives_night_task', default=True),
    'public-record-people': agent('Dokumenty Sejmu przy osobach', 'Co noc bez sieci dopina interpelacje, zapytania i wystąpienia do osób po oficjalnym identyfikatorze posła.', 'news.tasks.public_record_people_task', default=True),
    'zmiana-zdania': agent('Zmiana zdania', 'Co 30 minut przy nowych diagnozach szuka bez AI wcześniejszych wypowiedzi tej samej osoby na ten sam temat (wpisy z kont potwierdzonych podwójnie, wystąpienia i głosy po oficjalnym identyfikatorze posła, co najmniej 14 dni wcześniej); jeden darmowy model ocenia, czy stanowisko się zmieniło. Ten sam próg dla każdej partii; nigdy nie wstrzymuje diagnozy.', 'news.tasks.zmiana_zdania_task', 'ZMIANA_ZDANIA_ENABLED', True),
    'odbior-spinu': agent('Jak spin zadziałał', 'Co godzinę dobę po wpisie z mocnym spinem (ten sam próg dla każdej partii) odczytuje z oficjalnego API X liczniki wpisu i próbkę odpowiedzi (domyślnie 30 na wpis, 300 odczytów na dobę, w budżecie X); jeden darmowy model ocenia zgodę, sprzeciw i kpinę. Zapisuje tylko liczby zbiorcze, bez danych osób prywatnych. Płatne: włącza właściciel.', 'news.tasks.odbior_spinu_task', 'X_REPLIES_ENABLED', False, cost='replies'),
    'raport-petli': agent('Raport pętli', 'Codziennie o 7:05 jeden mail: czy każda pętla agentów działa, ile wyprodukowała, co czeka na odbiorcę ponad termin i najlepsze nowe pomysły. Bez AI.', 'news.tasks.raport_petli_task', 'LOOP_REPORT_ENABLED', True),
    'x-value': agent('Wartość kont X', 'Codziennie ustala, jak często czytać każde konto X według jego wartości (taniej i legalnie).', 'news.tasks.x_value_task', 'X_VALUE_INTERVALS', True),
    'pracownia-osint': agent('Pracownia OSINT przeszłość.today', 'Ośmiu agentów rozwija narzędzie dla dziennikarzy: Kartograf (luki wobec konkurencji), Zwiadowca (nowe legalne zbiory z dane.gov.pl), Prawnik (ocena legalności każdej propozycji), Dziennikarz testowy (trzy osoby wykonują prawdziwe zadania), Kontroler danych (świeżość i pokrycie, bez AI), Architekt (tygodniowy plan 10 funkcji z gotowymi zleceniami), Wynalazca (co 3 dni nowe, kreatywne funkcje ponad konkurencję z danych, które już zbieramy), Technolog (co tydzień nowe otwarte narzędzia do podłączenia). Tylko proponują.', 'news.tasks.pracownia_osint_task', 'AGENTS_ENABLED'),
    'dyrygent': agent('Dyrygent', 'Zna wszystkie pętle, harmonogram i limity: co 15 minut ustawia tryb (pełny, oszczędny, strażnicy) według wolnych limitów darmowych modeli - najpierw treść, potem strażnicy, niezawodność, rozwój, nauka; codziennie plan dnia z kolizjami harmonogramu i kolejką budowy dla Claude i Codexa.', 'news.tasks.dyrygent_task', 'AGENTS_ENABLED'),
    'sprint': agent('Sprint tygodnia', 'W poniedziałek o 6:00 zamienia przyjęte i wysoko ocenione pomysły agentów w bilety budowy z terminem (do 8, bez duplikatów i bez propozycji odrzuconych przez Prawnika); w inne dni dopełnia kolejkę, gdy otwartych jest mniej niż 3. Bez AI.', 'news.tasks.sprint_intake_task', default=True),
    'badacz': agent('Badacz', 'Pętla researchu: codziennie odkrywa nowe źródła z linków w nowościach (kanały RSS/Atom), drugi model ocenia ich jakość, aktywne trafiają do Automatyka, Projektanta i Pracowni OSINT; martwe usypia.', 'news.tasks.badacz_task', 'AGENTS_ENABLED'),
    'opiekunowie': agent('Opiekunowie pętli', 'Każda pętla ma czterech opiekunów z pełnym kontekstem: Alarmowy (co godzinę, bez AI), Naprawiacz (przy alarmie), Usprawniacz (codziennie kolejne pętle) i Strażnik bezpieczeństwa (raz w tygodniu każda pętla). Tylko proponują i alarmują.', 'news.tasks.opiekunowie_task', 'AGENTS_ENABLED'),
    'automatyk': agent('Automatyk', 'Raz dziennie sprawdza wszystkie pętle agentów obu portali na żywych danych (wyłączone, z błędem, bez strażnika, zatkane propozycje) i proponuje usprawnienia z gotowymi zleceniami; drugi model sprawdza.', 'news.tasks.automatyk_task', 'AGENTS_ENABLED'),
    'mechanik': agent('Mechanik', 'Co godzinę naprawia połączenia z modelami: sprawdza listę modeli u dostawcy, przywraca działające, podpina następcę przemianowanego modelu.', 'news.tasks.mechanik_task', 'AGENTS_ENABLED'),
    'ekspert-ai': agent('Ekspert AI', 'Raz w tygodniu stan wiedzy o AI ze znalezisk Pielgrzyma; wskazuje Rekruterowi modele do egzaminu.', 'news.tasks.ekspert_ai_task', 'AGENTS_ENABLED'),
    'krs': agent('Agent KRS', 'Sprawdza powiązania osób z podmiotami KRS.', 'news.tasks.krs_agent_task', 'KRS_AGENT_ENABLED', cost='krs'),
    'seba': agent('Seba', 'Krytycznie ocenia propozycje agentów.', 'news.tasks.seba_task', 'SEBA_ENABLED', True),  # seba.enabled(): domyślnie włączona (Raport pętli 6.10 pokazywał „wył.”)
    'second-key': agent('Drugi klucz', 'Weryfikuje podejrzenia Strażnika kont.', 'news.tasks.warden_second_key_task', 'WARDEN_SECOND_KEY_ENABLED'),
    'interviews': agent('Wywiad dnia', 'Przygotowuje transkrypcję i diagnozę wywiadu.', 'news.tasks.clinic_interview_task', 'CLINIC_INTERVIEW_ENABLED', cost='interviews'),
    'sejm-wideo': agent('Wystąpienia z Sejmu', 'Co 30 minut w dzień wybiera z wczorajszych nagrań Sejmu (sala i komisje) najwyżej SEJM_VIDEO_SPIN_DAILY wystąpień posłów - tylko po długości, jedno na osobę, ta sama miara dla wszystkich - i diagnozuje je jak wpisy (Konsylium z kworum, osobny budżet). Link do odtwarzacza Sejmu z sekundą wystąpienia.', 'news.tasks.sejm_wideo_task', 'SEJM_VIDEO_SPIN_ENABLED'),
    'straznik-mediow': agent('Strażnik mediów', 'Co godzinę zapisuje w Wayback Machine kopię artykułów cytowanych w opublikowanych diagnozach i tematach dnia (najwyżej kilka na przebieg, w limicie 15/min), a raz na dobę porównuje skrót tekstu artykułu; zmiana po cytowaniu = alarm z kopią sprzed i po. Bez AI, bez zapisu treści.', 'news.tasks.straznik_mediow_task', 'MEDIA_WATCH_ENABLED'),
    'fakty': agent('Tę tezę sprawdzili', 'Co 2 godziny szuka w Google Fact Check API weryfikacji tych samych tez (Demagog, AFP i inni) przy opublikowanych diagnozach; zapisuje wydawcę, werdykt i link. Wymaga klucza FACTCHECK_API_KEY.', 'news.tasks.fakty_task', 'FACTCHECK_ENABLED'),
    'interview-pick': agent('Wybór wywiadu', 'Wybiera materiał do wywiadu dnia.', 'news.tasks.clinic_interview_pick_task', 'CLINIC_INTERVIEW_ENABLED'),
    'spin-thread': agent('Wątek Dr. Spina', 'Przygotowuje kontekst spinu dnia.', 'news.tasks.dr_spin_thread_task', 'DR_SPIN_THREADS_ENABLED'),
    'messages': agent('Przekaz dnia', 'Porównuje przekaz obu obozów politycznych.', 'news.tasks.clinic_daily_messages_task', 'CLINIC_AI_ENABLED'),
    'raport-tygodniowy': agent('Raport tygodniowy dla instytucji', 'W poniedziałek o 6:40 bez AI liczy PDF i CSV za poprzedni tydzień: wypowiedzi, techniki obu stron, trend klubów, ta sama miara; próbka publiczna na /dla-redakcji tylko po zatwierdzeniu (albo WEEKLY_SAMPLE_AUTO_PUBLIC).', 'news.tasks.raport_tygodniowy_task', 'WEEKLY_INSTITUTION_REPORT_ENABLED', True),
    'zamowienia-publiczne': agent('Zamówienia publiczne', 'Codziennie o 8:10 bez AI czyta zebrane ogłoszenia BZP o strony WWW, BIP i dostępność (CPV 72413000, 72212224, 79822500 i inne, słowa kluczowe); każde z terminem ofert = sygnał z zamawiającym, wartością, linkiem, szkicem oferty iapply i listą WCAG. Niczego nie wysyła; decyzja „składamy / pomijamy” w panelu, po terminie zamyka się sama.', 'news.tasks.zamowienia_publiczne_task', 'ZAMOWIENIA_ENABLED', True),
    'zapytania': agent('Zapytania (raporty i piloci)', 'Co godzinę bez AI: ponawia maile potwierdzające i ważne powiadomienia właściciela o potwierdzonych zgłoszeniach, usuwa niepotwierdzone po 30 dniach.', 'news.tasks.sales_leads_task', default=True),
    'weekly': agent('Raport tygodnia', 'Przygotowuje tygodniowe podsumowanie.', 'news.tasks.weekly_report_task'),
    'x-publish': agent('Publikacja X', 'Publikuje zatwierdzone wątki w granicach limitów.', 'news.tasks.x_publish_task', 'X_POST_ENABLED'),
    'social': agent('Publikacja społecznościowa', 'Przygotowuje publikacje w kanałach społecznościowych.', 'news.tasks.social_publish_task', 'SOCIAL_POST_ENABLED'),
    'notifications': agent('Powiadomienia', 'Obsługuje zdarzenia powiadomień czytelników.', 'news.notification_tasks.process_notification_events'),
    'digests': agent('Podsumowania czytelników', 'Wysyła zamówione podsumowania powiadomień.', 'news.notification_tasks.send_notification_digests'),
    'push': agent('Wieczorny spin', 'Przygotowuje wieczorne powiadomienie.', 'news.push_events.evening_spin'),
}

# Explicit allowlist: a new beat task cannot silently become a collector.
for task, name, env in (
    ('import_official_task', 'Zbieracz Sejmu i ELI', ''),
    ('discover_archives', 'Odkrywca archiwów', ''),
    ('check_data_quality', 'Kontrola jakości źródeł', ''),
    ('enrich_data_quality', 'Uzupełnianie metadanych', ''),
    ('archive_batch', 'Zbieracz archiwów', ''),
    ('discover_kprm_html', 'Zbieracz KPRM', ''),
    ('discover_mswia_metadata', 'Zbieracz MSWiA', ''),
    ('discover_ministry_finance_metadata', 'Zbieracz Ministerstwa Finansów', ''),
    ('discover_named_gov_metadata', 'Zbieracz instytucji publicznych', ''),
    ('audit_source_access', 'Kontrola dostępu do źródeł', ''),
    ('backfill_voting_history', 'Zbieracz historii głosowań', ''),
    ('scrape_rss_sources_task', 'Zbieracz RSS', ''),
    ('preflight_structured_metadata_source', 'Kontrola źródeł danych publicznych', ''),
    ('import_bzp_metadata', 'Zbieracz BZP', 'BZP_API_ENABLED'),
    ('scrape_newsapi_batch_task', 'Zbieracz NewsAPI', ''),
    ('sync_source_mailbox', 'Skrzynka źródeł', 'SOURCE_MAIL_IMAP_ENABLED'),
    ('gdelt_daily_topics', 'Zbieracz GDELT', 'GDELT_ENABLED'),
    ('discover_senat_metadata', 'Zbieracz Senatu', 'SENAT_METADATA_ENABLED'),
):
    REGISTRY[task] = agent(name, 'Zbiera lub sprawdza źródła zgodnie z zatwierdzonym dostępem.',
                           'scraper.tasks.' + task, env, collector=True)
for task, name, env in (
    ('youtube_official_task', 'Zbieracz YouTube', ''),
    ('youtube_leftover_task', 'Zbieracz pozostałego limitu YouTube', ''),
    ('source_social_task', 'Zbieracz kanałów źródeł', ''),
    ('deleted_posts_task', 'Kontrola usuniętych wpisów', ''),
    ('sejm_career_task', 'Zbieracz karier poselskich', ''),
    ('political_poll_task', 'Zbieracz X', 'X_POLITICAL_POLLING_ENABLED'),
    ('sync_live_public_rosters_task', 'Zbieracz składów instytucji', ''),
):
    REGISTRY[task] = agent(name, 'Aktualizuje dane z publicznych źródeł w granicach limitów.',
                           'news.tasks.' + task, env, collector=True)


REGISTRY['zasil-baze'] = agent(
    'Zasilanie bazy', 'Co noc (01:00-06:00) i przed północą dociąga całą historię włączonych źródeł od początku X kadencji '
    '(TED 12 miesięcy, KRS wszystkie obserwowane podmioty) w osobnym limicie, w granicach kart dostępu; gotowe źródła '
    'pomija sam. Bez AI.', 'scraper.tasks.zasil_baze_task', 'ZASIL_BAZE_ENABLED', True, collector=True)

# Explicit private research sources, each with its own flag/task/pulse.
from scraper.public_records import SOURCES as PUBLIC_RECORD_SOURCES
for _source, _spec in PUBLIC_RECORD_SOURCES.items():
    REGISTRY['public-records-' + _source] = agent(
        _spec.title, 'Dane publiczne do analiz wewnętrznych, bez AI.',
        'scraper.tasks.collect_public_' + _source, _spec.flag(_source), collector=True)


def enabled(spec):
    return not spec['flag'] or flag(spec['flag'], spec['default'])


def task_enabled(task):
    specs = [s for s in REGISTRY.values() if s['task'] == task]
    return any(enabled(s) for s in specs) if specs else True


def schedule_label(schedule):
    if hasattr(schedule, 'run_every'):
        return f'co {schedule.run_every.total_seconds() / 60:g} min'
    minute, hour = schedule._orig_minute, schedule._orig_hour
    if str(hour) == '*' and str(minute).startswith('*/'):
        return f'co {str(minute)[2:]} min'
    if str(hour) == '*' and str(minute) == '*':
        return 'co 1 min'
    if str(hour) == '*':
        return f'co godzinę, minuta: {minute}'
    if len(schedule.hour) == len(schedule.minute) == 1:
        at = f'{min(schedule.hour)}:{min(schedule.minute):02d}'
        if str(schedule._orig_day_of_month) != '*':
            return f'co miesiąc, dzień: {schedule._orig_day_of_month}, godz. {at}'
        if str(schedule._orig_day_of_week) != '*':
            days = ['niedziela', 'poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota']
            return f'co tydzień: {", ".join(days[d] for d in sorted(schedule.day_of_week))}, {at}'
        return f'codziennie {at}'
    return f'codziennie, godziny: {hour}, minuty: {minute}'


def next_run(schedule, now):
    schedule = copy(schedule)
    local = now.astimezone(WARSAW)
    schedule.nowfun = lambda: local
    return now + schedule.remaining_estimate(local)


def snapshot(now=None):
    from config.celery import app
    from news.duty import daily_costs
    now = now or timezone.now()
    costs = daily_costs(now)
    from celery.schedules import schedule as every
    # tryb ciągły zbieracza X zapisuje harmonogram jako timedelta (audyt Automatyka 5.10: przez to padała mapa agentów)
    entries = {key: ({**entry, 'schedule': every(entry['schedule'])} if isinstance(entry['schedule'], timedelta) else entry)
               for key, entry in app.conf.beat_schedule.items()}
    pulses = cache.get_many(['heartbeat:' + key for key in entries])
    rows = []
    for identity, spec in REGISTRY.items():
        matching = [(key, entry) for key, entry in entries.items() if entry['task'] == spec['task']]
        for key, entry in matching or [(None, None)]:
            pulse = pulses.get('heartbeat:' + key, {}) if key else {}
            last = stamp(pulse.get('started_at'))
            interval = cadence(entry['schedule']) if entry else None
            active = enabled(spec)
            stale = bool(last and interval and (now - last).total_seconds() > 3 * interval)
            state = ('error' if pulse.get('result') == 'error' else 'warn'
                     if stale or not pulse or pulse.get('result') == 'skipped' else 'ok')
            due = next_run(entry['schedule'], now) if entry and active else None
            if spec['task'] == 'news.tasks.agents_window_task':
                from news.models import RepairerState
                backoff = RepairerState.objects.filter(key='agents-window').first()
                retry_at = stamp((backoff.data if backoff else {}).get('next_attempt'))
                if due and retry_at and retry_at > due:
                    due = next_run(entry['schedule'], retry_at - timedelta(microseconds=1))
            rows.append(dict(id=f'{identity}:{key or "soon"}', name=spec['name'], description=spec['description'],
                collector=spec['collector'], task=spec['task'], beat=key, flag=spec['flag'], enabled=active,
                schedule=schedule_label(entry['schedule']) if entry else 'wkrótce',
                last_run=last, result=state, summary=pulse.get('summary', 'Brak pulsu.'), next_run=due,
                cost_today_usd=costs.get(spec['cost']), cost_note='Szacunek z zapisanych danych.' if spec['cost'] else '',
                source=', '.join(str(a) for a in entry.get('args', [])) if entry else ''))
    return rows
