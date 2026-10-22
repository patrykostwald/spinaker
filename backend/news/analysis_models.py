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


class CoordinatedCluster(models.Model):
    """Wspólny przekaz: prawie identyczne zdania z co najmniej 3 różnych kont w krótkim oknie (news.coordinated).
    Klaster to obserwacja z danych, nie dowód zmowy; te same progi dla wszystkich obozów."""
    phrase = models.TextField(help_text='Przykładowe brzmienie (najwcześniejszy dostępny wpis klastra).')
    posts = models.ManyToManyField('news.PoliticalPost', related_name='coordinated_clusters')
    first_at = models.DateTimeField(db_index=True)
    last_at = models.DateTimeField(db_index=True)
    accounts_count = models.PositiveSmallIntegerField(default=0)
    posts_count = models.PositiveSmallIntegerField(default=0)
    accounts = models.JSONField(default=list, help_text='Konta: handle, nazwa, partia, obóz.')
    parties = models.JSONField(default=list)
    camps = models.JSONField(default=list)
    cross_party = models.BooleanField(default=False, db_index=True)
    cross_camp = models.BooleanField(default=False)
    similarity = models.FloatField(default=0, help_text='Najniższe podobieństwo krawędzi w klastrze (Jaccard 5-gramów).')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'wspólny przekaz (klaster)'
        verbose_name_plural = 'wspólny przekaz (klastry)'
        ordering = ['-first_at', '-pk']

    def __str__(self):
        return f'{self.accounts_count} kont: {self.phrase[:60]}'
