"""Symulacje modelu (bez bazy): sybil 1000 boxów / 200 użytkowników / 5 kont, Monte Carlo 10 000 przypięć, klastry."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from spina3 import scoring
from spina3.config import LEVELS, ScoringConfig

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def simulate_wall(seed=7, boxes=1000, users=200, pins_per_user=12, cfg=None):
    cfg = cfg or ScoringConfig(open_window_hours=0, level_step_per_day=0)
    rng = random.Random(seed)
    bias = {b: rng.uniform(-0.9, 0.9) for b in range(boxes)}
    records: dict[int, list[scoring.RatingInput]] = {b: [] for b in range(boxes)}
    for u in range(users):
        for b in rng.sample(range(boxes), pins_per_user):
            p = bias[b]
            r = rng.random()
            stance = 1 if r < (0.5 + p / 2) else -1   # v2: dwa stany
            records[b].append(scoring.RatingInput(stance=stance, weight=1.0, trusted=True,
                                               created_at=NOW - timedelta(days=rng.uniform(0, 60))))
    return records, cfg, rng


def rank(records, cfg):
    rows = []
    for b, inputs in records.items():
        agg = scoring.aggregate(inputs, cfg, NOW)
        lv = scoring.level(agg.s, agg.weighted_n, None, cfg, raw_n=agg.n)
        rows.append((scoring.sort_key(lv.level, agg.last_rating_at, agg.n, b, NOW - timedelta(days=b % 30)), b))
    rows.sort()
    return [b for _, b in rows]


def test_sybil_attack_keeps_top50_kendall_tau_above_09():
    records, cfg, rng = simulate_wall()
    before = rank(records, cfg)
    top50 = before[:50]
    # 5 kont sybil: młode (waga 0,5), w klastrze (Jaccard 1 na 20 wspólnych boxach, to samo stanowisko, w oknie 1 h)
    targets = rng.sample(range(50, 1000), 20)  # próbują wepchnąć 20 boxów spoza szczytu
    cluster_size = 5
    for b in targets:
        for s in range(5):
            weight = scoring.pin_weight(0.5, 1.0, cluster_size)
            records[b].append(scoring.RatingInput(stance=1, weight=weight, trusted=False, created_at=NOW - timedelta(minutes=s)))
    after = rank(records, cfg)
    tau = scoring.kendall_tau(top50, after)
    assert tau >= 0.9, tau
    pushed = sum(1 for b in targets if after.index(b) < 50)
    assert pushed <= 2, pushed      # kryterium główne to tau; pojedynczy box na granicy pasma może zmienić sekcję


def test_sybil_without_defenses_would_break_ranking():
    """Kontrola: te same konta z pełną wagą i bez klastra przestawiają szczyt (dowód, że zabezpieczenia działają)."""
    records, cfg, rng = simulate_wall()
    before = rank(records, cfg)
    top50 = before[:50]
    targets = rng.sample(range(50, 1000), 20)
    for b in targets:
        for s in range(5):
            records[b].append(scoring.RatingInput(stance=1, weight=1.0, trusted=True, created_at=NOW - timedelta(minutes=s)))
    after = rank(records, cfg)
    pushed = sum(1 for b in targets if after.index(b) < 50)
    assert pushed >= 5


def test_monte_carlo_level_changes_below_3_per_100_pins_when_n_gt_10():
    cfg = ScoringConfig(open_window_hours=0, level_step_per_day=0)
    rng = random.Random(11)
    boxes = 100
    bias = [rng.uniform(-0.9, 0.9) for _ in range(boxes)]
    state = [[] for _ in range(boxes)]
    prev = [None] * boxes
    level_now = ['open'] * boxes
    changes = 0
    pins_counted = 0
    for i in range(10_000):
        b = rng.randrange(boxes)
        p = bias[b]
        r = rng.random()
        stance = 1 if r < (0.5 + p / 2) else -1   # v2: dwa stany
        state[b].append(scoring.RatingInput(stance=stance, weight=1.0, trusted=True, created_at=NOW - timedelta(seconds=10_000 - i)))
        agg = scoring.aggregate(state[b], cfg, NOW)
        res = scoring.level(agg.s, agg.weighted_n, prev[b], cfg, raw_n=agg.n)
        prev[b] = res.level_raw
        if agg.n > 10:
            pins_counted += 1
            if res.level != level_now[b]:
                changes += 1
        level_now[b] = res.level
    per_100 = changes / pins_counted * 100
    assert per_100 < 3.0, per_100


def test_monte_carlo_without_hysteresis_changes_more_often():
    cfg = ScoringConfig(hysteresis=0.0, open_window_hours=0, level_step_per_day=0)
    strict = ScoringConfig(open_window_hours=0, level_step_per_day=0)

    def run(c):
        rng = random.Random(5)
        state, prev, level_now = [[] for _ in range(60)], [None] * 60, ['open'] * 60
        changes = counted = 0
        bias = [rng.uniform(-0.5, 0.5) for _ in range(60)]
        for i in range(6000):
            b = rng.randrange(60)
            r = rng.random()
            stance = 1 if r < (0.5 + bias[b] / 2) else -1
            state[b].append(scoring.RatingInput(stance=stance, weight=1.0, trusted=True, created_at=NOW))
            agg = scoring.aggregate(state[b], c, NOW)
            res = scoring.level(agg.s, agg.weighted_n, prev[b], c, raw_n=agg.n)
            prev[b] = res.level_raw
            if agg.n > 10:
                counted += 1
                changes += res.level != level_now[b]
            level_now[b] = res.level
        return changes / counted * 100
    assert run(cfg) >= run(strict)


def test_cluster_detection_jaccard():
    cfg = ScoringConfig()
    records = []
    base = NOW - timedelta(hours=5)
    for u in ('a', 'b', 'c'):
        for box in range(6):
            records.append(scoring.PinRecord(u, box, 1, base + timedelta(minutes=10 * (ord(u) - 96))))
    for box in range(6):   # 'd' przypina te same boxy, ale inne stanowisko i 3 h później: nie jest w klastrze
        records.append(scoring.PinRecord('d', box, -1, base + timedelta(hours=3)))
    records.append(scoring.PinRecord('e', 1, 1, base))   # za mało wspólnych
    clusters = scoring.detect_clusters(records, cfg)
    assert clusters == {'a': 3, 'b': 3, 'c': 3}


def test_levels_distribution_reasonable_on_simulated_wall():
    records, cfg, _ = simulate_wall()
    counts = {lv: 0 for lv in (*LEVELS, 'open')}
    for inputs in records.values():
        agg = scoring.aggregate(inputs, cfg, NOW)
        counts[scoring.level(agg.s, agg.weighted_n, None, cfg, raw_n=agg.n).level] += 1
    assert counts['P5'] + counts['P1'] < counts['P4'] + counts['P2'] + counts['P3']
    assert sum(counts.values()) == 1000
