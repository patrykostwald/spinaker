"""Klinika spinu: automatyczne diagnozy AI postów polityków z X.

Strażnik (darmowe modele: Groq, zapasowo NVIDIA NIM) ocenia każdy nowy post z potwierdzonych kont
obozu rządzącego i opozycji. Płatna diagnoza (Claude) rusza tylko dla postów wartych sprawdzenia.
Człowiek wyłącznie zatwierdza albo odrzuca gotową diagnozę — nigdy nie edytuje
jej treści (model nie ma pola do edycji, a API przeglądu przyjmuje tylko decyzję).
"""
from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models
from django.utils import timezone

from news.techniques import categorize_techniques

from news.political_models import EDITORIAL_CAMPS, PoliticalPost, PublicFigure

REVIEW_STATUSES = [
    ('flagged', 'Strażnik: warte sprawdzenia — czeka na decyzję o badaniu'),
    ('queued', 'W kolejce do płatnej diagnozy'),
    ('pending_review', 'Czeka na zatwierdzenie'),
    ('approved', 'Zatwierdzona'),
    ('rejected', 'Odrzucona'),
    ('failed', 'Błąd analizy'),
    ('not_applicable', 'Bez treści do oceny'),
]
VERDICTS = [
    ('spin', 'Spin'),
    ('partial', 'Częściowy spin'),
    ('no_spin', 'Bez spinu'),
    ('unclear', 'Nie da się ocenić'),
]
POLARITIES = [('positive', 'Trafna diagnoza'), ('negative', 'Nietrafna diagnoza')]


class SpinDiagnosis(models.Model):
    repair_attempts = models.PositiveSmallIntegerField(default=0)
    post = models.OneToOneField(PoliticalPost, on_delete=models.CASCADE, related_name='spin_diagnosis')
    status = models.CharField(max_length=16, choices=REVIEW_STATUSES + [('withdrawn', 'Wycofana')], default='pending_review', db_index=True)
    verdict = models.CharField(max_length=12, choices=VERDICTS, blank=True)
    intensity = models.PositiveSmallIntegerField(default=0, help_text='Siła spinu 0–100 według modelu.')
    headline = models.CharField(max_length=200, blank=True)
    summary = models.TextField(blank=True)
    plain = models.JSONField(default=dict, blank=True, help_text='Prosty pierwszy ekran: title, gist, top.')
    analysis = models.TextField(blank=True)
    techniques = models.JSONField(default=list, blank=True)
    claims = models.JSONField(default=list, blank=True)
    lab = models.JSONField(default=dict, blank=True)
    limitations = models.TextField(blank=True)
    x_thread = models.JSONField(default=list, blank=True,
                                help_text='Synteza diagnozy do wątku na X (darmowy model): wpis otwierający i 2–3 kolejne.')
    x_posted_ids = models.JSONField(default=list, blank=True, help_text='Identyfikatory wpisów wątku opublikowanego z konta spin.clinic.')
    x_posted_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text='Kiedy konto spin.clinic opublikowało wątek diagnozy.')
    triage = models.JSONField(default=dict, blank=True, help_text='Ocena strażnika: wynik 0–100, uzasadnienie, model.')
    screen_score = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True,
                                                    help_text='Jak bardzo post jest wart sprawdzenia według strażnika (0–100).')
    diagnosed_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text='Kiedy wykonano płatną diagnozę.')
    provider = models.CharField(max_length=32, blank=True)
    model_name = models.CharField(max_length=64, blank=True)
    prompt_version = models.CharField(max_length=16, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    alert_sent_at = models.DateTimeField(null=True, blank=True)
    hidden_at = models.DateTimeField(null=True, blank=True,
                                     help_text='Ukrycie po zgłoszeniu prawnym. Treść diagnozy pozostaje bez zmian.')
    hidden_reason = models.CharField(max_length=240, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True, db_index=True)
    withdrawn_reason = models.CharField(max_length=400, blank=True)
    withdrawn_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='+')

    def save(self, *args, **kwargs):
        if kwargs.get('update_fields') is None or 'techniques' in kwargs['update_fields']:
            self.techniques = categorize_techniques(self.techniques)
        if (kwargs.get('update_fields') is None or 'usage' in kwargs['update_fields']) and 'loaded_words' in (self.usage or {}):
            from news.loaded_words import validate_loaded_words
            self.usage = {**self.usage, 'loaded_words': validate_loaded_words(self.post.text, self.usage['loaded_words'])}
        return super().save(*args, **kwargs)

    class Meta:
        ordering = ['-post__published_at', '-pk']
        verbose_name = 'diagnoza spinu'
        verbose_name_plural = 'diagnozy spinu'

    def __str__(self):
        return f'{self.get_verdict_display() or "—"} · @{self.post.account.handle} · {self.post.post_id}'

    @property
    def camp(self):
        return self.post.camp_at_collection


class ClinicAuthorReply(models.Model):
    diagnosis = models.ForeignKey(SpinDiagnosis, on_delete=models.PROTECT, related_name='author_replies')
    body = models.TextField(max_length=1500, validators=[MaxLengthValidator(1500)], verbose_name='treść')
    source_url = models.URLField(max_length=500, verbose_name='link do źródła')
    received_at = models.DateTimeField(default=timezone.now, verbose_name='data otrzymania')
    published_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='data publikacji')
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-published_at', '-pk']
        verbose_name = 'odpowiedź autora'
        verbose_name_plural = 'odpowiedzi autorów'

    def __str__(self):
        return f'Odpowiedź do diagnozy {self.diagnosis_id}'


class CouncilCall(models.Model):
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    provider = models.CharField(max_length=32)
    model = models.CharField(max_length=200)
    outcome = models.CharField(max_length=24)
    seconds = models.FloatField(default=0)


class InquisitorReview(models.Model):
    diagnosis = models.OneToOneField(SpinDiagnosis, on_delete=models.PROTECT, related_name='inquisitor_review')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    camp = models.CharField(max_length=12)
    reviewers = models.JSONField(default=list)
    answers = models.JSONField(default=list)
    verdict = models.CharField(max_length=16, default='incomplete')
    decided_at = models.DateTimeField(null=True, blank=True)
    decision = models.CharField(max_length=8, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-created_at', '-pk']


class CouncilCharterAcceptance(models.Model):
    """Historia odpowiedzi modeli; zmiana Karty nie nadpisuje poprzednich deklaracji."""
    model = models.CharField(max_length=200)
    provider = models.CharField(max_length=32)
    company = models.CharField(max_length=100)
    charter_version = models.CharField(max_length=32)
    charter_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    response = models.JSONField(default=dict)


class CouncilSeat(models.Model):
    """Miejsce modelu w Konsylium poza stałą konfiguracją: przyjęty przez Rekrutera albo zawieszony przez kontrolę zdrowia.

    Stały skład nadal pochodzi z konfiguracji (clinic_council); ta tabela go koryguje — zawieszeni są pomijani we wszystkich
    rolach, przyjęci przez Rekrutera dochodzą do ról, które przyznało im Konsylium."""
    STATUSES = [('active', 'aktywny'), ('suspended', 'zawieszony')]
    provider = models.CharField(max_length=32)
    model = models.CharField(max_length=200)
    company = models.CharField(max_length=100, blank=True)
    origin = models.CharField(max_length=16, default='config', help_text='config — stały skład, recruiter — przyjęty przez Rekrutera.')
    roles = models.JSONField(default=list, blank=True, help_text='Role przyznane przez Konsylium (dla origin=recruiter).')
    status = models.CharField(max_length=12, choices=STATUSES, default='active', db_index=True)
    admitted_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    last_ok_at = models.DateTimeField(null=True, blank=True)
    first_fail_at = models.DateTimeField(null=True, blank=True, help_text='Początek nieprzerwanej serii twardych błędów (np. 404).')
    last_error = models.CharField(max_length=160, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['provider', 'model'], name='council_seat_unique')]


class CouncilRecruitment(models.Model):
    """Dziennik Rekrutera: kandydat, egzamin, głosy Konsylium i decyzja (jawny na stronie Konsylium)."""
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    kind = models.CharField(max_length=16, default='candidate', help_text='candidate, suspension, return')
    provider = models.CharField(max_length=32)
    model = models.CharField(max_length=200)
    company = models.CharField(max_length=100, blank=True)
    source = models.JSONField(default=dict, blank=True, help_text='Skąd kandydat: katalog dostawcy, kontekst, uwagi sita.')
    exam = models.JSONField(default=dict, blank=True)
    votes = models.JSONField(default=list, blank=True)
    decision = models.CharField(max_length=20, blank=True, help_text='admitted, rejected, would_admit, would_reject, suspended, returned')
    roles = models.JSONField(default=list, blank=True)
    mode = models.CharField(max_length=8, default='trial', help_text='trial — tylko rekomendacja, auto — decyzja wykonana.')
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']


class ClinicDailyMessage(models.Model):
    """Przekaz dnia jednego obozu — streszczenie AI z postów danego dnia."""
    day = models.DateField()
    camp = models.CharField(max_length=12, choices=EDITORIAL_CAMPS)
    message = models.TextField()
    analysis = models.TextField(blank=True, help_text='Dłuższa analiza przekazu (widok po kliknięciu).')
    themes = models.JSONField(default=list, blank=True)
    thesis = models.CharField(max_length=160, blank=True)
    points = models.JSONField(default=list, blank=True)
    tone = models.JSONField(default=list, blank=True)
    stats = models.JSONField(default=dict, blank=True)
    posts = models.ManyToManyField(PoliticalPost, related_name='clinic_daily_messages', blank=True)
    status = models.CharField(max_length=16, choices=REVIEW_STATUSES, default='pending_review', db_index=True)
    model_name = models.CharField(max_length=64, blank=True)
    prompt_version = models.CharField(max_length=16, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    alert_sent_at = models.DateTimeField(null=True, blank=True)
    # Wiersz ze status='failed' i pustym message: zapisany powód, dlaczego przekaz nie powstał (6.10: błąd ginął w logu).
    # Nigdy nie jest publiczny i nie blokuje kolejnych przebiegów - udany przebieg go nadpisuje.
    error = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        ordering = ['-day', 'camp']
        constraints = [models.UniqueConstraint(fields=['day', 'camp'], name='one_clinic_message_per_day_camp')]
        verbose_name = 'przekaz dnia'
        verbose_name_plural = 'przekazy dnia'

    def __str__(self):
        return f'{self.day} · {self.get_camp_display()}'


CHAIN_STATUSES = [
    ('pending_review', 'Do zatwierdzenia'),
    ('approved', 'Zatwierdzony'),
    ('rejected', 'Odrzucony'),
    ('failed', 'Odrzucony przez walidator'),
]


class CausalChain(models.Model):
    """„Dr Spin wyjaśnia” (v3): ciąg przyczynowo-skutkowy przekazu dnia (news/causal_chain.py).

    Kroki przeszły walidator w kodzie (źródła faktów tylko z materiałów przekazu, bez wymyślonych liczb i cytatów).
    Publicznie tylko po zatwierdzeniu przez człowieka (approved_at) i przy włączonej fladze CAUSAL_CHAIN_ENABLED.
    Człowiek zatwierdza albo odrzuca, nie edytuje kroków (jak diagnozy)."""
    message = models.OneToOneField(ClinicDailyMessage, on_delete=models.CASCADE, related_name='causal_chain')
    steps = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=CHAIN_STATUSES, default='pending_review', db_index=True)
    gates = models.JSONField(default=dict, blank=True, help_text='Wyniki bramek: walidator, fact-checker, prawnik, językoznawca.')
    model_name = models.CharField(max_length=200, blank=True)
    prompt_version = models.CharField(max_length=16, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True, db_index=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    rejected_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=400, blank=True)

    class Meta:
        indexes = [models.Index(fields=['status', 'created_at'], name='causal_chain_queue_v3')]
        permissions = [('can_decide_causalchain', 'Może zatwierdzać i odrzucać ciągi przyczyn przekazu')]
        verbose_name = 'ciąg przyczyn przekazu'
        verbose_name_plural = 'ciągi przyczyn przekazów'

    def __str__(self):
        return f'Ciąg przyczyn: {self.message} ({self.get_status_display()})'


class CausalChainEvent(models.Model):
    """Dziennik łańcucha (AI Act art. 50, przejrzystość): każde wygenerowanie, odrzucenie przez walidator i decyzja człowieka.
    Tylko dopisywanie; wpisy nie są edytowane ani usuwane przez aplikację."""
    chain = models.ForeignKey(CausalChain, on_delete=models.CASCADE, related_name='events')
    event = models.CharField(max_length=24)
    at = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    model_name = models.CharField(max_length=200, blank=True)
    prompt_version = models.CharField(max_length=16, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['at', 'pk']
        verbose_name = 'zdarzenie ciągu przyczyn'
        verbose_name_plural = 'dziennik ciągów przyczyn'


PAIR_STATUSES = [
    ('suggested', 'Zgłoszona'),
    ('approved', 'Zatwierdzona'),
    ('rejected', 'Odrzucona'),
    ('withdrawn', 'Wycofana'),
]


class PositionPair(models.Model):
    """„Wcześniej i teraz” (v3, news/position_pairs.py): dwie wypowiedzi albo głosy tej samej osoby o tym samym temacie.

    A starsza, B nowsza. Każda strona: rodzaj, data, cytat dosłowny albo wynik głosowania, źródło i klucz materiału w bazie
    (post:<id>, record:<id>, ballot:<id>). Bez ocen: publicznie tylko po zatwierdzeniu przez człowieka (POSITION_PAIRS_ENABLED).
    Ta sama osoba wyłącznie po identyfikatorze (konta X potwierdzone przy osobie, oficjalny identyfikator posła)."""
    figure = models.ForeignKey(PublicFigure, on_delete=models.PROTECT, related_name='position_pairs')
    topic = models.CharField(max_length=120)
    a = models.JSONField(default=dict)
    b = models.JSONField(default=dict)
    a_key = models.CharField(max_length=40)
    b_key = models.CharField(max_length=40)
    a_date = models.DateField()
    b_date = models.DateField(db_index=True)
    context = models.CharField(max_length=200, blank=True)
    context_source = models.CharField(max_length=8, blank=True, choices=[('ai', 'AI'), ('human', 'Człowiek')],
                                      help_text='Kto napisał kontekst (publiczne; AI Act art. 50).')
    status = models.CharField(max_length=12, choices=PAIR_STATUSES, default='suggested', db_index=True)
    ai_suggested = models.BooleanField(default=False)
    suggested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    diagnosis = models.ForeignKey(SpinDiagnosis, null=True, blank=True, on_delete=models.SET_NULL, related_name='position_pairs')
    source_check = models.ForeignKey('PositionCheck', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    model_name = models.CharField(max_length=200, blank=True)
    prompt_version = models.CharField(max_length=16, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True, db_index=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=400, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['figure', 'a_key', 'b_key'], name='position_pair_once')]
        indexes = [models.Index(fields=['status', 'created_at'], name='position_pair_queue_v3'),
                   models.Index(fields=['status', '-b_date', '-id'], name='position_pair_public_v3'),
                   models.Index(fields=['figure', 'status', '-b_date', '-id'], name='position_pair_figure_v3')]
        permissions = [('can_decide_positionpair', 'Może zatwierdzać, odrzucać i wycofywać pary stanowisk')]
        verbose_name = 'para stanowisk (wcześniej i teraz)'
        verbose_name_plural = 'pary stanowisk (wcześniej i teraz)'

    def __str__(self):
        return f'{self.figure} · {self.topic} ({self.get_status_display()})'


class PositionPairEvent(models.Model):
    """Dziennik pary (AI Act art. 50): zgłoszenie, decyzje, zgłoszenia błędów, wycofanie. Tylko dopisywanie."""
    pair = models.ForeignKey(PositionPair, on_delete=models.CASCADE, related_name='events')
    event = models.CharField(max_length=24)
    at = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['at', 'pk']
        verbose_name = 'zdarzenie pary stanowisk'
        verbose_name_plural = 'dziennik par stanowisk'


class PositionPairReport(models.Model):
    """Zgłoszenie błędu przy parze (procedura sprostowania): para wraca do decyzji człowieka."""
    pair = models.ForeignKey(PositionPair, on_delete=models.CASCADE, related_name='reports')
    reason = models.TextField(max_length=1000, validators=[MaxLengthValidator(1000)])
    contact = models.CharField(max_length=200, blank=True)
    is_subject = models.BooleanField(default=False, help_text='Zgłasza osoba, której dotyczy para (albo jej przedstawiciel).')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    # Recenzja Codex 2: kolejka moderacji i progi automatycznego zdjęcia (news/position_pairs.report).
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    ip_hash = models.CharField(max_length=64, blank=True, help_text='Skrót IP z solą serwisu; sam adres nie jest zapisywany.')
    verified = models.BooleanField(default=False, help_text='Konto potwierdzone jako osoba z pary albo jej przedstawiciel.')
    priority = models.CharField(max_length=8, default='zwykly', db_index=True, choices=[('wysoki', 'Wysoki'), ('zwykly', 'Zwykły')])
    # Recenzja Fable (poprawka 5): potwierdzenie e-mail osoby (link 48 h) i odpowiedź z decyzją.
    confirm_token = models.CharField(max_length=64, blank=True, db_index=True)
    email_confirmed_at = models.DateTimeField(null=True, blank=True)
    official_domain = models.BooleanField(default=False, help_text='Potwierdzony e-mail z domeny z listy POSITION_PAIR_OFFICIAL_DOMAINS.')
    decision_sent_at = models.DateTimeField(null=True, blank=True)
    # Recenzja Codex 3: w confirm_token i response_token tylko skrót sha256 (news/v3_tokens.py), termin i jednorazowość.
    token_expires_at = models.DateTimeField(null=True, blank=True)
    token_used_at = models.DateTimeField(null=True, blank=True)
    response_token = models.CharField(max_length=64, blank=True, db_index=True,
                                      help_text='Skrót tokenu odpowiedzi osoby (po potwierdzeniu adresu urzędowego).')
    response_token_expires_at = models.DateTimeField(null=True, blank=True)
    response_token_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['confirm_token'], condition=~models.Q(confirm_token=''), name='pair_report_token_unique'),
            models.UniqueConstraint(fields=['response_token'], condition=~models.Q(response_token=''), name='pair_report_response_token_unique'),
        ]
        verbose_name = 'zgłoszenie błędu pary stanowisk'
        verbose_name_plural = 'zgłoszenia błędów par stanowisk'


class VerifiedReporter(models.Model):
    """Konto potwierdzone przez personel jako osoba publiczna albo jej przedstawiciel (np. biuro posła).
    Zgłoszenie błędu z takiego konta zdejmuje parę tej osoby z API do decyzji człowieka."""
    ROLES = [('osoba', 'Osoba z rejestru'), ('przedstawiciel', 'Przedstawiciel osoby')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='verified_reporter_roles')
    figure = models.ForeignKey(PublicFigure, on_delete=models.CASCADE, related_name='verified_reporters')
    role = models.CharField(max_length=16, choices=ROLES)
    evidence = models.CharField(max_length=400, help_text='Jak potwierdzono (np. e-mail z domeny sejm.gov.pl, pismo).')
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    verified_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'figure'], name='verified_reporter_once')]
        verbose_name = 'zweryfikowany zgłaszający'
        verbose_name_plural = 'zweryfikowani zgłaszający'


class CausalChainReport(models.Model):
    """Zgłoszenie błędu przy opublikowanym ciągu przyczyn (recenzja Fable, poprawka 6): kolejka moderacji, bez zdjęcia
    automatycznego (łańcuch nie dotyczy jednej osoby); decyzja człowieka z publicznym powodem w rejestrze korekt."""
    chain = models.ForeignKey(CausalChain, on_delete=models.CASCADE, related_name='reports')
    reason = models.TextField(max_length=1000, validators=[MaxLengthValidator(1000)])
    contact = models.CharField(max_length=200, blank=True)
    is_subject = models.BooleanField(default=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    ip_hash = models.CharField(max_length=64, blank=True)
    priority = models.CharField(max_length=8, default='zwykly', choices=[('wysoki', 'Wysoki'), ('zwykly', 'Zwykły')])
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'zgłoszenie błędu ciągu przyczyn'
        verbose_name_plural = 'zgłoszenia błędów ciągów przyczyn'


class SiteFlag(models.Model):
    """Przełącznik v3 w bazie (recenzja Fable, poprawka 9): wartość z oknem od-do nadpisuje ustawienie z env bez restartu.
    Klucze: news/v3_flags.KNOWN. Każda zmiana trafia do SiteFlagChange (kto, kiedy, z czego na co)."""
    key = models.CharField(max_length=64, unique=True)
    value = models.BooleanField(default=False)
    active_from = models.DateTimeField(null=True, blank=True, help_text='Od kiedy obowiązuje (puste = od razu).')
    active_until = models.DateTimeField(null=True, blank=True, help_text='Do kiedy obowiązuje (puste = bez końca).')
    note = models.CharField(max_length=300, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'przełącznik v3'
        verbose_name_plural = 'przełączniki v3 (kill switch, cisza wyborcza)'

    def __str__(self):
        return f'{self.key} = {self.value}'



def _site_flags_changed(**kwargs):
    """Każdy zapis i usunięcie (także przez QuerySet) czyści pamięć przełączników: zmiana działa od następnego żądania."""
    from news.v3_flags import clear_cache
    clear_cache()


models.signals.post_save.connect(_site_flags_changed, sender=SiteFlag, dispatch_uid='site_flag_saved')
models.signals.post_delete.connect(_site_flags_changed, sender=SiteFlag, dispatch_uid='site_flag_deleted')


class SiteFlagChange(models.Model):
    """Dziennik przełączników (tylko dopisywanie)."""
    key = models.CharField(max_length=64, db_index=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    changed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'zmiana przełącznika v3'
        verbose_name_plural = 'dziennik przełączników v3'


class SpinOpinion(models.Model):
    """Reakcja czytelnika na diagnozę: trafna / nietrafna, opcjonalnie z komentarzem."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='spin_opinions')
    diagnosis = models.ForeignKey(SpinDiagnosis, on_delete=models.CASCADE, related_name='opinions')
    polarity = models.CharField(max_length=8, choices=POLARITIES, null=True, blank=True)
    body = models.CharField(max_length=240, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['user', 'diagnosis'], name='one_opinion_per_user_spin'),
            models.CheckConstraint(condition=models.Q(polarity__isnull=True) | models.Q(polarity__in=['positive', 'negative']), name='spin_opinion_valid_polarity'),
        ]


class XAccountSuggestion(models.Model):
    """Sugestia czytelnika: link do konta X osoby z rejestru. Wymaga weryfikacji zespołu."""
    public_figure = models.ForeignKey(PublicFigure, on_delete=models.CASCADE, related_name='x_account_suggestions')
    url = models.URLField(max_length=300)
    handle = models.CharField(max_length=15)
    note = models.CharField(max_length=300, blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='+')
    status = models.CharField(max_length=10, default='new', db_index=True,
                              choices=[('new', 'Nowa'), ('accepted', 'Przyjęta'), ('rejected', 'Odrzucona')])
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['public_figure', 'handle'], name='one_suggestion_per_figure_handle')]
        verbose_name = 'sugestia konta X'
        verbose_name_plural = 'sugestie kont X'

    def __str__(self):
        return f'@{self.handle} → {self.public_figure}'


class ClinicInterview(models.Model):
    selection_method = models.CharField(max_length=16, blank=True)
    selection_votes = models.PositiveIntegerField(default=0)
    repair_attempts = models.PositiveSmallIntegerField(default=0)
    """Wywiad dnia: publiczny film z YouTube z politykiem — transkrypcja (Gemini) i diagnoza Dr. Spina (Claude).

    Człowiek wybiera tylko materiał (link); treści diagnozy nikt nie poprawia. Ukrycie wyłącznie po zgłoszeniu prawnym.
    """
    day = models.DateField(db_index=True, help_text='Dzień emisji materiału (zwykle poprzedni dzień).')
    url = models.URLField(max_length=300)
    video_id = models.CharField(max_length=11, unique=True)
    title = models.CharField(max_length=300, blank=True)
    channel = models.CharField(max_length=200, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    guest_name = models.CharField(max_length=200, blank=True)
    guest_role = models.CharField(max_length=200, blank=True)
    host_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=16, choices=REVIEW_STATUSES, default='queued', db_index=True)
    headline = models.CharField(max_length=200, blank=True)
    summary = models.TextField(blank=True)
    overall = models.TextField(blank=True)
    guest_analysis = models.JSONField(default=dict, blank=True)
    host_analysis = models.JSONField(default=dict, blank=True)
    limitations = models.TextField(blank=True)
    transcript = models.TextField(blank=True)
    model_name = models.CharField(max_length=64, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(default=timezone.now)
    diagnosed_at = models.DateTimeField(null=True, blank=True)
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_reason = models.CharField(max_length=240, blank=True)

    def save(self, *args, **kwargs):
        for field, key in (('guest_analysis', 'techniques'), ('host_analysis', 'notes')):
            if kwargs.get('update_fields') is None or field in kwargs['update_fields']:
                analysis = getattr(self, field)
                if isinstance(analysis, dict) and key in analysis:
                    setattr(self, field, {**analysis, key: categorize_techniques(analysis[key])})
        return super().save(*args, **kwargs)

    class Meta:
        ordering = ['-day', '-created_at']
        verbose_name = 'wywiad dnia'
        verbose_name_plural = 'wywiady dnia'

    def __str__(self):
        return f'{self.day} · {self.title or self.video_id}'


class WeeklyReport(models.Model):
    """Raport tygodnia Dr. Spina — zestawienie danych z 7 dni i krótkie podsumowanie darmowego modelu."""
    week_start = models.DateField()
    week_end = models.DateField(unique=True)
    data = models.JSONField(default=dict)
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-week_end']

    def __str__(self):
        return f'Raport {self.week_start} – {self.week_end}'


SOCIAL_PLATFORMS = [
    ('tiktok', 'TikTok'),
    ('shorts', 'YouTube Shorts'),
    ('facebook', 'Facebook (film)'),
    ('instagram', 'Instagram (Reels)'),
    ('bluesky', 'Bluesky'),
    ('manual', 'TikTok i YouTube Shorts (mail z filmem)'),
]


class SocialPost(models.Model):
    """Wpis diagnozy w mediach społecznościowych poza X (news/social_publish.py). Usunięty, gdy autor usunie swój wpis."""
    diagnosis = models.ForeignKey(SpinDiagnosis, on_delete=models.CASCADE, related_name='social_posts')
    platform = models.CharField(max_length=12, choices=SOCIAL_PLATFORMS)
    external_id = models.CharField(max_length=200, blank=True)
    url = models.URLField(max_length=500, blank=True)
    posted_at = models.DateTimeField(default=timezone.now, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ['-posted_at']
        constraints = [models.UniqueConstraint(fields=['diagnosis', 'platform'], name='social_post_once_per_platform')]

    def __str__(self):
        return f'{self.get_platform_display()} — diagnoza {self.diagnosis_id}'


POSITION_SOURCE_KINDS = [('post', 'Wpis na X'), ('statement', 'Wystąpienie w Sejmie'), ('vote', 'Głosowanie w Sejmie')]
POSITION_RELATIONS = [
    ('pending', 'Czeka na sprawdzenie'),
    ('change', 'Zmiana stanowiska'),
    ('same', 'To samo stanowisko'),
    ('off_topic', 'Nie na temat'),
    ('unclear', 'Nie da się ocenić (cytat bez potwierdzenia)'),
]


class PositionScan(models.Model):
    """Zmiana zdania: znak, że dla diagnozy wyszukano już wcześniejsze wypowiedzi tej samej osoby (news/zmiana_zdania.py)."""
    diagnosis = models.OneToOneField(SpinDiagnosis, on_delete=models.CASCADE, related_name='position_scan')
    scanned_at = models.DateTimeField(default=timezone.now, db_index=True)
    candidates = models.PositiveSmallIntegerField(default=0)


class PositionCheck(models.Model):
    """Wcześniejsza wypowiedź tej samej osoby na ten sam temat i ocena modelu: zmiana stanowiska, to samo albo nie na temat.

    Kandydaci powstają bez AI (wspólne słowa, co najmniej 14 dni wcześniej); jeden darmowy model ocenia parę.
    Publicznie pokazujemy wyłącznie „change” z pewnością od progu (ten sam próg dla każdej partii) i z potwierdzonymi cytatami."""
    diagnosis = models.ForeignKey(SpinDiagnosis, on_delete=models.CASCADE, related_name='position_checks')
    source_kind = models.CharField(max_length=12, choices=POSITION_SOURCE_KINDS)
    source_key = models.CharField(max_length=40, help_text='post:<id>, record:<id> albo ballot:<id>.')
    earlier_post = models.ForeignKey(PoliticalPost, null=True, blank=True, on_delete=models.CASCADE, related_name='+')
    source_url = models.URLField(max_length=1024)
    source_date = models.DateField()
    source_title = models.CharField(max_length=300, blank=True)
    earlier_text = models.TextField(help_text='Wcześniejsza wypowiedź (fragment) albo opis głosu.')
    similarity = models.FloatField(default=0)
    relation = models.CharField(max_length=12, choices=POSITION_RELATIONS, default='pending', db_index=True)
    confidence = models.PositiveSmallIntegerField(default=0)
    explanation = models.CharField(max_length=400, blank=True)
    quote_then = models.CharField(max_length=400, blank=True)
    quote_now = models.CharField(max_length=400, blank=True)
    model_name = models.CharField(max_length=200, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    checked_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-source_date', '-pk']
        constraints = [models.UniqueConstraint(fields=['diagnosis', 'source_key'], name='position_check_once')]

    def __str__(self):
        return f'{self.source_key} → diagnoza {self.diagnosis_id}: {self.relation}'


RECEPTION_STATUSES = [
    ('retry', 'Ponowić odczyt'),
    ('done', 'Sprawdzone'),
    ('no_model', 'Liczniki bez oceny modelu'),
    ('unavailable', 'Wpis niedostępny'),
    ('failed', 'Nieudane'),
]


class ReceptionCheck(models.Model):
    """Jak spin zadziałał (news/odbior_spinu.py): odbiór wpisu dobę później. Tylko liczby zbiorcze - żadnych nazw kont,
    identyfikatorów ani treści odpowiedzi osób prywatnych (RODO); osoby publiczne z rejestru jako nazwa i odnośnik."""
    diagnosis = models.OneToOneField(SpinDiagnosis, on_delete=models.CASCADE, related_name='reception')
    status = models.CharField(max_length=12, choices=RECEPTION_STATUSES, default='retry', db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    checked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    hours_after = models.FloatField(null=True, blank=True)
    metrics_before = models.JSONField(default=dict, blank=True, help_text='Liczniki wpisu przy pobraniu.')
    metrics_after = models.JSONField(default=dict, blank=True, help_text='Liczniki wpisu po dobie.')
    requested = models.PositiveSmallIntegerField(default=0)
    sample = models.PositiveSmallIntegerField(default=0, help_text='Liczba przeanalizowanych odpowiedzi.')
    shares = models.JSONField(default=dict, blank=True, help_text='Udziały w procentach: zgoda, sprzeciw, kpina, inne, powtarza, zrodla.')
    sentiment = models.JSONField(default=dict, blank=True)
    phrases = models.JSONField(default=list, blank=True, help_text='Najwyżej 3 zwroty z co najmniej 3 odpowiedzi, bez nazw i @.')
    figures = models.JSONField(default=list, blank=True, help_text='Odpowiedzi osób publicznych z rejestru: nazwa, konto, odnośnik.')
    verdict = models.CharField(max_length=12, blank=True)
    model_name = models.CharField(max_length=200, blank=True)
    reads_used = models.PositiveSmallIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'odbiór spinu'
        verbose_name_plural = 'odbiór spinu'

    def __str__(self):
        return f'Odbiór {self.diagnosis_id}: {self.status}'


class OfficialDomainChange(models.Model):
    """Dziennik zmian listy domen urzędowych i partyjnych (news/official_domains.py). Tylko dopisywanie; ostatni wpis dla domeny
    decyduje, czy jest dodana do listy z pliku, czy z niej usunięta."""
    ACTIONS = [('add', 'Dodana'), ('remove', 'Usunięta')]
    domain = models.CharField(max_length=253, db_index=True)
    action = models.CharField(max_length=8, choices=ACTIONS)
    kind = models.CharField(max_length=16, blank=True, help_text='urzad, parlament, partia, klub')
    source = models.CharField(max_length=500, blank=True)
    note = models.CharField(max_length=300, blank=True)
    changed_by = models.CharField(max_length=150, blank=True)
    changed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-changed_at', '-pk']
        verbose_name = 'zmiana listy domen urzędowych'
        verbose_name_plural = 'dziennik listy domen urzędowych'


class DataObjection(models.Model):
    """Sprzeciw (art. 21 RODO) albo inne żądanie osoby wobec profilu przeszłość.today (news/privacy_notice.py).
    Kolejka personelu, bez automatycznego usuwania; potwierdzenie e-mail jak przy zgłoszeniach par."""
    STATUSES = [('nowy', 'Nowy'), ('potwierdzony', 'Potwierdzony e-mailem'), ('uwzgledniony', 'Uwzględniony'),
                ('odrzucony', 'Odrzucony')]
    figure = models.ForeignKey(PublicFigure, null=True, blank=True, on_delete=models.SET_NULL, related_name='data_objections')
    ident = models.CharField(max_length=120, blank=True, help_text='Identyfikator profilu z adresu (także nieistniejący: bez enumeracji).')
    relation = models.CharField(max_length=16, choices=[('osoba', 'Osoba z profilu'), ('przedstawiciel', 'Przedstawiciel'),
                                                          ('inna', 'Inna osoba')])
    reason = models.TextField(max_length=2000, validators=[MaxLengthValidator(2000)])
    contact = models.CharField(max_length=200)
    confirm_token = models.CharField(max_length=64, blank=True, db_index=True)
    email_confirmed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=14, choices=STATUSES, default='nowy', db_index=True)
    decision_note = models.CharField(max_length=600, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_sent_at = models.DateTimeField(null=True, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    notice_version = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    token_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['confirm_token'], condition=~models.Q(confirm_token=''),
                                               name='objection_token_unique')]
        verbose_name = 'sprzeciw wobec przetwarzania (art. 21)'
        verbose_name_plural = 'sprzeciwy wobec przetwarzania (art. 21)'


class SubjectResponse(models.Model):
    """Odpowiedź osoby obok pary „Wcześniej i teraz” (decyzja właściciela 13.10): od zweryfikowanego zgłaszającego albo
    z potwierdzonego adresu urzędowego; publiczna dopiero po zatwierdzeniu przez personel (can_decide_positionpair)."""
    STATUSES = [('zgloszona', 'Zgłoszona'), ('opublikowana', 'Opublikowana'), ('odrzucona', 'Odrzucona')]
    pair = models.ForeignKey(PositionPair, on_delete=models.CASCADE, related_name='subject_responses')
    text = models.TextField(max_length=600, validators=[MaxLengthValidator(600)])
    status = models.CharField(max_length=14, choices=STATUSES, default='zgloszona', db_index=True)
    via = models.CharField(max_length=16, help_text='verified_reporter albo official_email')
    report = models.ForeignKey(PositionPairReport, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    submitted_at = models.DateTimeField(default=timezone.now)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=400, blank=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'odpowiedź osoby (para stanowisk)'
        verbose_name_plural = 'odpowiedzi osób (pary stanowisk)'


class AssetDeclaration(models.Model):
    """Oświadczenie majątkowe posła (decyzja właściciela 13.10, news/asset_declarations.py): tylko link do oficjalnego PDF
    Sejmu i metadane (rok, data publikacji, typ, suma kontrolna). Odczyt z PDF tylko automatyczny i oznaczony; bez
    wskaźników pochodnych, porównań i ocen. Ta sama procedura dla każdego posła."""
    KINDS = [('oswiadczenie', 'Oświadczenie'), ('korekta', 'Korekta'), ('inne', 'Inny dokument')]
    record = models.OneToOneField('news.PublicRecord', null=True, blank=True, on_delete=models.SET_NULL, related_name='asset_declaration')
    figure = models.ForeignKey(PublicFigure, null=True, blank=True, on_delete=models.SET_NULL, related_name='asset_declarations')
    term = models.PositiveSmallIntegerField()
    mp_id = models.PositiveIntegerField(db_index=True)
    name = models.CharField(max_length=200, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=14, choices=KINDS, default='oswiadczenie')
    title = models.CharField(max_length=400, blank=True)
    url = models.URLField(max_length=1024, unique=True)
    published_on = models.DateField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    size = models.PositiveIntegerField(null=True, blank=True)
    etag = models.CharField(max_length=200, blank=True)
    last_modified = models.CharField(max_length=100, blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    fetch_error = models.CharField(max_length=200, blank=True)
    auto_read = models.JSONField(default=dict, blank=True, help_text='Odczyt automatyczny z PDF (strony, warstwa tekstu); sprawdź w PDF.')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-year', '-published_on', '-pk']
        indexes = [models.Index(fields=['term', 'mp_id', '-year'], name='asset_decl_mp_year'),
                   models.Index(fields=['fetched_at', 'id'], name='asset_decl_fetch_queue')]
        verbose_name = 'oświadczenie majątkowe'
        verbose_name_plural = 'oświadczenia majątkowe'
