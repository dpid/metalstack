"""Metals.Dev API client for precious metal prices."""

import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from .models import MetalPrice, MetalType, TimePeriod

BASE_URL = "https://api.metals.dev/v1"
CACHE_DIR = Path.home() / ".cache" / "metalstack"
DEFAULT_CACHE_TTL_SECONDS = 3600  # Default: 1 hour


class MetalsAPIError(Exception):
    """Error from the Metals.Dev API."""


class MetalsAPI:
    """Client for the Metals.Dev API."""

    def __init__(self, api_key: str | None = None, cache_ttl: int | None = None):
        self.api_key = api_key or os.environ.get("METALS_API_KEY", "")
        if not self.api_key:
            raise MetalsAPIError(
                "API key required. Set METALS_API_KEY environment variable "
                "or pass api_key to constructor. Get a free key at https://metals.dev"
            )

        # Cache TTL: constructor arg > env var > default (1 hour)
        if cache_ttl is not None:
            self.cache_ttl = cache_ttl
        else:
            env_ttl = os.environ.get("METALS_CACHE_TTL")
            self.cache_ttl = int(env_ttl) if env_ttl else DEFAULT_CACHE_TTL_SECONDS

        self._client = httpx.Client(timeout=30.0)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, endpoint: str, params: dict) -> Path:
        """Generate cache file path for a request."""
        safe_endpoint = endpoint.replace("/", "_")
        # Use deterministic hash (sorted JSON) instead of Python's randomized hash()
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]
        cache_key = f"{safe_endpoint}_{params_hash}"
        return CACHE_DIR / f"{cache_key}.json"

    def _get_cached(self, cache_path: Path) -> dict | None:
        """Get cached response if valid."""
        if not cache_path.exists():
            return None
        try:
            data = json.loads(cache_path.read_text())
            cached_at = datetime.fromisoformat(data.get("_cached_at", ""))
            if datetime.now() - cached_at < timedelta(seconds=self.cache_ttl):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def _save_cache(self, cache_path: Path, data: dict) -> None:
        """Save response to cache."""
        data["_cached_at"] = datetime.now().isoformat()
        cache_path.write_text(json.dumps(data))

    def _request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make API request with caching."""
        params = params or {}
        params["api_key"] = self.api_key

        cache_path = self._get_cache_path(endpoint, params)
        cached = self._get_cached(cache_path)
        if cached:
            return cached

        url = f"{BASE_URL}/{endpoint}"
        response = self._client.get(url, params=params)

        if response.status_code != 200:
            raise MetalsAPIError(f"API error {response.status_code}: {response.text}")

        data = response.json()
        self._save_cache(cache_path, data)
        return data

    def get_latest_prices(self) -> dict[MetalType, MetalPrice]:
        """Get latest spot prices for all precious metals."""
        data = self._request("latest", {"currency": "USD", "unit": "toz"})

        metals = data.get("metals", {})
        result = {}

        for metal_type in MetalType:
            price = metals.get(metal_type.value, 0)
            result[metal_type] = MetalPrice(
                metal=metal_type,
                spot=price,
                change=0.0,
                change_pct=0.0,
            )

        return result

    def get_metal_spot(self, metal: MetalType) -> MetalPrice:
        """Get detailed spot data for a specific metal."""
        data = self._request("metal/spot", {"metal": metal.value, "currency": "USD"})
        rate = data.get("rate", {})

        return MetalPrice(
            metal=metal,
            spot=rate.get("price", 0),
            bid=rate.get("bid"),
            ask=rate.get("ask"),
            change=rate.get("change", 0),
            change_pct=rate.get("change_percent", 0),
        )

    def get_historical_prices(
        self, metal: MetalType, period: TimePeriod
    ) -> list[tuple[str, float]]:
        """Get historical prices for charting.

        Returns list of (date_string, price) tuples.
        """
        end_date = datetime.now()
        start_date = self._get_start_date(period, end_date)

        # API limits to 30 days per request, so we may need multiple requests
        all_prices = []
        current_end = end_date

        while current_end > start_date:
            current_start = max(start_date, current_end - timedelta(days=30))

            data = self._request(
                "timeseries",
                {
                    "start_date": current_start.strftime("%Y-%m-%d"),
                    "end_date": current_end.strftime("%Y-%m-%d"),
                    "currency": "USD",
                    "unit": "toz",
                },
            )

            rates = data.get("rates", {})
            for date_str in sorted(rates.keys()):
                price = rates[date_str].get("metals", {}).get(metal.value, 0)
                if price:
                    all_prices.append((date_str, price))

            current_end = current_start - timedelta(days=1)

        return sorted(all_prices, key=lambda x: x[0])

    def _get_start_date(self, period: TimePeriod, end_date: datetime) -> datetime:
        """Calculate start date for a time period."""
        match period:
            case TimePeriod.DAY:
                return end_date - timedelta(days=1)
            case TimePeriod.THREE_DAYS:
                return end_date - timedelta(days=3)
            case TimePeriod.WEEK:
                return end_date - timedelta(weeks=1)
            case TimePeriod.MONTH:
                return end_date - timedelta(days=30)
            case TimePeriod.YTD:
                return datetime(end_date.year, 1, 1)
            case TimePeriod.YEAR:
                return end_date - timedelta(days=365)
            case TimePeriod.FIVE_YEARS:
                return end_date - timedelta(days=365 * 5)
            case TimePeriod.ALL:
                return end_date - timedelta(days=365 * 30)
