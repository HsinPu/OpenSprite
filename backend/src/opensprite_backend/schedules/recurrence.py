"""Timezone-aware once, daily, and weekly recurrence calculation."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import Cadence, CadenceType


class RecurrenceError(ValueError):
    pass


def require_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise RecurrenceError("invalid_time_zone") from None


def next_occurrence(cadence: Cadence, time_zone: str, after: datetime) -> datetime | None:
    if after.tzinfo is None:
        raise RecurrenceError("naive_datetime")
    after = after.astimezone(UTC)
    zone = require_zone(time_zone)
    if cadence.type is CadenceType.ONCE:
        if cadence.run_at is None or cadence.run_at.tzinfo is None:
            raise RecurrenceError("invalid_once")
        candidate = cadence.run_at.astimezone(UTC)
        return candidate if candidate > after else None
    if cadence.local_time is None or cadence.local_time.tzinfo is not None:
        raise RecurrenceError("invalid_local_time")
    weekdays = set(cadence.weekdays)
    if cadence.type is CadenceType.WEEKLY and (not weekdays or any(day < 1 or day > 7 for day in weekdays)):
        raise RecurrenceError("invalid_weekdays")
    start = after.astimezone(zone).date()
    for offset in range(0, 370):
        day = start + timedelta(days=offset)
        if cadence.type is CadenceType.WEEKLY and day.isoweekday() not in weekdays:
            continue
        candidate = _resolve_local(day, cadence.local_time, zone)
        if candidate > after:
            return candidate
    raise RecurrenceError("recurrence_not_found")


def occurrences_between(cadence: Cadence, time_zone: str, start_exclusive: datetime, end_inclusive: datetime, *, limit: int = 10_000) -> tuple[datetime, ...]:
    items: list[datetime] = []
    current = start_exclusive
    while len(items) < limit:
        candidate = next_occurrence(cadence, time_zone, current)
        if candidate is None or candidate > end_inclusive.astimezone(UTC):
            return tuple(items)
        items.append(candidate)
        current = candidate
    raise RecurrenceError("occurrence_limit")


def _resolve_local(day: date, local_time, zone: ZoneInfo) -> datetime:
    naive = datetime.combine(day, local_time)
    for minute in range(0, 181):
        shifted = naive + timedelta(minutes=minute)
        candidates: list[datetime] = []
        for fold in (0, 1):
            aware = shifted.replace(tzinfo=zone, fold=fold)
            utc = aware.astimezone(UTC)
            if utc.astimezone(zone).replace(tzinfo=None) == shifted:
                candidates.append(utc)
        if candidates:
            return min(candidates)
    raise RecurrenceError("invalid_local_time")
