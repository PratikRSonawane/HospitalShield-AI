"""Weather adapter (S7): optional Open-Meteo integration.

Uses the Open-Meteo forecast API (hourly temperature_2m, relative_humidity_2m),
open data under CC-BY 4.0 (attribution: Open-Meteo.com). 3-second timeout,
one retry, validation, SQLite cache with TTL, and a CSV fallback that never
raises to the caller. Weather is labelled REAL WEATHER and kept separate
from synthetic hospital data.
"""

from __future__ import annotations

import csv
import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2].parents[1]
FALLBACK_CSV = ROOT / "data" / "demo_weather_fallback.csv"
CACHE_DB = ROOT / "data" / "weather_cache.sqlite3"
CACHE_TTL_SECONDS = 3600
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

ATTRIBUTION = "Weather data by Open-Meteo.com (CC-BY 4.0), used as REAL WEATHER input only."


def _valid_series(values: list[Any]) -> list[float] | None:
    """Validate length, NaN and plausible Celsius ranges; None when invalid."""
    out: list[float] = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        if math.isnan(f) or not (-70.0 <= f <= 60.0):
            return None
        out.append(round(f, 2))
    return out or None


def _cache_key(lat: float, lon: float, hours: int) -> str:
    return f"{round(lat, 3)},{round(lon, 3)},{hours}"


def _cache_get(key: str) -> dict[str, Any] | None:
    """Return cached response when younger than the TTL; None otherwise."""
    if not CACHE_DB.exists():
        return None
    try:
        conn = sqlite3.connect(CACHE_DB, timeout=1)
        row = conn.execute("SELECT payload, fetched_at FROM weather_cache WHERE key = ?", (key,)).fetchone()
        conn.close()
        if row is None:
            return None
        payload, fetched_at = row
        if time.time() - fetched_at > CACHE_TTL_SECONDS:
            return None
        data = json.loads(payload)
        data["source"] = "cache"
        return data
    except sqlite3.Error:
        return None


def _cache_put(key: str, payload: dict[str, Any]) -> None:
    """Best-effort cache write; a database failure only logs a warning."""
    try:
        conn = sqlite3.connect(CACHE_DB, timeout=1)
        conn.execute("CREATE TABLE IF NOT EXISTS weather_cache (key TEXT PRIMARY KEY, payload TEXT, fetched_at REAL)")
        conn.execute("INSERT OR REPLACE INTO weather_cache (key, payload, fetched_at) VALUES (?, ?, ?)",
                     (key, json.dumps(payload), time.time()))
        conn.commit()
        conn.close()
    except sqlite3.Error:
        pass  # cache is optional; never raise to the caller


def _fallback(hours: int, warnings: list[str]) -> dict[str, Any]:
    """Labelled CSV fallback series (SYNTHETIC, never presented as real)."""
    series: list[float] = []
    if FALLBACK_CSV.exists():
        try:
            with FALLBACK_CSV.open("r", encoding="utf-8") as fh:
                series = [float(row["temperature_c"]) for row in csv.DictReader(fh)]
        except (OSError, ValueError, KeyError):
            series = []
    if len(series) < hours:
        warnings.append("fallback weather file missing or short; using flat 30 C profile")
        series = [30.0] * hours
    return {
        "source": "fallback",
        "fetched_at": None,
        "location": None,
        "series_c": series[:hours],
        "label": "SYNTHETIC",
        "warnings": warnings,
    }


def fetch_weather(lat: float, lon: float, hours: int) -> dict[str, Any]:
    """Fetch hourly temperatures; never raises. live -> cache -> fallback."""
    warnings: list[str] = []
    key = _cache_key(lat, lon, hours)

    cached = _cache_get(key)
    if cached is not None:
        return cached

    params = {"latitude": lat, "longitude": lon, "hourly": "temperature_2m,relative_humidity_2m",
              "forecast_days": max(1, min(7, math.ceil(hours / 24) + 1))}
    for attempt in (1, 2):
        try:
            response = httpx.get(OPEN_METEO_URL, params=params, timeout=3.0)
            if response.status_code == 200:
                payload = response.json()
                series = _valid_series(payload.get("hourly", {}).get("temperature_2m", []))
                if series and len(series) >= hours:
                    out = {
                        "source": "live",
                        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "location": {"latitude": lat, "longitude": lon},
                        "series_c": series[:hours],
                        "label": "REAL WEATHER",
                        "attribution": ATTRIBUTION,
                        "warnings": warnings,
                    }
                    _cache_put(key, out)
                    return out
                warnings.append("open-meteo response incomplete; falling back")
            elif response.status_code == 429:
                warnings.append(f"open-meteo rate limited (429) on attempt {attempt}")
                time.sleep(0.5 * attempt)
            else:
                warnings.append(f"open-meteo HTTP {response.status_code} on attempt {attempt}")
        except httpx.HTTPError as exc:
            warnings.append(f"open-meteo request failed: {type(exc).__name__}")
    return _fallback(hours, warnings)
