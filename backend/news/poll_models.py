"""Szybkie głosowania bez kont i maili (właściciel 3.10.2026): jeden głos na przeglądarkę w każdym pytaniu."""
from django.db import models
from django.utils import timezone


class PollVote(models.Model):
    poll = models.CharField(max_length=40)
    # Losowy identyfikator z przeglądarki głosującego; nie wiąże się z żadną osobą.
    voter = models.CharField(max_length=32)
    # Skrót adresu IP z solą (do limitu głosów z jednej sieci); samego adresu nie zapisujemy.
    network = models.CharField(max_length=32, db_index=True)
    answers = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['poll', 'voter'], name='poll_one_voter')]
