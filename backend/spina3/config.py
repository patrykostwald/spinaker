"""Konfiguracja modelu oceny i zabezpieczeń spina3 v2 w jednym miejscu.

Źródła: PROMPT-BACKEND.md (poprawki po recenzji 11.10.2026), RECENZJA-FABLE.md, PETLA-PRODUKT.md (sekcje 2, 5, 7) oraz nowy model
produktu (właściciel 11.10, v2): jedno przypięcie autora na box, OCENY dwustanowe innych użytkowników, komentarze pod parą.
Wartości domyślne są poniżej; nadpisanie przez `settings.SPINA3` (słownik) albo zmienne środowiskowe w settings.py.
Frontend liczy optymistycznie tą samą czystą funkcją (`spina3.scoring`), dlatego progi są publiczne (GET /api/spina3/config).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace

from django.conf import settings

FORMULA_VERSION = '2.0'  # 2.0: S z ocen dwustanowych przypięcia autora (zamiast przypięć wielu użytkowników).

LEVELS = ('P1', 'P2', 'P3', 'P4', 'P5')
OPEN = 'open'  # stan bez poziomu: "Otwarta" (aria: "bez poziomu")

COLORS = {
    'P5': '#62E8A3', 'P4': '#8BBF48', 'P3': '#D49A33', 'P2': '#E07A3C', 'P1': '#E45A5A', OPEN: '#8E959E',
}
LEVEL_LABELS = {'P5': 'P5', 'P4': 'P4', 'P3': 'P3', 'P2': 'P2', 'P1': 'P1', OPEN: 'Otwarta'}

# Oceny przypięcia (Rating): dwa stany.
STANCES = {'agree': 1, 'disagree': -1}
STANCE_NAMES = {1: 'agree', -1: 'disagree'}
STANCE_LABELS = {1: 'Zgadzam się', -1: 'Nie zgadzam się'}
# Stanowisko AUTORA wobec treści boxa (opcjonalne pole przypięcia, nie liczy się do S).
AUTHOR_STANCES = {'agree': 1, 'doubt': 0, 'disagree': -1}
AUTHOR_STANCE_NAMES = {1: 'agree', 0: 'doubt', -1: 'disagree'}

# Kolory nicków: identyfikatory z listy; frontend mapuje na własne tokeny. "spin" = niebieski akcent spin.clinic,
# zarezerwowany dla konta Dr. Spina (403 przy próbie wyboru przez użytkownika).
NICK_COLORS = {
    'lila': '#AB91F3', 'wrzos': '#D991F3', 'fuksja': '#F391E1', 'roz': '#F391B5',
    'brzoskwinia': '#F3BF91', 'piasek': '#F3E291', 'cytryna': '#DFF391', 'pistacja': '#BFF391',
}  # 8 barw frontu; "spin" pozostaje zarezerwowany.
NICK_COLOR_RESERVED = {'spin': '#4F8CFF'}
NICK_COLOR_DEFAULT = 'piasek'


@dataclass(frozen=True)
class ScoringConfig:
    # Wzór: S = suma ważonych ocen / (n_w + m); ocena +1 / -1
    m: float = 3.0
    # Progi domknięte: P5 S >= 0,60; P4 0,20 <= S < 0,60; P3 -0,20 < S < 0,20; P2 -0,60 < S <= -0,20; P1 S <= -0,60
    bounds: tuple = (-0.60, -0.20, 0.20, 0.60)
    hysteresis: float = 0.04
    min_n: float = 3.0               # próg na n ważonym OCEN (PETLA 5.2)
    min_n_extreme: float = 8.0       # P5 i P1 dopiero od n_w >= 8; poniżej przycięcie do P4 / P2 (PETLA 5.1)
    mode: str = 'zgodnosc'           # 'zgodnosc' | 'popularnosc'
    popularity_bounds: tuple = (1, 4, 10, 20, 40)  # P1 1-3, P2 4-9, P3 10-19, P4 20-39, P5 >= 40 (n surowe ocen)
    open_window_hours: float = 6.0   # poziom najwcześniej 6 h po pierwszej ocenie
    level_step_per_day: int = 1      # najwyżej jeden stopień poziomu na 24 h; 0 = zamrożenie (alarm 2)
    # Wagi wiarygodności
    weight_young: float = 0.5
    weight_tier: dict = field(default_factory=lambda: {'T0': 0.0, 'T1': 0.5, 'T2': 1.0, 'T3': 1.0})
    weight_team: float = 0.0         # oceny zespołu spina3: kontekst, nie głos
    young_account_days: int = 14
    young_account_min_activity: int = 5   # T2 od 5 opublikowanych aktywności (przypięcia + oceny + komentarze widoczne)
    tier2_min_distinct_subjects: int = 3
    cluster_jaccard: float = 0.8
    cluster_min_common: int = 5
    cluster_window_hours: float = 1.0
    # Ranking i ściana
    batch_size: int = 48
    max_batches: int = 20
    default_period_days: int = 90
    min_rated_share: float = 0.10
    snapshot_interval_seconds: int = 600
    snapshot_keep: int = 12
    snapshot_retention_days: int = 365
    top_cap_per_author: int = 2
    top_cap_group_share: float = 0.40
    first_screen: int = 24
    today_hour: int = 7
    today_size: int = 7
    # Widoki oparte na ocenach (od n_w >= 10): Spór, Zgoda, Najgoręcej, Zmiana zdania
    views_min_n: float = 10.0
    dispute_share: float = 0.35
    consensus_share: float = 0.75
    hot_min_24h: int = 5
    hot_multiplier: float = 2.0
    change_min_edits: int = 3
    change_min_share: float = 0.10
    change_min_age_days: int = 7
    facet_min_share: float = 0.05
    # Limity: boxy z przypięciem (na dobę), oceny (na dobę), komentarze (na dobę)
    daily_pins: dict = field(default_factory=lambda: {'T0': 0, 'T1': 3, 'T2': 10, 'T3': 10, 'team': 0})
    daily_ratings: dict = field(default_factory=lambda: {'T0': 0, 'T1': 30, 'T2': 200, 'T3': 200, 'team': 10 ** 6})  # zespół: waga 0
    daily_comments: dict = field(default_factory=lambda: {'T0': 0, 'T1': 10, 'T2': 60, 'T3': 60, 'team': 10 ** 6})
    same_target_30d: dict = field(default_factory=lambda: {'T1': 3, 'T2': 10, 'T3': 10})
    stance_edit_cooldown_hours: float = 24.0     # stanowisko autora w przypięciu
    rating_change_cooldown_hours: float = 1.0    # zmiana oceny (zgadzam się <-> nie zgadzam się)
    url_pending_per_account: int = 1
    url_per_domain_per_day: int = 5
    reports_per_day: int = 10
    burst_window_seconds: int = 60
    burst_max_pins: int = 3
    burst_max_ratings: int = 10
    burst_max_comments: int = 3
    comment_duplicate_hours: float = 24.0
    comment_text_max: int = 600          # komentarz pod parą
    comment_replies_limit: int = 50      # odpowiedzi dołączane do komentarza głównego
    replace_days: int = 7
    comment_max: int = 280               # komentarz autora w przypięciu
    event_retention_days: int = 90      # nieużywane: retencję dziennika ustawia settings.SPINA3_EVENT_RETENTION_DAYS
    url_recheck_days: int = 30


@dataclass(frozen=True)
class Flags:
    enabled: bool = True
    pins_enabled: bool = True            # tworzenie boxów z przypięciem przez użytkowników
    ratings_enabled: bool = True
    comments_enabled: bool = True
    levels_visible: bool = True
    views_enabled: bool = True
    url_pins_enabled: bool = True
    allow_image_pins: bool = False
    adopt_authorless_boxes: bool = True  # box importera bez przypięcia może "przejąć" pierwszy użytkownik jednym przypięciem
    chains_enabled: bool = False
    public_profiles: bool = False
    # Cisza wyborcza (właściciel 11.10): daty ISO (np. '2027-10-15T00:00:00+02:00'); puste = brak ciszy.
    # W czasie ciszy wstrzymane są NASZE publikacje (nowe boxy diagnoz, przypięcia systemowe, zespołu, RSS); kolejka wstrzymanych
    # publikuje się po zakończeniu. Publikacje użytkowników wstrzymują osobne flagi (domyślnie false, pytanie do prawnika).
    election_silence_start: str = ''
    election_silence_end: str = ''
    election_silence_pause_user_pins: bool = False   # boxy i przypięcia użytkowników (423)
    election_silence_pause_ratings: bool = False     # oceny (423)
    election_silence_pause_comments: bool = False    # komentarze (423)
    url_fetch_enabled: bool = False
    x_source_check_enabled: bool = True   # spina3_sync: oEmbed X, czy wpis istnieje u źródła (do 60 wpisów na przebieg)
    import_press: bool = False
    auth_mode: str = 'session'


def _overrides() -> dict:
    raw = getattr(settings, 'SPINA3', None) or {}
    return dict(raw)


def config() -> ScoringConfig:
    data = _overrides().get('scoring') or {}
    base = ScoringConfig()
    known = {k: v for k, v in data.items() if k in asdict(base)}
    return replace(base, **known)


def flags() -> Flags:
    data = _overrides().get('flags') or {}
    base = Flags()
    known = {k: v for k, v in data.items() if k in asdict(base)}
    return replace(base, **known)


def _parse(value: str):
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone as tz
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if tz.is_naive(parsed):
        parsed = tz.make_aware(parsed)
    return parsed


def election_silence(now=None) -> dict:
    """Stan ciszy wyborczej: aktywna, gdy start <= now < end (obie daty ustawione)."""
    from django.utils import timezone as tz
    fl = flags()
    start, end = _parse(fl.election_silence_start), _parse(fl.election_silence_end)
    now = now or tz.now()
    active = bool(start and end and start <= now < end)
    return {'active': active, 'starts_at': start.isoformat() if start else None,
            'ends_at': end.isoformat() if end else None,
            'pause_user_pins': bool(fl.election_silence_pause_user_pins),
            'pause_ratings': bool(fl.election_silence_pause_ratings),
            'pause_comments': bool(fl.election_silence_pause_comments),
            'user_pins_paused': active and bool(fl.election_silence_pause_user_pins),
            'ratings_paused': active and bool(fl.election_silence_pause_ratings),
            'comments_paused': active and bool(fl.election_silence_pause_comments)}


def public_silence() -> dict:
    state = election_silence()
    return {'active': state['active'], 'start': state['starts_at'], 'end': state['ends_at'],
            'pause': {key: state['pause_' + key] for key in ('user_pins', 'ratings', 'comments')}}


def public_config() -> dict:
    cfg, fl = config(), flags()
    return {
        'election_silence': public_silence(),
        'formula_version': FORMULA_VERSION,
        'm': cfg.m, 'bounds': list(cfg.bounds), 'hysteresis': cfg.hysteresis,
        'min_n': cfg.min_n, 'min_n_extreme': cfg.min_n_extreme, 'mode': cfg.mode,
        'popularity_bounds': list(cfg.popularity_bounds),
        'open_window_hours': cfg.open_window_hours, 'level_step_per_day': cfg.level_step_per_day,
        'colors': dict(COLORS), 'labels': dict(LEVEL_LABELS), 'stances': dict(STANCES), 'author_stances': dict(AUTHOR_STANCES),
        'nick_colors': dict(NICK_COLORS), 'nick_colors_reserved': dict(NICK_COLOR_RESERVED), 'nick_color_default': NICK_COLOR_DEFAULT,
        'batch_size': cfg.batch_size, 'max_batches': cfg.max_batches,
        'default_period_days': cfg.default_period_days, 'min_rated_share': cfg.min_rated_share,
        'views_min_n': cfg.views_min_n, 'comment_max': cfg.comment_max, 'comment_text_max': cfg.comment_text_max,
        'replace_days': cfg.replace_days,
        'daily_pins': dict(cfg.daily_pins), 'daily_ratings': dict(cfg.daily_ratings), 'daily_comments': dict(cfg.daily_comments),
        'stance_edit_cooldown_hours': cfg.stance_edit_cooldown_hours, 'rating_change_cooldown_hours': cfg.rating_change_cooldown_hours,
        'flags': {key: value for key, value in asdict(fl).items() if not key.startswith('election_silence_')},
        'legend': 'Kolor spinki to oceny czytelników wobec przypięcia autora, a nie ocena prawdziwości. Liczymy oceny, nie ludzi.',
    }
