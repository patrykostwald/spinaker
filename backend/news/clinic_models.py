"""Klinika spinu: automatyczne diagnozy AI postów polityków z X.

Strażnik (darmowe modele: Groq, zapasowo NVIDIA NIM) ocenia każdy nowy post z potwierdzonych kont
obozu rządzącego i opozycji. Płatna diagnoza (Claude) rusza tylko dla postów wartych sprawdzenia.
Człowiek wyłącznie zatwierdza albo odrzuca gotową diagnozę — nigdy nie edytuje
jej treści (model nie ma pola do edycji, a API przeglądu przyjmuje tylko decyzję).
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

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
    post = models.OneToOneField(PoliticalPost, on_delete=models.CASCADE, related_name='spin_diagnosis')
    status = models.CharField(max_length=16, choices=REVIEW_STATUSES, default='pending_review', db_index=True)
    verdict = models.CharField(max_length=12, choices=VERDICTS, blank=True)
    intensity = models.PositiveSmallIntegerField(default=0, help_text='Siła spinu 0–100 według modelu.')
    headline = models.CharField(max_length=200, blank=True)
    summary = models.TextField(blank=True)
    analysis = models.TextField(blank=True)
    techniques = models.JSONField(default=list, blank=True)
    claims = models.JSONField(default=list, blank=True)
    limitations = models.TextField(blank=True)
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

    class Meta:
        ordering = ['-post__published_at', '-pk']
        verbose_name = 'diagnoza spinu'
        verbose_name_plural = 'diagnozy spinu'

    def __str__(self):
        return f'{self.get_verdict_display() or "—"} · @{self.post.account.handle} · {self.post.post_id}'

    @property
    def camp(self):
        return self.post.camp_at_collection


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
    polarity = models.CharField(max_length=8, choices=POLARITIES)
    body = models.CharField(max_length=240, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['user', 'diagnosis'], name='one_opinion_per_user_spin'),
            models.CheckConstraint(condition=models.Q(polarity__in=['positive', 'negative']), name='spin_opinion_valid_polarity'),
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

    class Meta:
        ordering = ['-day', '-created_at']
        verbose_name = 'wywiad dnia'
        verbose_name_plural = 'wywiady dnia'

    def __str__(self):
        return f'{self.day} · {self.title or self.video_id}'
