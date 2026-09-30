"""Owner-entered balance observations, never provider credentials."""
from django.db import models
from django.utils import timezone


PROVIDERS = [('x', 'X API'), ('gemini', 'Gemini / Google AI Studio'),
             ('anthropic', 'Anthropic / Claude'), ('openrouter', 'OpenRouter'),
             ('ovh', 'OVH'), ('other', 'Inne')]
CURRENCIES = [('USD', 'USD'), ('EUR', 'EUR'), ('PLN', 'PLN')]


class WalletBalance(models.Model):
    provider = models.CharField(max_length=20, choices=PROVIDERS)
    amount = models.DecimalField(max_digits=14, decimal_places=4)
    currency = models.CharField(max_length=3, choices=CURRENCIES, default='USD')
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-recorded_at', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(amount__gte=0), name='wallet_amount_nonnegative')]
