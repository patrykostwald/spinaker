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

    class Meta:
        ordering = ['-day', 'camp']
        constraints = [models.UniqueConstraint(fields=['day', 'camp'], name='one_clinic_message_per_day_camp')]
        verbose_name = 'przekaz dnia'
        verbose_name_plural = 'przekazy dnia'

    def __str__(self):
        return f'{self.day} · {self.get_camp_display()}'


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
