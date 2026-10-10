from datetime import UTC, datetime


def get_utc_now() -> datetime:
    return datetime.now(UTC)


def get_billing_period_bounds(period_start: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Get the UTC calendar month bounds for a given date.
    If no date provided, uses current UTC time.

    Returns (period_start, period_end) where:
    - period_start: First day of month at 00:00:00 UTC
    - period_end: First day of next month at 00:00:00 UTC (exclusive)

    This implements the canonical UTC calendar-month billing policy.
    """
    dt = period_start or get_utc_now()

    # Start of current month in UTC
    start = datetime(dt.year, dt.month, 1, tzinfo=UTC)

    # Start of next month in UTC (exclusive end)
    if dt.month == 12:
        end = datetime(dt.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(dt.year, dt.month + 1, 1, tzinfo=UTC)

    return start, end


def get_current_billing_period() -> tuple[datetime, datetime]:
    """Get the current UTC calendar month billing period bounds."""
    return get_billing_period_bounds()


def is_within_billing_period(dt: datetime, period_start: datetime, period_end: datetime) -> bool:
    """Check if a datetime falls within a billing period (inclusive start, exclusive end)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return period_start <= dt < period_end
