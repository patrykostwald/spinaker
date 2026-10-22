"""Model oceny v2 (oceny dwustanowe przypięcia autora): wzór, progi domknięte, histereza, min_n_extreme, oba tryby, przypadki graniczne (bez bazy)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from spina3 import scoring
from spina3.config import OPEN, ScoringConfig

CFG = ScoringConfig(open_window_hours=0, level_step_per_day=0)
NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def ratings(*stances, weight=1.0, start=NOW - timedelta(days=10)):
    return [scoring.RatingInput(stance=s, weight=weight, created_at=start + timedelta(minutes=i), trusted=True) for i, s in enumerate(stances)]


def level_of(*stances, prev=None, cfg=CFG):
    agg = scoring.aggregate(ratings(*stances), cfg, NOW)
    return scoring.level(agg.s, agg.weighted_n, prev, cfg, raw_n=agg.n)


def test_score_formula_m3():
    assert scoring.score(3, 3, 3) == pytest.approx(0.5)
    assert scoring.score(0, 0, 3) == 0.0
    assert scoring.score(-5, 5, 3) == pytest.approx(-0.625)


def test_three_unanimous_gives_p4():
    assert level_of(1, 1, 1).level == 'P4'          # S = 0,50


def test_five_unanimous_clamped_to_p4_with_min_n_extreme_and_p5_without():
    assert level_of(1, 1, 1, 1, 1).level == 'P4'    # S = 0,625, n_w = 5 < 8: przycięcie (PETLA 5.1)
    assert level_of(1, 1, 1, 1, 1).level_raw == 'P5'
    relaxed = ScoringConfig(min_n_extreme=3, open_window_hours=0, level_step_per_day=0)
    assert level_of(1, 1, 1, 1, 1, cfg=relaxed).level == 'P5'
    assert level_of(-1, -1, -1, -1, -1).level == 'P2'


def test_n_w_growing_from_7_to_8_at_constant_s_moves_p4_to_p5():
    # 7 ocen o S = 0,625 nie istnieje przy m = 3 (7/10 = 0,7), więc symulujemy wagami: n_w 7 -> 8 przy tym samym S
    first = scoring.level(0.625, 7, None, CFG)
    assert first.level == 'P4' and first.level_raw == 'P5'
    second = scoring.level(0.625, 8, first.level_raw, CFG)
    assert second.level == 'P5'


@pytest.mark.parametrize('s,expected', [(0.60, 'P5'), (0.599, 'P4'), (0.20, 'P4'), (0.199, 'P3'), (-0.199, 'P3'),
                                        (-0.20, 'P2'), (-0.599, 'P2'), (-0.60, 'P1')])
def test_closed_thresholds(s, expected):
    assert scoring.band(s) == expected


def test_hysteresis_both_directions():
    assert scoring.band_with_hysteresis(0.22, 'P3', CFG) == 'P3'   # granica 0,20 przekroczona o mniej niż 0,04
    assert scoring.band_with_hysteresis(0.24, 'P3', CFG) == 'P4'
    assert scoring.band_with_hysteresis(0.18, 'P4', CFG) == 'P4'
    assert scoring.band_with_hysteresis(0.159, 'P4', CFG) == 'P3'
    assert scoring.band_with_hysteresis(-0.22, 'P3', CFG) == 'P3'
    assert scoring.band_with_hysteresis(-0.25, 'P3', CFG) == 'P2'
    # skok o dwa pasma naraz (np. po usunięciach) też działa
    assert scoring.band_with_hysteresis(0.70, 'P2', CFG) == 'P5'


def test_withdrawn_and_zero_weight_ratings():
    rows = ratings(1, 1, 1) + [scoring.RatingInput(stance=1, weight=0.0, created_at=NOW, counts=True),    # zespół: waga 0
                               scoring.RatingInput(stance=-1, weight=1.0, created_at=NOW, counts=False)]  # ocena wycofana
    agg = scoring.aggregate(rows, CFG, NOW)
    assert agg.n == 4 and agg.weighted_n == 3 and agg.s == pytest.approx(0.5)
    assert agg.distribution == {'agree': 4, 'disagree': 0}


def test_invalid_stance_is_ignored():
    agg = scoring.aggregate([scoring.RatingInput(stance=0, weight=1.0, created_at=NOW)], CFG, NOW)
    assert agg.n == 0 and agg.distribution == {'agree': 0, 'disagree': 0}


def test_removal_below_minimum_gives_open():
    assert level_of(1, 1, 1).level == 'P4'
    after = level_of(1, 1, prev='P4')
    assert after.level == OPEN and after.reason == 'open'


def test_young_accounts_hold_level():
    rows = ratings(1, 1, 1, 1, weight=0.5)
    agg = scoring.aggregate(rows, CFG, NOW)
    result = scoring.level(agg.s, agg.weighted_n, None, CFG, raw_n=agg.n)
    assert agg.n == 4 and agg.weighted_n == 2.0
    assert result.level == OPEN and result.reason == 'hold_new_accounts'


def test_tie_is_p3():
    assert level_of(1, -1, 1, -1).level == 'P3'


def test_stance_change_recomputes():
    assert level_of(1, 1, 1, 1, -1).level == 'P4'      # 3/8 = 0,375
    assert level_of(1, 1, -1, -1, -1, prev='P4').level == 'P3'


def test_popularity_mode_levels_by_raw_n():
    cfg = ScoringConfig(mode='popularnosc', open_window_hours=0, level_step_per_day=0)
    assert level_of(cfg=cfg).level == OPEN
    assert level_of(1, cfg=cfg).level == 'P1'
    assert level_of(*[1] * 4, cfg=cfg).level == 'P2'
    assert level_of(*[-1] * 10, cfg=cfg).level == 'P3'
    assert level_of(*([1, -1] * 10), cfg=cfg).level == 'P4'
    assert level_of(*[1] * 40, cfg=cfg).level == 'P5'
    # kolor nadal z S: level_raw niesie pasmo S
    assert level_of(*[-1] * 40, cfg=cfg).level_raw == 'P1'


def test_open_window_six_hours():
    cfg = ScoringConfig(open_window_hours=6, level_step_per_day=0)
    first = NOW - timedelta(hours=2)
    res = scoring.level_transition(0.5, 3, None, cfg, raw_n=3, now=NOW, first_rating_at=first)
    assert res.level == OPEN and res.reason == 'open_window'
    res = scoring.level_transition(0.5, 3, None, cfg, raw_n=3, now=NOW, first_rating_at=NOW - timedelta(hours=7))
    assert res.level == 'P4'


def test_level_step_limited_to_one_per_day():
    cfg = ScoringConfig(open_window_hours=0, level_step_per_day=1)
    prev = scoring.LevelResult('P2', 'P2', 'ok')
    changed = NOW - timedelta(hours=2)
    res = scoring.level_transition(0.7, 10, prev, cfg, raw_n=10, now=NOW, first_rating_at=NOW - timedelta(days=3), level_changed_at=changed)
    assert res.level == 'P2' and res.pending and res.reason == 'step_limited'
    res = scoring.level_transition(0.7, 10, prev, cfg, raw_n=10, now=NOW, first_rating_at=NOW - timedelta(days=3), level_changed_at=NOW - timedelta(days=2))
    assert res.level == 'P3' and res.pending   # jeden stopień, reszta jutro
    res = scoring.level_transition(0.7, 10, scoring.LevelResult('P4', 'P5', 'ok'), cfg, raw_n=10, now=NOW,
                                   first_rating_at=NOW - timedelta(days=3), level_changed_at=NOW - timedelta(days=2))
    assert res.level == 'P5' and not res.pending


def test_frozen_keeps_level():
    prev = scoring.LevelResult('P4', 'P4', 'ok')
    res = scoring.level_transition(-0.9, 20, prev, CFG, raw_n=20, now=NOW, frozen=True)
    assert res.level == 'P4' and res.reason == 'frozen'


def test_views_thresholds():
    agg = scoring.aggregate(ratings(*([1] * 5 + [-1] * 5)), CFG, NOW)
    v = scoring.views(agg, CFG)
    assert v['eligible'] and v['dispute'] and not v['consensus']
    agg = scoring.aggregate(ratings(*([1] * 8 + [-1] * 2)), CFG, NOW)
    assert scoring.views(agg, CFG)['consensus']
    assert 'doubt' not in scoring.views(agg, CFG)
    agg = scoring.aggregate(ratings(*([1] * 9)), CFG, NOW)
    assert not scoring.views(agg, CFG)['eligible']          # n_w < 10
    hot = scoring.aggregate(ratings(*([1] * 10), start=NOW - timedelta(hours=3)), CFG, NOW)
    assert scoring.views(hot, CFG, daily_average=1.0)['hot']


def test_team_weight_zero_and_cluster_division():
    assert scoring.rating_weight(1.0, 1, is_team=True, cfg=CFG) == 0.0
    assert scoring.rating_weight(0.5, 5) == pytest.approx(0.1)
    assert scoring.rating_weight(0.0, 1) == 0.0


def test_sort_key_sections_and_open_last():
    k_p5 = scoring.sort_key('P5', NOW, 3, 1, NOW)
    k_p4 = scoring.sort_key('P4', NOW, 30, 2, NOW)
    k_open = scoring.sort_key(OPEN, None, 0, 3, NOW)
    assert k_p5 < k_p4 < k_open
    newer = scoring.sort_key('P4', NOW, 1, 4, NOW)
    older = scoring.sort_key('P4', NOW - timedelta(hours=1), 50, 5, NOW)
    assert newer < older                                   # last_rating_at przed n


def test_cursor_roundtrip():
    key = scoring.sort_key('P3', NOW, 7, 42, NOW)
    cursor = scoring.encode_cursor(17, key)
    version, decoded = scoring.decode_cursor(cursor)
    assert version == 17 and decoded == key
    assert scoring.decode_cursor('zle') is None or scoring.decode_cursor('zle')


def test_effective_sort_newest_until_rated_share():
    assert scoring.effective_sort(None, 0.05, CFG) == 'newest'
    assert scoring.effective_sort(None, 0.10, CFG) == 'level'
    assert scoring.effective_sort('level', 0.0, CFG) == 'level'
    assert scoring.effective_sort('level', 0.9, CFG, silence=True) == 'newest'


def test_aria_label_polish_decimal():
    assert scoring.aria_label('P4', 0.41, 12) == 'Spinka: poziom P4, ocena 0,41, 12 ocen'
    assert 'bez poziomu' in scoring.aria_label(OPEN, 0.0, 2)


def test_aria_label_open_reasons():
    assert 'brak przypięcia' in scoring.aria_label(OPEN, 0.0, 0, 'no_pin')
    assert 'dowód przypięcia niedostępny' in scoring.aria_label(OPEN, 0.0, 4, 'target_unavailable')
