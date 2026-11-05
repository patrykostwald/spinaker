"""Czyste funkcje oceny spinki v2: S z OCEN dwustanowych, poziomy, histereza, wagi, klastry, widoki, klucz sortowania.

Bez Django ORM: ten sam algorytm można przepisać 1:1 na frontend (liczenie optymistyczne), a backend potwierdza
w odpowiedzi PUT /pin/{id}/rating/. Konfiguracja: `spina3.config.ScoringConfig`.

Poziomy (tryb "zgodność"): P5 S >= 0,60; P4 0,20 <= S < 0,60; P3 -0,20 < S < 0,20; P2 -0,60 < S <= -0,20; P1 S <= -0,60.
Histereza 0,04 działa w przestrzeni S na poziomie SUROWYM (level_raw); przycięcie skrajnych poziomów (min_n_extreme)
i minimum n działają w przestrzeni n ważonego na poziomie WYŚWIETLANYM. Dzięki temu n_w rosnące z 7 do 8 przy stałym
S = 0,625 daje przejście P4 -> P5 (PETLA 5.1), a histereza nie blokuje, bo granica S nie była przekraczana.
Dwa stany oceny (+1 / -1): P3 to oceny bliskie remisu, nie "wątpliwości".
"""
from __future__ import annotations

import base64
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, Sequence

from .config import COLORS, LEVELS, OPEN, STANCE_NAMES, ScoringConfig

LEVEL_INDEX = {name: index for index, name in enumerate(LEVELS)}  # P1 = 0 ... P5 = 4


# --- wzór i pasma ------------------------------------------------------------------------------------------

def score(weighted_sum: float, weighted_n: float, m: float) -> float:
    """S = suma ważonych ocen / (n_w + m); przy n_w = 0 daje 0."""
    if weighted_n <= 0 and weighted_sum == 0:
        return 0.0
    return weighted_sum / (weighted_n + m)


def band(s: float, bounds: Sequence[float] = (-0.60, -0.20, 0.20, 0.60)) -> str:
    """Pasmo poziomu dla S według domkniętych progów (bez minimum n i bez histerezy)."""
    b1, b2, b3, b4 = bounds
    if s >= b4:
        return 'P5'
    if s >= b3:
        return 'P4'
    if s > b2:
        return 'P3'
    if s > b1:
        return 'P2'
    return 'P1'


def band_with_hysteresis(s: float, previous_raw: str | None, cfg: ScoringConfig) -> str:
    """Zmiana pasma dopiero, gdy S przekroczy granicę o `hysteresis` (w obie strony). Czysta funkcja."""
    if previous_raw not in LEVEL_INDEX:
        return band(s, cfg.bounds)
    h = cfg.hysteresis
    up, down = band(round(s - h, 9), cfg.bounds), band(round(s + h, 9), cfg.bounds)  # bez błędu zmiennoprzecinkowego na granicy
    if LEVEL_INDEX[up] > LEVEL_INDEX[previous_raw]:
        return up
    if LEVEL_INDEX[down] < LEVEL_INDEX[previous_raw]:
        return down
    return previous_raw


def popularity_band(n: float, bounds: Sequence[int] = (1, 4, 10, 20, 40)) -> str:
    """Tryb "popularność": poziom wg n (surowego); n = 0 -> Otwarta."""
    if n < bounds[0]:
        return OPEN
    if n >= bounds[4]:
        return 'P5'
    if n >= bounds[3]:
        return 'P4'
    if n >= bounds[2]:
        return 'P3'
    if n >= bounds[1]:
        return 'P2'
    return 'P1'


def clamp_extreme(level: str, weighted_n: float, cfg: ScoringConfig) -> str:
    """P5 i P1 dopiero od n_w >= min_n_extreme; poniżej przycięcie do P4 / P2."""
    if weighted_n >= cfg.min_n_extreme:
        return level
    if level == 'P5':
        return 'P4'
    if level == 'P1':
        return 'P2'
    return level


@dataclass(frozen=True)
class LevelResult:
    level: str            # poziom wyświetlany: P1..P5 albo 'open'
    level_raw: str | None  # stan histerezy w przestrzeni S (bez przycięcia); None gdy brak danych
    reason: str           # 'ok' | 'open' | 'hold_new_accounts' | 'open_window' | 'step_limited' | 'frozen' | 'silence' | 'no_pin' | 'target_unavailable'
    pending: bool = False  # poziom przeliczy się jutro (limit stopnia na dobę)
    changed: bool = False


def level(s: float, weighted_n: float, previous_raw: str | None, cfg: ScoringConfig, *,
          raw_n: int | None = None) -> LevelResult:
    """level(S, n_w, poprzedni_poziom): czysta funkcja bez czasu (okno otwarte i limit stopnia: `level_transition`)."""
    raw = band_with_hysteresis(s, previous_raw, cfg)
    if cfg.mode == 'popularnosc':
        shown = popularity_band(raw_n if raw_n is not None else weighted_n, cfg.popularity_bounds)
        return LevelResult(shown, raw, 'ok' if shown != OPEN else 'open')
    if weighted_n < cfg.min_n:
        if raw_n is not None and raw_n >= cfg.min_n:
            return LevelResult(OPEN, raw, 'hold_new_accounts')
        return LevelResult(OPEN, raw, 'open')
    return LevelResult(clamp_extreme(raw, weighted_n, cfg), raw, 'ok')


def level_transition(s: float, weighted_n: float, previous: LevelResult | None, cfg: ScoringConfig, *,
                     raw_n: int | None = None, now: datetime | None = None, first_rating_at: datetime | None = None,
                     level_changed_at: datetime | None = None, frozen: bool = False) -> LevelResult:
    """Poziom z uwzględnieniem czasu: okno otwarte od pierwszej oceny i najwyżej jeden stopień na 24 h.
    Nadwyżka zmiany zostaje jako `pending` (kafelek: "poziom przeliczy się jutro")."""
    prev_raw = previous.level_raw if previous else None
    prev_level = previous.level if previous else OPEN
    if frozen:
        return LevelResult(prev_level, prev_raw, 'frozen')
    target = level(s, weighted_n, prev_raw, cfg, raw_n=raw_n)
    if target.level != OPEN and cfg.open_window_hours > 0 and now is not None and first_rating_at is not None:
        if now < first_rating_at + timedelta(hours=cfg.open_window_hours):
            return LevelResult(OPEN, target.level_raw, 'open_window')
    if target.level == prev_level:
        return LevelResult(prev_level, target.level_raw, target.reason)
    if prev_level == OPEN or target.level == OPEN or now is None or level_changed_at is None:
        return LevelResult(target.level, target.level_raw, target.reason, changed=True)
    if cfg.level_step_per_day <= 0:
        return LevelResult(prev_level, target.level_raw, 'step_limited', pending=True)
    if now < level_changed_at + timedelta(days=1):
        return LevelResult(prev_level, target.level_raw, 'step_limited', pending=True)
    direction = 1 if LEVEL_INDEX[target.level] > LEVEL_INDEX[prev_level] else -1
    step = LEVELS[LEVEL_INDEX[prev_level] + direction * min(cfg.level_step_per_day, abs(LEVEL_INDEX[target.level] - LEVEL_INDEX[prev_level]))]
    pending = step != target.level
    return LevelResult(step, target.level_raw, 'step_limited' if pending else 'ok', pending=pending, changed=True)


def color(level_name: str) -> str:
    return COLORS.get(level_name, COLORS[OPEN])


# --- agregacja ocen ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class RatingInput:
    stance: int                 # +1 albo -1
    weight: float = 1.0         # waga konta / rozmiar klastra; 0 = nie głosuje (zespół, T0, sankcja)
    created_at: datetime | None = None
    trusted: bool = True        # konto >= 7 dni, pełna waga: tylko takie oceny ustawiają last_rating_at
    stance_changed_at: datetime | None = None
    counts: bool = True         # False: ocena wycofana albo przypięcie bez dostępnego dowodu


PinInput = RatingInput  # zgodność nazw z wersją 1.0 (symulacje)


@dataclass
class Aggregate:
    n: int = 0                  # n surowe (na kafelku)
    weighted_n: float = 0.0     # n_w (do progów i wzoru)
    weighted_sum: float = 0.0
    s: float = 0.0
    distribution: dict = field(default_factory=lambda: {'agree': 0, 'disagree': 0})
    first_rating_at: datetime | None = None
    last_rating_at: datetime | None = None
    ratings_24h: int = 0
    trusted_ratings_24h: int = 0
    stance_edits_7d: int = 0


def aggregate(ratings: Iterable[RatingInput], cfg: ScoringConfig, now: datetime | None = None) -> Aggregate:
    """Zlicza wyłącznie oceny `counts=True` o stanowisku +1 / -1."""
    out = Aggregate()
    last_any = None
    for row in ratings:
        if not row.counts or row.stance not in STANCE_NAMES:
            continue
        out.n += 1
        out.weighted_n += row.weight
        out.weighted_sum += row.weight * row.stance
        out.distribution[STANCE_NAMES[row.stance]] += 1
        if row.created_at:
            if out.first_rating_at is None or row.created_at < out.first_rating_at:
                out.first_rating_at = row.created_at
            if last_any is None or row.created_at > last_any:
                last_any = row.created_at
            if row.trusted and row.weight >= 1.0 and (out.last_rating_at is None or row.created_at > out.last_rating_at):
                out.last_rating_at = row.created_at
            if now is not None and row.created_at >= now - timedelta(hours=24):
                out.ratings_24h += 1
                if row.trusted:
                    out.trusted_ratings_24h += 1
        if now is not None and row.stance_changed_at and row.created_at and row.stance_changed_at >= now - timedelta(days=7) \
                and row.stance_changed_at >= row.created_at + timedelta(days=cfg.change_min_age_days):
            out.stance_edits_7d += 1
    if out.last_rating_at is None:
        out.last_rating_at = last_any
    out.s = score(out.weighted_sum, out.weighted_n, cfg.m)
    return out


def views(agg: Aggregate, cfg: ScoringConfig, daily_average: float = 0.0) -> dict:
    """Widoki oparte na ocenach (od n_w >= views_min_n): Spór, Zgoda, Najgoręcej, Zmiana zdania."""
    out = {'dispute': False, 'consensus': False, 'hot': False, 'change': False, 'eligible': False}
    if agg.weighted_n < cfg.views_min_n or agg.n == 0:
        return out
    n = agg.n
    a, x = agg.distribution['agree'], agg.distribution['disagree']
    out['eligible'] = True
    out['dispute'] = min(a, x) / n >= cfg.dispute_share
    out['consensus'] = a / n >= cfg.consensus_share or x / n >= cfg.consensus_share
    out['hot'] = agg.trusted_ratings_24h >= cfg.hot_min_24h and agg.trusted_ratings_24h >= cfg.hot_multiplier * max(daily_average, 0.0)
    out['change'] = agg.stance_edits_7d >= cfg.change_min_edits and agg.stance_edits_7d >= cfg.change_min_share * n
    return out


def aria_label(level_name: str, s: float, n: int, reason: str = 'ok') -> str:
    if level_name == OPEN:
        tail = {'hold_new_accounts': 'poziom wstrzymany: oceny z nowych kont',
                'open_window': 'poziom pojawi się po oknie otwarcia',
                'no_pin': 'brak przypięcia do oceny',
                'target_unavailable': 'dowód przypięcia niedostępny'}.get(reason, 'bez poziomu')
        return f'Spinka: Otwarta ({tail}), {n} ocen'
    return f'Spinka: poziom {level_name}, ocena {s:.2f}'.replace('.', ',') + f', {n} ocen'


# --- wagi i klastry ---------------------------------------------------------------------------------------

def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class RatingRecord:
    user: str
    item: int                   # id ocenianego przypięcia
    stance: int
    created_at: datetime


PinRecord = RatingRecord  # zgodność nazw z wersją 1.0


def cluster_groups(records: Iterable[RatingRecord], cfg: ScoringConfig) -> list[set[str]]:
    """Klaster kont zależnych: Jaccard ocenianych przypięć >= 0,8 przy >= 5 wspólnych z tym samym stanowiskiem
    w oknie 1 h. Zwraca listę grup (>= 2 konta). Union-find po parach."""
    by_user: dict[str, dict[int, tuple[int, datetime]]] = {}
    for row in records:
        by_user.setdefault(row.user, {})[row.item] = (row.stance, row.created_at)
    users = sorted(by_user)
    parent = {u: u for u in users}

    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    window = timedelta(hours=cfg.cluster_window_hours)
    for i, u in enumerate(users):
        items_u = set(by_user[u])
        if len(items_u) < cfg.cluster_min_common:
            continue
        for v in users[i + 1:]:
            items_v = set(by_user[v])
            common = items_u & items_v
            if len(common) < cfg.cluster_min_common or jaccard(items_u, items_v) < cfg.cluster_jaccard:
                continue
            same = 0
            for item in common:
                su, tu = by_user[u][item]
                sv, tv = by_user[v][item]
                if su == sv and abs(tu - tv) <= window:
                    same += 1
            if same >= cfg.cluster_min_common:
                parent[find(u)] = find(v)
    groups: dict[str, set] = {}
    for u in users:
        groups.setdefault(find(u), set()).add(u)
    return [members for members in groups.values() if len(members) >= 2]


def detect_clusters(records: Iterable[RatingRecord], cfg: ScoringConfig) -> dict[str, int]:
    """{user: rozmiar_klastra} dla kont w klastrach (>= 2)."""
    return {u: len(members) for members in cluster_groups(records, cfg) for u in members}


def rating_weight(account_weight: float, cluster_size: int = 1, is_team: bool = False,
                  cfg: ScoringConfig | None = None) -> float:
    """waga oceny = waga konta / rozmiar klastra; zespół i T0 = 0."""
    cfg = cfg or ScoringConfig()
    if is_team:
        return cfg.weight_team
    if cluster_size < 1:
        cluster_size = 1
    return max(0.0, account_weight) / cluster_size


def pin_weight(account_weight: float, target_weight: float = 1.0, cluster_size: int = 1, is_team: bool = False,
               cfg: ScoringConfig | None = None) -> float:
    """Zgodność z 1.0 (symulacje): waga x waga celu / klaster."""
    return rating_weight(account_weight, cluster_size, is_team, cfg) * max(0.0, target_weight)


# --- kolejność ściany i kursor --------------------------------------------------------------------------------

def sort_key(level_name: str, last_rating_at: datetime | None, n: int, box_id: int, published_at: datetime | None):
    """Sekcje poziomów P5..P1, w sekcji last_rating_at malejąco, potem n, potem id. "Otwarta" na końcu, najnowsze pierwsze.
    S nie sortuje (tylko kolor): stabilny kursor (RF sekcja 2 pkt 4)."""
    rank = -(LEVEL_INDEX[level_name] + 1) if level_name in LEVEL_INDEX else 0
    if level_name == OPEN:
        ts = published_at.timestamp() if published_at else 0.0
        return (rank, -ts, 0, -box_id)
    ts = last_rating_at.timestamp() if last_rating_at else 0.0
    return (rank, -ts, -n, -box_id)


def newest_key(published_at: datetime | None, box_id: int):
    return (-(published_at.timestamp() if published_at else 0.0), -box_id)


def encode_cursor(version: int, key: tuple) -> str:
    payload = f'{version}|' + '|'.join(repr(float(x)) if isinstance(x, float) else str(int(x)) for x in key)
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')


def decode_cursor(cursor: str) -> tuple[int, tuple] | None:
    try:
        padded = cursor + '=' * (-len(cursor) % 4)
        payload = base64.urlsafe_b64decode(padded.encode()).decode()
        version, *parts = payload.split('|')
        key = tuple(float(p) if '.' in p or 'e' in p else int(p) for p in parts)
        return int(version), key
    except (ValueError, UnicodeDecodeError, TypeError):
        return None


def kendall_tau(ranking_a: Sequence[int], ranking_b: Sequence[int]) -> float:
    """Tau Kendalla (tau-a) dla pozycji elementów `ranking_a` w obu rankingach; elementy spoza B na końcu B."""
    pos_b = {item: i for i, item in enumerate(ranking_b)}
    items = list(ranking_a)
    missing = len(ranking_b)
    ranks_b = [pos_b.get(item, missing + i) for i, item in enumerate(items)]
    concordant = discordant = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            diff = ranks_b[i] - ranks_b[j]
            if diff < 0:
                concordant += 1
            elif diff > 0:
                discordant += 1
    pairs = len(items) * (len(items) - 1) / 2
    return 1.0 if pairs == 0 else (concordant - discordant) / pairs


def effective_sort(requested: str | None, rated_share: float, cfg: ScoringConfig, silence: bool = False) -> str:
    """Domyślnie "najnowsze", dopóki mniej niż min_rated_share boxów ma poziom; cisza wyborcza wymusza "najnowsze"."""
    if silence:
        return 'newest'
    if requested in ('level', 'newest', 'today'):
        return requested
    return 'level' if rated_share >= cfg.min_rated_share else 'newest'


def is_finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)
