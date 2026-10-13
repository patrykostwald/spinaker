"""Serializacja publiczna według flag praw: publiczne API nie zwraca pól spoza flag (tytuł, cytat, miniatura, awatar).

Pełna treść tylko dla wpisów z API platformy (box aktywny) i dokumentów publicznych (show_quote). Wpis usunięty
u źródła: "Autor usunął wpis", bez treści. Cisza wyborcza i zasłona kalibracyjna (levels_visible=false): spinka szara,
n i rozkład nadal widoczne. Autorzy: nick, znaczek (dr_spin | team | author | ''), kolor nicku z listy.
"""
from __future__ import annotations

from django.conf import settings

from . import scoring
from .config import (AUTHOR_STANCE_NAMES, COLORS, FORMULA_VERSION, LEVEL_LABELS, NICK_COLOR_DEFAULT, OPEN, STANCE_NAMES,
                     election_silence, flags)
from .models import Box, BoxSpinka, Comment, Pin

EMPTY_DIST = {'agree': 0, 'disagree': 0}


def spinka_payload(sp: BoxSpinka | None, *, silence: bool = False, levels_visible: bool = True) -> dict:
    if sp is None:
        sp = BoxSpinka(level=OPEN, level_reason='no_pin', distribution=dict(EMPTY_DIST))
    level, reason = sp.level, sp.level_reason
    if silence:
        level, reason = OPEN, 'silence'
    elif not levels_visible:
        level, reason = OPEN, 'calibration'
    label = {'silence': 'cisza wyborcza', 'calibration': 'kolory po kalibracji'}.get(reason, LEVEL_LABELS[level])
    dist = {**EMPTY_DIST, **(sp.distribution or {})}
    dist.pop('doubt', None)
    views = sp.views or {}
    return {
        'n': sp.n, 'level': level, 'label': label, 'color': COLORS[level], 'score': round(sp.score, 3) if level != OPEN else None,
        'reason': reason, 'pending': bool(sp.level_pending), 'distribution': dist,
        'dispute': bool(views.get('dispute')), 'views': {k: bool(v) for k, v in views.items() if k != 'eligible'},
        'last_rating_at': sp.last_rating_at.isoformat() if sp.last_rating_at else None,
        'aria': scoring.aria_label(level, sp.score, sp.n, reason), 'formula_version': FORMULA_VERSION,
    }


def author_info(user, *, is_team: bool = False, anonymized: bool = False, is_author: bool = False) -> dict:
    """Nick, znaczek i kolor nicku; konto usunięte = "konto usunięte" bez koloru."""
    if anonymized or user is None:
        return {'nick': 'konto usunięte', 'badge': '', 'color': None, 'is_team': False, 'system': False, 'label': ''}
    profile = getattr(user, 'spina3_profile', None)
    system = bool(profile and profile.is_system)
    team = is_team or bool(profile and profile.is_team)
    if system:
        return {'nick': 'Dr. Spin', 'badge': 'dr_spin', 'color': 'spin', 'is_team': False, 'system': True,
                'label': 'Diagnoza AI, zatwierdzona przez zespół spina3'}
    badge = 'team' if team else ('author' if is_author else '')
    color = (profile.nick_color if profile and profile.nick_color else NICK_COLOR_DEFAULT)
    return {'nick': user.username, 'badge': badge, 'color': color, 'is_team': team, 'system': False,
            'label': 'zespół: kontekst' if team else ('autor' if is_author else '')}


def _author(box: Box) -> dict | None:
    if not box.author_name and not box.author_handle:
        return None
    return {'name': box.author_name, 'handle': box.author_handle, 'initials': box.author_initials,
            'avatar_url': box.thumbnail_url if box.show_avatar else ''}


def pin_summary(pin: Pin | None) -> dict | None:
    """Skrót przypięcia na kafelek: kto, co i jakim rodzajem dowodu."""
    if pin is None:
        return None
    target_title = pin.diagnosis_title if pin.kind == 'diagnosis' else (pin.pinned_box.title if pin.pinned_box_id and pin.target_status == 'ok' else '')
    target_box = pin.pinned_box if pin.kind not in ('url', 'image') and pin.pinned_box_id else None
    target = {'box_id': target_box.pk if target_box else None,
              'title': target_title if target_box else pin.title,
              'kind': target_box.kind if target_box else pin.kind,
              'subtype': target_box.subtype if target_box else '', 'status': pin.target_status}
    return {'id': pin.pk, 'kind': pin.kind, 'status': pin.status, 'target_status': pin.target_status,
            'title': pin.title or (pin.diagnosis_title if pin.kind == 'diagnosis' else ''),
            'subtitle': pin.subtitle, 'target': target,
            'author': author_info(pin.user, is_team=pin.is_team, anonymized=pin.anonymized),
            'author_stance': AUTHOR_STANCE_NAMES.get(pin.stance), 'target_title': target_title,
            'target_box_id': pin.pinned_box_id if pin.target_status == 'ok' else None,
            'comment': pin.comment if pin.comment_status == 'ok' else ''}


def box_item(box: Box, sp: BoxSpinka | None = None, *, my_rating: int | None = None, has_diagnosis: bool | None = None,
             detail: bool = False, pin: Pin | None = None, comment_count: int | None = None) -> dict:
    fl = flags()
    silence = election_silence()['active']
    sp = sp if sp is not None else getattr(box, 'spinka', None)
    removed = box.source_status == 'removed_at_source'
    withdrawn = box.source_status == 'withdrawn'
    title = box.title if (box.show_title and not withdrawn) else ('Materiał wycofany' if withdrawn else '')
    if removed and box.kind == 'post':
        title = 'Autor usunął wpis'
    if pin is None:
        pin = Pin.objects.filter(box=box).exclude(status='removed').select_related('user__spina3_profile', 'pinned_box').first()
    published_at = box.published_at or (pin.created_at if box.reader_link and pin else None)
    item = {
        'id': box.pk, 'kind': box.kind, 'subtype': box.subtype, 'title': title,
        'source': {'name': box.source_name, 'domain': box.source_domain},
        'author': _author(box) if not withdrawn else None,
        'published_at': published_at.isoformat() if published_at else None,
        'quote': box.quote if (box.show_quote and not removed and not withdrawn) else '',
        'thumbnail_url': box.thumbnail_url if (box.show_thumbnail and not removed and not withdrawn) else '',
        'source_status': box.source_status, 'status': box.status, 'reader_link': box.reader_link, 'topic': box.topic,
        'persons': [{'id': p.get('id'), 'name': p.get('name')} for p in (box.persons or [])],
        'portals': {'spin_diagnosis_url': (box.portals or {}).get('spin_diagnosis_url'),
                    'przeszlosc_url': (box.portals or {}).get('przeszlosc_url'),
                    'spina3_url': f"{getattr(settings, 'SPINA3_PUBLIC_URL', '')}/box/{box.pk}/"},
        'has_diagnosis': bool(has_diagnosis) if has_diagnosis is not None else box.links.filter(kind='diagnosis_of', is_current=True).exists(),
        'pinnable': box.pinnable_as_target and box.public_function and box.source_status == 'active',
        'has_pin': bool(pin and pin.status == 'published'),
        'pin': pin_summary(pin if pin and pin.status == 'published' else None),
        'spinka': spinka_payload(sp, silence=silence, levels_visible=fl.levels_visible),
        'my_rating': STANCE_NAMES.get(my_rating) if my_rating is not None else None,
        'comment_count': comment_count if comment_count is not None else Comment.objects.filter(box=box, status='visible').count(),
        'rel': 'ugc nofollow noopener' if box.reader_link else 'noopener',
    }
    if box.reader_link:
        item['label'] = 'dodane z linku czytelnika'
    if detail:
        show_text = (box.kind == 'post' and box.source_status == 'active') or (box.show_quote and box.kind in ('document', 'voting', 'legal_act', 'diagnosis'))
        item['text'] = box.text if show_text else ''
        item['url'] = box.url if box.source_status == 'active' else ''
        item['ai_label'] = 'Diagnoza AI, zatwierdzona przez zespół spina3' if box.kind == 'diagnosis' else ''
    return item


def target_card(pin: Pin) -> dict:
    if pin.kind == 'url':
        from urllib.parse import urlsplit
        domain = urlsplit(pin.url).hostname or ''
        status = pin.target_status
        card = {'kind': 'url', 'status': status, 'domain': domain if status == 'ok' else '', 'rel': 'ugc nofollow noopener'}
        if status == 'ok' and pin.pinned_box_id:
            card['box'] = box_item(pin.pinned_box)
        elif status == 'pending':
            card['label'] = 'oczekuje na weryfikację'
        else:
            card['label'] = 'materiał niedostępny'
        return card
    if pin.pinned_box_id and pin.target_status == 'ok':
        card = {'kind': 'box', 'status': 'ok', 'box': box_item(pin.pinned_box)}
        if pin.pinned_box.kind in ('person', 'entity'):
            card['label'] = 'dane rejestrowe'
        return card
    return {'kind': 'box', 'status': pin.target_status, 'label': 'materiał niedostępny',
            'replace_deadline': pin.replace_deadline.isoformat() if pin.replace_deadline else None}


def ratings_summary(sp: BoxSpinka | None) -> dict:
    dist = {**EMPTY_DIST, **((sp.distribution or {}) if sp else {})}
    return {'n': sp.n if sp else 0, 'agree': dist['agree'], 'disagree': dist['disagree']}


def pin_item(pin: Pin, *, viewer=None, my_rating: int | None = None, sp: BoxSpinka | None = None) -> dict:
    own = viewer is not None and getattr(viewer, 'pk', None) is not None and pin.user_id == viewer.pk
    sp = sp if sp is not None else getattr(pin.box, 'spinka', None)
    base = {
        'id': pin.pk, 'box_id': pin.box_id, 'kind': pin.kind, 'system': pin.kind == 'diagnosis',
        'ratings': ratings_summary(sp), 'my_rating': STANCE_NAMES.get(my_rating) if my_rating is not None else None,
        'ratable': pin.ratable and not own and pin.box.status == 'published' and pin.box.source_status == 'active',
        'created_at': pin.created_at.isoformat(), 'title': pin.title, 'subtitle': pin.subtitle,
    }
    if pin.kind == 'diagnosis':
        return {**base, 'author_stance': None, 'title': pin.diagnosis_title, 'url': pin.diagnosis_url, 'technique': pin.technique,
                'label': 'Diagnoza AI, zatwierdzona przez zespół spina3',
                'approved_at': pin.approved_at.isoformat() if pin.approved_at else None,
                'target': ({'kind': 'box', 'status': 'ok', 'box': box_item(pin.pinned_box)} if pin.pinned_box_id else None),
                'target_status': pin.target_status, 'author': author_info(pin.user), 'editable': False, 'comment': ''}
    return {
        **base, 'author_stance': AUTHOR_STANCE_NAMES.get(pin.stance),
        'comment': pin.comment if pin.comment_status == 'ok' else '',
        'comment_status': pin.comment_status if own else ('held' if pin.comment_status == 'held' else 'ok'),
        'target': target_card(pin), 'target_status': pin.target_status,
        'author': author_info(pin.user, is_team=pin.is_team, anonymized=pin.anonymized),
        'updated_at': pin.updated_at.isoformat() if pin.updated_at else None,
        'stance_changed_at': pin.stance_changed_at.isoformat() if pin.stance_changed_at else None,
        'replace_deadline': pin.replace_deadline.isoformat() if pin.replace_deadline else None,
        'editable': own and pin.status == 'published', 'status': pin.status if own else 'published',
    }


def comment_item(comment: Comment, *, viewer=None, voted: set | None = None, replies: list | None = None) -> dict:
    own = viewer is not None and getattr(viewer, 'pk', None) is not None and comment.user_id == viewer.pk
    visible = comment.status == 'visible'
    item = {
        'id': comment.pk, 'box_id': comment.box_id, 'parent_id': comment.parent_id,
        'text': comment.text if (visible or own) else '',
        'status': comment.status if own else ('visible' if visible else comment.status),
        'hidden_reason': comment.hidden_reason if own else '',
        'author': author_info(comment.user, is_team=comment.is_team, anonymized=comment.anonymized, is_author=comment.is_author),
        'helpful_count': comment.helpful_count, 'my_helpful': comment.pk in (voted or set()),
        'reply_count': comment.reply_count,
        'created_at': comment.created_at.isoformat(), 'edited_at': comment.edited_at.isoformat() if comment.edited_at else None,
        'editable': own and comment.status in ('visible', 'held'),
    }
    if replies is not None:
        item['replies'] = replies
    return item
