"""Modele nowych źródeł (raport źródeł 6.10): diagnozy wystąpień z nagrań Sejmu i strażnik mediów (kopie Wayback)."""
from django.db import models
from django.utils import timezone

from news.clinic_models import REVIEW_STATUSES, VERDICTS
from news.techniques import categorize_techniques


class SejmVideoSpin(models.Model):
    """Diagnoza Dr. Spina wystąpienia posła na sali albo w komisji (tekst urzędowy z API Sejmu) z miejscem w nagraniu.

    Ta sama ścieżka co wpisy: Konsylium (clinic_ai.diagnose), kworum, limity treści. Człowiek tylko zatwierdza albo
    odrzuca; treści nikt nie edytuje. Nagrań nie pobieramy: link do odtwarzacza Sejmu i sekunda wystąpienia."""
    record = models.OneToOneField('news.PublicRecord', on_delete=models.CASCADE, related_name='video_spin')
    figure = models.ForeignKey('news.PublicFigure', null=True, blank=True, on_delete=models.SET_NULL, related_name='sejm_video_spins')
    day = models.DateField(db_index=True)
    place = models.CharField(max_length=12, choices=[('sala', 'Sala posiedzeń'), ('komisja', 'Komisja')])
    video_unid = models.CharField(max_length=32, blank=True)
    video_url = models.URLField(max_length=1024, blank=True)
    offset_seconds = models.PositiveIntegerField(null=True, blank=True)
    offset_exact = models.BooleanField(default=False, help_text='Sekunda z czasu wystąpienia w API Sejmu (sala); '
                                       'w komisji szacunek z położenia w zapisie przebiegu.')
    rank_score = models.PositiveIntegerField(default=0, help_text='Liczba słów wystąpienia (to samo kryterium dla wszystkich).')
    status = models.CharField(max_length=16, choices=REVIEW_STATUSES + [('withdrawn', 'Wycofana')], default='queued', db_index=True)
    verdict = models.CharField(max_length=12, choices=VERDICTS, blank=True)
    intensity = models.PositiveSmallIntegerField(default=0)
    headline = models.CharField(max_length=200, blank=True)
    summary = models.TextField(blank=True)
    plain = models.JSONField(default=dict, blank=True)
    analysis = models.TextField(blank=True)
    techniques = models.JSONField(default=list, blank=True)
    claims = models.JSONField(default=list, blank=True)
    lab = models.JSONField(default=dict, blank=True)
    limitations = models.TextField(blank=True)
    model_name = models.CharField(max_length=64, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    diagnosed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_reason = models.CharField(max_length=240, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawn_reason = models.CharField(max_length=400, blank=True)

    def save(self, *args, **kwargs):
        if kwargs.get('update_fields') is None or 'techniques' in kwargs['update_fields']:
            self.techniques = categorize_techniques(self.techniques)
        return super().save(*args, **kwargs)

    class Meta:
        ordering = ['-day', '-rank_score', '-pk']
        verbose_name = 'diagnoza wystąpienia w Sejmie'
        verbose_name_plural = 'diagnozy wystąpień w Sejmie'

    def __str__(self):
        return f'{self.day} · {self.record.title[:60]}'


class CitedArticle(models.Model):
    """Strażnik mediów (raport źródeł 6.10, punkt 7): artykuł cytowany w opublikowanej diagnozie albo temacie dnia.

    Trzymamy tylko adres, tytuł, skrót SHA-256 tekstu (bez samego tekstu), daty i linki do kopii w Wayback Machine.
    Zmiana skrótu po cytowaniu = sygnał „artykuł zmieniony po cytowaniu” z kopią sprzed i po zmianie."""
    url = models.URLField(max_length=1024)
    url_sha256 = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=300, blank=True)
    cited_by = models.JSONField(default=list, blank=True, help_text='Odwołania: diagnosis:<id>, sejm:<id>, topic:<temat>.')
    first_cited_at = models.DateTimeField(default=timezone.now, db_index=True)
    archive_url = models.URLField(max_length=1500, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archive_status = models.CharField(max_length=16, blank=True, db_index=True)
    archive_attempts = models.PositiveSmallIntegerField(default=0)
    first_sha256 = models.CharField(max_length=64, blank=True)
    last_sha256 = models.CharField(max_length=64, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    check_status = models.CharField(max_length=24, blank=True)
    changed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    change_count = models.PositiveSmallIntegerField(default=0)
    changed_archive_url = models.URLField(max_length=1500, blank=True)
    history = models.JSONField(default=list, blank=True, help_text='Ostatnie sprawdzenia: data, skrót, kod HTTP (bez treści).')

    class Meta:
        ordering = ['-first_cited_at', '-pk']
        verbose_name = 'artykuł cytowany (strażnik mediów)'
        verbose_name_plural = 'artykuły cytowane (strażnik mediów)'

    def __str__(self):
        return self.url[:120]
