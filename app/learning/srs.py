"""Aralıklı tekrar zamanlaması (SM-2 türevi, açıklanabilir kurallar).

Her kart (kelime + yön) için dört değer tutulur:
- ease: kolaylık katsayısı (başlangıç 2,5; en az 1,3)
- interval_days: bir sonraki tekrara kadar gün sayısı
- repetitions: art arda başarılı tekrar sayısı
- lapses: daha önce bilinen kartın unutulma sayısı

Kullanıcının verdiği cevaba göre:
- AGAIN  (bilemedim): kart 10 dakika sonra yeniden sorulur, art arda sayaç sıfırlanır, ease 0,20 düşer.
- HARD   (zor):       aralık hafifçe artar (×1,2), ease 0,15 düşer.
- GOOD   (bildim):    1 gün → 6 gün → sonrasında aralık × ease.
- EASY   (kolay):     4 gün → sonrasında aralık × ease × 1,3; ease 0,15 artar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

AGAIN, HARD, GOOD, EASY = 0, 1, 2, 3
GRADES = (AGAIN, HARD, GOOD, EASY)

DEFAULT_EASE = 2.5
MIN_EASE = 1.3
MAX_INTERVAL_DAYS = 365
AGAIN_DELAY = timedelta(minutes=10)
LEARNED_INTERVAL_DAYS = 21      # bu aralığa ulaşan kart "iyi öğrenildi" sayılır
LONG_TERM_INTERVAL_DAYS = 60    # "uzun süredir doğru cevaplanan"
DIFFICULT_LAPSES = 3            # bu kadar unutulan kart "sık yanlış yapılan" sayılır


@dataclass(frozen=True)
class CardState:
    ease: float = DEFAULT_EASE
    interval_days: int = 0
    repetitions: int = 0
    lapses: int = 0


def schedule(state: CardState, grade: int, now: datetime) -> tuple[CardState, datetime]:
    """Cevaba göre kartın yeni durumunu ve bir sonraki tekrar zamanını hesaplar."""
    if grade not in GRADES:
        raise ValueError(f"Geçersiz not: {grade}")

    if grade == AGAIN:
        new_state = CardState(
            ease=max(MIN_EASE, round(state.ease - 0.20, 2)),
            interval_days=0,
            repetitions=0,
            lapses=state.lapses + (1 if state.repetitions > 0 else 0),
        )
        return new_state, now + AGAIN_DELAY

    ease = state.ease
    if grade == HARD:
        ease = max(MIN_EASE, round(ease - 0.15, 2))
        interval = 1 if state.interval_days == 0 else max(state.interval_days + 1, round(state.interval_days * 1.2))
    elif grade == GOOD:
        if state.repetitions == 0:
            interval = 1
        elif state.repetitions == 1:
            interval = max(6, state.interval_days + 1)
        else:
            interval = max(state.interval_days + 1, round(state.interval_days * ease))
    else:  # EASY
        ease = round(ease + 0.15, 2)
        if state.repetitions == 0:
            interval = 4
        else:
            interval = max(state.interval_days + 1, round(max(state.interval_days, 6) * ease * 1.3))

    interval = min(interval, MAX_INTERVAL_DAYS)
    new_state = CardState(ease=ease, interval_days=interval, repetitions=state.repetitions + 1, lapses=state.lapses)
    return new_state, now + timedelta(days=interval)


def bucket(state: CardState) -> str:
    """Kartın öğrenme aşaması: learning (öğreniliyor), learned (iyi öğrenildi), long_term."""
    if state.interval_days >= LONG_TERM_INTERVAL_DAYS:
        return "long_term"
    if state.interval_days >= LEARNED_INTERVAL_DAYS:
        return "learned"
    return "learning"
