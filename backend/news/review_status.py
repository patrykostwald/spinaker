from news.agent_models import SebaReview
from news.political_models import WardenReview


def panel_section(now):
    from news.admin_status import card, metric
    from news.warden_second_key import enabled as second_enabled
    from news.seba import enabled as seba_enabled
    owner = WardenReview.objects.filter(status='owner')
    pending = WardenReview.objects.filter(status='pending')
    queued = SebaReview.objects.filter(status='queued')
    items = [card('Wymaga Ciebie: @' + row.account.handle, 'warn', row.reason,
                  row.created_at) for row in owner.select_related('account')[:30]]
    return card('Drugi klucz i Seba', 'warn' if owner.exists() or pending.exists() or queued.exists() else 'ok',
        'Dowody i decyzje: sekcja Agenci, Drugi klucz. Odmienne głosy wymagają decyzji człowieka.', now,
        [metric('Wymaga Ciebie', owner.count()), metric('Czeka na drugi odczyt', pending.count()),
         metric('Kolejka Seby', queued.count()), metric('Drugi klucz włączony', second_enabled()),
         metric('Seba włączony', seba_enabled())], items)
