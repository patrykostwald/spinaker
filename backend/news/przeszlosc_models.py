"""Alerty przeszłość.today (sprint 1): dziennikarz obserwuje temat albo osobę publiczną bez zakładania konta.

Podwójne potwierdzenie, jeden list dziennie o 7:00 ze wszystkimi nowościami, wypisanie jednym kliknięciem.
Bez śledzenia: zwykły tekst, bez pikseli i parametrów w linkach. Przechowujemy tylko adres, przedmiot obserwacji i daty.
"""
from django.db import models
from django.utils import timezone


class PrzeszloscAlert(models.Model):
    KINDS = [('topic', 'Temat'), ('person', 'Osoba publiczna')]
    STATUSES = [('pending', 'czeka na potwierdzenie'), ('confirmed', 'aktywny'), ('unsubscribed', 'wypisany')]

    email = models.EmailField(max_length=254, db_index=True)
    kind = models.CharField(max_length=8, choices=KINDS)
    key = models.CharField(max_length=140, help_text='topic:<temat małymi literami> albo person:<id osoby>.')
    query = models.CharField(max_length=120, blank=True, help_text='Temat w brzmieniu użytkownika.')
    figure = models.ForeignKey('news.PublicFigure', null=True, blank=True, on_delete=models.CASCADE, related_name='przeszlosc_alerts')
    status = models.CharField(max_length=12, choices=STATUSES, default='pending', db_index=True)
    token = models.CharField(max_length=64, unique=True, help_text='Link potwierdzenia i wypisania - bez logowania.')
    consent_version = models.CharField(max_length=16)
    created_at = models.DateTimeField(default=timezone.now)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    last_sent_at = models.DateTimeField(null=True, blank=True, help_text='Ostatni dzienny list z tym alertem.')
    sent_ids = models.JSONField(default=list, blank=True, help_text='Ostatnio wysłane pozycje tematu (bez powtórek).')

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['email', 'key'], name='przeszlosc_alert_email_key')]
        verbose_name = 'alert przeszłość.today'
        verbose_name_plural = 'alerty przeszłość.today'

    def __str__(self):
        return f'{self.email}: {self.label} ({self.get_status_display()})'

    @property
    def label(self):
        return self.query if self.kind == 'topic' else (self.figure.canonical_name if self.figure_id else self.key)
