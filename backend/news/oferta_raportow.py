"""Prywatna oferta PDF „Raporty spin.clinic” (plan finansowy 6.10, ruch 6). Ceny są tylko tutaj, nigdy na stronie.

Jedna oferta dla wszystkich: ten sam cennik i te same warunki dla każdego kupującego (agencje, firmy, instytucje,
redakcje, uczelnie, partie i sztaby). Zmienia się tylko nazwa odbiorcy i data. Kryteria Dr. Spina nigdy nie są
przedmiotem umowy. Bez AI, bez sieci.
"""
import io
from datetime import timedelta

from django.utils import timezone

from news.report_exports import PAD, WIDTH, Pages
from news.x_card import _font

TIERS = (
    ('Raport tygodniowy', 490, [
        'PDF + CSV co poniedziałek za poprzedni pełny tydzień',
        'wypowiedzi tygodnia z linkami do źródeł i analiz Dr. Spina',
        'techniki perswazji po obu stronach, trend klubów, metoda',
        'licencja do użytku wewnętrznego w organizacji, do 5 osób',
    ]),
    ('Raport i dane', 990, [
        'wszystko z pakietu „Raport tygodniowy”',
        'miesięczne zestawienie wybranego tematu lub branży: projekty ustaw, wypowiedzi, sygnały lobbingu',
        'dane CSV z archiwum diagnoz (od 13.11.2023) do własnych analiz',
        'licencja do użytku wewnętrznego, do 20 osób',
    ]),
)
TERMS = [
    'Ceny netto za miesiąc, do ceny doliczamy VAT 23%. Faktura z góry za miesiąc.',
    'Umowa miesięczna, wypowiedzenie z miesięcznym wyprzedzeniem. Pierwszy raport (próbka) bezpłatnie.',
    'Ten sam cennik i te same warunki dla każdego kupującego, także dla partii i sztabów. Nie ma wariantów zależnych od obozu.',
    'Kupujący nie ma wpływu na kryteria Dr. Spina, wybór wpisów, diagnozy ani treść serwisu. Umowa tego nie obejmuje.',
    'Sprzedajemy nasze analizy i liczby, nie cudze treści. Wpisy polityków są w raporcie linkami do źródeł.',
    'Oferta poufna: ceny nie są publikowane na stronie spin.clinic.',
]


def render(recipient='', today=None):
    today = today or timezone.localdate()
    pages = Pages(False)
    pages.text('Raporty spin.clinic', 42, True)
    pages.text('Oferta dla: ' + (recipient.strip() or '........................................'), 24)
    pages.text(f'Data: {today:%d.%m.%Y} · ważna do {today + timedelta(days=30):%d.%m.%Y}', 20, color='#536174')
    pages.heading('Co dostajesz')
    pages.text('Co tydzień liczby o przekazie rządzących i opozycji z opublikowanych diagnoz Dr. Spina: '
               'te same kryteria dla wszystkich, metoda opisana w każdym raporcie.')
    for name, price, items in TIERS:
        pages.need(320)
        pages.y += 18
        top = pages.y
        pages.text(name, 30, True)
        pages.draw.text((WIDTH - PAD, top), f'{price} zł netto / mies.', fill='#17212e', anchor='ra', font=_font(28, 700))
        for item in items:
            pages.text('·  ' + item, 21)
        pages.draw.line((PAD, pages.y + 6, WIDTH - PAD, pages.y + 6), fill='#dce2e9', width=2)
        pages.y += 14
    pages.heading('Warunki')
    for line in TERMS:
        pages.text('·  ' + line, 20)
    pages.heading('Kontakt')
    pages.text('spin.clinic · iapply sp. z o.o., pl. Wolności 16, 61-739 Poznań · kontakt@spin.clinic', 20)
    out = io.BytesIO()
    images = pages.finish()
    images[0].save(out, format='PDF', save_all=True, append_images=images[1:], resolution=150,
                   title='spin.clinic - oferta raportów', author='iapply sp. z o.o.')
    return out.getvalue()
