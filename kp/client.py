import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from .cache import gfz_cache, noaa_cache
from .models import KpReading, KpResponse

GFZ_URL = "https://kp.gfz.de/app/json/"
NOAA_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"

_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


async def fetch_gfz(days_back: int = 7) -> KpResponse:
    """Fetch historical KP data from GFZ Potsdam (no auth required)."""
    cache_key = f"gfz_{days_back}"
    cached = gfz_cache.get(cache_key)
    if cached:
        return cached

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    params = {
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "index": "Kp",
    }
    client = await _get_client()
    response = await client.get(GFZ_URL, params=params)
    response.raise_for_status()
    data = response.json()

    readings: list[KpReading] = []
    for ts, kp_val, status in zip(data["datetime"], data["Kp"], data["status"]):
        try:
            readings.append(
                KpReading(
                    timestamp=datetime.fromisoformat(ts.replace("Z", "+00:00")),
                    kp=float(kp_val),
                    source="gfz",
                    status=status,
                )
            )
        except (ValueError, TypeError):
            continue

    result = KpResponse(readings=readings, fetched_at=datetime.now(timezone.utc))
    gfz_cache.set(cache_key, result)
    return result


async def fetch_noaa_realtime() -> KpResponse:
    """Fetch recent real-time KP data from NOAA SWPC (3-hour intervals)."""
    cached = noaa_cache.get("noaa_realtime")
    if cached:
        return cached

    client = await _get_client()
    response = await client.get(NOAA_URL)
    response.raise_for_status()
    raw = response.json()

    # NOAA format: first row is header ["time_tag", "Kp", "a_running", "station_count"]
    readings: list[KpReading] = []
    for row in raw[1:]:
        try:
            if row[1] is None:
                continue
            kp_val = float(row[1])
            # NOAA uses -1 as a sentinel for missing/unavailable data
            if kp_val < 0:
                continue
            ts = datetime.fromisoformat(row[0])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            readings.append(
                KpReading(
                    timestamp=ts,
                    kp=kp_val,
                    source="noaa",
                    status="real-time",
                )
            )
        except (ValueError, TypeError, IndexError):
            continue

    result = KpResponse(readings=readings, fetched_at=datetime.now(timezone.utc))
    noaa_cache.set("noaa_realtime", result)
    return result


def _round_to_3h(dt: datetime) -> datetime:
    """Round a datetime down to the nearest 3-hour boundary (UTC)."""
    hour = (dt.hour // 3) * 3
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0)


async def fetch_merged(days_back: int = 7) -> KpResponse:
    """
    Merge GFZ historical + NOAA real-time data.
    NOAA readings overwrite GFZ for the same 3-hour window (more current).
    Falls back gracefully if one source is unavailable.
    """
    results = await asyncio.gather(
        fetch_gfz(days_back),
        fetch_noaa_realtime(),
        return_exceptions=True,
    )

    gfz_result = results[0] if not isinstance(results[0], Exception) else None
    noaa_result = results[1] if not isinstance(results[1], Exception) else None

    if gfz_result is None and noaa_result is None:
        # Both failed — re-raise the GFZ error as it is usually more descriptive
        raise results[0]

    # Merge: key by 3h-rounded timestamp; NOAA overwrites GFZ for the same slot
    seen: dict[datetime, KpReading] = {}
    if gfz_result is not None:
        for r in gfz_result.readings:
            seen[_round_to_3h(r.timestamp)] = r
    if noaa_result is not None:
        for r in noaa_result.readings:
            seen[_round_to_3h(r.timestamp)] = r

    merged = sorted(seen.values(), key=lambda r: r.timestamp)
    return KpResponse(readings=merged, fetched_at=datetime.now(timezone.utc))
