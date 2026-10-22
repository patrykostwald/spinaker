"""Zgłoszenia błędów i mapa ścieżek (właściciel 5.10: „przycisk zgłoś błąd” + „każdy user journey zapisywać”).

Ścieżki (decyzja 4.10): tylko trasa przez serwis, nic o osobie. Bez identyfikatora, IP, ciasteczek i pamięci
przeglądarki; od razu zliczane w godzinnych koszykach, więc surowych zdarzeń nie ma czego kasować.
"""
from django.conf import settings
from django.db import models


class BugReport(models.Model):
    KINDS = [('bug', 'Błąd'), ('idea', 'Pomysł')]
    STATUSES = [('new', 'Nowe'), ('fixed', 'Naprawione'), ('rejected', 'Nie dotyczy')]
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    kind = models.CharField(max_length=8, choices=KINDS, default='bug')
    text = models.TextField(max_length=1200)
    path = models.CharField(max_length=200)
    # dołączane jawnie (formularz mówi, co wysyła): rozmiar ekranu, motyw, ostatnie strony tej wizyty
    viewport = models.CharField(max_length=20, blank=True)
    theme = models.CharField(max_length=10, blank=True)
    trail = models.JSONField(default=list, blank=True)
    contact = models.EmailField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    status = models.CharField(max_length=10, choices=STATUSES, default='new', db_index=True)
    staff_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'zgłoszenie błędu'
        verbose_name_plural = 'zgłoszenia błędów'


class JourneyStep(models.Model):
    """Ile razy w danej godzinie ktoś przeszedł z jednego miejsca do drugiego (lub kliknął element)."""
    hour = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=120)
    target = models.CharField(max_length=120)
    action = models.CharField(max_length=60)
    device = models.CharField(max_length=8)  # telefon / komputer, z szerokości ekranu
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['hour', 'source', 'target', 'action', 'device'], name='journey_step_unique')]
        verbose_name = 'krok ścieżki'
        verbose_name_plural = 'ścieżki użytkowników (zbiorczo)'


class ClientNote(models.Model):
    """Uwagi klientów do podglądów stron zbudujmi (właściciel 6.10: podgląd u nas zamiast na Claude, kontakt przez
    zbudujmi). Klient klika miejsce na stronie i pisze uwagę; zapisujemy tylko to, co sam wpisał, plus miejsce."""
    STATUSES = [('new', 'Nowa'), ('done', 'Wprowadzona'), ('rejected', 'Nie wprowadzamy')]
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    project = models.CharField(max_length=60, db_index=True)
    page = models.CharField(max_length=200, blank=True)
    # miejsce kliknięcia jako ułamek szerokości i wysokości dokumentu (0-1) oraz najbliższy nagłówek sekcji
    x = models.FloatField(null=True, blank=True)
    y = models.FloatField(null=True, blank=True)
    anchor = models.CharField(max_length=200, blank=True)
    text = models.TextField(max_length=2000)
    name = models.CharField(max_length=120, blank=True)
    viewport = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default='new', db_index=True)
    staff_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'uwaga klienta (zbudujmi)'
        verbose_name_plural = 'uwagi klientów (zbudujmi)'
