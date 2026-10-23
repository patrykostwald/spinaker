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


class KrsKolejka(models.Model):
    """Kolejka uzupełniania KRS (sprint 23.10): numer KRS albo NIP podmiotu do sprawdzenia w oficjalnych rejestrach.

    Tylko identyfikatory podmiotów - bez nazw osób. NIP sprawdzamy w Białej liście MF (zwraca numer KRS), KRS w api-krs.ms.gov.pl.
    Błędy sieci ponawiamy z rosnącą przerwą; „brak w rejestrze” to osobny stan, nie błąd.
    """
    KINDS = [('krs', 'numer KRS'), ('nip', 'NIP')]
    STATUSES = [('pending', 'czeka'), ('ok', 'pobrano odpis'), ('missing', 'brak w rejestrze'),
                ('no_krs', 'Biała lista nie podaje numeru KRS dla tego NIP'), ('mismatch', 'NIP z KRS niezgodny'),
                ('error', 'błąd rejestru - ponowimy')]

    kind = models.CharField(max_length=4, choices=KINDS)
    value = models.CharField(max_length=10)
    origin = models.CharField(max_length=24, blank=True, help_text='Skąd numer: org, niw, ted_wykonawca, ted_zamawiajacy, bzp, fts.')
    priority = models.PositiveSmallIntegerField(default=5, help_text='0 najpilniejsze.')
    status = models.CharField(max_length=10, choices=STATUSES, default='pending', db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_try_at = models.DateTimeField(default=timezone.now, db_index=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    krs_number = models.CharField(max_length=10, blank=True, help_text='Wynik: numer KRS podmiotu.')
    organisation = models.ForeignKey('news.RegisteredOrganisation', null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='krs_kolejka')
    last_error = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['priority', 'next_try_at', 'pk']
        constraints = [models.UniqueConstraint(fields=['kind', 'value'], name='krs_kolejka_kind_value')]
        verbose_name = 'kolejka KRS'
        verbose_name_plural = 'kolejka KRS'

    def __str__(self):
        return f'{self.kind} {self.value}: {self.status}'
