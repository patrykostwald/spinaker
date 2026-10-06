"""Sprzedaż bez wpływu na metodę (plan finansowy 6.10, ruchy 6 i 9).

SalesLead - zapytanie z formularza („Raporty dla instytucji” na /dla-redakcji albo pilot przeszłość.today).
Podwójne potwierdzenie: zapis czeka, aż nadawca kliknie link w e-mailu; dopiero wtedy właściciel dostaje powiadomienie,
a zaznaczona zgoda na newsletter staje się potwierdzonym zapisem. Nie pytamy o poglądy ani przynależność partyjną.

WeeklyReportIssue - „Raport tygodniowy” (PDF + CSV) liczony bez AI co poniedziałek za poprzedni pełny tydzień.
Publiczna próbka (tylko zbiorcze liczby) pojawia się na /dla-redakcji dopiero po zatwierdzeniu w panelu.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class SalesLead(models.Model):
    KINDS = [('raporty', 'Raporty dla instytucji'), ('pilot', 'Pilot przeszłość.today')]
    STATUSES = [('pending', 'czeka na potwierdzenie e-mail'), ('confirmed', 'potwierdzony - do kontaktu'),
                ('contacted', 'w rozmowie'), ('won', 'umowa'), ('lost', 'bez umowy')]
    ORG_TYPES = [('agencja', 'Agencja PR lub public affairs'), ('firma', 'Dział komunikacji firmy'),
                 ('instytucja', 'Instytucja publiczna lub ambasada'), ('nauka', 'Uczelnia lub think tank'),
                 ('redakcja', 'Redakcja lub dziennikarz'), ('ngo', 'Organizacja pozarządowa'),
                 ('partia', 'Partia lub sztab'), ('inne', 'Inne')]

    kind = models.CharField('rodzaj', max_length=8, choices=KINDS, db_index=True)
    name = models.CharField('imię i nazwisko', max_length=120)
    organisation = models.CharField('organizacja', max_length=160, blank=True)
    org_type = models.CharField('typ odbiorcy', max_length=12, choices=ORG_TYPES, default='inne')
    email = models.EmailField(max_length=254, db_index=True)
    message = models.TextField('wiadomość', blank=True, max_length=2000)
    newsletter = models.BooleanField('zgoda na newsletter', default=False)
    status = models.CharField(max_length=12, choices=STATUSES, default='pending', db_index=True)
    token = models.CharField(max_length=64, unique=True)
    consent_version = models.CharField(max_length=24)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    owner_notified_at = models.DateTimeField(null=True, blank=True)
    # Pilot przeszłość.today: bezpłatny Pro do tej daty (przyznaje właściciel w panelu, PRZESZLOSC_PILOT_DAYS dni).
    pilot_until = models.DateField('pilot Pro do', null=True, blank=True)
    notes = models.TextField('notatki zespołu', blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'zapytanie (raporty, pilot)'
        verbose_name_plural = 'zapytania: raporty dla instytucji i piloci'

    def __str__(self):
        return f'{self.get_kind_display()}: {self.organisation or self.name} ({self.get_status_display()})'


class WeeklyReportIssue(models.Model):
    STATUSES = [('ready', 'gotowy (prywatny)'), ('empty', 'za mało danych'), ('failed', 'błąd')]

    week_start = models.DateField('poniedziałek', unique=True)
    week_end = models.DateField('niedziela')
    status = models.CharField(max_length=8, choices=STATUSES, default='ready')
    data = models.JSONField('dane zbiorcze', default=dict)
    pdf = models.BinaryField(null=True, editable=False)
    csv = models.BinaryField(null=True, editable=False)
    generated_at = models.DateTimeField(default=timezone.now, db_index=True)
    public_approved_at = models.DateTimeField('próbka publiczna od', null=True, blank=True)
    public_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                           related_name='+')

    class Meta:
        ordering = ['-week_start']
        verbose_name = 'raport tygodniowy dla instytucji'
        verbose_name_plural = 'raporty tygodniowe dla instytucji'

    def __str__(self):
        return f'Raport tygodniowy {self.week_start:%d.%m}-{self.week_end:%d.%m.%Y}'


from news.agent_models import AgentNote  # noqa: E402


class ZamowienieSygnal(AgentNote):
    """Sygnały pętli „Zamówienia publiczne” (agent='zamowienia') w osobnej liście panelu z decyzją składamy / pomijamy."""
    class Meta:
        proxy = True
        verbose_name = 'zamówienie publiczne (sygnał)'
        verbose_name_plural = 'Zamówienia publiczne: strony i WCAG'
