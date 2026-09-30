import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0093_council_recruiter')]
    operations = [migrations.CreateModel(
        name='WalletBalance',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('provider', models.CharField(choices=[('x', 'X API'), ('gemini', 'Gemini / Google AI Studio'), ('anthropic', 'Anthropic / Claude'), ('openrouter', 'OpenRouter'), ('ovh', 'OVH'), ('other', 'Inne')], max_length=20)),
            ('amount', models.DecimalField(decimal_places=4, max_digits=14)),
            ('currency', models.CharField(choices=[('USD', 'USD'), ('EUR', 'EUR'), ('PLN', 'PLN')], default='USD', max_length=3)),
            ('recorded_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
        ],
        options={'ordering': ['-recorded_at', '-pk'], 'constraints': [models.CheckConstraint(condition=models.Q(amount__gte=0), name='wallet_amount_nonnegative')]},
    )]
