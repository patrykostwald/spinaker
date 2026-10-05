"""Wyniki analiz liczonych z danych, które już zbieramy (plan Architekta 6.10). Bez AI, ta sama miara dla wszystkich."""
from django.db import models
from django.utils import timezone


class VotingDeviationSnapshot(models.Model):
    """Odstępstwa od klubu w głosowaniach Sejmu: jeden wynik na kadencję i okres (cała kadencja albo ostatnie 90 dni).
    Liczone co noc przez news.voting_anomalies; API czyta gotowy wynik."""
    term = models.PositiveSmallIntegerField()
    period = models.CharField(max_length=10, choices=[('term', 'Cała kadencja'), ('90d', 'Ostatnie 90 dni')])
    computed_at = models.DateTimeField(default=timezone.now)
    data = models.JSONField(default=dict)

    class Meta:
        verbose_name = 'odstępstwa od klubu (wynik)'
        verbose_name_plural = 'odstępstwa od klubu (wyniki)'
        constraints = [models.UniqueConstraint(fields=['term', 'period'], name='unique_voting_deviation_snapshot')]

    def __str__(self):
        return f'kadencja {self.term} · {self.period}'
