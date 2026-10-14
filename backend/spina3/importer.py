"""Importer boxów Dr. Spina (etap D): wpisy polityków, diagnozy jako osobne boxy przypięte systemowo, dokumenty publiczne.

Korzysta z ISTNIEJĄCYCH mechanizmów spin.clinic bez ich zmiany: `news.PoliticalPost` (importer X), `news.SpinDiagnosis`
(diagnoza zatwierdzana przez człowieka w klinice: `clinic.review`), `news.deleted_posts` (wpis usunięty u źródła),
`news.media_rights` (flagi praw), `news.Article` z kategoriami urzędowymi. Żadnych wywołań sieciowych.

Model BOX + BOX (właściciel 11.10, v2): post jest boxem; diagnoza AI jest drugim boxem (kind='diagnosis') związanym z postem
przez BoxLink 'diagnosis_of' (jedna aktualna, historia wersji) i przypiętym systemowo (Pin.kind='diagnosis') jako JEDYNE
przypięcie wpisu: użytkownicy oceniają diagnozę (zgadzam się / nie zgadzam się) i komentują pod parą. Gdy użytkownik
zdążył przypiąć do wpisu wcześniej, przypięcie systemowe nie powstaje (relacja zostaje; zdarzenie w dzienniku).
Cisza wyborcza: nowe boxy diagnoz i przypięcia systemowe trafiają do kolejki wstrzymanych (status 'held').
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from news.clinic_models import SpinDiagnosis
from news.media_rights import article_media_allowed
from news.models import Article, ArticleContent
from news.political_models import PoliticalPost, PublicFigureArticleReference

from . import events
from .config import config, election_silence
from .models import Box, BoxLink, DiagnosisApproval, HeldPublication, Pin, Spina3Profile
from .spinka import recompute
from .text import normalize, short

DOC_CATEGORIES = {'voting': ('voting', 'głosowanie'), 'legislation': ('legal_act', 'akt prawny'),
                  'parliamentary_print': ('document', 'druk sejmowy'), 'document': ('document', 'dokument urzędowy'),
                  'statement': ('document', 'komunikat')}
PRESS_CATEGORIES = {'article': 'article', 'interview': 'article', 'reportage': 'article', 'opinion': 'article',
                    'video': 'video', 'podcast': 'video'}


def dr_spin_user():
    """Konto systemowe Dr. Spina (nieaktywne do logowania, nigdy nie głosuje)."""
    name = getattr(settings, 'SPINA3_DR_SPIN_USERNAME', 'dr_spin')
    user, created = get_user_model().objects.get_or_create(username=name, defaults={'is_active': False})
    profile = Spina3Profile.for_user(user)
    if not profile.is_system:
        profile.is_system = True
        profile.save(update_fields=['is_system'])
    return user


def spin_url(path: str) -> str:
    return f"{getattr(settings, 'SPINA3_SPIN_CLINIC_URL', 'https://spin.clinic')}{path}"


def person_url(figure) -> str:
    base = getattr(settings, 'SPINA3_PRZESZLOSC_URL', 'https://przeszlosc.today')
    path = getattr(settings, 'SPINA3_PRZESZLOSC_PERSON_PATH', '/osoby/{slug}')
    try:
        from news.przeszlosc_osoba import slug as person_slug
        slug_value = person_slug(figure)
    except Exception:  # noqa: BLE001 - brak modułu slug w innej gałęzi nie może zatrzymać importu
        slug_value = str(figure.pk)
    return base + path.format(slug=slug_value, id=figure.pk)


def _figure_for_account(account_id: int):
    try:
        from news.clinic import figures_by_account
        return figures_by_account({account_id}).get(account_id)
    except Exception:  # noqa: BLE001
        return None


def _held(now):
    silence = election_silence(now)
    if not silence['active']:
        return None
    from django.utils.dateparse import parse_datetime
    return parse_datetime(silence['ends_at'])


def _hold_box(box: Box, release_at):
    box.status, box.held_until = 'held', release_at
    box.save(update_fields=['status', 'held_until', 'updated_at'])
    HeldPublication.objects.get_or_create(kind='box', object_id=box.pk, defaults={'release_at': release_at})


# --- wpisy polityków ---------------------------------------------------------------------------------------

@transaction.atomic
def import_post(post: PoliticalPost, now=None) -> Box:
    now = now or timezone.now()
    figure = _figure_for_account(post.account_id)
    author = (post.author_data or {}).get('name') or post.account.display_name
    persons = [{'id': figure.pk, 'name': figure.canonical_name}] if figure else []
    portals = {}
    if figure:
        portals['przeszlosc_url'] = person_url(figure)
    group = ''
    if figure:
        try:
            from news.clinic import party_affiliation
            group = (party_affiliation(figure) or {}).get('party') or ''
        except Exception:  # noqa: BLE001
            group = ''
    defaults = {
        'kind': 'post', 'post': post, 'added_by': 'dr_spin', 'title': short(post.text, 80) or f'Wpis @{post.account.handle}',
        'source_name': 'X', 'source_domain': 'x.com', 'author_name': author, 'author_handle': post.account.handle,
        'author_group': group, 'text': post.text, 'show_title': True, 'show_quote': True, 'show_thumbnail': False,
        'show_avatar': False, 'published_at': post.published_at, 'persons': persons, 'portals': portals,
        'source_status': 'active' if post.available else 'removed_at_source',
        'search_text': normalize(f'{post.text} {author} {post.account.handle}'),
    }
    box, created = Box.objects.get_or_create(url=post.url, defaults=defaults)
    if not created:
        changed = False
        for key in ('text', 'title', 'persons', 'portals', 'author_group'):
            if getattr(box, key) != defaults[key] and post.available:
                setattr(box, key, defaults[key])
                changed = True
        if changed:
            box.search_text = defaults['search_text']
            box.save()
    if not post.available:
        mark_post_removed(box, now)
    return box


def import_posts(limit: int = 200, days: int | None = None, now=None) -> dict:
    """Wpisy zweryfikowanych kont (ten sam zestaw co w klinice: enabled i potwierdzone), bez kolorów obozów."""
    now = now or timezone.now()
    days = days or config().default_period_days
    rows = (PoliticalPost.objects.filter(account__enabled=True, account__confirmed_at__isnull=False,
                                         published_at__gte=now - timedelta(days=days))
            .exclude(url__in=Box.objects.filter(kind='post').values_list('url', flat=True))
            .select_related('account').order_by('-published_at')[:limit])
    created = 0
    for post in rows:
        import_post(post, now)
        created += 1
    return {'posts_created': created}


@transaction.atomic
def mark_post_removed(box: Box, now=None) -> None:
    """Wpis usunięty u źródła (news.deleted_posts): treść znika, zostaje fakt i przypięcia; S zamrożone, nowe przypięcia blokowane."""
    now = now or timezone.now()
    if box.source_status == 'removed_at_source' and not box.text:
        return
    date = timezone.localtime(box.published_at).strftime('%d.%m.%Y') if box.published_at else ''
    box.source_status, box.text, box.quote, box.thumbnail_url = 'removed_at_source', '', '', ''
    box.title = f'Wpis z {date}, usunięty przez autora'.replace(' ,', ',')
    box.search_text = normalize(f'{box.author_name} {box.author_handle}')
    box.save()
    events.log('system', box, meta={'removed_at_source': True}, now=now)
    recompute(box, now)
    from .pins import mark_target_unavailable
    mark_target_unavailable(box, now)


def sync_removed_posts(now=None) -> int:
    count = 0
    for box in Box.objects.filter(kind='post', post__available=False, source_status='active').select_related('post'):
        mark_post_removed(box, now)
        count += 1
    return count


# --- diagnozy: BOX + BOX --------------------------------------------------------------------------------------

def diagnosis_visible(diagnosis: SpinDiagnosis) -> bool:
    return (diagnosis.status == 'approved' and not diagnosis.withdrawn_at and not diagnosis.hidden_at
            and diagnosis.reviewed_at is not None and diagnosis.post.available)


def _technique(diagnosis: SpinDiagnosis) -> str:
    first = next(iter(diagnosis.techniques or []), {})
    return str(first.get('name') or '').strip()[:160] if isinstance(first, dict) else ''


def _diagnosis_sources(diagnosis: SpinDiagnosis) -> list[str]:
    """Źródła wersji: wpis, którego dotyczy diagnoza, i adresy wskazane w tezach (bez danych osobowych)."""
    sources = [diagnosis.post.url] if getattr(diagnosis.post, 'url', '') else []
    for claim in diagnosis.claims or []:
        if isinstance(claim, dict):
            for key in ('source_url', 'url', 'source'):
                value = claim.get(key)
                if isinstance(value, str) and value.startswith('http') and value not in sources:
                    sources.append(value)
    return sources[:20]


def record_approval(post_box: Box, diagnosis_box: Box, diagnosis: SpinDiagnosis, now=None, *, change: str = '') -> DiagnosisApproval | None:
    """Log zatwierdzeń: nowa wersja przy imporcie i przy każdej zmianie treści, zatwierdzającego, modelu albo stanu."""
    import hashlib
    now = now or timezone.now()
    withdrawn = not diagnosis_visible(diagnosis)
    model = '/'.join(part for part in (diagnosis.provider, diagnosis.model_name) if part)
    raw = '|'.join(str(v) for v in (diagnosis.headline, diagnosis.summary, diagnosis.reviewed_at, diagnosis.reviewed_by_id, model,
                                    diagnosis.prompt_version, withdrawn))
    signature = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    last = DiagnosisApproval.objects.filter(diagnosis_box=diagnosis_box).order_by('-version').first()
    if last is not None and last.signature == signature:
        return None
    if not change:
        change = 'withdrawn' if withdrawn else ('created' if last is None else ('restored' if last.change == 'withdrawn' else 'updated'))
    return DiagnosisApproval.objects.create(
        box=post_box, diagnosis_box=diagnosis_box, version=(last.version + 1) if last else 1, change=change,
        approved_by=diagnosis.reviewed_by, approved_by_account=diagnosis.reviewed_by_id, approved_at=diagnosis.reviewed_at,
        model=model[:100], sources=_diagnosis_sources(diagnosis), signature=signature, created_at=now)


def approval_payload(row: DiagnosisApproval, current_id: int | None = None) -> dict:
    """Wpis historii publicznie: numer konta zespołu zamiast imienia."""
    return {'version': row.version, 'target_id': row.diagnosis_box_id, 'current': row.pk == current_id, 'change': row.change,
            'approved_by': f'konto zespołu nr {row.approved_by_account}' if row.approved_by_account else None,
            'approved_at': row.approved_at.isoformat() if row.approved_at else None, 'model': row.model, 'sources': list(row.sources or []),
            'label': row.label, 'created_at': row.created_at.isoformat()}


def diagnosis_history(box: Box) -> list[dict]:
    from django.db.models import Q
    rows = list(DiagnosisApproval.objects.filter(Q(box=box) | Q(diagnosis_box=box)).order_by('created_at', 'pk'))
    if not rows:   # relacje sprzed logu zatwierdzeń (S2): wersje z BoxLink, bez zatwierdzającego i modelu
        links = BoxLink.objects.filter(Q(box=box) | Q(target=box), kind='diagnosis_of').order_by('version', 'pk')
        return [{'version': link.version, 'target_id': link.target_id, 'current': link.is_current, 'change': 'created',
                 'approved_by': None, 'approved_at': None, 'model': '', 'sources': [],
                 'label': DiagnosisApproval._meta.get_field('label').default, 'created_at': link.created_at.isoformat()}
                for link in links]
    current = rows[-1].pk if rows[-1].change != 'withdrawn' else None
    return [approval_payload(row, current) for row in rows]


@transaction.atomic
def sync_diagnosis(diagnosis: SpinDiagnosis, now=None) -> tuple[Box | None, Pin | None]:
    """Diagnoza zatwierdzona przez człowieka -> box 'diagnosis' + BoxLink 'diagnosis_of' + przypięcie systemowe Dr. Spina.
    Wycofana, ukryta albo wpis usunięty -> box i przypięcie ukryte (relacja zostaje w historii)."""
    now = now or timezone.now()
    post_box = Box.objects.filter(post=diagnosis.post).first()
    if post_box is None:
        post_box = import_post(diagnosis.post, now)
    url = spin_url(f'/klinika/{diagnosis.pk}')
    if not diagnosis_visible(diagnosis):
        box = Box.objects.filter(url=url).first()
        if box is not None and box.status != 'hidden':
            box.status = 'hidden'
            box.save(update_fields=['status', 'updated_at'])
            from .pins import mark_target_unavailable
            mark_target_unavailable(box, now)
        pin = Pin.objects.filter(box=post_box, kind='diagnosis').first()
        if pin is not None and pin.status != 'hidden':
            pin.status, pin.hidden_reason = 'hidden', 'diagnoza wycofana albo wpis usunięty'
            pin.save(update_fields=['status', 'hidden_reason', 'updated_at'])
        if box is not None and DiagnosisApproval.objects.filter(diagnosis_box=box).exists():
            record_approval(post_box, box, diagnosis, now)
        return box, pin
    release_at = _held(now)
    title = short(f'Diagnoza: {diagnosis.headline}', 200)
    technique = _technique(diagnosis)
    defaults = {
        'kind': 'diagnosis', 'diagnosis': diagnosis, 'added_by': 'dr_spin', 'title': title, 'source_name': 'spin.clinic',
        'source_domain': 'spin.clinic', 'author_name': 'Dr. Spin', 'text': diagnosis.summary or '', 'quote': short(diagnosis.summary, 300),
        'show_title': True, 'show_quote': True, 'show_thumbnail': False, 'published_at': diagnosis.reviewed_at or diagnosis.created_at,
        'persons': post_box.persons, 'topic': post_box.topic, 'subtype': technique,
        'portals': {'spin_diagnosis_url': url, **({'przeszlosc_url': post_box.portals.get('przeszlosc_url')} if post_box.portals.get('przeszlosc_url') else {})},
        'search_text': normalize(f'{title} {technique} {post_box.author_name}'), 'status': 'published',
    }
    box, created = Box.objects.get_or_create(url=url, defaults=defaults)
    if not created and (box.title != title or box.status == 'hidden' or box.text != defaults['text']):
        box.title, box.text, box.quote, box.subtype = title, defaults['text'], defaults['quote'], technique
        if box.status == 'hidden':
            box.status = 'published'
            from .pins import restore_target
            restore_target(box, now)
        box.save()
    if created and release_at:
        _hold_box(box, release_at)
    if not post_box.portals.get('spin_diagnosis_url'):
        post_box.portals = {**post_box.portals, 'spin_diagnosis_url': url}
        post_box.save(update_fields=['portals', 'updated_at'])
    current = BoxLink.objects.filter(box=post_box, kind='diagnosis_of', is_current=True).first()
    if current is None or current.target_id != box.pk:
        version = 1
        if current is not None:
            current.is_current, current.superseded_at = False, now
            current.save(update_fields=['is_current', 'superseded_at'])
            version = current.version + 1
        BoxLink.objects.create(box=post_box, target=box, kind='diagnosis_of', version=version, created_at=now)
    record_approval(post_box, box, diagnosis, now)
    pin = Pin.objects.filter(box=post_box, kind='diagnosis').first()
    pin_created = False
    if pin is None:
        other = Pin.objects.filter(box=post_box).exclude(status='removed').first()
        if other is not None:
            # Box ma już przypięcie użytkownika (jedno na box): diagnoza zostaje w relacji BoxLink, bez przypięcia systemowego.
            events.log('system', post_box, meta={'diagnosis_pin_skipped': True, 'user_pin_id': other.pk}, now=now)
            recompute(post_box, now)
            return box, None
        pin = Pin.objects.create(
            box=post_box, kind='diagnosis', user=dr_spin_user(), pinned_box=box, diagnosis=diagnosis,
            diagnosis_title=short(diagnosis.headline, 200), diagnosis_url=url, technique=technique, stance=None, status='published',
            approved_at=diagnosis.reviewed_at, approved_by=diagnosis.reviewed_by, created_at=diagnosis.reviewed_at or now)
        pin_created = True
    if not pin_created:
        pin.pinned_box, pin.diagnosis, pin.diagnosis_title, pin.technique = box, diagnosis, short(diagnosis.headline, 200), technique
        pin.approved_at, pin.approved_by = diagnosis.reviewed_at, diagnosis.reviewed_by
        if pin.status == 'hidden':
            pin.status, pin.hidden_reason = 'published', ''
        pin.save()
    if pin_created and release_at:
        pin.status, pin.held_until = 'held', release_at
        pin.save(update_fields=['status', 'held_until', 'updated_at'])
        HeldPublication.objects.get_or_create(kind='pin', object_id=pin.pk, defaults={'release_at': release_at})
    recompute(post_box, now)
    return box, pin


def sync_diagnoses(limit: int = 500, now=None) -> dict:
    now = now or timezone.now()
    synced = 0
    rows = SpinDiagnosis.objects.filter(status__in=['approved', 'withdrawn']).select_related('post__account').order_by('-reviewed_at')[:limit]
    for diagnosis in rows:
        sync_diagnosis(diagnosis, now)
        synced += 1
    return {'diagnoses_synced': synced}


# --- dokumenty publiczne i prasa --------------------------------------------------------------------------------

def _persons_for_article(article: Article) -> list[dict]:
    refs = PublicFigureArticleReference.objects.filter(article=article, verification_status='confirmed').select_related('public_figure')
    return [{'id': r.public_figure.pk, 'name': r.public_figure.canonical_name} for r in refs]


@transaction.atomic
def import_article(article: Article, now=None) -> Box | None:
    now = now or timezone.now()
    category = article.category
    if category in DOC_CATEGORIES:
        kind, subtype = DOC_CATEGORIES[category]
        allowed = article_media_allowed(article)
        if not allowed:
            return None  # dokument spoza źródeł urzędowych: nie wyświetlamy w całości
        content = ArticleContent.objects.filter(article=article).first()
        text = content.text if content and content.status != 'metadata_only' else ''
    elif category in PRESS_CATEGORIES:
        from .config import flags
        if not flags().import_press:
            return None
        kind, subtype = PRESS_CATEGORIES[category], category
        allowed = article_media_allowed(article)
        text = ''
    else:
        return None
    persons = _persons_for_article(article)
    portals = {}
    if persons:
        figure = PublicFigureArticleReference.objects.filter(article=article, verification_status='confirmed').select_related('public_figure').first()
        if figure:
            portals['przeszlosc_url'] = person_url(figure.public_figure)
    source = article.source
    from urllib.parse import urlsplit
    domain = (urlsplit(article.url).hostname or '').removeprefix('www.')
    defaults = {
        'kind': kind, 'subtype': subtype, 'article': article, 'added_by': 'importer', 'title': article.title[:500],
        'source_name': source.name if source else domain, 'source_domain': domain, 'author_name': article.author,
        'text': text if allowed else '', 'quote': short(article.description, 300) if allowed else '',
        'thumbnail_url': article.image_url if allowed else '', 'show_title': True, 'show_quote': allowed,
        'show_thumbnail': bool(allowed and article.image_url), 'published_at': article.published_date or article.created_at,
        'persons': persons, 'portals': portals, 'topic': (article.tags or [''])[0] if isinstance(article.tags, list) and article.tags else '',
        'search_text': normalize(f'{article.title} {article.author} {article.description if allowed else ""}'),
    }
    box, _ = Box.objects.get_or_create(url=article.url, defaults=defaults)
    return box


def import_documents(limit: int = 500, days: int | None = None, now=None) -> dict:
    now = now or timezone.now()
    days = days or config().default_period_days
    rows = (Article.objects.filter(category__in=list(DOC_CATEGORIES), published_date__gte=now - timedelta(days=days))
            .exclude(url__in=Box.objects.filter(article__isnull=False).values_list('url', flat=True))
            .select_related('source').order_by('-published_date')[:limit])
    created = sum(1 for a in rows if import_article(a, now) is not None)
    return {'documents_created': created}


def import_press(limit: int = 500, days: int | None = None, now=None) -> dict:
    now = now or timezone.now()
    days = days or config().default_period_days
    rows = (Article.objects.filter(category__in=list(PRESS_CATEGORIES), published_date__gte=now - timedelta(days=days))
            .exclude(url__in=Box.objects.filter(article__isnull=False).values_list('url', flat=True))
            .select_related('source').order_by('-published_date')[:limit])
    created = sum(1 for a in rows if import_article(a, now) is not None)
    return {'press_created': created}


def run_all(now=None) -> dict:
    """Pełny przebieg (zadanie okresowe): wpisy, diagnozy, dokumenty, usunięte wpisy, zwolnienie wstrzymanych,
    wygaśnięcie 7 dni, odświeżenie wag i klastrów."""
    from .pins import expire_unavailable, release_held
    from .spinka import refresh_account_weights, refresh_clusters
    now = now or timezone.now()
    out = {}
    out.update(import_posts(now=now))
    out.update(sync_diagnoses(now=now))
    out.update(import_documents(now=now))
    out['posts_removed'] = sync_removed_posts(now)
    out['released'] = release_held(now)
    out['expired'] = expire_unavailable(now)
    out['weights_recomputed'] = refresh_account_weights(now)
    out['clusters'] = len(refresh_clusters(now))
    return out
