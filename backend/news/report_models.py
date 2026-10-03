"""Private report snapshots and an append-only review journal. No delivery model."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


REPORT_TYPES = [('weekly', 'Raport tygodniowy przekazu'), ('topic', 'Monitoring tematu / branży'),
                ('profile', 'Profil wypowiedzi'), ('weekly_en', 'Weekly in English'),
                ('research', 'Dane do badań')]
REPORT_STATUSES = [('queued', 'W kolejce'), ('working', 'W recenzji'), ('blocked', 'Brakuje danych'),
                   ('awaiting_approval', 'Do zatwierdzenia'), ('approved', 'Zatwierdzony'),
                   ('rejected', 'Odrzucony')]


class InstitutionalReport(models.Model):
    kind = models.CharField('typ', max_length=16, choices=REPORT_TYPES)
    audience = models.CharField('odbiorcy', max_length=64)
    # One free example per audience, independent of report type or concurrent commands.
    sample_key = models.CharField(max_length=64, unique=True)
    scope = models.JSONField('zakres', default=dict)
    status = models.CharField('status', max_length=24, choices=REPORT_STATUSES, default='queued', db_index=True)
    snapshot = models.JSONField('dane i metoda', default=dict)
    gate = models.JSONField('gotowość danych', default=dict)
    draft = models.JSONField('tekst', default=dict)
    extra_roles = models.JSONField('konsultacje', default=list)
    panel = models.JSONField('modele', default=dict)
    phase = models.CharField(max_length=24, default='draft')
    round = models.PositiveSmallIntegerField('runda', default=1)
    cursor = models.PositiveSmallIntegerField(default=0)
    objections = models.JSONField('zastrzeżenia', default=list)
    pdf = models.BinaryField(null=True, editable=False)
    csv = models.BinaryField(null=True, editable=False)
    method = models.TextField('metoda i źródła', blank=True)
    artifact_hash = models.CharField(max_length=64, blank=True)
    approved_hash = models.CharField(max_length=64, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='+')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField('utworzono', default=timezone.now)

    class Meta:
        verbose_name = 'raport dla instytucji'
        verbose_name_plural = 'raporty dla instytucji'
        constraints = [models.CheckConstraint(condition=models.Q(round__gte=1, round__lte=3),
                                               name='reports_max_three_rounds_092')]


class ReportReview(models.Model):
    report = models.ForeignKey(InstitutionalReport, on_delete=models.PROTECT, related_name='reviews')
    round = models.PositiveSmallIntegerField()
    slot = models.CharField(max_length=64)
    role = models.CharField(max_length=64)
    provider = models.CharField(max_length=32)
    model = models.CharField(max_length=200)
    draft_hash = models.CharField(max_length=64)
    decision = models.CharField(max_length=24, default='started')
    response = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=['report', 'slot'], name='reports_unique_step_092')]
        verbose_name = 'recenzja raportu'
        verbose_name_plural = 'recenzje raportów'


class ReportDailyBudget(models.Model):
    day = models.DateField(unique=True)
    calls = models.PositiveIntegerField(default=0)


class ReportObservation(models.Model):
    """Reviewed analytical input contract for public-data/narrative collectors.

    Until those collectors supply this contract, explicit editorial verification
    is required. This table stores our analysis and references, never post text.
    """
    KINDS = [('bill', 'Projekt ustawy'), ('amendment', 'Poprawka'), ('lobbying', 'Sygnał lobbingu'),
             ('stance', 'Stanowisko w wypowiedzi')]
    external_key = models.CharField('klucz źródłowy', max_length=200, unique=True)
    kind = models.CharField('rodzaj', max_length=16, choices=KINDS)
    topic = models.SlugField('temat', max_length=100, db_index=True)
    day = models.DateField('data', db_index=True)
    analysis = models.CharField('nasza analiza', max_length=500,
                                help_text='Własny opis analityczny. Bez treści i cytatów z cudzych wpisów.')
    source_url = models.URLField('źródło', max_length=1024)
    corroborating_url = models.URLField('drugie źródło', max_length=1024, blank=True)
    confidence = models.CharField('pewność', max_length=12, default='low',
        choices=[('low', 'Niska'), ('medium', 'Umiarkowana'), ('high', 'Wysoka')])
    confidence_reason = models.CharField('podstawa poziomu pewności', max_length=400)
    figure = models.ForeignKey('news.PublicFigure', null=True, blank=True, on_delete=models.PROTECT,
                               verbose_name='osoba')
    diagnosis = models.ForeignKey('news.SpinDiagnosis', null=True, blank=True, on_delete=models.PROTECT,
                                  verbose_name='diagnoza wypowiedzi')
    stance = models.CharField('stanowisko', max_length=12, blank=True,
                              choices=[('support', 'Poparcie'), ('oppose', 'Sprzeciw'), ('neutral', 'Neutralne')])
    ballot = models.ForeignKey('news.Ballot', null=True, blank=True, on_delete=models.PROTECT,
                               verbose_name='powiązany głos')
    # A verified semantic mapping is necessary for amendments and procedural motions.
    supporting_vote = models.CharField('głos oznaczający poparcie tej tezy', max_length=30, blank=True,
                                       help_text='Dokładna wartość vote ze źródła. Nie wnioskuj jej z tytułu głosowania.')
    approved = models.BooleanField('zweryfikowane', default=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+', editable=False)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = 'obserwacja do raportów'
        verbose_name_plural = 'obserwacje do raportów'
        constraints = [models.UniqueConstraint(fields=['topic', 'diagnosis'], condition=models.Q(kind='stance'),
                                               name='reports_one_stance_per_topic_092')]

    def clean(self):
        if self.kind == 'stance' and (not self.figure_id or not self.diagnosis_id or not self.stance):
            raise ValidationError('Stanowisko wymaga osoby, diagnozy i klasyfikacji.')
        if self.ballot_id:
            if self.kind != 'stance' or not self.supporting_vote:
                raise ValidationError('Porównanie z głosem wymaga stanowiska i zweryfikowanego znaczenia głosu.')
            roster = self.figure.parliamentary_roster_entry if self.figure_id else None
            if (not roster or roster.source != 'sejm' or str(self.ballot.mp_id) != roster.external_id
                    or self.ballot.voting.term != roster.term):
                raise ValidationError('Głos nie odpowiada potwierdzonemu mandatowi i kadencji tej osoby.')
            if self.supporting_vote not in ('YES', 'NO'):
                raise ValidationError('Porównanie wymaga jednoznacznego głosowania YES/NO.')
        if self.diagnosis_id and self.figure_id:
            from news.clinic import figures_by_account
            identity = figures_by_account([self.diagnosis.post.account_id])
            if getattr(identity.get(self.diagnosis.post.account_id), 'pk', None) != self.figure_id:
                raise ValidationError('Diagnoza nie jest potwierdzoną wypowiedzią tej osoby.')
            if self.day != timezone.localdate(self.diagnosis.post.published_at):
                raise ValidationError('Data stanowiska musi odpowiadać dacie wypowiedzi.')
        if self.confidence == 'high' and (not self.corroborating_url or self.corroborating_url == self.source_url):
            raise ValidationError('Wysoka pewność wymaga drugiego źródła.')

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.get(pk=self.pk)
            analytical = ('kind', 'topic', 'day', 'analysis', 'source_url', 'corroborating_url', 'confidence',
                          'confidence_reason', 'figure_id', 'diagnosis_id', 'stance', 'ballot_id', 'supporting_vote')
            if any(getattr(old, key) != getattr(self, key) for key in analytical):
                # Changed evidence must be verified again, never silently inherit approval.
                self.approved, self.verified_by, self.verified_at = False, None, None
                if kwargs.get('update_fields'):
                    kwargs['update_fields'] = set(kwargs['update_fields']) | {'approved', 'verified_by', 'verified_at'}
        super().save(*args, **kwargs)
