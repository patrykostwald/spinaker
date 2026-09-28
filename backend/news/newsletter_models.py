"""Zapisy na powiadomienie o starcie spin.clinic (newsletter) — z podwójnym potwierdzeniem."""
from django.db import models
from django.utils import timezone


class NewsletterSubscriber(models.Model):
    STATUSES = [('pending', 'czeka na potwierdzenie'), ('confirmed', 'potwierdzony'), ('unsubscribed', 'wypisany')]

    email = models.EmailField(max_length=254, unique=True)
    status = models.CharField(max_length=12, choices=STATUSES, default='pending', db_index=True)
    token = models.CharField(max_length=64, unique=True, help_text='Link potwierdzenia i wypisania — bez logowania.')
    consent_version = models.CharField(max_length=16, help_text='Wersja treści zgody, którą zaznaczono przy zapisie.')
    source = models.CharField(max_length=64, blank=True, help_text='Miejsce zapisu na stronie (np. home, o-nas).')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.email} ({self.get_status_display()})'
